# X-Expohub × Exhibition-SaaS 技术/产品比对与降维整合方案 v2

> 主体：**X-Expohub**（FastAPI + SQLAlchemy + SQLite，展会撮合平台；双前端 Vue3 Web + Uniapp）
> 参照：**exhibition-saas**（NestJS + TypeORM + MySQL/Redis，仿 Cvent 会展管理 SaaS）
> **约束（用户澄清后的版本）**：① 以 X-Expohub 为主体；② **用户功能零修改**（现有一切用户可见功能冻结，只增不减）；③ **架构与技术实现可自由重构**（目录、分层、数据层、基础设施、工程化均可改造，无「不能动代码」限制）。

---

## 0. 结论摘要（TL;DR）

| 项 | X-Expohub（主体） | exhibition-saas（参照） |
|---|---|---|
| 综合评分（50%技术 + 50%产品）| **5.00** | **8.23** |
| 技术层加权分 | 4.22 | 8.12 |
| 产品层加权分 | 5.78 | 8.34 |
| 一句话定位 | 展会撮合/采购匹配原型：功能多、前端双端、工程化弱 | 多租户 SaaS 蓝图：工程化强、无前端 |

**整合策略**：以 X-Expohub 的**功能全集**为「产品冻结基线」，吸收 exhibition-saas 的**架构范式**（域模块化、多租户、票务支付、现场签到、AI 原生层、审计/调度、测试门禁、计费），在**保留全部用户功能的前提下对 X-Expohub 进行架构级重构**，合成一个多租户、可商业化、带 AI 的完整展会 SaaS。

---

## 1. 项目画像

### 1.1 X-Expohub（主体）
- 技术栈：FastAPI + SQLAlchemy(asyncio) + SQLite(默认，可切 MySQL) + JWT；Vue3 + Vite + Pinia（Web）与 Uniapp（小程序）。
- 存量：`expohub-backend/app` 约 23 个 API 模块、约 20 个模型；42 次提交。另有历史遗留工程：`helloworld / moba-* / weather-* / src(备用实现) / app(旧版六层实现)`。
- 角色：游客 / 展商 / 买家 / 主办方 / 管理员。
- 用户功能亮点：采购需求发布与匹配、微展位按展会归类、展馆选馆、积分/会员/成长、消息/通知/收藏/评价/海报。
- 工程短板：单租户、无票务支付、无 AI 原生层、审计薄弱、无调度、测试偏单元、目录平铺。

### 1.2 exhibition-saas（参照）
- NestJS + TypeORM + MySQL 8.4 + Redis；9 业务域：租户身份/展会配置/注册票务/展商管理/现场签到/配对撮合/数据分析/AI 原生/平台运营。
- 硬能力：多租户四道隔离、审计日志、分布式锁+SKIP LOCKED、PayProvider(微信+Mock+对公)、六维评分+LLM、AI 预算/脱敏/结构化输出、双轨部署、五层测试、16 周里程碑。
- 短板：仓库内无前端。

---

## 2. 技术层逐项比对与评分（0–10）

| 技术维度 | X-Expohub | exhibition-saas | 权重 | 说明 |
|---|:--:|:--:|:--:|---|
| 后端技术栈与分层 | 6 | 8 | 0.07 | FastAPI 6 层(平铺) vs NestJS 模块化(域) |
| 架构可扩展性 | 5 | 9 | 0.09 | 单体薄 vs 域拆分+组合 |
| 多租户 / SaaS 化 | 2 | 9 | 0.12 | 无隔离 vs 四道防线+租户头 |
| 数据库与迁移 | 6 | 8 | 0.06 | SQLite+1 迁移 vs MySQL+15 迁移 |
| 认证与授权(RBAC) | 7 | 8 | 0.05 | JWT+多角色 vs 短信/JWT/微信+角色守卫 |
| 票务支付深度 | 1 | 9 | 0.10 | 无 vs 订单/支付/退款/发票/微信 |
| 展会域覆盖 | 7 | 8 | 0.05 | 展会/展馆/展位 vs 展会/场地/档期/邀请 |
| 现场签到 | 4 | 9 | 0.04 | 基础 checkin vs 批量/核销/统计/胸牌 |
| 撮合匹配（差异化）| 8 | 8 | 0.05 | 采购匹配/微展位 vs 六维评分+预约/名片 |
| AI 原生层 | 2 | 9 | 0.09 | 规则推荐 vs LLM 网关/预算/脱敏/异步 job |
| 运营数据分析 | 6 | 8 | 0.04 | 分析/看板 vs 导入闭环+复用 |
| 审计与安全合规 | 2 | 9 | 0.06 | 弱 vs 审计日志+脱敏+隔离契约 |
| 定时 / 并发任务 | 1 | 8 | 0.04 | 无 vs 分布式锁+SKIP LOCKED |
| 测试与质量门禁 | 3 | 9 | 0.08 | ~133 用例 vs spec/契约/E2E+覆盖率 |
| 部署与 DevOps | 5 | 8 | 0.06 | compose+Makefile vs 双轨+CI+补丁热更 |
| 前端覆盖 | 8 | 2 | 0.03 | Vue3 + Uniapp 双端 vs 无前端 |
| 在线沟通 / 消息 | 7 | 3 | 0.03 | messages/通知/收藏 vs notes/预约 |
| 积分 / 会员 / 激励 | 8 | 2 | 0.02 | points/会员/成长 vs 无 |
| **技术层加权** | **4.22** | **8.12** | | |

## 3. 产品层逐项比对与评分（0–10）

| 产品维度 | X-Expohub | exhibition-saas | 权重 | 说明 |
|---|:--:|:--:|:--:|---|
| 市场定位清晰度 | 6 | 9 | 0.10 | 展会撮合 vs 仿 Cvent |
| 角色体系完整度 | 7 | 7 | 0.09 | 5 角色 vs 角色矩阵 |
| 核心场景覆盖 | 7 | 9 | 0.14 | 撮合 vs 全流程 |
| 差异化 / 创新点 | 9 | 7 | 0.12 | 采购匹配/微展位/积分 vs 六维+LLM |
| 变现 / 商业化 | 3 | 9 | 0.11 | 弱 vs 档位订阅 |
| 运营增长闭环 | 6 | 9 | 0.10 | 会员/激励 vs 导入-分析-复用 |
| 用户 / 体验成熟度 | 5 | 6 | 0.08 | 原型级 UI vs 结构化流程 |
| 规划 / 文档完整度 | 4 | 9 | 0.14 | 交付清单 vs spec+架构+4计划 |
| 演进可持续性 | 5 | 9 | 0.12 | demo 为主 vs 16 周可上线 |
| **产品层加权** | **5.78** | **8.34** | | |

## 4. 评分汇总

| 评估 | X-Expohub | exhibition-saas |
|------|:--:|:--:|
| 技术层 | 4.22 | 8.12 |
| 产品层 | 5.78 | 8.34 |
| **综合（50/50）** | **5.00** | **8.23** |

**结论**：exhibition-saas 工程更成熟，X-Expohub 在功能广度、双端前端与撮合差异化上不可替代。整合 = **功能以 X-Expohub 为基、架构以 exhibition-saas 为范式**。

---

## 5. 整合总则（修正版红线）

1. **功能冻结（不可改）**：X-Expohub 现有**用户可见功能**全部保持不变 —— 见 §6「功能冻结清单」。可新增功能，不可删改既有功能语义。
2. **架构自由（可重构）**：目录结构、分层方式、数据层、ORM 组织、中间件、调度、支付/AI 基础设施、测试体系均可按目标架构重构。
3. **主体不换栈**：仍以 Python/FastAPI 生态承载（X-Expohub 为主体即以其技术栈为基座）；NestJS/TypeORM 仅作**架构蓝图**，以 Python 等价实现。
4. **API 行为兼容优先**：功能等价是硬约束，接口路径/字段可重构（前后端同仓同版本推进），但对外可感知行为与现有前端页面功能不得回退。
5. **仓库整理属于技术实现**：历史遗留（helloworld/moba/weather、src 备用、app 旧版）可归档或移除，但**执行前需你确认**（删除文件）。

---

## 6. 功能冻结清单（用户功能 = 整合的硬边界）

> 以下为用户功能基线：整合后这些功能必须**原样可用**（含行为、规则、角色边界、页面流程）。实现代码允许重写，但可感知功能不变。

| # | 端 | 功能 | 现状落点 |
|:-:|---|---|---|
| 1 | 全部 | 账号体系：注册/登录(游客)/登出/JWT 会话 | expohub-backend auth + user |
| 2 | 全部 | 角色边界：游客/展商/买家/主办方/管理员权限划分 | RBAC + 各端页面 |
| 3 | 游客/公共 | 首页聚合、展会浏览、展会详情、报名展会 | exhibitions/registrations |
| 4 | 游客/公共 | 微展位公开页 + 按展会归类浏览 | micro_booths + exhibitions |
| 5 | 游客/公共 | 展馆列表/详情、主办方选馆建展会（内嵌对比面板）| venues/exhibitions |
| 6 | 游客/公共 | 搜索（展会/展商/展品/分类筛选） | search/categories/products |
| 7 | 游客/买家 | 采购需求：发布/浏览/分类筛选/我的采购 | procurements |
| 8 | 游客/买家 | 采购匹配推荐（含未登录提示态） | recommendations |
| 9 | 展商 | 展品管理、参展申请、展商工作台 | products/exhibitors/dashboard |
| 10 | 主办方 | 主办方工作台、展会管理、展位分配、统计 | organizer/exhibitions/booths/analytics |
| 11 | 全体 | 收藏/评价/海报分享 | favorites/reviews/poster |
| 12 | 全体 | 消息/在线沟通、通知列表 | messages/notifications |
| 13 | 全体 | 积分/会员等级/成长值 | points/membership/growth |
| 14 | 管理员 | 后台管理（管理员视图） | admin 前端 + 管理 API |

> 注：以上清单以**现有页面+接口行为**为准，逐项冻结；实施时以「功能验收用例」校验回归。

---

## 7. 整合方案：目标架构（架构可重构，功能冻结）

### 7.1 目标目录结构（对标 exhibition-saas 域范式，重构 X-Expohub）

```
expohub-backend/
├── core/                      # 基础底座（重构现有 app/core 等）
│   ├── config/                # pydantic-settings 分层配置
│   ├── security/              # JWT 双令牌/RBAC/密码/脱敏(PII)
│   ├── tenant/                # 租户上下文/中间件/查询隔离(四道防线)
│   ├── audit/                 # 审计日志(新增)
│   ├── scheduler/             # APScheduler + 分布式锁(新增)
│   ├── pay/                   # PayProvider 抽象: wechat/mock/对公(新增)
│   └── llm/                   # LLM 网关: deepseek/siliconflow/mock(新增)
├── modules/                   # 业务域（原平铺 api/ 重组，功能不变）
│   ├── identity/              # auth/user/membership/points  ← 功能①③积分等
│   ├── expo/                  # exhibitions/venues/booths/micro_booths/categories
│   ├── exhibitor/             # exhibitors/products/dashboard/申请
│   ├── matching/              # procurements/recommendations/appointments/采购匹配
│   ├── interaction/           # messages/notifications/favorites/reviews/poster
│   ├── analytics/             # analytics/growth/看板
│   ├── ticketing/             # 新增：票种/订单/票/发票/支付/退款
│   ├── onsite/                # 增强：签到/批量/统计/热力/胸牌
│   ├── ai/                    # 新增：AI 撮合增强/大会助手/催办/文案
│   └── platform/              # 新增：租户/计费档位/开放配置
├── migrations/                # Alembic 多版本迁移（重建迁移基线）
└── api/                       # 路由聚合层（对外暴露，路径与功能等价）
```

### 7.2 吸收能力映射（架构自由 + 功能冻结 + 新增能力）

| 吸收能力 | 架构动作 | 功能影响 |
|---|---|---|
| ① 多租户 SaaS | 全库加 tenant 上下文；中间件+查询过滤四道防线 | 无（现有数据归默认租户） |
| ② 票务支付 | 新增 ticketing 域；PayProvider 微信+Mock；订单超时+名额回退 | 新增；现有「报名」升级为含免费票语义（报名动作等价） |
| ③ 现场签到 | onsite 域增强：批量/撤销/统计/热力/胸牌 | 新增/增强，签到主语义不变 |
| ④ AI 原生层 | LLM 网关+预算+脱敏+结构化输出+ai_jobs；规则推荐保留为基座并叠加 LLM reason | 推荐结果增强，原规则推荐仍可用 |
| ⑤ 审计/合规 | 审计中间件+日志表+隔离契约 | 无（透明） |
| ⑥ 调度/并发 | APScheduler+SKIP LOCKED；订单过期/cold 线索/催办/统计 | 新增自动化 |
| ⑦ 数据+计费 | analytics 增加导入-分析-复用；platform 档位计费 | 新增 |
| ⑧ 测试门禁 | 五层测试体系 + 覆盖率门禁 + CI | 无（守护功能冻结） |

### 7.3 原则性工程改良（技术层自由改造清单）

- **数据层**：SQLAlchemy 2.0 asyncio 统一封装 → repository 模式；Alembic 重建版本基线（1→N 迁移）；SQLite 保持默认，MySQL/PG 以配置切换。
- **认证**：JWT 双令牌（access+refresh）、统一角色守卫矩阵；可选接入微信/短信登录（新渠道，不删原密码登录）。
- **事务与并发**：统一事务边界；行级乐观锁/名额扣减原子化；订单超时任务。
- **错误处理**：统一异常过滤器 + 业务错误码 + 结构化响应（兼容现有前端解析）。
- **前端**：Vue3 工程保持；API 层按新路由重映射（功能等价）；Uniapp 小程序同步（如作为二期）。
- **仓库整理**（需你确认）：归档 `helloworld/moba-*/weather-*/src/app 旧版` 等非主体工程。

---

## 8. 数据模型融合（示意）

```
[存量核心（功能冻结，模型可重构）]          [新增（吸收自 exhibition-saas）]
users / memberships / points        tenants(id, tier, ai_enabled, budget)
exhibitions / venues / booths       ticket_types / orders / tickets
micro_booths / categories           invoices / payment_configs
exhibitors / products               checkin_batches / audit_logs
procurements / procurement_match    ai_jobs / ai_usage_logs
registrations / appointments        expo_faqs / leads(+cold状态)
messages / favorites / reviews
统一附加: tenant_id, 状态机字段, created/updated 审计列
```

## 9. 分阶段实施路线（功能冻结下的重构节奏）

| 阶段 | 内容 | 产出 | 功能影响 |
|---|---|---|---|
| P0 基线冻结 | 功能清单→验收用例；双端回归基线；仓库整理（待确认） | 功能验收套件 | 无 |
| P1 架构重构 | 域模块化目录迁移 + repository/统一事务 + Alembic 重建 + 异常体系 | 新骨架跑通全部存量功能 | 无 |
| P2 多租户+审计 | tenant 上下文四道防线 + audit + Redis 可选 | 隔离契约测试通过 | 无 |
| P3 票务支付 | ticketing 域 + PayProvider + 订单超时 | 商化闭环上线 | 新增（报名融合） |
| P4 现场签到 | onsite 批量/撤销/统计/热力/胸牌 | 会中运营 | 增强 |
| P5 AI 原生 | LLM 网关 + 铁律 + ai_jobs + 撮合增强 + AI 助手 | 差异化护城河 | 增强（规则基座保留） |
| P6 数据计费 | 导入-分析-复用 + 档位订阅 + 双轨部署 | SaaS 化完成 | 新增 |
| P7 工程化 | 五层测试 + 覆盖率门禁 + CI/CD | 可上线 | 无 |

> 每阶段出口都跑 P0 的功能验收用例，确保**用户功能零回退**。

## 10. 风险与对策

| 风险 | 对策 |
|---|---|
| 重构破坏存量功能 | P0 功能验收用例为门禁；分域迁移+每阶段回归 |
| 多租户漏隔离 | 四道防线 + 隔离契约测试 |
| SQLite 并发上限 | 默认租户可 SQLite；上线切 MySQL/PG |
| AI 预算/隐私 | 预算护栏+PII 脱敏+结构化输出 |
| 前端大面积返工 | API 重映射保持行为等价；前端同版本演进 |

## 11. 结语

以 **X-Expohub 的功能全集**为不可变基座，以 **exhibition-saas 的架构范式**为改造蓝图：技术实现全面重构（域模块化、多租户、支付、AI、审计调度、测试门禁），**用户功能只增不减**，最终合成一个功能完整、工程成熟、可商业化上线的多租户展会撮合 SaaS。
