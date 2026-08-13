"""
ExpoHub 数据模型单元测试

覆盖：
1. 模型字段类型和约束
2. 模型关系
3. 枚举值
4. 唯一约束和索引
"""

import pytest
from datetime import datetime, timezone

from sqlalchemy import inspect

from src.models import (
    User, UserRole, UserStatus,
    Exhibition, ExhibitionStatus,
    Booth, BoothStatus,
    VisitorRegistration, AuditLog,
)


class TestUserModel:
    """用户模型测试"""

    def test_user_table_exists(self, db_session):
        """测试：users 表存在"""
        inspector = inspect(db_session.bind)
        tables = inspector.get_table_names()
        assert "users" in tables

    def test_user_columns(self, db_session):
        """测试：用户表包含所有字段"""
        inspector = inspect(db_session.bind)
        columns = {col["name"]: col for col in inspector.get_columns("users")}
        expected_columns = [
            "id", "username", "email", "phone", "password_hash",
            "role", "status",
            "nickname", "avatar_url", "gender", "company", "position", "bio",
            "created_at", "updated_at", "last_login_at", "deleted_at",
        ]
        for col in expected_columns:
            assert col in columns, f"缺少字段: {col}"

    def test_user_username_unique(self, db_session):
        """测试：用户名唯一约束"""
        user1 = User(username="testuser", email="a@b.com", password_hash="hash", role=UserRole.VISITOR)
        db_session.add(user1)
        db_session.commit()

        user2 = User(username="testuser", email="c@d.com", password_hash="hash", role=UserRole.VISITOR)
        db_session.add(user2)
        with pytest.raises(Exception):  # IntegrityError
            db_session.commit()
        db_session.rollback()

    def test_user_email_unique(self, db_session):
        """测试：邮箱唯一约束"""
        user1 = User(username="user1", email="same@test.com", password_hash="hash", role=UserRole.VISITOR)
        db_session.add(user1)
        db_session.commit()

        user2 = User(username="user2", email="same@test.com", password_hash="hash", role=UserRole.VISITOR)
        db_session.add(user2)
        with pytest.raises(Exception):
            db_session.commit()
        db_session.rollback()

    def test_user_phone_unique(self, db_session):
        """测试：手机号唯一约束"""
        user1 = User(username="user1", email="a@b.com", password_hash="hash",
                     role=UserRole.VISITOR, phone="13800138000")
        db_session.add(user1)
        db_session.commit()

        user2 = User(username="user2", email="c@d.com", password_hash="hash",
                     role=UserRole.VISITOR, phone="13800138000")
        db_session.add(user2)
        with pytest.raises(Exception):
            db_session.commit()
        db_session.rollback()

    def test_user_created_at_default(self, db_session):
        """测试：created_at 有默认值"""
        user = User(username="testuser", email="test@test.com",
                    password_hash="hash", role=UserRole.VISITOR)
        db_session.add(user)
        db_session.commit()
        assert user.created_at is not None

    def test_user_role_default_visitor(self, db_session):
        """测试：角色默认值为 VISITOR"""
        user = User(username="testuser", email="test@test.com",
                    password_hash="hash")
        db_session.add(user)
        db_session.commit()
        assert user.role == UserRole.VISITOR

    def test_user_status_default_pending(self, db_session):
        """测试：状态默认值为 PENDING"""
        user = User(username="testuser", email="test@test.com",
                    password_hash="hash", role=UserRole.VISITOR)
        db_session.add(user)
        db_session.commit()
        assert user.status == UserStatus.PENDING

    def test_user_repr(self, db_session):
        """测试：__repr__ 输出"""
        user = User(username="testuser", email="test@test.com",
                    password_hash="hash", role=UserRole.VISITOR)
        db_session.add(user)
        db_session.commit()
        repr_str = repr(user)
        assert "User" in repr_str
        assert "testuser" in repr_str
        assert "visitor" in repr_str


class TestExhibitionModel:
    """展会模型测试"""

    def test_exhibition_table_exists(self, db_session):
        """测试：exhibitions 表存在"""
        inspector = inspect(db_session.bind)
        tables = inspector.get_table_names()
        assert "exhibitions" in tables

    def test_exhibition_columns(self, db_session):
        """测试：展会表包含所有字段"""
        inspector = inspect(db_session.bind)
        columns = {col["name"]: col for col in inspector.get_columns("exhibitions")}
        expected_columns = [
            "id", "name", "short_name", "description", "cover_url",
            "start_date", "end_date", "registration_deadline",
            "venue", "address", "city",
            "status", "organizer_id",
            "total_booths", "available_booths", "visitor_count",
            "created_at", "updated_at",
        ]
        for col in expected_columns:
            assert col in columns, f"缺少字段: {col}"

    def test_exhibition_foreign_key(self, db_session, organizer_user):
        """测试：展会关联主办方"""
        exhibition = Exhibition(
            name="Test Expo",
            start_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2025, 1, 5, tzinfo=timezone.utc),
            venue="Venue",
            address="Address",
            city="City",
            organizer_id=organizer_user.id,
        )
        db_session.add(exhibition)
        db_session.commit()
        assert exhibition.organizer_id == organizer_user.id
        assert exhibition.organizer.username == organizer_user.username

    def test_exhibition_status_default_draft(self, db_session, organizer_user):
        """测试：展会状态默认 DRAFT"""
        exhibition = Exhibition(
            name="Test Expo",
            start_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2025, 1, 5, tzinfo=timezone.utc),
            venue="Venue",
            address="Address",
            city="City",
            organizer_id=organizer_user.id,
        )
        db_session.add(exhibition)
        db_session.commit()
        assert exhibition.status == ExhibitionStatus.DRAFT


class TestBoothModel:
    """展位模型测试"""

    def test_booth_table_exists(self, db_session):
        """测试：booths 表存在"""
        inspector = inspect(db_session.bind)
        tables = inspector.get_table_names()
        assert "booths" in tables

    def test_booth_unique_constraint(self, db_session, sample_exhibition):
        """测试：同一展会内展位编号唯一"""
        booth1 = Booth(
            exhibition_id=sample_exhibition.id,
            booth_number="A-001",
        )
        db_session.add(booth1)
        db_session.commit()

        booth2 = Booth(
            exhibition_id=sample_exhibition.id,
            booth_number="A-001",  # 相同编号
        )
        db_session.add(booth2)
        with pytest.raises(Exception):
            db_session.commit()
        db_session.rollback()

    def test_booth_same_number_different_exhibition_ok(self, db_session, sample_exhibition, organizer_user):
        """测试：不同展会可以使用相同展位编号"""
        # 创建第二个展会
        exhibition2 = Exhibition(
            name="Expo 2",
            start_date=datetime(2025, 6, 1, tzinfo=timezone.utc),
            end_date=datetime(2025, 6, 5, tzinfo=timezone.utc),
            venue="Venue 2",
            address="Address 2",
            city="City 2",
            organizer_id=organizer_user.id,
        )
        db_session.add(exhibition2)
        db_session.commit()

        booth1 = Booth(exhibition_id=sample_exhibition.id, booth_number="A-001")
        booth2 = Booth(exhibition_id=exhibition2.id, booth_number="A-001")
        db_session.add(booth1)
        db_session.add(booth2)
        db_session.commit()  # 应该成功
        assert booth1.id != booth2.id

    def test_booth_status_default_available(self, db_session, sample_exhibition):
        """测试：展位状态默认 AVAILABLE"""
        booth = Booth(exhibition_id=sample_exhibition.id, booth_number="B-001")
        db_session.add(booth)
        db_session.commit()
        assert booth.status == BoothStatus.AVAILABLE


class TestVisitorRegistrationModel:
    """报名记录模型测试"""

    def test_registration_table_exists(self, db_session):
        """测试：visitor_registrations 表存在"""
        inspector = inspect(db_session.bind)
        tables = inspector.get_table_names()
        assert "visitor_registrations" in tables

    def test_registration_unique_constraint(self, db_session, visitor_user, sample_exhibition_published):
        """测试：同一用户对同一展会只能有一条记录"""
        reg1 = VisitorRegistration(
            visitor_id=visitor_user.id,
            exhibition_id=sample_exhibition_published.id,
            is_registered=True,
        )
        db_session.add(reg1)
        db_session.commit()

        reg2 = VisitorRegistration(
            visitor_id=visitor_user.id,
            exhibition_id=sample_exhibition_published.id,
            is_favorite=True,
        )
        db_session.add(reg2)
        with pytest.raises(Exception):
            db_session.commit()
        db_session.rollback()

    def test_registration_relationships(self, db_session, visitor_user, sample_exhibition_published):
        """测试：报名记录关联用户和展会"""
        reg = VisitorRegistration(
            visitor_id=visitor_user.id,
            exhibition_id=sample_exhibition_published.id,
            is_registered=True,
        )
        db_session.add(reg)
        db_session.commit()

        assert reg.visitor.username == visitor_user.username
        assert reg.exhibition.name == sample_exhibition_published.name


class TestAuditLogModel:
    """审计日志模型测试"""

    def test_audit_log_table_exists(self, db_session):
        """测试：audit_logs 表存在"""
        inspector = inspect(db_session.bind)
        tables = inspector.get_table_names()
        assert "audit_logs" in tables

    def test_audit_log_creation(self, db_session, visitor_user):
        """测试：创建审计日志"""
        log = AuditLog(
            user_id=visitor_user.id,
            user_role="visitor",
            action="user:login",
            resource_type="session",
            detail='{"ip": "127.0.0.1"}',
        )
        db_session.add(log)
        db_session.commit()
        assert log.id is not None
        assert log.action == "user:login"
        assert log.created_at is not None


class TestModelRelationships:
    """模型关系测试"""

    def test_user_booths_relationship(self, db_session, exhibitor_user, sample_exhibition):
        """测试：用户-展位关系"""
        booth = Booth(
            exhibition_id=sample_exhibition.id,
            booth_number="C-001",
            exhibitor_id=exhibitor_user.id,
        )
        db_session.add(booth)
        db_session.commit()

        assert len(list(exhibitor_user.booths)) == 1
        assert exhibitor_user.booths[0].booth_number == "C-001"

    def test_user_organized_exhibitions(self, db_session, organizer_user):
        """测试：主办方-展会关系"""
        exhibition = Exhibition(
            name="Organizer's Expo",
            start_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2025, 1, 5, tzinfo=timezone.utc),
            venue="Venue",
            address="Address",
            city="City",
            organizer_id=organizer_user.id,
        )
        db_session.add(exhibition)
        db_session.commit()

        assert len(list(organizer_user.organized_exhibitions)) == 1
        assert organizer_user.organized_exhibitions[0].name == "Organizer's Expo"

    def test_exhibition_booths_cascade(self, db_session, sample_exhibition):
        """测试：展会-展位关系"""
        booth1 = Booth(exhibition_id=sample_exhibition.id, booth_number="D-001")
        booth2 = Booth(exhibition_id=sample_exhibition.id, booth_number="D-002")
        db_session.add(booth1)
        db_session.add(booth2)
        db_session.commit()

        assert sample_exhibition.booths.count() == 2


class TestEnumValues:
    """枚举值测试"""

    def test_user_role_values(self):
        """测试：用户角色枚举值"""
        assert UserRole.VISITOR.value == "visitor"
        assert UserRole.EXHIBITOR.value == "exhibitor"
        assert UserRole.BOSS.value == "boss"
        assert UserRole.ORGANIZER.value == "organizer"

    def test_user_status_values(self):
        """测试：用户状态枚举值"""
        assert UserStatus.PENDING.value == "pending"
        assert UserStatus.ACTIVE.value == "active"
        assert UserStatus.DISABLED.value == "disabled"
        assert UserStatus.BANNED.value == "banned"

    def test_exhibition_status_values(self):
        """测试：展会状态枚举值"""
        assert ExhibitionStatus.DRAFT.value == "draft"
        assert ExhibitionStatus.PENDING.value == "pending"
        assert ExhibitionStatus.PUBLISHED.value == "published"
        assert ExhibitionStatus.ONGOING.value == "ongoing"
        assert ExhibitionStatus.ENDED.value == "ended"
        assert ExhibitionStatus.CANCELLED.value == "cancelled"

    def test_booth_status_values(self):
        """测试：展位状态枚举值"""
        assert BoothStatus.AVAILABLE.value == "available"
        assert BoothStatus.RESERVED.value == "reserved"
        assert BoothStatus.OCCUPIED.value == "occupied"
        assert BoothStatus.MAINTENANCE.value == "maintenance"
