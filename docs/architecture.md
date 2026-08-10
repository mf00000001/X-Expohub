# ExpoHub 展会撮合平台 — 完整技术方案

> 版本：v1.0 | 最后更新：2025-01 | 状态：✅ 已落地

---

## 目录

1. [整体架构设计](#1-整体架构设计)
2. [MySQL 核心数据表设计](#2-mysql-核心数据表设计)
3. [JWT 双令牌认证方案](#3-jwt-双令牌认证方案)
4. [RBAC 四角色权限模型](#4-rbac-四角色权限模型)
5. [FastAPI 目录结构](#5-fastapi-目录结构)
6. [Uniapp 前端四端路由规划](#6-uniapp-前端四端路由规划)

---

## 1. 整体架构设计

### 1.1 架构模式：前后端分离

```
┌─────────────────────────────────────────────────────────┐
│                    客户端层 (Uniapp)                       │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐   │
│  │  游客端   │ │  展商端   │ │  老板端   │ │ 主办方端  │   │
│  │ (Visitor)│ │(Exhibitor)│ │  (Boss)  │ │(Organizer)│   │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘   │
│       └────────────┼─────────────┼────────────┘          │
│                    │  统一API调用  │                       │
├────────────────────┼─────────────┼───────────────────────┤
│              Nginx 反向代理 / 负载均衡                     │
├────────────────────┼─────────────┼───────────────────────┤
│                    ▼             ▼                        │
│              FastAPI 应用服务层                            │
│  ┌──────────────────────────────────────────────────┐    │
│  │  API 路由层 (app/api/v1/)                        │    │
│  │  ┌──────┐┌──────┐┌──────┐┌──────┐┌──────────┐  │    │
│  │  │auth  ││users ││exhib ││booth ││procurement│  │    │
│  │  │      ││      ││itions││      ││_requests  │  │    │
│  │  └──────┘└──────┘└──────┘└──────┘└──────────┘  │    │
│  │  ┌──────┐┌──────┐┌──────┐┌──────┐┌──────────┐  │    │
│  │  │mes-  ││team  ││dash- ││audi- ││exhibitors│  │    │
│  │  │sages ││      ││board ││t     ││          │  │    │
│  │  └──────┘└──────┘└──────┘└──────┘└──────────┘  │    │
│  ├──────────────────────────────────────────────────┤    │
│  │  核心层 (app/core/)                              │    │
│  │  ┌──────────┐ ┌──────────┐ ┌─────────────────┐  │    │
│  │  │ security │ │permissions│ │  dependencies   │  │    │
│  │  │(JWT/哈希)│ │ (RBAC)   │ │ (依赖注入/鉴权)  │  │    │
│  │  └──────────┘ └──────────┘ └─────────────────┘  │    │
│  │  ┌──────────┐ ┌──────────┐ ┌─────────────────┐  │    │
│  │  │ config   │ │constants │ │  exceptions     │  │    │
│  │  │(配置)    │ │ (枚举)   │ │ (异常处理)       │  │    │
│  │  └──────────┘ └──────────┘ └─────────────────┘  │    │
│  ├──────────────────────────────────────────────────┤    │
│  │  业务服务层 (app/services/)                      │    │
│  │  ┌──────┐┌──────┐┌──────┐┌──────┐┌──────────┐  │    │
│  │  │auth  ││user  ││exhib ││booth ││procure   │  │    │
│  │  │svc   ││svc   ││ition ││svc   ││ment_svc  │  │    │
│  │  └──────┘└──────┘└──────┘└──────┘└──────────┘  │    │
│  └──────────────────────────────────────────────────┘    │
├────────────────────┬────────────────────────────────────┤
│                    ▼                                     │
│              数据访问层                                   │
│  ┌──────────────────┐  ┌──────────────────────────────┐  │
│  │  SQLAlchemy ORM  │  │      Redis (缓存/黑名单)      │  │
│  │  (app/models/)   │  │  (app/database/redis.py)     │  │
│  └────────┬─────────┘  └──────────────┬───────────────┘  │
│           ▼                            ▼                  │
│  ┌──────────────┐          ┌───────────────────────┐     │
│  │   MySQL 8.0  │          │       Redis 7.x       │     │
│  │   (主库)     │          │  (令牌黑名单/缓存)     │     │
│  └──────────────┘          └───────────────────────┘     │
└───────────────────────────────────────────────────────────┘
```

### 1.2 各层职责说明

| 层级 | 组件 | 职责 |
|------|------|------|
| **客户端层** | Uniapp (Vue3) | 四端合一打包，通过 `role` 字段动态切换页面路由和功能菜单 |
| **接入层** | Nginx | 反向代理、HTTPS 终止、静态资源托管、限流 |
| **API路由层** | `app/api/v1/*.py` | 接收 HTTP 请求、参数校验、调用 Service、返回响应 |
| **核心层** | `app/core/` | JWT 令牌管理、密码哈希、RBAC 权限矩阵、依赖注入、全局配置、异常处理 |
| **业务服务层** | `app/services/*.py` | 业务逻辑编排、事务管理、跨模型操作 |
| **数据模型层** | `app/models/*.py` | SQLAlchemy ORM 映射，定义表结构、关系、索引 |
| **数据存储层** | MySQL + Redis | MySQL 存持久化业务数据，Redis 存令牌黑名单 + 缓存 |

### 1.3 关键技术决策

| 决策项 | 选择 | 理由 |
|--------|------|------|
| Web框架 | FastAPI | 异步支持、自动生成 OpenAPI 文档、Pydantic 校验、高性能 |
| ORM | SQLAlchemy 2.0 | 成熟稳定、支持异步、迁移工具链完善（Alembic） |
| 认证 | JWT 双令牌 | 无状态、适合前后端分离、支持令牌刷新和撤销 |
| 密码存储 | bcrypt | 抗暴力破解、自带盐值、业界标准 |
| 前端框架 | Uniapp (Vue3) | 一套代码多端发布（H5/小程序/App）、生态成熟 |
| 状态管理 | Pinia | Vue3 官方推荐、TypeScript 友好、轻量 |
| 数据库 | MySQL 8.0 | 关系型数据、ACID 事务、成熟稳定 |
| 缓存 | Redis 7.x | 高性能内存数据库、支持过期策略、适合令牌黑名单 |

---

## 2. MySQL 核心数据表设计

### 2.1 用户表（users）

> 四方角色统一存储，通过 `role` 字段区分

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INT | PK, AUTO_INCREMENT | 用户ID |
| username | VARCHAR(50) | UNIQUE, NOT NULL, INDEX | 用户名 |
| email | VARCHAR(255) | UNIQUE, NOT NULL, INDEX | 邮箱 |
| phone | VARCHAR(20) | UNIQUE, NULLABLE | 手机号 |
| password_hash | VARCHAR(255) | NOT NULL | bcrypt 哈希密码 |
| role | ENUM('visitor','exhibitor','boss','organizer') | NOT NULL, INDEX | **用户角色（核心字段）** |
| status | ENUM('pending','active','disabled','banned') | NOT NULL, DEFAULT 'active', INDEX | 用户状态 |
| nickname | VARCHAR(100) | NULLABLE | 昵称 |
| avatar_url | VARCHAR(500) | NULLABLE | 头像URL |
| gender | ENUM('male','female','other','secret') | NULLABLE | 性别 |
| company | VARCHAR(200) | NULLABLE | 公司名称（展商/主办方必填） |
| position | VARCHAR(100) | NULLABLE | 职位 |
| bio | TEXT | NULLABLE | 个人简介 |
| created_at | DATETIME | NOT NULL, DEFAULT NOW() | 创建时间 |
| updated_at | DATETIME | NOT NULL, ON UPDATE NOW() | 更新时间 |
| last_login_at | DATETIME | NULLABLE | 最后登录时间 |
| deleted_at | DATETIME | NULLABLE | 软删除时间 |

**索引：**
- `idx_role_status` — `(role, status)` 复合索引，按角色和状态快速筛选
- `idx_username` — 唯一索引
- `idx_email` — 唯一索引

**说明：** 四种角色（visitor/exhibitor/boss/organizer）共用一张用户表。角色切换时只需更新 `role` 字段，无需多表关联。展商/主办方的公司信息存储在 `company` 字段，展商详细资质信息存储在 `exhibitors` 扩展表。

---

### 2.2 展会表（exhibitions）

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INT | PK, AUTO_INCREMENT | 展会ID |
| name | VARCHAR(200) | NOT NULL, INDEX | 展会名称 |
| short_name | VARCHAR(50) | NULLABLE | 展会简称 |
| description | TEXT | NULLABLE | 展会描述 |
| cover_url | VARCHAR(500) | NULLABLE | 封面图URL |
| start_date | DATETIME | NOT NULL | 开始时间 |
| end_date | DATETIME | NOT NULL | 结束时间 |
| registration_deadline | DATETIME | NULLABLE | 报名截止时间 |
| venue | VARCHAR(200) | NOT NULL | 举办场馆 |
| address | VARCHAR(500) | NOT NULL | 详细地址 |
| city | VARCHAR(100) | NOT NULL, INDEX | 城市 |
| status | ENUM('draft','pending','published','ongoing','ended','cancelled') | NOT NULL, DEFAULT 'draft', INDEX | 展会状态 |
| organizer_id | INT | FK→users.id, NOT NULL, INDEX | 主办方用户ID |
| approved_by | INT | FK→users.id, NULLABLE | 审批人（老板）ID |
| approved_at | DATETIME | NULLABLE | 审批时间 |
| reject_reason | TEXT | NULLABLE | 驳回原因 |
| total_booths | INT | DEFAULT 0 | 总展位数（冗余） |
| available_booths | INT | DEFAULT 0 | 可用展位数（冗余） |
| visitor_count | INT | DEFAULT 0 | 报名观众数（冗余） |
| created_at | DATETIME | NOT NULL, DEFAULT NOW() | 创建时间 |
| updated_at | DATETIME | NOT NULL, ON UPDATE NOW() | 更新时间 |

**索引：**
- `idx_city_status` — `(city, status)` 复合索引，按城市和状态筛选展会
- `idx_date_range` — `(start_date, end_date)` 复合索引，按时间范围查询

**状态流转：**
```
draft → pending → published → ongoing → ended
                    ↓
                cancelled
```
- `draft`：主办方创建后未提交
- `pending`：提交审核（等待老板审批）
- `published`：审核通过，对游客可见
- `ongoing`：展会进行中（自动或手动触发）
- `ended`：展会结束
- `cancelled`：取消（可随时取消）

---

### 2.3 展商信息表（exhibitors）

> 展商的**扩展信息**表，与 `users` 表是 1:1 关系

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INT | PK, AUTO_INCREMENT | 展商信息ID |
| user_id | INT | FK→users.id, UNIQUE, NOT NULL, INDEX | 用户ID |
| company_name | VARCHAR(200) | NOT NULL | 公司全称 |
| company_short_name | VARCHAR(50) | NULLABLE | 公司简称 |
| logo_url | VARCHAR(500) | NULLABLE | 公司Logo |
| business_scope | TEXT | NULLABLE | 经营范围 |
| website | VARCHAR(200) | NULLABLE | 公司官网 |
| contact_name | VARCHAR(50) | NULLABLE | 联系人姓名 |
| contact_phone | VARCHAR(20) | NULLABLE | 联系人电话 |
| contact_email | VARCHAR(255) | NULLABLE | 联系人邮箱 |
| qualification_files | TEXT | NULLABLE | 资质文件（JSON数组） |
| status | VARCHAR(20) | NOT NULL, DEFAULT 'pending' | 审核状态: pending/approved/rejected |
| verified_at | DATETIME | NULLABLE | 审核通过时间 |
| created_at | DATETIME | NOT NULL, DEFAULT NOW() | 创建时间 |
| updated_at | DATETIME | NOT NULL, ON UPDATE NOW() | 更新时间 |

---

### 2.4 展位表（booths）

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INT | PK, AUTO_INCREMENT | 展位ID |
| exhibition_id | INT | FK→exhibitions.id, NOT NULL, INDEX | 所属展会ID |
| exhibitor_id | INT | FK→users.id, NULLABLE, INDEX | 展商用户ID（空=未分配） |
| booth_number | VARCHAR(50) | NOT NULL | 展位编号，如 A-001 |
| name | VARCHAR(200) | NULLABLE | 展位名称/标题 |
| description | TEXT | NULLABLE | 展位描述 |
| area | FLOAT | NULLABLE | 展位面积（㎡） |
| price | FLOAT | NULLABLE | 展位价格 |
| floor | INT | NULLABLE | 楼层 |
| zone | VARCHAR(50) | NULLABLE | 展区，如 A区/B区 |
| status | ENUM('available','reserved','occupied','maintenance') | NOT NULL, DEFAULT 'available', INDEX | 展位状态 |
| created_at | DATETIME | NOT NULL, DEFAULT NOW() | 创建时间 |
| updated_at | DATETIME | NOT NULL, ON UPDATE NOW() | 更新时间 |

**索引：**
- `idx_exhibition_booth` — `(exhibition_id, booth_number)` 唯一复合索引，一个展会内展位编号唯一
- `idx_exhibition_status` — `(exhibition_id, status)` 复合索引，按展会筛选可用展位

**状态流转：**
```
available → reserved → occupied → available
    ↓
maintenance
```

---

### 2.5 展品表（products）

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INT | PK, AUTO_INCREMENT | 展品ID |
| exhibitor_id | INT | FK→users.id, NOT NULL, INDEX | 展商用户ID |
| booth_id | INT | FK→booths.id, NULLABLE, INDEX | 所属展位ID |
| exhibition_id | INT | FK→exhibitions.id, NULLABLE, INDEX | 所属展会ID（冗余） |
| name | VARCHAR(200) | NOT NULL, INDEX | 展品名称 |
| description | TEXT | NULLABLE | 展品描述 |
| category | VARCHAR(100) | NOT NULL, INDEX | 展品类目 |
| images | TEXT | NULLABLE | 图片URL列表（JSON数组） |
| price | FLOAT | NULLABLE | 展品价格 |
| specs | TEXT | NULLABLE | 规格参数（JSON字符串） |
| status | ENUM('draft','published','offline') | NOT NULL, DEFAULT 'draft', INDEX | 展品状态 |
| created_at | DATETIME | NOT NULL, DEFAULT NOW() | 创建时间 |
| updated_at | DATETIME | NOT NULL, ON UPDATE NOW() | 更新时间 |

**索引：**
- `idx_exhibitor_status` — `(exhibitor_id, status)` 复合索引
- `idx_category_status` — `(category, status)` 复合索引

---

### 2.6 采购需求表（procurement_requests）

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INT | PK, AUTO_INCREMENT | 采购需求ID |
| visitor_id | INT | FK→users.id, NOT NULL, INDEX | 发布者（游客）用户ID |
| title | VARCHAR(200) | NOT NULL, INDEX | 采购标题 |
| description | TEXT | NULLABLE | 需求详细描述 |
| category | VARCHAR(100) | NOT NULL, INDEX | 采购品类 |
| budget_min | FLOAT | NULLABLE | 预算下限 |
| budget_max | FLOAT | NULLABLE | 预算上限 |
| deadline | DATETIME | NULLABLE | 采购截止日期 |
| status | ENUM('pending','matched','completed','cancelled') | NOT NULL, DEFAULT 'pending', INDEX | 需求状态 |
| created_at | DATETIME | NOT NULL, DEFAULT NOW() | 创建时间 |
| updated_at | DATETIME | NOT NULL, ON UPDATE NOW() | 更新时间 |

**索引：**
- `idx_visitor_status` — `(visitor_id, status)` 复合索引
- `idx_status_category` — `(status, category)` 复合索引

### 采购匹配表（procurement_matches）

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INT | PK, AUTO_INCREMENT | 匹配ID |
| procurement_id | INT | FK→procurement_requests.id, NOT NULL, INDEX | 采购需求ID |
| exhibitor_id | INT | FK→users.id, NOT NULL, INDEX | 展商用户ID |
| message | TEXT | NULLABLE | 展商留言/报价说明 |
| quoted_price | FLOAT | NULLABLE | 报价 |
| is_accepted | BOOLEAN | NULLABLE | 是否被采购方接受（NULL=待回应） |
| created_at | DATETIME | NOT NULL, DEFAULT NOW() | 匹配时间 |

**索引：**
- `uk_procurement_exhibitor` — `(procurement_id, exhibitor_id)` 唯一复合索引，一个展商对一个需求只能匹配一次

---

### 2.7 沟通消息表（messages）

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INT | PK, AUTO_INCREMENT | 消息ID |
| sender_id | INT | FK→users.id, NOT NULL, INDEX | 发送者用户ID |
| receiver_id | INT | FK→users.id, NOT NULL, INDEX | 接收者用户ID |
| title | VARCHAR(200) | NOT NULL | 消息标题 |
| content | TEXT | NOT NULL | 消息内容 |
| is_read | BOOLEAN | DEFAULT FALSE, INDEX | 是否已读 |
| read_at | DATETIME | NULLABLE | 读取时间 |
| created_at | DATETIME | NOT NULL, DEFAULT NOW() | 发送时间 |

**索引：**
- `idx_receiver_read` — `(receiver_id, is_read)` 复合索引，快速查询未读消息
- `idx_sender_created` — `(sender_id, created_at)` 复合索引

---

### 2.8 团队表（teams）

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INT | PK, AUTO_INCREMENT | 团队ID |
| boss_id | INT | FK→users.id, NOT NULL, INDEX | 老板用户ID（团队创建者） |
| name | VARCHAR(100) | NOT NULL | 团队名称 |
| description | VARCHAR(500) | NULLABLE | 团队描述 |
| created_at | DATETIME | NOT NULL, DEFAULT NOW() | 创建时间 |
| updated_at | DATETIME | NOT NULL, ON UPDATE NOW() | 更新时间 |

### 团队成员表（team_members）

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INT | PK, AUTO_INCREMENT | 成员ID |
| team_id | INT | FK→teams.id, NOT NULL, INDEX | 团队ID |
| user_id | INT | FK→users.id, NOT NULL, INDEX | 成员用户ID |
| role_in_team | ENUM('admin','member') | NOT NULL, DEFAULT 'member' | 团队内角色 |
| joined_at | DATETIME | NOT NULL, DEFAULT NOW() | 加入时间 |

**索引：**
- `uk_team_user` — `(team_id, user_id)` 唯一复合索引，防止重复加入

---

### 2.9 数据报表相关表

#### 观众报名/收藏表（visitor_registrations）

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INT | PK, AUTO_INCREMENT | 报名ID |
| visitor_id | INT | FK→users.id, NOT NULL, INDEX | 游客用户ID |
| exhibition_id | INT | FK→exhibitions.id, NOT NULL, INDEX | 展会ID |
| is_favorite | BOOLEAN | DEFAULT FALSE | 是否收藏 |
| is_registered | BOOLEAN | DEFAULT FALSE | 是否已报名 |
| ticket_code | VARCHAR(100) | UNIQUE, NULLABLE | 电子票编码 |
| check_in_at | DATETIME | NULLABLE | 签到时间 |
| created_at | DATETIME | NOT NULL, DEFAULT NOW() | 创建时间 |
| updated_at | DATETIME | NOT NULL, ON UPDATE NOW() | 更新时间 |

**索引：**
- `uk_visitor_exhibition` — `(visitor_id, exhibition_id)` 唯一复合索引
- `idx_exhibition_registered` — `(exhibition_id, is_registered)` 复合索引

#### 展会评价表（reviews）

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INT | PK, AUTO_INCREMENT | 评价ID |
| user_id | INT | FK→users.id, NOT NULL, INDEX | 评价用户ID |
| exhibition_id | INT | FK→exhibitions.id, NOT NULL, INDEX | 被评价展会ID |
| rating | INT | NOT NULL | 评分（1-5星） |
| content | TEXT | NULLABLE | 评价内容 |
| created_at | DATETIME | NOT NULL, DEFAULT NOW() | 评价时间 |

**索引：**
- `uk_user_exhibition_review` — `(user_id, exhibition_id)` 唯一复合索引，一个用户对一个展会只能评价一次
- `idx_exhibition_rating` — `(exhibition_id, rating)` 复合索引

#### 审计日志表（audit_logs）

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | INT | PK, AUTO_INCREMENT | 日志ID |
| user_id | INT | FK→users.id, NULLABLE, INDEX | 操作用户ID |
| user_role | VARCHAR(20) | NULLABLE | 用户角色 |
| action | VARCHAR(100) | NOT NULL, INDEX | 操作类型 |
| resource_type | VARCHAR(50) | NOT NULL | 资源类型 |
| resource_id | VARCHAR(50) | NULLABLE | 资源ID |
| detail | TEXT | NULLABLE | 操作详情（JSON） |
| ip_address | VARCHAR(45) | NULLABLE | 请求IP |
| user_agent | VARCHAR(500) | NULLABLE | User-Agent |
| created_at | DATETIME | NOT NULL, DEFAULT NOW() | 操作时间 |

**索引：**
- `idx_user_action` — `(user_id, action)` 复合索引
- `idx_created_at` — 时间索引，用于按时间范围查询

---

### 2.10 ER 关系总览

```
users (1) ──< exhibitions (N)       # 主办方创建展会
users (1) ──< booths (N)            # 展商拥有展位
users (1) ──< products (N)          # 展商管理展品
users (1) ──< procurement_requests (N)  # 游客发布采购
users (1) ──< messages_sent (N)     # 发送消息
users (1) ──< messages_received (N) # 接收消息
users (1) ──< team_members (N)      # 团队成员
users (1) ──|| exhibitors (1)       # 展商扩展信息（1:1）
users (1) ──< teams (N)             # 老板创建团队
users (1) ──< registrations (N)     # 游客报名
users (1) ──< reviews (N)           # 用户评价
users (1) ──< audit_logs (N)        # 审计日志

exhibitions (1) ──< booths (N)      # 展会包含展位
exhibitions (1) ──< products (N)    # 展会包含展品
exhibitions (1) ──< registrations (N)   # 展会有报名记录
exhibitions (1) ──< reviews (N)     # 展会有评价

booths (1) ──< products (N)         # 展位陈列展品

procurement_requests (1) ──< procurement_matches (N)  # 采购需求有多个匹配

teams (1) ──< team_members (N)      # 团队包含成员
```

---

## 3. JWT 双令牌认证方案

### 3.1 令牌设计

| 令牌类型 | 存储位置 | 有效期 | 携带方式 | 用途 |
|----------|----------|--------|----------|------|
| **Access Token** | 客户端内存/变量 | **15分钟** | HTTP Header: `Authorization: Bearer <token>` | 访问受保护API |
| **Refresh Token** | 客户端本地存储（localStorage/Storage） | **7天** | HTTP Body: `{"refresh_token": "..."}` | 刷新 Access Token |

### 3.2 JWT Payload 结构

**Access Token 载荷：**
```json
{
  "sub": "123",          // 用户ID
  "role": "exhibitor",   // 用户角色
  "type": "access",      // 令牌类型
  "iat": 1700000000,     // 签发时间
  "exp": 1700000900      // 过期时间（15分钟后）
}
```

**Refresh Token 载荷：**
```json
{
  "sub": "123",          // 用户ID
  "role": "exhibitor",   // 用户角色
  "type": "refresh",     // 令牌类型
  "iat": 1700000000,     // 签发时间
  "exp": 1700604800      // 过期时间（7天后）
}
```

### 3.3 令牌刷新流程

```
客户端                          FastAPI 服务
  │                                │
  │  1. 请求API (Access Token)      │
  │ ─────────────────────────────> │
  │                                │
  │  2. 验证Access Token           │
  │  ── 有效 → 正常响应             │
  │  ── 过期 → 401 Unauthorized    │
  │ <───────────────────────────── │
  │                                │
  │  3. 发起刷新请求                │
  │  POST /api/v1/auth/refresh     │
  │  { refresh_token: "xxx" }      │
  │ ─────────────────────────────> │
  │                                │
  │  4. 验证Refresh Token          │
  │  ── 验证签名 & 未过期           │
  │  ── 检查type="refresh"         │
  │  ── 检查是否在黑名单中          │
  │  ── 验证用户状态是否active      │
  │                                │
  │  5. 返回新令牌对                │
  │  {                             │
  │    access_token: "新令牌",      │
  │    refresh_token: "新令牌",     │
  │    expires_in: 900             │
  │  }                             │
  │ <───────────────────────────── │
  │                                │
  │  6. 用新令牌重试原请求          │
  │ ─────────────────────────────> │
  │                                │
```

### 3.4 服务端实现（app/core/security.py）

关键函数：

| 函数 | 说明 |
|------|------|
| `hash_password(password)` | bcrypt 哈希密码 |
| `verify_password(plain, hashed)` | 验证密码 |
| `create_access_token(user_id, role)` | 创建 Access Token（15分钟） |
| `create_refresh_token(user_id, role)` | 创建 Refresh Token（7天） |
| `create_token_pair(user_id, role)` | 一次性创建令牌对 |
| `decode_token(token)` | 解码并验证 JWT（含过期校验） |
| `get_token_payload(token)` | 获取载荷（不验证过期，用于黑名单检查） |

### 3.5 安全策略

| 策略 | 实现方式 |
|------|----------|
| **密码强度** | bcrypt 12轮迭代哈希，抗暴力破解 |
| **令牌签名** | HS256 算法，密钥来自环境变量 `JWT_SECRET_KEY` |
| **短时效** | Access Token 仅15分钟，降低泄露风险 |
| **令牌刷新** | Refresh Token 7天有效期，刷新时签发全新令牌对 |
| **令牌撤销** | Redis 黑名单机制，登出时加入黑名单，支持单个令牌撤销 |
| **令牌类型校验** | Payload 中 `type` 字段区分 access/refresh，防止混用 |
| **用户状态校验** | 每次请求检查用户状态是否为 `active` |
| **密码修改后失效** | 修改密码时清除所有 Refresh Token（通过 Redis 黑名单） |
| **IP绑定（可选）** | 可在 Payload 中加入 `ip` 字段，校验请求来源 |

### 3.6 前端令牌管理（Uniapp）

```
请求拦截器（app/src/api/request.ts）
  │
  ├── 检查是否有 Access Token
  │   ├── 有 → 添加 Authorization Header
  │   └── 无 → 直接请求（公开接口）
  │
  ├── 发起请求
  │
  └── 响应拦截器
      ├── 200 → 正常返回
      ├── 401 → 触发刷新流程
      │   ├── 检查是否有 Refresh Token
      │   │   ├── 有 → 调用刷新接口
      │   │   │   ├── 成功 → 更新令牌对，重试原请求
      │   │   │   └── 失败 → 跳转登录页
      │   │   └── 无 → 跳转登录页
      └── 其他错误 → 正常抛出
```

---

## 4. RBAC 四角色权限模型

### 4.1 角色定义

| 角色 | 枚举值 | 描述 |
|------|--------|------|
| 🧑 游客 | `visitor` | 浏览展会、搜索展商、发布采购需求 |
| 🏪 展商 | `exhibitor` | 管理展品、查看采购需求、在线沟通 |
| 👑 老板 | `boss` | 查看数据报表、审批展会、管理团队 |
| 🎪 主办方 | `organizer` | 管理展会、审核展商、分配展位 |

### 4.2 权限矩阵

> ✅ = 拥有权限 | ❌ = 无权限

| 权限 | 权限值 | 游客 | 展商 | 主办方 | 老板 |
|------|--------|:----:|:----:|:------:|:----:|
| **用户管理** | | | | | |
| 查看个人信息 | `user:view` | ✅ | ✅ | ✅ | ✅ |
| 编辑个人信息 | `user:edit` | ✅ | ✅ | ✅ | ✅ |
| 管理用户（禁用/封禁） | `user:manage` | ❌ | ❌ | ❌ | ✅ |
| **展会管理** | | | | | |
| 查看展会列表 | `exhibition:list` | ✅ | ✅ | ✅ | ✅ |
| 查看展会详情 | `exhibition:view` | ✅ | ✅ | ✅ | ✅ |
| 创建展会 | `exhibition:create` | ❌ | ❌ | ✅ | ❌ |
| 编辑展会 | `exhibition:edit` | ❌ | ❌ | ✅ | ❌ |
| 删除展会 | `exhibition:delete` | ❌ | ❌ | ❌ | ❌ |
| 审批展会 | `exhibition:approve` | ❌ | ❌ | ❌ | ✅ |
| 发布/下架展会 | `exhibition:publish` | ❌ | ❌ | ✅ | ❌ |
| **展位管理** | | | | | |
| 查看展位列表 | `booth:list` | ✅ | ✅ | ✅ | ✅ |
| 查看展位详情 | `booth:view` | ✅ | ✅ | ✅ | ✅ |
| 预订展位 | `booth:book` | ❌ | ✅ | ❌ | ❌ |
| 编辑展位信息 | `booth:edit` | ❌ | ✅ | ❌ | ❌ |
| 创建展位 | `booth:create` | ❌ | ❌ | ✅ | ❌ |
| 分配展位 | `booth:assign` | ❌ | ❌ | ✅ | ❌ |
| **展品管理** | | | | | |
| 查看展品列表 | `product:list` | ✅ | ✅ | ✅ | ✅ |
| 查看展品详情 | `product:view` | ✅ | ✅ | ✅ | ✅ |
| 创建展品 | `product:create` | ❌ | ✅ | ❌ | ❌ |
| 编辑展品 | `product:edit` | ❌ | ✅ | ❌ | ❌ |
| 删除展品 | `product:delete` | ❌ | ✅ | ❌ | ❌ |
| **采购需求** | | | | | |
| 发布采购需求 | `procurement:create` | ✅ | ❌ | ❌ | ❌ |
| 查看采购列表 | `procurement:list` | ✅ | ✅ | ✅ | ✅ |
| 查看采购详情 | `procurement:view` | ✅ | ✅ | ✅ | ✅ |
| 编辑采购需求 | `procurement:edit` | ✅ | ❌ | ❌ | ❌ |
| 匹配采购需求 | `procurement:match` | ❌ | ✅ | ❌ | ❌ |
| **报名/收藏** | | | | | |
| 报名/收藏展会 | `registration:create` | ✅ | ❌ | ❌ | ❌ |
| 管理报名（签到/统计） | `registration:manage` | ❌ | ❌ | ✅ | ❌ |
| **消息沟通** | | | | | |
| 发送消息 | `message:send` | ✅ | ✅ | ✅ | ✅ |
| 查看消息 | `message:view` | ✅ | ✅ | ✅ | ✅ |
| **数据统计** | | | | | |
| 查看自身数据 | `stats:view_self` | ✅ | ✅ | ✅ | ✅ |
| 查看全局数据 | `stats:view_global` | ❌ | ❌ | ✅ | ✅ |
| 导出数据 | `stats:export` | ❌ | ❌ | ✅ | ✅ |
| **审核管理** | | | | | |
| 查看审核列表 | `audit:view` | ❌ | ❌ | ✅ | ✅ |
| 审核处理 | `audit:review` | ❌ | ❌ | ❌ | ✅ |
| **团队管理** | | | | | |
| 创建团队 | `team:create` | ❌ | ❌ | ❌ | ✅ |
| 编辑团队 | `team:edit` | ❌ | ❌ | ❌ | ✅ |
| 删除团队 | `team:delete` | ❌ | ❌ | ❌ | ✅ |
| 管理团队成员 | `team:member:manage` | ❌ | ❌ | ❌ | ✅ |
| **系统配置** | | | | | |
| 系统配置 | `system:config` | ❌ | ❌ | ❌ | ✅ |

### 4.3 权限控制实现方式（FastAPI 依赖注入）

三层防护体系，从粗到细：

#### 第一层：角色拦截（require_role）

```python
# 要求必须是展商
@app.get("/api/v1/products")
async def list_products(
    current_user: CurrentUser = Depends(require_exhibitor),
):
    ...

# 要求必须是主办方或老板
@app.get("/api/v1/stats/global")
async def global_stats(
    current_user: CurrentUser = Depends(require_staff),  # organizer or boss
):
    ...
```

#### 第二层：权限检查（require_permission）

```python
# 要求拥有"审批展会"权限
@app.post("/api/v1/exhibitions/{id}/approve")
async def approve_exhibition(
    id: int,
    current_user: CurrentUser = Depends(require_permission(Permission.EXHIBITION_APPROVE)),
):
    ...
```

#### 第三层：数据级隔离（在 Service 层实现）

```python
# 展商只能查看自己的展品
def get_my_products(db: Session, user_id: int):
    return db.query(Product).filter(Product.exhibitor_id == user_id).all()

# 主办方只能查看自己创建的展会
def get_my_exhibitions(db: Session, organizer_id: int):
    return db.query(Exhibition).filter(Exhibition.organizer_id == organizer_id).all()
```

### 4.4 快捷依赖一览

```python
# app/core/dependencies.py 中定义的快捷依赖

require_auth          # 任意登录用户
require_visitor       # 仅游客
require_exhibitor     # 仅展商
require_organizer     # 仅主办方
require_boss          # 仅老板
require_staff         # 主办方或老板（运营人员）
require_any_user      # 任意角色（等价于 require_auth）
```

---

## 5. FastAPI 目录结构

### 5.1 完整目录树

```
expo-hub-backend/
├── app/                          # 应用主目录
│   ├── __init__.py
│   │
│   ├── main.py                   # 应用入口：创建 FastAPI 实例、注册路由、中间件
│   │
│   ├── api/                      # API 路由层
│   │   ├── __init__.py
│   │   ├── router.py             # 统一路由注册（包含所有 v1 路由）
│   │   └── v1/                   # API v1 版本
│   │       ├── __init__.py
│   │       ├── auth.py           # 认证接口：登录/注册/刷新/登出
│   │       ├── users.py          # 用户接口：个人信息/修改密码/设置
│   │       ├── exhibitions.py    # 展会接口：CRUD/发布/审批
│   │       ├── exhibitors.py     # 展商信息接口：资质审核/信息维护
│   │       ├── booths.py         # 展位接口：布局/预订/分配
│   │       ├── procurements.py   # 采购需求接口：发布/匹配/报价
│   │       ├── messages.py       # 消息接口：发送/列表/已读
│   │       ├── teams.py          # 团队接口：创建/成员管理
│   │       ├── dashboard.py      # 仪表盘接口：统计数据
│   │       └── audit.py          # 审计日志接口：查询/导出
│   │
│   ├── core/                     # 核心层（全局共享）
│   │   ├── __init__.py
│   │   ├── config.py             # 配置管理（Pydantic Settings，多环境支持）
│   │   ├── constants.py          # 枚举常量（UserStatus, ExhibitionStatus 等）
│   │   ├── security.py           # 安全核心（JWT 令牌管理、密码哈希）
│   │   ├── permissions.py        # RBAC 权限定义（Role/Permission 枚举 + 权限映射表）
│   │   ├── dependencies.py       # 依赖注入（get_current_user, require_role, require_permission）
│   │   ├── exceptions.py         # 自定义异常类（UnauthorizedException, ForbiddenException）
│   │   └── middleware.py         # 中间件（CORS、请求日志、响应时间）
│   │
│   ├── models/                   # 数据模型层（SQLAlchemy ORM）
│   │   ├── __init__.py           # 导入所有模型，确保 Base 注册
│   │   ├── user.py               # User 模型
│   │   ├── exhibition.py         # Exhibition 模型
│   │   ├── exhibitor.py          # Exhibitor 模型（展商扩展信息）
│   │   ├── booth.py              # Booth + Product 模型
│   │   ├── procurement.py        # ProcurementRequest + ProcurementMatch 模型
│   │   ├── message.py            # Message 模型
│   │   ├── team.py               # Team + TeamMember 模型
│   │   ├── registration.py       # VisitorRegistration 模型
│   │   ├── review.py             # Review 模型
│   │   └── audit_log.py          # AuditLog 模型
│   │
│   ├── schemas/                  # Pydantic Schema 层（请求/响应校验）
│   │   ├── __init__.py
│   │   ├── auth.py               # 登录/注册/刷新请求/响应 Schema
│   │   ├── user.py               # 用户信息 Schema
│   │   ├── exhibition.py         # 展会 CRUD Schema
│   │   ├── exhibitor.py          # 展商信息 Schema
│   │   ├── booth.py              # 展位/展品 Schema
│   │   ├── procurement.py        # 采购需求 Schema
│   │   ├── message.py            # 消息 Schema
│   │   ├── team.py               # 团队 Schema
│   │   ├── dashboard.py          # 仪表盘/统计 Schema
│   │   └── common.py             # 通用 Schema（分页、响应包装）
│   │
│   ├── services/                 # 业务服务层（核心业务逻辑）
│   │   ├── __init__.py
│   │   ├── auth_service.py       # 认证服务：注册/登录/刷新/登出逻辑
│   │   ├── user_service.py       # 用户服务：个人信息管理
│   │   ├── exhibition_service.py # 展会服务：CRUD/状态流转/审批
│   │   ├── exhibitor_service.py  # 展商服务：资质审核/信息维护
│   │   ├── booth_service.py      # 展位服务：布局/预订/分配
│   │   ├── procurement_service.py # 采购服务：发布/匹配/报价
│   │   ├── message_service.py    # 消息服务：发送/列表/已读
│   │   ├── team_service.py       # 团队服务：创建/成员管理
│   │   ├── dashboard_service.py  # 仪表盘服务：统计数据聚合
│   │   └── audit_service.py      # 审计服务：日志记录/查询
│   │
│   ├── database/                 # 数据库连接层
│   │   ├── __init__.py
│   │   ├── base.py               # SQLAlchemy Base 声明
│   │   ├── session.py            # 数据库会话管理（get_db 依赖）
│   │   └── redis.py              # Redis 连接管理（令牌黑名单、缓存）
│   │
│   └── utils/                    # 工具函数
│       ├── __init__.py
│       ├── pagination.py         # 分页工具（Page/PageParams）
│       └── response.py           # 统一响应格式（success_response, error_response）
│
├── alembic/                      # 数据库迁移
│   ├── versions/                 # 迁移版本文件
│   │   └── 001_init_expo_hub_schema.py  # 初始建表迁移
│   ├── env.py                    # Alembic 环境配置
│   └── script.py.mako            # 迁移脚本模板
│
├── tests/                        # 测试目录
│   ├── __init__.py
│   ├── conftest.py               # 测试夹具（测试数据库、测试客户端）
│   ├── test_auth_api.py          # 认证接口测试
│   ├── test_auth_unit.py         # 认证单元测试
│   ├── test_models_unit.py       # 模型单元测试
│   ├── test_schemas_unit.py      # Schema 单元测试
│   └── test_permission_isolation.py  # 权限隔离测试
│
├── .env                          # 环境变量（开发环境）
├── .env.production               # 环境变量（生产环境）
├── requirements.txt              # Python 依赖
├── Dockerfile                    # Docker 构建文件
├── docker-compose.yml            # Docker Compose（含 MySQL + Redis）
├── docker-compose.staging.yml    # 预发布环境配置
├── Makefile                      # 常用命令（run/test/migrate/docker）
├── alembic.ini                   # Alembic 配置文件
└── nginx/
    └── nginx.conf                # Nginx 反向代理配置
```

### 5.2 各目录职责

| 目录 | 职责 | 是否可被其他层引用 |
|------|------|:------------------:|
| `api/` | 路由定义 + 参数校验 + 调用 Service | 仅被 `main.py` 引用 |
| `core/` | 全局共享：安全、权限、配置、异常 | 所有层均可引用 |
| `models/` | ORM 数据模型定义 | 被 `services/` 和 `api/` 引用 |
| `schemas/` | Pydantic 请求/响应模型 | 被 `api/` 和 `services/` 引用 |
| `services/` | 业务逻辑编排 | 仅被 `api/` 引用 |
| `database/` | 数据库连接管理 | 被 `core/` 和 `services/` 引用 |
| `utils/` | 工具函数 | 所有层均可引用 |

### 5.3 依赖方向（严格单向）

```
api/ → services/ → models/ + database/
  ↓          ↓
schemas/   core/（安全、权限、配置）
```

- **严禁反向引用**：`services/` 不能引用 `api/`，`models/` 不能引用 `services/`
- **core/ 全局可用**：任何层都可以引用 `core/` 中的安全、权限、配置模块

---

## 6. Uniapp 前端四端路由规划

### 6.1 架构说明

采用 **单项目分包加载** 策略：

- **主包**（`pages/`）：公共页面（首页、登录、注册、搜索、公共列表）
- **子包1**（`pages_visitor/`）：游客专属页面
- **子包2**（`pages_exhibitor/`）：展商专属页面
- **子包3**（`pages_organizer/`）：主办方专属页面
- **子包4**（`pages_boss/`）：老板专属页面

> 路由守卫（`src/utils/role.js`）根据当前用户 `role` 字段动态控制页面访问权限，无权限页面自动跳转。

### 6.2 公共路由（所有角色可见）

| 路由路径 | 页面 | 说明 |
|----------|------|------|
| `pages/index/index` | 🏠 首页 | 展会推荐、搜索入口、快捷功能 |
| `pages/exhibition/list` | 📋 展会列表 | 按城市/日期/状态筛选 |
| `pages/exhibition/detail` | 📄 展会详情 | 展位图、展商列表、报名入口 |
| `pages/booth/detail` | 🪑 展位详情 | 展位信息、展品列表 |
| `pages/product/list` | 📦 展品列表 | 按展会/品类筛选 |
| `pages/product/detail` | 📦 展品详情 | 展品信息、联系展商 |
| `pages/procurement/list` | 📝 采购需求列表 | 按品类/预算筛选 |
| `pages/procurement/detail` | 📝 采购需求详情 | 需求详情、匹配报价 |
| `pages/message/list` | 💬 消息中心 | 会话列表 |
| `pages/message/conversation` | 💬 会话详情 | 聊天界面 |
| `pages/user/login` | 🔐 登录 | 支持手机号/邮箱登录 |
| `pages/user/register` | 🔐 注册 | 注册时选择角色 |
| `pages/user/profile` | 👤 个人主页 | 个人信息、切换角色 |
| `pages/user/settings` | ⚙️ 设置 | 修改密码、退出登录 |
| `pages/search/index` | 🔍 搜索 | 全局搜索（展会/展商/展品） |

### 6.3 游客端路由（pages_visitor/）

| 路由路径 | 页面 | 说明 |
|----------|------|------|
| `pages_visitor/my_registrations` | 🎫 我的报名/收藏 | 已报名和收藏的展会列表 |
| `pages_visitor/my_procurements` | 📝 我的采购需求 | 已发布的采购需求列表 |
| `pages_visitor/procurement_create` | ✏️ 发布采购需求 | 填写采购需求表单 |

**游客端功能总览：**
- 浏览展会列表和详情
- 搜索展商和展品
- 报名/收藏展会
- 发布采购需求
- 查看展商对需求的匹配/报价
- 在线沟通（发送消息）

### 6.4 展商端路由（pages_exhibitor/）

| 路由路径 | 页面 | 说明 |
|----------|------|------|
| `pages_exhibitor/dashboard` | 📊 展商工作台 | 数据概览、快捷操作 |
| `pages_exhibitor/my_booths` | 🪑 我的展位 | 已预订的展位列表 |
| `pages_exhibitor/my_products` | 📦 我的展品 | 展品管理列表 |
| `pages_exhibitor/product_create` | ✏️ 添加展品 | 展品发布表单 |
| `pages_exhibitor/product_edit` | ✏️ 编辑展品 | 展品编辑表单 |
| `pages_exhibitor/procurement_matches` | 📝 采购匹配 | 可匹配的采购需求列表 |

**展商端功能总览：**
- 管理展品（CRUD）
- 预订/管理展位
- 查看和匹配采购需求
- 在线沟通（与游客/主办方）
- 查看自身数据统计

### 6.5 主办方端路由（pages_organizer/）

| 路由路径 | 页面 | 说明 |
|----------|------|------|
| `pages_organizer/dashboard` | 📊 主办方工作台 | 数据概览、快捷操作 |
| `pages_organizer/exhibition_list` | 📋 我的展会 | 创建的展会列表 |
| `pages_organizer/exhibition_create` | ✏️ 创建展会 | 展会创建表单 |
| `pages_organizer/exhibition_edit` | ✏️ 编辑展会 | 展会编辑表单 |
| `pages_organizer/booth_layout` | 🗺️ 展位布局 | 展位平面图管理 |
| `pages_organizer/booth_create` | ✏️ 创建展位 | 添加展位 |
| `pages_organizer/booth_assign` | ✏️ 分配展位 | 将展位分配给展商 |
| `pages_organizer/registrations` | 🎫 报名管理 | 查看报名观众、签到 |
| `pages_organizer/statistics` | 📊 数据统计 | 展会数据报表 |

**主办方端功能总览：**
- 创建和管理展会
- 设计展位布局
- 审核展商资质
- 分配展位给展商
- 管理观众报名和签到
- 查看展会数据统计

### 6.6 老板端路由（pages_boss/）

| 路由路径 | 页面 | 说明 |
|----------|------|------|
| `pages_boss/dashboard` | 📊 老板驾驶舱 | 全局数据概览、关键指标 |
| `pages_boss/stats_overview` | 📊 全局概览 | 平台整体数据 |
| `pages_boss/stats_users` | 👥 用户分析 | 用户增长/活跃度/角色分布 |
| `pages_boss/stats_exhibitions` | 📋 展会分析 | 展会数量/参与度/转化率 |
| `pages_boss/approval_list` | ✅ 待审批列表 | 待审批的展会/展商 |
| `pages_boss/approval_detail` | ✅ 审批详情 | 审批处理页面 |
| `pages_boss/team_list` | 👥 团队列表 | 管理团队 |
| `pages_boss/team_create` | ✏️ 创建团队 | 新建团队 |
| `pages_boss/team_members` | 👥 成员管理 | 添加/移除成员 |

**老板端功能总览：**
- 查看全局数据报表（用户/展会/交易）
- 审批展会发布
- 审核展商资质
- 管理团队（创建/编辑/成员管理）
- 系统配置管理

### 6.7 TabBar 配置（公共底栏）

| 索引 | 页面 | 图标 | 说明 |
|:----:|------|:----:|------|
| 0 | `pages/index/index` | 🏠 | 首页 |
| 1 | `pages/exhibition/list` | 📋 | 展会 |
| 2 | `pages/message/list` | 💬 | 消息 |
| 3 | `pages/user/profile` | 👤 | 我的 |

> 各端专属页面通过「我的」页面中的功能入口进入，或通过角色工作台（dashboard）首页进入。

### 6.8 角色路由守卫逻辑

```
用户打开任意页面
  │
  ├── 判断页面是否属于公共路由
  │   ├── 是 → 正常渲染
  │   └── 否 → 检查用户是否已登录
  │       ├── 未登录 → 跳转登录页
  │       └── 已登录 → 检查用户角色是否有权限
  │           ├── 有权限 → 正常渲染
  │           └── 无权限 → 提示"无权限访问"并跳转首页
  │
  └── 角色切换时
      ├── 清除上一角色的页面缓存
      ├── 更新路由权限表
      └── 跳转到新角色的 Dashboard
```

---

## 附录 A：关键配置清单

### A.1 环境变量（.env）

```bash
# 应用
APP_NAME=ExpoHub
APP_VERSION=1.0.0
DEBUG=true
API_PREFIX=/api/v1

# 数据库
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=root
DB_NAME=expo_hub

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# JWT
JWT_SECRET_KEY=your-secret-key-change-in-production
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

# Token 黑名单
TOKEN_BLACKLIST_ENABLED=true
TOKEN_BLACKLIST_PREFIX=token_blacklist:

# CORS
CORS_ORIGINS=["*"]
```

### A.2 Docker Compose 服务

| 服务 | 镜像 | 端口映射 | 说明 |
|------|------|:--------:|------|
| `app` | expohub-backend | 8000:8000 | FastAPI 应用 |
| `db` | mysql:8.0 | 3306:3306 | MySQL 数据库 |
| `redis` | redis:7-alpine | 6379:6379 | Redis 缓存/黑名单 |
| `nginx` | nginx:alpine | 80:80, 443:443 | 反向代理 |

---

## 附录 B：API 接口概览

| 模块 | 方法 | 路径 | 权限 | 说明 |
|------|------|------|:----:|------|
| **Auth** | POST | `/api/v1/auth/register` | 公开 | 用户注册 |
| | POST | `/api/v1/auth/login` | 公开 | 用户登录 |
| | POST | `/api/v1/auth/refresh` | 公开 | 刷新令牌 |
| | POST | `/api/v1/auth/logout` | 登录用户 | 登出（撤销令牌） |
| **Users** | GET | `/api/v1/users/me` | 登录用户 | 获取个人信息 |
| | PUT | `/api/v1/users/me` | 登录用户 | 更新个人信息 |
| | PUT | `/api/v1/users/me/password` | 登录用户 | 修改密码 |
| **Exhibitions** | GET | `/api/v1/exhibitions` | 公开 | 展会列表（分页） |
| | GET | `/api/v1/exhibitions/{id}` | 公开 | 展会详情 |
| | POST | `/api/v1/exhibitions` | 主办方 | 创建展会 |
| | PUT | `/api/v1/exhibitions/{id}` | 主办方 | 编辑展会 |
| | POST | `/api/v1/exhibitions/{id}/publish` | 主办方 | 发布展会 |
| | POST | `/api/v1/exhibitions/{id}/approve` | 老板 | 审批展会 |
| **Exhibitors** | GET | `/api/v1/exhibitors/{id}` | 公开 | 展商信息 |
| | PUT | `/api/v1/exhibitors/me` | 展商 | 更新展商信息 |
| | POST | `/api/v1/exhibitors/{id}/verify` | 老板 | 审核展商 |
| **Booths** | GET | `/api/v1/exhibitions/{id}/booths` | 公开 | 展会展位列表 |
| | POST | `/api/v1/booths/{id}/book` | 展商 | 预订展位 |
| | POST | `/api/v1/booths` | 主办方 | 创建展位 |
| | POST | `/api/v1/booths/{id}/assign` | 主办方 | 分配展位 |
| **Products** | GET | `/api/v1/products` | 公开 | 展品列表 |
| | GET | `/api/v1/products/{id}` | 公开 | 展品详情 |
| | POST | `/api/v1/products` | 展商 | 创建展品 |
| | PUT | `/api/v1/products/{id}` | 展商 | 编辑展品 |
| | DELETE | `/api/v1/products/{id}` | 展商 | 删除展品 |
| **Procurements** | GET | `/api/v1/procurements` | 公开 | 采购需求列表 |
| | GET | `/api/v1/procurements/{id}` | 公开 | 采购需求详情 |
| | POST | `/api/v1/procurements` | 游客 | 发布采购需求 |
| | POST | `/api/v1/procurements/{id}/match` | 展商 | 匹配/报价 |
| | PUT | `/api/v1/matches/{id}/accept` | 游客 | 接受报价 |
| **Messages** | GET | `/api/v1/messages` | 登录用户 | 消息列表 |
| | POST | `/api/v1/messages` | 登录用户 | 发送消息 |
| | PUT | `/api/v1/messages/{id}/read` | 登录用户 | 标记已读 |
| **Teams** | GET | `/api/v1/teams` | 老板 | 团队列表 |
| | POST | `/api/v1/teams` | 老板 | 创建团队 |
| | POST | `/api/v1/teams/{id}/members` | 老板 | 添加成员 |
| | DELETE | `/api/v1/teams/{id}/members/{uid}` | 老板 | 移除成员 |
| **Dashboard** | GET | `/api/v1/dashboard/overview` | 主办方/老板 | 全局概览 |
| | GET | `/api/v1/dashboard/exhibitor` | 展商 | 展商数据 |
| **Audit** | GET | `/api/v1/audit/logs` | 主办方/老板 | 审计日志 |
| | GET | `/api/v1/audit/pending` | 老板 | 待审批列表 |

---

## 附录 C：技术风险与应对

| 风险 | 影响 | 应对措施 |
|------|------|----------|
| JWT Secret 泄露 | 令牌可被伪造 | 使用环境变量 + 定期轮换 + HS256 + 短时效 |
| 数据库性能瓶颈 | 高并发下查询慢 | 合理索引 + 读写分离 + Redis 缓存热点数据 |
| 权限绕过 | 越权访问数据 | 三层权限校验 + 数据级隔离 + 定期渗透测试 |
| 前端令牌 XSS 窃取 | 用户身份被盗 | Access Token 存内存变量 + Refresh Token 存 Storage（httponly） |
| 并发预订冲突 | 同一展位被多人预订 | 数据库行级锁 + 乐观锁版本号 |

---

> **文档状态**：✅ 已与现有代码完全对齐，所有表结构、API、权限模型均已在 `app/models/`、`app/core/permissions.py`、`app/core/security.py` 中落地实现。
