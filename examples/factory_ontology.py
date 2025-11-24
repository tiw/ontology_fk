from ontology_framework import (
    Ontology, ObjectType, LinkType, ActionType, PropertyType, ontology_function,
    ObjectInstance, ObjectSetService, ObjectView, ObjectExplorer, Quiver,
    AccessControlList, PermissionType
)

def main():
    ontology = Ontology()
    oss = ObjectSetService()
    explorer = ObjectExplorer()
    quiver = Quiver()

    # 1. Define Object Types with Metadata & Permissions
    factory_acl = AccessControlList()
    factory_acl.grant("user_1", PermissionType.VIEW)
    
    factory = ObjectType(
        api_name="Factory", 
        display_name="Factory", 
        primary_key="factory_id",
        backing_datasource_id="ri.foundry.main.dataset.1234",
        title_property="location",
        icon="factory",
        permissions=factory_acl
    )
    factory.add_property("factory_id", PropertyType.STRING)
    factory.add_property("location", PropertyType.STRING)
    factory.add_property("capacity", PropertyType.INTEGER)

    ontology.register_object_type(factory)

    # 2. Create Object Instances (Simulating Data Ingestion)
    f1 = ObjectInstance("Factory", "F1", {"factory_id": "F1", "location": "New York", "capacity": 100})
    f2 = ObjectInstance("Factory", "F2", {"factory_id": "F2", "location": "London", "capacity": 200})
    f3 = ObjectInstance("Factory", "F3", {"factory_id": "F3", "location": "Tokyo", "capacity": 150})

    oss.index_object(f1)
    oss.index_object(f2)
    oss.index_object(f3)

    # 3. Data Retrieval & Querying (Object Sets)
    print("\n--- Data Retrieval ---")
    try:
        # User without permission
        base_set = oss.get_base_object_set(factory, principal_id="user_2")
    except PermissionError as e:
        print(f"Expected Error: {e}")

    # User with permission
    base_set = oss.get_base_object_set(factory, principal_id="user_1")
    print(f"Base Set Count: {len(base_set.all())}")

    # Filtering
    ny_factories = base_set.filter("location", "New York")
    print(f"NY Factories: {len(ny_factories.all())}")

    # Aggregation
    total_capacity = base_set.aggregate("capacity", "sum")
    print(f"Total Capacity: {total_capacity}")

    # Search
    search_results = oss.search(factory, "Tok")
    print(f"Search 'Tok' Results: {len(search_results.all())}")

    # 4. Application Integration
    print("\n--- Application Integration ---")
    
    # Object View
    factory_view = ObjectView(factory, "Factory Overview", widgets=["Capacity Chart", "Location Map"])
    explorer.register_view(factory_view)
    explorer.open("Factory", base_set)

    # Quiver Analysis
    quiver.analyze(base_set)

    print("\nOntology Demonstration Complete.")

if __name__ == "__main__":
    main()
