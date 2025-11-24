# 模块间集成测试
# 测试 core、services、applications、exceptions、logging 等模块之间的集成

import pytest
import time
import uuid
from unittest.mock import Mock, patch
import io

from ontology_framework.core import (
    ObjectType,
    ObjectInstance,
    ObjectSet,
    ActionType,
    Ontology,
    PropertyType,
)
from ontology_framework.services import ObjectSetService, ActionService
from ontology_framework.applications import ObjectView, ObjectExplorer, Quiver
from ontology_framework.permissions import AccessControlList, Principal, PermissionType
from ontology_framework.exceptions import (
    OntologyError,
    ValidationError,
    PermissionError,
    NotFoundError,
    ErrorCategory,
    ErrorSeverity
)
from ontology_framework.logging_config import (
    OntologyLogger,
    LoggingContext,
    main_logger,
    get_logger
)


class TestCoreServicesIntegration:
    """测试核心模块与服务模块的集成"""

    def setup_method(self):
        """每个测试前的设置"""
        self.ontology = Ontology()
        self.object_set_service = ObjectSetService()
        self.action_service = ActionService(self.ontology)

        # 创建测试对象类型
        self.employee_type = ObjectType(
            api_name="employee",
            display_name="Employee",
            primary_key="id"
        )
        self.employee_type.add_property("id", PropertyType.STRING)
        self.employee_type.add_property("name", PropertyType.STRING)
        self.employee_type.add_property("department", PropertyType.STRING)
        self.employee_type.add_property("salary", PropertyType.STRING)

        # 注册对象类型
        self.ontology.register_object_type(self.employee_type)

        # 创建测试动作类型
        self.hire_action = ActionType(
            api_name="hire_employee",
            display_name="Hire Employee",
            target_object_types=["employee"]
        )
        self.hire_action.add_parameter("name", "string", required=True)
        self.hire_action.add_parameter("department", "string", required=True)
        self.hire_action.add_parameter("salary", "string", required=False)

        # 注册动作类型
        self.ontology.register_action_type(self.hire_action)

    def test_ontology_object_set_service_integration(self):
        """测试Ontology与ObjectSetService的集成"""
        # 创建对象实例
        employee = ObjectInstance(
            object_type_api_name="employee",
            primary_key_value="emp001",
            property_values={
                "id": "emp001",
                "name": "Alice",
                "department": "Engineering",
                "salary": "100000"
            }
        )

        # 索引对象
        self.object_set_service.index_object(employee)

        # 获取对象集
        object_set = self.object_set_service.get_base_object_set(self.employee_type)

        # 验证对象集
        assert len(object_set.all()) == 1
        assert object_set.all()[0].primary_key_value == "emp001"
        assert object_set.object_type == self.employee_type

    def test_ontology_action_service_integration(self):
        """测试Ontology与ActionService的集成"""
        principal = Principal("manager", "manager")

        # 创建动作逻辑
        def hire_logic(context, **kwargs):
            # 在上下文中创建新员工对象
            context.create_object("employee", kwargs["name"], kwargs)

        self.hire_action.logic = hire_logic

        # 执行动作
        with patch('time.time', return_value=1234567890):
            with patch('uuid.uuid4', return_value='action-uuid-123'):
                log = self.action_service.execute_action(
                    "hire_employee",
                    {
                        "name": "Bob",
                        "department": "Finance",
                        "salary": "80000"
                    },
                    principal
                )

        # 验证动作执行
        assert log.action_type_api_name == "hire_employee"
        assert log.user_id == "manager"
        assert log.parameters["name"] == "Bob"
        assert log.changes is not None

    def test_services_search_integration(self):
        """测试服务模块搜索功能的集成"""
        # 创建多个员工
        employees = [
            ObjectInstance(
                object_type_api_name="employee",
                primary_key_value="emp001",
                property_values={
                    "id": "emp001",
                    "name": "Alice Johnson",
                    "department": "Engineering",
                    "salary": "100000"
                }
            ),
            ObjectInstance(
                object_type_api_name="employee",
                primary_key_value="emp002",
                property_values={
                    "id": "emp002",
                    "name": "Bob Smith",
                    "department": "Finance",
                    "salary": "80000"
                }
            ),
            ObjectInstance(
                object_type_api_name="employee",
                primary_key_value="emp003",
                property_values={
                    "id": "emp003",
                    "name": "Charlie Brown",
                    "department": "Engineering",
                    "salary": "90000"
                }
            )
        ]

        # 索引所有员工
        for emp in employees:
            self.object_set_service.index_object(emp)

        # 测试搜索功能
        engineering_results = self.object_set_service.search(self.employee_type, "Engineering")
        assert len(engineering_results.all()) == 2

        alice_results = self.object_set_service.search(self.employee_type, "Alice")
        assert len(alice_results.all()) == 1
        assert alice_results.all()[0].property_values["name"] == "Alice Johnson"

    def test_permissions_integration(self):
        """测试权限系统集成"""
        # 设置权限
        acl = AccessControlList()
        acl.grant("hr_manager", PermissionType.VIEW)
        acl.grant("hr_manager", PermissionType.EDIT)
        self.employee_type.permissions = acl

        # 创建员工
        employee = ObjectInstance(
            object_type_api_name="employee",
            primary_key_value="emp001",
            property_values={
                "id": "emp001",
                "name": "Alice",
                "department": "HR"
            }
        )
        self.object_set_service.index_object(employee)

        # 测试有权限的用户
        object_set = self.object_set_service.get_base_object_set(
            self.employee_type,
            principal_id="hr_manager"
        )
        assert len(object_set.all()) == 1

        # 测试无权限的用户
        with pytest.raises(PermissionError):
            self.object_set_service.get_base_object_set(
                self.employee_type,
                principal_id="unauthorized_user"
            )


class TestApplicationsServicesIntegration:
    """测试应用层与服务层的集成"""

    def setup_method(self):
        """每个测试前的设置"""
        self.ontology = Ontology()
        self.object_set_service = ObjectSetService()
        self.explorer = ObjectExplorer()

        # 创建产品对象类型
        self.product_type = ObjectType(
            api_name="product",
            display_name="Product",
            primary_key="id"
        )
        self.product_type.add_property("id", PropertyType.STRING)
        self.product_type.add_property("name", PropertyType.STRING)
        self.product_type.add_property("price", PropertyType.STRING)
        self.product_type.add_property("category", PropertyType.STRING)

        self.ontology.register_object_type(self.product_type)

        # 创建产品视图
        self.product_view = ObjectView(
            object_type=self.product_type,
            title="产品列表视图",
            widgets=["表格", "价格图表", "分类过滤器"]
        )
        self.explorer.register_view(self.product_view)

    def test_object_explorer_service_integration(self):
        """测试ObjectExplorer与ObjectSetService的集成"""
        # 创建产品数据
        products = [
            ObjectInstance(
                object_type_api_name="product",
                primary_key_value="p001",
                property_values={
                    "id": "p001",
                    "name": "Laptop",
                    "price": "999.99",
                    "category": "Electronics"
                }
            ),
            ObjectInstance(
                object_type_api_name="product",
                primary_key_value="p002",
                property_values={
                    "id": "p002",
                    "name": "Mouse",
                    "price": "29.99",
                    "category": "Electronics"
                }
            )
        ]

        # 索引产品
        for product in products:
            self.object_set_service.index_object(product)

        # 获取产品集
        product_set = self.object_set_service.get_base_object_set(self.product_type)

        # 使用探索器打开视图
        captured_output = io.StringIO()
        with patch('sys.stdout', captured_output):
            self.explorer.open("product", product_set)

        output = captured_output.getvalue()

        # 验证自定义视图被使用
        assert "--- Object View: 产品列表视图 ---" in output
        assert "Object Type: Product" in output
        assert "Total Objects: 2" in output
        assert "- [Widget] 表格" in output

    def test_quiver_service_integration(self):
        """测试Quiver与ObjectSetService的集成"""
        # 创建大量产品数据用于分析
        products = []
        for i in range(10):
            product = ObjectInstance(
                object_type_api_name="product",
                primary_key_value=f"p{i:03d}",
                property_values={
                    "id": f"p{i:03d}",
                    "name": f"Product {i}",
                    "price": f"{i * 10}.99",
                    "category": f"Category {i % 3}"
                }
            )
            products.append(product)
            self.object_set_service.index_object(product)

        # 获取产品集
        product_set = self.object_set_service.get_base_object_set(self.product_type)

        # 使用Quiver分析
        quiver = Quiver()
        captured_output = io.StringIO()
        with patch('sys.stdout', captured_output):
            quiver.analyze(product_set)

        output = captured_output.getvalue()

        # 验证分析输出
        assert "--- Quiver Analysis ---" in output
        assert "Analyzing 10 objects of type product" in output
        assert "Generating charts... [Done]" in output


class TestExceptionsServicesIntegration:
    """测试异常处理与服务模块的集成"""

    def setup_method(self):
        """每个测试前的设置"""
        self.ontology = Ontology()
        self.action_service = ActionService(self.ontology)

        # 创建测试对象类型
        self.user_type = ObjectType(
            api_name="user",
            display_name="User",
            primary_key="id"
        )
        self.user_type.add_property("id", PropertyType.STRING)
        self.user_type.add_property("email", PropertyType.STRING)

        self.ontology.register_object_type(self.user_type)

        # 创建测试动作类型
        self.create_user_action = ActionType(
            api_name="create_user",
            display_name="Create User",
            target_object_types=["user"]
        )
        self.create_user_action.add_parameter("email", "string", required=True)
        self.create_user_action.add_parameter("name", "string", required=True)

        self.ontology.register_action_type(self.create_user_action)

    def test_action_service_error_handling(self):
        """测试ActionService中的错误处理"""
        principal = Principal("admin", "admin")

        # 测试找不到动作类型的错误
        with pytest.raises(ValueError) as exc_info:
            self.action_service.execute_action("nonexistent_action", {}, principal)

        assert "Action type nonexistent_action not found" in str(exc_info.value)

        # 测试缺少必需参数的错误
        with pytest.raises(ValueError) as exc_info:
            self.action_service.execute_action("create_user", {"email": "test@example.com"}, principal)

        assert "Missing required parameter: name" in str(exc_info.value)

    def test_permission_error_integration(self):
        """测试权限错误的集成"""
        # 设置权限
        acl = AccessControlList()
        acl.grant("admin", PermissionType.EDIT)
        self.create_user_action.permissions = acl

        # 测试权限不足的用户
        unauthorized_user = Principal("user", "user")
        with pytest.raises(PermissionError) as exc_info:
            self.action_service.execute_action(
                "create_user",
                {"email": "test@example.com", "name": "Test User"},
                unauthorized_user
            )

        assert "does not have permission to execute action create_user" in str(exc_info.value)
        assert "user" in str(exc_info.value)


class TestLoggingServicesIntegration:
    """测试日志系统与服务模块的集成"""

    def setup_method(self):
        """每个测试前的设置"""
        self.ontology = Ontology()
        self.action_service = ActionService(self.ontology)
        self.logger = get_logger("integration_test")

        # 创建测试对象类型
        self.task_type = ObjectType(
            api_name="task",
            display_name="Task",
            primary_key="id"
        )
        self.task_type.add_property("id", PropertyType.STRING)
        self.task_type.add_property("title", PropertyType.STRING)

        self.ontology.register_object_type(self.task_type)

        # 创建测试动作
        self.create_task_action = ActionType(
            api_name="create_task",
            display_name="Create Task",
            target_object_types=["task"]
        )
        self.create_task_action.add_parameter("title", "string", required=True)

        self.ontology.register_action_type(self.create_task_action)

    def test_action_service_logging(self):
        """测试ActionService的日志集成"""
        principal = Principal("manager", "manager")

        # 使用日志上下文执行动作
        with LoggingContext(user_id="manager", operation="create_task"):
            with patch('time.time', return_value=1234567890):
                with patch('uuid.uuid4', return_value='task-uuid-123'):
                    log = self.action_service.execute_action(
                        "create_task",
                        {"title": "Complete integration test"},
                        principal
                    )

        # 验证日志记录
        assert log.action_type_api_name == "create_task"
        assert log.user_id == "manager"
        assert log.parameters["title"] == "Complete integration test"

    def test_object_set_service_logging(self):
        """测试ObjectSetService的日志集成"""
        # 创建对象
        task = ObjectInstance(
            object_type_api_name="task",
            primary_key_value="task001",
            property_values={
                "id": "task001",
                "title": "Test Task"
            }
        )

        # 使用日志上下文索引对象
        with LoggingContext(operation="index_object"):
            self.object_set_service = ObjectSetService()
            self.object_set_service.index_object(task)

        # 验证对象被索引
        object_set = self.object_set_service.get_base_object_set(self.task_type)
        assert len(object_set.all()) == 1


class TestFullWorkflowIntegration:
    """完整工作流集成测试"""

    def test_complete_employee_management_workflow(self):
        """测试完整的员工管理工作流"""
        # 1. 初始化系统
        ontology = Ontology()
        object_service = ObjectSetService()
        action_service = ActionService(ontology)
        explorer = ObjectExplorer()
        quiver = Quiver()

        # 2. 定义员工对象类型
        employee_type = ObjectType(
            api_name="employee",
            display_name="Employee",
            primary_key="id"
        )
        employee_type.add_property("id", PropertyType.STRING)
        employee_type.add_property("name", PropertyType.STRING)
        employee_type.add_property("department", PropertyType.STRING)
        employee_type.add_property("position", PropertyType.STRING)

        ontology.register_object_type(employee_type)

        # 3. 创建员工视图
        employee_view = ObjectView(
            object_type=employee_type,
            title="员工管理视图",
            widgets=["员工列表", "部门统计", "职级分布"]
        )
        explorer.register_view(employee_view)

        # 4. 定义招聘动作
        hire_action = ActionType(
            api_name="hire_employee",
            display_name="Hire Employee",
            target_object_types=["employee"]
        )
        hire_action.add_parameter("name", "string", required=True)
        hire_action.add_parameter("department", "string", required=True)
        hire_action.add_parameter("position", "string", required=True)

        def hire_logic(context, **kwargs):
            # 模拟招聘逻辑：创建员工记录
            emp_id = f"emp_{int(time.time())}"
            context.create_object("employee", emp_id, kwargs)

        hire_action.logic = hire_logic
        ontology.register_action_type(hire_action)

        # 5. 执行招聘动作
        hr_manager = Principal("hr_manager", "hr")

        with patch('time.time', return_value=1234567890):
            with patch('uuid.uuid4', return_value='hire-uuid-123'):
                hire_log = action_service.execute_action(
                    "hire_employee",
                    {
                        "name": "John Doe",
                        "department": "Engineering",
                        "position": "Software Engineer"
                    },
                    hr_manager
                )

        # 6. 验证动作执行结果
        assert hire_log.action_type_api_name == "hire_employee"
        assert hire_log.user_id == "hr_manager"
        assert hire_log.parameters["name"] == "John Doe"
        assert hire_log.changes is not None

        # 7. 创建实际员工对象用于演示
        employee = ObjectInstance(
            object_type_api_name="employee",
            primary_key_value="emp123",
            property_values={
                "id": "emp123",
                "name": "John Doe",
                "department": "Engineering",
                "position": "Software Engineer"
            }
        )

        # 8. 索引员工对象
        object_service.index_object(employee)

        # 9. 获取员工集合
        employee_set = object_service.get_base_object_set(employee_type)

        # 10. 使用视图展示员工
        captured_output = io.StringIO()
        with patch('sys.stdout', captured_output):
            explorer.open("employee", employee_set)

        view_output = captured_output.getvalue()
        assert "--- Object View: 员工管理视图 ---" in view_output
        assert "Object Type: Employee" in view_output
        assert "Total Objects: 1" in view_output

        # 11. 使用Quiver分析员工数据
        analysis_output = io.StringIO()
        with patch('sys.stdout', analysis_output):
            quiver.analyze(employee_set)

        analysis_result = analysis_output.getvalue()
        assert "--- Quiver Analysis ---" in analysis_result
        assert "Analyzing 1 objects of type employee" in analysis_result

        # 12. 验证整个工作流完成
        assert len(employee_set.all()) == 1
        assert employee_set.all()[0].property_values["name"] == "John Doe"
        assert employee_set.all()[0].property_values["department"] == "Engineering"