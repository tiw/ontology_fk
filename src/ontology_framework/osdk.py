"""
轻量级 Ontology SDK，提供类型安全的对象/函数访问能力。
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, Optional

from .core import (
    Function,
    ObjectInstance,
    ObjectSet,
    ObjectSetTypeSpec,
    ObjectType,
    ObjectTypeSpec,
    Ontology,
    PrimitiveType,
    PropertyType,
    TypeSpec,
)
from .exceptions import NotFoundError, ValidationError


class OntologySDK:
    """
    针对 Agent/应用开发者的安全访问入口。

    - 自动校验对象类型是否存在
    - 根据函数签名进行参数类型检查
    - 支持以 PK 或 ObjectInstance 方式传入对象引用
    """

    def __init__(self, ontology: Ontology):
        self._ontology = ontology

    # ---- Object helpers -------------------------------------------------

    def get_object_type(self, api_name: str) -> ObjectType:
        obj_type = self._ontology.get_object_type(api_name)
        if not obj_type:
            raise NotFoundError(
                f"ObjectType '{api_name}' not found", resource_type="object_type", resource_id=api_name
            )
        return obj_type

    def get_object(self, object_type_api_name: str, primary_key: Any) -> ObjectInstance:
        self.get_object_type(object_type_api_name)
        instance = self._ontology.get_object(object_type_api_name, primary_key)
        if not instance:
            raise NotFoundError(
                f"{object_type_api_name}:{primary_key} not found",
                resource_type=object_type_api_name,
                resource_id=str(primary_key),
            )
        return instance

    def list_objects(self, object_type_api_name: str) -> Iterable[ObjectInstance]:
        self.get_object_type(object_type_api_name)
        return self._ontology.get_objects_of_type(object_type_api_name)

    # ---- Function helpers -----------------------------------------------

    def get_function(self, api_name: str) -> Function:
        fn = self._ontology.get_function(api_name)
        if not fn:
            raise NotFoundError(
                f"Function '{api_name}' not found", resource_type="function", resource_id=api_name
            )
        return fn

    def execute_function(self, function_api_name: str, **kwargs) -> Any:
        fn = self.get_function(function_api_name)
        prepared_args = self._prepare_arguments(fn, kwargs)
        return self._ontology.execute_function(function_api_name, **prepared_args)

    # ---- Schema helpers -------------------------------------------------

    def describe_schema(self) -> Dict[str, Any]:
        """导出当前 Ontology 的结构，供 Agent 读取。"""
        return self._ontology.export_schema_for_llm()

    # ---- Internal -------------------------------------------------------

    def _prepare_arguments(self, function: Function, supplied: Dict[str, Any]) -> Dict[str, Any]:
        prepared: Dict[str, Any] = {}
        for name, arg_def in function.inputs.items():
            if name not in supplied:
                if arg_def.required:
                    raise ValidationError(
                        f"Missing required argument '{name}' for function {function.api_name}",
                        field_name=name,
                    )
                continue
            prepared[name] = self._coerce_argument(arg_def.type, supplied[name], name)

        extra = set(supplied.keys()) - set(function.inputs.keys())
        if extra:
            raise ValidationError(
                f"Unknown arguments for function {function.api_name}: {', '.join(sorted(extra))}"
            )
        return prepared

    def _coerce_argument(self, type_spec: TypeSpec, value: Any, arg_name: str) -> Any:
        if isinstance(type_spec, PrimitiveType):
            return self._coerce_primitive(type_spec.type, value, arg_name)

        if isinstance(type_spec, ObjectTypeSpec):
            return self._materialize_object(type_spec.object_type_api_name, value, arg_name)

        if isinstance(type_spec, ObjectSetTypeSpec):
            if isinstance(value, ObjectSet):
                if value.object_type.api_name != type_spec.object_type_api_name:
                    raise ValidationError(
                        f"Argument '{arg_name}' expects ObjectSet<{type_spec.object_type_api_name}>",
                        field_name=arg_name,
                        expected_type=type_spec.object_type_api_name,
                    )
                return value
            raise ValidationError(
                f"Argument '{arg_name}' expects ObjectSet value",
                field_name=arg_name,
                expected_type="ObjectSet",
            )

        # 未知类型直接返回
        return value

    @staticmethod
    def _coerce_primitive(expected_type: PropertyType, value: Any, arg_name: str) -> Any:
        if value is None:
            return None

        if expected_type == PropertyType.STRING:
            return str(value)

        if expected_type == PropertyType.INTEGER:
            try:
                return int(value)
            except (TypeError, ValueError) as exc:
                raise ValidationError(
                    f"Argument '{arg_name}' expects integer", field_name=arg_name, expected_type="int"
                ) from exc

        if expected_type == PropertyType.BOOLEAN:
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                normalized = value.strip().lower()
                if normalized in {"true", "1", "yes", "y"}:
                    return True
                if normalized in {"false", "0", "no", "n"}:
                    return False
            return bool(value)

        if expected_type in {PropertyType.DATE, PropertyType.TIMESTAMP}:
            try:
                return float(value)
            except (TypeError, ValueError) as exc:
                raise ValidationError(
                    f"Argument '{arg_name}' expects timestamp-like value",
                    field_name=arg_name,
                    expected_type="timestamp",
                ) from exc

        return value

    def _materialize_object(
        self, object_type_api_name: str, raw_value: Any, arg_name: str
    ) -> ObjectInstance:
        if isinstance(raw_value, ObjectInstance):
            if raw_value.object_type_api_name != object_type_api_name:
                raise ValidationError(
                    f"Argument '{arg_name}' expects {object_type_api_name}, "
                    f"got {raw_value.object_type_api_name}",
                    field_name=arg_name,
                    expected_type=object_type_api_name,
                )
            return raw_value

        lookup_key: Optional[Any] = None
        if isinstance(raw_value, dict):
            lookup_key = raw_value.get("primary_key") or raw_value.get("id")
        elif raw_value is not None:
            lookup_key = raw_value

        if lookup_key is None:
            raise ValidationError(
                f"Argument '{arg_name}' needs primary_key for {object_type_api_name}",
                field_name=arg_name,
                expected_type=object_type_api_name,
            )

        instance = self._ontology.get_object(object_type_api_name, lookup_key)
        if not instance:
            raise NotFoundError(
                f"{object_type_api_name}:{lookup_key} not found",
                resource_type=object_type_api_name,
                resource_id=str(lookup_key),
            )
        return instance

