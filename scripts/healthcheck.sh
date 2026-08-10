#!/bin/bash
# ============================================================
# ExpoHub 健康检查脚本
#
# 功能：
#   1. 检查 API 服务健康状态
#   2. 检查 MySQL 数据库连接
#   3. 检查 Redis 连接
#   4. 检查磁盘空间
#   5. 检查容器运行状态
#   6. 汇总报告
#
# 使用方式：
#   ./scripts/healthcheck.sh                  # 默认检查所有
#   ./scripts/healthcheck.sh --api-only       # 仅检查 API
#   ./scripts/healthcheck.sh --json           # JSON 格式输出
#   ./scripts/healthcheck.sh --slack-webhook  # 发送到 Slack
# ============================================================

set -euo pipefail

# ========== 颜色定义 ==========
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# ========== 配置 ==========
API_URL="${API_URL:-http://localhost:8000}"
MYSQL_HOST="${MYSQL_HOST:-localhost}"
MYSQL_PORT="${MYSQL_PORT:-3306}"
MYSQL_USER="${MYSQL_USER:-expo_hub}"
MYSQL_PASSWORD="${MYSQL_PASSWORD:-expo_hub_pass}"
MYSQL_DATABASE="${MYSQL_DATABASE:-expo_hub}"
REDIS_HOST="${REDIS_HOST:-localhost}"
REDIS_PORT="${REDIS_PORT:-6379}"
REDIS_PASSWORD="${REDIS_PASSWORD:-redis_pass}"
DISK_WARN_THRESHOLD="${DISK_WARN_THRESHOLD:-80}"  # 磁盘使用率警告阈值（%）
DISK_CRIT_THRESHOLD="${DISK_CRIT_THRESHOLD:-90}"  # 磁盘使用率严重阈值（%）

# ========== 状态变量 ==========
EXIT_CODE=0
RESULTS=()
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# ========== 辅助函数 ==========

print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

record_result() {
    local component="$1"
    local status="$2"
    local message="$3"
    RESULTS+=("$(echo "{\"component\":\"$component\",\"status\":\"$status\",\"message\":\"$message\",\"timestamp\":\"$TIMESTAMP\"}")")
    if [ "$status" != "OK" ]; then
        EXIT_CODE=1
    fi
}

# ========== 检查函数 ==========

check_api() {
    echo ""
    echo "=========================================="
    echo "  🔍 检查 API 服务"
    echo "=========================================="

    local http_code
    local response_time

    # 检查根路径
    http_code=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 --max-time 10 "${API_URL}/" 2>/dev/null || echo "000")
    response_time=$(curl -s -o /dev/null -w "%{time_total}" --connect-timeout 5 --max-time 10 "${API_URL}/" 2>/dev/null || echo "0")

    if [ "$http_code" = "200" ]; then
        print_info "根路径: HTTP $http_code (响应时间: ${response_time}s)"
        record_result "api_root" "OK" "HTTP $http_code, response_time=${response_time}s"
    else
        print_error "根路径: HTTP $http_code"
        record_result "api_root" "FAIL" "HTTP $http_code"
    fi

    # 检查 /health 端点
    local health_code
    health_code=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 --max-time 10 "${API_URL}/health" 2>/dev/null || echo "000")

    if [ "$health_code" = "200" ]; then
        print_info "健康检查端点: HTTP $health_code"
        record_result "api_health" "OK" "HTTP $health_code"
    else
        print_error "健康检查端点: HTTP $health_code"
        record_result "api_health" "FAIL" "HTTP $health_code"
    fi

    # 检查响应内容
    local response_body
    response_body=$(curl -s --connect-timeout 5 --max-time 10 "${API_URL}/" 2>/dev/null || echo "")
    if echo "$response_body" | grep -q '"status":"ok"'; then
        print_info "API 状态: 正常"
        record_result "api_status" "OK" "Service status is OK"
    else
        print_warn "API 响应内容异常: $response_body"
        record_result "api_status" "WARN" "Unexpected response: $response_body"
    fi
}

check_mysql() {
    echo ""
    echo "=========================================="
    echo "  🗄️  检查 MySQL 数据库"
    echo "=========================================="

    if ! command -v mysqladmin &>/dev/null; then
        print_warn "mysqladmin 未安装，尝试使用 docker exec"
        if docker ps --format '{{.Names}}' | grep -q "expohub-mysql"; then
            local ping_result
            ping_result=$(docker exec expohub-mysql mysqladmin ping -h localhost -u root -p"${MYSQL_PASSWORD}" --silent 2>/dev/null || echo "failed")
            if [ "$ping_result" = "mysqld is alive" ]; then
                print_info "MySQL 连接正常 (通过 docker exec)"
                record_result "mysql_connection" "OK" "mysqld is alive"
            else
                print_error "MySQL 连接失败 (通过 docker exec)"
                record_result "mysql_connection" "FAIL" "Cannot ping MySQL"
            fi
        else
            print_error "MySQL 容器未运行"
            record_result "mysql_connection" "FAIL" "Container not running"
        fi
        return
    fi

    # 直接连接检查
    if mysqladmin ping -h "${MYSQL_HOST}" -P "${MYSQL_PORT}" -u "${MYSQL_USER}" -p"${MYSQL_PASSWORD}" --silent 2>/dev/null; then
        print_info "MySQL 连接正常"
        record_result "mysql_connection" "OK" "mysqld is alive"

        # 检查数据库是否存在
        local db_exists
        db_exists=$(mysql -h "${MYSQL_HOST}" -P "${MYSQL_PORT}" -u "${MYSQL_USER}" -p"${MYSQL_PASSWORD}" -e "SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA WHERE SCHEMA_NAME='${MYSQL_DATABASE}';" 2>/dev/null)
        if echo "$db_exists" | grep -q "${MYSQL_DATABASE}"; then
            print_info "数据库 ${MYSQL_DATABASE} 存在"
            record_result "mysql_database" "OK" "Database ${MYSQL_DATABASE} exists"
        else
            print_error "数据库 ${MYSQL_DATABASE} 不存在"
            record_result "mysql_database" "FAIL" "Database not found"
        fi

        # 检查连接数
        local connections
        connections=$(mysql -h "${MYSQL_HOST}" -P "${MYSQL_PORT}" -u "${MYSQL_USER}" -p"${MYSQL_PASSWORD}" -e "SHOW STATUS LIKE 'Threads_connected';" 2>/dev/null | grep Threads_connected | awk '{print $2}')
        print_info "当前连接数: ${connections:-未知}"
        record_result "mysql_connections" "OK" "Connections: ${connections:-unknown}"
    else
        print_error "MySQL 连接失败"
        record_result "mysql_connection" "FAIL" "Cannot connect to MySQL"
    fi
}

check_redis() {
    echo ""
    echo "=========================================="
    echo "  🔴 检查 Redis 缓存"
    echo "=========================================="

    if ! command -v redis-cli &>/dev/null; then
        print_warn "redis-cli 未安装，尝试使用 docker exec"
        if docker ps --format '{{.Names}}' | grep -q "expohub-redis"; then
            local ping_result
            ping_result=$(docker exec expohub-redis redis-cli -a "${REDIS_PASSWORD}" ping 2>/dev/null || echo "failed")
            if [ "$ping_result" = "PONG" ]; then
                print_info "Redis 连接正常 (通过 docker exec)"
                record_result "redis_connection" "OK" "PONG"
            else
                print_error "Redis 连接失败 (通过 docker exec)"
                record_result "redis_connection" "FAIL" "Cannot ping Redis"
            fi
        else
            print_error "Redis 容器未运行"
            record_result "redis_connection" "FAIL" "Container not running"
        fi
        return
    fi

    # 直接连接检查
    local ping_result
    ping_result=$(redis-cli -h "${REDIS_HOST}" -p "${REDIS_PORT}" -a "${REDIS_PASSWORD}" ping 2>/dev/null || echo "failed")
    if [ "$ping_result" = "PONG" ]; then
        print_info "Redis 连接正常"
        record_result "redis_connection" "OK" "PONG"

        # 检查内存使用
        local info_memory
        info_memory=$(redis-cli -h "${REDIS_HOST}" -p "${REDIS_PORT}" -a "${REDIS_PASSWORD}" INFO memory 2>/dev/null || echo "")
        local used_memory_human
        used_memory_human=$(echo "$info_memory" | grep "used_memory_human:" | cut -d: -f2 | tr -d '\r')
        print_info "Redis 内存使用: ${used_memory_human:-未知}"
        record_result "redis_memory" "OK" "Memory: ${used_memory_human:-unknown}"
    else
        print_error "Redis 连接失败"
        record_result "redis_connection" "FAIL" "Cannot connect to Redis"
    fi
}

check_disk() {
    echo ""
    echo "=========================================="
    echo "  💾 检查磁盘空间"
    echo "=========================================="

    # 检查根分区
    local root_usage
    root_usage=$(df / | tail -1 | awk '{print $5}' | tr -d '%')
    print_info "根分区使用率: ${root_usage}%"

    if [ "$root_usage" -ge "$DISK_CRIT_THRESHOLD" ]; then
        print_error "根分区磁盘空间严重不足！"
        record_result "disk_root" "CRIT" "Usage: ${root_usage}% (threshold: ${DISK_CRIT_THRESHOLD}%)"
    elif [ "$root_usage" -ge "$DISK_WARN_THRESHOLD" ]; then
        print_warn "根分区磁盘空间不足"
        record_result "disk_root" "WARN" "Usage: ${root_usage}% (threshold: ${DISK_WARN_THRESHOLD}%)"
    else
        record_result "disk_root" "OK" "Usage: ${root_usage}%"
    fi

    # 检查 Docker 数据目录
    if command -v docker &>/dev/null; then
        local docker_root
        docker_root=$(docker info --format '{{.DockerRootDir}}' 2>/dev/null || echo "/var/lib/docker")
        if [ -d "$docker_root" ]; then
            local docker_usage
            docker_usage=$(df "$docker_root" | tail -1 | awk '{print $5}' | tr -d '%')
            print_info "Docker 数据目录使用率: ${docker_usage}%"
            if [ "$docker_usage" -ge "$DISK_CRIT_THRESHOLD" ]; then
                print_error "Docker 磁盘空间严重不足！"
                record_result "disk_docker" "CRIT" "Usage: ${docker_usage}%"
            elif [ "$docker_usage" -ge "$DISK_WARN_THRESHOLD" ]; then
                print_warn "Docker 磁盘空间不足"
                record_result "disk_docker" "WARN" "Usage: ${docker_usage}%"
            else
                record_result "disk_docker" "OK" "Usage: ${docker_usage}%"
            fi
        fi
    fi
}

check_containers() {
    echo ""
    echo "=========================================="
    echo "  🐳 检查 Docker 容器状态"
    echo "=========================================="

    if ! command -v docker &>/dev/null; then
        print_error "Docker 未安装"
        record_result "docker" "FAIL" "Docker not installed"
        return
    fi

    # 检查 expohub 相关容器
    local containers
    containers=$(docker ps --filter "name=expohub" --format "{{.Names}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || echo "")

    if [ -z "$containers" ]; then
        print_warn "未找到 expohub 相关容器"
        record_result "docker_containers" "WARN" "No expohub containers found"
        return
    fi

    echo "容器列表:"
    echo "$containers" | while IFS=$'\t' read -r name status ports; do
        if echo "$status" | grep -qi "healthy"; then
            print_info "  ✅ $name - $status"
        elif echo "$status" | grep -qi "up"; then
            print_warn "  ⚠️  $name - $status (无健康检查)"
        else
            print_error "  ❌ $name - $status"
        fi
        echo "     端口映射: $ports"
    done

    # 统计健康状态
    local total
    local healthy
    total=$(echo "$containers" | wc -l)
    healthy=$(echo "$containers" | grep -c "healthy" || true)
    record_result "docker_containers" "OK" "Containers: ${healthy}/${total} healthy"

    # 检查是否有重启的容器
    local restarting
    restarting=$(docker ps --filter "name=expohub" --filter "status=restarting" --format "{{.Names}}" 2>/dev/null)
    if [ -n "$restarting" ]; then
        print_error "以下容器正在重启: $restarting"
        record_result "docker_restarting" "FAIL" "Restarting containers: $restarting"
    fi
}

generate_report() {
    echo ""
    echo "=========================================="
    echo "  📊 健康检查报告"
    echo "=========================================="
    echo "时间戳: $TIMESTAMP"
    echo ""

    local total=${#RESULTS[@]}
    local ok=0
    local warn=0
    local fail=0
    local critical=0

    for result in "${RESULTS[@]}"; do
        local status
        status=$(echo "$result" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])" 2>/dev/null || echo "UNKNOWN")
        case "$status" in
            "OK")   ((ok++)) ;;
            "WARN") ((warn++)) ;;
            "FAIL") ((fail++)) ;;
            "CRIT") ((critical++)) ;;
        esac
    done

    echo "  总计: $total 项检查"
    echo -e "  ${GREEN}通过: $ok${NC}"
    [ "$warn" -gt 0 ] && echo -e "  ${YELLOW}警告: $warn${NC}"
    [ "$fail" -gt 0 ] && echo -e "  ${RED}失败: $fail${NC}"
    [ "$critical" -gt 0 ] && echo -e "  ${RED}严重: $critical${NC}"
    echo ""

    # 输出详细结果
    echo "详细结果:"
    for result in "${RESULTS[@]}"; do
        local component status message
        component=$(echo "$result" | python3 -c "import sys,json; print(json.load(sys.stdin)['component'])" 2>/dev/null || echo "unknown")
        status=$(echo "$result" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])" 2>/dev/null || echo "UNKNOWN")
        message=$(echo "$result" | python3 -c "import sys,json; print(json.load(sys.stdin)['message'])" 2>/dev/null || echo "")
        case "$status" in
            "OK")   echo -e "  ${GREEN}[$status]${NC} $component: $message" ;;
            "WARN") echo -e "  ${YELLOW}[$status]${NC} $component: $message" ;;
            "FAIL"|"CRIT") echo -e "  ${RED}[$status]${NC} $component: $message" ;;
        esac
    done

    echo ""
    if [ $EXIT_CODE -eq 0 ]; then
        print_info "✅ 所有检查通过"
    else
        print_error "❌ 存在 $((fail + critical)) 项异常，请及时处理"
    fi
}

generate_json_report() {
    echo "{"
    echo "  \"timestamp\": \"$TIMESTAMP\","
    echo "  \"exit_code\": $EXIT_CODE,"
    echo "  \"results\": ["
    local first=true
    for result in "${RESULTS[@]}"; do
        if [ "$first" = true ]; then
            first=false
        else
            echo ","
        fi
        echo "    $result"
    done
    echo ""
    echo "  ]"
    echo "}"
}

# ========== 主函数 ==========

main() {
    echo ""
    echo "╔══════════════════════════════════════════════╗"
    echo "║     ExpoHub 健康检查工具 v2.0                ║"
    echo "║     时间: $(date '+%Y-%m-%d %H:%M:%S UTC')              ║"
    echo "╚══════════════════════════════════════════════╝"

    local json_output=false

    # 解析参数
    for arg in "$@"; do
        case "$arg" in
            --api-only)
                check_api
                generate_report
                exit $EXIT_CODE
                ;;
            --json)
                json_output=true
                ;;
            --help|-h)
                echo "使用方式: $0 [选项]"
                echo "选项:"
                echo "  --api-only    仅检查 API 服务"
                echo "  --json        JSON 格式输出"
                echo "  --help|-h     显示帮助信息"
                exit 0
                ;;
        esac
    done

    # 执行所有检查
    check_api
    check_mysql
    check_redis
    check_disk
    check_containers

    # 输出报告
    if [ "$json_output" = true ]; then
        generate_json_report
    else
        generate_report
    fi

    exit $EXIT_CODE
}

main "$@"
