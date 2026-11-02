# 参展关系表改造报告（`exhibition_exhibitors`）

> 范围：`X-Expohub/expohub-backend`（SQLite `expohub-backend/expohub.db`）
> 目标：把「弱三层」`catalog_exhibitors.exhibition_id`（48.8% 有值）+ `expo_name` 字符串别名补齐，
> 改成「干净的多对多参展关系」表，并让展会详情页三个端点只从关系表取数。
> 执行日期：2026-10-19 · 全部脚本真跑过（含真实迁移与回填，写前已备份）

---

## 0. 结论（TL;DR）

| 项目 | 结果 |
|---|---|
| 新表 `exhibition_exhibitors` | 已建（6 列 / 1 唯一约束 / 2 索引 / 2 外键），回填 **27,685** 行 |
| 12 场展会「展商数 / 展品数」 | 与改造前基线 **逐场完全一致，差异 0**（集合级对称差也是 0） |
| 三端点实测 `/stats`、`/exhibitors`、`/products` | 12 场 × 3 = **36 个请求全部 200**；分页/字段/`total` 全部不变 |
| 别名逻辑 `_catalog_expo_aliases` | **已删除**（原 `exhibitions.py` L501 / L528 / L542 及 3 处调用） |
| 无法映射的 `expo_name` | 3 个 / **4,253** 行（CIOE 3,209、CMES 华机展 522、CMES 华机展 · 青岛 522）→ 不产生关系，只进报告 |
| 备份 | `expohub.db.bak-20261019-180251`（**回填前**，109.8 MB，integrity_check=ok）<br>`…-180316` / `…-180726`（之后两次幂等重跑的"写前"备份，112.5 MB，内容与回填后一致） |
| 回归测试 | `pytest -q` → **95 passed**；`tests/test_exhibitions_timeline_exhibitors.py` → 3 passed |
| 未做 | 不 git、不装依赖、不重启 8002/5173、不动前端 |

---

## 1. 交付文件

| 文件 | 作用 |
|---|---|
| `expohub-backend/app/models/exhibition_exhibitor.py` | 新模型 `ExhibitionExhibitor`（含设计口径注释） |
| `expohub-backend/app/models/__init__.py` | 导出 `ExhibitionExhibitor`（+ `__all__`） |
| `expohub-backend/app/main.py` | 启动时显式 import（`create_all` 能建表；pytest 隔离库同样生效） |
| `expohub-backend/scripts/migrate_exhibition_exhibitors.py` | 幂等建表 DDL 脚本，`--db` / `--dry-run`，自带「DDL 与模型一致」自检 |
| `expohub-backend/scripts/backfill_exhibition_exhibitors.py` | 回填脚本：规范化映射 + 备份 + `--apply`/`--db`/`--match-mode`/`--report` |
| `expohub-backend/app/modules/expo/exhibitions.py` | 三个端点改为关系表 join；删除别名逻辑 |
| `reports/exhibition_exhibitors_backfill.txt` | 脚本生成的报告（最后一次 `--apply` 的幂等验证输出：插入 0 行） |
| `reports/exhibition_exhibitors_backfill_dryrun.txt` | dry-run 报告原文 |
| `reports/exhibition_exhibitors_verify.txt` | 改造前/后逐场 + 集合级 + 端点 + 分页边界验证输出 |

---

## 2. 新表结构

```sql
CREATE TABLE IF NOT EXISTS exhibition_exhibitors (
	id INTEGER NOT NULL,
	exhibition_id INTEGER NOT NULL,          -- FK exhibitions.id
	catalog_exhibitor_id INTEGER NOT NULL,   -- FK catalog_exhibitors.id
	expo_label VARCHAR(255),                 -- 名录原文展会名（仅追溯/展示，不参与匹配）
	booth_no VARCHAR(64),                    -- 该届展位号
	created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
	PRIMARY KEY (id),
	CONSTRAINT uq_exhibition_exhibitor UNIQUE (exhibition_id, catalog_exhibitor_id),
	FOREIGN KEY(exhibition_id) REFERENCES exhibitions (id),
	FOREIGN KEY(catalog_exhibitor_id) REFERENCES catalog_exhibitors (id)
);
CREATE INDEX IF NOT EXISTS ix_exhibition_exhibitors_exhibition_id       ON exhibition_exhibitors (exhibition_id);
CREATE INDEX IF NOT EXISTS ix_exhibition_exhibitors_catalog_exhibitor_id ON exhibition_exhibitors (catalog_exhibitor_id);
```

- **唯一约束** `(exhibition_id, catalog_exhibitor_id)`：同一展会同一展商只有一条关系；回填用 `INSERT OR IGNORE` ⇒ 重复执行幂等。
- **两个列都建索引**：`exhibition_id`（详情页主查询）、`catalog_exhibitor_id`（反查参展历史 + 展品 join）。
- `expo_label` / `booth_no` 是「该届」的属性，不参与任何匹配；实测 1,955 条关系带非空 `booth_no`，`expo_label` 12 个 distinct 值。
- `created_at` 由 SQLite `CURRENT_TIMESTAMP`（UTC）填充，与既有表一致。

---

## 3. 迁移脚本（幂等）

```powershell
python scripts/migrate_exhibition_exhibitors.py --dry-run   # 只打印 SQL
python scripts/migrate_exhibition_exhibitors.py             # 真建表（本次已执行）
python scripts/migrate_exhibition_exhibitors.py --db path/to/expohub.db
```

真实执行输出（摘要）：

```
[--] 现有表 29 张；现有索引 95 个
[OK] 建表：exhibition_exhibitors
[OK] 建索引：ix_exhibition_exhibitors_exhibition_id
[OK] 建索引：ix_exhibition_exhibitors_catalog_exhibitor_id
     exhibition_exhibitors: 6 列 ['id','exhibition_id','catalog_exhibitor_id','expo_label','booth_no','created_at']
     exhibition_exhibitors: 3 个索引 ['ix_..._catalog_exhibitor_id','ix_..._exhibition_id','sqlite_autoindex_..._1']
     exhibition_exhibitors: 外键 [('catalog_exhibitors','catalog_exhibitor_id','id'), ('exhibitions','exhibition_id','id')]
     exhibition_exhibitors: 行数 0 -> 0（本脚本不写数据）
[OK] DDL 自检：脚本 DDL 与 app/models/exhibition_exhibitor.py 完全一致
```

再跑一次：`表已存在，跳过建表` / `新建索引 0 个` ⇒ 幂等。

---

## 4. 回填：映射规则与执行

### 4.1 映射不写死展会名（三层规范化）

映射两边的数据都只来自库里：`catalog_exhibitors.expo_name` ↔ `exhibitions.title`。

| 层 | 规则 | 例子 |
|---|---|---|
| `strict` | `normalize(x)` 后相等。normalize = NFKC 全半角归一 → `\|` 换 `·` → 去所有空白 → 小写 → 反复去尾部括号后缀 | `CMES 华机展 · 东莞` ↔ `CMES 华机展 · 东莞` |
| `loose` | strict 再剥：`第…届` 序号前缀、通用修饰词（中国/国际/全国）、开头的全大写英文缩写（CMEF/NHNE/TME…） | `CMEF 中国国际医疗器械博览会` ↔ `第九十四届中国国际医疗器械博览会（CMEF）` |
| `alias` | 括号内容当别名双向匹配 | 标题尾部 `（高交会）` ↔ 名录 `高交会（CHTF）` |

> ⚠️ 纯严格相等只覆盖 8 / 12 场：会被判"映射不上"的是 CMEF(13,306)、NHNE(760)、高交会(1,810)、玉环(403)，
> 详情页会从 1.3 万家掉到 0。因此**默认 `layered`**；`--match-mode strict` 可复现纯严格口径（见 §8.1）。
> 这层放宽是本报告最需要你复核的决定。

### 4.2 映射明细（实跑 `layered`）

| expo_name | 名录行数 | 匹配层 | → 展会 | 说明 |
|---|---:|---|---:|---|
| CMEF 中国国际医疗器械博览会 | 13,306 | loose | 9 | 唯一命中 |
| CIOE 中国国际光电博览会 | 3,209 | **未命中** | — | `exhibitions` 里没有光博会 |
| CMES 华机展 · 东莞 | 3,070 | strict | 7 | |
| CMES 华机展 · 上海 | 2,497 | strict | 11 | |
| 高交会（CHTF） | 1,810 | alias | 10 | 标题尾部 `（高交会）` |
| CMES 华机展 · 苏州 | 1,404 | strict | 13 | |
| CMES 华机展 · 宁波 | 1,230 | strict | 6 | |
| CMES 华机展 · 天津 | 1,091 | strict | 5 | |
| CMES 华机展 · 佛山 | 969 | strict | 4 | |
| CMES 华机展 · 西安 | 860 | strict | 12 | |
| NHNE 中国国际健康营养博览会 | 760 | loose | 8 | 去 中国/国际 + 英文缩写 |
| CMES 华机展 | 522 | **未命中** | — | 集团级"总称"，不该摊到任何一届 |
| CMES 华机展 · 青岛 | 522 | **未命中** | — | `exhibitions` 里没有青岛场 |
| 玉环机床展 | 403 | loose | 14 | 标题 `玉环**国际**机床展`，去修饰词后相等 |
| TME台州机床展 | 285 | strict | 15 | 去空白后相等 |

- 可映射：12 个 `expo_name` → 27,685 行展商
- 无法映射：3 个 → 4,253 行（不产生关系）
- 关系总数 = 27,685 = 31,938 − 4,253（每个命中展商按其 `expo_name` 生成恰好一条）

### 4.3 执行与备份

```powershell
python scripts/backfill_exhibition_exhibitors.py            # 默认 dry-run
python scripts/backfill_exhibition_exhibitors.py --apply    # 写库（写前自动备份）
```

第 1 次 `--apply` 关键输出：

```
[OK] 已备份：...\expohub-backend\expohub.db.bak-20261019-180251
     （109.8 MB，integrity_check=ok，catalog_exhibitors=31,938、catalog_products=67,357、exhibitions=12）
- 本次插入：27,685 行（已存在而被忽略：0 行）
- exhibition_exhibitors 当前总行数：27,685（推算 27,685，一致）
- 唯一约束自检：重复 (exhibition_id, catalog_exhibitor_id) 组数 = 0
- 外键自检（PRAGMA foreign_key_check(exhibition_exhibitors)）违规 = 0 条
- 全库外键检查：25 条历史遗留违规（points_ledger 16 / memberships 9 → users），与本表无关
- expo_label 为空的行：0
```

第 2、3 次 `--apply`（幂等验证，脚本已是最终版本）：`本次插入 0 行（已存在而被忽略 27,685 行）`，
总行数仍 27,685，`推算 vs 实际：全部一致`（见 `reports/exhibition_exhibitors_backfill.txt`）。
回填只做 SELECT/INSERT，**没有 DELETE / UPDATE**；`catalog_exhibitors.exhibition_id` 等遗留列原样保留。

---

## 5. 端点改造（`app/modules/expo/exhibitions.py`）

### 5.1 新口径

```
exhibitions 1 ──< exhibition_exhibitors >── 1 catalog_exhibitors ──< catalog_products
```

| 端点 | 改造前 | 改造后 |
|---|---|---|
| `GET /exhibitions/{id}/stats` | `catalog_exhibitors.exhibition_id = ?` **OR** `expo_name IN (别名)` | `exhibition_exhibitors` join `catalog_exhibitors`（展商/城市/行业）+ join `catalog_products`（展品） |
| `GET /exhibitions/{id}/exhibitors` | 同上（条件复用） | `exhibition_exhibitors` JOIN `catalog_exhibitors`，排序 `product_count DESC, id ASC` 不变 |
| `GET /exhibitions/{id}/products` | `catalog_products JOIN catalog_exhibitors` + 同一 condition | `exhibition_exhibitors` JOIN `catalog_products`（`exhibitor_id`），`ORDER BY id` 不变 |

保留：响应字段（`exhibitor_id/name/industry/city/product_count/source`、`id/name/category/image/exhibitor_name/source`）、
分页参数（`page`/`page_size`，上限 100）、`_paginated_response`（`list/total/page/pageSize/totalPages`）、
404 语义、以及「名录无数据时回落 booths / products 表」（平台自建展会仍能出数，测试依赖）。
路由顺序不变：`/{exhibition_id}/stats|products|exhibitors` 都定义在 `/{exhibition_id}`（L810）之前。

### 5.2 被删掉的别名逻辑位置（改造前文件行号）

| 位置 | 内容 |
|---|---|
| L481–L498 | 注释块「ID 优先 + 名录别名补齐」口径说明 |
| L501–L525 | `_catalog_expo_aliases()`：从库里学 `expo_name` → 只归属单一展会的别名 |
| L528–L539 | `_catalog_scope()`：`exhibition_id == id OR expo_name IN aliases` |
| L542–L577 | `_catalog_stats()`：带别名的聚合 |
| L613 / L638 / L722 | 三个端点里的 `_, condition = _catalog_scope(...)` 调用 |

替换为：`_relation_exhibitor_total()` / `_relation_product_total()` / `_relation_stats()`（见 L511 / L525 / L543）。
现在整段只在新注释里提到旧函数名（说明"为什么删"），`ast` 自检确认 `_catalog_expo_aliases`、`_catalog_scope`、
`_catalog_stats` **既无定义也无调用**：

```
deleted funcs confirmed absent: ['_catalog_expo_aliases', '_catalog_scope', '_catalog_stats']
new funcs present: ['_relation_exhibitor_total', '_relation_product_total', '_relation_stats']
stray calls referenced: not in fns
```

---

## 6. 验证

### 6.1 12 场展会逐场对比（基线 vs 改造后，端点实测）

基线 = 改造前在 8012 端口实测的三端点数值（与任务书给的基线逐项一致）。

| ID | 展会 | 基线 展商/展品 | 改造后 展商/展品 | 差异 | 差异解释 |
|---:|---|---|---|---:|---|
| 4 | CMES 华机展 · 佛山 | 969 / 574 | 969 / 574 | 0 / 0 | 关系与旧口径集合完全相同 |
| 5 | CMES 华机展 · 天津 | 1,091 / 499 | 1,091 / 499 | 0 / 0 | 同上 |
| 6 | CMES 华机展 · 宁波 | 1,230 / 552 | 1,230 / 552 | 0 / 0 | 同上 |
| 7 | CMES 华机展 · 东莞 | 3,070 / 1,529 | 3,070 / 1,529 | 0 / 0 | 同上 |
| 8 | 中国国际健康营养博览会（NHNE） | 760 / 0 | 760 / 0 | 0 / 0 | 展商经 loose 层映射到 8；名录里这批展商确实没有展品，端点走 products 表回落也仍为 0（与基线同） |
| 9 | 第九十四届 CMEF | 13,306 / 36,999 | 13,306 / 36,999 | 0 / 0 | 旧实现的 11,332 行是靠别名补齐，本次改为显式关系（loose 层映射） |
| 10 | 第二十八届高交会 | 1,810 / 4,764 | 1,810 / 4,764 | 0 / 0 | 别名层：标题 `（高交会）` ↔ 名录 `高交会（CHTF）` |
| 11 | CMES 华机展 · 上海 | 2,497 / 2,065 | 2,497 / 2,065 | 0 / 0 | 同上（strict） |
| 12 | CMES 华机展 · 西安 | 860 / 412 | 860 / 412 | 0 / 0 | |
| 13 | CMES 华机展 · 苏州 | 1,404 / 949 | 1,404 / 949 | 0 / 0 | |
| 14 | 玉环国际机床展 | 403 / 92 | 403 / 92 | 0 / 0 | loose 层：`玉环机床展` ↔ `玉环**国际**机床展` |
| 15 | TME 台州机床展 | 285 / 608 | 285 / 608 | 0 / 0 | |

**逐场差异全部为 0**。关于任务书里点名的 `CIOE 3,209 行`：它在改造前也没有被算进任何一场展会
（旧别名逻辑同样要求 `expo_name` 已对齐到某场展会），所以它**不出现在任何逐场差值里**；
它的影响只是"这 3,209 家展商没有参展关系、进不了任何详情页"，属预期，已记入 §7。

### 6.2 集合级比对（比数字更严：旧口径 ID 集合 vs 关系表 ID 集合）

| 展会 | 旧展商集合 | 新展商集合 | 对称差 | 旧展品集合 | 新展品集合 | 对称差 |
|---:|---:|---:|---:|---:|---:|---:|
| 4 | 969 | 969 | 0 | 574 | 574 | 0 |
| 5 | 1,091 | 1,091 | 0 | 499 | 499 | 0 |
| 6 | 1,230 | 1,230 | 0 | 552 | 552 | 0 |
| 7 | 3,070 | 3,070 | 0 | 1,529 | 1,529 | 0 |
| 8 | 760 | 760 | 0 | 0 | 0 | 0 |
| 9 | 13,306 | 13,306 | 0 | 36,999 | 36,999 | 0 |
| 10 | 1,810 | 1,810 | 0 | 4,764 | 4,764 | 0 |
| 11 | 2,497 | 2,497 | 0 | 2,065 | 2,065 | 0 |
| 12 | 860 | 860 | 0 | 412 | 412 | 0 |
| 13 | 1,404 | 1,404 | 0 | 949 | 949 | 0 |
| 14 | 403 | 403 | 0 | 92 | 92 | 0 |
| 15 | 285 | 285 | 0 | 608 | 608 | 0 |

⇒ 不只是计数相同，**命中的展商/展品 ID 集合完全相同**（12 场全部对称差 0）。

### 6.3 DB 分布（Python `sqlite3` 模块，引擎 3.53.1；机器上没有 `sqlite3.exe`，SQL 一致）

```
SELECT COUNT(*) FROM exhibition_exhibitors;  →  27,685

SELECT exhibition_id, COUNT(*) FROM exhibition_exhibitors GROUP BY exhibition_id ORDER BY exhibition_id;
  exhibition_id=4  rows=969    CMES 华机展 · 佛山
  exhibition_id=5  rows=1091   CMES 华机展 · 天津
  exhibition_id=6  rows=1230   CMES 华机展 · 宁波
  exhibition_id=7  rows=3070   CMES 华机展 · 东莞
  exhibition_id=8  rows=760    中国国际健康营养博览会（NHNE）
  exhibition_id=9  rows=13306  第九十四届中国国际医疗器械博览会（CMEF）
  exhibition_id=10 rows=1810   第二十八届中国国际高新技术成果交易会（高交会）
  exhibition_id=11 rows=2497   CMES 华机展 · 上海
  exhibition_id=12 rows=860    CMES 华机展 · 西安
  exhibition_id=13 rows=1404   CMES 华机展 · 苏州
  exhibition_id=14 rows=403    玉环国际机床展
  exhibition_id=15 rows=285    TME 台州机床展
```

附加自检：

| 检查 | 结果 |
|---|---|
| 无关系的展会数 | 0 |
| 参展多场的展商数（>1 条关系） | **0**（见 §8.2） |
| 无关系的名录展商数 | 4,253（= 31,938 − 27,685） |
| 同一展会内同名展商（潜在重复展示） | 0 组 |
| 带非空 `booth_no` 的关系 | 1,955 条 |
| 索引 | `ix_..._catalog_exhibitor_id`、`ix_..._exhibition_id`、`sqlite_autoindex_...`(唯一约束) |
| 外键违规（仅本表） | 0 |

### 6.4 临时 8012 端口只读实测（验完已 kill）

```
4 200 969 574      9  200 13306 36999
5 200 1091 499     10 200 1810 4764
6 200 1230 552     11 200 2497 2065
7 200 3070 1529    12 200 860 412
8 200 760 0        13 200 1404 949
                   14 200 403 92
                   15 200 285 608
```

响应样例（改造后，8012）：

```json
### GET /exhibitions/9/stats  →  HTTP 200
{ "success": true, "code": "OK", "message": "获取成功",
  "data": { "exhibitors": 13306, "products": 36999, "cities": 1, "industries": 22 } }

### GET /exhibitions/4/exhibitors?page=1&page_size=2  →  HTTP 200
{ "success": true, "code": "OK", "message": "获取成功",
  "data": { "list": [
      { "exhibitor_id": 8,  "name": "东莞市鼎盛节能设备有限公司", "industry": "家用电器",
        "city": "佛山", "product_count": 8, "source": "catalog" },
      { "exhibitor_id": 93, "name": "广东广船国际电梯有限公司", "industry": "机床工具",
        "city": "佛山", "product_count": 8, "source": "catalog" } ],
    "total": 969, "page": 1, "pageSize": 2, "totalPages": 485 } }

### GET /exhibitions/9/products?page=1&page_size=2  →  HTTP 200
{ "success": true, "code": "OK", "message": "获取成功",
  "data": { "list": [
      { "id": 17874, "name": "RCM-605系列高端移动C形臂X射线机", "category": "摄影X射线机",
        "image": "", "exhibitor_name": "大为医疗（江苏）有限公司", "source": "catalog" },
      { "id": 17875, "name": "RD-550系列便携式DR", "category": "摄影X射线机",
        "image": "", "exhibitor_name": "大为医疗（江苏）有限公司", "source": "catalog" } ],
    "total": 36999, "page": 1, "pageSize": 2, "totalPages": 18500 } }
```

分页/边界实测（全部 200，语义与改造前一致）：

| 请求 | 结果 |
|---|---|
| `/exhibitions/9/exhibitors?page=665&page_size=20`（末页） | 200，total=13,306，list_len=20 |
| `/exhibitions/9/exhibitors?page=700&page_size=20`（超末页） | 200，total=13,306，list_len=0 |
| `/exhibitions/9/products?page=1850&page_size=20` | 200，total=36,999，list_len=19 |
| `/exhibitions/9/products?page=1&page_size=100` | 200，total=36,999，list_len=100 |
| `/exhibitions/8/products`（0 条，走回落） | 200，total=0，list_len=0 |
| `/exhibitions/99999999/{stats,exhibitors,products}` | 404（3/3） |

before/after 逐字段比对：`stats.data` 12 场全等、`exhibitors.products` 的 `total/pageSize/totalPages/首页字段集` 全等，
差异项合计 **0**；36 个请求状态码全 200。验证结束后 `8012` 已关闭（`8002` pid 3200、`5173` pid 14492 未动）。

### 6.5 回归测试

```
python -m pytest tests/test_exhibitions_timeline_exhibitors.py -q   →  3 passed
python -m pytest -q                                                 →  95 passed, 12 warnings in 30.23s
```

（pytest 用隔离库 `pytest_expohub.db`，不碰真实库；测试验证了「无关系的平台自建展会」仍走 booth 回落。）

---

## 7. 无法映射的 `expo_name` 清单（不硬塞）

| expo_name | 行数 | 原因 | 影响 |
|---|---:|---|---|
| `CIOE 中国国际光电博览会` | 3,209 | `exhibitions` 表里没有光电博览会 | 这 3,209 家展商 / 其展品不进任何展会详情页（改前也一样进不去） |
| `CMES 华机展` | 522 | 集团级"总称"，无城市；摊到 7 场会串展，故不映射 | 522 家展商只在名录里可见 |
| `CMES 华机展 · 青岛` | 522 | `exhibitions` 表里没有青岛场 | 522 家展商只在名录里可见 |
| **合计** | **4,253** | 占名录 13.3% | 关系表 27,685 行 + 4,253 = 31,938 |

想补上时：先在 `exhibitions` 建对应展会记录，再重跑回填脚本即可（幂等，只会新增关系）。

---

## 8. 不确定点 / 需要你拍板的地方

1. **映射层数超出了任务书的"规范化后相等"**（最重要）。
   严格相等只能覆盖 8/12 场：`--match-mode strict` 实测 → 可映射 8 个 `expo_name`、11,406 行，
   剩余 20,532 行映射不上，其中 CMEF **13,306**、高交会 1,810、NHNE 760、玉环 403 会直接掉到 0 家展商。
   我保留了 strict 作为第一层，另加了两层通用规则（去修饰词/序号/英文缩写、括号别名双向匹配），
   使 12 场全部与基线一致；规则是通用的、两侧对称、无写死展会名，并且有"多命中即判歧义、不写入"的保护。
   如果你要"宁可少映射也不放宽"，把默认口径改成 `--match-mode strict` 并重跑回填（需先清理已有关系，脚本目前只增不删）。
2. **本批数据里"同一展商参加多届"没有实例**：`catalog_exhibitors` 的唯一键是 `(expo_name, name)`，
   同一个企业在不同展会=不同行，所以每条行只映射到 1 场，`>1 条关系的展商 = 0`。
   表结构已支持多对多（一个 `catalog_exhibitor_id` 可挂多场），但要在业务上真正体现"同一展商多届"，
   需要先做**企业级去重**（名称规范化 / `name_en` / `website` / 展位号合并）。参考量级：
   当前有 **2,898 个名称** 出现在多个 `expo_name` 下，即 2,898 个企业被按届拆成了多行。
3. **`exhibitions.exhibitor_count` 仍按 booths 计数**（`_exhibition_to_dict`）：`booths` 表为空 ⇒
   展会列表/详情里的 `exhibitor_count` 12 场全是 0。这不属于本次三个端点，未改；建议后续改成
   关系表 COUNT（并保留 booth 回落，否则 `test_exhibitions_timeline_exhibitors.py` 的断言要同步改）。
4. **名录列表接口仍暴露遗留列** `catalog_exhibitors.exhibition_id`（`app/modules/catalog/routes.py:168`
   仍把它放进列表响应；库里 16,353 有值 / 15,585 为 NULL）。若前端用这个字段做"按展会筛名录"，
   口径会和详情页不一致。本次未动（超出范围）。
5. 回填脚本只 `INSERT`、不 `DELETE`：如果以后改映射口径，旧关系不会自动清掉，需要人工或另加 `--reset`。
6. `created_at` 是 SQLite `CURRENT_TIMESTAMP`＝UTC（实测写入 `2026-10-19 10:02:54`，本地 18:02），与既有表口径一致。
7. 机器上没有 `sqlite3.exe`，"sqlite3 查询"是用 Python 标准库 `sqlite3`（3.53.1）执行的，SQL 文本与任务要求一致。
8. 未执行 git 操作、未安装任何依赖；`expohub.db` 已在写前备份（§4.3），可用备份直接回滚。
