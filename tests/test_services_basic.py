# Services 模块基础测试
# 专注于提高 services.py 的覆盖率

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


class TestActionServiceBasic:
    """ActionService 基础测试用例，专注于覆盖 services.py 的更多行"""

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

        # 注册动作类型到本体
        self.ontology.register_action_type(self.test_action_type)

    def test_action_service_initialization(self):
        """测试ActionService初始化"""
        assert self.service.ontology == self.ontology
        assert len(self.service.action_logs) == 0

    def test_execute_action_type_not_found(self):
        """测试执行不存在的动作类型"""
        with pytest.raises(ValueError) as exc_info:
            self.service.execute_action(
                "nonexistent_action",
                {},
                self.test_principal
            )

        assert "Action type nonexistent_action not found" in str(exc_info.value)

    def test_execute_action_without_permissions(self):
        """测试执行无权限要求的动作"""
        parameters = {"name": "John Doe"}

        with patch('time.time', return_value=1234567890):
            with patch('uuid.uuid4', return_value='test-uuid-456'):
                log = self.service.execute_action(
                    "create_user",
                    parameters,
                    self.test_principal
                )

        # 验证日志被创建
        assert log.action_type_api_name == "create_user"
        assert log.user_id == "user123"
        assert log.timestamp == 1234567890
        assert log.parameters == parameters

        # 验证日志被添加到服务中
        assert len(self.service.action_logs) == 1
        assert self.service.action_logs[0] == log

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

    def test_execute_action_with_permission_granted(self):
        """测试执行带权限要求的动作（权限通过）"""
        # 设置权限
        acl = AccessControlList()
        acl.grant("user123", PermissionType.EDIT)
        self.test_action_type.permissions = acl

        parameters = {"name": "John Doe"}

        with patch('time.time', return_value=1234567890):
            with patch('uuid.uuid4', return_value='test-uuid-789'):
                log = self.service.execute_action(
                    "create_user",
                    parameters,
                    self.test_principal
                )

        assert log.action_type_api_name == "create_user"
        assert log.user_id == "user123"

    def test_execute_action_missing_required_parameter(self):
        """测试执行动作时缺少必需参数"""
        # name 是必需参数，但我们不提供
        parameters = {}

        with pytest.raises(ValueError) as exc_info:
            self.service.execute_action(
                "create_user",
                parameters,
                self.test_principal
            )

        assert "Missing required parameter: name" in str(exc_info.value)

    def test_execute_action_with_logic(self):
        """测试执行带逻辑的动作"""
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
        # 创建模拟Webhook副作用，确保它有url属性但没有recipients属性
        mock_webhook = Mock()
        mock_webhook.url = "https://api.example.com/webhook"
        mock_webhook.method = "POST"
        # 确保没有recipients属性
        del mock_webhook.recipients

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
        # 执行多个动作
        for i in range(3):
            parameters = {"name": f"User {i}"}
            with patch('time.time', return_value=1234567890 + i):
                with patch('uuid.uuid4', return_value=f'test-uuid-{i}'):
                    log = self.service.execute_action(
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
        # 创建会变更context的逻辑
        def test_logic(context, **kwargs):
            # 使用正确的create_object调用方式
            context.create_object("user", kwargs["name"], {})

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