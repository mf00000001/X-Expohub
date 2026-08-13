"""角色设置(权限映射表)验证脚本

运行: python scripts/permissions_verify.py
前置: 无(纯单元级断言,不依赖服务)

验证 ROLE_PERMISSIONS 声明表与安全修复后的路由语义一致:
- admin 拥有全部权限(补全后)
- organizer 拥有展会管理权限,但无 product:edit/delete 等业务资源写权限
- exhibitor 拥有产品管理权限,无采购发布权限
- visitor/buyer 无管理权限
- has_permission 函数行为正确
"""
import sys

sys.path.insert(0, "expohub-backend")

from app.core.constants import RoleEnum
from app.core.permissions import Permission, ROLE_PERMISSIONS, has_permission

fails = []


def check(name, cond, detail=""):
    print(f"  [{'PASS' if cond else 'FAIL'}] {name} ({detail})")
    if not cond:
        fails.append(name)


# 1. admin 拥有全部权限(补全后)
all_perms = set(Permission)
admin_perms = ROLE_PERMISSIONS[RoleEnum.ADMIN]
missing = all_perms - admin_perms
check("admin:has-all-permissions", not missing, f"missing={sorted(p.value for p in missing)}")

# 2. organizer: 有展会管理权限,无业务资源写权限
org_perms = ROLE_PERMISSIONS[RoleEnum.ORGANIZER]
check("organizer:exhibition-edit", Permission.EXHIBITION_EDIT in org_perms)
check("organizer:exhibition-delete", Permission.EXHIBITION_DELETE in org_perms)
check("organizer:exhibition-publish", Permission.EXHIBITION_PUBLISH in org_perms)
check("organizer:no-product-edit", Permission.PRODUCT_EDIT not in org_perms)
check("organizer:no-product-delete", Permission.PRODUCT_DELETE not in org_perms)
check("organizer:no-procurement-edit", Permission.PROCUREMENT_EDIT not in org_perms)
check("organizer:no-procurement-delete", Permission.PROCUREMENT_DELETE not in org_perms)
check("organizer:no-user-manage", Permission.USER_MANAGE not in org_perms)

# 3. exhibitor: 产品管理权限,无采购发布
exh_perms = ROLE_PERMISSIONS[RoleEnum.EXHIBITOR]
check("exhibitor:product-create", Permission.PRODUCT_CREATE in exh_perms)
check("exhibitor:product-edit", Permission.PRODUCT_EDIT in exh_perms)
check("exhibitor:product-delete", Permission.PRODUCT_DELETE in exh_perms)
check("exhibitor:no-procurement-create", Permission.PROCUREMENT_CREATE not in exh_perms)
check("exhibitor:no-exhibition-create", Permission.EXHIBITION_CREATE not in exh_perms)

# 4. visitor/buyer 无管理权限
vis_perms = ROLE_PERMISSIONS[RoleEnum.VISITOR]
buy_perms = ROLE_PERMISSIONS[RoleEnum.BUYER]
check("visitor:no-stats-global", Permission.STATS_VIEW_GLOBAL not in vis_perms)
check("visitor:no-exhibition-create", Permission.EXHIBITION_CREATE not in vis_perms)
check("buyer:no-exhibition-create", Permission.EXHIBITION_CREATE not in buy_perms)
check("buyer:no-stats-global", Permission.STATS_VIEW_GLOBAL not in buy_perms)

# 5. has_permission 函数
check("has_permission:admin-product-edit", has_permission(RoleEnum.ADMIN, Permission.PRODUCT_EDIT))
check("has_permission:visitor-product-edit-rejected", not has_permission(RoleEnum.VISITOR, Permission.PRODUCT_EDIT))
check("has_permission:organizer-exhibition-edit", has_permission(RoleEnum.ORGANIZER, Permission.EXHIBITION_EDIT))
check("has_permission:unknown-role-empty", has_permission("hacker", Permission.USER_VIEW) is False)

print("RESULT:", "ALL PASS" if not fails else f"FAILED: {fails}")
sys.exit(0 if not fails else 1)
