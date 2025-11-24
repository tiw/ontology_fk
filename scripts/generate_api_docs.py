#!/usr/bin/env python3
"""
自动生成API文档脚本
基于代码注释和类型注解生成完整的API参考文档
"""

import ast
import inspect
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import fields, is_dataclass
import importlib.util

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

def import_module_from_file(file_path: Path):
    """从文件路径导入模块"""
    try:
        # 尝试直接导入
        module_name = f"ontology_framework.{file_path.stem}"
        if module_name in sys.modules:
            return sys.modules[module_name]

        spec = importlib.util.spec_from_file_location(module_name, file_path)
        module = importlib.util.module_from_spec(spec)

        # 设置模块的__package__属性
        module.__package__ = "ontology_framework"

        spec.loader.exec_module(module)
        return module
    except Exception as e:
        print(f"无法导入模块 {file_path}: {e}")
        return None

def extract_class_info(cls, module_name: str) -> Dict[str, Any]:
    """提取类的信息"""
    info = {
        "name": cls.__name__,
        "module": module_name,
        "docstring": inspect.getdoc(cls),
        "bases": [base.__name__ for base in cls.__bases__],
        "methods": {},
        "properties": {},
        "is_dataclass": is_dataclass(cls),
        "signature": str(inspect.signature(cls.__init__)) if hasattr(cls, "__init__") else None
    }

    # 提取方法
    for name, method in inspect.getmembers(cls, inspect.isfunction):
        if not name.startswith("_"):
            info["methods"][name] = {
                "signature": str(inspect.signature(method)),
                "docstring": inspect.getdoc(method),
                "return_type": getattr(method, "__annotations__", {}).get("return")
            }

    # 提取属性
    for name, value in inspect.getmembers(cls):
        if not name.startswith("_") and not inspect.isfunction(value) and not inspect.ismethod(value):
            if isinstance(value, property):
                info["properties"][name] = {
                    "type": "property",
                    "docstring": inspect.getdoc(value) if value.fget else None
                }
            else:
                info["properties"][name] = {
                    "type": type(value).__name__,
                    "value": str(value)[:100] if len(str(value)) > 100 else str(value)
                }

    # 如果是dataclass，提取字段信息
    if info["is_dataclass"]:
        field_info = {}
        for field in fields(cls):
            field_info[field.name] = {
                "type": field.type.__name__ if hasattr(field.type, "__name__") else str(field.type),
                "default": field.default if field.default != field.default_factory else "factory",
                "init": field.init,
                "repr": field.repr,
                "compare": field.compare,
                "hash": field.hash,
                "metadata": field.metadata
            }
        info["dataclass_fields"] = field_info

    return info

def extract_function_info(func, module_name: str) -> Dict[str, Any]:
    """提取函数信息"""
    info = {
        "name": func.__name__,
        "module": module_name,
        "docstring": inspect.getdoc(func),
        "signature": str(inspect.signature(func)),
        "return_type": getattr(func, "__annotations__", {}).get("return"),
        "parameters": {}
    }

    # 提取参数信息
    sig = inspect.signature(func)
    for param_name, param in sig.parameters.items():
        param_info = {
            "type": param.annotation.__name__ if param.annotation != inspect.Parameter.empty else None,
            "default": str(param.default) if param.default != inspect.Parameter.empty else None,
            "kind": param.kind.name
        }
        info["parameters"][param_name] = param_info

    return info

def extract_enum_info(cls, module_name: str) -> Dict[str, Any]:
    """提取枚举类信息"""
    info = {
        "name": cls.__name__,
        "module": module_name,
        "docstring": inspect.getdoc(cls),
        "type": "enum",
        "values": {}
    }

    # 提取枚举值
    for name, value in cls.__members__.items():
        if not name.startswith("_"):
            info["values"][name] = {
                "value": value.value,
                "name": value.name
            }

    return info

def analyze_source_files(source_dir: Path) -> Dict[str, Any]:
    """分析源代码文件"""
    api_info = {
        "modules": {},
        "classes": {},
        "functions": {},
        "enums": {},
        "constants": {}
    }

    for py_file in source_dir.glob("*.py"):
        if py_file.name == "__init__.py":
            continue

        module_name = f"ontology_framework.{py_file.stem}"

        try:
            module = import_module_from_file(py_file)

            # 提取模块信息
            api_info["modules"][py_file.stem] = {
                "name": module_name,
                "docstring": module.__doc__,
                "file": str(py_file)
            }

            # 提取类信息
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if obj.__module__ == module_name:
                    if hasattr(obj, "__members__") and all(hasattr(v, "value") and hasattr(v, "name") for v in obj.__members__.values()):
                        # 可能是枚举
                        try:
                            if hasattr(obj, "_value2member_map_"):
                                api_info["enums"][f"{module_name}.{name}"] = extract_enum_info(obj, module_name)
                        except:
                            pass

                    api_info["classes"][f"{module_name}.{name}"] = extract_class_info(obj, module_name)

            # 提取函数信息
            for name, obj in inspect.getmembers(module, inspect.isfunction):
                if obj.__module__ == module_name:
                    api_info["functions"][f"{module_name}.{name}"] = extract_function_info(obj, module_name)

            # 提取常量
            for name in dir(module):
                if not name.startswith("_"):
                    obj = getattr(module, name)
                    if not inspect.isfunction(obj) and not inspect.isclass(obj) and not inspect.ismodule(obj):
                        api_info["constants"][f"{module_name}.{name}"] = {
                            "type": type(obj).__name__,
                            "value": str(obj)[:100] if len(str(obj)) > 100 else str(obj)
                        }

        except Exception as e:
            print(f"Error processing {py_file}: {e}")

    return api_info

def generate_markdown_docs(api_info: Dict[str, Any], output_file: Path):
    """生成Markdown格式的API文档"""

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("# Ontology Framework API Reference\n\n")
        f.write("本文档提供 Ontology Framework 的完整 API 参考，基于源代码自动生成。\n\n")

        f.write("## 目录\n\n")
        f.write("- [核心模块 (core)](#core-module)\n")
        f.write("- [函数模块 (functions)](#functions-module)\n")
        f.write("- [权限模块 (permissions)](#permissions-module)\n")
        f.write("- [服务模块 (services)](#services-module)\n")
        f.write("- [应用模块 (applications)](#applications-module)\n")
        f.write("- [异常模块 (exceptions)](#exceptions-module)\n")
        f.write("- [日志模块 (logging_config)](#logging_config-module)\n")
        f.write("- [错误恢复模块 (error_recovery)](#error_recovery-module)\n")
        f.write("- [调试工具模块 (debug_tools)](#debug_tools-module)\n\n")

        # 按模块分组
        modules = {}
        for full_name, class_info in api_info["classes"].items():
            module_name = full_name.split('.')[1]
            if module_name not in modules:
                modules[module_name] = {"classes": {}, "functions": {}, "enums": {}, "constants": {}}
            modules[module_name]["classes"][full_name] = class_info

        for full_name, func_info in api_info["functions"].items():
            module_name = full_name.split('.')[1]
            if module_name not in modules:
                modules[module_name] = {"classes": {}, "functions": {}, "enums": {}, "constants": {}}
            modules[module_name]["functions"][full_name] = func_info

        for full_name, enum_info in api_info["enums"].items():
            module_name = full_name.split('.')[1]
            if module_name not in modules:
                modules[module_name] = {"classes": {}, "functions": {}, "enums": {}, "constants": {}}
            modules[module_name]["enums"][full_name] = enum_info

        # 生成每个模块的文档
        for module_name, module_data in sorted(modules.items()):
            f.write(f"## {module_name.title()} Module\n\n")

            if module_name in api_info["modules"]:
                module_info = api_info["modules"][module_name]
                f.write(f"**文件**: `{module_info['file']}`\n\n")
                if module_info.get("docstring"):
                    f.write(f"{module_info['docstring']}\n\n")

            # 生成类的文档
            for full_name, class_info in sorted(module_data.get("classes", {}).items()):
                class_name = full_name.split('.')[-1]
                f.write(f"### `{class_name}`\n\n")

                if class_info.get("docstring"):
                    f.write(f"{class_info['docstring']}\n\n")

                # 继承关系
                if class_info.get("bases"):
                    f.write("**继承自**: {', '.join(class_info['bases'])}\n\n")

                # dataclass信息
                if class_info.get("is_dataclass"):
                    f.write("**类型**: `@dataclass`\n\n")

                # 构造函数签名
                if class_info.get("signature"):
                    f.write(f"**构造函数**: `class {class_name}{class_info['signature']}`\n\n")

                # dataclass字段
                if class_info.get("dataclass_fields"):
                    f.write("**字段**:\n\n")
                    for field_name, field_info in class_info["dataclass_fields"].items():
                        f.write(f"- `{field_name}` (`{field_info['type']}`)")
                        if field_info.get("default") and field_info["default"] != "factory":
                            f.write(f" = `{field_info['default']}`")
                        f.write("\n")
                    f.write("\n")

                # 属性
                if class_info.get("properties"):
                    f.write("**属性**:\n\n")
                    for prop_name, prop_info in class_info["properties"].items():
                        f.write(f"- `{prop_name}`")
                        if prop_info.get("docstring"):
                            f.write(f": {prop_info['docstring']}")
                        f.write("\n")
                    f.write("\n")

                # 方法
                if class_info.get("methods"):
                    f.write("**方法**:\n\n")
                    for method_name, method_info in class_info["methods"].items():
                        f.write(f"#### `{class_name}.{method_name}`\n\n")
                        f.write(f"```python\n{method_name}{method_info['signature']}\n```\n\n")
                        if method_info.get("docstring"):
                            f.write(f"{method_info['docstring']}\n\n")
                        if method_info.get("return_type"):
                            f.write(f"**返回类型**: `{method_info['return_type']}`\n\n")

                f.write("---\n\n")

            # 生成函数的文档
            for full_name, func_info in sorted(module_data.get("functions", {}).items()):
                func_name = full_name.split('.')[-1]
                f.write(f"### `{func_name}`\n\n")

                if func_info.get("docstring"):
                    f.write(f"{func_info['docstring']}\n\n")

                f.write(f"```python\n{func_name}{func_info['signature']}\n```\n\n")

                # 参数
                if func_info.get("parameters"):
                    f.write("**参数**:\n\n")
                    for param_name, param_info in func_info["parameters"].items():
                        f.write(f"- `{param_name}`")
                        if param_info.get("type"):
                            f.write(f" (`{param_info['type']}`)")
                        if param_info.get("default"):
                            f.write(f" = `{param_info['default']}`")
                        f.write("\n")
                    f.write("\n")

                if func_info.get("return_type"):
                    f.write(f"**返回值**: `{func_info['return_type']}`\n\n")

                f.write("---\n\n")

            # 生成枚举的文档
            for full_name, enum_info in sorted(module_data.get("enums", {}).items()):
                enum_name = full_name.split('.')[-1]
                f.write(f"### `{enum_name}`\n\n")

                if enum_info.get("docstring"):
                    f.write(f"{enum_info['docstring']}\n\n")

                f.write("**类型**: `enum`\n\n")

                if enum_info.get("values"):
                    f.write("**枚举值**:\n\n")
                    for value_name, value_info in enum_info["values"].items():
                        f.write(f"- `{value_name}` = `{value_info['value']}`\n")
                    f.write("\n")

                f.write("---\n\n")

def main():
    """主函数"""
    source_dir = project_root / "src" / "ontology_framework"
    output_file = project_root / "doc" / "API_REFERENCE_COMPLETE.md"

    print("正在分析源代码...")
    api_info = analyze_source_files(source_dir)

    print("正在生成API文档...")
    generate_markdown_docs(api_info, output_file)

    print(f"API文档已生成: {output_file}")
    print(f"发现模块: {len(api_info['modules'])}")
    print(f"发现类: {len(api_info['classes'])}")
    print(f"发现函数: {len(api_info['functions'])}")
    print(f"发现枚举: {len(api_info['enums'])}")

if __name__ == "__main__":
    main()