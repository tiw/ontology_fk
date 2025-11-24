import sys
import os
import json

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src")))

from ontology_framework.core import Ontology, ObjectInstance, ActionContext
from example.order_delivery.schema import setup_ontology

def verify_oag():
    print("=== Verifying OAG Capabilities ===")
    
    # 1. Setup Ontology
    ontology = Ontology()
    setup_ontology(ontology)
    print("Ontology setup complete.")
    
    # 2. Create Sample Data
    # Merchant
    merchant = ObjectInstance("Merchant", "m1", {"name": "Pizza Place", "address": "123 Main St"})
    ontology.add_object(merchant)
    
    # Rider
    rider = ObjectInstance("Rider", "r1", {"name": "John Doe", "phone": "555-0101"})
    ontology.add_object(rider)
    
    # Orders
    # Order 1: Created, linked to Merchant
    order1 = ObjectInstance("Order", "o1", {
        "user_id": "u1", "merchant_id": "m1", "status": "CREATED", "items": "Pizza", "user_expected_t_min": 30
    })
    ontology.add_object(order1)
    ontology.create_link("OrderHasMerchant", "o1", "m1")
    
    # Order 2: Delivering, linked to Merchant and Rider
    order2 = ObjectInstance("Order", "o2", {
        "user_id": "u2", "merchant_id": "m1", "rider_id": "r1", "status": "DELIVERING", "items": "Burger", "user_expected_t_min": 45
    })
    ontology.add_object(order2)
    ontology.create_link("OrderHasMerchant", "o2", "m1")
    ontology.create_link("OrderHasRider", "o2", "r1")

    # Order 3: Completed, linked to Merchant and Rider
    order3 = ObjectInstance("Order", "o3", {
        "user_id": "u3", "merchant_id": "m1", "rider_id": "r1", "status": "COMPLETED", "items": "Salad", "user_expected_t_min": 20
    })
    ontology.add_object(order3)
    ontology.create_link("OrderHasMerchant", "o3", "m1")
    ontology.create_link("OrderHasRider", "o3", "r1")
    
    print("Sample data created.")

    # 3. Test Forward Traversal (Order -> Merchant)
    print("\n--- Test Forward Traversal (Order -> Merchant) ---")
    # Get Order 1 as an ObjectSet (simulated)
    # We need to fetch it first.
    o1_instance = ontology.get_object("Order", "o1")
    from ontology_framework.core import ObjectSet
    order_set = ObjectSet(ontology.get_object_type("Order"), [o1_instance], ontology)
    
    merchants = order_set.search_around("OrderHasMerchant")
    print(f"Order o1 linked merchants: {[m.primary_key_value for m in merchants.all()]}")
    assert len(merchants.all()) == 1
    assert merchants.all()[0].primary_key_value == "m1"
    print("PASS")

    # 4. Test Reverse Traversal (Merchant -> Order)
    print("\n--- Test Reverse Traversal (Merchant -> Order) ---")
    m1_instance = ontology.get_object("Merchant", "m1")
    merchant_set = ObjectSet(ontology.get_object_type("Merchant"), [m1_instance], ontology)
    
    orders = merchant_set.search_around("OrderHasMerchant")
    print(f"Merchant m1 linked orders: {[o.primary_key_value for o in orders.all()]}")
    assert len(orders.all()) == 3
    assert "o1" in [o.primary_key_value for o in orders.all()]
    print("PASS")

    # 5. Test Filtered Traversal (Rider -> Orders with status="DELIVERING")
    print("\n--- Test Filtered Traversal (Rider -> Orders, status='DELIVERING') ---")
    r1_instance = ontology.get_object("Rider", "r1")
    rider_set = ObjectSet(ontology.get_object_type("Rider"), [r1_instance], ontology)
    
    # Rider has o2 (DELIVERING) and o3 (COMPLETED)
    delivering_orders = rider_set.search_around("OrderHasRider", status="DELIVERING")
    print(f"Rider r1 delivering orders: {[o.primary_key_value for o in delivering_orders.all()]}")
    assert len(delivering_orders.all()) == 1
    assert delivering_orders.all()[0].primary_key_value == "o2"
    print("PASS")
    
    # 6. Test Aggregation
    print("\n--- Test Aggregation ---")
    # Calculate total expected time for all orders of Merchant m1
    total_expected_time = orders.aggregate("user_expected_t_min", "sum")
    print(f"Total expected time for m1 orders: {total_expected_time}")
    assert total_expected_time == 30 + 45 + 20 # 95
    print("PASS")

    # 7. Test Schema Export
    print("\n--- Test Schema Export ---")
    schema = ontology.export_schema_for_llm()
    print(json.dumps(schema, indent=2))
    assert len(schema["object_types"]) == 3
    assert len(schema["link_types"]) == 2
    assert len(schema["action_types"]) == 7
    print("PASS")

if __name__ == "__main__":
    verify_oag()
