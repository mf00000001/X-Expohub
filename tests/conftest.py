"""
ExpoHub 测试配置与共享 Fixtures

提供：
1. 测试数据库（SQLite 内存模式）
2. 测试客户端（FastAPI TestClient）
3. 四类角色的测试账号 Fixtures
4. 认证令牌 Fixtures
"""

import pytest
from datetime import datetime, timezone
from typing import Generator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.database import Base, get_db
from src.main import create_app
from src.config import settings
from src.models import User, UserRole, UserStatus, Exhibition, ExhibitionStatus, Booth, BoothStatus
from src.auth import hash_password, create_access_token, create_refresh_token

# ============================================================
# 测试数据库配置（SQLite 内存模式）
# ============================================================

TEST_DATABASE_URL = "sqlite:///./test_expo_hub.db"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,
)

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# ============================================================
# 测试账号常量
# ============================================================

TEST_USERS = {
    "visitor": {
        "username": "visitor_alice",
        "email": "alice@example.com",
        "password": "Test1234",
        "role": UserRole.VISITOR,
        "nickname": "Alice",
    },
    "exhibitor": {
        "username": "exhibitor_bob",
        "email": "bob@example.com",
        "password": "Test1234",
        "role": UserRole.EXHIBITOR,
        "nickname": "Bob",
        "company": "Bob Tech Co.",
    },
    "organizer": {
        "username": "organizer_carol",
        "email": "carol@example.com",
        "password": "Test1234",
        "role": UserRole.ORGANIZER,
        "nickname": "Carol",
        "company": "Carol Expo Inc.",
    },
    "boss": {
        "username": "boss_dave",
        "email": "dave@example.com",
        "password": "Test1234",
        "role": UserRole.BOSS,
        "nickname": "Dave",
    },
}


# ============================================================
# 全局 Fixtures
# ============================================================

@pytest.fixture(scope="session")
def test_app():
    """创建测试应用实例"""
    app = create_app()
    return app


@pytest.fixture(scope="function")
def db_session():
    """创建独立的测试数据库会话（每个测试函数独立）"""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        # 清理所有表数据
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(table.delete())
        db.commit()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(test_app, db_session):
    """
    创建测试 HTTP 客户端
    使用 override 替换数据库依赖
    """
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    test_app.dependency_overrides[get_db] = override_get_db
    with TestClient(test_app) as c:
        yield c
    test_app.dependency_overrides.clear()


# ============================================================
# 测试账号 Fixtures
# ============================================================

def _create_test_user(db: Session, user_data: dict) -> User:
    """创建测试用户并返回"""
    user = User(
        username=user_data["username"],
        email=user_data["email"],
        password_hash=hash_password(user_data["password"]),
        role=user_data["role"],
        status=UserStatus.ACTIVE,
        nickname=user_data.get("nickname"),
        company=user_data.get("company"),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture(scope="function")
def visitor_user(db_session) -> User:
    """创建游客测试账号"""
    return _create_test_user(db_session, TEST_USERS["visitor"])


@pytest.fixture(scope="function")
def exhibitor_user(db_session) -> User:
    """创建展商测试账号"""
    return _create_test_user(db_session, TEST_USERS["exhibitor"])


@pytest.fixture(scope="function")
def organizer_user(db_session) -> User:
    """创建主办方测试账号"""
    return _create_test_user(db_session, TEST_USERS["organizer"])


@pytest.fixture(scope="function")
def boss_user(db_session) -> User:
    """创建老板测试账号"""
    return _create_test_user(db_session, TEST_USERS["boss"])


@pytest.fixture(scope="function")
def all_users(db_session) -> dict[str, User]:
    """创建所有四类测试账号"""
    users = {}
    for role_key, user_data in TEST_USERS.items():
        users[role_key] = _create_test_user(db_session, user_data)
    return users


# ============================================================
# 认证令牌 Fixtures
# ============================================================

@pytest.fixture(scope="function")
def visitor_token(visitor_user) -> str:
    """游客的访问令牌"""
    return create_access_token(user_id=visitor_user.id, role=visitor_user.role.value)


@pytest.fixture(scope="function")
def exhibitor_token(exhibitor_user) -> str:
    """展商的访问令牌"""
    return create_access_token(user_id=exhibitor_user.id, role=exhibitor_user.role.value)


@pytest.fixture(scope="function")
def organizer_token(organizer_user) -> str:
    """主办方的访问令牌"""
    return create_access_token(user_id=organizer_user.id, role=organizer_user.role.value)


@pytest.fixture(scope="function")
def boss_token(boss_user) -> str:
    """老板的访问令牌"""
    return create_access_token(user_id=boss_user.id, role=boss_user.role.value)


@pytest.fixture(scope="function")
def visitor_refresh_token(visitor_user) -> str:
    """游客的刷新令牌"""
    return create_refresh_token(user_id=visitor_user.id, role=visitor_user.role.value)


# ============================================================
# 请求头 Fixtures
# ============================================================

@pytest.fixture(scope="function")
def visitor_headers(visitor_token) -> dict:
    """游客认证请求头"""
    return {"Authorization": f"Bearer {visitor_token}"}


@pytest.fixture(scope="function")
def exhibitor_headers(exhibitor_token) -> dict:
    """展商认证请求头"""
    return {"Authorization": f"Bearer {exhibitor_token}"}


@pytest.fixture(scope="function")
def organizer_headers(organizer_token) -> dict:
    """主办方认证请求头"""
    return {"Authorization": f"Bearer {organizer_token}"}


@pytest.fixture(scope="function")
def boss_headers(boss_token) -> dict:
    """老板认证请求头"""
    return {"Authorization": f"Bearer {boss_token}"}


# ============================================================
# 测试数据 Fixtures
# ============================================================

@pytest.fixture(scope="function")
def sample_exhibition(db_session, organizer_user) -> Exhibition:
    """创建一个示例展会（草稿状态）"""
    exhibition = Exhibition(
        name="2025 国际消费电子展",
        short_name="CES 2025",
        description="全球最大的消费电子展会",
        start_date=datetime(2025, 6, 1, tzinfo=timezone.utc),
        end_date=datetime(2025, 6, 5, tzinfo=timezone.utc),
        venue="上海国家会展中心",
        address="上海市青浦区崧泽大道333号",
        city="上海",
        status=ExhibitionStatus.DRAFT,
        organizer_id=organizer_user.id,
        total_booths=100,
        available_booths=100,
    )
    db_session.add(exhibition)
    db_session.commit()
    db_session.refresh(exhibition)
    return exhibition


@pytest.fixture(scope="function")
def sample_exhibition_published(db_session, organizer_user) -> Exhibition:
    """创建一个已发布的展会"""
    exhibition = Exhibition(
        name="2025 国际人工智能大会",
        short_name="AI 2025",
        description="人工智能领域顶级会议",
        start_date=datetime(2025, 7, 1, tzinfo=timezone.utc),
        end_date=datetime(2025, 7, 3, tzinfo=timezone.utc),
        venue="北京国家会议中心",
        address="北京市朝阳区天辰东路7号",
        city="北京",
        status=ExhibitionStatus.PUBLISHED,
        organizer_id=organizer_user.id,
        total_booths=50,
        available_booths=48,
    )
    db_session.add(exhibition)
    db_session.commit()
    db_session.refresh(exhibition)
    return exhibition


@pytest.fixture(scope="function")
def sample_booth(db_session, sample_exhibition) -> Booth:
    """创建一个示例展位"""
    booth = Booth(
        exhibition_id=sample_exhibition.id,
        booth_number="A-001",
        name="主展位",
        area=50.0,
        price=10000.0,
        zone="A区",
        status=BoothStatus.AVAILABLE,
    )
    db_session.add(booth)
    db_session.commit()
    db_session.refresh(booth)
    return booth
