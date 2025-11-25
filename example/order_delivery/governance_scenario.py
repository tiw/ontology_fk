"""
场景：演示 Functions 治理 + ActionContext 扩展 + Runtime Metadata。

1. 初始化 order_delivery 本体，并注入一个存在迟到风险的订单。
2. 手动制造一个「错误商户链接」与一个「错误骑手链接」，观察验证逻辑如何把它们过滤掉。
3. 通过 ObjectSet.search_around() 触发动态评分，并从 runtime_metadata 中读取结果。
"""

from __future__ import annotations

from pprint import pprint
from typing import Dict

from ontology_framework.core import ObjectInstance, ObjectSet, Ontology
from ontology_framework.osdk import OntologySDK

from example.order_delivery.schema import setup_ontology


def _seed_entities(ontology: Ontology) -> None:
    """创建本场景所需的 Merchant/Rider/Order。"""
    merchants: Dict[str, str] = {
        "merchant_legit": "优选炸鸡店",
        "merchant_wrong": "误连接商户",
    }
    for merchant_id, name in merchants.items():
        ontology.add_object(
            ObjectInstance(
                "Merchant",
                merchant_id,
                {
                    "merchant_id": merchant_id,
                    "name": name,
                    "address": "示例路 123 号",
                },
            )
        )

    riders = {
        "rider_slow": "迟到王",
        "rider_wrong": "误链接骑手",
    }
    for rider_id, name in riders.items():
        ontology.add_object(
            ObjectInstance(
                "Rider",
                rider_id,
                {"rider_id": rider_id, "name": name, "phone": "555-0101"},
            )
        )

    order = ObjectInstance(
        "Order",
        "ord_governed",
        {
            "order_id": "ord_governed",
            "user_id": "user_demo",
            "merchant_id": "merchant_legit",
            "rider_id": "rider_slow",
            "status": "COMPLETED",
            "user_expected_t_min": 30,
            # 期望 30 分钟，实际约 48 分钟 -> t_gap_min = -18（迟到）
            "ts_created": 1_700_000_000.0,
            "ts_delivered": 1_700_000_000.0 + 48 * 60,
        },
    )
    ontology.add_object(order)

    # 正确链接
    ontology.create_link("OrderHasMerchant", "ord_governed", "merchant_legit")
    ontology.create_link("OrderHasRider", "ord_governed", "rider_slow")

    # 人为制造「错误链接」，验证函数会在遍历时过滤它们
    ontology.create_link("OrderHasMerchant", "ord_governed", "merchant_wrong")
    ontology.create_link("OrderHasRider", "ord_governed", "rider_wrong")


def run():
    ontology = Ontology()
    setup_ontology(ontology)
    _seed_entities(ontology)

    sdk = OntologySDK(ontology)
    order = sdk.get_object("Order", "ord_governed")

    print("=== Derived properties ===")
    print("actual_t_min:", order.get("actual_t_min"))
    print("t_gap_min:", order.get("t_gap_min"))

    order_type = ontology.get_object_type("Order")
    governed_set = ObjectSet(order_type, [order], ontology=ontology)

    print("\n=== Validated merchants (错误链接会被过滤) ===")
    merchants = governed_set.search_around("OrderHasMerchant")
    for merchant in merchants.all():
        print(f"- {merchant.get('name')}  (PK={merchant.primary_key_value})")

    print("\n=== Riders with runtime scores ===")
    riders = governed_set.search_around("OrderHasRider")
    for rider in riders.all():
        scores = rider.get_annotation("function_scores", {})
        print(
            f"- {rider.get('name')}, function_scores={scores.get('OrderHasRider')}, "
            f"runtime_metadata={rider.runtime_metadata}"
        )

    print("\n=== Schema snapshot (Functions + Derived Properties) ===")
    schema_payload = sdk.describe_schema()
    pprint(
        {
            "object_types": [
                ot
                for ot in schema_payload["object_types"]
                if ot["api_name"] in {"Order", "Merchant", "Rider"}
            ],
            "functions": [
                fn
                for fn in schema_payload["functions"]
                if fn["api_name"]
                in {
                    "calculate_actual_t",
                    "calculate_t_gap",
                    "validate_order_rider_assignment",
                    "score_order_rider_timeliness",
                }
            ],
        }
    )


if __name__ == "__main__":
    run()

