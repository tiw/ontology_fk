import random
import time
from ontology_framework.core import Ontology, ActionContext, ObjectInstance
from example.order_delivery.schema import setup_ontology

def simulate_orders(n=1000):
    ontology = Ontology()
    setup_ontology(ontology)
    
    # Constants
    USER_EXPECTED_T = 30 # minutes
    
    print(f"Simulating {n} orders...")
    
    # Seed for reproducibility
    random.seed(42)
    
    for i in range(n):
        order_id = f"ord_{i:04d}"
        t0 = 1000000000.0 + (i * 60) # Stagger start times
        
        # Simulate durations (in seconds)
        # Normal distribution with some variance
        d_accept = max(10, random.gauss(60, 20))      # ~1 min
        d_call = max(10, random.gauss(60, 20))        # ~1 min
        
        # Merchant Prep: usually 10-20 mins, sometimes long
        d_prep = max(300, random.gauss(900, 300))     # ~15 min
        if random.random() < 0.1: d_prep += 900       # 10% chance of +15 min delay
        
        # Rider Arrive: usually 5-15 mins
        d_arrive = max(180, random.gauss(600, 180))   # ~10 min
        if random.random() < 0.1: d_arrive += 600     # 10% chance of delay
        
        # Pickup: fast if both ready
        d_pickup_process = max(30, random.gauss(60, 10)) # ~1 min handover
        
        # Delivery: 10-20 mins
        d_deliver = max(300, random.gauss(900, 300))  # ~15 min
        if random.random() < 0.05: d_deliver += 900   # 5% chance of +15 min delay
        
        # Timestamps
        t_created = t0
        t_accepted = t_created + d_accept
        t_called = t_accepted + d_call
        t_merchant_out = t_called + d_prep
        t_rider_arrive = t_called + d_arrive
        
        t_ready_for_pickup = max(t_merchant_out, t_rider_arrive)
        t_picked = t_ready_for_pickup + d_pickup_process
        t_delivered = t_picked + d_deliver
        
        # Create Order Object directly
        props = {
            "user_id": f"user_{random.randint(1, 100)}",
            "merchant_id": f"merch_{random.randint(1, 10)}",
            "status": "COMPLETED",
            "user_expected_t_min": USER_EXPECTED_T,
            "ts_created": t_created,
            "ts_merchant_accepted": t_accepted,
            "ts_rider_called": t_called,
            "ts_merchant_out": t_merchant_out,
            "ts_rider_arrived_store": t_rider_arrive,
            "ts_rider_picked": t_picked,
            "ts_delivered": t_delivered
        }
        
        ontology.add_object(ObjectInstance("Order", order_id, props))
        
    print("Simulation complete. Analyzing...")
    
    # Analysis
    all_orders = ontology.get_objects_of_type("Order")
    
    results = []
    for order in all_orders:
        # Trigger derived properties
        actual_t = order.get("actual_t_min")
        t_gap = order.get("t_gap_min")
        
        # Calculate segments for analysis
        # We need to access raw props
        p = order.property_values
        
        # Segments (in minutes)
        s_response = (p['ts_rider_called'] - p['ts_created']) / 60
        s_prep = (p['ts_merchant_out'] - p['ts_rider_called']) / 60
        s_arrive = (p['ts_rider_arrived_store'] - p['ts_rider_called']) / 60
        
        # Wait time
        wait_goods = max(0, p['ts_merchant_out'] - p['ts_rider_arrived_store']) / 60 # Rider waiting for goods
        wait_rider = max(0, p['ts_rider_arrived_store'] - p['ts_merchant_out']) / 60 # Goods waiting for rider
        
        s_pickup = (p['ts_rider_picked'] - max(p['ts_merchant_out'], p['ts_rider_arrived_store'])) / 60
        s_deliver = (p['ts_delivered'] - p['ts_rider_picked']) / 60
        
        results.append({
            "id": order.primary_key_value,
            "actual_t": actual_t,
            "t_gap": t_gap,
            "s_response": s_response,
            "s_prep": s_prep,
            "s_arrive": s_arrive,
            "wait_goods": wait_goods, # Rider waiting for goods
            "wait_rider": wait_rider, # Goods waiting for rider
            "s_pickup": s_pickup,
            "s_deliver": s_deliver
        })
        
    # Group by TGAP
    groups = {
        "On Time (TGAP >= 0)": [],
        "Late (TGAP < 0)": [],
        "Very Late (TGAP < -10)": []
    }
    
    for r in results:
        if r['t_gap'] >= 0:
            groups["On Time (TGAP >= 0)"].append(r)
        else:
            groups["Late (TGAP < 0)"].append(r)
            if r['t_gap'] < -10:
                groups["Very Late (TGAP < -10)"].append(r)
                
    # Print Stats
    print(f"\n{'Group':<25} | {'Count':<5} | {'Avg TGAP':<8} | {'Resp':<5} | {'Prep':<5} | {'Arrive':<6} | {'WaitGoods':<9} | {'WaitRider':<9} | {'Deliver':<7}")
    print("-" * 110)
    
    for name, items in groups.items():
        if not items: continue
        count = len(items)
        avg_tgap = sum(x['t_gap'] for x in items) / count
        avg_resp = sum(x['s_response'] for x in items) / count
        avg_prep = sum(x['s_prep'] for x in items) / count
        avg_arrive = sum(x['s_arrive'] for x in items) / count
        avg_wait_g = sum(x['wait_goods'] for x in items) / count
        avg_wait_r = sum(x['wait_rider'] for x in items) / count
        avg_del = sum(x['s_deliver'] for x in items) / count
        
        print(f"{name:<25} | {count:<5} | {avg_tgap:<8.1f} | {avg_resp:<5.1f} | {avg_prep:<5.1f} | {avg_arrive:<6.1f} | {avg_wait_g:<9.1f} | {avg_wait_r:<9.1f} | {avg_del:<7.1f}")

    print("\nAnalysis:")
    # Simple heuristic analysis
    late_items = groups["Very Late (TGAP < -10)"]
    ontime_items = groups["On Time (TGAP >= 0)"]
    
    if late_items and ontime_items:
        avg_prep_late = sum(x['s_prep'] for x in late_items) / len(late_items)
        avg_prep_ontime = sum(x['s_prep'] for x in ontime_items) / len(ontime_items)
        
        avg_del_late = sum(x['s_deliver'] for x in late_items) / len(late_items)
        avg_del_ontime = sum(x['s_deliver'] for x in ontime_items) / len(ontime_items)
        
        avg_wait_g_late = sum(x['wait_goods'] for x in late_items) / len(late_items) # Rider waiting
        avg_wait_g_ontime = sum(x['wait_goods'] for x in ontime_items) / len(ontime_items)

        print(f"Comparing 'Very Late' vs 'On Time':")
        print(f"- Prep Time diff: {avg_prep_late - avg_prep_ontime:.1f} min")
        print(f"- Delivery Time diff: {avg_del_late - avg_del_ontime:.1f} min")
        print(f"- Rider Wait (for Goods) diff: {avg_wait_g_late - avg_wait_g_ontime:.1f} min")
        
        causes = []
        if (avg_prep_late - avg_prep_ontime) > 5: causes.append("Merchant Prep Delay")
        if (avg_del_late - avg_del_ontime) > 5: causes.append("Rider Delivery Delay")
        if (avg_wait_g_late - avg_wait_g_ontime) > 5: causes.append("Rider Waiting for Merchant")
        
        if causes:
            print(f"Primary Causes of Delay: {', '.join(causes)}")
        else:
            print("Delays are distributed across multiple stages.")

if __name__ == "__main__":
    simulate_orders()
