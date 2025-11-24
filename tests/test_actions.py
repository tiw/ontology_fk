import unittest
from ontology_framework.core import Ontology, ObjectType, PropertyType, ActionType, ObjectInstance
from ontology_framework.services import ActionService
from ontology_framework.permissions import Principal, AccessControlList, PermissionType

class TestActionCapabilities(unittest.TestCase):
    def setUp(self):
        self.ontology = Ontology()
        self.action_service = ActionService(self.ontology)
        
        # Setup Object Type
        self.factory_type = ObjectType(
            api_name="Factory",
            display_name="Factory",
            primary_key="factory_id"
        )
        self.factory_type.add_property("factory_id", PropertyType.STRING)
        self.factory_type.add_property("capacity", PropertyType.INTEGER)
        self.ontology.register_object_type(self.factory_type)
        
        # Setup Principal
        self.admin = Principal("admin_user", ["admin_group"])
        self.user = Principal("regular_user", ["user_group"])

    def test_action_definition_and_registration(self):
        action = ActionType(
            api_name="create_factory",
            display_name="Create Factory",
            target_object_types=["Factory"]
        )
        action.add_parameter("factory_id", PropertyType.STRING)
        action.add_parameter("capacity", PropertyType.INTEGER)
        
        self.ontology.register_action_type(action)
        
        retrieved_action = self.ontology.get_action_type("create_factory")
        self.assertIsNotNone(retrieved_action)
        self.assertEqual(len(retrieved_action.parameters), 2)

    def test_action_execution_create_object(self):
        # Define Action Logic
        def create_factory_logic(context, factory_id, capacity):
            context.create_object("Factory", factory_id, {
                "factory_id": factory_id,
                "capacity": capacity
            })

        action = ActionType(
            api_name="create_factory_action",
            display_name="Create Factory Action",
            target_object_types=["Factory"],
            logic=create_factory_logic
        )
        action.add_parameter("factory_id", PropertyType.STRING)
        action.add_parameter("capacity", PropertyType.INTEGER)
        self.ontology.register_action_type(action)

        # Execute Action
        params = {"factory_id": "F_TEST_1", "capacity": 500}
        log = self.action_service.execute_action("create_factory_action", params, self.admin)

        # Verify Object Created
        obj = self.ontology.get_object("Factory", "F_TEST_1")
        self.assertIsNotNone(obj)
        self.assertEqual(obj.get("capacity"), 500)
        
        # Verify Log
        self.assertEqual(log.action_type_api_name, "create_factory_action")
        self.assertEqual(log.user_id, "admin_user")
        self.assertEqual(len(log.changes), 1)
        self.assertIn("Created object Factory", log.changes[0])

    def test_action_execution_modify_object(self):
        # Setup existing object
        f1 = ObjectInstance("Factory", "F_MOD_1", {"factory_id": "F_MOD_1", "capacity": 100})
        self.ontology.add_object(f1)

        # Define Modify Logic
        def update_capacity_logic(context, factory_id, new_capacity):
            obj = context.get_object("Factory", factory_id)
            if obj:
                context.modify_object(obj, "capacity", new_capacity)
            else:
                raise ValueError("Object not found")

        action = ActionType(
            api_name="update_capacity",
            display_name="Update Capacity",
            target_object_types=["Factory"],
            logic=update_capacity_logic
        )
        action.add_parameter("factory_id", PropertyType.STRING)
        action.add_parameter("new_capacity", PropertyType.INTEGER)
        self.ontology.register_action_type(action)

        # Execute
        self.action_service.execute_action("update_capacity", {"factory_id": "F_MOD_1", "new_capacity": 200}, self.admin)

        # Verify
        obj = self.ontology.get_object("Factory", "F_MOD_1")
        self.assertEqual(obj.get("capacity"), 200)

    def test_parameter_validation(self):
        action = ActionType(
            api_name="param_test",
            display_name="Param Test",
            target_object_types=["Factory"]
        )
        action.add_parameter("req_param", PropertyType.STRING, required=True)
        self.ontology.register_action_type(action)

        with self.assertRaises(ValueError) as cm:
            self.action_service.execute_action("param_test", {}, self.admin)
        self.assertIn("Missing required parameter", str(cm.exception))

    def test_action_permissions(self):
        acl = AccessControlList()
        # Only admin has EDIT permission
        acl.grant("admin_user", PermissionType.EDIT)
        
        action = ActionType(
            api_name="secure_action",
            display_name="Secure Action",
            target_object_types=["Factory"],
            permissions=acl
        )
        self.ontology.register_action_type(action)

        # User without permission should fail
        with self.assertRaises(PermissionError):
            self.action_service.execute_action("secure_action", {}, self.user)
            
        # Admin should succeed (even with empty logic/params)
        try:
            self.action_service.execute_action("secure_action", {}, self.admin)
        except PermissionError:
            self.fail("Admin should have permission")

    def test_side_effects(self):
        from ontology_framework.core import Notification, Webhook
        
        action = ActionType(
            api_name="notify_action",
            display_name="Notify Action",
            target_object_types=["Factory"]
        )
        action.add_side_effect(Notification(recipients=["admin@example.com"], message="Action executed"))
        action.add_side_effect(Webhook(url="https://example.com/webhook"))
        self.ontology.register_action_type(action)

        # Capture stdout to verify print statements (since we just print for now)
        import io
        import sys
        captured_output = io.StringIO()
        sys.stdout = captured_output
        
        self.action_service.execute_action("notify_action", {}, self.admin)
        
        sys.stdout = sys.__stdout__
        output = captured_output.getvalue()
        
        self.assertIn("[Notification] Sending to ['admin@example.com']: Action executed", output)
        self.assertIn("[Webhook] POST https://example.com/webhook", output)

if __name__ == '__main__':
    unittest.main()
