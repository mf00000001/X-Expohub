#!/bin/bash
# ============================================================
# ExpoHub 数据库备份脚本
#
# 功能：
#   1. MySQL 数据库完整备份（含存储过程、触发器、事件）
#   2. 压缩备份文件
#   3. 备份轮转（保留最近 N 天）
#   4. 可选：上传到远程存储（S3/MinIO）
#   5. 可选：发送通知（Slack/邮件）
#   6. 备份完整性验证
#
# 使用方式：
#   ./scripts/backup.sh                          # 执行备份
#   ./scripts/backup.sh --dry-run                # 试运行（不实际备份）
#   ./scripts/backup.sh --restore backup.sql.gz  # 恢复备份
#   ./scripts/backup.sh --list                   # 列出可用备份
#   ./scripts/backup.sh --cron                   # 定时任务模式
#
# 推荐 crontab 配置：
#   0 2 * * * /path/to/scripts/backup.sh --cron >> /var/log/expohub-backup.log 2>&1
# ============================================================

set -euo pipefail

# ========== 配置 ==========

# 数据库配置
MYSQL_HOST="${MYSQL_HOST:-localhost}"
MYSQL_PORT="${MYSQL_PORT:-3306}"
MYSQL_USER="${MYSQL_USER:-expo_hub}"
MYSQL_PASSWORD="${MYSQL_PASSWORD:-expo_hub_pass}"
MYSQL_DATABASE="${MYSQL_DATABASE:-expo_hub}"

# Docker 容器名（如果在容器内运行）
MYSQL_CONTAINER="${MYSQL_CONTAINER:-expohub-mysql}"

# 备份存储配置
BACKUP_DIR="${BACKUP_DIR:-/data/backups/mysql}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"          # 本地保留天数
RETENTION_WEEKLY="${RETENTION_WEEKLY:-12}"      # 周备份保留个数
RETENTION_MONTHLY="${RETION_MONTHLY:-6}"        # 月备份保留个数

# 远程存储配置（可选）
REMOTE_ENABLED="${REMOTE_ENABLED:-false}"
REMOTE_TYPE="${REMOTE_TYPE:-s3}"                # s3 / minio / scp
REMOTE_BUCKET="${REMOTE_BUCKET:-expohub-backups}"
REMOTE_ENDPOINT="${REMOTE_ENDPOINT:-}"
REMOTE_ACCESS_KEY="${REMOTE_ACCESS_KEY:-}"
REMOTE_SECRET_KEY="${REMOTE_SECRET_KEY:-}"

# 通知配置（可选）
SLACK_WEBHOOK_URL="${SLACK_WEBHOOK_URL:-}"
NOTIFY_ON_FAILURE_ONLY="${NOTIFY_ON_FAILURE_ONLY:-true}"

# ========== 颜色与格式 ==========
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DATE_TAG=$(date +%Y%m%d)
WEEK_NUM=$(date +%V)
MONTH_NUM=$(date +%Y%m)
BACKUP_LOG="${BACKUP_DIR}/backup_${TIMESTAMP}.log"

# ========== 辅助函数 ==========

log_info() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')] [INFO]${NC} $*" | tee -a "$BACKUP_LOG"
}

log_warn() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] [WARN]${NC} $*" | tee -a "$BACKUP_LOG"
}

log_error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] [ERROR]${NC} $*" | tee -a "$BACKUP_LOG"
}

cleanup() {
    local exit_code=$?
    if [ $exit_code -ne 0 ]; then
        log_error "备份过程异常退出 (exit code: $exit_code)"
        send_notification "❌ ExpoHub 数据库备份失败" "备份过程异常退出，错误码: $exit_code"
    fi
    exit $exit_code
}

trap cleanup EXIT

# ========== 通知函数 ==========

send_notification() {
    local subject="$1"
    local message="$2"

    # Slack 通知
    if [ -n "$SLACK_WEBHOOK_URL" ]; then
        local payload
        payload=$(cat <<EOF
{
    "text": "*${subject}*",
    "blocks": [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "${subject}"
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "${message}"
            }
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "Host: $(hostname) | Time: $(date '+%Y-%m-%d %H:%M:%S')"
                }
            ]
        }
    ]
}
EOF
)
        curl -s -X POST -H "Content-Type: application/json" -d "$payload" "$SLACK_WEBHOOK_URL" > /dev/null 2>&1 || log_warn "Slack 通知发送失败"
    fi
}

# ========== 备份函数 ==========

check_prerequisites() {
    log_info "检查前置条件..."

    # 创建备份目录
    mkdir -p "${BACKUP_DIR}/{daily,weekly,monthly}"

    # 检查 mysqldump 是否可用
    if command -v mysqldump &>/dev/null; then
        MYSQLDUMP_CMD="mysqldump"
        log_info "使用本地 mysqldump"
    elif command -v docker &>/dev/null; then
        # 尝试通过 docker 执行
        if docker ps --format '{{.Names}}' | grep -q "${MYSQL_CONTAINER}"; then
            MYSQLDUMP_CMD="docker exec ${MYSQL_CONTAINER} mysqldump"
            log_info "使用 Docker 容器内的 mysqldump"
        else
            log_error "MySQL 容器 ${MYSQL_CONTAINER} 未运行"
            exit 1
        fi
    else
        log_error "未找到 mysqldump 或 Docker"
        exit 1
    fi

    # 检查 gzip
    if ! command -v gzip &>/dev/null; then
        log_error "gzip 未安装"
        exit 1
    fi

    # 检查磁盘空间
    local available_space
    available_space=$(df "$BACKUP_DIR" | tail -1 | awk '{print $4}')
    if [ "${available_space}" -lt 1048576 ]; then  # 小于 1GB 警告
        log_warn "备份目录磁盘空间不足 1GB，当前可用: $((available_space / 1024))MB"
    fi

    log_info "前置条件检查通过"
}

do_backup() {
    local backup_type="${1:-daily}"
    local backup_file="${BACKUP_DIR}/${backup_type}/expo_hub_${DATE_TAG}_${TIMESTAMP}.sql"
    local backup_file_gz="${backup_file}.gz"

    log_info "开始 ${backup_type} 备份..."
    log_info "备份文件: ${backup_file_gz}"

    # 执行备份
    log_info "导出数据库 ${MYSQL_DATABASE}..."

    # mysqldump 参数说明：
    #   --single-transaction: 保证一致性读，不锁表
    #   --routines: 导出存储过程和函数
    #   --triggers: 导出触发器
    #   --events: 导出事件
    #   --quick: 逐行读取，避免大表内存占用
    #   --lock-tables=false: 不锁表（配合 single-transaction）
    #   --set-gtid-purged=OFF: 不输出 GTID 信息（便于跨环境恢复）
    if $MYSQLDUMP_CMD \
        -h "$MYSQL_HOST" \
        -P "$MYSQL_PORT" \
        -u "$MYSQL_USER" \
        -p"$MYSQL_PASSWORD" \
        --databases "$MYSQL_DATABASE" \
        --single-transaction \
        --routines \
        --triggers \
        --events \
        --quick \
        --lock-tables=false \
        --set-gtid-purged=OFF \
        --skip-tz-utc \
        2>> "$BACKUP_LOG" | gzip > "$backup_file_gz"; then

        # 验证备份文件
        local file_size
        file_size=$(stat -c%s "$backup_file_gz" 2>/dev/null || stat -f%z "$backup_file_gz" 2>/dev/null || echo "0")

        if [ "$file_size" -eq 0 ]; then
            log_error "备份文件为空"
            rm -f "$backup_file_gz"
            return 1
        fi

        # 验证 gzip 完整性
        if ! gzip -t "$backup_file_gz" 2>/dev/null; then
            log_error "备份文件损坏（gzip 校验失败）"
            rm -f "$backup_file_gz"
            return 1
        fi

        log_info "备份完成！文件大小: $(numfmt --to=iec $file_size)"

        # 创建周/月备份的硬链接
        if [ "$backup_type" = "daily" ]; then
            # 如果是周一，保存为周备份
            if [ "$(date +%u)" -eq 1 ]; then
                ln -f "$backup_file_gz" "${BACKUP_DIR}/weekly/expo_hub_week${WEEK_NUM}_${DATE_TAG}.sql.gz"
                log_info "创建周备份链接"
            fi
            # 如果是1号，保存为月备份
            if [ "$(date +%d)" -eq 1 ]; then
                ln -f "$backup_file_gz" "${BACKUP_DIR}/monthly/expo_hub_${MONTH_NUM}.sql.gz"
                log_info "创建月备份链接"
            fi
        fi

        # 生成校验和
        md5sum "$backup_file_gz" > "${backup_file_gz}.md5"
        log_info "校验和文件: ${backup_file_gz}.md5"

        return 0
    else
        log_error "备份执行失败"
        return 1
    fi
}

rotate_backups() {
    log_info "清理过期备份..."

    local deleted_count=0

    # 清理每日备份（保留 N 天）
    if [ "$RETENTION_DAYS" -gt 0 ]; then
        local old_files
        old_files=$(find "${BACKUP_DIR}/daily" -name "expo_hub_*.sql.gz" -type f -mtime "+${RETENTION_DAYS}" 2>/dev/null)
        for file in $old_files; do
            rm -f "$file" "${file}.md5"
            ((deleted_count++))
        done
    fi

    # 清理周备份（保留 N 个）
    if [ "$RETENTION_WEEKLY" -gt 0 ]; then
        local weekly_backups
        weekly_backups=$(ls -t "${BACKUP_DIR}/weekly"/expo_hub_*.sql.gz 2>/dev/null | tail -n +$((RETENTION_WEEKLY + 1)))
        for file in $weekly_backups; do
            [ -f "$file" ] && rm -f "$file" "${file}.md5" && ((deleted_count++))
        done
    fi

    # 清理月备份（保留 N 个）
    if [ "$RETENTION_MONTHLY" -gt 0 ]; then
        local monthly_backups
        monthly_backups=$(ls -t "${BACKUP_DIR}/monthly"/expo_hub_*.sql.gz 2>/dev/null | tail -n +$((RETENTION_MONTHLY + 1)))
        for file in $monthly_backups; do
            [ -f "$file" ] && rm -f "$file" "${file}.md5" && ((deleted_count++))
        done
    fi

    if [ "$deleted_count" -gt 0 ]; then
        log_info "已清理 ${deleted_count} 个过期备份"
    else
        log_info "无需清理"
    fi
}

upload_remote() {
    if [ "$REMOTE_ENABLED" != "true" ]; then
        return 0
    fi

    log_info "上传到远程存储..."

    local latest_backup
    latest_backup=$(ls -t "${BACKUP_DIR}/daily"/*.sql.gz 2>/dev/null | head -1)

    if [ -z "$latest_backup" ]; then
        log_warn "没有可上传的备份文件"
        return 0
    fi

    case "$REMOTE_TYPE" in
        s3|minio)
            if command -v aws &>/dev/null; then
                AWS_ACCESS_KEY_ID="$REMOTE_ACCESS_KEY" \
                AWS_SECRET_ACCESS_KEY="$REMOTE_SECRET_KEY" \
                AWS_ENDPOINT_URL="$REMOTE_ENDPOINT" \
                aws s3 cp "$latest_backup" "s3://${REMOTE_BUCKET}/$(basename "$latest_backup")" \
                    --only-show-errors 2>> "$BACKUP_LOG" && \
                log_info "远程上传成功" || \
                log_warn "远程上传失败"
            else
                log_warn "aws CLI 未安装，跳过远程上传"
            fi
            ;;
        scp)
            if [ -n "${REMOTE_SCP_TARGET:-}" ]; then
                scp "$latest_backup" "$REMOTE_SCP_TARGET" 2>> "$BACKUP_LOG" && \
                log_info "SCP 上传成功" || \
                log_warn "SCP 上传失败"
            fi
            ;;
        *)
            log_warn "未知的远程存储类型: $REMOTE_TYPE"
            ;;
    esac
}

verify_backup() {
    log_info "验证最新备份..."

    local latest_backup
    latest_backup=$(ls -t "${BACKUP_DIR}/daily"/*.sql.gz 2>/dev/null | head -1)

    if [ -z "$latest_backup" ]; then
        log_warn "没有可验证的备份文件"
        return 0
    fi

    # 验证 gzip 完整性
    if gzip -t "$latest_backup" 2>/dev/null; then
        log_info "✅ 备份文件完整性验证通过: $(basename "$latest_backup")"
    else
        log_error "❌ 备份文件损坏"
        return 1
    fi

    # 验证 SQL 语法（解压后检查前几行）
    if zcat "$latest_backup" 2>/dev/null | head -20 | grep -q "CREATE DATABASE\|-- MySQL dump"; then
        log_info "✅ 备份内容格式验证通过"
    else
        log_error "❌ 备份内容格式异常"
        return 1
    fi

    return 0
}

list_backups() {
    echo ""
    echo "=========================================="
    echo "  📋 ExpoHub 备份列表"
    echo "=========================================="
    echo ""

    for type in daily weekly monthly; do
        local dir="${BACKUP_DIR}/${type}"
        echo "--- ${type^} Backups ---"
        if [ -d "$dir" ]; then
            local count
            count=$(ls -1 "$dir"/*.sql.gz 2>/dev/null | wc -l)
            if [ "$count" -gt 0 ]; then
                ls -lhS "$dir"/*.sql.gz 2>/dev/null | awk '{printf "  %s %s %s\n", $6, $7, $9}'
                echo "  总计: $count 个备份文件"
            else
                echo "  (空)"
            fi
        else
            echo "  (目录不存在)"
        fi
        echo ""
    done
}

restore_backup() {
    local backup_file="$1"

    if [ ! -f "$backup_file" ]; then
        log_error "备份文件不存在: $backup_file"
        exit 1
    fi

    log_info "开始恢复备份: $backup_file"
    log_warn "恢复操作将覆盖现有数据库！"
    echo -n "确认恢复？(yes/no): "
    read -r confirm

    if [ "$confirm" != "yes" ]; then
        log_info "恢复已取消"
        exit 0
    fi

    # 解压并恢复
    if [[ "$backup_file" == *.gz ]]; then
        gunzip -c "$backup_file" | mysql \
            -h "$MYSQL_HOST" \
            -P "$MYSQL_PORT" \
            -u "$MYSQL_USER" \
            -p"$MYSQL_PASSWORD" \
            2>> "$BACKUP_LOG"
    else
        mysql -h "$MYSQL_HOST" \
            -P "$MYSQL_PORT" \
            -u "$MYSQL_USER" \
            -p"$MYSQL_PASSWORD" \
            < "$backup_file" \
            2>> "$BACKUP_LOG"
    fi

    if [ $? -eq 0 ]; then
        log_info "✅ 数据库恢复成功"
        send_notification "✅ ExpoHub 数据库恢复完成" "数据库已从备份恢复: $(basename "$backup_file")"
    else
        log_error "❌ 数据库恢复失败"
        send_notification "❌ ExpoHub 数据库恢复失败" "恢复操作失败: $(basename "$backup_file")"
        exit 1
    fi
}

# ========== 主函数 ==========

main() {
    echo ""
    echo "╔══════════════════════════════════════════════╗"
    echo "║     ExpoHub 数据库备份工具 v2.0              ║"
    echo "║     时间: $(date '+%Y-%m-%d %H:%M:%S')                  ║"
    echo "╚══════════════════════════════════════════════╝"
    echo ""

    # 解析参数
    case "${1:-}" in
        --dry-run)
            log_info "=== 试运行模式 ==="
            check_prerequisites
            log_info "将执行以下操作:"
            echo "  1. 备份数据库: ${MYSQL_DATABASE}"
            echo "  2. 备份目录: ${BACKUP_DIR}/daily/"
            echo "  3. 保留策略: 每日 ${RETENTION_DAYS}天 / 每周 ${RETENTION_WEEKLY}个 / 每月 ${RETENTION_MONTHLY}个"
            [ "$REMOTE_ENABLED" = "true" ] && echo "  4. 远程上传: 已启用 ($REMOTE_TYPE)" || echo "  4. 远程上传: 未启用"
            exit 0
            ;;
        --list)
            list_backups
            exit 0
            ;;
        --restore)
            if [ -z "${2:-}" ]; then
                log_error "请指定要恢复的备份文件"
                echo "使用方式: $0 --restore /path/to/backup.sql.gz"
                exit 1
            fi
            restore_backup "$2"
            exit 0
            ;;
        --cron)
            log_info "=== 定时备份模式 ==="
            ;;
        --help|-h)
            echo "使用方式: $0 [选项]"
            echo ""
            echo "选项:"
            echo "  (无参数)    执行完整备份流程"
            echo "  --dry-run   试运行，不实际备份"
            echo "  --list      列出可用备份"
            echo "  --restore   恢复备份"
            echo "  --cron      定时任务模式"
            echo "  --help,-h   显示帮助信息"
            exit 0
            ;;
    esac

    # 执行备份流程
    local backup_status=0

    check_prerequisites

    if do_backup "daily"; then
        backup_status=0
        log_info "✅ 每日备份成功"

        # 验证备份
        verify_backup || backup_status=1

        # 清理过期备份
        rotate_backups

        # 上传远程
        upload_remote

        # 发送成功通知
        if [ "$NOTIFY_ON_FAILURE_ONLY" != "true" ]; then
            local latest_file
            latest_file=$(ls -t "${BACKUP_DIR}/daily"/*.sql.gz 2>/dev/null | head -1)
            local file_size
            file_size=$(stat -c%s "$latest_file" 2>/dev/null | numfmt --to=iec 2>/dev/null || echo "unknown")
            send_notification "✅ ExpoHub 数据库备份成功" "备份文件: $(basename "$latest_file")\n文件大小: $file_size\n保留天数: ${RETENTION_DAYS}天"
        fi
    else
        backup_status=1
        log_error "❌ 每日备份失败"
        send_notification "❌ ExpoHub 数据库备份失败" "请检查服务器日志: ${BACKUP_LOG}"
    fi

    # 打印日志路径
    log_info "备份日志: ${BACKUP_LOG}"

    exit $backup_status
}

main "$@"
