# ExpoHub — 展会撮合平台 · 状态锚点

> **最后更新**：2026-09-16 ｜ **状态**：进行中（智能匹配工作流重构完成）
> **规则**：只写代码和文档里**读不出来**的东西。上限 150 行，超了就修剪——细节流到 `docs/`，这里只留指针。

---

## 一句话目标
展前撮合平台：**帮犹豫的展商免费试水 → 看到数据 → 参加线下展会**。
当前工程目标：在 X-Expohub 的功能全集之上，吸收 `exhibition-saas` 的架构范式，**在功能零回退的前提下**重构为多租户、可商业化、AI 原生的完整展会 SaaS。

## 当前阶段
**整合重构 P0–P7 已全部跑完**（2026-09-02 单日完成），之后转入功能补齐与演示打磨。

## 上次停在哪
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

### 存量规模（供参考）
后端 97 个 py / `app/models` 20 个模型 / 前端 111 个 vue+ts / 小程序 8 页 / 测试 13 个文件（86 passed）

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

## 文件地图

| 想找什么 | 去哪 |
|---|---|
| **整合方案（评分/红线/功能冻结清单/目标架构/P0-P7 路线）** | `docs/整合规划_以X-Expohub为主体的合并方案.md` |
| 架构文档 | `docs/architecture.md`（1075 行）、`docs/expo-hub-architecture.md` |
| 小程序设计 | `docs/expo-hub-uniapp-frontend-design.md`（1147 行） |
| 后端 | `expohub-backend/app/` — `core/`（tenant/audit/scheduler/jobs/security/permissions）+ `modules/`（十域）+ `models/` |
| 前端 Web | `expo-hub-frontend/`（Vue3 + TS + Vite + Pinia） |
| 小程序 | `expo-hub-uniapp/` |
| 质量门禁 / 运维脚本 | `scripts/quality_gate.py` `security_verify.py` `permissions_verify.py` `healthcheck.sh` `backup.sh` |
| **架构参照蓝本（独立项目）** | `D:\Projects\exhibition-saas\`（NestJS，48 提交，仿 Cvent） |

> ⚠️ 方案 §7.1 画的是 `expohub-backend/{core,modules}`，**实际落在 `expohub-backend/app/{core,modules}`**——文档与实现有偏差，以代码为准。

## ⚠️ 不要碰

1. **功能冻结红线** — 方案 §6 列出的 14 项用户可见功能（账号/角色/展会浏览/微展位/展馆/搜索/采购/匹配推荐/展商/主办方/收藏评价海报/消息通知/积分会员/后台管理）**语义不可删改**，只能增强。
2. **git remote 指向上游而非自己的 fork**：`origin = https://github.com/mf00000001/X-Expohub.git`。且本机 **github.com 被墙**（见全局 CLAUDE.md 环境事实）——推送/拉取需代理，别盲目 `git push`。
3. **历史遗留目录别自作主张删** — `helloworld/` `moba-backend/` `moba-frontend/` `weather-app/` `weather-backend/` `weather-frontend/` `src/`。方案 §5 明确"**执行前需你确认**"。
4. **`exhibition-saas` 是参照蓝本，不是废弃项目** — 它的 48 次提交（租户四道防线/票务/六维评分/AI 五铁律）是整合的架构来源，可直接查。
5. 本仓库含 `test_expo_hub.db` / `expohub.db` 等本地数据工件，改动前留意 `.gitignore` 是否已覆盖。
