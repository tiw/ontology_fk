# Applications 模块扩展测试
# 专门用于提升 applications.py 的测试覆盖率

import pytest
from unittest.mock import Mock, patch
import io

from ontology_framework.applications import (
    ObjectView,
    ObjectExplorer,
    PivotAggregationPlan,
    Quiver,
    Vertex,
    VertexSimulation,
)
from ontology_framework.core import (
    Function,
    LinkType,
    ObjectType,
    ObjectSet,
    ObjectInstance,
    Ontology,
    PrimitiveType,
    PropertyType,
)


class TestObjectViewExtended:
    """ObjectView 扩展测试用例"""

    def setup_method(self):
        """每个测试前的设置"""
        self.test_object_type = ObjectType(
            api_name="test_product",
            display_name="Test Product",
            primary_key="id"
        )
        self.test_object_type.add_property("id", PropertyType.STRING)
        self.test_object_type.add_property("name", PropertyType.STRING)
        self.test_object_type.add_property("price", PropertyType.STRING)

        self.test_view = ObjectView(
            object_type=self.test_object_type,
            title="产品视图",
            widgets=["表格", "图表", "过滤器"]
        )

        # 创建测试对象集
        self.test_objects = [
            ObjectInstance(
                object_type_api_name="test_product",
                primary_key_value="prod1",
                property_values={
                    "id": "prod1",
                    "name": "产品A",
                    "price": "100"
                }
            ),
            ObjectInstance(
                object_type_api_name="test_product",
                primary_key_value="prod2",
                property_values={
                    "id": "prod2",
                    "name": "产品B",
                    "price": "200"
                }
            )
        ]
        self.test_object_set = ObjectSet(self.test_object_type, self.test_objects)

    def test_object_view_creation(self):
        """测试ObjectView创建"""
        assert self.test_view.object_type == self.test_object_type
        assert self.test_view.title == "产品视图"
        assert len(self.test_view.widgets) == 3
        assert "表格" in self.test_view.widgets
        assert "图表" in self.test_view.widgets
        assert "过滤器" in self.test_view.widgets

    def test_object_view_creation_with_default_widgets(self):
        """测试ObjectView创建（默认widgets）"""
        view = ObjectView(
            object_type=self.test_object_type,
            title="默认视图"
        )

        assert view.widgets == []

    def test_object_view_render_with_objects(self):
        """测试ObjectView渲染（有对象）"""
        # 捕获print输出
        captured_output = io.StringIO()
        with patch('sys.stdout', captured_output):
            self.test_view.render(self.test_object_set)

        output = captured_output.getvalue()

        # 验证输出包含预期内容
        assert "--- Object View: 产品视图 ---" in output
        assert "Object Type: Test Product" in output
        assert "Total Objects: 2" in output
        assert "Widgets:" in output
        assert "- [Widget] 表格" in output
        assert "- [Widget] 图表" in output
        assert "- [Widget] 过滤器" in output
        assert "-------------------------------" in output

    def test_object_view_render_empty_object_set(self):
        """测试ObjectView渲染（空对象集）"""
        empty_object_set = ObjectSet(self.test_object_type, [])

        captured_output = io.StringIO()
        with patch('sys.stdout', captured_output):
            self.test_view.render(empty_object_set)

        output = captured_output.getvalue()

        # 验证输出包含预期内容
        assert "Total Objects: 0" in output

    def test_object_view_render_with_different_object_types(self):
        """测试ObjectView渲染（不同对象类型）"""
        # 创建不同类型的对象
        user_object_type = ObjectType(
            api_name="test_user",
            display_name="Test User",
            primary_key="id"
        )
        user_view = ObjectView(
            object_type=user_object_type,
            title="用户视图"
        )
        user_object_set = ObjectSet(user_object_type, [])

        captured_output = io.StringIO()
        with patch('sys.stdout', captured_output):
            user_view.render(user_object_set)

        output = captured_output.getvalue()

        # 验证输出显示正确的对象类型
        assert "--- Object View: 用户视图 ---" in output
        assert "Object Type: Test User" in output


class TestObjectExplorerExtended:
    """ObjectExplorer 扩展测试用例"""

    def setup_method(self):
        """每个测试前的设置"""
        self.explorer = ObjectExplorer()

        # 创建测试对象类型
        self.test_object_type = ObjectType(
            api_name="test_employee",
            display_name="Test Employee",
            primary_key="id"
        )
        self.test_object_type.add_property("id", PropertyType.STRING)
        self.test_object_type.add_property("name", PropertyType.STRING)

        self.another_object_type = ObjectType(
            api_name="test_department",
            display_name="Test Department",
            primary_key="id"
        )
        self.another_object_type.add_property("id", PropertyType.STRING)
        self.another_object_type.add_property("name", PropertyType.STRING)

        # 创建测试视图
        self.employee_view = ObjectView(
            object_type=self.test_object_type,
            title="员工视图",
            widgets=["列表", "详情"]
        )
        self.department_view = ObjectView(
            object_type=self.another_object_type,
            title="部门视图",
            widgets=["组织结构"]
        )

        # 创建测试对象
        self.test_objects = [
            ObjectInstance(
                object_type_api_name="test_employee",
                primary_key_value="emp1",
                property_values={
                    "id": "emp1",
                    "name": "张三"
                }
            ),
            ObjectInstance(
                object_type_api_name="test_employee",
                primary_key_value="emp2",
                property_values={
                    "id": "emp2",
                    "name": "李四"
                }
            )
        ]
        self.test_object_set = ObjectSet(self.test_object_type, self.test_objects)

    def test_object_explorer_initialization(self):
        """测试ObjectExplorer初始化"""
        assert self.explorer.views == {}

    def test_register_view(self):
        """测试注册视图"""
        self.explorer.register_view(self.employee_view)

        assert len(self.explorer.views) == 1
        assert "test_employee" in self.explorer.views
        assert self.explorer.views["test_employee"] == self.employee_view

    def test_register_multiple_views(self):
        """测试注册多个视图"""
        self.explorer.register_view(self.employee_view)
        self.explorer.register_view(self.department_view)

        assert len(self.explorer.views) == 2
        assert "test_employee" in self.explorer.views
        assert "test_department" in self.explorer.views
        assert self.explorer.views["test_employee"] == self.employee_view
        assert self.explorer.views["test_department"] == self.department_view

    def test_register_view_override(self):
        """测试覆盖已注册的视图"""
        original_view = ObjectView(
            object_type=self.test_object_type,
            title="原始视图"
        )
        new_view = ObjectView(
            object_type=self.test_object_type,
            title="新视图"
        )

        self.explorer.register_view(original_view)
        assert self.explorer.views["test_employee"] == original_view

        # 注册新视图应该覆盖旧视图
        self.explorer.register_view(new_view)
        assert self.explorer.views["test_employee"] == new_view
        assert len(self.explorer.views) == 1

    def test_open_with_registered_view(self):
        """测试打开已注册的视图"""
        self.explorer.register_view(self.employee_view)

        captured_output = io.StringIO()
        with patch('sys.stdout', captured_output):
            self.explorer.open("test_employee", self.test_object_set)

        output = captured_output.getvalue()

        # 验证使用自定义视图渲染
        assert "--- Object View: 员工视图 ---" in output
        assert "Object Type: Test Employee" in output
        assert "Total Objects: 2" in output
        assert "- [Widget] 列表" in output
        assert "- [Widget] 详情" in output

    def test_open_with_unregistered_view(self):
        """测试打开未注册的视图（显示默认列表）"""
        captured_output = io.StringIO()
        with patch('sys.stdout', captured_output):
            self.explorer.open("test_employee", self.test_object_set)

        output = captured_output.getvalue()

        # 验证显示默认列表
        assert "No custom view for test_employee, using normalized Object View." in output
        assert "--- Object View: Test Employee (Normalized View) ---" in output

    def test_open_with_empty_object_set_unregistered(self):
        """测试打开未注册视图的空对象集"""
        empty_object_set = ObjectSet(self.test_object_type, [])

        captured_output = io.StringIO()
        with patch('sys.stdout', captured_output):
            self.explorer.open("test_employee", empty_object_set)

        output = captured_output.getvalue()

        # 验证显示默认消息并渲染标准视图
        assert "No custom view for test_employee, using normalized Object View." in output
        assert "--- Object View: Test Employee (Normalized View) ---" in output

    def test_open_with_empty_object_set_registered(self):
        """测试打开已注册视图的空对象集"""
        empty_object_set = ObjectSet(self.test_object_type, [])
        self.explorer.register_view(self.employee_view)

        captured_output = io.StringIO()
        with patch('sys.stdout', captured_output):
            self.explorer.open("test_employee", empty_object_set)

        output = captured_output.getvalue()

        # 验证使用自定义视图渲染
        assert "--- Object View: 员工视图 ---" in output
        assert "Total Objects: 0" in output

    def test_open_different_object_types(self):
        """测试打开不同对象类型的视图"""
        self.explorer.register_view(self.employee_view)
        self.explorer.register_view(self.department_view)

        employee_set = ObjectSet(self.test_object_type, self.test_objects)
        department_set = ObjectSet(self.another_object_type, [])

        # 测试员工视图
        emp_output = io.StringIO()
        with patch('sys.stdout', emp_output):
            self.explorer.open("test_employee", employee_set)

        # 测试部门视图
        dept_output = io.StringIO()
        with patch('sys.stdout', dept_output):
            self.explorer.open("test_department", department_set)

        # 验证不同视图显示正确内容
        emp_result = emp_output.getvalue()
        dept_result = dept_output.getvalue()

        assert "--- Object View: 员工视图 ---" in emp_result
        assert "Test Employee" in emp_result
        assert "--- Object View: 部门视图 ---" in dept_result
        assert "Test Department" in dept_result

    def test_describe_view_default_generation(self):
        """测试描述未注册视图时返回标准结构"""
        schema = self.explorer.describe_view(object_type=self.test_object_type)

        assert schema["object_type"] == "test_employee"
        assert schema["widgets"][0] == "standard_table"
        assert "id" in schema["properties"]


class TestObjectExplorerPivoting:
    """验证ObjectExplorer枢轴上下文聚合能力"""

    def setup_method(self):
        self.ontology = Ontology()
        self.asset_type = ObjectType(
            api_name="asset",
            display_name="Asset",
            primary_key="id"
        )
        self.asset_type.add_property("id", PropertyType.STRING)
        self.asset_type.add_property("status", PropertyType.STRING)

        self.vendor_type = ObjectType(
            api_name="vendor",
            display_name="Vendor",
            primary_key="id"
        )
        self.vendor_type.add_property("id", PropertyType.STRING)
        self.vendor_type.add_property("name", PropertyType.STRING)
        self.vendor_type.add_property("score", PropertyType.INTEGER)

        self.ontology.register_object_type(self.asset_type)
        self.ontology.register_object_type(self.vendor_type)

        self.ontology.add_object(
            ObjectInstance(
                object_type_api_name="asset",
                primary_key_value="asset-1",
                property_values={"id": "asset-1", "status": "OK"},
            )
        )
        self.ontology.add_object(
            ObjectInstance(
                object_type_api_name="vendor",
                primary_key_value="vendor-1",
                property_values={"id": "vendor-1", "name": "Vendor A", "score": 90},
            )
        )
        self.ontology.add_object(
            ObjectInstance(
                object_type_api_name="vendor",
                primary_key_value="vendor-2",
                property_values={"id": "vendor-2", "name": "Vendor B", "score": 100},
            )
        )

        self.ontology.register_link_type(
            LinkType(
                api_name="asset_has_vendor",
                display_name="Asset Has Vendor",
                source_object_type="asset",
                target_object_type="vendor",
            )
        )
        self.ontology.create_link("asset_has_vendor", "asset-1", "vendor-1")
        self.ontology.create_link("asset_has_vendor", "asset-1", "vendor-2")

        asset_instances = [self.ontology.get_object("asset", "asset-1")]
        self.asset_set = ObjectSet(
            self.asset_type, asset_instances, ontology=self.ontology
        )
        self.explorer = ObjectExplorer()

    def test_pivot_context_with_metrics(self):
        """执行枢轴聚合并返回指标"""
        plan = PivotAggregationPlan(
            link_type_api_name="asset_has_vendor",
            metrics={"score": "avg"},
            properties=["name", "score"],
            limit=10,
        )

        context = self.explorer.pivot_context(
            self.asset_set, [plan], include_root_properties=["status"]
        )

        assert context["root"]["object_type"] == "asset"
        assert context["root"]["objects"][0]["properties"]["status"] == "OK"
        pivot = context["pivots"][0]
        assert pivot["link_type"]["api_name"] == "asset_has_vendor"
        assert pytest.approx(pivot["metrics"]["score"], rel=1e-6) == 95
        assert {obj["properties"]["name"] for obj in pivot["objects"]} == {
            "Vendor A",
            "Vendor B",
        }

    def test_pivot_context_requires_ontology(self):
        """没有Ontology上下文时抛出错误"""
        plan = PivotAggregationPlan(link_type_api_name="asset_has_vendor")
        object_set = ObjectSet(self.asset_type, [])

        with pytest.raises(ValueError):
            self.explorer.pivot_context(object_set, [plan])


class TestQuiverExtended:
    """Quiver 扩展测试用例"""

    def setup_method(self):
        """每个测试前的设置"""
        self.quiver = Quiver()

        # 创建测试对象类型
        self.test_object_type = ObjectType(
            api_name="test_analytics",
            display_name="Test Analytics Data",
            primary_key="id"
        )
        self.test_object_type.add_property("id", PropertyType.STRING)
        self.test_object_type.add_property("metric", PropertyType.STRING)

        # 创建测试对象
        self.test_objects = [
            ObjectInstance(
                object_type_api_name="test_analytics",
                primary_key_value="data1",
                property_values={
                    "id": "data1",
                    "metric": "sales"
                }
            ),
            ObjectInstance(
                object_type_api_name="test_analytics",
                primary_key_value="data2",
                property_values={
                    "id": "data2",
                    "metric": "revenue"
                }
            )
        ]
        self.test_object_set = ObjectSet(self.test_object_type, self.test_objects)

    def test_quiver_analyze_single_object(self):
        """测试Quiver分析单个对象"""
        single_object_set = ObjectSet(self.test_object_type, [self.test_objects[0]])

        captured_output = io.StringIO()
        with patch('sys.stdout', captured_output):
            self.quiver.analyze(single_object_set)

        output = captured_output.getvalue()

        # 验证分析输出
        assert "--- Quiver Analysis ---" in output
        assert "Analyzing 1 objects of type test_analytics" in output
        assert "Generating charts... [Done]" in output
        assert "-----------------------" in output

    def test_quiver_analyze_multiple_objects(self):
        """测试Quiver分析多个对象"""
        captured_output = io.StringIO()
        with patch('sys.stdout', captured_output):
            self.quiver.analyze(self.test_object_set)

        output = captured_output.getvalue()

        assert "--- Quiver Analysis ---" in output
        assert "Analyzing 2 objects of type test_analytics" in output
        assert "Generating charts... [Done]" in output
        assert "-----------------------" in output

    def test_quiver_analyze_empty_object_set(self):
        """测试Quiver分析空对象集"""
        empty_object_set = ObjectSet(self.test_object_type, [])

        captured_output = io.StringIO()
        with patch('sys.stdout', captured_output):
            self.quiver.analyze(empty_object_set)

        output = captured_output.getvalue()

        assert "--- Quiver Analysis ---" in output
        assert "Analyzing 0 objects of type test_analytics" in output
        assert "Generating charts... [Done]" in output
        assert "-----------------------" in output

    def test_quiver_analyze_different_object_types(self):
        """测试Quiver分析不同对象类型"""
        user_object_type = ObjectType(
            api_name="test_user_analytics",
            display_name="Test User Analytics",
            primary_key="id"
        )
        user_object_set = ObjectSet(user_object_type, [])

        captured_output = io.StringIO()
        with patch('sys.stdout', captured_output):
            self.quiver.analyze(user_object_set)

        output = captured_output.getvalue()

        assert "--- Quiver Analysis ---" in output
        assert "Analyzing 0 objects of type test_user_analytics" in output
        assert "Test User Analytics" not in output

    def test_quiver_large_object_set_analysis(self):
        """测试Quiver分析大对象集"""
        large_object_list = []
        for i in range(100):
            obj = ObjectInstance(
                object_type_api_name="test_analytics",
                primary_key_value=f"data{i}",
                property_values={
                    "id": f"data{i}",
                    "metric": f"metric_{i}"
                }
            )
            large_object_list.append(obj)

        large_object_set = ObjectSet(self.test_object_type, large_object_list)

        captured_output = io.StringIO()
        with patch('sys.stdout', captured_output):
            self.quiver.analyze(large_object_set)

        output = captured_output.getvalue()

        assert "--- Quiver Analysis ---" in output
        assert "Analyzing 100 objects of type test_analytics" in output
        assert "Generating charts... [Done]" in output
        assert "-----------------------" in output


class TestVertexExtended:
    """Vertex 图谱与模拟测试"""

    def setup_method(self):
        self.ontology = Ontology()
        self.order_type = ObjectType(
            api_name="order",
            display_name="Order",
            primary_key="id",
        )
        self.order_type.add_property("id", PropertyType.STRING)
        self.order_type.add_property("status", PropertyType.STRING)

        self.asset_type = ObjectType(
            api_name="asset",
            display_name="Asset",
            primary_key="id",
        )
        self.asset_type.add_property("id", PropertyType.STRING)
        self.asset_type.add_property("health", PropertyType.INTEGER)

        self.ontology.register_object_type(self.order_type)
        self.ontology.register_object_type(self.asset_type)

        self.ontology.add_object(
            ObjectInstance(
                object_type_api_name="order",
                primary_key_value="order-1",
                property_values={"id": "order-1", "status": "IN_PROGRESS"},
            )
        )
        self.ontology.add_object(
            ObjectInstance(
                object_type_api_name="asset",
                primary_key_value="asset-1",
                property_values={"id": "asset-1", "health": 80},
            )
        )

        self.ontology.register_link_type(
            LinkType(
                api_name="order_depends_on_asset",
                display_name="Order Depends On Asset",
                source_object_type="order",
                target_object_type="asset",
            )
        )
        self.ontology.create_link("order_depends_on_asset", "order-1", "asset-1")

        self.vertex = Vertex(self.ontology)

    def test_generate_system_graph(self):
        """构建系统图谱"""
        order_instance = self.ontology.get_object("order", "order-1")
        seed_set = ObjectSet(
            self.order_type, [order_instance], ontology=self.ontology
        )

        graph = self.vertex.generate_system_graph(
            seed_set, max_depth=2, include_properties=["status"]
        )

        assert "order:order-1" in graph["nodes"]
        assert "asset:asset-1" in graph["nodes"]
        assert any(
            edge["link_type"] == "order_depends_on_asset" for edge in graph["edges"]
        )

    def test_vertex_simulation_with_binding(self):
        """注册并运行带绑定逻辑的模拟"""
        state = {}

        def runner(**kwargs):
            return {"prediction": kwargs["throughput"] * 2}

        def binder(ontology, result, params):
            state["value"] = result["prediction"]

        simulation = VertexSimulation(
            name="capacity_forecast",
            runner=runner,
            description="Capacity stress test",
            binding_handler=binder,
        )
        self.vertex.register_simulation(simulation)

        result = self.vertex.run_simulation("capacity_forecast", throughput=5)

        assert result["result"]["prediction"] == 10
        assert result["bound"] is True
        assert state["value"] == 10

    def test_vertex_function_backed_simulation(self):
        """验证函数驱动的模拟注册"""
        function = Function(
            api_name="predict_delay",
            display_name="Predict Delay",
            logic=lambda base: {"delay": base + 1},
        )
        function.add_input(
            "base",
            PrimitiveType(PropertyType.INTEGER),
            required=True,
            description="Base minutes",
        )
        self.ontology.register_function(function)

        self.vertex.register_function_backed_simulation(
            name="delay_prediction",
            function_api_name="predict_delay",
            description="Delay forecast",
        )

        result = self.vertex.run_simulation("delay_prediction", base=3, bind=False)

        assert result["result"]["delay"] == 4
        assert result["bound"] is False
