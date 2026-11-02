# ExpoHub — 展会撮合平台 · 状态锚点

> **最后更新**：2026-10-19 ｜ **状态**：进行中（已收缩为两方撮合 · 平台自营展会）
> **规则**：只写代码和文档里**读不出来**的东西。上限 150 行，超了就修剪——细节流到 `docs/`，这里只留指针。

---

## 一句话目标
展前撮合平台：**帮犹豫的展商免费试水 → 看到数据 → 参加线下展会**。
（2026-10-19 起为**两方撮合**：展商 ↔ 采购商；**会展举办方角色取消**，展会由平台自营，观众保留。）
当前工程目标：在 X-Expohub 的功能全集之上，吸收 `exhibition-saas` 的架构范式，**在功能零回退的前提下**重构为多租户、可商业化、AI 原生的完整展会 SaaS。

## 当前阶段
**整合重构 P0–P7 已全部跑完**（2026-09-02 单日完成），之后转入功能补齐与演示打磨。
**2026-10-19：完成「去掉主办方」重构**（详见下方「⚠️ 决策变更」）。

## ⚠️ 决策变更（2026-10-19，用户指示，覆盖原方案）

**去掉会展举办方（organizer），收缩为两方撮合**，展会改「平台自营」：

- 角色枚举收敛为 4 个：`visitor / buyer / exhibitor / admin`；`organizer` 已从 `RoleEnum` 移除
- 展会创建/发布/审批、展位创建/分配、报名名单与导出、票种、现场核销、统计 —— 全部归 `admin`
- 前端 `/organizer/*` 路由整体迁到 `/admin/*`，视图目录 `views/organizer/` → `views/expo-admin/`
- 存量数据迁移：`scripts/migrate_drop_organizer.py`（organizer 账号 → admin；展会归属归一到管理员；补齐 `users.region` 列）
- 被删除的死代码：`utils/role.ts`（旧 boss/organizer 映射，无人引用）、`components/NavBar.vue`（从未挂载）
- `exhibitions.organizer_id / organizer_name`、`users.organizer_status` 作为**历史字段名保留**（SQLite 改列风险大），语义已变：
  - `organizer_id` = 创建人（平台运营账号）；`organizer_name` = 固定「平台运营」
  - `organizer_status` = 入驻/账号审核状态（展商审核仍在用）
- 顺带修掉两个真实缺陷：`users.region` 缺列导致 `GET /exhibitions/{id}/exhibitors` 必 500；
  `DELETE /exhibitions/{id}` 撞外键必 500（现按「展位/报名/评价/预约随展删，展品与采购解绑保留，有已支付订单则拒绝」处理）

**数据抓取（沈建议 2）**：已确认要「后续新增脚本抓取」，本次交付骨架
`scripts/scrape/expo_scraper.py`（默认不联网、不落库，走平台导入接口），方案与红线见
`docs/2026-10-19-数据抓取方案与合规边界.md`。**真站适配器待来源清单确认后再写。**

## 上次停在哪
**2026-09-23：做了「发给领导试用的零安装便携包」**（构建脚本已入库到 `portable/`）。
FastAPI 改成**同源托管前端**（一个端口同时供页面与 `/api`，零 CORS 零代理），
Python 3.13.9 embeddable + 裁剪依赖打包，解压双击即用——不装 Python/Node/Docker、不需联网。
实测首启 4.8s、二次 2s、停止 4.9s；端口被占自动避让；成品 ZIP **35.4MB**（解压后 96MB）。
一键重建：`powershell -File portable\build\build_portable.ps1 -SkipDeps -SkipFrontend`。

🔴 **刻意不改本仓库源码**：同源托管逻辑放在包内独立的 `server/portable_main.py`，盖在未改动的
`app.main:app` 之上——这样 git 拉新代码不会与它冲突，`app/` 保持纯净。

ℹ️ **在线更新：能力已就绪，刻意未启用**（2026-09-23 决定）。
`检查更新.bat` 与 `update.ps1` 已用本地 HTTP 源**实测通过全链路**
（成功 / 404 / 畸形包三种情形，含备份与失败后自动恢复），
但包内 `scripts/update-source.txt` 保持**空白模板**——要启用只需填一行压缩包直链。

⚠️ **演示数据只清测试账号，展会一律不动**：`clean_demo_data.py` 现在只删
`222`/`333`/`user` 三个测试账号（及级联依赖），`JUNK_EXHIBITION_IDS` **默认为空**。
早先这里挂过一条"日期年份不在 2000–2100 就当垃圾删"的自动判断，**误删过一条真实展会**
（id=6「请问」）—— 已移除该启发式并补回数据。教训：清理演示数据**不做自动判断**，
清哪些由人在常量里显式列。
清理只作用于便携包的库副本，原库 `expohub-backend/expohub.db` 始终未被改动。

**2026-09-16：智能匹配重构为「多阶段匹配工作流」**（详见 `docs/智能匹配工作流.md`）。

用户反馈：原智能匹配"精度不高、依赖云端大模型、经常超时" → 重构为
S0 画像→S1 多路召回→S2 过滤→S3 多信号打分→S4 排序→S5 本地解释 的显式工作流：
零云依赖、热态 40–100ms、IDF/同义词/品类归一化修复精度（评测 P@10 0→0.85）。
云 LLM 降级为按钮触发的可选「AI 解读」，失败自动降级本地解读。

**同日第二项：全角色接口/页面审计 + 基础功能通用化**（详见 `docs/角色能力矩阵.md`）。
用 `scripts/role_audit.py` 自动打出 5 角色 × 79 个 GET 接口矩阵：后端接口层本已"登录即用"，
断层都在前端入口 —— 修复 5 处（我的采购/发布采购路由放开全角色、个人中心/顶栏入口补齐、
canPublish 全角色、pipeline 元信息透传），UI 端到端已实测（证据图 docs/evidence/）。

⚠️ **下一步待确认**：本次任务未提及 9-04 演示的结果（"演示是否交付"仍未知）。
若演示已跑完，可问：下一批要补的功能是什么（参考 9-04 会话的候选队列）。

---

## ✅ 已完成

### 整合路线 P0–P7（2026-09-02 一天内全部完成）

| 阶段 | 提交 | 内容 |
|---|---|---|
| **P1** | `refactor(P1)` | 域模块化重构：api 平铺路由归组为 `modules/{identity,expo,exhibitor,matching,interaction,analytics,ticketing,onsite,ai,platform}` 十域 |
| **P2** | `feat(P2)` | `core/tenant`（租户头解析/回落默认租户）+ `core/audit`（审计日志+写操作审计）+ `core/scheduler`（APScheduler，默认关闭），**全默认行为不变** |
| **P3** | `feat(P3)` | `modules/ticketing`：ticket_types/orders/tickets + PayProvider 抽象（微信位预留）+ 免费票直通 + mock 支付出票 + 名额原子扣减/取消回退 + HMAC 签名二维码 + 验票 |
| **P4** | `feat(P4)` | `modules/onsite`：核销流水模型 + 单张/批量核销 |
| **P5** | `feat(P5)` | `modules/ai`：PII 脱敏 + LLM 网关（Mock/DeepSeek/SiliconFlow/OpenAI 兼容） |
| **P6** | `feat(P6)` | `modules/platform`：档位计费 TenantPlan + 租户订阅 + 批量导入展会（去重+逐行校验）+ 订单过期任务（`core/jobs`）+ 权限 `platform:manage` |
| **P7** | `feat(P7)` | `scripts/quality_gate.py` 覆盖率基线防回退 |

### 功能补齐（9-02 → 9-04，约 47 提交）

埋点链路（page_view/favorite 去重）· 取消报名 · 取消订单 · 取消采购需求 · 微展位编辑与会员升级 · 产品编辑整包 · 消息跳错会话语义修复 · 展商数据洞察 · 通知中心类型化 · 小程序通知页 · 中标通知跳转 · 智能匹配

### 智能匹配工作流（2026-09-16）

- 新模块：`app/modules/matching/textkit.py`（分词/品类归一化/同义词三层/同空间 IDF）+ `workflow.py`（S0–S5 工作流引擎 + 语料缓存 + 通知工作流）
- 接入：`recommendations.py` 三端点重写（for-exhibitor / for-buyer / score-procurements）、采购详情推荐、发布采购通知（阈值 Top5）
- 前端：展商/买家工作台匹配度徽章 + 工作流运行摘要；匹配列表页实时打分+排序；采购详情本地解读 + AI 降级
- 依赖：新增 `jieba==0.42.1`（缺库自动降级，不影响功能）
- 评测脚本：`scripts/match_eval.py`（新 P@5 0.86 / P@10 0.85 vs 老 0.00；展商侧 P@10 1.00 vs 0.84）
- ⚠️ Docker 镜像需重建才有 jieba + 新代码（缺 jieba 也能跑，只是分词粒度变粗）

### 桌面启动器（2026-09-21）

`desktop/` —— 桌面双击启动 + 实时热更新。形态是**快捷方式 + Edge `--app` 独立窗口**，
**没有打包成 exe**：PyInstaller 会把代码冻结进二进制，与热更新互斥，这是刻意的取舍。

实测证据：冷启动 **6.9 秒**就绪（双 200）；**幂等**（重复双击 PID 不变、不起第二套）；
后端探针文件写入后 **0.5 秒**触发 WatchFiles 重载；前端标记注入后 dev server 立即返回新代码。

⚠️ 两个非显然的坑，改 `desktop/` 前必读 `desktop/README.md`：
`.ps1` 必须 **UTF-8 with BOM**（PS 5.1 按 GBK 读，无 BOM 中文乱码）；
`WScript.Shell.Run(cmd,0,..)` 的 SW_HIDE 会**连带隐藏进程创建的第一个顶层窗口**（需 P/Invoke 覆盖）。

### 存量规模（供参考）
后端 `app/` 81 个 py / `app/models` 21 个模型 / 前端 58 个 vue / 测试 15 个文件（**89 passed**，2026-10-19 实测）

## ⛔ 阻塞 / 待决

- **演示是否交付** — 未知，需问用户
- **覆盖率 54.99%**（`coverage_baseline.txt`）——`quality_gate.py` 只防回退，**不设绝对值门禁**
- **历史遗留目录未整理** — 方案 §5 说可归档 `helloworld / moba-* / weather-* / src / app 旧版`，但**明文要求"执行前需你确认"**，尚未确认
- **产品名** — 文档用 `ExpoHub`，仓库名 `X-Expohub`

---

## 关键决策（只记「为什么」）
> 完整版在 `docs/整合规划_以X-Expohub为主体的合并方案.md`。

| 决策 | 为什么 |
|---|---|
| **X-Expohub 为主体，exhibition-saas 只作架构蓝本** | 综合评分 X=5.00 / ex=8.23，但两者互补：X 胜在功能广度+双端前端+撮合差异化，ex 胜在工程化。**X 的功能不可替代** |
| **功能冻结：用户可见功能只增不减** | 14 项功能清单为硬边界，重构不得造成可感知回退（方案 §6） |
| **主体不换栈** | 仍以 Python/FastAPI 承载；NestJS/TypeORM 仅作**蓝图**，用 Python 等价实现 |
| **API 行为兼容优先** | 接口路径/字段可重构（前后端同仓同版本推进），但页面功能不得回退 |
| **多租户用默认租户兜底** | P2 落地时"全默认行为不变"——现有数据归默认租户，不破坏存量 |
| **取消主办方角色（2026-10-19）** | 战略上要绕开展会举办方做撮合；保留角色会让"平台自营"与"主办方入驻"两套模型长期冲突，因此角色收敛、能力归 admin、数据迁移而不是删数据 |

## 文件地图

| 想找什么 | 去哪 |
|---|---|
| **整合方案（评分/红线/功能冻结清单/目标架构/P0-P7 路线）** | `docs/整合规划_以X-Expohub为主体的合并方案.md` |
| 架构文档 | `docs/architecture.md`（1075 行）、`docs/expo-hub-architecture.md` |
| 小程序设计 | `docs/expo-hub-uniapp-frontend-design.md`（1147 行） |
| 后端 | `expohub-backend/app/` — `core/`（tenant/audit/scheduler/jobs/security/permissions）+ `modules/`（十域）+ `models/` |
| 前端 Web | `expo-hub-frontend/`（Vue3 + TS + Vite + Pinia） |
| 小程序（旧） | `expo-hub-uniapp/` — 已有现成产物 `dist/build/mp-weixin`，可直接导入微信开发者工具 |
| 小程序（新） | `expo-hub-miniapp/` — uni-app **源码**工程。必须先在目录内 `npm install` + `npm run dev:mp-weixin` 生成 `dist/dev/mp-weixin`，否则开发者工具会报「未找到 app.json」 |
| **桌面启动器 / 启动脚本 / 日志** | `desktop/`（用法与 8 条踩坑见 `desktop/README.md`，日志在 `desktop/logs/`） |
| 质量门禁 / 运维脚本 | `scripts/quality_gate.py` `security_verify.py` `permissions_verify.py` `healthcheck.sh` `backup.sh` |
| **架构参照蓝本（独立项目）** | `D:\Projects\exhibition-saas\`（NestJS，48 提交，仿 Cvent） |
| **领导试用便携包** | 构建脚本在 **`portable/`**（本仓库，用法见 `portable/README.md`）；构建产物与工作区在 `D:\Projects\expo-hub-portable\`，`ExpoHub-试用版.zip`（~35MB）就是发出去的包 |

> ⚠️ 方案 §7.1 画的是 `expohub-backend/{core,modules}`，**实际落在 `expohub-backend/app/{core,modules}`**——文档与实现有偏差，以代码为准。

| 想找什么 | 去哪 |
|---|---|
| 去掉主办方的迁移脚本 | `scripts/migrate_drop_organizer.py`（`--dry-run` 预演；默认自动备份） |
| 平台自营展会管理页（原主办方页） | `expo-hub-frontend/src/views/expo-admin/`，路由 `/admin/*` |
| 公开信息采集骨架 | `scripts/scrape/expo_scraper.py` + `sources.json`；方案见 `docs/2026-10-19-数据抓取方案与合规边界.md` |
| 改进建议核查结论 | `docs/2026-10-19-建议核查与落地路线.md` |

## ⚠️ 不要碰

1. **功能冻结红线（2026-10-19 已修订）** — 原 14 项中的「主办方」按用户决策**已取消**，其能力并入「后台管理（平台自营）」。其余 13 项仍**语义不可删改**，只能增强。
2. **git remote 指向上游而非自己的 fork**：`origin = https://github.com/mf00000001/X-Expohub.git`。且本机 **github.com 被墙**（见全局 CLAUDE.md 环境事实）——推送/拉取需代理，别盲目 `git push`。
3. **历史遗留目录别自作主张删** — `helloworld/` `moba-backend/` `moba-frontend/` `weather-app/` `weather-backend/` `weather-frontend/` `src/`。方案 §5 明确"**执行前需你确认**"。
4. **`exhibition-saas` 是参照蓝本，不是废弃项目** — 它的 48 次提交（租户四道防线/票务/六维评分/AI 五铁律）是整合的架构来源，可直接查。
5. 本仓库含 `test_expo_hub.db` / `expohub.db` 等本地数据工件，改动前留意 `.gitignore` 是否已覆盖。
