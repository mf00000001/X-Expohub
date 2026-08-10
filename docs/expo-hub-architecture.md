# ExpoHub 智能撮合平台 — 完整技术方案

> 版本：v2.0 | 最后更新：2025-01 | 作者：Architect Agent

---

## 📋 需求理解

ExpoHub 是一个连接**展会游客（Visitor）**、**展商（Exhibitor）**、**老板/投资人（Boss）**、**主办方（Organizer）** 四类角色的智能撮合平台。核心业务闭环为：主办方创建展会 → 展商入驻并管理展品 → 游客浏览报名/发布采购需求 → 智能匹配撮合 → 即时通讯沟通 → Boss 审批监管与数据决策。

---

## 🏗️ 技术方案

### 整体架构

```
┌─────────────────────────────────────────────────────────┐
│                   客户端层 (UniApp)                       │
│  H5 / 微信小程序 / App（一套代码多端运行）                │
└────────────────────┬────────────────────────────────────┘
                     │ HTTP/WebSocket
┌────────────────────▼────────────────────────────────────┐
│                 API 网关层 (Nginx)                        │
│  负载均衡 / 限流 / SSL卸载 / 静态资源缓存                 │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│              应用服务层 (FastAPI + Uvicorn)               │
│                                                        │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│  │ 认证模块 │ │ 展会模块 │ │ 展位模块 │ │ 展品模块 │  │
│  ├──────────┤ ├──────────┤ ├──────────┤ ├──────────┤  │
│  │ 采购模块 │ │ 消息模块 │ │ 团队模块 │ │ 统计模块 │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘  │
│                                                        │
│  ┌──────────────────────────────────────────────────┐   │
│  │         智能匹配引擎 (规则+协同过滤)               │   │
│  └──────────────────────────────────────────────────┘   │
└────────────┬──────────────────────────────┬─────────────┘
             │                              │
┌────────────▼──────────┐   ┌──────────────▼─────────────┐
│    MySQL (主库)        │   │    Redis (缓存/会话/队列)   │
│  业务数据持久化         │   │   Token黑名单/消息队列/缓存  │
└───────────────────────┘   └────────────────────────────┘
```

**架构模式**：前后端分离的单体应用（Monolithic First），后续可按模块拆分为微服务。

**设计原则**：
- **Monolithic First**：初期单体快速迭代，模块化拆分好，后续可平滑过渡到微服务
- **RBAC 权限模型**：四角色权限体系已完善定义
- **分层架构**：API → Service → Model，职责清晰

---

### 技术栈

| 层级 | 技术 | 版本 | 选型理由 |
|------|------|------|---------|
| **后端框架** | Python FastAPI | ≥0.100 | 异步高性能、自动生成 OpenAPI、类型安全 |
| **ASGI 服务器** | Uvicorn + Gunicorn | - | 生产级部署 |
| **ORM** | SQLAlchemy 2.0 | ≥2.0 | 成熟稳定、支持异步 |
| **数据库迁移** | Alembic | - | 版本化管理 |
| **数据库** | MySQL 8.0 | - | 事务支持、成熟生态 |
| **缓存** | Redis 7 | - | Token黑名单、缓存、消息队列 |
| **认证** | JWT (Access+Refresh) + bcrypt | - | 无状态、安全 |
| **前端框架** | UniApp (Vue 3) | - | 一套代码多端运行 |
| **WebSocket** | FastAPI WebSocket | - | 即时消息推送 |
| **容器化** | Docker + Docker Compose | - | 环境一致性 |
| **反向代理** | Nginx | - | 负载均衡、静态资源 |

---

### 数据模型

#### 核心实体关系图

```
User (统一用户表, role区分四类角色)
  ├── Exhibitor (展商扩展信息, 1:1)
  ├── Exhibition (展会, organizer_id -> User)
  ├── Booth (展位, exhibition_id -> Exhibition, exhibitor_id -> User)
  ├── Product (展品, exhibitor_id -> User, booth_id -> Booth)
  ├── ProcurementRequest (采购需求, visitor_id -> User)
  │   └── ProcurementMatch (匹配记录, procurement_id + exhibitor_id)
  ├── Message (消息, sender_id + receiver_id -> User)
  ├── Team (团队, boss_id -> User)
  │   └── TeamMember (成员, team_id + user_id)
  ├── VisitorRegistration (报名/收藏, visitor_id + exhibition_id)
  └── Review (评价, user_id + exhibition_id)
```

#### 关键表结构（已有，无需新增）

| 表名 | 核心字段 | 说明 |
|------|---------|------|
| `users` | id, username, email, role, status | 统一用户，role ∈ {visitor, exhibitor, boss, organizer} |
| `exhibitions` | id, name, start_date, end_date, venue, city, status, organizer_id | 展会，Boss可审批 |
| `exhibitors` | id, user_id, company_name, status | 展商资质审核 |
| `booths` | id, exhibition_id, exhibitor_id, booth_number, status, price | 展位分配 |
| `products` | id, exhibitor_id, booth_id, name, category, price | 展品管理 |
| `procurement_requests` | id, visitor_id, title, category, budget_min/max, status | 采购需求 |
| `procurement_matches` | id, procurement_id, exhibitor_id, quoted_price, is_accepted | 匹配撮合 |
| `messages` | id, sender_id, receiver_id, title, content, is_read | 即时通讯 |
| `teams` / `team_members` | id, boss_id, name / team_id, user_id, role_in_team | 团队管理 |
| `visitor_registrations` | id, visitor_id, exhibition_id, is_favorite, is_registered | 报名收藏 |
| `reviews` | id, user_id, exhibition_id, rating, content | 展会评价 |
| `audit_logs` | id, user_id, action, target_type, target_id, detail | 操作审计 |

---

### API 设计（已有 + 增强）

#### 认证模块
| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| POST | `/api/v1/auth/register` | 注册（含角色选择） | 公开 |
| POST | `/api/v1/auth/login` | 登录（返回Access+Refresh Token） | 公开 |
| POST | `/api/v1/auth/refresh` | 刷新Token | 已登录 |
| POST | `/api/v1/auth/logout` | 登出（Token加入黑名单） | 已登录 |
| GET | `/api/v1/auth/me` | 获取当前用户信息 | 已登录 |

#### 展会模块
| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | `/api/v1/exhibitions` | 展会列表（筛选/分页） | 公开 |
| GET | `/api/v1/exhibitions/{id}` | 展会详情 | 公开 |
| POST | `/api/v1/exhibitions` | 创建展会 | organizer |
| PUT | `/api/v1/exhibitions/{id}` | 编辑展会 | organizer |
| POST | `/api/v1/exhibitions/{id}/publish` | 发布展会 | organizer |
| POST | `/api/v1/exhibitions/{id}/approve` | 审批展会 | boss |
| POST | `/api/v1/exhibitions/{id}/reject` | 驳回展会 | boss |

#### 展位模块
| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | `/api/v1/exhibitions/{id}/booths` | 展位列表 | 公开 |
| POST | `/api/v1/exhibitions/{id}/booths` | 创建展位 | organizer |
| POST | `/api/v1/booths/{id}/book` | 预订展位 | exhibitor |
| PUT | `/api/v1/booths/{id}` | 编辑展位 | organizer |

#### 展品模块
| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | `/api/v1/products` | 展品列表（筛选） | 公开 |
| POST | `/api/v1/products` | 添加展品 | exhibitor |
| PUT | `/api/v1/products/{id}` | 编辑展品 | exhibitor |
| DELETE | `/api/v1/products/{id}` | 删除展品 | exhibitor |

#### 采购撮合模块（核心）
| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| POST | `/api/v1/procurements` | 发布采购需求 | visitor |
| GET | `/api/v1/procurements` | 采购需求列表（展商可见） | 已登录 |
| GET | `/api/v1/procurements/{id}` | 需求详情 | 已登录 |
| PUT | `/api/v1/procurements/{id}` | 编辑需求 | visitor(本人) |
| POST | `/api/v1/procurements/{id}/match` | 展商响应匹配 | exhibitor |
| GET | `/api/v1/procurements/{id}/matches` | 匹配列表 | visitor(本人) |
| POST | `/api/v1/matches/{id}/accept` | 接受匹配 | visitor(本人) |

#### 消息模块
| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| POST | `/api/v1/messages` | 发送消息 | 已登录 |
| GET | `/api/v1/messages` | 消息列表 | 已登录 |
| GET | `/api/v1/messages/conversation/{user_id}` | 会话详情 | 已登录 |
| PUT | `/api/v1/messages/{id}/read` | 标记已读 | 已登录 |
| GET | `/api/v1/messages/unread-count` | 未读数 | 已登录 |
| WS | `/api/v1/ws/chat` | WebSocket 实时聊天 | 已登录 |

#### 报名/收藏
| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| POST | `/api/v1/exhibitions/{id}/register` | 报名展会 | visitor |
| POST | `/api/v1/exhibitions/{id}/favorite` | 收藏/取消收藏 | visitor |
| GET | `/api/v1/registrations` | 我的报名/收藏 | visitor |

#### 评价模块
| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| POST | `/api/v1/exhibitions/{id}/reviews` | 发布评价 | visitor(已报名) |
| GET | `/api/v1/exhibitions/{id}/reviews` | 评价列表 | 公开 |

#### 团队模块
| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| POST | `/api/v1/teams` | 创建团队 | boss |
| GET | `/api/v1/teams` | 我的团队 | boss |
| PUT | `/api/v1/teams/{id}` | 编辑团队 | boss |
| POST | `/api/v1/teams/{id}/members` | 添加成员 | boss |
| DELETE | `/api/v1/teams/{id}/members/{user_id}` | 移除成员 | boss |

#### 数据看板
| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | `/api/v1/dashboard` | 全局统计 | boss/organizer |
| GET | `/api/v1/dashboard/exhibitions` | 展会统计 | boss/organizer |
| GET | `/api/v1/dashboard/procurements` | 采购统计 | boss/organizer |

#### 审核模块
| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | `/api/v1/audit/logs` | 审计日志 | boss/organizer |
| POST | `/api/v1/exhibitors/{id}/verify` | 审核展商资质 | boss/organizer |

---

### 四类角色核心业务流程

```
┌─────────────────────────────────────────────────────────────────┐
│  游客 (Visitor)                                                 │
│  ├─ 浏览展会列表 → 查看详情 → 报名/收藏                          │
│  ├─ 发布采购需求 → 等待展商匹配 → 查看匹配 → 沟通/接受           │
│  └─ 展会结束后 → 评价                                           │
├─────────────────────────────────────────────────────────────────┤
│  展商 (Exhibitor)                                               │
│  ├─ 提交资质 → 等待审核 → 审核通过                               │
│  ├─ 浏览展会 → 预订展位 → 管理展品                               │
│  ├─ 浏览采购需求 → 响应匹配 → 报价沟通                           │
│  └─ 与游客/主办方即时通讯                                        │
├─────────────────────────────────────────────────────────────────┤
│  主办方 (Organizer)                                             │
│  ├─ 创建/编辑展会 → 设置展位 → 发布                             │
│  ├─ 审核展商入驻 → 分配展位                                     │
│  └─ 查看展会数据 → 管理报名                                     │
├─────────────────────────────────────────────────────────────────┤
│  老板/投资人 (Boss)                                             │
│  ├─ 审批展会（发布前需Boss审批）                                 │
│  ├─ 查看全局数据报表                                            │
│  ├─ 管理团队（创建团队/邀请成员）                                │
│  └─ 系统配置管理                                                │
└─────────────────────────────────────────────────────────────────┘
```

---

### 智能匹配引擎设计

#### 匹配逻辑（ProcurementRequest ↔ Exhibitor）

```
游客发布采购需求 ──→ 匹配引擎 ──→ 推荐给相关展商
                                      │
                                      ▼
                              展商响应匹配 (报价+留言)
                                      │
                                      ▼
                              游客查看匹配列表
                                      │
                                      ▼
                              游客接受匹配 → 状态变更为 completed
```

**匹配规则**：
1. **品类匹配**：`ProcurementRequest.category` ↔ `Product.category`（核心规则）
2. **展会关联**：同一展会下的展商优先推荐
3. **历史数据**：展商历史成交记录作为加分项
4. **推送通知**：匹配成功后通过消息模块通知双方

---

### 安全设计

| 层面 | 措施 |
|------|------|
| **认证** | JWT Access Token(15min) + Refresh Token(7d) |
| **Token安全** | Redis黑名单机制，登出即失效 |
| **密码** | bcrypt 12轮哈希 |
| **鉴权** | RBAC + 细粒度 Permission 检查 |
| **数据隔离** | 行级权限：只能操作自己的数据 |
| **防注入** | SQLAlchemy ORM 参数化查询 |
| **审计** | AuditLog 记录所有关键操作 |
| **CORS** | 可配置的跨域策略 |
| **限流** | Nginx + 后续可加 Redis 限流 |

---

### 文件结构

```
expo-hub/
├── app/                          # 后端核心代码
│   ├── api/                      # API 路由层
│   │   ├── v1/                   # v1 版本
│   │   │   ├── auth.py           # 认证接口
│   │   │   ├── users.py          # 用户接口
│   │   │   ├── exhibitions.py    # 展会接口
│   │   │   ├── exhibitors.py     # 展商接口
│   │   │   ├── booths.py         # 展位接口
│   │   │   ├── procurements.py   # 采购撮合接口
│   │   │   ├── messages.py       # 消息接口
│   │   │   ├── teams.py          # 团队接口
│   │   │   ├── dashboard.py      # 数据看板
│   │   │   └── audit.py          # 审计接口
│   │   └── router.py             # 路由聚合
│   ├── core/                     # 核心基础设施
│   │   ├── config.py             # 配置管理
│   │   ├── constants.py          # 常量/枚举
│   │   ├── security.py           # JWT/密码工具
│   │   ├── permissions.py        # RBAC权限定义
│   │   ├── dependencies.py       # 依赖注入
│   │   ├── exceptions.py         # 异常定义
│   │   └── middleware.py         # 中间件
│   ├── models/                   # SQLAlchemy ORM 模型
│   ├── schemas/                  # Pydantic 校验模型
│   ├── services/                 # 业务逻辑层
│   ├── database/                 # 数据库连接
│   │   ├── session.py            # SQLAlchemy Session
│   │   └── redis.py              # Redis 客户端
│   └── utils/                    # 工具函数
│       ├── pagination.py         # 分页工具
│       └── response.py           # 统一响应格式
├── expo-hub-uniapp/              # 前端 UniApp
│   ├── pages/                    # 主包页面
│   ├── subpkg_visitor/           # 游客分包
│   ├── subpkg_exhibitor/         # 展商分包
│   ├── subpkg_boss/              # Boss分包
│   ├── subpkg_organizer/         # 主办方分包
│   └── src/                      # 核心工具
│       ├── request.js            # HTTP 请求封装
│       ├── auth.js               # 认证管理
│       └── router.js             # 路由守卫
├── alembic/                      # 数据库迁移
├── nginx/                        # Nginx 配置
├── docker-compose.yml            # 容器编排
├── Dockerfile                    # 后端镜像
└── tests/                        # 测试
    ├── test_auth_api.py
    ├── test_auth_unit.py
    ├── test_models_unit.py
    ├── test_schemas_unit.py
    └── test_permission_isolation.py
```

---

## 📝 任务拆解

### 已完成的模块（现有代码已覆盖）

| 模块 | 状态 | 说明 |
|------|------|------|
| 用户认证 | ✅ 完成 | 注册/登录/Token刷新/登出 |
| 权限系统 | ✅ 完成 | RBAC 四角色权限定义 |
| 展会管理 | ✅ 完成 | CRUD + 发布/审批/驳回 |
| 展位管理 | ✅ 完成 | CRUD + 预订 |
| 展品管理 | ✅ 完成 | CRUD |
| 采购撮合 | ✅ 完成 | 发布/匹配/接受 |
| 消息通讯 | ✅ 完成 | 发送/列表/会话/已读 |
| 团队管理 | ✅ 完成 | 创建/成员管理 |
| 数据看板 | ✅ 完成 | 全局统计 |
| 审计日志 | ✅ 完成 | 操作记录 |
| 评价系统 | ✅ 完成 | 发布/列表 |
| 报名收藏 | ✅ 完成 | 报名/收藏 |

### 待增强/新增的任务

| 序号 | 任务 | 负责人 | 预估时间 | 依赖 | 优先级 |
|------|------|--------|---------|------|--------|
| 1 | WebSocket 实时消息推送 | Backend | 2h | 现有消息模块 | P1 |
| 2 | 智能匹配引擎（协同过滤推荐） | Backend | 4h | 采购模块 | P1 |
| 3 | 展商资质审核流程优化 | Backend | 2h | 展商模块 | P1 |
| 4 | 消息通知推送（站内信+模板） | Backend | 3h | 1 | P2 |
| 5 | 搜索功能增强（ES集成） | Backend | 6h | - | P2 |
| 6 | 数据看板图表API增强 | Backend | 2h | 现有看板 | P2 |
| 7 | 前端分包页面完善（4个角色） | Frontend | 8h | 全部API | P0 |
| 8 | 前端页面路由守卫/权限控制 | Frontend | 2h | 7 | P0 |
| 9 | 前端消息聊天界面 | Frontend | 4h | 1 | P1 |
| 10 | 端到端集成测试 | Testing | 4h | 全部 | P1 |
| 11 | 性能压测与优化 | Testing | 3h | 10 | P2 |
| 12 | 部署文档与CI/CD | DevOps | 2h | - | P2 |

---

## ⚠️ 风险与建议

### 技术风险

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| **单体应用性能瓶颈** | 高并发下API响应变慢 | ① 关键接口加Redis缓存 ② 后续按模块拆分微服务（消息/采购独立） |
| **WebSocket 连接管理** | 大量长连接占用资源 | ① 使用 Redis Pub/Sub 做横向扩展 ② 接入层用 Nginx 做 WS 负载均衡 |
| **搜索性能** | 展会/展品/采购需求增多后MySQL模糊查询慢 | 引入 Elasticsearch 做全文搜索（P2阶段） |
| **数据一致性** | 匹配并发导致超卖/重复匹配 | ① 数据库唯一索引约束 ② 乐观锁版本号 ③ 后续引入分布式锁 |

### 架构演进路线

```
Phase 1 (当前) ──→ Phase 2 ──→ Phase 3
   单体应用        消息模块拆分     微服务化
   MySQL+Redis    +WebSocket      +ES/消息队列
   FastAPI        +推送通知        +容器编排(K8s)
```

### 建议

1. **优先完善前端**：后端API已基本完备，前端分包页面（4个角色）是当前最大缺口
2. **尽快接入WebSocket**：消息模块目前只有HTTP轮询，实时性不足影响撮合体验
3. **匹配引擎可先做规则版**：基于品类关键词匹配即可上线，协同过滤推荐作为P1优化
4. **测试覆盖**：权限隔离测试（`test_permission_isolation.py`）思路很好，建议扩展到所有模块
5. **监控告警**：生产环境建议接入 Sentry（错误监控）+ Prometheus（性能监控）
