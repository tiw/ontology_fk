#!/usr/bin/env python3
"""
简化的API文档生成器
基于现有导入生成API参考文档
"""

import inspect
import sys
from pathlib import Path
from typing import Dict, List, Any
from dataclasses import fields, is_dataclass

def generate_api_docs():
    """生成API文档"""
    # 导入所有必要的模块
    sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

    try:
        from ontology_framework import (
            Ontology,
            ObjectType,
            LinkType,
            ActionType,
            ObjectInstance,
            ObjectSet,
            PropertyType,
        )
        from ontology_framework import (
            ObjectSetService,
        )
        # ActionService 需要单独导入
        from ontology_framework.services import ActionService
        from ontology_framework.applications import (
            ObjectView,
            ObjectExplorer,
            Quiver,
        )
        from ontology_framework.permissions import (
            AccessControlList,
            Principal,
            PermissionType,
        )
        from ontology_framework.exceptions import (
            OntologyError,
            ValidationError,
            PermissionError,
        )
        from ontology_framework.logging_config import (
            OntologyLogger,
            LoggingContext,
        )
        from ontology_framework.error_recovery import (
            RetryMechanism,
            CircuitBreaker,
        )
        from ontology_framework.debug_tools import (
            DebugSession,
            PerformanceProfiler,
        )
    except ImportError as e:
        print(f"导入模块失败: {e}")
        return

    # 准备要分析的类
    classes_to_document = [
        # 核心模块
        (Ontology, "核心本体管理器"),
        (ObjectType, "对象类型定义"),
        (LinkType, "链接类型定义"),
        (ActionType, "动作类型定义"),
        (ObjectInstance, "对象实例"),
        (ObjectSet, "对象集合"),
        (PropertyType, "属性类型枚举"),

        # 服务模块
        (ObjectSetService, "对象集合服务"),
        (ActionService, "动作服务"),

        # 应用模块
        (ObjectView, "对象视图"),
        (ObjectExplorer, "对象浏览器"),
        (Quiver, "数据分析工具"),

        # 权限模块
        (AccessControlList, "访问控制列表"),
        (Principal, "主体"),
        (PermissionType, "权限类型"),

        # 异常模块
        (OntologyError, "基础异常类"),
        (ValidationError, "验证错误"),
        (PermissionError, "权限错误"),

        # 日志模块
        (OntologyLogger, "结构化日志器"),
        (LoggingContext, "日志上下文管理"),

        # 错误恢复模块
        (RetryMechanism, "重试机制"),
        (CircuitBreaker, "熔断器"),

        # 调试工具模块
        (DebugSession, "调试会话"),
        (PerformanceProfiler, "性能分析器"),
    ]

    # 生成文档
    output_file = Path(__file__).parent.parent / "doc" / "API_REFERENCE_UPDATED.md"

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("# Ontology Framework API Reference\n\n")
        f.write("本文档提供 Ontology Framework 的完整 API 参考文档。\n\n")
        f.write("## 目录\n\n")

        # 生成目录
        sections = []
        for cls, description in classes_to_document:
            section_name = cls.__name__
            sections.append((section_name, description))

        for i, (section_name, description) in enumerate(sections, 1):
            f.write(f"{i}. [{section_name}](#{section_name.lower().replace(' ', '-')}) - {description}\n")

        f.write("\n---\n\n")

        # 生成每个类的文档
        for cls, description in classes_to_document:
            class_name = cls.__name__
            f.write(f"## {class_name}\n\n")
            f.write(f"{description}\n\n")

            # 类的文档字符串
            if cls.__doc__:
                f.write(f"**说明**: {cls.__doc__}\n\n")

            # 构造函数
            if hasattr(cls, "__init__"):
                try:
                    sig = inspect.signature(cls.__init__)
                    f.write(f"**构造函数**:\n```python\n{class_name}{sig}\n```\n\n")
                except:
                    pass

            # 如果是dataclass，显示字段
            if is_dataclass(cls):
                f.write("**类型**: `@dataclass`\n\n")
                f.write("**字段**:\n\n")
                for field in fields(cls):
                    field_type = field.type.__name__ if hasattr(field.type, "__name__") else str(field.type)
                    default = field.default if field.default != field.default_factory else "factory()"
                    f.write(f"- `{field.name}` ({field_type}): {default}\n")
                f.write("\n")

            # 公共方法
            public_methods = []
            for name, method in inspect.getmembers(cls):
                if (inspect.isfunction(method) or inspect.ismethod(method)) and not name.startswith("_"):
                    public_methods.append((name, method))

            if public_methods:
                f.write("**公共方法**:\n\n")
                for method_name, method in public_methods:
                    try:
                        sig = inspect.signature(method)
                        f.write(f"### `{method_name}`\n\n")
                        f.write(f"```python\n{method_name}{sig}\n```\n\n")

                        # 方法文档
                        if method.__doc__:
                            f.write(f"{method.__doc__}\n\n")

                        # 返回类型
                        annotations = getattr(method, "__annotations__", {})
                        if "return" in annotations:
                            f.write(f"**返回值**: `{annotations['return']}`\n\n")

                        f.write("---\n\n")
                    except:
                        continue

            f.write("---\n\n")

    print(f"API文档已生成: {output_file}")

if __name__ == "__main__":
    generate_api_docs()