# 端到端业务流程测试
# 模拟真实业务场景的完整流程

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
from ontology_framework.logging_config import LoggingContext, get_logger
from ontology_framework.exceptions import OntologyError, ErrorSeverity


class TestEcommerceBusinessFlow:
    """电商业务流程端到端测试"""

    def setup_method(self):
        """初始化电商系统"""
        self.ontology = Ontology()
        self.product_service = ObjectSetService()
        self.order_service = ObjectSetService()
        self.action_service = ActionService(self.ontology)
        self.explorer = ObjectExplorer()
        self.quiver = Quiver()
        self.logger = get_logger("ecommerce_system")

        # 设置管理员用户
        self.admin = Principal("admin", "admin")
        self.customer = Principal("customer", "customer")

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
        self.product_type.add_property("stock", PropertyType.STRING)

        # 创建订单对象类型
        self.order_type = ObjectType(
            api_name="order",
            display_name="Order",
            primary_key="id"
        )
        self.order_type.add_property("id", PropertyType.STRING)
        self.order_type.add_property("customer_id", PropertyType.STRING)
        self.order_type.add_property("total_amount", PropertyType.STRING)
        self.order_type.add_property("status", PropertyType.STRING)
        self.order_type.add_property("items", PropertyType.STRING)

        # 创建订单项对象类型
        self.order_item_type = ObjectType(
            api_name="order_item",
            display_name="Order Item",
            primary_key="id"
        )
        self.order_item_type.add_property("id", PropertyType.STRING)
        self.order_item_type.add_property("order_id", PropertyType.STRING)
        self.order_item_type.add_property("product_id", PropertyType.STRING)
        self.order_item_type.add_property("quantity", PropertyType.STRING)
        self.order_item_type.add_property("price", PropertyType.STRING)

        # 注册所有对象类型
        self.ontology.register_object_type(self.product_type)
        self.ontology.register_object_type(self.order_type)
        self.ontology.register_object_type(self.order_item_type)

        # 设置权限
        product_acl = AccessControlList()
        product_acl.grant("admin", PermissionType.EDIT)
        product_acl.grant("customer", PermissionType.VIEW)
        self.product_type.permissions = product_acl

        order_acl = AccessControlList()
        order_acl.grant("admin", PermissionType.EDIT)
        order_acl.grant("customer", PermissionType.VIEW)
        self.order_type.permissions = order_acl

        # 创建业务动作
        self._setup_business_actions()

        # 创建业务视图
        self._setup_business_views()

    def _setup_business_actions(self):
        """设置业务动作"""
        # 添加产品动作
        add_product_action = ActionType(
            api_name="add_product",
            display_name="Add Product",
            target_object_types=["product"]
        )
        add_product_action.add_parameter("name", "string", required=True)
        add_product_action.add_parameter("price", "string", required=True)
        add_product_action.add_parameter("category", "string", required=True)
        add_product_action.add_parameter("stock", "string", required=True)

        def add_product_logic(context, **kwargs):
            product_id = f"prod_{int(time.time())}"
            context.create_object("product", product_id, kwargs)

        add_product_action.logic = add_product_logic
        self.ontology.register_action_type(add_product_action)

        # 创建订单动作
        create_order_action = ActionType(
            api_name="create_order",
            display_name="Create Order",
            target_object_types=["order"]
        )
        create_order_action.add_parameter("customer_id", "string", required=True)
        create_order_action.add_parameter("items", "string", required=True)  # JSON string

        def create_order_logic(context, **kwargs):
            order_id = f"order_{int(time.time())}"
            # 简化逻辑：计算总金额
            total_amount = "100.00"  # 这里应该是基于items计算的真实值
            context.create_object("order", order_id, {
                **kwargs,
                "total_amount": total_amount,
                "status": "pending"
            })

        create_order_action.logic = create_order_logic
        self.ontology.register_action_type(create_order_action)

    def _setup_business_views(self):
        """设置业务视图"""
        # 产品管理视图
        self.product_view = ObjectView(
            object_type=self.product_type,
            title="产品管理视图",
            widgets=["产品列表", "价格分析", "库存监控"]
        )
        self.explorer.register_view(self.product_view)

        # 订单管理视图
        self.order_view = ObjectView(
            object_type=self.order_type,
            title="订单管理视图",
            widgets=["订单列表", "销售统计", "客户分析"]
        )
        self.explorer.register_view(self.order_view)

    def test_complete_ecommerce_flow(self):
        """测试完整的电商业务流程"""
        # Step 1: 管理员添加产品
        with LoggingContext(user_id="admin", operation="product_management"):
            with patch('time.time', return_value=1640995200):  # 2022-01-01
                with patch('uuid.uuid4', return_value='product-uuid-001'):
                    add_log = self.action_service.execute_action(
                        "add_product",
                        {
                            "name": "Laptop Pro",
                            "price": "999.99",
                            "category": "Electronics",
                            "stock": "50"
                        },
                        self.admin
                    )

        # 验证产品添加成功
        assert add_log.action_type_api_name == "add_product"
        assert add_log.parameters["name"] == "Laptop Pro"
        assert add_log.changes is not None

        # Step 2: 创建实际产品对象用于演示
        laptop = ObjectInstance(
            object_type_api_name="product",
            primary_key_value="prod_001",
            property_values={
                "id": "prod_001",
                "name": "Laptop Pro",
                "price": "999.99",
                "category": "Electronics",
                "stock": "50"
            }
        )
        self.product_service.index_object(laptop)

        # 添加更多产品
        products = [
            ObjectInstance(
                object_type_api_name="product",
                primary_key_value="prod_002",
                property_values={
                    "id": "prod_002",
                    "name": "Wireless Mouse",
                    "price": "29.99",
                    "category": "Electronics",
                    "stock": "100"
                }
            ),
            ObjectInstance(
                object_type_api_name="product",
                primary_key_value="prod_003",
                property_values={
                    "id": "prod_003",
                    "name": "USB-C Hub",
                    "price": "49.99",
                    "category": "Electronics",
                    "stock": "75"
                }
            )
        ]

        for product in products:
            self.product_service.index_object(product)

        # Step 3: 管理员查看产品目录
        product_set = self.product_service.get_base_object_set(
            self.product_type,
            principal_id="admin"
        )

        captured_output = io.StringIO()
        with patch('sys.stdout', captured_output):
            self.explorer.open("product", product_set)

        view_output = captured_output.getvalue()
        assert "--- Object View: 产品管理视图 ---" in view_output
        assert "Total Objects: 3" in view_output

        # Step 4: 客户搜索产品
        search_results = self.product_service.search(self.product_type, "Laptop")
        assert len(search_results.all()) == 1
        assert search_results.all()[0].property_values["name"] == "Laptop Pro"

        electronics_results = self.product_service.search(self.product_type, "Electronics")
        assert len(electronics_results.all()) == 3  # 所有产品都是电子产品

        # Step 5: 客户创建订单
        with LoggingContext(user_id="customer", operation="order_creation"):
            with patch('time.time', return_value=1640995300):
                with patch('uuid.uuid4', return_value='order-uuid-001'):
                    order_log = self.action_service.execute_action(
                        "create_order",
                        {
                            "customer_id": "cust_001",
                            "items": '[{"product_id": "prod_001", "quantity": 1}]'
                        },
                        self.customer
                    )

        # 验证订单创建成功
        assert order_log.action_type_api_name == "create_order"
        assert order_log.parameters["customer_id"] == "cust_001"

        # Step 6: 创建实际订单对象
        order = ObjectInstance(
            object_type_api_name="order",
            primary_key_value="order_001",
            property_values={
                "id": "order_001",
                "customer_id": "cust_001",
                "total_amount": "999.99",
                "status": "pending",
                "items": '[{"product_id": "prod_001", "quantity": 1}]'
            }
        )
        self.order_service.index_object(order)

        # Step 7: 管理员查看订单
        order_set = self.order_service.get_base_object_set(
            self.order_type,
            principal_id="admin"
        )

        captured_output = io.StringIO()
        with patch('sys.stdout', captured_output):
            self.explorer.open("order", order_set)

        order_view_output = captured_output.getvalue()
        assert "--- Object View: 订单管理视图 ---" in order_view_output
        assert "Total Objects: 1" in order_view_output

        # Step 8: 生成业务分析报告
        product_analysis = io.StringIO()
        with patch('sys.stdout', product_analysis):
            self.quiver.analyze(product_set)

        analysis_output = product_analysis.getvalue()
        assert "--- Quiver Analysis ---" in analysis_output
        assert "Analyzing 1 objects of type order" in analysis_output

        # Step 9: 验证完整业务流程
        assert len(product_set.all()) == 3
        assert len(order_set.all()) == 1

        # 验证业务数据一致性
        total_products = len(self.product_service.search(self.product_type, "").all())
        total_orders = len(self.order_service.search(self.order_type, "").all())
        assert total_products == 3
        assert total_orders == 1


class TestProjectManagementWorkflow:
    """项目管理业务流程测试"""

    def setup_method(self):
        """初始化项目管理系统"""
        self.ontology = Ontology()
        self.project_service = ObjectSetService()
        self.task_service = ObjectSetService()
        self.action_service = ActionService(self.ontology)
        self.logger = get_logger("project_management")

        # 项目经理和团队成员
        self.project_manager = Principal("pm", "project_manager")
        self.team_member = Principal("dev", "developer")

        # 创建项目对象类型
        self.project_type = ObjectType(
            api_name="project",
            display_name="Project",
            primary_key="id"
        )
        self.project_type.add_property("id", PropertyType.STRING)
        self.project_type.add_property("name", PropertyType.STRING)
        self.project_type.add_property("description", PropertyType.STRING)
        self.project_type.add_property("status", PropertyType.STRING)
        self.project_type.add_property("start_date", PropertyType.STRING)
        self.project_type.add_property("end_date", PropertyType.STRING)

        # 创建任务对象类型
        self.task_type = ObjectType(
            api_name="task",
            display_name="Task",
            primary_key="id"
        )
        self.task_type.add_property("id", PropertyType.STRING)
        self.task_type.add_property("project_id", PropertyType.STRING)
        self.task_type.add_property("title", PropertyType.STRING)
        self.task_type.add_property("description", PropertyType.STRING)
        self.task_type.add_property("status", PropertyType.STRING)
        self.task_type.add_property("assignee", PropertyType.STRING)
        self.task_type.add_property("priority", PropertyType.STRING)

        # 注册对象类型
        self.ontology.register_object_type(self.project_type)
        self.ontology.register_object_type(self.task_type)

        # 设置权限
        project_acl = AccessControlList()
        project_acl.grant("pm", PermissionType.EDIT)
        project_acl.grant("dev", PermissionType.VIEW)
        self.project_type.permissions = project_acl

        task_acl = AccessControlList()
        task_acl.grant("pm", PermissionType.EDIT)
        task_acl.grant("dev", PermissionType.EDIT)  # 开发者可以编辑任务
        self.task_type.permissions = task_acl

        # 创建项目管理动作
        self._setup_project_actions()

    def _setup_project_actions(self):
        """设置项目管理动作"""
        # 创建项目动作
        create_project_action = ActionType(
            api_name="create_project",
            display_name="Create Project",
            target_object_types=["project"]
        )
        create_project_action.add_parameter("name", "string", required=True)
        create_project_action.add_parameter("description", "string", required=True)

        def create_project_logic(context, **kwargs):
            project_id = f"proj_{int(time.time())}"
            context.create_object("project", project_id, {
                **kwargs,
                "status": "active",
                "start_date": "2024-01-01"
            })

        create_project_action.logic = create_project_logic
        self.ontology.register_action_type(create_project_action)

        # 创建任务动作
        create_task_action = ActionType(
            api_name="create_task",
            display_name="Create Task",
            target_object_types=["task"]
        )
        create_task_action.add_parameter("project_id", "string", required=True)
        create_task_action.add_parameter("title", "string", required=True)
        create_task_action.add_parameter("description", "string", required=True)
        create_task_action.add_parameter("assignee", "string", required=True)

        def create_task_logic(context, **kwargs):
            task_id = f"task_{int(time.time())}"
            context.create_object("task", task_id, {
                **kwargs,
                "status": "todo",
                "priority": "medium"
            })

        create_task_action.logic = create_task_logic
        self.ontology.register_action_type(create_task_action)

    def test_project_lifecycle_workflow(self):
        """测试完整的项目生命周期工作流"""
        # Step 1: 项目经理创建项目
        with LoggingContext(user_id="pm", operation="project_creation"):
            with patch('time.time', return_value=1672531200):  # 2023-01-01
                with patch('uuid.uuid4', return_value='project-uuid-001'):
                    project_log = self.action_service.execute_action(
                        "create_project",
                        {
                            "name": "E-commerce Platform",
                            "description": "New e-commerce platform development"
                        },
                        self.project_manager
                    )

        assert project_log.action_type_api_name == "create_project"
        assert project_log.parameters["name"] == "E-commerce Platform"

        # 创建实际项目对象
        project = ObjectInstance(
            object_type_api_name="project",
            primary_key_value="proj_001",
            property_values={
                "id": "proj_001",
                "name": "E-commerce Platform",
                "description": "New e-commerce platform development",
                "status": "active",
                "start_date": "2024-01-01",
                "end_date": None
            }
        )
        self.project_service.index_object(project)

        # Step 2: 项目经理为项目创建任务
        tasks_data = [
            {
                "title": "Design Database Schema",
                "description": "Design and implement database schema",
                "assignee": "dev"
            },
            {
                "title": "Implement User Authentication",
                "description": "Develop user authentication system",
                "assignee": "dev"
            },
            {
                "title": "Create Product Catalog",
                "description": "Implement product catalog functionality",
                "assignee": "dev"
            }
        ]

        for i, task_data in enumerate(tasks_data, 1):
            with LoggingContext(user_id="pm", operation="task_creation"):
                with patch('time.time', return_value=1672531200 + i):
                    with patch('uuid.uuid4', return_value=f'task-uuid-{i:03d}'):
                        task_log = self.action_service.execute_action(
                            "create_task",
                            {
                                "project_id": "proj_001",
                                **task_data
                            },
                            self.project_manager
                        )

                assert task_log.action_type_api_name == "create_task"
                assert task_log.parameters["project_id"] == "proj_001"

            # 创建实际任务对象
            task = ObjectInstance(
                object_type_api_name="task",
                primary_key_value=f"task_{i:03d}",
                property_values={
                    "id": f"task_{i:03d}",
                    "project_id": "proj_001",
                    "title": task_data["title"],
                    "description": task_data["description"],
                    "status": "todo",
                    "assignee": task_data["assignee"],
                    "priority": "medium"
                }
            )
            self.task_service.index_object(task)

        # Step 3: 验证项目和任务数据
        project_set = self.project_service.get_base_object_set(
            self.project_type,
            principal_id="pm"
        )
        task_set = self.task_service.get_base_object_set(
            self.task_type,
            principal_id="pm"
        )

        assert len(project_set.all()) == 1
        assert len(task_set.all()) == 3

        # Step 4: 团队成员查看分配的任务
        dev_task_set = self.task_service.get_base_object_set(
            self.task_type,
            principal_id="dev"
        )
        assert len(dev_task_set.all()) == 3

        # Step 5: 搜索特定任务
        design_tasks = self.task_service.search(self.task_type, "Design")
        assert len(design_tasks.all()) == 1
        assert "Design Database Schema" in design_tasks.all()[0].property_values["title"]

        # Step 6: 验证项目与任务的关联
        all_tasks = task_set.all()
        for task in all_tasks:
            assert task.property_values["project_id"] == "proj_001"
            assert task.property_values["assignee"] == "dev"

        # Step 7: 生成项目报告
        quiver = Quiver()
        project_analysis = io.StringIO()
        with patch('sys.stdout', project_analysis):
            quiver.analyze(project_set)

        analysis_output = project_analysis.getvalue()
        assert "--- Quiver Analysis ---" in analysis_output
        assert "Analyzing 1 objects of type project" in analysis_output

        # Step 8: 生成任务报告
        task_analysis = io.StringIO()
        with patch('sys.stdout', task_analysis):
            quiver.analyze(task_set)

        task_report = task_analysis.getvalue()
        assert "--- Quiver Analysis ---" in task_report
        assert "Analyzing 3 objects of type task" in task_report

        # Step 9: 验证工作流完整性
        project = project_set.all()[0]
        assert project.property_values["name"] == "E-commerce Platform"
        assert project.property_values["status"] == "active"

        # 验证所有任务都属于这个项目
        project_tasks = [t for t in task_set.all() if t.property_values["project_id"] == "proj_001"]
        assert len(project_tasks) == 3

        # 验证业务规则
        high_priority_tasks = [t for t in task_set.all() if t.property_values.get("priority") == "high"]
        assert len(high_priority_tasks) == 0  # 所有任务都是medium优先级


class TestErrorHandlingInBusinessFlow:
    """业务流程中的错误处理测试"""

    def setup_method(self):
        """初始化测试环境"""
        self.ontology = Ontology()
        self.action_service = ActionService(self.ontology)
        self.logger = get_logger("error_handling_test")

        # 创建用户类型
        self.user_type = ObjectType(
            api_name="user",
            display_name="User",
            primary_key="id"
        )
        self.user_type.add_property("id", PropertyType.STRING)
        self.user_type.add_property("email", PropertyType.STRING)
        self.user_type.add_property("username", PropertyType.STRING)

        self.ontology.register_object_type(self.user_type)

        # 设置严格的权限控制
        acl = AccessControlList()
        acl.grant("admin", PermissionType.EDIT)
        self.user_type.permissions = acl

    def test_business_flow_error_recovery(self):
        """测试业务流程中的错误恢复"""
        # 创建需要严格验证的动作
        create_user_action = ActionType(
            api_name="create_user",
            display_name="Create User",
            target_object_types=["user"]
        )
        create_user_action.add_parameter("email", "string", required=True)
        create_user_action.add_parameter("username", "string", required=True)

        def validate_user_logic(context, **kwargs):
            # 业务验证逻辑
            email = kwargs.get("email", "")
            username = kwargs.get("username", "")

            if "@" not in email:
                raise ValidationError("Invalid email format", context={"email": email})

            if len(username) < 3:
                raise ValidationError("Username too short", context={"username": username})

            # 验证通过，创建用户
            user_id = f"user_{int(time.time())}"
            context.create_object("user", user_id, kwargs)

        create_user_action.logic = validate_user_logic
        self.ontology.register_action_type(create_user_action)

        unauthorized_user = Principal("user", "user")
        admin_user = Principal("admin", "admin")

        # 测试1: 权限错误
        with pytest.raises(PermissionError) as exc_info:
            self.action_service.execute_action(
                "create_user",
                {"email": "test@example.com", "username": "testuser"},
                unauthorized_user
            )
        assert "permission to execute action" in str(exc_info.value)

        # 测试2: 数据验证错误 - 无效邮箱
        with pytest.raises(ValidationError) as exc_info:
            self.action_service.execute_action(
                "create_user",
                {"email": "invalid_email", "username": "testuser"},
                admin_user
            )
        assert "Invalid email format" in str(exc_info.value)

        # 测试3: 数据验证错误 - 用户名太短
        with pytest.raises(ValidationError) as exc_info:
            self.action_service.execute_action(
                "create_user",
                {"email": "test@example.com", "username": "ab"},
                admin_user
            )
        assert "Username too short" in str(exc_info.value)

        # 测试4: 成功创建用户
        with patch('time.time', return_value=1672531200):
            with patch('uuid.uuid4', return_value='user-uuid-001'):
                success_log = self.action_service.execute_action(
                    "create_user",
                    {"email": "valid@example.com", "username": "validuser"},
                    admin_user
                )

        assert success_log.action_type_api_name == "create_user"
        assert success_log.parameters["email"] == "valid@example.com"
        assert success_log.changes is not None

    def test_cascade_error_handling(self):
        """测试级联错误处理"""
        # 创建依赖关系复杂的业务动作
        create_order_action = ActionType(
            api_name="create_order",
            display_name="Create Order",
            target_object_types=["order"]  # 假设有order类型
        )
        create_order_action.add_parameter("customer_id", "string", required=True)
        create_order_action.add_parameter("items", "string", required=True)

        def complex_order_logic(context, **kwargs):
            # 模拟复杂的订单处理逻辑
            customer_id = kwargs.get("customer_id")
            items = kwargs.get("items", "[]")

            if not customer_id or not customer_id.startswith("cust_"):
                raise ValidationError("Invalid customer ID format", context={"customer_id": customer_id})

            if not items or items == "[]":
                raise ValidationError("Order cannot be empty", context={"items": items})

            # 模拟可能的系统错误
            import random
            if random.random() < 0.1:  # 10%的几率失败
                raise OntologyError(
                    "Payment processing failed",
                    error_code="PAYMENT_ERROR",
                    severity=ErrorSeverity.HIGH,
                    context={"customer_id": customer_id}
                )

            # 成功创建订单
            order_id = f"order_{int(time.time())}"
            context.create_object("order", order_id, kwargs)

        create_order_action.logic = complex_order_logic
        self.ontology.register_action_type(create_order_action)

        admin_user = Principal("admin", "admin")

        # 测试级联错误
        test_cases = [
            {
                "name": "Invalid Customer ID",
                "params": {"customer_id": "invalid", "items": '[{"product_id": "p1"}]'},
                "expected_error": ValidationError
            },
            {
                "name": "Empty Order",
                "params": {"customer_id": "cust_001", "items": "[]"},
                "expected_error": ValidationError
            }
        ]

        for case in test_cases:
            with pytest.raises(case["expected_error"]):
                self.action_service.execute_action("create_order", case["params"], admin_user)