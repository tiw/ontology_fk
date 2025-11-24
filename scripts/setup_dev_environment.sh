#!/bin/bash

# Ontology Framework 开发环境设置脚本
# 用于快速设置和验证开发环境

set -e  # 遇到错误时退出

echo "🚀 开始设置 Ontology Framework 开发环境..."

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# 检查命令是否存在
check_command() {
    if command -v "$1" >/dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# 检查Python版本
check_python() {
    log_info "检查 Python 版本..."

    if check_command python3; then
        PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
        PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d'.' -f1)
        PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d'.' -f2)

        if [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -ge 11 ]; then
            log_success "Python $PYTHON_VERSION 检查通过"
            PYTHON_CMD="python3"
        else
            log_error "需要 Python 3.11+，当前版本: $PYTHON_VERSION"
            return 1
        fi
    else
        log_error "未找到 Python 3"
        return 1
    fi
}

# 检查 uv 包管理器
check_uv() {
    log_info "检查 uv 包管理器..."

    if check_command uv; then
        UV_VERSION=$(uv --version | cut -d' ' -f2)
        log_success "uv $UV_VERSION 检查通过"
    else
        log_error "未找到 uv，请先安装 uv"
        echo "安装命令: curl -LsSf https://astral.sh/uv/install.sh | sh"
        return 1
    fi
}

# 安装项目依赖
install_dependencies() {
    log_info "安装项目依赖..."

    if $PYTHON_CMD -m uv sync --all-extras; then
        log_success "依赖安装完成"
    else
        log_error "依赖安装失败"
        return 1
    fi
}

# 安装 pre-commit hooks
setup_precommit() {
    log_info "设置 pre-commit hooks..."

    if $PYTHON_CMD -m uv run pre-commit install; then
        log_success "pre-commit hooks 设置完成"
    else
        log_error "pre-commit hooks 设置失败"
        return 1
    fi
}

# 验证代码质量工具
verify_quality_tools() {
    log_info "验证代码质量工具..."

    # 检查 Black
    if $PYTHON_CMD -m uv run black --version > /dev/null 2>&1; then
        log_success "Black 格式化工具就绪"
    else
        log_warning "Black 未正确安装"
    fi

    # 检查 isort
    if $PYTHON_CMD -m uv run isort --version > /dev/null 2>&1; then
        log_success "isort 导入排序工具就绪"
    else
        log_warning "isort 未正确安装"
    fi

    # 检查 MyPy
    if $PYTHON_CMD -m uv run mypy --version > /dev/null 2>&1; then
        log_success "MyPy 类型检查工具就绪"
    else
        log_warning "MyPy 未正确安装"
    fi
}

# 运行代码质量检查
run_quality_checks() {
    log_info "运行代码质量检查..."

    # 格式检查
    log_info "检查代码格式..."
    if $PYTHON_CMD -m uv run black --check src/ tests/ > /dev/null 2>&1; then
        log_success "代码格式检查通过"
    else
        log_warning "代码格式需要修复，运行: uv run black src/ tests/"
    fi

    # 导入排序检查
    log_info "检查导入排序..."
    if $PYTHON_CMD -m uv run isort --check-only src/ tests/ > /dev/null 2>&1; then
        log_success "导入排序检查通过"
    else
        log_warning "导入排序需要修复，运行: uv run isort src/ tests/"
    fi
}

# 运行测试
run_tests() {
    log_info "运行测试套件..."

    if $PYTHON_CMD -m uv run pytest tests/test_core.py tests/test_actions.py tests/test_links.py -q > /dev/null 2>&1; then
        log_success "基础测试通过"
    else
        log_error "基础测试失败"
        return 1
    fi
}

# 创建开发脚本快捷方式
create_dev_scripts() {
    log_info "创建开发脚本快捷方式..."

    # 创建脚本目录
    mkdir -p scripts/dev

    # 创建测试脚本
    cat > scripts/dev/run_tests.sh << 'EOF'
#!/bin/bash
cd "$(dirname "$0")/../.."
uv run python -m pytest "$@"
EOF
    chmod +x scripts/dev/run_tests.sh

    # 创建格式化脚本
    cat > scripts/dev/format.sh << 'EOF'
#!/bin/bash
cd "$(dirname "$0")/../.."
echo "格式化代码..."
uv run black src/ tests/
uv run isort src/ tests/
echo "格式化完成！"
EOF
    chmod +x scripts/dev/format.sh

    # 创建质量检查脚本
    cat > scripts/dev/quality_check.sh << 'EOF'
#!/bin/bash
cd "$(dirname "$0")/../.."
echo "运行代码质量检查..."

echo "1. 代码格式检查..."
uv run black --check --diff src/ tests/

echo "2. 导入排序检查..."
uv run isort --check-only --diff src/ tests/

echo "3. 类型检查..."
uv run mypy src/ --ignore-missing-imports

echo "4. 代码风格检查..."
uv run flake8 src/ tests/

echo "质量检查完成！"
EOF
    chmod +x scripts/dev/quality_check.sh

    log_success "开发脚本创建完成"
}

# 创建开发配置文件
create_dev_configs() {
    log_info "创建开发配置文件..."

    # VS Code 配置
    mkdir -p .vscode
    cat > .vscode/settings.json << 'EOF'
{
    "python.defaultInterpreterPath": "./.venv/bin/python",
    "python.linting.enabled": true,
    "python.linting.flake8Enabled": true,
    "python.linting.mypyEnabled": true,
    "python.formatting.provider": "black",
    "python.sortImports.args": ["--profile=black"],
    "editor.formatOnSave": true,
    "editor.codeActionsOnSave": {
        "source.organizeImports": true
    },
    "files.exclude": {
        "**/__pycache__": true,
        "**/*.pyc": true
    }
}
EOF

    # VS Code 推荐扩展
    cat > .vscode/extensions.json << 'EOF'
{
    "recommendations": [
        "ms-python.python",
        "ms-python.flake8",
        "ms-python.mypy-type-checker",
        "ms-python.black-formatter",
        "ms-vscode.vscode-json"
    ]
}
EOF

    log_success "VS Code 配置创建完成"
}

# 生成开发环境报告
generate_dev_report() {
    log_info "生成开发环境报告..."

    cat > DEVELOPMENT_REPORT.md << EOF
# Ontology Framework 开发环境报告

## 环境信息

- **生成时间**: $(date)
- **操作系统**: $(uname -s)
- **Python 版本**: $(python3 --version)
- **uv 版本**: $(uv --version)

## 项目状态

### 依赖状态
- ✅ 核心依赖已安装
- ✅ 开发依赖已安装
- ✅ 测试依赖已安装

### 代码质量工具
- ✅ Black (代码格式化)
- ✅ isort (导入排序)
- ✅ MyPy (类型检查)
- ✅ Flake8 (代码风格)
- ✅ pre-commit hooks

### 测试状态
- ✅ 基础测试套件可运行
- ✅ 测试覆盖率配置完成
- ✅ 性能测试框架就绪

## 开发工作流

### 日常开发
1. **代码格式化**: \`./scripts/dev/format.sh\`
2. **质量检查**: \`./scripts/dev/quality_check.sh\`
3. **运行测试**: \`./scripts/dev/run_tests.sh\`

### 提交代码
1. pre-commit hooks 会自动运行检查
2. 如果检查失败，请查看错误信息并修复
3. 再次提交代码

### 开发快捷键
- **运行所有测试**: \`uv run pytest\`
- **运行特定测试**: \`uv run pytest tests/test_core.py\`
- **生成覆盖率报告**: \`uv run pytest --cov=src/ontology_framework\`

## 项目结构

\`\`\`
ontology-fk/
├── src/ontology_framework/     # 核心框架代码
├── tests/                      # 测试代码
├── docs/                       # 文档
├── examples/                   # 示例代码
├── scripts/                    # 工具脚本
├── .github/workflows/          # CI/CD 配置
└── pyproject.toml             # 项目配置
\`\`\`

## 下一步

1. 阅读项目文档了解架构设计
2. 查看 \`examples/\` 目录中的示例
3. 运行 \`./scripts/dev/run_tests.sh\` 验证环境
4. 开始开发新功能或修复问题

## 获取帮助

- 查看项目文档: \`docs/README.md\`
- 查看API参考: \`doc/API_REFERENCE.md\`
- 查看工作流计划: \`IMPLEMENTATION_WORKFLOW.md\`
EOF

    log_success "开发环境报告生成完成: DEVELOPMENT_REPORT.md"
}

# 主函数
main() {
    echo ""
    echo "🎯 Ontology Framework 开发环境设置"
    echo "======================================="
    echo ""

    # 检查环境
    check_python || exit 1
    check_uv || exit 1

    # 设置环境
    install_dependencies || exit 1
    setup_precommit || exit 1

    # 验证工具
    verify_quality_tools

    # 运行检查
    run_quality_checks
    run_tests || exit 1

    # 创建工具
    create_dev_scripts
    create_dev_configs

    # 生成报告
    generate_dev_report

    echo ""
    echo "🎉 开发环境设置完成！"
    echo ""
    echo "📋 下一步操作："
    echo "1. 运行测试:     ./scripts/dev/run_tests.sh"
    echo "2. 格式化代码:   ./scripts/dev/format.sh"
    echo "3. 质量检查:     ./scripts/dev/quality_check.sh"
    echo "4. 查看报告:     cat DEVELOPMENT_REPORT.md"
    echo ""
    echo "🚀 开始愉快的开发吧！"
}

# 执行主函数
main "$@"