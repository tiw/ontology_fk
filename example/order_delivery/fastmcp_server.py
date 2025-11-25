from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from threading import RLock
from textwrap import dedent
from typing import Any, Iterable, Literal, Mapping, Optional

from fastmcp import FastMCP

from ontology_framework.core import (
    FunctionArgument,
    LinkType,
    ObjectInstance,
    ObjectSet,
    ObjectSetTypeSpec,
    ObjectType,
    ObjectTypeSpec,
    Ontology,
    PropertyType,
)
from ontology_framework.permissions import Principal
from ontology_framework.services import ActionService

from .schema import setup_ontology


INSTRUCTIONS = dedent(
    """
    你正在访问 “Ontology FastMCP Server”。它已经预载了订单履约（Order Delivery）本体，
    并提供了一组可调用的工具，以便通过 MCP 直接：
      • 查询对象、链接与派生属性
      • 执行动作（Action），如创建订单、推进节点
      • 调用注册函数（例如计算实际时长、TGAP）

    📚 结构化资料：
      • resource://ontology/schema 返回 JSON Schema，描述对象、属性、动作。
      • resource://ontology/guide 返回使用说明与样例调用建议。

    ✅ 常见操作建议：
      1. 先调用 list_object_types / list_actions 获取能力目录。
      2. 使用 list_objects / get_object 查看实体当前状态。
      3. 若要更新状态，先检查动作需要的参数，再通过 execute_action 调用。
      4. 调用 invoke_function 可在任意对象上计算 derived 指标。

    请结合资源里的结构信息，合理规划调用顺序；工具会返回严格的 JSON，方便后续推理。
    """
).strip()

server = FastMCP(
    name="ontology-fkmcp",
    instructions=INSTRUCTIONS,
    version="0.1.0",
    website_url="https://github.com/ting/ontology_fk",
)

ONTOLOGY_LOCK = RLock()


@dataclass(frozen=True)
class MerchantSeed:
    merchant_id: str
    name: str
    address: str


@dataclass(frozen=True)
class RiderSeed:
    rider_id: str
    name: str
    phone: str


@dataclass(frozen=True)
class OrderSeed:
    order_id: str
    user_id: str
    merchant_id: str
    rider_id: str
    description: str
    user_expected_t_min: int
    timeline_min: Mapping[str, float]


BASE_TS = 1_700_000_000.0


MERCHANTS: tuple[MerchantSeed, ...] = (
    MerchantSeed("merchantA", "Pizza Hub", "123 Main St"),
    MerchantSeed("merchantB", "Sushi Express", "456 River Rd"),
)

RIDERS: tuple[RiderSeed, ...] = (
    RiderSeed("rider1", "John Doe", "555-1001"),
    RiderSeed("rider2", "Amy Chen", "555-1002"),
    RiderSeed("rider3", "Luis García", "555-1003"),
)

ORDER_SCENARIOS: tuple[OrderSeed, ...] = (
    OrderSeed(
        order_id="ord_fast",
        user_id="user_001",
        merchant_id="merchantA",
        rider_id="rider2",
        description="Fast lane pizza combo",
        user_expected_t_min=30,
        timeline_min={
            "create": 0,
            "accept": 1,
            "call_rider": 2,
            "merchant_out": 10,
            "rider_arrive": 12,
            "pickup": 13,
            "deliver": 20,
        },
    ),
    OrderSeed(
        order_id="ord_slow",
        user_id="user_002",
        merchant_id="merchantA",
        rider_id="rider1",
        description="Slow delivery sample (late)",
        user_expected_t_min=30,
        timeline_min={
            "create": 0,
            "accept": 5,
            "call_rider": 10,
            "merchant_out": 30,
            "rider_arrive": 20,
            "pickup": 31,
            "deliver": 40,
        },
    ),
    OrderSeed(
        order_id="ord_rider_waits",
        user_id="user_003",
        merchant_id="merchantB",
        rider_id="rider3",
        description="Rider waits for merchant",
        user_expected_t_min=45,
        timeline_min={
            "create": 0,
            "accept": 1,
            "call_rider": 2,
            "rider_arrive": 10,
            "merchant_out": 20,
            "pickup": 21,
            "deliver": 30,
        },
    ),
)


def _ts(offset_min: float) -> float:
    return BASE_TS + offset_min * 60.0


def _seed_demo_data(ontology: Ontology) -> None:
    for merchant in MERCHANTS:
        ontology.add_object(
            ObjectInstance(
                "Merchant",
                merchant.merchant_id,
                {
                    "merchant_id": merchant.merchant_id,
                    "name": merchant.name,
                    "address": merchant.address,
                },
            )
        )

    for rider in RIDERS:
        ontology.add_object(
            ObjectInstance(
                "Rider",
                rider.rider_id,
                {
                    "rider_id": rider.rider_id,
                    "name": rider.name,
                    "phone": rider.phone,
                },
            )
        )

    for scenario in ORDER_SCENARIOS:
        timeline = {key: _ts(value) for key, value in scenario.timeline_min.items()}
        props = {
            "order_id": scenario.order_id,
            "user_id": scenario.user_id,
            "merchant_id": scenario.merchant_id,
            "rider_id": scenario.rider_id,
            "status": "COMPLETED",
            "items": scenario.description,
            "user_expected_t_min": scenario.user_expected_t_min,
            "ts_created": timeline["create"],
            "ts_merchant_accepted": timeline.get("accept"),
            "ts_rider_called": timeline.get("call_rider"),
            "ts_merchant_out": timeline.get("merchant_out"),
            "ts_rider_arrived_store": timeline.get("rider_arrive"),
            "ts_rider_picked": timeline.get("pickup"),
            "ts_delivered": timeline.get("deliver"),
        }
        ontology.add_object(ObjectInstance("Order", scenario.order_id, props))
        ontology.create_link("OrderHasMerchant", scenario.order_id, scenario.merchant_id)
        ontology.create_link("OrderHasRider", scenario.order_id, scenario.rider_id)


def _build_ontology() -> Ontology:
    ontology = Ontology()
    setup_ontology(ontology)
    _seed_demo_data(ontology)
    return ontology


ONTOLOGY = _build_ontology()
ACTION_SERVICE = ActionService(ONTOLOGY)
DEFAULT_PRINCIPAL = Principal(id="mcp_service", attributes=["system"])


def _load_json(payload: Optional[str]) -> dict[str, Any]:
    if payload is None or payload.strip() == "":
        return {}
    data = json.loads(payload)
    if not isinstance(data, dict):
        raise ValueError("JSON 内容必须是对象（key-value）")
    return data


def _serialize_object(
    obj: ObjectInstance,
    *,
    include_derived: bool,
    include_runtime_metadata: bool = False,
) -> dict[str, Any]:
    serialized: dict[str, Any] = {
        "object_type": obj.object_type_api_name,
        "primary_key": obj.primary_key_value,
        "properties": dict(obj.property_values),
    }
    if include_derived:
        ontology = obj._ontology or ONTOLOGY
        obj_type = ontology.get_object_type(obj.object_type_api_name)
        derived: dict[str, Any] = {}
        if obj_type:
            for prop in obj_type.derived_properties:
                derived[prop] = obj.get(prop)
        serialized["derived_properties"] = derived
    if include_runtime_metadata and obj.runtime_metadata:
        serialized["runtime_metadata"] = dict(obj.runtime_metadata)
    return serialized


def _match_filters(obj: ObjectInstance, filters: dict[str, Any]) -> bool:
    if not filters:
        return True
    for key, expected in filters.items():
        if key.startswith("derived."):
            prop_name = key.split(".", 1)[1]
            actual = obj.get(prop_name)
        else:
            actual = obj.property_values.get(key)
        if isinstance(expected, list):
            if actual not in expected:
                return False
        else:
            if actual != expected:
                return False
    return True


def _coerce_scalar(expected_type: PropertyType, raw: Any) -> Any:
    if raw is None:
        return None
    if expected_type == PropertyType.STRING:
        return str(raw)
    if expected_type == PropertyType.INTEGER:
        return int(raw)
    if expected_type == PropertyType.BOOLEAN:
        if isinstance(raw, bool):
            return raw
        if isinstance(raw, str):
            normalized = raw.strip().lower()
            if normalized in {"true", "1", "yes", "y"}:
                return True
            if normalized in {"false", "0", "no", "n"}:
                return False
        return bool(raw)
    if expected_type == PropertyType.TIMESTAMP:
        return float(raw)
    return raw


def _prepare_action_parameters(
    action_api_name: str, raw_json: Optional[str]
) -> dict[str, Any]:
    payload = _load_json(raw_json)
    action_type = ONTOLOGY.get_action_type(action_api_name)
    if not action_type:
        raise ValueError(f"未知的 Action：{action_api_name}")
    parsed: dict[str, Any] = {}
    for name, param in action_type.parameters.items():
        if name not in payload:
            if param.required:
                raise ValueError(f"缺少必填参数：{name}")
            continue
        parsed[name] = _coerce_scalar(param.data_type, payload[name])
    for supplied in payload:
        if supplied not in action_type.parameters:
            raise ValueError(f"参数 {supplied} 未在 {action_api_name} 中定义")
    return parsed


def _prepare_function_arguments(
    function_api_name: str, raw_json: Optional[str]
) -> dict[str, Any]:
    payload = _load_json(raw_json)
    function = ONTOLOGY.get_function(function_api_name)
    if not function:
        raise ValueError(f"未知的函数：{function_api_name}")
    prepared: dict[str, Any] = {}
    for name, arg in function.inputs.items():
        if name not in payload:
            if arg.required:
                raise ValueError(f"缺少必填函数参数：{name}")
            continue
        prepared[name] = _materialize_function_argument(arg, payload[name])
    return prepared


def _materialize_function_argument(
    arg_def: FunctionArgument, raw_value: Any
) -> Any:
    type_spec = arg_def.type
    if isinstance(type_spec, ObjectTypeSpec):
        if not isinstance(raw_value, dict):
            raise ValueError(
                f"参数 {arg_def.name} 需要 object_type / primary_key 结构"
            )
        object_type = raw_value.get("object_type") or raw_value.get("type")
        primary_key = raw_value.get("primary_key") or raw_value.get("id")
        if not object_type or primary_key is None:
            raise ValueError(
                f"参数 {arg_def.name} 缺少 object_type 或 primary_key 字段"
            )
        obj = ONTOLOGY.get_object(object_type, primary_key)
        if obj is None:
            raise ValueError(
                f"未找到对象 {object_type}:{primary_key}（函数 {arg_def.name}）"
            )
        return obj
    if isinstance(type_spec, ObjectSetTypeSpec):
        raise ValueError("暂不支持 ObjectSet 类型的函数参数，请按需扩展")
    return raw_value


def _object_snapshots(
    obj_type_names: Iterable[str], params: Mapping[str, Any]
) -> dict[str, Any]:
    snapshots: dict[str, Any] = {}
    for type_name in obj_type_names:
        obj_type = ONTOLOGY.get_object_type(type_name)
        if not obj_type or not obj_type.primary_key:
            continue
        pk_param = obj_type.primary_key
        pk_value = params.get(pk_param)
        if pk_value is None:
            continue
        obj = ONTOLOGY.get_object(type_name, pk_value)
        if obj:
            snapshots[type_name] = _serialize_object(obj, include_derived=True)
    return snapshots


def _list_schema_entries(collection: Mapping[str, ObjectType]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for obj_type in collection.values():
        entries.append(
            {
                "api_name": obj_type.api_name,
                "display_name": obj_type.display_name,
                "description": obj_type.description,
                "primary_key": obj_type.primary_key,
                "properties": [
                    {
                        "name": prop.name,
                        "type": prop.type.value,
                        "description": prop.description,
                    }
                    for prop in obj_type.properties.values()
                ],
                "derived_properties": list(obj_type.derived_properties.keys()),
            }
        )
    return entries


@server.tool(name="list_object_types", description="列出所有对象类型及属性")
def list_object_types() -> list[dict[str, Any]]:
    with ONTOLOGY_LOCK:
        return _list_schema_entries(ONTOLOGY.object_types)


@server.tool(name="list_link_types", description="列出对象间的链接定义")
def list_link_types() -> list[dict[str, Any]]:
    with ONTOLOGY_LOCK:
        return [
            {
                "api_name": link.api_name,
                "display_name": link.display_name,
                "source": link.source_object_type,
                "target": link.target_object_type,
                "cardinality": link.cardinality,
                "description": link.description,
            }
            for link in ONTOLOGY.link_types.values()
        ]


@server.tool(name="list_actions", description="查看可执行动作及参数")
def list_actions() -> list[dict[str, Any]]:
    with ONTOLOGY_LOCK:
        entries: list[dict[str, Any]] = []
        for action in ONTOLOGY.action_types.values():
            entries.append(
                {
                    "api_name": action.api_name,
                    "display_name": action.display_name,
                    "description": action.description,
                    "target_object_types": action.target_object_types,
                    "parameters": [
                        {
                            "name": param.name,
                            "type": param.data_type.value,
                            "required": param.required,
                            "description": param.description,
                        }
                        for param in action.parameters.values()
                    ],
                }
            )
        return entries


@server.tool(name="list_functions", description="查看注册函数及输入")
def list_functions() -> list[dict[str, Any]]:
    with ONTOLOGY_LOCK:
        result: list[dict[str, Any]] = []
        for function in ONTOLOGY.functions.values():
            result.append(
                {
                    "api_name": function.api_name,
                    "display_name": function.display_name,
                    "description": function.description,
                    "inputs": [
                        {
                            "name": arg.name,
                            "type": type(arg.type).__name__,
                            "required": arg.required,
                            "description": arg.description,
                        }
                        for arg in function.inputs.values()
                    ],
                }
            )
        return result


@server.tool(name="get_object", description="获取指定对象的当前状态")
def get_object(
    object_type: str, primary_key: str, include_derived: bool = True
) -> dict[str, Any]:
    with ONTOLOGY_LOCK:
        obj = ONTOLOGY.get_object(object_type, primary_key)
        if obj is None:
            raise ValueError(f"未找到 {object_type}:{primary_key}")
        return _serialize_object(
            obj,
            include_derived=include_derived,
            include_runtime_metadata=True,
        )


@server.tool(
    name="list_objects",
    description="按条件检索对象，可通过 filters_json 精确匹配属性",
)
def list_objects(
    object_type: str,
    filters_json: Optional[str] = None,
    limit: int = 20,
    include_derived: bool = False,
) -> list[dict[str, Any]]:
    filters = _load_json(filters_json)
    limit = max(1, min(limit, 100))
    with ONTOLOGY_LOCK:
        obj_type = ONTOLOGY.get_object_type(object_type)
        if not obj_type:
            raise ValueError(f"未知对象类型：{object_type}")
        instances = ONTOLOGY.get_objects_of_type(object_type)
        matched: list[dict[str, Any]] = []
        for instance in instances:
            if _match_filters(instance, filters):
                matched.append(
                    _serialize_object(
                        instance,
                        include_derived=include_derived,
                        include_runtime_metadata=True,
                    )
                )
            if len(matched) >= limit:
                break
        return matched


@server.tool(name="get_related_objects", description="沿链接关系查找关联实体并执行治理逻辑")
def get_related_objects(
    object_type: str,
    primary_key: str,
    link_type_api_name: str,
    direction: Literal["auto", "forward", "reverse"] = "auto",
    filters_json: Optional[str] = None,
    limit: int = 20,
) -> dict[str, Any]:
    raw_filters = _load_json(filters_json)
    normalized_filters = {
        (key.split(".", 1)[1] if key.startswith("derived.") else key): value
        for key, value in raw_filters.items()
    }
    limit = max(1, min(limit, 100))
    with ONTOLOGY_LOCK:
        obj_type = ONTOLOGY.get_object_type(object_type)
        if not obj_type:
            raise ValueError(f"未知对象类型：{object_type}")
        anchor = ONTOLOGY.get_object(object_type, primary_key)
        if not anchor:
            raise ValueError(f"未找到对象 {object_type}:{primary_key}")
        link_type = ONTOLOGY.get_link_type(link_type_api_name)
        if not link_type:
            raise ValueError(f"未知链接类型：{link_type_api_name}")
        traversal = _resolve_traversal(direction, obj_type.api_name, link_type)
        anchor_set = ObjectSet(obj_type, [anchor], ontology=ONTOLOGY)
        related_set = anchor_set.search_around(
            link_type_api_name, limit=limit, **normalized_filters
        )
        related_objects = [
            _serialize_object(
                obj,
                include_derived=True,
                include_runtime_metadata=True,
            )
            for obj in related_set.all()
        ]
        return {
            "direction": traversal,
            "link_type": link_type_api_name,
            "anchor": _serialize_object(
                anchor, include_derived=True, include_runtime_metadata=True
            ),
            "related": related_objects,
        }


def _resolve_traversal(
    requested: Literal["auto", "forward", "reverse"],
    anchor_type: str,
    link_type: LinkType,
) -> Literal["forward", "reverse"]:
    if requested == "auto":
        if link_type.source_object_type == anchor_type:
            return "forward"
        if link_type.target_object_type == anchor_type:
            return "reverse"
        raise ValueError(
            f"对象类型 {anchor_type} 与链接 {link_type.api_name} 不匹配，请指定 direction"
        )
    if requested == "forward":
        if link_type.source_object_type != anchor_type:
            raise ValueError(
                f"链接 {link_type.api_name} 源对象为 {link_type.source_object_type}，"
                f"无法从 {anchor_type} 按 forward 方向遍历"
            )
        return "forward"
    if requested == "reverse":
        if link_type.target_object_type != anchor_type:
            raise ValueError(
                f"链接 {link_type.api_name} 目标对象为 {link_type.target_object_type}，"
                f"无法从 {anchor_type} 按 reverse 方向遍历"
            )
        return "reverse"
    raise ValueError(f"不支持的 direction: {requested}")


@server.tool(name="execute_action", description="执行本体中的动作（Action）")
def execute_action(action_api_name: str, parameters_json: Optional[str]) -> dict[str, Any]:
    params = _prepare_action_parameters(action_api_name, parameters_json)
    with ONTOLOGY_LOCK:
        log = ACTION_SERVICE.execute_action(
            action_api_name, params, DEFAULT_PRINCIPAL
        )
        snapshots = _object_snapshots(
            ONTOLOGY.get_action_type(action_api_name).target_object_types, params
        )
    return {
        "action_log_id": log.id,
        "changes": log.changes,
        "parameters": log.parameters,
        "snapshots": snapshots,
    }


@server.tool(name="invoke_function", description="调用注册函数（包括派生属性）")
def invoke_function(function_api_name: str, args_json: Optional[str] = None) -> dict[str, Any]:
    args = _prepare_function_arguments(function_api_name, args_json)
    with ONTOLOGY_LOCK:
        result = ONTOLOGY.execute_function(function_api_name, **args)
    if isinstance(result, ObjectInstance):
        payload: Any = _serialize_object(result, include_derived=True)
    elif isinstance(result, list):
        payload = result
    else:
        payload = result
    return {"function": function_api_name, "result": payload}


@server.resource(
    "resource://ontology/schema",
    name="order_delivery_schema",
    mime_type="application/json",
)
def schema_resource() -> str:
    with ONTOLOGY_LOCK:
        schema = ONTOLOGY.export_schema_for_llm()
    return json.dumps(schema, ensure_ascii=False, indent=2)


@server.resource(
    "resource://ontology/guide",
    name="usage_guide",
    mime_type="text/markdown",
)
def guide_resource() -> str:
    return dedent(
        """
        # Ontology FastMCP 使用手册

        ## 核心对象
        - Order：外卖订单，包含状态、各阶段时间戳、派生指标（actual_t_min, t_gap_min）
        - Merchant：商家基本信息
        - Rider：骑手基本信息

        ## 常用工具
        - list_object_types / list_actions / list_functions：理解能力边界
        - list_objects(object_type="Order", filters_json='{"status":"COMPLETED"}')
        - get_object(object_type="Order", primary_key="ord_fast")
        - get_related_objects(object_type="Order", primary_key="ord_fast", link_type_api_name="OrderHasMerchant")
        - execute_action("CreateOrder", '{"order_id":"ord_010","user_id":"user_999","merchant_id":"merchantA","items":"Burger","expected_t":25,"now":1700003600}')
        - invoke_function("calculate_t_gap", '{"order":{"object_type":"Order","primary_key":"ord_fast"}}')

        ## 建议工作流
        1. 通过资源 `resource://ontology/schema` 读取结构概览。
        2. 根据任务选择需要的对象或动作，先检索当前状态。
        3. 执行动作前，确认参数满足类型约束（见 list_actions 返回）。
        4. 使用函数或 derived 属性校验结果并形成分析。
        """
    ).strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Ontology FastMCP server")
    parser.add_argument(
        "--transport",
        default="stdio",
        choices=["stdio", "http", "sse", "streamable-http"],
        help="MCP 传输协议，默认 stdio",
    )
    parser.add_argument("--host", default="127.0.0.1", help="HTTP/SSE 模式监听地址")
    parser.add_argument(
        "--port", type=int, default=8765, help="HTTP/SSE 模式监听端口"
    )
    parser.add_argument(
        "--no-banner",
        action="store_true",
        help="启动时不打印 FastMCP banner（默认打印）",
    )
    args = parser.parse_args()

    transport_kwargs: dict[str, Any] = {}
    if args.transport != "stdio":
        transport_kwargs["host"] = args.host
        transport_kwargs["port"] = args.port

    server.run(
        transport=args.transport,
        show_banner=not args.no_banner,
        **transport_kwargs,
    )


if __name__ == "__main__":
    main()

