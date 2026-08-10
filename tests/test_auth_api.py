"""
ExpoHub 认证接口测试（P0 优先级）

覆盖认证全流程：
1. 注册 → 登录 → 获取令牌 → 刷新令牌 → 获取用户信息
2. 异常路径：重复注册、错误密码、无效令牌
"""

import pytest
from fastapi import status

from src.models import UserRole


class TestRegisterAPI:
    """注册接口测试"""

    REGISTER_URL = "/api/auth/register"

    def test_register_visitor_success(self, client):
        """P0 测试：游客注册成功"""
        response = client.post(self.REGISTER_URL, json={
            "username": "new_visitor",
            "email": "new_visitor@example.com",
            "password": "SecurePass123",
            "role": "visitor",
        })
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["username"] == "new_visitor"
        assert data["user"]["role"] == "visitor"

    def test_register_exhibitor_with_company_success(self, client):
        """P0 测试：展商注册成功（需提供公司名称）"""
        response = client.post(self.REGISTER_URL, json={
            "username": "new_exhibitor",
            "email": "new_exhibitor@example.com",
            "password": "SecurePass123",
            "role": "exhibitor",
            "company": "New Exhibitor Corp",
        })
        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["user"]["company"] == "New Exhibitor Corp"

    def test_register_exhibitor_without_company_fails(self, client):
        """P1 测试：展商注册不提供公司名称应失败"""
        response = client.post(self.REGISTER_URL, json={
            "username": "new_exhibitor2",
            "email": "new_exhibitor2@example.com",
            "password": "SecurePass123",
            "role": "exhibitor",
        })
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_register_duplicate_username_fails(self, client, visitor_user):
        """P0 测试：重复用户名注册应返回 409"""
        response = client.post(self.REGISTER_URL, json={
            "username": "visitor_alice",  # 已存在的用户名
            "email": "another@example.com",
            "password": "SecurePass123",
            "role": "visitor",
        })
        assert response.status_code == status.HTTP_409_CONFLICT
        assert "用户名已存在" in response.text

    def test_register_duplicate_email_fails(self, client, visitor_user):
        """P0 测试：重复邮箱注册应返回 409"""
        response = client.post(self.REGISTER_URL, json={
            "username": "another_user",
            "email": "alice@example.com",  # 已存在的邮箱
            "password": "SecurePass123",
            "role": "visitor",
        })
        assert response.status_code == status.HTTP_409_CONFLICT
        assert "邮箱已被注册" in response.text

    def test_register_invalid_data_fails(self, client):
        """P1 测试：无效数据注册应返回 422"""
        test_cases = [
            {"username": "ab", "email": "a@b.com", "password": "Pass1234"},  # 用户名太短
            {"username": "testuser", "email": "invalid", "password": "Pass1234"},  # 无效邮箱
            {"username": "testuser", "email": "a@b.com", "password": "short"},  # 密码太短
            {"username": "testuser", "email": "a@b.com", "password": "12345678"},  # 密码无字母
            {"username": "testuser", "email": "a@b.com", "password": "abcdefgh"},  # 密码无数字
        ]
        for case in test_cases:
            response = client.post(self.REGISTER_URL, json=case)
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY, f"Failed for: {case}"


class TestLoginAPI:
    """登录接口测试"""

    LOGIN_URL = "/api/auth/login"

    def test_login_with_username_success(self, client, visitor_user):
        """P0 测试：使用用户名登录成功"""
        response = client.post(self.LOGIN_URL, json={
            "username": "visitor_alice",
            "password": "Test1234",
        })
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["user"]["username"] == "visitor_alice"
        assert data["user"]["role"] == "visitor"

    def test_login_with_email_success(self, client, visitor_user):
        """P0 测试：使用邮箱登录成功"""
        response = client.post(self.LOGIN_URL, json={
            "username": "alice@example.com",
            "password": "Test1234",
        })
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data

    def test_login_wrong_password_fails(self, client, visitor_user):
        """P0 测试：错误密码登录应返回 401"""
        response = client.post(self.LOGIN_URL, json={
            "username": "visitor_alice",
            "password": "WrongPassword!",
        })
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_login_nonexistent_user_fails(self, client):
        """P0 测试：不存在的用户登录应返回 401"""
        response = client.post(self.LOGIN_URL, json={
            "username": "nonexistent_user",
            "password": "Test1234",
        })
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_login_disabled_user_fails(self, client, db_session, visitor_user):
        """P1 测试：已禁用用户登录应返回 403"""
        from src.models import UserStatus
        visitor_user.status = UserStatus.DISABLED
        db_session.commit()

        response = client.post(self.LOGIN_URL, json={
            "username": "visitor_alice",
            "password": "Test1234",
        })
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "禁用" in response.text

    def test_login_banned_user_fails(self, client, db_session, visitor_user):
        """P1 测试：已封禁用户登录应返回 403"""
        from src.models import UserStatus
        visitor_user.status = UserStatus.BANNED
        db_session.commit()

        response = client.post(self.LOGIN_URL, json={
            "username": "visitor_alice",
            "password": "Test1234",
        })
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "封禁" in response.text

    def test_login_updates_last_login(self, client, db_session, visitor_user):
        """P2 测试：登录后更新最后登录时间"""
        assert visitor_user.last_login_at is None

        client.post(self.LOGIN_URL, json={
            "username": "visitor_alice",
            "password": "Test1234",
        })

        db_session.refresh(visitor_user)
        assert visitor_user.last_login_at is not None


class TestRefreshTokenAPI:
    """刷新令牌接口测试"""

    REFRESH_URL = "/api/auth/refresh"

    def test_refresh_token_success(self, client, visitor_user):
        """P0 测试：使用刷新令牌获取新访问令牌"""
        # 先登录获取令牌
        login_resp = client.post("/api/auth/login", json={
            "username": "visitor_alice",
            "password": "Test1234",
        })
        refresh_token = login_resp.json()["refresh_token"]

        # 刷新令牌
        response = client.post(self.REFRESH_URL, json={
            "refresh_token": refresh_token,
        })
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] > 0

    def test_refresh_with_access_token_fails(self, client, visitor_user):
        """P1 测试：使用访问令牌刷新应失败"""
        login_resp = client.post("/api/auth/login", json={
            "username": "visitor_alice",
            "password": "Test1234",
        })
        access_token = login_resp.json()["access_token"]

        response = client.post(self.REFRESH_URL, json={
            "refresh_token": access_token,
        })
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_refresh_with_invalid_token_fails(self, client):
        """P1 测试：使用无效令牌刷新应失败"""
        response = client.post(self.REFRESH_URL, json={
            "refresh_token": "invalid.token.here",
        })
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestGetCurrentUserAPI:
    """获取当前用户信息接口测试"""

    ME_URL = "/api/auth/me"

    def test_get_me_authenticated(self, client, visitor_headers):
        """P0 测试：已登录用户获取个人信息成功"""
        response = client.get(self.ME_URL, headers=visitor_headers)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["username"] == "visitor_alice"
        assert data["role"] == "visitor"

    def test_get_me_unauthenticated_fails(self, client):
        """P0 测试：未登录用户获取个人信息应返回 401"""
        response = client.get(self.ME_URL)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_get_me_with_invalid_token_fails(self, client):
        """P1 测试：无效令牌获取个人信息应返回 401"""
        response = client.get(self.ME_URL, headers={
            "Authorization": "Bearer invalid_token"
        })
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestAuthFullFlow:
    """认证全流程测试"""

    def test_full_auth_flow(self, client):
        """P0 测试：注册 → 登录 → 获取信息 → 刷新令牌 完整流程"""
        # 1. 注册
        register_resp = client.post("/api/auth/register", json={
            "username": "flow_test_user",
            "email": "flow_test@example.com",
            "password": "FlowTest123",
            "role": "visitor",
        })
        assert register_resp.status_code == status.HTTP_201_CREATED
        register_data = register_resp.json()
        access_token = register_data["access_token"]
        refresh_token = register_data["refresh_token"]

        # 2. 使用注册返回的令牌获取用户信息
        me_resp = client.get("/api/auth/me", headers={
            "Authorization": f"Bearer {access_token}"
        })
        assert me_resp.status_code == status.HTTP_200_OK
        assert me_resp.json()["username"] == "flow_test_user"

        # 3. 刷新令牌
        refresh_resp = client.post("/api/auth/refresh", json={
            "refresh_token": refresh_token,
        })
        assert refresh_resp.status_code == status.HTTP_200_OK
        new_access_token = refresh_resp.json()["access_token"]

        # 4. 使用新令牌获取用户信息
        me_resp2 = client.get("/api/auth/me", headers={
            "Authorization": f"Bearer {new_access_token}"
        })
        assert me_resp2.status_code == status.HTTP_200_OK
        assert me_resp2.json()["username"] == "flow_test_user"

        # 5. 登录
        login_resp = client.post("/api/auth/login", json={
            "username": "flow_test_user",
            "password": "FlowTest123",
        })
        assert login_resp.status_code == status.HTTP_200_OK
