#!/bin/bash
# 质量检查脚本
# 一键运行所有质量检查工具

set -e

echo "🚀 开始运行质量检查套件..."

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印分隔线
print_separator() {
    echo -e "${BLUE}================================================${NC}"
}

# 打印步骤标题
print_step() {
    echo -e "\n${BLUE}📝 $1${NC}"
    print_separator
}

# 打印成功信息
print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

# 打印警告信息
print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

# 打印错误信息
print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# 检查命令是否存在
check_command() {
    if ! command -v $1 &> /dev/null; then
        print_error "$1 未安装或不在PATH中"
        return 1
    fi
    return 0
}

# 记录开始时间
START_TIME=$(date +%s)
OVERALL_SUCCESS=true

# 步骤1: 环境检查
print_step "环境检查"

if ! check_command uv; then
    print_error "UV 未安装，请先安装 UV: https://docs.astral.sh/uv/"
    exit 1
fi

print_success "UV 已安装"

# 检查项目结构
if [ ! -f "pyproject.toml" ]; then
    print_error "未找到 pyproject.toml 文件，请确保在项目根目录运行"
    exit 1
fi

print_success "项目结构检查通过"

# 步骤2: 安装依赖
print_step "安装项目依赖"

echo "安装开发依赖..."
if uv sync --all-extras; then
    print_success "依赖安装成功"
else
    print_error "依赖安装失败"
    exit 1
fi

# 步骤3: 代码格式检查
print_step "代码格式检查"

echo "检查 Black 代码格式..."
if uv run black --check src tests 2>/dev/null; then
    print_success "Black 代码格式检查通过"
else
    print_warning "Black 代码格式检查未通过，建议运行 'uv run black src tests' 修复"
    OVERALL_SUCCESS=false
fi

echo "检查 isort 导入排序..."
if uv run isort --check-only src tests 2>/dev/null; then
    print_success "isort 导入排序检查通过"
else
    print_warning "isort 导入排序检查未通过，建议运行 'uv run isort src tests' 修复"
    OVERALL_SUCCESS=false
fi

# 步骤4: 代码质量检查
print_step "代码质量检查"

echo "运行 flake8 代码风格检查..."
if uv run flake8 src tests; then
    print_success "flake8 代码风格检查通过"
else
    print_warning "flake8 代码风格检查发现问题"
    OVERALL_SUCCESS=false
fi

echo "运行 MyPy 类型检查..."
if uv run mypy src 2>/dev/null; then
    print_success "MyPy 类型检查通过"
else
    print_warning "MyPy 类型检查发现问题"
    OVERALL_SUCCESS=false
fi

# 步骤5: 安全检查
print_step "安全检查"

echo "运行 bandit 安全扫描..."
if uv run bandit -r src -c pyproject.toml; then
    print_success "bandit 安全扫描通过"
else
    print_warning "bandit 安全扫描发现潜在安全问题"
    OVERALL_SUCCESS=false
fi

echo "运行 safety 依赖安全检查..."
if uv run safety check 2>/dev/null; then
    print_success "safety 依赖安全检查通过"
else
    print_warning "safety 依赖安全检查发现潜在安全漏洞"
    OVERALL_SUCCESS=false
fi

# 步骤6: 测试检查
print_step "测试检查"

echo "运行单元测试和覆盖率检查..."
COVERAGE_CMD="uv run pytest tests/unit/ -v --cov=src/ontology_framework --cov-report=term-missing --cov-fail-under=75"

if $COVERAGE_CMD; then
    print_success "单元测试和覆盖率检查通过"
else
    print_warning "单元测试或覆盖率检查未达标"
    OVERALL_SUCCESS=false
fi

echo "运行集成测试..."
if uv run pytest tests/integration/ -v 2>/dev/null; then
    print_success "集成测试通过"
else
    print_warning "集成测试存在问题"
    OVERALL_SUCCESS=false
fi

# 步骤7: 性能检查（如果存在性能测试）
print_step "性能检查"

if [ -d "tests/performance" ]; then
    echo "运行性能基准测试..."
    if uv run pytest tests/performance/ -v --benchmark-only 2>/dev/null; then
        print_success "性能基准测试通过"
    else
        print_warning "性能基准测试发现问题"
        # 性能测试不作为阻塞性检查
    fi
else
    print_warning "未找到性能测试目录，跳过性能检查"
fi

# 步骤8: 代码复杂度检查
print_step "代码复杂度检查"

if check_command radon; then
    echo "检查代码圈复杂度..."
    if radon cc src --min B; then
        print_success "代码复杂度检查完成"
    else
        print_warning "发现高复杂度代码块"
        OVERALL_SUCCESS=false
    fi
else
    print_warning "radon 未安装，跳过代码复杂度检查"
    print_warning "安装命令: pip install radon"
fi

# 步骤9: 文档检查
print_step "文档检查"

echo "检查文档字符串..."
if check_command pydocstyle; then
    if pydocstyle src/ 2>/dev/null; then
        print_success "文档字符串检查通过"
    else
        print_warning "文档字符串检查发现问题"
        # 文档检查不作为阻塞性检查
    fi
else
    print_warning "pydocstyle 未安装，跳过文档检查"
    print_warning "安装命令: pip install pydocstyle"
fi

# 步骤10: 生成质量报告
print_step "生成质量报告"

if [ -f "scripts/quality_monitor.py" ]; then
    echo "生成质量趋势报告..."
    if python scripts/quality_monitor.py --collect --report --days 7; then
        print_success "质量报告生成完成"
    else
        print_warning "质量报告生成失败"
    fi
else
    print_warning "质量监控脚本不存在，跳过报告生成"
fi

# 计算执行时间
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

# 最终结果
print_step "质量检查总结"

echo "执行时间: ${DURATION} 秒"
echo ""

if [ "$OVERALL_SUCCESS" = true ]; then
    print_success "🎉 所有核心质量检查通过！"
    echo ""
    echo "项目质量状态: 良好"
    echo "建议: 继续保持代码质量标准"
    exit 0
else
    print_error "存在质量问题需要修复"
    echo ""
    echo "项目质量状态: 需要改进"
    echo "建议: 修复上述警告后重新运行检查"
    echo ""
    echo "快速修复命令:"
    echo "  - 代码格式: uv run black src tests && uv run isort src tests"
    echo "  - 类型检查: 修复 MyPy 报告的类型错误"
    echo "  - 安全问题: 修复 bandit 报告的安全问题"
    echo "  - 测试覆盖: 增加测试用例以提高覆盖率"
    exit 1
fi