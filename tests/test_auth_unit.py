"""
ExpoHub 认证模块单元测试

覆盖：
1. 密码哈希与验证
2. JWT 令牌编解码
3. 令牌类型验证
4. RBAC 权限检查
5. 角色依赖注入函数
"""

import pytest
from datetime import datetime, timezone, timedelta

from src.auth import (
    hash_password, verify_password,
    create_access_token, create_refresh_token, decode_token, refresh_access_token,
    check_permission, Permission, ROLE_PERMISSIONS,
    CurrentUser,
)
from src.models import UserRole, UserStatus


class TestPasswordHashing:
    """密码哈希与验证测试"""

    def test_hash_password_returns_string(self):
        """测试：密码哈希返回字符串"""
        hashed = hash_password("SecurePass123!")
        assert isinstance(hashed, str)
        assert len(hashed) > 0

    def test_hash_password_differs_from_plaintext(self):
        """测试：哈希值不同于明文"""
        password = "SecurePass123!"
        hashed = hash_password(password)
        assert hashed != password

    def test_verify_password_correct(self):
        """测试：正确密码验证通过"""
        password = "SecurePass123!"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        """测试：错误密码验证失败"""
        hashed = hash_password("SecurePass123!")
        assert verify_password("WrongPassword!", hashed) is False

    def test_verify_password_empty(self):
        """测试：空密码验证失败"""
        hashed = hash_password("SecurePass123!")
        assert verify_password("", hashed) is False

    def test_hash_is_deterministic(self):
        """测试：相同密码每次哈希值不同（bcrypt 加盐）"""
        password = "SecurePass123!"
        hash1 = hash_password(password)
        hash2 = hash_password(password)
        assert hash1 != hash2  # bcrypt 加盐，每次不同
        assert verify_password(password, hash1) is True
        assert verify_password(password, hash2) is True

    @pytest.mark.parametrize("password", [
        "a",
        "12345678",
        "abcdefgh",
        "Test@123!@#$%^&*()",
        "你好世界123",
        "a" * 128,
    ])
    def test_hash_various_passwords(self, password):
        """测试：各种密码都能正确哈希和验证"""
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True


class TestJWTTokens:
    """JWT 令牌编解码测试"""

    def test_create_access_token_success(self):
        """测试：成功创建访问令牌"""
        token = create_access_token(user_id=1, role="visitor")
        assert isinstance(token, str)
        assert len(token.split(".")) == 3  # JWT 有三段

    def test_create_access_token_payload(self):
        """测试：访问令牌包含正确声明"""
        token = create_access_token(user_id=42, role="organizer")
        payload = decode_token(token)
        assert payload["sub"] == "42"
        assert payload["role"] == "organizer"
        assert payload["type"] == "access"
        assert "iat" in payload
        assert "exp" in payload

    def test_create_access_token_with_extra_claims(self):
        """测试：访问令牌包含额外声明"""
        token = create_access_token(
            user_id=1, role="visitor",
            extra_claims={"company": "TestCorp", "is_premium": True}
        )
        payload = decode_token(token)
        assert payload["company"] == "TestCorp"
        assert payload["is_premium"] is True

    def test_create_refresh_token_success(self):
        """测试：成功创建刷新令牌"""
        token = create_refresh_token(user_id=1, role="visitor")
        assert isinstance(token, str)
        assert len(token.split(".")) == 3

    def test_create_refresh_token_payload(self):
        """测试：刷新令牌包含正确声明"""
        token = create_refresh_token(user_id=99, role="boss")
        payload = decode_token(token)
        assert payload["sub"] == "99"
        assert payload["role"] == "boss"
        assert payload["type"] == "refresh"

    def test_access_token_expiry(self):
        """测试：访问令牌过期时间约为15分钟"""
        token = create_access_token(user_id=1, role="visitor")
        payload = decode_token(token)
        exp = payload["exp"]
        iat = payload["iat"]
        # 过期时间应该在 14-16 分钟之间
        diff_minutes = (exp - iat) / 60
        assert 14 <= diff_minutes <= 16

    def test_refresh_token_expiry(self):
        """测试：刷新令牌过期时间约为7天"""
        token = create_refresh_token(user_id=1, role="visitor")
        payload = decode_token(token)
        exp = payload["exp"]
        iat = payload["iat"]
        # 过期时间应该在 6.9-7.1 天之间
        diff_days = (exp - iat) / (24 * 3600)
        assert 6.9 <= diff_days <= 7.1

    def test_decode_invalid_token(self):
        """测试：无效令牌解码抛出 401"""
        with pytest.raises(Exception) as excinfo:
            decode_token("invalid.token.string")
        assert "无效的认证令牌" in str(excinfo.value)

    def test_decode_expired_token(self):
        """测试：过期令牌解码抛出异常"""
        from src.config import settings
        # 创建一个立即过期的令牌
        now = datetime.now(timezone.utc)
        from jose import jwt
        expired_payload = {
            "sub": "1",
            "role": "visitor",
            "type": "access",
            "iat": now - timedelta(hours=1),
            "exp": now - timedelta(minutes=1),  # 已过期
        }
        expired_token = jwt.encode(
            expired_payload, settings.secret_key, algorithm=settings.algorithm
        )
        with pytest.raises(Exception) as excinfo:
            decode_token(expired_token)
        assert "无效的认证令牌" in str(excinfo.value)

    def test_token_tampered(self):
        """测试：篡改后的令牌解码失败"""
        token = create_access_token(user_id=1, role="visitor")
        # 篡改令牌
        parts = token.split(".")
        tampered_token = f"{parts[0]}.{parts[1]}modified.{parts[2]}"
        with pytest.raises(Exception):
            decode_token(tampered_token)


class TestRefreshToken:
    """刷新令牌功能测试"""

    def test_refresh_access_token_success(self):
        """测试：使用刷新令牌成功获取新访问令牌"""
        refresh_token = create_refresh_token(user_id=1, role="visitor")
        result = refresh_access_token(refresh_token)
        assert "access_token" in result
        assert result["token_type"] == "bearer"
        assert "expires_in" in result
        assert result["expires_in"] > 0

    def test_refresh_token_new_token_valid(self):
        """测试：新访问令牌可以解码"""
        refresh_token = create_refresh_token(user_id=1, role="visitor")
        result = refresh_access_token(refresh_token)
        new_token = result["access_token"]
        payload = decode_token(new_token)
        assert payload["type"] == "access"
        assert payload["sub"] == "1"
        assert payload["role"] == "visitor"

    def test_refresh_with_access_token_fails(self):
        """测试：使用访问令牌刷新应失败"""
        access_token = create_access_token(user_id=1, role="visitor")
        with pytest.raises(Exception) as excinfo:
            refresh_access_token(access_token)
        assert "令牌类型错误" in str(excinfo.value)

    def test_refresh_with_invalid_token_fails(self):
        """测试：使用无效令牌刷新应失败"""
        with pytest.raises(Exception):
            refresh_access_token("invalid.token.here")


class TestRBACPermissions:
    """RBAC 权限检查测试"""

    def test_visitor_permissions(self):
        """测试：游客拥有正确的权限集"""
        visitor_perms = ROLE_PERMISSIONS[UserRole.VISITOR]
        assert Permission.USER_READ in visitor_perms
        assert Permission.USER_UPDATE in visitor_perms
        assert Permission.EXHIBITION_READ in visitor_perms
        assert Permission.BOOTH_READ in visitor_perms
        assert Permission.REGISTRATION_CREATE in visitor_perms
        assert Permission.REGISTRATION_READ in visitor_perms
        assert Permission.REGISTRATION_CANCEL in visitor_perms

    def test_visitor_no_admin_permissions(self):
        """测试：游客没有管理权限"""
        visitor_perms = ROLE_PERMISSIONS[UserRole.VISITOR]
        assert Permission.EXHIBITION_CREATE not in visitor_perms
        assert Permission.EXHIBITION_APPROVE not in visitor_perms
        assert Permission.BOOTH_BOOK not in visitor_perms
        assert Permission.STATS_VIEW not in visitor_perms
        assert Permission.USER_MANAGE not in visitor_perms

    def test_exhibitor_permissions(self):
        """测试：展商拥有正确的权限集"""
        exhibitor_perms = ROLE_PERMISSIONS[UserRole.EXHIBITOR]
        assert Permission.BOOTH_BOOK in exhibitor_perms
        assert Permission.BOOTH_UPDATE in exhibitor_perms
        assert Permission.BOOTH_READ in exhibitor_perms
        assert Permission.EXHIBITION_READ in exhibitor_perms
        assert Permission.STATS_VIEW in exhibitor_perms

    def test_exhibitor_no_organizer_permissions(self):
        """测试：展商没有主办方权限"""
        exhibitor_perms = ROLE_PERMISSIONS[UserRole.EXHIBITOR]
        assert Permission.EXHIBITION_CREATE not in exhibitor_perms
        assert Permission.EXHIBITION_PUBLISH not in exhibitor_perms
        assert Permission.BOOTH_CREATE not in exhibitor_perms
        assert Permission.BOOTH_ASSIGN not in exhibitor_perms
        assert Permission.REGISTRATION_CHECKIN not in exhibitor_perms

    def test_organizer_permissions(self):
        """测试：主办方拥有正确的权限集"""
        organizer_perms = ROLE_PERMISSIONS[UserRole.ORGANIZER]
        assert Permission.EXHIBITION_CREATE in organizer_perms
        assert Permission.EXHIBITION_UPDATE in organizer_perms
        assert Permission.EXHIBITION_PUBLISH in organizer_perms
        assert Permission.BOOTH_CREATE in organizer_perms
        assert Permission.BOOTH_ASSIGN in organizer_perms
        assert Permission.REGISTRATION_CHECKIN in organizer_perms
        assert Permission.STATS_VIEW in organizer_perms
        assert Permission.STATS_EXPORT in organizer_perms
        assert Permission.AUDIT_LOG_VIEW in organizer_perms

    def test_organizer_no_boss_permissions(self):
        """测试：主办方没有老板专属权限"""
        organizer_perms = ROLE_PERMISSIONS[UserRole.ORGANIZER]
        assert Permission.EXHIBITION_APPROVE not in organizer_perms
        assert Permission.SYSTEM_CONFIG not in organizer_perms
        assert Permission.USER_MANAGE not in organizer_perms

    def test_boss_permissions(self):
        """测试：老板拥有正确的权限集"""
        boss_perms = ROLE_PERMISSIONS[UserRole.BOSS]
        assert Permission.EXHIBITION_APPROVE in boss_perms
        assert Permission.STATS_VIEW in boss_perms
        assert Permission.STATS_EXPORT in boss_perms
        assert Permission.AUDIT_LOG_VIEW in boss_perms
        assert Permission.SYSTEM_CONFIG in boss_perms
        assert Permission.USER_MANAGE in boss_perms

    def test_boss_no_operational_permissions(self):
        """测试：老板没有日常运营权限"""
        boss_perms = ROLE_PERMISSIONS[UserRole.BOSS]
        assert Permission.EXHIBITION_CREATE not in boss_perms
        assert Permission.EXHIBITION_UPDATE not in boss_perms
        assert Permission.EXHIBITION_PUBLISH not in boss_perms
        assert Permission.BOOTH_CREATE not in boss_perms
        assert Permission.BOOTH_BOOK not in boss_perms
        assert Permission.REGISTRATION_CHECKIN not in boss_perms

    def test_check_permission_visitor_read_exhibition(self):
        """测试：游客可以浏览展会"""
        assert check_permission(UserRole.VISITOR, Permission.EXHIBITION_READ) is True

    def test_check_permission_visitor_create_exhibition(self):
        """测试：游客不能创建展会"""
        assert check_permission(UserRole.VISITOR, Permission.EXHIBITION_CREATE) is False

    def test_check_permission_exhibitor_book_booth(self):
        """测试：展商可以预订展位"""
        assert check_permission(UserRole.EXHIBITOR, Permission.BOOTH_BOOK) is True

    def test_check_permission_organizer_publish(self):
        """测试：主办方可以发布展会"""
        assert check_permission(UserRole.ORGANIZER, Permission.EXHIBITION_PUBLISH) is True

    def test_check_permission_boss_approve(self):
        """测试：老板可以审批展会"""
        assert check_permission(UserRole.BOSS, Permission.EXHIBITION_APPROVE) is True

    def test_check_permission_unknown_role(self):
        """测试：未知角色没有权限"""
        assert check_permission(None, Permission.EXHIBITION_READ) is False

    @pytest.mark.parametrize("role,perm,expected", [
        (UserRole.VISITOR, Permission.REGISTRATION_CREATE, True),
        (UserRole.VISITOR, Permission.BOOTH_BOOK, False),
        (UserRole.EXHIBITOR, Permission.BOOTH_BOOK, True),
        (UserRole.EXHIBITOR, Permission.EXHIBITION_CREATE, False),
        (UserRole.ORGANIZER, Permission.EXHIBITION_CREATE, True),
        (UserRole.ORGANIZER, Permission.EXHIBITION_APPROVE, False),
        (UserRole.BOSS, Permission.EXHIBITION_APPROVE, True),
        (UserRole.BOSS, Permission.BOOTH_CREATE, False),
    ])
    def test_permission_matrix(self, role, perm, expected):
        """测试：完整的权限矩阵验证"""
        assert check_permission(role, perm) is expected


class TestCurrentUser:
    """CurrentUser 模型测试"""

    def test_current_user_creation(self):
        """测试：创建 CurrentUser 实例"""
        user = CurrentUser(
            user_id=1,
            username="testuser",
            role=UserRole.VISITOR,
            status=UserStatus.ACTIVE,
            token_payload={"sub": "1", "role": "visitor"},
        )
        assert user.user_id == 1
        assert user.username == "testuser"
        assert user.role == UserRole.VISITOR
        assert user.status == UserStatus.ACTIVE

    def test_is_active_true(self):
        """测试：ACTIVE 状态返回 True"""
        user = CurrentUser(1, "test", UserRole.VISITOR, UserStatus.ACTIVE, {})
        assert user.is_active is True

    def test_is_active_false_for_disabled(self):
        """测试：DISABLED 状态返回 False"""
        user = CurrentUser(1, "test", UserRole.VISITOR, UserStatus.DISABLED, {})
        assert user.is_active is False

    def test_is_active_false_for_banned(self):
        """测试：BANNED 状态返回 False"""
        user = CurrentUser(1, "test", UserRole.VISITOR, UserStatus.BANNED, {})
        assert user.is_active is False

    def test_role_properties(self):
        """测试：角色属性快捷方法"""
        visitor = CurrentUser(1, "a", UserRole.VISITOR, UserStatus.ACTIVE, {})
        assert visitor.is_visitor is True
        assert visitor.is_exhibitor is False
        assert visitor.is_organizer is False
        assert visitor.is_boss is False

        exhibitor = CurrentUser(2, "b", UserRole.EXHIBITOR, UserStatus.ACTIVE, {})
        assert exhibitor.is_visitor is False
        assert exhibitor.is_exhibitor is True

        organizer = CurrentUser(3, "c", UserRole.ORGANIZER, UserStatus.ACTIVE, {})
        assert organizer.is_organizer is True

        boss = CurrentUser(4, "d", UserRole.BOSS, UserStatus.ACTIVE, {})
        assert boss.is_boss is True

    def test_repr(self):
        """测试：__repr__ 输出格式"""
        user = CurrentUser(1, "testuser", UserRole.VISITOR, UserStatus.ACTIVE, {})
        repr_str = repr(user)
        assert "CurrentUser" in repr_str
        assert "testuser" in repr_str
        assert "visitor" in repr_str
