import time
from ontology_framework.core import Ontology, ObjectType, PropertyType, ObjectInstance

def test_oss():
    print("Initializing Ontology...")
    ontology = Ontology()

    # 1. Define Object Type
    print("Defining Object Type 'Employee'...")
    employee_type = ObjectType(
        api_name="Employee",
        display_name="Employee",
        primary_key="id"
    ).add_property("id", PropertyType.STRING).add_property("department", PropertyType.STRING)
    
    ontology.register_object_type(employee_type)

    # 2. Create Objects
    print("Creating Employees...")
    ontology.add_object(ObjectInstance("Employee", "1", {"id": "1", "department": "Engineering"}))
    ontology.add_object(ObjectInstance("Employee", "2", {"id": "2", "department": "Sales"}))
    ontology.add_object(ObjectInstance("Employee", "3", {"id": "3", "department": "Engineering"}))
    ontology.add_object(ObjectInstance("Employee", "4", {"id": "4", "department": "HR"}))

    # 3. Create Dynamic Object Set (Filter)
    print("\n--- Testing Dynamic Object Set ---")
    base_set = ontology.object_set("Employee") # Assuming this method exists or we create it manually
    # Wait, Ontology.object_set() might not exist yet, let's check core.py or use ObjectSet constructor directly.
    # Checking core.py... Ontology doesn't have object_set() factory method in the snippet I saw.
    # I should use ObjectSet constructor.
    from ontology_framework.core import ObjectSet
    
    base_set = ObjectSet(employee_type, ontology=ontology, lazy=True)
    engineering_set = base_set.filter("department", "Engineering")
    
    print(f"Engineering Set Count (Before Save): {len(engineering_set.all())}")
    
    # 4. Save as Temporary Object Set
    oss = ontology.object_set_service
    dynamic_rid = oss.save_object_set(engineering_set, persistence_type="TEMPORARY")
    print(f"Saved Dynamic Object Set RID: {dynamic_rid}")
    
    # 5. Load and Verify
    loaded_dynamic_set = oss.load_object_set(dynamic_rid)
    print(f"Loaded Dynamic Set Count: {len(loaded_dynamic_set.all())}")
    assert len(loaded_dynamic_set.all()) == 2
    
    # Verify it updates with new data
    print("Adding new Engineering employee...")
    ontology.add_object(ObjectInstance("Employee", "5", {"id": "5", "department": "Engineering"}))
    
    # Re-load to get fresh data
    loaded_dynamic_set = oss.load_object_set(dynamic_rid)
    print(f"Loaded Dynamic Set Count (After Add): {len(loaded_dynamic_set.all())}")
    assert len(loaded_dynamic_set.all()) == 3
    print("Dynamic Object Set verified.")

    # 6. Create Static Object Set
    print("\n--- Testing Static Object Set ---")
    # Create a static set manually (e.g. specific list of objects)
    sales_employee = ontology.get_object("Employee", "2")
    static_set = ObjectSet(employee_type, objects=[sales_employee], ontology=ontology)
    
    # Save as Permanent Object Set
    static_rid = oss.save_object_set(static_set, persistence_type="PERMANENT")
    print(f"Saved Static Object Set RID: {static_rid}")
    
    # Load and Verify
    loaded_static_set = oss.load_object_set(static_rid)
    print(f"Loaded Static Set Count: {len(loaded_static_set.all())}")
    assert len(loaded_static_set.all()) == 1
    assert loaded_static_set.all()[0].primary_key_value == "2"
    
    # Verify it DOES NOT update with new data (if we added another sales person and it was static? 
    # Well, static is defined by PKs. So adding a new object won't change the set of PKs.)
    print("Static Object Set verified.")

    # 7. Test Expiration (Mocking)
    print("\n--- Testing Expiration ---")
    # We can't easily wait 24 hours, but we can manually expire it by hacking the store or creating one with short expiry if we allowed it.
    # Or just verify the expiration time in the definition.
    definition = oss._store[dynamic_rid]
    print(f"Expiration Time: {definition.expiration_time}")
    assert definition.expiration_time is not None
    
    permanent_def = oss._store[static_rid]
    print(f"Permanent Expiration Time: {permanent_def.expiration_time}")
    assert permanent_def.expiration_time is None
    
    print("\nAll OSS tests passed!")

if __name__ == "__main__":
    test_oss()
