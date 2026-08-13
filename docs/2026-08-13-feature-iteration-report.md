# ExpoHub 功能迭代交付报告

> 版本:v1.0 | 日期:2026-08-13
> 范围:展馆系统 / 主办方选馆 / 采购需求增强 / 登录安全修复 / 界面统一
> 提交线:`b67fa41`(最新)→ `1bd66e1` → `ecbf6ff` → `6527bbe` → `ca366be` → ... → `900c019`(安全修复首轮)

---

## 1. 本次迭代总览

| 模块 | 内容 | 状态 |
|---|---|---|
| 展馆系统 | 23 个场馆(官网数据充实)+ 实景图 + 平面图 + 名录页 + 详情页 UI 改版 | ✅ |
| 主办方选馆 | 选馆页(汇总对比)+ 创建展会内嵌对比面板 + 已建展会回填 | ✅ |
| 采购需求 | 底部导航入口 + 分类筛选 + 微展位排版 + 35 条示例数据 + 一页展示 | ✅ |
| 登录安全 | token_version 登出闭环 + 401 拦截器递归修复 | ✅ |
| 界面统一 | 编辑展会页中文化 | ✅ |

## 2. 展馆系统

### 2.1 数据(23 个场馆,20+ 城市)
- 12 个初批 + 10 个第二批(天津/郑州/厦门/苏州/昆明/长沙/宁波/济南/哈尔滨/大连)+ 上海世博中心
- **官网官方信息**(6 个重点场馆,来源标注):国家会展中心(上海)总建筑 150万㎡/进博会举办地(neccsh.com)、国家会议中心(大会堂 6400㎡/ICCA·UFI 会员/cnccchina.com)、厦门国际会展中心(23 展厅/展览面积 20万㎡/xicec.com)、天津国家会展中心(32 无柱展厅/40万㎡/ncectj.com)、广交会展馆(33.8万㎡ A·B·C 区/ciefc.com)、深圳国际会展中心(shenzhen-world.com)
- 更新脚本:`scripts/seed_venues.py`、`scripts/seed_venues_extra.py`、`scripts/update_venue_official.py`、`scripts/update_venue_official2.py`(均幂等)

### 2.2 功能
- **venues API**:列表(城市/关键词筛选)、详情(公开);写操作仅 admin
- **场馆平面图**:12+10 个场馆示意 SVG(点击放大),`scripts/seed_venue_plans.py`
- **场馆实景图**:`image_url` 字段,5 个场馆官网真实图片(国家会展中心上海/国家会议中心/厦门/天津/广交会)
- **展馆名录页** `/venues`:城市 chips + 搜索 + 卡片网格(骨架屏/空状态)
- **展馆详情页** `/venues/:id`:Hero 真实图片背景 + 信息卡片 + 重要信息 + 平面图 + 荣誉(骨架屏/错误状态)
- **展会关联**:创建/编辑展会可选展馆(venue_id 校验),详情返回 venue_info,地点可点击跳转展馆页;已建 5 个展会按 location 回填

## 3. 主办方选馆

- **选馆页** `/organizer/venues`(主办方/管理员):按面积从大到小对比 + 城市筛选 + 实景图缩略 + 交通/荣誉摘要,选馆直达创建展会
- **创建展会内嵌对比面板**:展馆选择下拉旁"🔍 对比挑选"展开内嵌列表(不跳转、表单不丢失),选中自动填充地点
- 工作台新增"🏛️ 展馆选择"入口

## 4. 采购需求增强

- **底部导航**:游客/主办方/管理员组新增"采购需求"Tab(原缺失)
- **分类筛选**:分类 chips(全部 + EXHIBITION_CATEGORIES 16 类),与搜索可组合
- **排版**:采用微展位风格(page-header + 自适应卡片网格 + 卡片样式统一)
- **示例数据**:35 条(26 条新增,覆盖 16 分类、多买家、多状态),`scripts/seed_procurements.py`
- **一页展示**:page_size 50(35 条单页显示,分页自动隐藏)

## 5. 登录安全修复

| 问题 | 修复 |
|---|---|
| **登出闭环缺失**(原 P1 遗留) | token_version 机制:登出递增版本,该用户所有 token(含 refresh)立即失效;新增 `POST /api/auth/logout`;前端主动登出调用后端 |
| **401 拦截器递归回归**(本次引入后修复) | 401 时原调 `userStore.logout()`(会调后端 → token_version 全局递增 → 新登录 token 也被废 + 递归风暴);改为仅本地清理 `localLogout()` + 跳过 logout 请求自身的 401 |

验证:登录 → 接口 200 → 主动登出 200 → 旧 access/refresh 401 → 重新登录 200(全链路通过)

## 6. 界面统一

- 编辑展会页(`ExhibitionEditView`)整体中文化(原为英文,与创建页统一)

## 7. 验证结果

| 层 | 结果 |
|---|---|
| pytest(`tests/test_security_regression.py`) | ✅ 12 passed |
| `scripts/security_verify.py`(API 隔离回归) | ✅ 12/12 ALL PASS |
| `scripts/permissions_verify.py`(权限表) | ✅ 22/22 ALL PASS |
| 前端 vite build | ✅ |
| 服务健康 | 后端 :8002 / 前端 :5173 均 200 |
| 数据完整性 | 展馆 23 / 采购需求 35 / 展会 5 |

## 8. 遗留事项

| 级别 | 事项 |
|---|---|
| 前端 | 126 个既有类型错误(`npm run build` 中 vue-tsc 不绿,dev 不受影响,独立专项) |
| P2 | 租户/组织维度(多主办方共存时需引入) |
| 其他 | 仓库根 `tests/`(旧版 src 后端)与本后端无关;部分展馆无实景图/平面图为示意 |

## 9. 常用命令

```bash
# 启动
cd expohub-backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 8002
cd expo-hub-frontend && npm run dev   # http://localhost:5173

# 数据脚本(均幂等)
python scripts/seed_venues.py            # 首批 12 场馆
python scripts/seed_venues_extra.py      # 第二批 10 场馆
python scripts/seed_venue_plans.py       # 示意平面图
python scripts/update_venue_official.py  # 官网信息(第一批 4 场馆)
python scripts/update_venue_official2.py # 官网信息(第二批 2 场馆)
python scripts/backfill_exhibition_venues.py # 已建展会回填展馆
python scripts/seed_procurements.py      # 采购需求示例数据

# 回归
cd expohub-backend && python -m pytest tests/
cd .. && python scripts/security_verify.py
python scripts/permissions_verify.py
```
