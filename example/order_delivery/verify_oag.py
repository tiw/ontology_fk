from __future__ import annotations

import json
import os
import sys
from collections import defaultdict, deque
from typing import Dict, List, Optional, Tuple

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src")))

from ontology_framework.core import Ontology, ObjectInstance, ObjectSet
from example.order_delivery.schema import setup_ontology

AnchorKey = Tuple[str, str]


def seed_sample_data(ontology: Ontology) -> Dict[str, str]:
    """Create a minimal but fully linked knowledge graph for testing."""
    merchant = ObjectInstance(
        "Merchant", "m1", {"name": "Pizza Place", "address": "123 Main St"}
    )
    rider = ObjectInstance(
        "Rider", "r1", {"name": "John Doe", "phone": "555-0101"}
    )
    ontology.add_object(merchant)
    ontology.add_object(rider)
    
    order1 = ObjectInstance(
        "Order",
        "o1",
        {
            "order_id": "o1",
            "user_id": "u1",
            "merchant_id": "m1",
            "status": "CREATED",
            "items": "Pizza",
            "user_expected_t_min": 30,
        },
    )
    order2 = ObjectInstance(
        "Order",
        "o2",
        {
            "order_id": "o2",
            "user_id": "u2",
            "merchant_id": "m1",
            "rider_id": "r1",
            "status": "DELIVERING",
            "items": "Burger",
            "user_expected_t_min": 45,
        },
    )
    order3 = ObjectInstance(
        "Order",
        "o3",
        {
            "order_id": "o3",
            "user_id": "u3",
            "merchant_id": "m1",
            "rider_id": "r1",
            "status": "COMPLETED",
            "items": "Salad",
            "user_expected_t_min": 20,
        },
    )

    for order in (order1, order2, order3):
        ontology.add_object(order)
        ontology.create_link("OrderHasMerchant", order.primary_key_value, "m1")

    ontology.create_link("OrderHasRider", "o2", "r1")
    ontology.create_link("OrderHasRider", "o3", "r1")
    
    return {"merchant_id": "m1", "rider_id": "r1", "anchor_order_id": "o2"}


def summarize_object(
    obj: ObjectInstance, projection: Optional[List[str]] = None
) -> Dict[str, Dict]:
    payload = {
        "node_id": f"{obj.object_type_api_name}:{obj.primary_key_value}",
        "type": obj.object_type_api_name,
        "primary_key": obj.primary_key_value,
        "properties": {},
    }
    if projection:
        payload["properties"] = {prop: obj.get(prop) for prop in projection}
    else:
        payload["properties"] = dict(obj.property_values)
    return payload


def execute_search_plan(
    ontology: Ontology,
    anchor_type: str,
    anchor_ids: List[str],
    plan: List[Dict],
) -> Dict[str, List[Dict]]:
    anchor_objects = [
        ontology.get_object(anchor_type, pk)
        for pk in anchor_ids
        if ontology.get_object(anchor_type, pk)
    ]
    if not anchor_objects:
        raise ValueError(f"No anchor objects found for {anchor_type}: {anchor_ids}")

    context_sets: Dict[str, ObjectSet] = {
        "anchor": ObjectSet(
            ontology.get_object_type(anchor_type), anchor_objects, ontology
        )
    }
    materialized: Dict[str, List[Dict]] = {}

    for step in plan:
        source_alias = step.get("from", "anchor")
        alias = step["alias"]
        link_type = step["link_type"]
        filters = step.get("filters", {})
        limit = step.get("limit")
        projection = step.get("projection")

        if source_alias not in context_sets:
            raise ValueError(f"Unknown source alias: {source_alias}")

        result_set = context_sets[source_alias].search_around(
            link_type, limit=limit, **filters
        )
        context_sets[alias] = result_set
        materialized[alias] = [
            summarize_object(obj, projection=projection) for obj in result_set.all()
        ]

    return materialized


def build_link_index(ontology: Ontology):
    index = defaultdict(list)
    for link in ontology.get_all_links():
        link_type = ontology.get_link_type(link.link_type_api_name)
        if not link_type:
            continue
        source_key: AnchorKey = (link_type.source_object_type, link.source_primary_key)
        target_key: AnchorKey = (link_type.target_object_type, link.target_primary_key)
        index[source_key].append(
            ("forward", link.link_type_api_name, target_key)
        )
        index[target_key].append(
            ("reverse", link.link_type_api_name, source_key)
        )
    return index


def collect_properties(ontology: Ontology, obj: ObjectInstance) -> Dict[str, object]:
    props = dict(obj.property_values)
    obj_type = ontology.get_object_type(obj.object_type_api_name)
    if obj_type:
        for derived_name in obj_type.derived_properties:
            value = obj.get(derived_name)
            if value is not None:
                props[derived_name] = value
    return props


def build_local_graph(
    ontology: Ontology,
    anchor_type: str,
    anchor_pk: str,
    max_hops: int = 2,
    max_nodes: int = 25,
    link_whitelist: Optional[List[str]] = None,
) -> Dict[str, object]:
    anchor_obj = ontology.get_object(anchor_type, anchor_pk)
    if not anchor_obj:
        raise ValueError(f"Anchor object {anchor_type}:{anchor_pk} not found")

    link_index = build_link_index(ontology)
    anchor_key: AnchorKey = (anchor_type, anchor_pk)
    queue = deque([(anchor_key, 0)])
    visited: set[AnchorKey] = set()
    nodes: Dict[AnchorKey, Dict[str, object]] = {}
    edges_set = set()
    path_registry: Dict[AnchorKey, List[Dict[str, str]]] = {anchor_key: []}

    while queue and len(visited) < max_nodes:
        key, depth = queue.popleft()
        if key in visited:
            continue
        visited.add(key)

        obj = ontology.get_object(*key)
        if not obj:
            continue
        nodes[key] = {
            "id": f"{key[0]}:{key[1]}",
            "type": key[0],
            "properties": collect_properties(ontology, obj),
        }

        if depth >= max_hops:
            continue

        for direction, link_type_name, neighbor in link_index.get(key, []):
            if link_whitelist and link_type_name not in link_whitelist:
                continue

            edge_tuple = (key, neighbor, link_type_name, direction)
            if edge_tuple not in edges_set:
                edges_set.add(edge_tuple)
            if neighbor not in path_registry:
                path_registry[neighbor] = path_registry[key] + [
                    {
                        "link_type": link_type_name,
                        "direction": direction,
                        "from": f"{key[0]}:{key[1]}",
                        "to": f"{neighbor[0]}:{neighbor[1]}",
                    }
                ]
            if neighbor not in visited:
                queue.append((neighbor, depth + 1))

    edges = [
        {
            "from": f"{src[0]}:{src[1]}",
            "to": f"{dst[0]}:{dst[1]}",
            "link_type": link_type_name,
            "direction": direction,
        }
        for src, dst, link_type_name, direction in edges_set
    ]

    node_payloads = []
    for key, info in nodes.items():
        node_payloads.append(
            {
                **info,
                "path_from_anchor": path_registry.get(key, []),
            }
        )

    return {
        "anchor": f"{anchor_type}:{anchor_pk}",
        "nodes": node_payloads,
        "edges": edges,
        "max_hops": max_hops,
    }


def verify_answer_against_graph(
    answer: Dict[str, object], graph: Dict[str, object]
) -> None:
    nodes_index = {node["id"]: node for node in graph["nodes"]}
    for fact in answer.get("facts", []):
        node_id = fact["node_id"]
        property_name = fact["property"]
        expected_value = fact["value"]
        evidence_link = fact.get("requires_link_type")

        node = nodes_index.get(node_id)
        if not node:
            raise AssertionError(f"Node {node_id} not found in local graph")

        actual_value = node["properties"].get(property_name)
        if actual_value != expected_value:
            raise AssertionError(
                f"Mismatch for {node_id}.{property_name}: expected {expected_value}, got {actual_value}"
            )

        if evidence_link:
            path_links = {step["link_type"] for step in node["path_from_anchor"]}
            if evidence_link not in path_links and node_id != graph["anchor"]:
                raise AssertionError(
                    f"Evidence link {evidence_link} not found on path to {node_id}"
                )


def run_basic_traversal_checks(ontology: Ontology):
    print("\n[Check] 基础 Search Around")
    order = ontology.get_object("Order", "o1")
    order_set = ObjectSet(
        ontology.get_object_type("Order"), [order], ontology
    )
    merchants = order_set.search_around("OrderHasMerchant")
    assert merchants.all()[0].primary_key_value == "m1"

    merchant = ontology.get_object("Merchant", "m1")
    merchant_set = ObjectSet(
        ontology.get_object_type("Merchant"), [merchant], ontology
    )
    orders = merchant_set.search_around("OrderHasMerchant")
    assert len(orders.all()) == 3
    total_expected = orders.aggregate("user_expected_t_min", "sum")
    assert total_expected == 95

    rider = ontology.get_object("Rider", "r1")
    rider_set = ObjectSet(
        ontology.get_object_type("Rider"), [rider], ontology
    )
    delivering = rider_set.search_around(
        "OrderHasRider", status="DELIVERING"
    )
    assert len(delivering.all()) == 1
    print("Search Around checks passed.")


def demo_search_arounds(ontology: Ontology, merchant_id: str) -> Dict[str, List[Dict]]:
    print("\n[Demo] Search Arounds 复合检索")
    plan = [
        {
            "alias": "delivering_orders",
            "link_type": "OrderHasMerchant",
            "filters": {"status": "DELIVERING"},
            "projection": ["status", "items", "rider_id"],
            "limit": 10,
        },
        {
            "alias": "assigned_riders",
            "from": "delivering_orders",
            "link_type": "OrderHasRider",
            "projection": ["name", "phone"],
            "limit": 5,
        },
    ]
    result = execute_search_plan(ontology, "Merchant", [merchant_id], plan)
    print(json.dumps(result, indent=2))
    return result


def build_oag_payload(
    ontology: Ontology, anchor_order_id: str, search_results: Dict[str, List[Dict]]
) -> Dict[str, object]:
    local_graph = build_local_graph(
        ontology,
        anchor_type="Order",
        anchor_pk=anchor_order_id,
        max_hops=2,
        max_nodes=10,
        link_whitelist=["OrderHasMerchant", "OrderHasRider"],
    )
    schema = ontology.export_schema_for_llm()
    return {
        "schema": schema,
        "local_graph": local_graph,
        "search_results": search_results,
    }


def simulate_llm_answer() -> Dict[str, object]:
    return {
        "question": "为什么订单 o2 仍在派送？",
        "conclusion": "订单 o2 正由骑手 John Doe 派送，商家 Pizza Place 已出餐，等待骑手完成剩余行程。",
        "facts": [
            {
                "node_id": "Order:o2",
                "property": "status",
                "value": "DELIVERING",
            },
            {
                "node_id": "Order:o2",
                "property": "items",
                "value": "Burger",
            },
            {
                "node_id": "Merchant:m1",
                "property": "name",
                "value": "Pizza Place",
                "requires_link_type": "OrderHasMerchant",
            },
            {
                "node_id": "Rider:r1",
                "property": "name",
                "value": "John Doe",
                "requires_link_type": "OrderHasRider",
            },
        ],
    }


def verify_oag():
    print("=== Verifying Ontology Augmented Generation (OAG) ===")

    ontology = Ontology()
    setup_ontology(ontology)
    print("Ontology setup complete.")

    ids = seed_sample_data(ontology)
    print("Sample data seeded.")

    run_basic_traversal_checks(ontology)
    search_results = demo_search_arounds(ontology, ids["merchant_id"])
    oag_payload = build_oag_payload(ontology, ids["anchor_order_id"], search_results)

    print("\n[Context] Local Knowledge Graph for LLM")
    print(json.dumps(oag_payload["local_graph"], indent=2))

    print("\n[Context] Schema Snapshot")
    schema = oag_payload["schema"]
    assert len(schema["object_types"]) == 3
    assert len(schema["link_types"]) == 2
    assert len(schema["action_types"]) == 7
    print(
        f"- Object Types: {len(schema['object_types'])}, "
        f"Link Types: {len(schema['link_types'])}, "
        f"Action Types: {len(schema['action_types'])}"
    )

    answer = simulate_llm_answer()
    verify_answer_against_graph(answer, oag_payload["local_graph"])
    print("\n[Validation] LLM answer verified against context.")


if __name__ == "__main__":
    verify_oag()
