-- ============================================================
-- ExpoHub 数据库初始化脚本
-- 适用于 MySQL 8.0+
-- 在 docker-compose 启动时自动执行
-- ============================================================

-- 创建数据库（如果不存在）
CREATE DATABASE IF NOT EXISTS expo_hub
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE expo_hub;

-- ============================================================
-- 1. 用户表 - 四类角色统一存储
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
    id              INT             NOT NULL AUTO_INCREMENT,
    username        VARCHAR(50)     NOT NULL COMMENT '用户名',
    email           VARCHAR(255)    NOT NULL COMMENT '邮箱',
    phone           VARCHAR(20)     NULL COMMENT '手机号',
    password_hash   VARCHAR(255)    NOT NULL COMMENT '密码哈希值',

    -- 角色与状态
    role            ENUM('visitor', 'exhibitor', 'boss', 'organizer')
                    NOT NULL DEFAULT 'visitor' COMMENT '角色',
    status          ENUM('pending', 'active', 'disabled', 'banned')
                    NOT NULL DEFAULT 'active' COMMENT '用户状态',

    -- 个人信息
    nickname        VARCHAR(100)    NULL COMMENT '昵称',
    avatar_url      VARCHAR(500)    NULL COMMENT '头像URL',
    gender          ENUM('male', 'female', 'other', 'secret')
                    NOT NULL DEFAULT 'secret' COMMENT '性别',
    company         VARCHAR(200)    NULL COMMENT '公司/机构名称',
    position        VARCHAR(100)    NULL COMMENT '职位',
    bio             TEXT            NULL COMMENT '个人简介',

    -- 时间戳
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    last_login_at   DATETIME        NULL COMMENT '最后登录时间',
    deleted_at      DATETIME        NULL COMMENT '软删除时间',

    PRIMARY KEY (id),
    UNIQUE KEY uq_users_username (username),
    UNIQUE KEY uq_users_email (email),
    UNIQUE KEY uq_users_phone (phone),

    INDEX ix_users_username (username),
    INDEX ix_users_email (email),
    INDEX ix_users_role (role),
    INDEX ix_users_status (status),
    INDEX ix_users_role_status (role, status),
    INDEX ix_users_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='统一用户表 - 游客/展商/主办方/老板四类角色共用';

-- ============================================================
-- 2. 展会表
-- ============================================================
CREATE TABLE IF NOT EXISTS exhibitions (
    id                  INT             NOT NULL AUTO_INCREMENT,
    name                VARCHAR(200)    NOT NULL COMMENT '展会名称',
    short_name          VARCHAR(50)     NULL COMMENT '展会简称',
    description         TEXT            NULL COMMENT '展会描述',
    cover_url           VARCHAR(500)    NULL COMMENT '封面图URL',

    -- 时间信息
    start_date          DATETIME        NOT NULL COMMENT '开始时间',
    end_date            DATETIME        NOT NULL COMMENT '结束时间',
    registration_deadline DATETIME      NULL COMMENT '报名截止时间',

    -- 地点信息
    venue               VARCHAR(200)    NOT NULL COMMENT '举办场馆',
    address             VARCHAR(500)    NOT NULL COMMENT '详细地址',
    city                VARCHAR(100)    NOT NULL COMMENT '城市',

    -- 状态与主办方
    status              ENUM('draft', 'pending', 'published', 'ongoing', 'ended', 'cancelled')
                        NOT NULL DEFAULT 'draft' COMMENT '展会状态',
    organizer_id        INT             NOT NULL COMMENT '主办方用户ID',

    -- 统计冗余字段
    total_booths        INT             NOT NULL DEFAULT 0 COMMENT '总展位数',
    available_booths    INT             NOT NULL DEFAULT 0 COMMENT '可用展位数',
    visitor_count       INT             NOT NULL DEFAULT 0 COMMENT '报名观众数',

    created_at          DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at          DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

    PRIMARY KEY (id),
    INDEX ix_exhibitions_name (name),
    INDEX ix_exhibitions_city (city),
    INDEX ix_exhibitions_status (status),
    INDEX ix_exhibitions_organizer_id (organizer_id),
    INDEX ix_exhibitions_city_status (city, status),
    INDEX ix_exhibitions_date_range (start_date, end_date),

    CONSTRAINT fk_exhibitions_organizer
        FOREIGN KEY (organizer_id) REFERENCES users(id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='展会信息表';

-- ============================================================
-- 3. 展位表
-- ============================================================
CREATE TABLE IF NOT EXISTS booths (
    id              INT             NOT NULL AUTO_INCREMENT,
    exhibition_id   INT             NOT NULL COMMENT '所属展会ID',
    exhibitor_id    INT             NULL COMMENT '展商用户ID',

    booth_number    VARCHAR(50)     NOT NULL COMMENT '展位编号，如 A-001',
    name            VARCHAR(200)    NULL COMMENT '展位名称/标题',
    description     TEXT            NULL COMMENT '展位描述',
    area            DECIMAL(10,2)   NULL COMMENT '展位面积（平方米）',
    price           DECIMAL(12,2)   NULL COMMENT '展位价格',
    floor           INT             NULL COMMENT '楼层',
    zone            VARCHAR(50)     NULL COMMENT '展区，如 A区/B区',

    status          ENUM('available', 'reserved', 'occupied', 'maintenance')
                    NOT NULL DEFAULT 'available' COMMENT '展位状态',

    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

    PRIMARY KEY (id),
    UNIQUE KEY uq_exhibition_booth_number (exhibition_id, booth_number),

    INDEX ix_booths_exhibition_id (exhibition_id),
    INDEX ix_booths_exhibitor_id (exhibitor_id),
    INDEX ix_booths_status (status),
    INDEX ix_booths_zone (zone),
    INDEX ix_booths_exhibition_status (exhibition_id, status),

    CONSTRAINT fk_booths_exhibition
        FOREIGN KEY (exhibition_id) REFERENCES exhibitions(id)
        ON DELETE CASCADE,
    CONSTRAINT fk_booths_exhibitor
        FOREIGN KEY (exhibitor_id) REFERENCES users(id)
        ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='展位表';

-- ============================================================
-- 4. 观众报名/收藏表
-- ============================================================
CREATE TABLE IF NOT EXISTS visitor_registrations (
    id              INT             NOT NULL AUTO_INCREMENT,
    visitor_id      INT             NOT NULL COMMENT '游客用户ID',
    exhibition_id   INT             NOT NULL COMMENT '展会ID',

    is_favorite     TINYINT(1)      NOT NULL DEFAULT 0 COMMENT '是否收藏',
    is_registered   TINYINT(1)      NOT NULL DEFAULT 0 COMMENT '是否已报名',
    ticket_code     VARCHAR(100)    NULL COMMENT '电子票编码',
    check_in_at     DATETIME        NULL COMMENT '签到时间',

    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',

    PRIMARY KEY (id),
    UNIQUE KEY uq_visitor_exhibition (visitor_id, exhibition_id),
    UNIQUE KEY uq_ticket_code (ticket_code),

    INDEX ix_visitor_reg_visitor_id (visitor_id),
    INDEX ix_visitor_reg_exhibition_id (exhibition_id),
    INDEX ix_visitor_reg_exhibition_registered (exhibition_id, is_registered),

    CONSTRAINT fk_registrations_visitor
        FOREIGN KEY (visitor_id) REFERENCES users(id)
        ON DELETE CASCADE,
    CONSTRAINT fk_registrations_exhibition
        FOREIGN KEY (exhibition_id) REFERENCES exhibitions(id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='观众报名/收藏展会记录表';

-- ============================================================
-- 5. 操作审计日志表
-- ============================================================
CREATE TABLE IF NOT EXISTS audit_logs (
    id              BIGINT          NOT NULL AUTO_INCREMENT,
    user_id         INT             NULL COMMENT '操作用户ID',
    user_role       VARCHAR(20)     NULL COMMENT '用户角色',
    action          VARCHAR(100)    NOT NULL COMMENT '操作类型',
    resource_type   VARCHAR(50)     NOT NULL COMMENT '资源类型',
    resource_id     VARCHAR(50)     NULL COMMENT '资源ID',
    detail          JSON            NULL COMMENT '操作详情',
    ip_address      VARCHAR(45)     NULL COMMENT '请求IP',
    user_agent      VARCHAR(500)    NULL COMMENT 'User-Agent',
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '操作时间',

    PRIMARY KEY (id),
    INDEX ix_audit_logs_user_id (user_id),
    INDEX ix_audit_logs_action (action),
    INDEX ix_audit_logs_user_action (user_id, action),
    INDEX ix_audit_logs_created_at (created_at),
    INDEX ix_audit_logs_resource (resource_type, resource_id),

    CONSTRAINT fk_audit_logs_user
        FOREIGN KEY (user_id) REFERENCES users(id)
        ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='操作审计日志表';

-- ============================================================
-- 插入测试数据（四类角色各一个）
-- ============================================================
-- 密码都是 "Test1234"
INSERT INTO users (username, email, phone, password_hash, role, status, nickname, company) VALUES
    ('visitor_alice', 'alice@example.com', '13800000001',
     '$2b$12$LJ3m4ys3Lk0TSwHnbfOMiOXPm1Qlq5Gz0q5Gz0q5Gz0q5Gz0q5GzO',
     'visitor', 'active', '爱丽丝', NULL),
    ('exhibitor_bob', 'bob@example.com', '13800000002',
     '$2b$12$LJ3m4ys3Lk0TSwHnbfOMiOXPm1Qlq5Gz0q5Gz0q5Gz0q5Gz0q5GzO',
     'exhibitor', 'active', '鲍勃科技', '鲍勃科技有限公司'),
    ('organizer_carol', 'carol@example.com', '13800000003',
     '$2b$12$LJ3m4ys3Lk0TSwHnbfOMiOXPm1Qlq5Gz0q5Gz0q5Gz0q5Gz0q5GzO',
     'organizer', 'active', '卡罗尔会展', '卡罗尔国际会展有限公司'),
    ('boss_dave', 'dave@example.com', '13800000004',
     '$2b$12$LJ3m4ys3Lk0TSwHnbfOMiOXPm1Qlq5Gz0q5Gz0q5Gz0q5Gz0q5GzO',
     'boss', 'active', '戴维总裁', '戴维集团');
