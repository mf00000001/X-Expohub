"""
ExpoHub 核心数据表 DDL - MySQL 优化版

迁移说明：
- 创建 5 张核心表：users, exhibitions, booths, visitor_registrations, audit_logs
- 统一用户体系，通过 role 字段区分四类角色
- 复合索引优化查询性能
- 外键约束保证数据完整性
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """升级：创建所有核心表"""

    # ============================================================
    # 1. 用户表 - 四类角色统一存储
    # ============================================================
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("username", sa.String(50), nullable=False, comment="用户名"),
        sa.Column("email", sa.String(255), nullable=False, comment="邮箱"),
        sa.Column("phone", sa.String(20), nullable=True, comment="手机号"),
        sa.Column("password_hash", sa.String(255), nullable=False, comment="密码哈希"),

        # 角色与状态
        sa.Column("role", sa.Enum(
            "visitor", "exhibitor", "boss", "organizer",
            name="user_role_enum"
        ), nullable=False, server_default="visitor", comment="角色"),
        sa.Column("status", sa.Enum(
            "pending", "active", "disabled", "banned",
            name="user_status_enum"
        ), nullable=False, server_default="active", comment="用户状态"),

        # 个人信息
        sa.Column("nickname", sa.String(100), nullable=True, comment="昵称"),
        sa.Column("avatar_url", sa.String(500), nullable=True, comment="头像URL"),
        sa.Column("gender", sa.Enum(
            "male", "female", "other", "secret",
            name="gender_enum"
        ), nullable=True, server_default="secret", comment="性别"),
        sa.Column("company", sa.String(200), nullable=True, comment="公司名称"),
        sa.Column("position", sa.String(100), nullable=True, comment="职位"),
        sa.Column("bio", sa.Text(), nullable=True, comment="个人简介"),

        # 时间戳
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
                  nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),

        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username", name="uq_users_username"),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.UniqueConstraint("phone", name="uq_users_phone"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
        comment="统一用户表 - 游客/展商/主办方/老板四类角色共用",
    )

    # 用户表索引
    op.create_index("ix_users_username", "users", ["username"])
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_role", "users", ["role"])
    op.create_index("ix_users_status", "users", ["status"])
    op.create_index("ix_users_role_status", "users", ["role", "status"])
    op.create_index("ix_users_created_at", "users", ["created_at"])

    # ============================================================
    # 2. 展会表
    # ============================================================
    op.create_table(
        "exhibitions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(200), nullable=False, comment="展会名称"),
        sa.Column("short_name", sa.String(50), nullable=True, comment="展会简称"),
        sa.Column("description", sa.Text(), nullable=True, comment="展会描述"),
        sa.Column("cover_url", sa.String(500), nullable=True, comment="封面图URL"),

        # 时间信息
        sa.Column("start_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("registration_deadline", sa.DateTime(timezone=True), nullable=True),

        # 地点信息
        sa.Column("venue", sa.String(200), nullable=False, comment="场馆"),
        sa.Column("address", sa.String(500), nullable=False, comment="地址"),
        sa.Column("city", sa.String(100), nullable=False, comment="城市"),

        # 状态与主办方
        sa.Column("status", sa.Enum(
            "draft", "pending", "published", "ongoing", "ended", "cancelled",
            name="exhibition_status_enum"
        ), nullable=False, server_default="draft", comment="展会状态"),
        sa.Column("organizer_id", sa.Integer(), nullable=False, comment="主办方ID"),

        # 统计冗余字段
        sa.Column("total_booths", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("available_booths", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("visitor_count", sa.Integer(), nullable=False, server_default="0"),

        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
                  nullable=False),

        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["organizer_id"], ["users.id"],
            name="fk_exhibitions_organizer",
            ondelete="CASCADE",
        ),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
        comment="展会信息表",
    )

    # 展会表索引
    op.create_index("ix_exhibitions_name", "exhibitions", ["name"])
    op.create_index("ix_exhibitions_city", "exhibitions", ["city"])
    op.create_index("ix_exhibitions_status", "exhibitions", ["status"])
    op.create_index("ix_exhibitions_organizer_id", "exhibitions", ["organizer_id"])
    op.create_index("ix_exhibitions_city_status", "exhibitions", ["city", "status"])
    op.create_index("ix_exhibitions_date_range", "exhibitions", ["start_date", "end_date"])

    # ============================================================
    # 3. 展位表
    # ============================================================
    op.create_table(
        "booths",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("exhibition_id", sa.Integer(), nullable=False, comment="所属展会ID"),
        sa.Column("exhibitor_id", sa.Integer(), nullable=True, comment="展商用户ID"),

        sa.Column("booth_number", sa.String(50), nullable=False, comment="展位编号"),
        sa.Column("name", sa.String(200), nullable=True, comment="展位名称"),
        sa.Column("description", sa.Text(), nullable=True, comment="展位描述"),
        sa.Column("area", sa.Float(), nullable=True, comment="面积(㎡)"),
        sa.Column("price", sa.Float(), nullable=True, comment="价格"),
        sa.Column("floor", sa.Integer(), nullable=True, comment="楼层"),
        sa.Column("zone", sa.String(50), nullable=True, comment="展区"),

        sa.Column("status", sa.Enum(
            "available", "reserved", "occupied", "maintenance",
            name="booth_status_enum"
        ), nullable=False, server_default="available", comment="展位状态"),

        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
                  nullable=False),

        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["exhibition_id"], ["exhibitions.id"],
            name="fk_booths_exhibition",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["exhibitor_id"], ["users.id"],
            name="fk_booths_exhibitor",
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint(
            "exhibition_id", "booth_number",
            name="uq_exhibition_booth_number"
        ),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
        comment="展位表",
    )

    # 展位表索引
    op.create_index("ix_booths_exhibition_id", "booths", ["exhibition_id"])
    op.create_index("ix_booths_exhibitor_id", "booths", ["exhibitor_id"])
    op.create_index("ix_booths_status", "booths", ["status"])
    op.create_index("ix_booths_zone", "booths", ["zone"])
    op.create_index("ix_booths_exhibition_status", "booths", ["exhibition_id", "status"])

    # ============================================================
    # 4. 观众报名/收藏表
    # ============================================================
    op.create_table(
        "visitor_registrations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("visitor_id", sa.Integer(), nullable=False, comment="游客ID"),
        sa.Column("exhibition_id", sa.Integer(), nullable=False, comment="展会ID"),

        sa.Column("is_favorite", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("is_registered", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("ticket_code", sa.String(100), nullable=True, unique=True),
        sa.Column("check_in_at", sa.DateTime(timezone=True), nullable=True),

        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
                  nullable=False),

        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["visitor_id"], ["users.id"],
            name="fk_registrations_visitor",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["exhibition_id"], ["exhibitions.id"],
            name="fk_registrations_exhibition",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "visitor_id", "exhibition_id",
            name="uq_visitor_exhibition"
        ),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
        comment="观众报名/收藏展会记录表",
    )

    # 报名表索引
    op.create_index("ix_visitor_reg_visitor_id", "visitor_registrations", ["visitor_id"])
    op.create_index("ix_visitor_reg_exhibition_id", "visitor_registrations", ["exhibition_id"])
    op.create_index("ix_visitor_reg_exhibition_registered",
                    "visitor_registrations", ["exhibition_id", "is_registered"])

    # ============================================================
    # 5. 操作审计日志表
    # ============================================================
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True, comment="操作用户ID"),
        sa.Column("user_role", sa.String(20), nullable=True, comment="用户角色"),
        sa.Column("action", sa.String(100), nullable=False, comment="操作类型"),
        sa.Column("resource_type", sa.String(50), nullable=False, comment="资源类型"),
        sa.Column("resource_id", sa.String(50), nullable=True, comment="资源ID"),
        sa.Column("detail", sa.Text(), nullable=True, comment="操作详情(JSON)"),
        sa.Column("ip_address", sa.String(45), nullable=True, comment="请求IP"),
        sa.Column("user_agent", sa.String(500), nullable=True, comment="User-Agent"),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),

        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name="fk_audit_logs_user",
            ondelete="SET NULL",
        ),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
        comment="操作审计日志表",
    )

    # 审计日志索引
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_user_action", "audit_logs", ["user_id", "action"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])
    op.create_index("ix_audit_logs_resource", "audit_logs", ["resource_type", "resource_id"])


def downgrade() -> None:
    """回滚：删除所有表"""
    op.drop_table("audit_logs")
    op.drop_table("visitor_registrations")
    op.drop_table("booths")
    op.drop_table("exhibitions")
    op.drop_table("users")

    # 删除 ENUM 类型
    op.execute("DROP TYPE IF EXISTS user_role_enum")
    op.execute("DROP TYPE IF EXISTS user_status_enum")
    op.execute("DROP TYPE IF EXISTS gender_enum")
    op.execute("DROP TYPE IF EXISTS exhibition_status_enum")
    op.execute("DROP TYPE IF EXISTS booth_status_enum")
