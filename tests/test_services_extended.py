# Services 模块扩展测试
# 专门用于提升 services.py 的测试覆盖率

import pytest
import time
import uuid
from unittest.mock import Mock, patch

from ontology_framework.services import ObjectSetService, ActionService
from ontology_framework.core import (
    ObjectType,
    ObjectInstance,
    ActionContext,
    ActionType,
    Ontology,
    PropertyType,
)
from ontology_framework.permissions import AccessControlList, Principal, PermissionType


class TestObjectSetServiceExtended:
    """ObjectSetService 扩展测试用例"""

    def setup_method(self):
        """每个测试前的设置"""
        self.service = ObjectSetService()
        self.test_object_type = ObjectType(
            api_name="test_user",
            display_name="Test User",
            primary_key="id"
        )
        self.test_object_type.add_property("id", PropertyType.STRING)
        self.test_object_type.add_property("name", PropertyType.STRING)
        self.test_object_type.add_property("email", PropertyType.STRING)

        # 创建测试对象
        self.test_obj1 = ObjectInstance(
            object_type_api_name="test_user",
            primary_key_value="user1",
            property_values={
                "id": "user1",
                "name": "Alice",
                "email": "alice@example.com"
            }
        )
        self.test_obj2 = ObjectInstance(
            object_type_api_name="test_user",
            primary_key_value="user2",
            property_values={
                "id": "user2",
                "name": "Bob",
                "email": "bob@example.com"
            }
        )
        self.test_obj3 = ObjectInstance(
            object_type_api_name="test_user",
            primary_key_value="user3",
            property_values={
                "id": "user3",
                "name": "Charlie",
                "email": "charlie@example.org"
            }
        )

    def test_index_object_single(self):
        """测试单个对象索引"""
        self.service.index_object(self.test_obj1)

        # 验证存储
        assert "test_user" in self.service._storage
        assert len(self.service._storage["test_user"]) == 1
        assert self.service._storage["test_user"][0] == self.test_obj1

        # 验证索引
        assert "test_user" in self.service._index
        assert "id" in self.service._index["test_user"]
        assert "name" in self.service._index["test_user"]
        assert "email" in self.service._index["test_user"]
        assert self.test_obj1 in self.service._index["test_user"]["name"]["Alice"]

    def test_index_multiple_objects(self):
        """测试多个对象索引"""
        objects = [self.test_obj1, self.test_obj2, self.test_obj3]

        for obj in objects:
            self.service.index_object(obj)

        # 验证所有对象都被存储
        assert len(self.service._storage["test_user"]) == 3

        # 验证索引正确性
        assert "Alice" in self.service._index["test_user"]["name"]
        assert "Bob" in self.service._index["test_user"]["name"]
        assert "Charlie" in self.service._index["test_user"]["name"]

        # 验证相同值的对象在同一索引列表中
        alice_objects = self.service._index["test_user"]["email"]["alice@example.com"]
        assert len(alice_objects) == 1
        assert alice_objects[0] == self.test_obj1

    def test_index_objects_with_same_property_values(self):
        """测试具有相同属性值的对象索引"""
        # 创建具有相同名称的对象
        duplicate_obj = ObjectInstance(
            object_type_api_name="test_user",
            primary_key_value="user4",
            property_values={
                "id": "user4",
                "name": "Alice",  # 与 test_obj1 相同
                "email": "alice2@example.com"
            }
        )

        self.service.index_object(self.test_obj1)
        self.service.index_object(duplicate_obj)

        # 验证两个对象都在同一个索引值下
        alice_objects = self.service._index["test_user"]["name"]["Alice"]
        assert len(alice_objects) == 2
        assert self.test_obj1 in alice_objects
        assert duplicate_obj in alice_objects

    def test_get_base_object_set_without_permission_check(self):
        """测试获取基础对象集（无权限检查）"""
        self.service.index_object(self.test_obj1)
        self.service.index_object(self.test_obj2)

        object_set = self.service.get_base_object_set(self.test_object_type)

        assert len(object_set.all()) == 2
        assert object_set.object_type == self.test_object_type

    def test_get_base_object_set_with_permission_granted(self):
        """测试获取基础对象集（权限检查通过）"""
        # 设置权限
        acl = AccessControlList()
        acl.grant("user123", PermissionType.VIEW)
        self.test_object_type.permissions = acl

        self.service.index_object(self.test_obj1)

        object_set = self.service.get_base_object_set(self.test_object_type, principal_id="user123")

        assert len(object_set.all()) == 1

    def test_get_base_object_set_with_permission_denied(self):
        """测试获取基础对象集（权限检查失败）"""
        # 设置权限
        acl = AccessControlList()
        acl.grant("user456", PermissionType.VIEW)  # 只给 user456 权限
        self.test_object_type.permissions = acl

        self.service.index_object(self.test_obj1)

        # 使用未授权的用户ID应该抛出异常
        with pytest.raises(PermissionError) as exc_info:
            self.service.get_base_object_set(self.test_object_type, principal_id="user789")

        assert "does not have VIEW permission" in str(exc_info.value)
        assert "user789" in str(exc_info.value)

    def test_get_base_object_set_empty_storage(self):
        """测试从空存储中获取对象集"""
        object_set = self.service.get_base_object_set(self.test_object_type)

        assert len(object_set.all()) == 0
        assert object_set.object_type == self.test_object_type

    def test_search_with_exact_match(self):
        """测试搜索功能（精确匹配）"""
        self.service.index_object(self.test_obj1)
        self.service.index_object(self.test_obj2)

        result_set = self.service.search(self.test_object_type, "Alice")

        assert len(result_set.all()) == 1
        assert result_set.all()[0].primary_key_value == "user1"

    def test_search_with_partial_match(self):
        """测试搜索功能（部分匹配）"""
        self.service.index_object(self.test_obj1)
        self.service.index_object(self.test_obj2)
        self.service.index_object(self.test_obj3)

        result_set = self.service.search(self.test_object_type, "example")

        # 应该匹配 "alice@example.com", "bob@example.com" 和 "charlie@example.org"
        assert len(result_set.all()) == 3

    def test_search_case_insensitive(self):
        """测试搜索功能（大小写不敏感）"""
        self.service.index_object(self.test_obj1)

        result_set_lower = self.service.search(self.test_object_type, "alice")
        result_set_upper = self.service.search(self.test_object_type, "ALICE")

        # 两次搜索都应该返回相同结果
        assert len(result_set_lower.all()) == 1
        assert len(result_set_upper.all()) == 1
        assert result_set_lower.all()[0].primary_key_value == "user1"
        assert result_set_upper.all()[0].primary_key_value == "user1"

    def test_search_no_results(self):
        """测试搜索功能（无结果）"""
        self.service.index_object(self.test_obj1)

        result_set = self.service.search(self.test_object_type, "nonexistent")

        assert len(result_set.all()) == 0

    def test_search_empty_storage(self):
        """测试在空存储中搜索"""
        result_set = self.service.search(self.test_object_type, "anything")

        assert len(result_set.all()) == 0

    def test_search_across_all_properties(self):
        """测试搜索功能（跨所有属性搜索）"""
        self.service.index_object(self.test_obj1)

        # 在不同属性中搜索应该都能找到
        name_result = self.service.search(self.test_object_type, "Alice")
        email_result = self.service.search(self.test_object_type, "alice@example.com")
        id_result = self.service.search(self.test_object_type, "user1")

        assert len(name_result.all()) == 1
        assert len(email_result.all()) == 1
        assert len(id_result.all()) == 1

        # 应该都是同一个对象
        assert name_result.all()[0].primary_key_value == "user1"
        assert email_result.all()[0].primary_key_value == "user1"
        assert id_result.all()[0].primary_key_value == "user1"


class TestActionServiceExtended:
    """ActionService 扩展测试用例"""

    def setup_method(self):
        """每个测试前的设置"""
        self.ontology = Ontology()
        self.service = ActionService(self.ontology)
        self.test_principal = Principal("user123", "user")

        # 首先创建并注册目标对象类型
        self.target_user_type = ObjectType(
            api_name="user",
            display_name="User",
            primary_key="id"
        )
        self.ontology.register_object_type(self.target_user_type)

        # 创建测试动作类型
        self.test_action_type = ActionType(
            api_name="create_user",
            display_name="Create User",
            target_object_types=["user"]
        )
        self.test_action_type.add_parameter("name", "string", required=True)
        self.test_action_type.add_parameter("email", "string", required=False)

        # 注册动作类型到本体
        self.ontology.register_action_type(self.test_action_type)

    def test_action_service_initialization(self):
        """测试ActionService初始化"""
        assert self.service.ontology == self.ontology
        assert len(self.service.action_logs) == 0

    def test_execute_action_success(self):
        """测试成功执行动作"""
        # 设置权限
        acl = AccessControlList()
        acl.grant("user123", PermissionType.EDIT)
        self.test_action_type.permissions = acl

        parameters = {"name": "John Doe", "email": "john@example.com"}

        with patch('time.time', return_value=1234567890):
            with patch('uuid.uuid4', return_value='test-uuid-123'):
                log = self.service.execute_action(
                    "create_user",
                    parameters,
                    self.test_principal
                )

        # 验证日志
        assert log.id == "test-uuid-123"
        assert log.action_type_api_name == "create_user"
        assert log.user_id == "user123"
        assert log.timestamp == 1234567890
        assert log.parameters == parameters

        # 验证日志被添加到服务中
        assert len(self.service.action_logs) == 1
        assert self.service.action_logs[0] == log

    def test_execute_action_type_not_found(self):
        """测试执行不存在的动作类型"""
        with pytest.raises(ValueError) as exc_info:
            self.service.execute_action(
                "nonexistent_action",
                {},
                self.test_principal
            )

        assert "Action type nonexistent_action not found" in str(exc_info.value)

    def test_execute_action_permission_denied(self):
        """测试执行动作时权限不足"""
        # 设置权限但不给当前用户
        acl = AccessControlList()
        acl.grant("other_user", PermissionType.EDIT)
        self.test_action_type.permissions = acl

        parameters = {"name": "John Doe"}

        with pytest.raises(PermissionError) as exc_info:
            self.service.execute_action(
                "create_user",
                parameters,
                self.test_principal
            )

        assert "does not have permission to execute action create_user" in str(exc_info.value)
        assert "user123" in str(exc_info.value)

    def test_execute_action_without_permissions(self):
        """测试执行无权限要求的动作"""
        # 不设置权限
        parameters = {"name": "John Doe"}

        with patch('time.time', return_value=1234567890):
            with patch('uuid.uuid4', return_value='test-uuid-456'):
                log = self.service.execute_action(
                    "create_user",
                    parameters,
                    self.test_principal
                )

        # 应该成功执行
        assert log.action_type_api_name == "create_user"
        assert log.user_id == "user123"

    def test_execute_action_missing_required_parameter(self):
        """测试执行动作时缺少必需参数"""
        # name 是必需参数，但我们不提供
        parameters = {"email": "john@example.com"}

        with pytest.raises(ValueError) as exc_info:
            self.service.execute_action(
                "create_user",
                parameters,
                self.test_principal
            )

        assert "Missing required parameter: name" in str(exc_info.value)

    def test_execute_action_with_optional_parameters(self):
        """测试执行动作时包含可选参数"""
        # 设置权限
        acl = AccessControlList()
        acl.grant("user123", PermissionType.EDIT)
        self.test_action_type.permissions = acl

        # 只提供必需参数
        parameters_required_only = {"name": "Jane Doe"}

        with patch('time.time', return_value=1234567890):
            with patch('uuid.uuid4', return_value='test-uuid-789'):
                log = self.service.execute_action(
                    "create_user",
                    parameters_required_only,
                    self.test_principal
                )

        assert log.parameters == parameters_required_only

    def test_execute_action_with_all_parameters(self):
        """测试执行动作时提供所有参数"""
        # 设置权限
        acl = AccessControlList()
        acl.grant("user123", PermissionType.EDIT)
        self.test_action_type.permissions = acl

        # 提供所有参数
        parameters_all = {
            "name": "Full User",
            "email": "fulluser@example.com"
        }

        with patch('time.time', return_value=1234567890):
            with patch('uuid.uuid4', return_value='test-uuid-full'):
                log = self.service.execute_action(
                    "create_user",
                    parameters_all,
                    self.test_principal
                )

        assert log.parameters == parameters_all

    def test_execute_action_with_logic(self):
        """测试执行带逻辑的动作"""
        # 设置权限
        acl = AccessControlList()
        acl.grant("user123", PermissionType.EDIT)
        self.test_action_type.permissions = acl

        # 创建模拟逻辑
        mock_logic = Mock()
        self.test_action_type.logic = mock_logic

        parameters = {"name": "Logic User"}

        with patch('time.time', return_value=1234567890):
            with patch('uuid.uuid4', return_value='test-uuid-logic'):
                log = self.service.execute_action(
                    "create_user",
                    parameters,
                    self.test_principal
                )

        # 验证逻辑被调用
        mock_logic.assert_called_once()
        # 获取调用的参数（第一个参数是ActionContext）
        call_args = mock_logic.call_args
        assert len(call_args[0]) == 1  # ActionContext
        assert call_args[1] == parameters  # 关键字参数

    def test_execute_action_with_side_effects_notification(self):
        """测试执行带有通知副作用动作"""
        # 设置权限
        acl = AccessControlList()
        acl.grant("user123", PermissionType.EDIT)
        self.test_action_type.permissions = acl

        # 创建模拟通知副作用
        mock_notification = Mock()
        mock_notification.recipients = ["user@example.com"]
        mock_notification.message = "User created successfully"
        self.test_action_type.side_effects = [mock_notification]

        parameters = {"name": "Notified User"}

        with patch('builtins.print') as mock_print:
            with patch('time.time', return_value=1234567890):
                with patch('uuid.uuid4', return_value='test-uuid-notif'):
                    log = self.service.execute_action(
                        "create_user",
                        parameters,
                        self.test_principal
                    )

        # 验证通知被打印
        mock_print.assert_called_with("[Notification] Sending to ['user@example.com']: User created successfully")

    def test_execute_action_with_side_effects_webhook(self):
        """测试执行带有Webhook副作用动作"""
        # 设置权限
        acl = AccessControlList()
        acl.grant("user123", PermissionType.EDIT)
        self.test_action_type.permissions = acl

        # 创建模拟Webhook副作用
        mock_webhook = Mock()
        mock_webhook.url = "https://api.example.com/webhook"
        mock_webhook.method = "POST"
        self.test_action_type.side_effects = [mock_webhook]

        parameters = {"name": "Webhook User"}

        with patch('builtins.print') as mock_print:
            with patch('time.time', return_value=1234567890):
                with patch('uuid.uuid4', return_value='test-uuid-webhook'):
                    log = self.service.execute_action(
                        "create_user",
                        parameters,
                        self.test_principal
                    )

        # 验证Webhook被打印
        mock_print.assert_called_with("[Webhook] POST https://api.example.com/webhook")

    def test_multiple_action_logs_accumulation(self):
        """测试多个动作日志的累积"""
        # 设置权限
        acl = AccessControlList()
        acl.grant("user123", PermissionType.EDIT)
        self.test_action_type.permissions = acl

        # 执行多个动作
        for i in range(3):
            parameters = {"name": f"User {i}"}
            with patch('time.time', return_value=1234567890 + i):
                with patch('uuid.uuid4', return_value=f'test-uuid-{i}'):
                    self.service.execute_action(
                        "create_user",
                        parameters,
                        self.test_principal
                    )

        # 验证所有日志都被保存
        assert len(self.service.action_logs) == 3
        assert self.service.action_logs[0].parameters["name"] == "User 0"
        assert self.service.action_logs[1].parameters["name"] == "User 1"
        assert self.service.action_logs[2].parameters["name"] == "User 2"

    def test_action_context_creation_and_changes(self):
        """测试ActionContext的创建和变更记录"""
        # 设置权限
        acl = AccessControlList()
        acl.grant("user123", PermissionType.EDIT)
        self.test_action_type.permissions = acl

        # 创建会变更context的逻辑
        def test_logic(context, **kwargs):
            context.create_object("test_obj", {"name": kwargs["name"]})

        self.test_action_type.logic = test_logic

        parameters = {"name": "Context Test User"}

        with patch('time.time', return_value=1234567890):
            with patch('uuid.uuid4', return_value='test-uuid-context'):
                log = self.service.execute_action(
                    "create_user",
                    parameters,
                    self.test_principal
                )

        # 验证变更被记录在日志中
        assert log.changes is not None