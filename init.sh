#!/bin/bash
# ========================================
# Creative Agent 环境自愈脚本
# Harness Engineering: 环境坏了，代码写得再好也没用
# ========================================

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# ========================================
# 1. 依赖检查与安装
# ========================================
check_uv() {
    if ! command -v uv &> /dev/null; then
        log_error "uv 未安装，请先安装: curl -LsSf https://astral.sh/uv/install.sh | sh"
        exit 1
    fi
    log_info "uv 已安装: $(uv --version)"
}

check_python() {
    local python_version=$(python3 --version 2>&1 | awk '{print $2}')
    local major=$(echo $python_version | cut -d. -f1)
    local minor=$(echo $python_version | cut -d. -f2)

    if [ "$major" -lt 3 ] || ([ "$major" -eq 3 ] && [ "$minor" -lt 10 ]); then
        log_error "Python 版本过低: $python_version，需要 >= 3.10"
        exit 1
    fi
    log_info "Python 版本: $python_version"
}

install_dependencies() {
    log_info "安装依赖..."
    uv sync --all-extras
    log_info "依赖安装完成"
}

# ========================================
# 2. 环境变量检查
# ========================================
check_env() {
    if [ ! -f ".env" ]; then
        log_warn ".env 文件不存在，从 .env.example 复制..."
        cp .env.example .env
        log_warn "请编辑 .env 文件填写真实的 API Key"
    fi
    log_info ".env 文件存在"
}

# ========================================
# 3. 服务健康检查
# ========================================
check_lightrag() {
    local lightrag_url="${LIGHTRAG_URL:-http://localhost:9621}"

    if curl -s --connect-timeout 3 "$lightrag_url/health" > /dev/null 2>&1; then
        log_info "LightRAG 服务正常: $lightrag_url"
    else
        log_warn "LightRAG 服务未启动: $lightrag_url"
        log_warn "请确保 LightRAG 服务正在运行"
    fi
}

# ========================================
# 4. 冒烟测试
# ========================================
run_sanity_test() {
    log_info "运行冒烟测试..."

    # 检查模块导入
    uv run python -c "
from src.config import settings
from src.constraints.rules import ConstraintChecker
from src.feedback.evaluator import ContentEvaluator
print('✓ 核心模块导入成功')
" 2>&1

    if [ $? -eq 0 ]; then
        log_info "冒烟测试通过"
    else
        log_error "冒烟测试失败，请检查代码"
        exit 1
    fi
}

# ========================================
# 5. 代码质量检查
# ========================================
run_quality_check() {
    log_info "运行代码质量检查..."

    # Lint
    if uv run ruff check src/ --quiet; then
        log_info "代码风格检查通过"
    else
        log_warn "代码风格检查发现问题，尝试自动修复..."
        uv run ruff check src/ --fix
    fi

    # 类型检查
    if uv run mypy src/ --ignore-missing-imports 2>&1 | grep -q "Success"; then
        log_info "类型检查通过"
    else
        log_warn "类型检查发现问题"
    fi
}

# ========================================
# 6. 测试运行
# ========================================
run_tests() {
    log_info "运行单元测试..."
    uv run pytest tests/ -v --tb=short -q
}

# ========================================
# 主流程
# ========================================
main() {
    echo ""
    echo "========================================"
    echo "  Creative Agent 环境自愈检查"
    echo "========================================"
    echo ""

    log_info "项目根目录: $PROJECT_ROOT"

    # 1. 基础依赖
    check_uv
    check_python
    install_dependencies

    # 2. 环境配置
    check_env

    # 3. 服务检查
    check_lightrag

    # 4. 冒烟测试
    run_sanity_test

    # 5. 质量检查（可选）
    if [ "$1" == "--full" ]; then
        run_quality_check
        run_tests
    fi

    echo ""
    echo "========================================"
    log_info "环境检查完成，可以开始开发"
    echo "========================================"
    echo ""
    echo "快速命令:"
    echo "  uv run python -m src.main    # 运行主程序"
    echo "  uv run pytest tests/ -v      # 运行测试"
    echo "  ./init.sh --full             # 完整检查"
    echo ""
}

main "$@"
