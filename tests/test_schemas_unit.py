"""
ExpoHub 数据模型 Schema 单元测试

覆盖：
1. RegisterRequest 验证（用户名、邮箱、密码、公司）
2. LoginRequest 验证
3. ExhibitionCreateRequest 验证（日期、字段）
4. BoothCreateRequest 验证
5. UserUpdateRequest 验证
"""

import pytest
from datetime import datetime, timezone, timedelta
from pydantic import ValidationError

from src.schemas import (
    RegisterRequest, LoginRequest, TokenResponse,
    ExhibitionCreateRequest, ExhibitionResponse,
    BoothCreateRequest, BoothBookRequest,
    RegistrationCreateRequest, UserUpdateRequest,
    RefreshTokenRequest,
)
from src.models import UserRole, UserStatus, Gender


class TestRegisterRequest:
    """注册请求验证测试"""

    def test_valid_visitor_registration(self):
        """测试：有效的游客注册"""
        data = RegisterRequest(
            username="testuser",
            email="test@example.com",
            password="SecurePass123",
            role=UserRole.VISITOR,
        )
        assert data.username == "testuser"
        assert data.email == "test@example.com"
        assert data.role == UserRole.VISITOR

    def test_valid_exhibitor_with_company(self):
        """测试：展商注册必须提供公司名称"""
        data = RegisterRequest(
            username="exhibitor1",
            email="exhibitor@test.com",
            password="Pass1234",
            role=UserRole.EXHIBITOR,
            company="Test Corp",
        )
        assert data.company == "Test Corp"

    def test_exhibitor_without_company_fails(self):
        """测试：展商注册不提供公司名称应失败"""
        with pytest.raises(ValidationError, match="必须提供公司名称"):
            RegisterRequest(
                username="exhibitor1",
                email="exhibitor@test.com",
                password="Pass1234",
                role=UserRole.EXHIBITOR,
            )

    def test_organizer_without_company_fails(self):
        """测试：主办方注册不提供公司名称应失败"""
        with pytest.raises(ValidationError, match="必须提供公司名称"):
            RegisterRequest(
                username="organizer1",
                email="organizer@test.com",
                password="Pass1234",
                role=UserRole.ORGANIZER,
            )

    def test_boss_without_company_ok(self):
        """测试：老板注册可以不提供公司名称"""
        data = RegisterRequest(
            username="boss1",
            email="boss@test.com",
            password="Pass1234",
            role=UserRole.BOSS,
        )
        assert data.company is None

    @pytest.mark.parametrize("username", [
        "ab",                    # 太短
        "a" * 51,               # 太长
        "user name",            # 包含空格
        "user@name",            # 包含特殊字符
        "user.name",            # 包含点
        "",                     # 空
    ])
    def test_invalid_username(self, username):
        """测试：无效的用户名"""
        with pytest.raises(ValidationError):
            RegisterRequest(
                username=username,
                email="test@example.com",
                password="SecurePass123",
            )

    @pytest.mark.parametrize("username", [
        "test_user",
        "test-user",
        "user123",
        "TestUser",
        "a_b-c",
    ])
    def test_valid_username_formats(self, username):
        """测试：有效的用户名格式"""
        data = RegisterRequest(
            username=username,
            email="test@example.com",
            password="SecurePass123",
        )
        assert data.username == username

    @pytest.mark.parametrize("email", [
        "",                      # 空
        "notanemail",           # 无@
        "@missinguser.com",     # 无用户名
        "user@",                # 无域名
        "user@.com",            # 无效域名
        "user@domain",          # 无顶级域
        "user@domain.",         # 末尾点
        "a" * 300 + "@test.com",  # 超长
    ])
    def test_invalid_email(self, email):
        """测试：无效的邮箱格式"""
        with pytest.raises(ValidationError):
            RegisterRequest(
                username="testuser",
                email=email,
                password="SecurePass123",
            )

    def test_email_lowercased(self):
        """测试：邮箱自动转为小写"""
        data = RegisterRequest(
            username="testuser",
            email="Test@Example.COM",
            password="SecurePass123",
        )
        assert data.email == "test@example.com"

    @pytest.mark.parametrize("password", [
        "short12",              # 太短（7位）
        "nonumberpass",         # 无数字
        "12345678",             # 无字母
        "",                     # 空
    ])
    def test_invalid_password(self, password):
        """测试：无效的密码"""
        with pytest.raises(ValidationError):
            RegisterRequest(
                username="testuser",
                email="test@example.com",
                password=password,
            )

    @pytest.mark.parametrize("password", [
        "SecurePass123",
        "Pass1234",
        "abcdef12345",
        "12345abcde",
        "A1b2C3d4E5",
        "a" * 7 + "1",          # 8位边界
    ])
    def test_valid_passwords(self, password):
        """测试：有效的密码"""
        data = RegisterRequest(
            username="testuser",
            email="test@example.com",
            password=password,
        )
        assert data.password == password

    @pytest.mark.parametrize("phone", [
        "12345678901",          # 不以1开头
        "10012345678",          # 第二位不是3-9
        "1380013800",           # 10位
        "138001380001",         # 12位
        "abcdefghijk",          # 非数字
    ])
    def test_invalid_phone(self, phone):
        """测试：无效的手机号"""
        with pytest.raises(ValidationError):
            RegisterRequest(
                username="testuser",
                email="test@example.com",
                password="SecurePass123",
                phone=phone,
            )

    def test_valid_phone(self):
        """测试：有效的手机号"""
        data = RegisterRequest(
            username="testuser",
            email="test@example.com",
            password="SecurePass123",
            phone="13800138000",
        )
        assert data.phone == "13800138000"


class TestLoginRequest:
    """登录请求验证测试"""

    def test_valid_login(self):
        """测试：有效的登录请求"""
        data = LoginRequest(username="testuser", password="Test1234")
        assert data.username == "testuser"
        assert data.password == "Test1234"

    def test_username_too_short(self):
        """测试：用户名太短"""
        with pytest.raises(ValidationError):
            LoginRequest(username="ab", password="Test1234")

    def test_username_too_long(self):
        """测试：用户名太长"""
        with pytest.raises(ValidationError):
            LoginRequest(username="a" * 51, password="Test1234")

    def test_empty_password(self):
        """测试：空密码"""
        with pytest.raises(ValidationError):
            LoginRequest(username="testuser", password="")


class TestExhibitionCreateRequest:
    """创建展会请求验证测试"""

    def test_valid_exhibition(self):
        """测试：有效的展会创建请求"""
        now = datetime.now(timezone.utc)
        data = ExhibitionCreateRequest(
            name="2025 国际消费电子展",
            start_date=now + timedelta(days=30),
            end_date=now + timedelta(days=33),
            venue="上海国家会展中心",
            address="上海市青浦区崧泽大道333号",
            city="上海",
            total_booths=100,
        )
        assert data.name == "2025 国际消费电子展"
        assert data.total_booths == 100

    def test_end_date_before_start_date_fails(self):
        """测试：结束时间在开始时间之前应失败"""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValidationError, match="结束时间必须在开始时间之后"):
            ExhibitionCreateRequest(
                name="Test Exhibition",
                start_date=now + timedelta(days=30),
                end_date=now + timedelta(days=29),  # 早于开始时间
                venue="Venue",
                address="Address",
                city="City",
            )

    def test_end_date_equal_start_date_fails(self):
        """测试：结束时间等于开始时间应失败"""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValidationError):
            ExhibitionCreateRequest(
                name="Test Exhibition",
                start_date=now,
                end_date=now,  # 等于开始时间
                venue="Venue",
                address="Address",
                city="City",
            )

    @pytest.mark.parametrize("name", [
        "a",                     # 太短
        "",                      # 空
    ])
    def test_invalid_name(self, name):
        """测试：无效的展会名称"""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValidationError):
            ExhibitionCreateRequest(
                name=name,
                start_date=now + timedelta(days=1),
                end_date=now + timedelta(days=3),
                venue="Venue",
                address="Address",
                city="City",
            )

    def test_negative_total_booths_fails(self):
        """测试：负的展位数应失败"""
        now = datetime.now(timezone.utc)
        with pytest.raises(ValidationError):
            ExhibitionCreateRequest(
                name="Test Exhibition",
                start_date=now + timedelta(days=1),
                end_date=now + timedelta(days=3),
                venue="Venue",
                address="Address",
                city="City",
                total_booths=-1,
            )

    def test_zero_total_booths_ok(self):
        """测试：展位数为0是允许的"""
        now = datetime.now(timezone.utc)
        data = ExhibitionCreateRequest(
            name="Test Exhibition",
            start_date=now + timedelta(days=1),
            end_date=now + timedelta(days=3),
            venue="Venue",
            address="Address",
            city="City",
            total_booths=0,
        )
        assert data.total_booths == 0


class TestBoothCreateRequest:
    """创建展位请求验证测试"""

    def test_valid_booth(self):
        """测试：有效的展位创建请求"""
        data = BoothCreateRequest(
            exhibition_id=1,
            booth_number="A-001",
            name="黄金展位",
            area=50.0,
            price=10000.0,
            zone="A区",
        )
        assert data.booth_number == "A-001"
        assert data.area == 50.0

    def test_negative_area_fails(self):
        """测试：负的面积应失败"""
        with pytest.raises(ValidationError):
            BoothCreateRequest(
                exhibition_id=1,
                booth_number="A-001",
                area=-1.0,
            )

    def test_zero_area_fails(self):
        """测试：面积为0应失败（gt=0）"""
        with pytest.raises(ValidationError):
            BoothCreateRequest(
                exhibition_id=1,
                booth_number="A-001",
                area=0,
            )

    def test_negative_price_fails(self):
        """测试：负的价格应失败"""
        with pytest.raises(ValidationError):
            BoothCreateRequest(
                exhibition_id=1,
                booth_number="A-001",
                price=-100,
            )

    def test_zero_price_ok(self):
        """测试：价格为0是允许的（免费展位）"""
        data = BoothCreateRequest(
            exhibition_id=1,
            booth_number="A-001",
            price=0,
        )
        assert data.price == 0


class TestUserUpdateRequest:
    """用户信息更新验证测试"""

    def test_valid_update(self):
        """测试：有效的更新请求"""
        data = UserUpdateRequest(
            nickname="新昵称",
            gender=Gender.MALE,
            company="New Corp",
            bio="Hello World",
        )
        assert data.nickname == "新昵称"
        assert data.gender == Gender.MALE

    def test_partial_update(self):
        """测试：部分字段更新"""
        data = UserUpdateRequest(nickname="新昵称")
        assert data.nickname == "新昵称"
        assert data.gender is None
        assert data.company is None

    def test_empty_update(self):
        """测试：空更新请求"""
        data = UserUpdateRequest()
        assert data.model_dump(exclude_unset=True) == {}

    def test_invalid_phone(self):
        """测试：无效的手机号"""
        with pytest.raises(ValidationError):
            UserUpdateRequest(phone="12345")


class TestRegistrationCreateRequest:
    """报名请求验证测试"""

    def test_valid_registration(self):
        """测试：有效的报名请求"""
        data = RegistrationCreateRequest(
            exhibition_id=1,
            is_favorite=False,
            is_registered=True,
        )
        assert data.exhibition_id == 1
        assert data.is_registered is True
        assert data.is_favorite is False

    def test_favorite_only(self):
        """测试：仅收藏"""
        data = RegistrationCreateRequest(
            exhibition_id=1,
            is_favorite=True,
            is_registered=False,
        )
        assert data.is_favorite is True
        assert data.is_registered is False
