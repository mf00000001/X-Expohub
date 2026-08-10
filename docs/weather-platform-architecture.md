# 🌤️ 天气查询平台 — 完整技术方案

> 版本：v1.0 | 状态：📋 方案设计阶段

---

## 📑 目录

1. [项目概述](#1-项目概述)
2. [整体架构设计](#2-整体架构设计)
3. [核心功能模块](#3-核心功能模块)
4. [数据库设计](#4-数据库设计)
5. [API 接口设计](#5-api-接口设计)
6. [外部天气 API 集成](#6-外部天气-api-集成)
7. [前端设计方案](#7-前端设计方案)
8. [缓存与性能优化](#8-缓存与性能优化)
9. [部署方案](#9-部署方案)
10. [安全策略](#10-安全策略)

---

## 1. 项目概述

### 1.1 项目定位

面向 C 端用户的**智能天气查询平台**，支持全球城市天气实时查询、多日预报、天气预警、空气质量指数（AQI）、生活指数等功能。

### 1.2 核心用户场景

| 用户 | 场景 | 频率 |
|------|------|:----:|
| 🌍 普通用户 | 查询当前城市天气 | 每日 |
| ✈️ 差旅用户 | 查询目的地未来天气 | 出行前 |
| 🏃 户外运动者 | 查询运动指数、紫外线 | 高频 |
| 🏠 家庭用户 | 关注多个城市天气（老家、子女所在城市） | 每日 |
| 📊 数据分析师 | 查看历史天气趋势 | 按需 |

### 1.3 技术选型

| 层级 | 技术 | 理由 |
|------|------|------|
| **后端框架** | FastAPI (Python 3.11+) | 异步高性能、自动 OpenAPI 文档、团队已有技术积累 |
| **数据库** | PostgreSQL 15 + PostGIS | 支持地理空间查询、JSON 支持好、ACID 事务 |
| **缓存** | Redis 7.x | 天气数据缓存（TTL 过期）、限流计数器 |
| **ORM** | SQLAlchemy 2.0 (async) | 成熟稳定、异步支持、Alembic 迁移 |
| **任务队列** | Celery + Redis | 定时拉取天气数据、天气预警推送 |
| **前端** | Vue 3 + Vite + TypeScript | 生态丰富、开发体验好 |
| **前端 UI** | Naive UI / Element Plus | 美观、组件丰富 |
| **地图** | Leaflet / 高德地图 API | 天气地图展示 |
| **天气数据源** | OpenWeatherMap / 和风天气 / 中国气象局 | 多源聚合、提高准确性 |
| **容器化** | Docker + Docker Compose | 一键部署、环境一致性 |
| **反向代理** | Nginx | HTTPS、静态资源、限流 |

---

## 2. 整体架构设计

### 2.1 架构总览

```
┌─────────────────────────────────────────────────────────────────┐
│                        客户端层                                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐    │
│  │  Web H5  │  │ 微信小程序 │  │  PWA     │  │  管理后台     │    │
│  │ (Vue 3)  │  │ (Uni-app) │  │(Service  │  │  (Vue 3)     │    │
│  │          │  │           │  │ Worker)  │  │              │    │
│  └────┬─────┘  └────┬──────┘  └────┬─────┘  └──────┬───────┘    │
│       └─────────────┼──────────────┼───────────────┘             │
│                     │   统一 API   │                              │
├─────────────────────┼──────────────┼──────────────────────────────┤
│                Nginx (HTTPS / 限流 / 静态资源)                     │
├─────────────────────┼──────────────┼──────────────────────────────┤
│                     ▼              ▼                              │
│              FastAPI 应用服务层                                    │
│  ┌───────────────────────────────────────────────────────────┐   │
│  │  API 路由层 (app/api/)                                     │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────┐   │   │
│  │  │ weather  │ │forecast  │ │  aqi     │ │  alerts    │   │   │
│  │  │ 实时天气  │ │ 预报     │ │ 空气质量  │ │ 天气预警   │   │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └────────────┘   │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────┐   │   │
│  │  │ cities   │ │favorites │ │ history  │ │  indices   │   │   │
│  │  │ 城市搜索  │ │ 收藏     │ │ 历史天气  │ │ 生活指数   │   │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └────────────┘   │   │
│  ├───────────────────────────────────────────────────────────┤   │
│  │  核心层 (app/core/)                                        │   │
│  │  ┌──────────┐ ┌──────────┐ ┌────────────┐ ┌──────────┐  │   │
│  │  │ config   │ │security  │ │ exceptions │ │middleware│  │   │
│  │  │ 多源配置  │ │ JWT/限流 │ │ 异常处理    │ │CORS/日志 │  │   │
│  │  └──────────┘ └──────────┘ └────────────┘ └──────────┘  │   │
│  ├───────────────────────────────────────────────────────────┤   │
│  │  业务服务层 (app/services/)                                │   │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐      │   │
│  │  │weather_service│ │city_service  │ │alert_service │      │   │
│  │  │ 多源聚合/缓存 │ │ 城市搜索/管理 │ │ 预警推送     │      │   │
│  │  └──────────────┘ └──────────────┘ └──────────────┘      │   │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐      │   │
│  │  │aqi_service   │ │forecast_svc  │ │history_svc   │      │   │
│  │  │ 空气数据     │ │ 预报数据     │ │ 历史统计     │      │   │
│  │  └──────────────┘ └──────────────┘ └──────────────┘      │   │
│  ├───────────────────────────────────────────────────────────┤   │
│  │  外部 API 网关 (app/gateway/)                              │   │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐      │   │
│  │  │openweather   │ │qweather(和风)│ │cma(气象局)   │      │   │
│  │  │   adapter    │ │   adapter    │ │   adapter    │      │   │
│  │  └──────────────┘ └──────────────┘ └──────────────┘      │   │
│  └───────────────────────────────────────────────────────────┘   │
├──────────────────────┬───────────────────────────────────────────┤
│                      ▼                                            │
│                数据存储层                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │ PostgreSQL   │  │  Redis 7.x   │  │  Celery Beat        │   │
│  │ + PostGIS    │  │  缓存+限流    │  │  定时任务调度        │   │
│  └──────────────┘  └──────────────┘  └──────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

### 2.2 数据流

```
用户请求 → Nginx → FastAPI → 检查 Redis 缓存
                              ├── 命中 → 直接返回
                              └── 未命中 → 调用外部天气 API
                                           ├── 聚合多源数据
                                           ├── 写入 Redis (TTL)
                                           └── 返回给用户

定时任务 → Celery Beat → fetch_weather_data()
                         ├── 拉取热门城市天气
                         ├── 更新缓存
                         └── 检测预警并推送
```

---

## 3. 核心功能模块

### 3.1 功能矩阵

| 模块 | 功能 | 优先级 | 说明 |
|------|------|:------:|------|
| 🌡️ **实时天气** | 当前天气查询 | P0 | 温度、湿度、风速、天气现象、体感温度 |
| | 逐小时预报 | P1 | 未来 48 小时逐小时预报 |
| | 逐日预报 | P0 | 未来 7-15 天预报 |
| 🏙️ **城市管理** | 城市搜索 | P0 | 全球城市模糊搜索 |
| | GPS 定位 | P0 | 根据经纬度反查城市 |
| | 热门城市 | P1 | 预设热门城市列表 |
| | 多城市收藏 | P1 | 用户收藏多个城市 |
| 💨 **空气质量** | AQI 指数 | P1 | 实时空气质量指数 |
| | 污染物详情 | P1 | PM2.5/PM10/O₃/NO₂/SO₂/CO |
| ⚠️ **天气预警** | 预警推送 | P1 | 极端天气预警通知 |
| | 预警列表 | P1 | 查看当前生效的预警 |
| 📊 **历史天气** | 历史查询 | P2 | 过去天气数据查询 |
| | 数据统计 | P2 | 月度/年度天气统计 |
| 🏃 **生活指数** | 运动指数 | P2 | 是否适合户外运动 |
| | 紫外线指数 | P1 | UV 指数及建议 |
| | 穿衣指数 | P2 | 穿衣建议 |
| | 洗车指数 | P3 | 是否适合洗车 |
| 🗺️ **天气地图** | 雷达图 | P2 | 降水雷达图 |
| | 温度分布图 | P3 | 区域温度颜色图 |
| 👤 **用户系统** | 注册/登录 | P1 | 手机号或邮箱注册 |
| | 收藏管理 | P1 | 城市的增删排序 |
| | 设置偏好 | P2 | 温度单位(℃/℉)、通知设置 |

---

## 4. 数据库设计

### 4.1 用户表（users）

```sql
CREATE TABLE users (
    id            SERIAL PRIMARY KEY,
    username      VARCHAR(50)  NOT NULL UNIQUE,
    email         VARCHAR(255) NULL UNIQUE,
    phone         VARCHAR(20)  NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    nickname      VARCHAR(100) NULL,
    avatar_url    VARCHAR(500) NULL,
    temp_unit     VARCHAR(5)   NOT NULL DEFAULT 'celsius',  -- celsius/fahrenheit
    lang          VARCHAR(10)  NOT NULL DEFAULT 'zh-CN',
    status        VARCHAR(20)  NOT NULL DEFAULT 'active',   -- active/disabled/banned
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    last_login_at TIMESTAMPTZ  NULL
);

CREATE INDEX idx_users_status ON users(status);
```

### 4.2 城市表（cities）

```sql
CREATE TABLE cities (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(200) NOT NULL,          -- 城市中文名
    name_en     VARCHAR(200) NOT NULL,          -- 城市英文名
    country     VARCHAR(100) NOT NULL,          -- 国家
    country_code VARCHAR(5)  NOT NULL,          -- 国家代码 CN/US
    admin1      VARCHAR(100) NULL,              -- 省/州
    admin2      VARCHAR(100) NULL,              -- 市/区
    latitude    DOUBLE PRECISION NOT NULL,       -- 纬度
    longitude   DOUBLE PRECISION NOT NULL,       -- 经度
    timezone    VARCHAR(50)  NOT NULL DEFAULT 'Asia/Shanghai',
    population  BIGINT NULL,                    -- 人口（决定热门程度）
    priority    INT NOT NULL DEFAULT 0,         -- 排序优先级（越大越靠前）
    is_hot      BOOLEAN NOT NULL DEFAULT FALSE,  -- 是否热门城市
    owm_city_id INT NULL,                       -- OpenWeatherMap City ID
    qw_city_id  VARCHAR(50) NULL,               -- 和风天气 City ID
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- PostGIS 地理空间索引（用于 GPS 反查最近城市）
SELECT AddGeometryColumn('cities', 'geom', 4326, 'POINT', 2);
CREATE INDEX idx_cities_geom ON cities USING GIST(geom);
CREATE INDEX idx_cities_name ON cities USING GIN(to_tsvector('simple', name));
CREATE INDEX idx_cities_country ON cities(country_code);
CREATE INDEX idx_cities_hot ON cities(is_hot, priority DESC);

-- 初始化时更新 geom 字段
-- UPDATE cities SET geom = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326);
```

### 4.3 用户收藏表（user_favorites）

```sql
CREATE TABLE user_favorites (
    id          SERIAL PRIMARY KEY,
    user_id     INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    city_id     INT NOT NULL REFERENCES cities(id) ON DELETE CASCADE,
    sort_order  INT NOT NULL DEFAULT 0,
    is_default  BOOLEAN NOT NULL DEFAULT FALSE,  -- 是否设为默认城市
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(user_id, city_id)
);

CREATE INDEX idx_favorites_user ON user_favorites(user_id, sort_order);
```

### 4.4 天气缓存表（weather_cache）

> 用于持久化存储最近查询的天气数据，作为 Redis 的二级缓存

```sql
CREATE TABLE weather_cache (
    id              SERIAL PRIMARY KEY,
    city_id         INT NOT NULL REFERENCES cities(id),
    weather_type    VARCHAR(20) NOT NULL,  -- current/hourly/daily/alert
    data            JSONB NOT NULL,        -- 天气数据 JSON
    source          VARCHAR(50) NOT NULL,  -- openweather/qweather/cma
    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at      TIMESTAMPTZ NOT NULL,
    UNIQUE(city_id, weather_type, source)
);

CREATE INDEX idx_weather_cache_expires ON weather_cache(expires_at);
```

### 4.5 天气预警记录表（weather_alerts）

```sql
CREATE TABLE weather_alerts (
    id              SERIAL PRIMARY KEY,
    city_id         INT NOT NULL REFERENCES cities(id),
    alert_id        VARCHAR(100) NOT NULL UNIQUE,  -- 外部 API 的预警 ID
    title           VARCHAR(300) NOT NULL,
    description     TEXT NULL,
    severity        VARCHAR(20) NOT NULL,  -- minor/moderate/severe/extreme
    event_type      VARCHAR(50) NOT NULL,  -- 暴雨/台风/高温/寒潮/...
    start_time      TIMESTAMPTZ NOT NULL,
    end_time        TIMESTAMPTZ NOT NULL,
    source          VARCHAR(50) NOT NULL,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_alerts_city_active ON weather_alerts(city_id, is_active);
CREATE INDEX idx_alerts_severity ON weather_alerts(severity);
CREATE INDEX idx_alerts_time ON weather_alerts(start_time, end_time);
```

### 4.6 查询日志表（query_logs）

```sql
CREATE TABLE query_logs (
    id          SERIAL PRIMARY KEY,
    user_id     INT NULL REFERENCES users(id),
    city_id     INT NULL REFERENCES cities(id),
    query_type  VARCHAR(20) NOT NULL,   -- current/forecast/aqi/alert
    ip_address  VARCHAR(45) NULL,
    user_agent  VARCHAR(500) NULL,
    cache_hit   BOOLEAN NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_query_logs_created ON query_logs(created_at);
```

### 4.7 ER 关系图

```
users ──< user_favorites >── cities
  │                              │
  │                              ├──< weather_cache
  │                              ├──< weather_alerts
  │                              └──< query_logs
  └──< query_logs
```

---

## 5. API 接口设计

### 5.1 接口总览

| 模块 | 方法 | 路径 | 认证 | 说明 |
|------|------|------|:----:|------|
| **天气** | GET | `/api/v1/weather/current` | 否 | 实时天气（按城市名/GPS） |
| | GET | `/api/v1/weather/current/{city_id}` | 否 | 实时天气（按城市ID） |
| | GET | `/api/v1/weather/hourly` | 否 | 逐小时预报（48h） |
| | GET | `/api/v1/weather/daily` | 否 | 逐日预报（7-15天） |
| **城市** | GET | `/api/v1/cities/search` | 否 | 城市模糊搜索 |
| | GET | `/api/v1/cities/geocode` | 否 | GPS 反查城市 |
| | GET | `/api/v1/cities/hot` | 否 | 热门城市列表 |
| | GET | `/api/v1/cities/{id}` | 否 | 城市详情 |
| **AQI** | GET | `/api/v1/aqi/current` | 否 | 当前空气质量 |
| | GET | `/api/v1/aqi/forecast` | 否 | AQI 预报 |
| **预警** | GET | `/api/v1/alerts` | 否 | 预警列表（按城市） |
| | GET | `/api/v1/alerts/active` | 否 | 所有活跃预警 |
| **生活指数** | GET | `/api/v1/indices` | 否 | 生活指数列表 |
| **历史** | GET | `/api/v1/history` | 否 | 历史天气查询 |
| | GET | `/api/v1/history/stats` | 否 | 历史天气统计 |
| **收藏** | GET | `/api/v1/favorites` | ✅ | 我的收藏列表 |
| | POST | `/api/v1/favorites` | ✅ | 添加收藏 |
| | DELETE | `/api/v1/favorites/{city_id}` | ✅ | 删除收藏 |
| | PUT | `/api/v1/favorites/sort` | ✅ | 排序收藏 |
| **用户** | POST | `/api/v1/auth/register` | 否 | 注册 |
| | POST | `/api/v1/auth/login` | 否 | 登录 |
| | GET | `/api/v1/users/me` | ✅ | 个人信息 |
| | PUT | `/api/v1/users/me` | ✅ | 更新设置 |

### 5.2 核心 API 详细设计

#### 5.2.1 实时天气查询

```
GET /api/v1/weather/current?city=beijing&lang=zh-CN&units=metric
GET /api/v1/weather/current?lat=39.9042&lon=116.4074&lang=zh-CN&units=metric

Response 200:
{
  "code": 200,
  "data": {
    "city": {
      "id": 1,
      "name": "北京",
      "name_en": "Beijing",
      "country": "中国",
      "country_code": "CN",
      "latitude": 39.9042,
      "longitude": 116.4074,
      "timezone": "Asia/Shanghai"
    },
    "current": {
      "temp": 22.5,              // 当前温度
      "feels_like": 21.8,        // 体感温度
      "temp_min": 18.0,          // 今日最低
      "temp_max": 26.0,          // 今日最高
      "humidity": 45,            // 湿度 %
      "pressure": 1013,          // 气压 hPa
      "wind_speed": 3.5,         // 风速 m/s
      "wind_deg": 180,           // 风向角度
      "wind_direction": "南风",   // 风向描述
      "visibility": 10000,       // 能见度 m
      "clouds": 20,              // 云量 %
      "uv_index": 3.0,           // 紫外线指数
      "weather": {
        "id": 800,
        "main": "Clear",         // 天气主类
        "description": "晴",     // 天气描述
        "icon": "01d"            // 图标代码
      },
      "sunrise": "05:30",
      "sunset": "18:45",
      "updated_at": "2025-01-15T10:30:00Z"
    },
    "source": "openweather"
  },
  "message": "ok"
}
```

#### 5.2.2 逐日预报

```
GET /api/v1/weather/daily?city_id=1&days=7&lang=zh-CN

Response 200:
{
  "code": 200,
  "data": {
    "city": { ... },
    "daily": [
      {
        "date": "2025-01-15",
        "temp": { "min": 18.0, "max": 26.0, "morn": 19.0, "day": 25.0, "eve": 22.0, "night": 18.5 },
        "feels_like": { "day": 24.5, "night": 17.0 },
        "humidity": 45,
        "wind_speed": 3.5,
        "wind_direction": "南风",
        "weather": { "id": 800, "main": "Clear", "description": "晴", "icon": "01d" },
        "rain_probability": 0.05,    // 降雨概率
        "snow_probability": 0.0,     // 降雪概率
        "sunrise": "05:30",
        "sunset": "18:45",
        "moon_phase": 0.25,
        "aqi": 65                    // 当天 AQI 预测
      },
      ...
    ],
    "source": "openweather"
  }
}
```

#### 5.2.3 城市搜索

```
GET /api/v1/cities/search?q=北京&limit=10&lang=zh-CN

Response 200:
{
  "code": 200,
  "data": {
    "cities": [
      {
        "id": 1,
        "name": "北京",
        "name_en": "Beijing",
        "country": "中国",
        "country_code": "CN",
        "admin1": "北京市",
        "latitude": 39.9042,
        "longitude": 116.4074
      },
      ...
    ],
    "total": 5
  }
}
```

#### 5.2.4 GPS 反查

```
GET /api/v1/cities/geocode?lat=39.9042&lon=116.4074&lang=zh-CN

Response 200:
{
  "code": 200,
  "data": {
    "id": 1,
    "name": "北京",
    "country": "中国",
    "distance_km": 0.5     // 距最近城市距离
  }
}
```

#### 5.2.5 天气预警

```
GET /api/v1/alerts/active?city_id=1

Response 200:
{
  "code": 200,
  "data": {
    "alerts": [
      {
        "id": "alert_001",
        "title": "暴雨橙色预警",
        "description": "预计未来6小时内降雨量将达50毫米以上...",
        "severity": "severe",       // minor/moderate/severe/extreme
        "event_type": "暴雨",
        "start_time": "2025-01-15T08:00:00Z",
        "end_time": "2025-01-15T20:00:00Z",
        "source": "qweather"
      }
    ]
  }
}
```

### 5.3 统一响应格式

```json
// 成功
{ "code": 200, "data": { ... }, "message": "ok" }

// 客户端错误
{ "code": 400, "data": null, "message": "参数错误", "detail": "city 参数不能为空" }

// 服务端错误
{ "code": 500, "data": null, "message": "服务器内部错误" }

// 限流
{ "code": 429, "data": null, "message": "请求过于频繁，请稍后再试", "retry_after": 60 }
```

---

## 6. 外部天气 API 集成

### 6.1 数据源选型

| 数据源 | 免费额度 | 实时天气 | 预报 | AQI | 预警 | 中文支持 |
|--------|:--------:|:--------:|:----:|:---:|:----:|:--------:|
| **OpenWeatherMap** | 1000次/天 | ✅ | ✅ 7天 | ✅ | ✅ | ⚠️ 部分 |
| **和风天气 (QWeather)** | 1000次/天 | ✅ | ✅ 15天 | ✅ | ✅ | ✅ 优秀 |
| **WeatherAPI** | 100万次/月 | ✅ | ✅ 3天 | ✅ | ✅ | ✅ |
| **中国气象局** | 有限 | ✅ | ✅ | ✅ | ✅ | ✅ 原生 |

**推荐方案：** 和风天气（主力，中文支持好） + OpenWeatherMap（备用，覆盖全球）

### 6.2 适配器模式

```python
# app/gateway/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class CurrentWeather:
    temp: float
    feels_like: float
    humidity: int
    wind_speed: float
    # ...

class WeatherAdapter(ABC):
    """天气数据源适配器基类"""

    @abstractmethod
    async def get_current(self, lat: float, lon: float) -> CurrentWeather:
        ...

    @abstractmethod
    async def get_forecast(self, lat: float, lon: float, days: int) -> list:
        ...

    @abstractmethod
    async def get_aqi(self, lat: float, lon: float) -> dict:
        ...

    @abstractmethod
    async def get_alerts(self, lat: float, lon: float) -> list:
        ...

# app/gateway/qweather_adapter.py
class QWeatherAdapter(WeatherAdapter):
    BASE_URL = "https://devapi.qweather.com/v7"

    async def get_current(self, lat, lon):
        # 调用和风天气 API
        ...

# app/gateway/openweather_adapter.py
class OpenWeatherAdapter(WeatherAdapter):
    BASE_URL = "https://api.openweathermap.org/data/3.0"

    async def get_current(self, lat, lon):
        # 调用 OpenWeatherMap API
        ...

# app/services/weather_service.py
class WeatherService:
    def __init__(self):
        self.primary = QWeatherAdapter()      # 主数据源
        self.fallback = OpenWeatherAdapter()  # 备用数据源

    async def get_current(self, lat, lon):
        try:
            return await self.primary.get_current(lat, lon)
        except Exception:
            return await self.fallback.get_current(lat, lon)
```

### 6.3 多源聚合策略

```
请求天气数据
  │
  ├── 尝试主数据源（和风天气）
  │   ├── 成功 → 转换统一格式 → 返回
  │   └── 失败/超时(3秒) → 尝试备用源
  │
  ├── 尝试备用源（OpenWeatherMap）
  │   ├── 成功 → 转换统一格式 → 返回
  │   └── 失败 → 返回缓存过期数据或报错
  │
  └── AQI 数据：优先和风天气，其次 WAQI
```

---

## 7. 前端设计方案

### 7.1 技术栈

```
Vue 3.4+ (Composition API + <script setup>)
├── TypeScript 5.x
├── Vite 5.x (构建工具)
├── Pinia (状态管理)
├── Vue Router 4.x (路由)
├── Naive UI (UI 组件库)
├── Tailwind CSS (工具类 CSS)
├── Leaflet (天气地图)
├── ECharts 5 (天气趋势图表)
├── axios (HTTP 请求，带拦截器)
└── @vueuse/core (工具 hooks)
```

### 7.2 目录结构

```
weather-app/
├── public/
│   ├── favicon.ico
│   └── manifest.json              # PWA 配置
├── src/
│   ├── api/                       # API 请求层
│   │   ├── index.ts               # axios 实例 + 拦截器
│   │   ├── weather.ts             # 天气相关 API
│   │   ├── cities.ts              # 城市搜索 API
│   │   ├── favorites.ts           # 收藏 API
│   │   └── auth.ts                # 认证 API
│   │
│   ├── assets/                    # 静态资源
│   │   ├── icons/                 # 天气图标
│   │   └── images/                # 背景图
│   │
│   ├── components/                # 公共组件
│   │   ├── layout/
│   │   │   ├── AppHeader.vue      # 顶部导航
│   │   │   └── AppFooter.vue      # 底部信息
│   │   ├── weather/
│   │   │   ├── WeatherCard.vue    # 天气卡片（当前天气）
│   │   │   ├── ForecastList.vue   # 预报列表
│   │   │   ├── HourlyChart.vue    # 逐小时温度曲线
│   │   │   ├── AqiBadge.vue       # AQI 徽章
│   │   │   └── WeatherIcon.vue    # 天气图标组件
│   │   ├── city/
│   │   │   ├── CitySearch.vue     # 城市搜索框
│   │   │   ├── CityCard.vue       # 城市卡片
│   │   │   └── FavoriteCities.vue # 收藏城市列表
│   │   └── common/
│   │       ├── Loading.vue
│   │       └── ErrorRetry.vue
│   │
│   ├── composables/               # 组合式函数
│   │   ├── useWeather.ts          # 天气数据获取
│   │   ├── useGeolocation.ts      # GPS 定位
│   │   ├── useFavorites.ts        # 收藏管理
│   │   └── useWeatherAlerts.ts    # 预警轮询
│   │
│   ├── layouts/                   # 布局
│   │   ├── DefaultLayout.vue
│   │   └── AdminLayout.vue
│   │
│   ├── router/                    # 路由
│   │   └── index.ts
│   │
│   ├── stores/                    # Pinia 状态
│   │   ├── weather.ts             # 天气数据
│   │   ├── cities.ts              # 城市状态
│   │   ├── user.ts                # 用户状态
│   │   └── settings.ts            # 设置（温度单位、语言）
│   │
│   ├── types/                     # TypeScript 类型
│   │   ├── weather.ts
│   │   ├── city.ts
│   │   └── api.ts
│   │
│   ├── utils/                     # 工具函数
│   │   ├── weather.ts             # 天气数据处理
│   │   ├── format.ts              # 格式化工具
│   │   └── constants.ts           # 常量
│   │
│   ├── views/                     # 页面
│   │   ├── HomeView.vue           # 首页（天气概览）
│   │   ├── CityDetailView.vue     # 城市天气详情
│   │   ├── SearchView.vue         # 城市搜索页
│   │   ├── ForecastView.vue       # 详细预报页
│   │   ├── AqiView.vue            # 空气质量详情
│   │   ├── MapView.vue            # 天气地图
│   │   ├── FavoritesView.vue      # 我的收藏
│   │   ├── SettingsView.vue       # 设置
│   │   ├── LoginView.vue          # 登录
│   │   └── RegisterView.vue       # 注册
│   │
│   ├── App.vue
│   └── main.ts
│
├── .env
├── .env.production
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts
└── tailwind.config.js
```

### 7.3 路由设计

```typescript
// src/router/index.ts
const routes = [
  {
    path: '/',
    component: DefaultLayout,
    children: [
      { path: '',              name: 'home',      component: () => import('@/views/HomeView.vue') },
      { path: 'city/:id',      name: 'city-detail', component: () => import('@/views/CityDetailView.vue') },
      { path: 'search',        name: 'search',     component: () => import('@/views/SearchView.vue') },
      { path: 'forecast/:id',  name: 'forecast',   component: () => import('@/views/ForecastView.vue') },
      { path: 'aqi/:id',       name: 'aqi',        component: () => import('@/views/AqiView.vue') },
      { path: 'map',           name: 'map',        component: () => import('@/views/MapView.vue') },
      { path: 'favorites',     name: 'favorites',  component: () => import('@/views/FavoritesView.vue'), meta: { auth: true } },
      { path: 'settings',      name: 'settings',   component: () => import('@/views/SettingsView.vue') },
    ]
  },
  { path: '/login',    name: 'login',    component: () => import('@/views/LoginView.vue') },
  { path: '/register', name: 'register', component: () => import('@/views/RegisterView.vue') },
]
```

### 7.4 首页布局设计

```
┌──────────────────────────────────────────┐
│  🔍 搜索城市...                  🇨🇳 ⚙️  │  ← AppHeader
├──────────────────────────────────────────┤
│                                          │
│  ┌────────────────────────────────────┐  │
│  │     🌤️  北京                       │  │  ← WeatherCard
│  │     22°C  晴                       │  │     (当前默认城市)
│  │     ↓18°  ↑26°  体感 21°          │  │
│  │     💧 45%  💨 南风 3级            │  │
│  │     🟢 AQI 65 良                   │  │
│  └────────────────────────────────────┘  │
│                                          │
│  ┌─ 逐小时预报 ───────────────────────┐  │
│  │ 现在  14时  15时  16时  17时  18时  │  │  ← HourlyChart
│  │ ☀️    ☀️    ⛅    ☁️    ☁️    🌧️   │  │
│  │ 22°   23°   24°   25°   24°   21°  │  │
│  └────────────────────────────────────┘  │
│                                          │
│  ┌─ 7天预报 ─────────────────────────┐  │
│  │ 今天    ☀️   18° / 26°             │  │  ← ForecastList
│  │ 明天    ⛅   19° / 24°             │  │
│  │ 后天    🌧️   15° / 20°            │  │
│  │ ...                                │  │
│  └────────────────────────────────────┘  │
│                                          │
│  ┌─ 收藏的城市 ───────────────────────┐  │
│  │ [北京 22°] [上海 25°] [广州 28°]  │  │  ← FavoriteCities
│  │ [+ 添加城市]                       │  │
│  └────────────────────────────────────┘  │
│                                          │
└──────────────────────────────────────────┘
```

### 7.5 PWA 支持

```typescript
// vite.config.ts 中使用 vite-plugin-pwa
// 支持离线查看缓存的天气数据
// 支持 Web Push 天气预警通知
```

---

## 8. 缓存与性能优化

### 8.1 多级缓存策略

```
┌──────────────────────────────────────────────┐
│              请求天气数据                      │
├──────────────────────────────────────────────┤
│  L1: 浏览器缓存 (Service Worker, ~5min)       │
│       ↓ miss                                  │
│  L2: Redis 缓存 (TTL: 10-30min)               │
│       Key: weather:{city_id}:current           │
│       ↓ miss                                  │
│  L3: PostgreSQL weather_cache 表 (TTL: 2h)    │
│       ↓ miss                                  │
│  L4: 外部天气 API (和风/OpenWeatherMap)        │
└──────────────────────────────────────────────┘
```

### 8.2 Redis 缓存设计

| Key Pattern | TTL | 说明 |
|-------------|:---:|------|
| `weather:current:{city_id}` | 10 min | 实时天气 |
| `weather:hourly:{city_id}` | 30 min | 逐小时预报 |
| `weather:daily:{city_id}` | 2 h | 逐日预报 |
| `weather:aqi:{city_id}` | 30 min | 空气质量 |
| `weather:alerts:{city_id}` | 10 min | 预警数据 |
| `cities:hot:{lang}` | 24 h | 热门城市列表 |
| `cities:search:{q}:{lang}` | 1 h | 搜索结果 |
| `ratelimit:{ip}:{endpoint}` | 1 min | 限流计数器 |

### 8.3 定时任务（Celery Beat）

| 任务 | 频率 | 说明 |
|------|:----:|------|
| `fetch_hot_cities_weather` | 每 10 分钟 | 拉取热门城市天气，预热缓存 |
| `fetch_alerts` | 每 5 分钟 | 拉取预警数据 |
| `clean_expired_cache` | 每小时 | 清理过期缓存 |
| `collect_stats` | 每天 | 收集查询统计 |

### 8.4 API 限流

```python
# 使用 Redis 滑动窗口算法
RATE_LIMITS = {
    "anonymous": 60,    # 匿名用户：60次/分钟
    "authenticated": 120,  # 登录用户：120次/分钟
    "weather_current": 30,  # 实时天气：30次/分钟
}
```

---

## 9. 部署方案

### 9.1 Docker Compose 编排

```yaml
# docker-compose.yml
version: "3.9"

services:
  # FastAPI 后端
  app:
    build:
      context: .
      dockerfile: Dockerfile
    image: weather-api:latest
    container_name: weather-api
    environment:
      - DATABASE_URL=postgresql+asyncpg://weather:${DB_PASSWORD}@db:5432/weather_db
      - REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/0
      - QWEATHER_API_KEY=${QWEATHER_API_KEY}
      - OWM_API_KEY=${OWM_API_KEY}
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    restart: unless-stopped
    networks:
      - weather-network

  # Celery Worker
  worker:
    build: .
    command: celery -A app.tasks worker -l info -c 4
    environment:
      - DATABASE_URL=...
      - REDIS_URL=...
    depends_on:
      - redis
      - db
    networks:
      - weather-network

  # Celery Beat (定时任务)
  beat:
    build: .
    command: celery -A app.tasks beat -l info
    depends_on:
      - redis
      - db
    networks:
      - weather-network

  # PostgreSQL + PostGIS
  db:
    image: postgis/postgis:15-3.4
    container_name: weather-db
    environment:
      POSTGRES_DB: weather_db
      POSTGRES_USER: weather
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - pg_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U weather -d weather_db"]
      interval: 10s
      retries: 5
    networks:
      - weather-network

  # Redis
  redis:
    image: redis:7-alpine
    container_name: weather-redis
    command: redis-server --requirepass ${REDIS_PASSWORD} --maxmemory 256mb --maxmemory-policy allkeys-lru
    volumes:
      - redis_data:/data
    networks:
      - weather-network

  # Nginx
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/conf.d/default.conf:ro
    depends_on:
      - app
    networks:
      - weather-network

  # Vue 前端 (开发环境)
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "3000:80"
    depends_on:
      - app
    networks:
      - weather-network

volumes:
  pg_data:
  redis_data:

networks:
  weather-network:
    driver: bridge
```

### 9.2 环境变量

```bash
# .env
APP_NAME=WeatherHub
APP_VERSION=1.0.0
DEBUG=true

# 数据库
DB_HOST=localhost
DB_PORT=5432
DB_USER=weather
DB_PASSWORD=change-me
DB_NAME=weather_db

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=change-me

# 外部 API 密钥
QWEATHER_API_KEY=your-key
OWM_API_KEY=your-key
WAQI_API_KEY=your-token

# JWT
JWT_SECRET_KEY=change-me-in-production
ACCESS_TOKEN_EXPIRE_MINUTES=30

# 缓存
WEATHER_CACHE_TTL_CURRENT=600      # 10分钟
WEATHER_CACHE_TTL_HOURLY=1800      # 30分钟
WEATHER_CACHE_TTL_DAILY=7200       # 2小时

# 限流
RATE_LIMIT_ANONYMOUS=60            # 匿名 60次/分钟
RATE_LIMIT_AUTHENTICATED=120       # 登录 120次/分钟
```

---

## 10. 安全策略

| 策略 | 实现 |
|------|------|
| **HTTPS** | Nginx 终止 SSL，Let's Encrypt 自动续期 |
| **API 密钥保护** | 外部天气 API Key 仅存后端环境变量，前端不可见 |
| **CORS** | 生产环境仅允许白名单域名 |
| **限流** | Redis 滑动窗口，匿名 60次/分钟，登录 120次/分钟 |
| **JWT 认证** | Access Token 30分钟有效 |
| **SQL 注入防护** | SQLAlchemy ORM 参数化查询 |
| **输入校验** | Pydantic Schema 严格校验 |
| **日志脱敏** | 敏感信息不记录到日志 |
| **依赖安全** | 定期 `pip-audit` / `npm audit` |

---

## 附录 A：项目文件清单（后端）

```
weather-platform/
├── app/
│   ├── __init__.py
│   ├── main.py                     # FastAPI 入口
│   ├── api/
│   │   ├── __init__.py
│   │   ├── router.py               # 路由注册
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── weather.py          # 天气接口
│   │       ├── forecast.py         # 预报接口
│   │       ├── cities.py           # 城市接口
│   │       ├── aqi.py              # AQI 接口
│   │       ├── alerts.py           # 预警接口
│   │       ├── indices.py          # 生活指数
│   │       ├── history.py          # 历史天气
│   │       ├── favorites.py        # 收藏接口
│   │       └── auth.py             # 认证接口
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py               # 配置管理
│   │   ├── security.py             # JWT + 密码哈希
│   │   ├── exceptions.py           # 异常类
│   │   ├── middleware.py           # 中间件(CORS/限流/日志)
│   │   └── dependencies.py         # 依赖注入
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── city.py
│   │   ├── favorite.py
│   │   ├── weather_cache.py
│   │   ├── weather_alert.py
│   │   └── query_log.py
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── weather.py
│   │   ├── city.py
│   │   ├── auth.py
│   │   └── common.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── weather_service.py
│   │   ├── city_service.py
│   │   ├── aqi_service.py
│   │   ├── alert_service.py
│   │   ├── forecast_service.py
│   │   ├── history_service.py
│   │   ├── favorite_service.py
│   │   └── auth_service.py
│   ├── gateway/
│   │   ├── __init__.py
│   │   ├── base.py                 # 适配器基类
│   │   ├── qweather_adapter.py
│   │   ├── openweather_adapter.py
│   │   └── waqi_adapter.py
│   ├── database/
│   │   ├── __init__.py
│   │   ├── session.py
│   │   └── redis.py
│   ├── tasks/
│   │   ├── __init__.py
│   │   ├── celery_app.py
│   │   ├── fetch_weather.py
│   │   └── fetch_alerts.py
│   └── utils/
│       ├── __init__.py
│       ├── response.py
│       └── pagination.py
├── alembic/
├── tests/
├── docker-compose.yml
├── Dockerfile
├── Makefile
├── requirements.txt
└── .env
```

---

## 附录 B：天气图标映射

| 天气代码 | 图标 | 日间 | 夜间 |
|----------|:----:|:----:|:----:|
| 晴 (Clear) | ☀️ | `01d` | `01n` |
| 少云 (Few Clouds) | 🌤️ | `02d` | `02n` |
| 多云 (Scattered) | ⛅ | `03d` | `03n` |
| 阴 (Overcast) | ☁️ | `04d` | `04n` |
| 小雨 (Light Rain) | 🌦️ | `09d` | `09n` |
| 中雨 (Rain) | 🌧️ | `10d` | `10n` |
| 大雨 (Heavy Rain) | 🌧️ | `10d` | `10n` |
| 雷阵雨 (Thunderstorm) | ⛈️ | `11d` | `11n` |
| 雪 (Snow) | 🌨️ | `13d` | `13n` |
| 雾 (Mist/Fog) | 🌫️ | `50d` | `50n` |

---

> **文档状态**：📋 方案设计完成，待开发启动。
> **预计工时**：后端 3 周 + 前端 3 周 + 联调测试 1 周 = 共 7 周
