from ontology_framework.core import (
    Ontology, ObjectType, PropertyType, ActionType, ActionContext, 
    Function, FunctionArgument, PrimitiveType, ObjectTypeSpec, DerivedPropertyDefinition, LinkType
)
from ontology_framework.functions import ontology_function, registry

# 1. Define Object Types

def create_order_type() -> ObjectType:
    return ObjectType(
        api_name="Order",
        display_name="Delivery Order",
        primary_key="order_id",
        title_property="order_id",
        icon="shopping-cart"
    ).add_property("order_id", PropertyType.STRING)\
     .add_property("user_id", PropertyType.STRING)\
     .add_property("merchant_id", PropertyType.STRING)\
     .add_property("rider_id", PropertyType.STRING)\
     .add_property("status", PropertyType.STRING)\
     .add_property("items", PropertyType.STRING)\
     .add_property("user_expected_t_min", PropertyType.INTEGER, "User expected delivery duration in minutes")\
     .add_property("ts_created", PropertyType.TIMESTAMP)\
     .add_property("ts_merchant_accepted", PropertyType.TIMESTAMP)\
     .add_property("ts_rider_called", PropertyType.TIMESTAMP)\
     .add_property("ts_merchant_out", PropertyType.TIMESTAMP)\
     .add_property("ts_rider_arrived_store", PropertyType.TIMESTAMP)\
     .add_property("ts_rider_picked", PropertyType.TIMESTAMP)\
     .add_property("ts_delivered", PropertyType.TIMESTAMP)\
     .add_derived_property("actual_t_min", PropertyType.INTEGER, "calculate_actual_t")\
     .add_derived_property("t_gap_min", PropertyType.INTEGER, "calculate_t_gap")

def create_merchant_type() -> ObjectType:
    return ObjectType(
        api_name="Merchant",
        display_name="Restaurant",
        primary_key="merchant_id",
        title_property="name",
        icon="shop"
    ).add_property("merchant_id", PropertyType.STRING)\
     .add_property("name", PropertyType.STRING)\
     .add_property("address", PropertyType.STRING)

def create_rider_type() -> ObjectType:
    return ObjectType(
        api_name="Rider",
        display_name="Delivery Rider",
        primary_key="rider_id",
        title_property="name",
        icon="bicycle"
    ).add_property("rider_id", PropertyType.STRING)\
     .add_property("name", PropertyType.STRING)\
     .add_property("phone", PropertyType.STRING)

# 2. Define Functions

@ontology_function(
    api_name="calculate_actual_t",
    display_name="Calculate Actual T",
    inputs={"order": ObjectTypeSpec("Order")},
    output_type=PrimitiveType(PropertyType.INTEGER)
)
def calculate_actual_t(order):
    created = order.get("ts_created")
    delivered = order.get("ts_delivered")
    if created is not None and delivered is not None:
        return int((delivered - created) / 60) # Return minutes
    return None

@ontology_function(
    api_name="calculate_t_gap",
    display_name="Calculate T Gap",
    inputs={"order": ObjectTypeSpec("Order")},
    output_type=PrimitiveType(PropertyType.INTEGER)
)
def calculate_t_gap(order):
    user_t = order.get("user_expected_t_min")
    actual_t = order.get("actual_t_min") # This will trigger recursive derived property calculation if framework supports it, or we re-calculate
    
    # For simplicity in this prototype, let's re-calculate actual_t if not available directly or if framework doesn't auto-resolve dependencies yet
    if actual_t is None:
        actual_t = calculate_actual_t(order)
        
    if user_t is not None and actual_t is not None:
        return user_t - actual_t
    return None

# 3. Define Link Types

def create_link_order_merchant() -> LinkType:
    return LinkType(
        api_name="OrderHasMerchant",
        display_name="Order Merchant",
        source_object_type="Order",
        target_object_type="Merchant",
        cardinality="ONE_TO_ONE" # Each order has one merchant
    )

def create_link_order_rider() -> LinkType:
    return LinkType(
        api_name="OrderHasRider",
        display_name="Order Rider",
        source_object_type="Order",
        target_object_type="Rider",
        cardinality="ONE_TO_ONE"
    )

# 4. Define Action Types

def create_action_create_order() -> ActionType:
    def logic(ctx: ActionContext, order_id: str, user_id: str, merchant_id: str, items: str, expected_t: int, now: float):
        ctx.create_object("Order", order_id, {
            "user_id": user_id,
            "merchant_id": merchant_id,
            "items": items,
            "status": "CREATED",
            "user_expected_t_min": expected_t,
            "ts_created": now
        })
        # Link to Merchant
        ctx.create_link("OrderHasMerchant", order_id, merchant_id)
    
    return ActionType(
        api_name="CreateOrder",
        display_name="User Places Order",
        target_object_types=["Order"],
        logic=logic
    ).add_parameter("order_id", PropertyType.STRING)\
     .add_parameter("user_id", PropertyType.STRING)\
     .add_parameter("merchant_id", PropertyType.STRING)\
     .add_parameter("items", PropertyType.STRING)\
     .add_parameter("expected_t", PropertyType.INTEGER)\
     .add_parameter("now", PropertyType.TIMESTAMP)

def create_action_merchant_accept() -> ActionType:
    def logic(ctx: ActionContext, order_id: str, now: float):
        order = ctx.get_object("Order", order_id)
        if order:
            ctx.modify_object(order, "status", "ACCEPTED")
            ctx.modify_object(order, "ts_merchant_accepted", now)
            
    return ActionType(
        api_name="MerchantAccept",
        display_name="Merchant Accepts Order",
        target_object_types=["Order"],
        logic=logic
    ).add_parameter("order_id", PropertyType.STRING)\
     .add_parameter("now", PropertyType.TIMESTAMP)

def create_action_call_rider() -> ActionType:
    def logic(ctx: ActionContext, order_id: str, now: float):
        order = ctx.get_object("Order", order_id)
        if order:
            ctx.modify_object(order, "status", "RIDER_CALLED")
            ctx.modify_object(order, "ts_rider_called", now)

    return ActionType(
        api_name="CallRider",
        display_name="Merchant Calls Rider",
        target_object_types=["Order"],
        logic=logic
    ).add_parameter("order_id", PropertyType.STRING)\
     .add_parameter("now", PropertyType.TIMESTAMP)

def create_action_merchant_out() -> ActionType:
    def logic(ctx: ActionContext, order_id: str, now: float):
        order = ctx.get_object("Order", order_id)
        if order:
            ctx.modify_object(order, "ts_merchant_out", now)
            # Status update might depend on whether rider is there, but let's keep it simple
            if order.get("status") == "RIDER_ARRIVED":
                 ctx.modify_object(order, "status", "READY_FOR_PICKUP")

    return ActionType(
        api_name="MerchantOut",
        display_name="Merchant Food Ready",
        target_object_types=["Order"],
        logic=logic
    ).add_parameter("order_id", PropertyType.STRING)\
     .add_parameter("now", PropertyType.TIMESTAMP)

def create_action_rider_arrive() -> ActionType:
    def logic(ctx: ActionContext, order_id: str, rider_id: str, now: float):
        order = ctx.get_object("Order", order_id)
        if order:
            ctx.modify_object(order, "rider_id", rider_id)
            ctx.modify_object(order, "ts_rider_arrived_store", now)
            if order.get("ts_merchant_out") is not None:
                 ctx.modify_object(order, "status", "READY_FOR_PICKUP")
            else:
                 ctx.modify_object(order, "status", "RIDER_ARRIVED")
            
            # Link to Rider
            ctx.create_link("OrderHasRider", order_id, rider_id)

    return ActionType(
        api_name="RiderArrive",
        display_name="Rider Arrives at Store",
        target_object_types=["Order"],
        logic=logic
    ).add_parameter("order_id", PropertyType.STRING)\
     .add_parameter("rider_id", PropertyType.STRING)\
     .add_parameter("now", PropertyType.TIMESTAMP)

def create_action_rider_pickup() -> ActionType:
    def logic(ctx: ActionContext, order_id: str, now: float):
        order = ctx.get_object("Order", order_id)
        if order:
            ctx.modify_object(order, "status", "DELIVERING")
            ctx.modify_object(order, "ts_rider_picked", now)

    return ActionType(
        api_name="RiderPickup",
        display_name="Rider Picks Up Order",
        target_object_types=["Order"],
        logic=logic
    ).add_parameter("order_id", PropertyType.STRING)\
     .add_parameter("now", PropertyType.TIMESTAMP)

def create_action_rider_deliver() -> ActionType:
    def logic(ctx: ActionContext, order_id: str, now: float):
        order = ctx.get_object("Order", order_id)
        if order:
            ctx.modify_object(order, "status", "COMPLETED")
            ctx.modify_object(order, "ts_delivered", now)

    return ActionType(
        api_name="RiderDeliver",
        display_name="Rider Delivers Order",
        target_object_types=["Order"],
        logic=logic
    ).add_parameter("order_id", PropertyType.STRING)\
     .add_parameter("now", PropertyType.TIMESTAMP)


def setup_ontology(ontology: Ontology):
    # Register Objects
    ontology.register_object_type(create_order_type())
    ontology.register_object_type(create_merchant_type())
    ontology.register_object_type(create_rider_type())
    
    # Register Link Types
    ontology.register_link_type(create_link_order_merchant())
    ontology.register_link_type(create_link_order_rider())
    
    # Register Functions
    registry.register_all_to_ontology(ontology)
    
    # Register Actions
    ontology.register_action_type(create_action_create_order())
    ontology.register_action_type(create_action_merchant_accept())
    ontology.register_action_type(create_action_call_rider())
    ontology.register_action_type(create_action_merchant_out())
    ontology.register_action_type(create_action_rider_arrive())
    ontology.register_action_type(create_action_rider_pickup())
    ontology.register_action_type(create_action_rider_deliver())
