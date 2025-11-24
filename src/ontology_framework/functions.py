from typing import Any, Callable, Dict, Optional, Type

from .core import (
    Function,
    FunctionArgument,
    ObjectSetTypeSpec,
    ObjectTypeSpec,
    Ontology,
    PrimitiveType,
    PropertyType,
    TypeSpec,
)


# Helper to map python types to TypeSpec
def _map_python_type(py_type: Type) -> TypeSpec:
    if py_type == str:
        return PrimitiveType(PropertyType.STRING)
    elif py_type == int:
        return PrimitiveType(PropertyType.INTEGER)
    elif py_type == bool:
        return PrimitiveType(PropertyType.BOOLEAN)
    # For Objects and ObjectSets, we might need custom annotations or hints
    # For now, default to String if unknown, or let user specify manually in decorator
    return PrimitiveType(PropertyType.STRING)


class FunctionRegistry:
    def __init__(self):
        self._pending_functions: Dict[str, Function] = {}

    def register(self, api_name: str, **kwargs):
        def decorator(func: Callable):
            # Create Function definition
            # We can inspect func signature here to infer inputs if not provided
            # For this prototype, we rely on manual definition in kwargs or simple defaults

            f = Function(
                api_name=api_name,
                display_name=kwargs.get("display_name", api_name),
                description=kwargs.get("description"),
                logic=func,
            )

            # Add inputs if specified
            inputs = kwargs.get("inputs", {})
            for name, type_spec in inputs.items():
                f.add_input(name, type_spec)

            self._pending_functions[api_name] = f
            return func

        return decorator

    def register_all_to_ontology(self, ontology: Ontology):
        for f in self._pending_functions.values():
            ontology.register_function(f)

    def clear(self):
        """清除所有待注册的函数"""
        self._pending_functions.clear()

    def get_pending_functions(self) -> Dict[str, Function]:
        """获取所有待注册的函数"""
        return self._pending_functions.copy()

    def has_function(self, api_name: str) -> bool:
        """检查是否存在指定API名称的函数"""
        return api_name in self._pending_functions

    def remove_function(self, api_name: str) -> bool:
        """移除指定API名称的函数"""
        if api_name in self._pending_functions:
            del self._pending_functions[api_name]
            return True
        return False


# Global registry
registry = FunctionRegistry()


def ontology_function(api_name: str, **kwargs):
    return registry.register(api_name, **kwargs)
