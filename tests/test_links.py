import unittest

from ontology_framework import (
    LinkType,
    ObjectInstance,
    ObjectSet,
    ObjectType,
    Ontology,
    PropertyType,
)


class TestLinks(unittest.TestCase):
    def setUp(self):
        self.ontology = Ontology()

        # Define Types
        factory = ObjectType(
            api_name="Factory", display_name="Factory", primary_key="id"
        )
        factory.add_property("id", PropertyType.STRING)

        equipment = ObjectType(
            api_name="Equipment", display_name="Equipment", primary_key="id"
        )
        equipment.add_property("id", PropertyType.STRING)

        self.ontology.register_object_type(factory)
        self.ontology.register_object_type(equipment)

        link_type = LinkType(
            api_name="FactoryHasEquipment",
            display_name="Factory Has Equipment",
            source_object_type="Factory",
            target_object_type="Equipment",
        )
        self.ontology.register_link_type(link_type)

        # Create Objects
        f1 = ObjectInstance("Factory", "f1", {"id": "f1"})
        f2 = ObjectInstance("Factory", "f2", {"id": "f2"})
        e1 = ObjectInstance("Equipment", "e1", {"id": "e1"})
        e2 = ObjectInstance("Equipment", "e2", {"id": "e2"})
        e3 = ObjectInstance("Equipment", "e3", {"id": "e3"})

        self.ontology.add_object(f1)
        self.ontology.add_object(f2)
        self.ontology.add_object(e1)
        self.ontology.add_object(e2)
        self.ontology.add_object(e3)

    def test_create_and_get_links(self):
        # Create links: f1 -> e1, f1 -> e2
        self.ontology.create_link("FactoryHasEquipment", "f1", "e1")
        self.ontology.create_link("FactoryHasEquipment", "f1", "e2")

        links = self.ontology.get_all_links()
        self.assertEqual(len(links), 2)
        self.assertEqual(links[0].source_primary_key, "f1")
        self.assertEqual(links[0].target_primary_key, "e1")

    def test_search_around(self):
        # Setup links
        self.ontology.create_link("FactoryHasEquipment", "f1", "e1")
        self.ontology.create_link("FactoryHasEquipment", "f1", "e2")
        self.ontology.create_link("FactoryHasEquipment", "f2", "e3")

        # Start with Factory f1
        f1_obj = self.ontology.get_objects_of_type("Factory")[0]  # f1 is first added
        # Ensure we got f1
        if f1_obj.primary_key_value != "f1":
            f1_obj = [
                o
                for o in self.ontology.get_objects_of_type("Factory")
                if o.primary_key_value == "f1"
            ][0]

        start_set = ObjectSet(
            self.ontology.get_object_type("Factory"), [f1_obj], self.ontology
        )

        # Search around to Equipment
        result_set = start_set.search_around("FactoryHasEquipment")

        self.assertEqual(result_set.object_type.api_name, "Equipment")
        results = result_set.all()
        self.assertEqual(len(results), 2)
        pks = {obj.primary_key_value for obj in results}
        self.assertIn("e1", pks)
        self.assertIn("e2", pks)
        self.assertNotIn("e3", pks)

    def test_search_around_invalid_link(self):
        f1_obj = self.ontology.get_objects_of_type("Factory")[0]
        start_set = ObjectSet(
            self.ontology.get_object_type("Factory"), [f1_obj], self.ontology
        )

        with self.assertRaisesRegex(ValueError, "Link type InvalidLink not found"):
            start_set.search_around("InvalidLink")

    def test_permissions(self):
        # Test with valid permission
        self.ontology.create_link(
            "FactoryHasEquipment",
            "f1",
            "e1",
            user_permissions=["EDIT_LINK_FactoryHasEquipment"],
        )

        # Test with missing permission
        with self.assertRaisesRegex(
            PermissionError, "Missing permission: EDIT_LINK_FactoryHasEquipment"
        ):
            self.ontology.create_link(
                "FactoryHasEquipment", "f1", "e2", user_permissions=["SOME_OTHER_PERM"]
            )

        # Test delete with missing permission
        with self.assertRaisesRegex(
            PermissionError, "Missing permission: EDIT_LINK_FactoryHasEquipment"
        ):
            self.ontology.delete_link(
                "FactoryHasEquipment", "f1", "e1", user_permissions=["SOME_OTHER_PERM"]
            )

        # Test delete with valid permission
        self.ontology.delete_link(
            "FactoryHasEquipment",
            "f1",
            "e1",
            user_permissions=["EDIT_LINK_FactoryHasEquipment"],
        )
        self.assertEqual(len(self.ontology.get_all_links()), 0)


if __name__ == "__main__":
    unittest.main()
