"""
示例：基于 order_delivery 场景串联 Object Explorer 枢轴聚合、Vertex 图谱/模拟，以及统一 Object View 导出。

运行本脚本将：
1. 初始化并填充一个示例 Ontology（复用 schema.py 中的定义 + 多个订单生命周期）。
2. 从所有订单里挑出「迟到」订单集合，演示 Object Explorer 的 Pivot 聚合上下文。
3. 利用 Vertex 生成订单-商户-骑手的系统图谱，并运行一个简单的模拟（假设重新规划交付时间）。
4. 输出与 Object View 对应的标准化视图 Schema，可直接被 LLM 或前台复用。
"""

from __future__ import annotations

from pprint import pprint
from typing import Dict, List

from ontology_framework.core import ActionContext, ObjectInstance, ObjectSet, Ontology
from ontology_framework.applications import (
    ObjectExplorer,
    ObjectView,
    PivotAggregationPlan,
    Vertex,
    VertexSimulation,
)

from example.order_delivery.schema import setup_ontology

# --- 基础配置 -------------------------------------------------------------------------------------

# 每个时间戳都相对该基准，方便肉眼推算
BASE_TS = 1_700_000_000.0

# 为了让枢轴/图谱有数据可用，准备三种不同的履约情境（与 run.py 中类似，但仅保留必要字段）
SCENARIOS: Dict[str, Dict[str, float]] = {
    "fast_flow": {
        "order_id": "ord_demo_001",
        "user_expected_t": 30,
        "timeline": {
            "create": BASE_TS,
            "accept": BASE_TS + 60,
            "call_rider": BASE_TS + 120,
            "merchant_out": BASE_TS + 600,
            "rider_arrive": BASE_TS + 720,
            "pickup": BASE_TS + 780,
            "deliver": BASE_TS + 1_200,
        },
    },
    "slow_delivery": {
        "order_id": "ord_demo_002",
        "user_expected_t": 30,
        "timeline": {
            "create": BASE_TS,
            "accept": BASE_TS + 300,
            "call_rider": BASE_TS + 600,
            "merchant_out": BASE_TS + 1_800,
            "rider_arrive": BASE_TS + 1_200,
            "pickup": BASE_TS + 1_860,
            "deliver": BASE_TS + 2_400,
        },
    },
    "rider_waits": {
        "order_id": "ord_demo_003",
        "user_expected_t": 45,
        "timeline": {
            "create": BASE_TS,
            "accept": BASE_TS + 60,
            "call_rider": BASE_TS + 120,
            "rider_arrive": BASE_TS + 600,
            "merchant_out": BASE_TS + 1_200,
            "pickup": BASE_TS + 1_260,
            "deliver": BASE_TS + 1_800,
        },
    },
}


# --- 数据准备 -------------------------------------------------------------------------------------


def ensure_static_objects(ontology: Ontology) -> None:
    """
    Merchant 与 Rider 在 schema 中是 LinkType 目标，需要先行落地，方便后续订单动作直接关联。
    这里手动注入两个 Merchant（快慢各一家）与两个 Rider（正常骑手 + 备选骑手）。
    """
    merchant_payloads = [
        ("merchant_fast_food", "极速披萨店"),
        ("merchant_slow_food", "悠闲意面屋"),
    ]
    for merchant_id, name in merchant_payloads:
        ontology.add_object(
            ObjectInstance(
                object_type_api_name="Merchant",
                primary_key_value=merchant_id,
                property_values={
                    "merchant_id": merchant_id,
                    "name": name,
                    "address": "123 Demo St",
                },
            )
        )

    rider_payloads = [
        ("rider_alpha", "Alpha 骑手"),
        ("rider_beta", "Beta 骑手"),
    ]
    for rider_id, name in rider_payloads:
        ontology.add_object(
            ObjectInstance(
                object_type_api_name="Rider",
                primary_key_value=rider_id,
                property_values={
                    "rider_id": rider_id,
                    "name": name,
                    "phone": "555-0101",
                },
            )
        )


def simulate_order_flow(
    ontology: Ontology,
    *,
    order_id: str,
    merchant_id: str,
    rider_id: str,
    user_expected_t: int,
    timeline: Dict[str, float],
) -> None:
    """
    使用 schema 中的 ActionType，按顺序回放单个订单的完整生命周期。

    说明：
    - ActionContext 用来确保每个步骤都以“事务”方式改写对象，并记录变更。
    - 每次调用动作后立刻 `apply_changes()`，与实时系统一致（若要批量提交也可以等所有动作跑完）。
    """
    ctx = ActionContext(ontology, principal_id="demo_orchestrator")

    def run(action_name: str, **kwargs):
        action = ontology.get_action_type(action_name)
        if not action:
            raise ValueError(f"未注册的 ActionType: {action_name}")
        action.logic(ctx, **kwargs)
        ctx.apply_changes()

    run(
        "CreateOrder",
        order_id=order_id,
        user_id="user_demo",
        merchant_id=merchant_id,
        items="Demo Pizza Combo",
        expected_t=user_expected_t,
        now=timeline["create"],
    )
    run("MerchantAccept", order_id=order_id, now=timeline["accept"])
    run("CallRider", order_id=order_id, now=timeline["call_rider"])

    # Merchant 与 Rider 到店顺序可能不同，故按时间排序后执行
    arrivals = [
        ("MerchantOut", {"order_id": order_id, "now": timeline.get("merchant_out")}),
        (
            "RiderArrive",
            {
                "order_id": order_id,
                "rider_id": rider_id,
                "now": timeline.get("rider_arrive"),
            },
        ),
    ]
    for action_name, params in sorted(arrivals, key=lambda item: params_timestamp(item[1])):
        run(action_name, **params)

    run("RiderPickup", order_id=order_id, now=timeline["pickup"])
    run("RiderDeliver", order_id=order_id, now=timeline["deliver"])


def params_timestamp(action_params: Dict[str, float]) -> float:
    """帮助 arrivals 队列排序的工具函数，默认返回 now 字段。"""
    return action_params.get("now", BASE_TS)


def seed_demo_orders(ontology: Ontology) -> None:
    """
    将 ensure_static_objects + 多场景生命周期封装为一个入口，便于 main 中直接调用。
    """
    ensure_static_objects(ontology)

    simulate_order_flow(
        ontology,
        order_id=SCENARIOS["fast_flow"]["order_id"],
        merchant_id="merchant_fast_food",
        rider_id="rider_alpha",
        user_expected_t=SCENARIOS["fast_flow"]["user_expected_t"],
        timeline=SCENARIOS["fast_flow"]["timeline"],
    )
    simulate_order_flow(
        ontology,
        order_id=SCENARIOS["slow_delivery"]["order_id"],
        merchant_id="merchant_slow_food",
        rider_id="rider_alpha",
        user_expected_t=SCENARIOS["slow_delivery"]["user_expected_t"],
        timeline=SCENARIOS["slow_delivery"]["timeline"],
    )
    simulate_order_flow(
        ontology,
        order_id=SCENARIOS["rider_waits"]["order_id"],
        merchant_id="merchant_fast_food",
        rider_id="rider_beta",
        user_expected_t=SCENARIOS["rider_waits"]["user_expected_t"],
        timeline=SCENARIOS["rider_waits"]["timeline"],
    )


# --- 枢轴聚合 -------------------------------------------------------------------------------------


def collect_late_orders(ontology: Ontology) -> ObjectSet:
    """
    从全部订单里筛出 t_gap_min < 0（即实际耗时超过预期）的对象集合，
    并绑定 Ontology 上下文，供 Object Explorer/Vertex 往返遍历。
    """
    order_type = ontology.get_object_type("Order")
    late_objects: List[ObjectInstance] = []
    for order in ontology.get_objects_of_type("Order"):
        gap = order.get("t_gap_min")
        if gap is not None and gap < 0:
            late_objects.append(order)
    return ObjectSet(order_type, late_objects, ontology=ontology)


def build_pivot_context(order_set: ObjectSet, explorer: ObjectExplorer) -> Dict[str, Dict]:
    """
    对迟到订单集合执行两条 Pivot：
    1. Order -> Merchant：了解这些订单集中在哪些商户、商户数量。
    2. Order -> Rider：了解涉及的骑手，便于排查调度问题。

    metrics 中使用 "count" 统计关联实体个数；include_root_properties 确保根对象带上 SLA 相关字段。
    """
    merchant_plan = PivotAggregationPlan(
        link_type_api_name="OrderHasMerchant",
        properties=["name", "address"],
        metrics={"merchant_id": "count"},
        limit=10,
    )
    rider_plan = PivotAggregationPlan(
        link_type_api_name="OrderHasRider",
        properties=["name", "phone"],
        metrics={"rider_id": "count"},
        limit=10,
    )
    return explorer.pivot_context(
        order_set,
        plans=[merchant_plan, rider_plan],
        include_root_properties=["user_expected_t_min", "actual_t_min", "t_gap_min"],
    )


# --- Vertex 图谱 + 模拟 ---------------------------------------------------------------------------


def configure_vertex(ontology: Ontology) -> Vertex:
    """
    1. 通过 Vertex.generate_system_graph 可遍历 Order-Merchant-Rider 网络。
    2. 注册一个简单的模拟：假设可以调整交付时间（new_delivery_ts），快速估算新的 t_gap。
    """
    vertex = Vertex(ontology)

    def reroute_simulation(**kwargs):
        order_id = kwargs["order_id"]
        new_delivery_ts = kwargs["new_delivery_ts"]
        order = ontology.get_object("Order", order_id)
        if not order:
            raise ValueError(f"订单 {order_id} 不存在")
        created = order.get("ts_created")
        expected = order.get("user_expected_t_min")
        if created is None or expected is None:
            raise ValueError("订单缺少 ts_created 或 user_expected_t_min 字段")
        hypothetical_actual = int((new_delivery_ts - created) / 60)
        simulated_gap = expected - hypothetical_actual
        return {
            "order_id": order_id,
            "original_gap": order.get("t_gap_min"),
            "hypothetical_actual_min": hypothetical_actual,
            "simulated_gap": simulated_gap,
        }

    vertex.register_simulation(
        VertexSimulation(
            name="hypothetical_delivery_gap",
            runner=reroute_simulation,
            description="调整交付时间后重新计算 t_gap",
        )
    )
    return vertex


def build_system_graph(vertex: Vertex, seed_set: ObjectSet) -> Dict[str, Dict]:
    """
    使用迟到订单作为种子，向外扩展两层节点（订单 -> 商户/骑手），并附带关键属性方便前端染色。
    """
    return vertex.generate_system_graph(
        seed_set,
        max_depth=2,
        include_properties=["status", "user_expected_t_min", "t_gap_min"],
    )


# --- Object View 导出 -----------------------------------------------------------------------------


def register_custom_order_view(explorer: ObjectExplorer, order_set: ObjectSet) -> None:
    """
    注册一个面向迟到订单的定制视图，强调 SLA 指标。Object View Schema 可被任何消费方加载，
    也可以 fallback 到默认视图。
    """
    order_view = ObjectView(
        object_type=order_set.object_type,
        title="迟到订单指挥舱视图",
        widgets=[
            "sla_summary_cards",
            "timeline_diff_chart",
            "related_entities_panel",
        ],
    )
    explorer.register_view(order_view)


def describe_order_view(explorer: ObjectExplorer, order_set: ObjectSet) -> Dict[str, Dict]:
    """返回结构化的视图 Schema，供 LLM / Web 端共享。"""
    return explorer.describe_view(object_set=order_set)


# --- 主流程 ---------------------------------------------------------------------------------------


def run_demo():
    # 0. 初始化 Ontology + Schema
    ontology = Ontology()
    setup_ontology(ontology)

    # 1. 填充数据
    seed_demo_orders(ontology)

    # 2. 聚焦「迟到订单」集合
    late_order_set = collect_late_orders(ontology)
    if not late_order_set.all():
        print("当前无迟到订单，示例无法继续。")
        return

    # 3. Object Explorer：注册视图 + 枢轴上下文
    explorer = ObjectExplorer()
    register_custom_order_view(explorer, late_order_set)
    pivot_payload = build_pivot_context(late_order_set, explorer)
    view_schema = describe_order_view(explorer, late_order_set)

    # 4. Vertex：构建图谱 & 运行模拟
    vertex = configure_vertex(ontology)
    graph_payload = build_system_graph(vertex, late_order_set)
    sample_order = late_order_set.all()[0]
    hypo_result = vertex.run_simulation(
        "hypothetical_delivery_gap",
        bind=False,
        order_id=sample_order.primary_key_value,
        new_delivery_ts=sample_order.get("ts_delivered") - 300,
    )

    # 5. 输出结果（生产环境可改为返回 JSON）
    print("\n=== 枢轴上下文 ===")
    pprint(pivot_payload)

    print("\n=== Vertex 系统图谱（节点/边计数） ===")
    print(f"节点数量: {len(graph_payload['nodes'])}")
    print(f"边数量: {len(graph_payload['edges'])}")

    print("\n=== Vertex 模拟结果 ===")
    pprint(hypo_result)

    print("\n=== Object View Schema ===")
    pprint(view_schema)

    print("\n示例完成，可将上述结构作为统一上下文提供给 LLM / 前台。")


if __name__ == "__main__":
    run_demo()

