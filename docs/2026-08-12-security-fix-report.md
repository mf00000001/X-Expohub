# ExpoHub 安全修复交付报告

> 日期:2026-08-12
> 依据:《数据隔离与安全评审报告》v1.1(`D:\reasonix work\docs\2026-08-12-expohub-security-review.md`)
> 范围:expohub-backend(FastAPI 后端)
> 结论:**P0 全部修复、P1 主要修复、统一 RBAC 依赖落地,三层验证体系全部通过**

---

## 1. 修复背景

外部专家对安全评审报告 v1.0 复核后指出:存在**匿名无鉴权接口**、**系统性 organizer 越权**(含未过审 pending 主办方即可越权)、**预约/收藏内存存储**、**登出/封禁闭环失效**等 P0/P1 缺陷。本报告记录针对这些缺陷的修复工作。

## 2. 修复清单(14 个文件,+303/-93)

### P0-1 匿名无鉴权接口(`app/api/dashboard.py`)
| 修复 | 说明 |
|---|---|
| `get_team_members` / `add_team_member` / `remove_team_member` | 补 `get_current_active_user` + `_require_admin_or_organizer` 鉴权 |
| `get_exhibition_registrations` | 补鉴权 + **展会归属校验**(organizer 仅可查看自己展会的报名),关闭 username+ticket_code 匿名泄露通道 |

### P0-2 系统性 organizer 越权(声明与执行背离 + 归属缺失)
| 文件 | 修复 |
|---|---|
| `app/api/products.py` | PUT/DELETE `is_admin` 仅剩 `admin`(原误含 organizer) |
| `app/api/reviews.py` | DELETE 同上(任何主办方删任意评价 → 仅 owner/admin) |
| `app/api/procurements.py` | PUT 仅 owner/admin(原误含 organizer) |
| `app/api/booths.py` | update 允许 owner/所属展会主办方/admin;delete 仅所属展会主办方/admin |
| `app/api/exhibitions.py` | PUT 仅 owner/admin;approve 增加 organizer_id 归属校验;**publish 同模式修复(第二轮:仅 owner/admin + 审核检查)** |
| `app/api/dashboard.py` | approve/reject 增加 organizer_id 归属校验 |

> **勘误记录(v1.1 → v1.2)**:v1.1 曾将 `exhibitions.py` publish 误判为"正确范例"(字面含归属校验),实际 `role not in ("admin","organizer")` 豁免使非 owner 主办方依旧放行(HTTP 实测 200)。第二轮修复改为 `exh.organizer_id != current_user.id and role != "admin"`,并补 `organizer_status == "approved"` 审核检查;实测越权 403、owner 发布 200。

### P0-2b 未过审(pending)主办方限制
| 文件 | 修复 |
|---|---|
| `app/api/dashboard.py` | `_require_admin_or_organizer` 增加 `organizer_status == "approved"` 检查(覆盖全部管理接口) |
| `app/api/exhibitions.py` | approve 增加审核状态检查 |

### P0-3 预约/收藏落库(原为内存存储)
| 文件 | 修复 |
|---|---|
| `app/models/appointment.py`(新增) | `appointments` 表(状态机扩展字段 buyer_id/exhibitor_id/exhibition_id/time_slot/status) |
| `app/models/favorite.py`(新增) | `favorites` 表(唯一约束防重复收藏) |
| `app/api/appointments.py` | 内存列表 → DB 读写(API 结构兼容) |
| `app/api/favorites.py` | 内存字典 → DB 读写,**收藏关系与 favorite_count 同事务提交**,解决重启后计数脱节 |
| `app/main.py` | 注册新模型(create_all 自动建表) |

### P1 加固
| 文件 | 修复 |
|---|---|
| `app/api/auth.py` | refresh 校验 `user.status == "active"`(**banned 用户无法续期**) |
| `app/api/booths.py` | book 仅限 exhibitor 角色(原注释"任何已登录用户均可预订") |
| `app/api/procurements.py` | `GET /{id}/matches`、`GET /{id}/recommendations` 补鉴权 + 归属校验(仅需求创建者/admin,**匿名报价泄露关闭**) |

### 统一 RBAC 依赖(报告 P0-2 验收标准)
| 文件 | 修复 |
|---|---|
| `app/api/deps.py` | 新增 `require_permission(permission)` 统一依赖(基于 `ROLE_PERMISSIONS` 声明表校验) |
| `app/core/permissions.py` | **admin 权限集补全 15 项**(EXHIBITION_*/BOOTH_*/PRODUCT_*/PROCUREMENT_*),声明表与路由行为一致;`has_permission` 从死代码变为真实执行 |
| `app/api/products.py` / `app/api/booths.py` | create 路由手写角色检查替换为 `Depends(require_permission(...))` |

### 附带修复
| 文件 | 修复 |
|---|---|
| `app/core/security.py` | **passlib 1.7.4 与 bcrypt≥4.1 不兼容**(登录 500)修复:直用 bcrypt 库,兼容现有 `$2b$` 哈希,无需迁移数据 |

## 3. 验证结果(三层验证体系)

| 层 | 命令 | 结果 |
|---|---|---|
| 项目测试 | `pytest tests/test_security_regression.py`(12 用例) | ✅ 12 passed |
| 权限表验证 | `python scripts/permissions_verify.py`(22 断言) | ✅ ALL PASS |
| API 隔离回归 | `python scripts/security_verify.py`(**12 断言,含 publish 越权**) | ✅ ALL PASS |
| 服务健康 | 后端 :8002 / 前端 :5173 | ✅ 200 / 200 |

### 隔离验证关键断言(全部通过)
- 匿名访问报名列表 → **401**
- organizer 改他人展品 → **403**
- **organizer 发布他人展会(publish)→ 403(第二轮新增)**;owner 发布自己展会 → 200
- pending 主办方访问管理统计 / 审批展会 → **403 / 403**
- buyer 预订展位 → **403**
- 匿名访问采购匹配(报价)→ **401**
- banned 用户 refresh 续期 → **401**
- 预约/收藏创建 → 200 且 **DB 落库确认**
- admin 拥有全部权限;organizer 有展会管理权无业务资源写权;exhibitor 有产品管理权无采购发布权;visitor/buyer 无管理权

## 4. 回归资产(可重复运行)

| 文件 | 说明 |
|---|---|
| `expohub-backend/tests/test_security_regression.py` | 角色设置 pytest 用例(12 个):权限映射表/has_permission/require_permission |
| `scripts/security_verify.py` | API 层隔离回归(11 断言,临时数据自清理) |
| `scripts/permissions_verify.py` | 权限映射表断言(22 项,纯单元级) |

## 5. 遗留事项

| 级别 | 事项 |
|---|---|
| P1 剩余 | TokenBlacklist(Redis 黑名单)仍为死代码,登出令牌撤销未实际接入(本次已修复 refresh 状态校验) |
| P2 | CORS 白名单化、生产 SECRET_KEY 强制随机、租户/组织维度(多主办方共存) |
| 其他 | 仓库根 `tests/`(旧版 `src/` 后端)用例未运行——与本后端无关;前端页面级回归未做(仅 API 层验证) |

## 6. 运行方式

```bash
# 后端
cd expohub-backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 8002

# 前端
cd expo-hub-frontend && npm run dev   # http://localhost:5173

# 验证
cd expohub-backend && python -m pytest tests/ -v
cd .. && python scripts/security_verify.py
python scripts/permissions_verify.py
```
