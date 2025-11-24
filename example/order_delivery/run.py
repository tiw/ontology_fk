import time
from ontology_framework.core import Ontology, ActionContext
from example.order_delivery.schema import setup_ontology

def run_scenario(ontology: Ontology, scenario_name: str, order_id: str, user_expected_t: int, 
                 time_steps: dict):
    print(f"\n--- Running Scenario: {scenario_name} ---")
    
    ctx = ActionContext(ontology, "system_user")
    
    # 1. Create Order
    t = time_steps['create']
    print(f"[{t}] Creating Order...")
    ontology.get_action_type("CreateOrder").logic(ctx, order_id, "user1", "merchantA", "Pizza", user_expected_t, t)
    ctx.apply_changes()
    
    # 2. Merchant Accept
    t = time_steps['accept']
    print(f"[{t}] Merchant Accept...")
    ontology.get_action_type("MerchantAccept").logic(ctx, order_id, t)
    ctx.apply_changes()
    
    # 3. Call Rider
    t = time_steps['call_rider']
    print(f"[{t}] Call Rider...")
    ontology.get_action_type("CallRider").logic(ctx, order_id, t)
    ctx.apply_changes()
    
    # 4. Merchant Out & Rider Arrive (Order depends on scenario)
    # We handle this by checking timestamps in the dict
    
    events = [
        ('merchant_out', time_steps['merchant_out'], "MerchantOut"),
        ('rider_arrive', time_steps['rider_arrive'], "RiderArrive")
    ]
    events.sort(key=lambda x: x[1])
    
    for name, t, action_name in events:
        print(f"[{t}] {action_name}...")
        if action_name == "MerchantOut":
            ontology.get_action_type("MerchantOut").logic(ctx, order_id, t)
        else:
            ontology.get_action_type("RiderArrive").logic(ctx, order_id, "rider1", t)
        ctx.apply_changes()

    # 5. Rider Pickup
    t = time_steps['pickup']
    print(f"[{t}] Rider Pickup...")
    ontology.get_action_type("RiderPickup").logic(ctx, order_id, t)
    ctx.apply_changes()
    
    # 6. Rider Deliver
    t = time_steps['deliver']
    print(f"[{t}] Rider Deliver...")
    ontology.get_action_type("RiderDeliver").logic(ctx, order_id, t)
    ctx.apply_changes()
    
    # Verify Results
    order = ontology.get_object("Order", order_id)
    print(f"Order Status: {order.get('status')}")
    print(f"User Expected T: {order.get('user_expected_t_min')} min")
    print(f"Actual T: {order.get('actual_t_min')} min")
    print(f"TGAP: {order.get('t_gap_min')} min")
    
    # Check wait type
    t_out = order.get("ts_merchant_out")
    t_arrive = order.get("ts_rider_arrived_store")
    if t_out > t_arrive:
        print("Wait Type: Rider Waited for Goods")
    elif t_out < t_arrive:
        print("Wait Type: Goods Waited for Rider")
    else:
        print("Wait Type: Perfect Sync")

def main():
    ontology = Ontology()
    setup_ontology(ontology)
    
    # Create Merchant and Rider objects (simulated via direct object store access or a setup action)
    # For this example, we'll just manually inject them or assume they exist for linking.
    # But wait, linking requires objects to exist in the store.
    # Let's add a helper to create them.
    
    from ontology_framework.core import ObjectInstance

    # Create Merchant
    ontology.add_object(ObjectInstance(
        "Merchant", "merchantA", {"name": "Pizza Hut", "address": "123 Main St"}
    ))
    # Create Rider
    ontology.add_object(ObjectInstance(
        "Rider", "rider1", {"name": "John Doe", "phone": "555-1234"}
    ))

    # Base time
    t0 = 1000000000.0
    
    # Scenario 1: Perfect Flow (Fast)
    # User expects 30 min. Actual is 20 min. TGAP = +10 (Good)
    # Merchant Out (10) < Rider Arrive (12) -> Goods Wait
    run_scenario(ontology, "Perfect Flow (Fast)", "ord_001", 30, {
        'create': t0,
        'accept': t0 + 60,       # +1 min
        'call_rider': t0 + 120,  # +2 min
        'merchant_out': t0 + 600, # +10 min
        'rider_arrive': t0 + 720, # +12 min
        'pickup': t0 + 780,      # +13 min
        'deliver': t0 + 1200     # +20 min
    })
    
    # Scenario 2: Slow Delivery
    # User expects 30 min. Actual is 40 min. TGAP = -10 (Bad)
    run_scenario(ontology, "Slow Delivery", "ord_002", 30, {
        'create': t0,
        'accept': t0 + 300,      # +5 min
        'call_rider': t0 + 600,  # +10 min
        'merchant_out': t0 + 1800, # +30 min
        'rider_arrive': t0 + 1200, # +20 min
        'pickup': t0 + 1860,     # +31 min
        'deliver': t0 + 2400     # +40 min
    })
    
    # Scenario 3: Rider Waits
    # Merchant Out (20) > Rider Arrive (10)
    run_scenario(ontology, "Rider Waits", "ord_003", 45, {
        'create': t0,
        'accept': t0 + 60,
        'call_rider': t0 + 120,
        'rider_arrive': t0 + 600,  # +10 min
        'merchant_out': t0 + 1200, # +20 min
        'pickup': t0 + 1260,       # +21 min
        'deliver': t0 + 1800       # +30 min
    })

    # --- Demonstrate Search Around ---
    print("\n--- Ontology Search & Traversal ---")
    
    # 1. Get Merchant
    merchant = ontology.get_object("Merchant", "merchantA")
    print(f"Merchant: {merchant.property_values['name']}")
    
    # 2. Find all Orders for this Merchant (Reverse traversal not directly supported by 'search_around' in core.py yet?)
    # Let's check core.py. search_around uses LinkType.
    # LinkType: Order -> Merchant.
    # So OrderSet.search_around("OrderHasMerchant") -> MerchantSet.
    # But we want Merchant -> Orders.
    # The core.py implementation of search_around checks:
    # if link_type.source_object_type == self.object_type.api_name: ...
    # It doesn't seem to support reverse traversal yet.
    # However, we can demonstrate Order -> Merchant.
    
    # Let's create an ObjectSet of Orders
    from ontology_framework.core import ObjectSet
    
    all_orders = ObjectSet(ontology.get_object_type("Order"), ontology.get_objects_of_type("Order"), ontology)
    print(f"Total Orders: {len(all_orders.all())}")
    
    # Filter Orders with negative TGAP (Late orders)
    # Note: ObjectSet.filter currently only supports exact match on properties.
    # We might need to iterate manually or enhance filter.
    # Let's iterate manually for this demo.
    late_orders = [o for o in all_orders.all() if o.get("t_gap_min") is not None and o.get("t_gap_min") < 0]
    print(f"Late Orders: {len(late_orders)}")
    
    # For a late order, find the Merchant
    if late_orders:
        late_order = late_orders[0]
        print(f"Analyzing Late Order: {late_order.primary_key_value}")
        
        # Create a set with just this order
        order_set = ObjectSet(ontology.get_object_type("Order"), [late_order], ontology)
        
        # Search around to Merchant
        merchants = order_set.search_around("OrderHasMerchant")
        for m in merchants.all():
            print(f"  -> Merchant: {m.property_values['name']}")
            
        # Search around to Rider
        riders = order_set.search_around("OrderHasRider")
        for r in riders.all():
            print(f"  -> Rider: {r.property_values['name']}")

if __name__ == "__main__":
    main()
