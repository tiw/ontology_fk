# 扩展性能基准测试
# 建立系统性能基准和监控指标

import pytest
import time
import uuid
from unittest.mock import Mock, patch

from ontology_framework.core import (
    ObjectType,
    ObjectInstance,
    ObjectSet,
    ActionType,
    Ontology,
    PropertyType,
)
from ontology_framework.services import ObjectSetService, ActionService
from ontology_framework.applications import ObjectExplorer, Quiver
from ontology_framework.permissions import AccessControlList, Principal, PermissionType


class TestOntologyPerformanceBenchmarks:
    """Ontology 核心性能基准测试"""

    def setup_method(self):
        """初始化性能测试环境"""
        self.ontology = Ontology()

        # 创建不同复杂度的对象类型
        self.simple_type = ObjectType(
            api_name="simple_object",
            display_name="Simple Object",
            primary_key="id"
        )
        self.simple_type.add_property("id", PropertyType.STRING)
        self.simple_type.add_property("name", PropertyType.STRING)

        self.complex_type = ObjectType(
            api_name="complex_object",
            display_name="Complex Object",
            primary_key="id"
        )
        # 添加多个属性
        for i in range(10):
            self.complex_type.add_property(f"field_{i}", PropertyType.STRING)

        # 注册对象类型
        self.ontology.register_object_type(self.simple_type)
        self.ontology.register_object_type(self.complex_type)

    def test_ontology_registration_performance(self, benchmark):
        """测试本体注册性能"""
        def register_multiple_types(count):
            temp_ontology = Ontology()
            for i in range(count):
                obj_type = ObjectType(
                    api_name=f"perf_test_{i}",
                    display_name=f"Performance Test {i}",
                    primary_key="id"
                )
                obj_type.add_property("id", PropertyType.STRING)
                obj_type.add_property("name", PropertyType.STRING)
                temp_ontology.register_object_type(obj_type)

        # 基准测试：注册100个对象类型
        result = benchmark(register_multiple_types, 100)
        assert result is not None

    def test_object_creation_performance(self, benchmark):
        """测试对象创建性能"""
        # 基准测试：创建1000个对象实例
        def create_objects(count):
            objects = []
            for i in range(count):
                obj = ObjectInstance(
                    object_type_api_name="simple_object",
                    primary_key_value=f"obj_{i}",
                    property_values={
                        "id": f"obj_{i}",
                        "name": f"Object {i}"
                    }
                )
                objects.append(obj)
            return objects

        result = benchmark(create_objects, 1000)
        assert len(result) == 1000

    def test_object_set_creation_performance(self, benchmark):
        """测试对象集创建性能"""
        # 预创建对象
        objects = []
        for i in range(500):
            obj = ObjectInstance(
                object_type_api_name="simple_object",
                primary_key_value=f"obj_{i}",
                property_values={
                    "id": f"obj_{i}",
                    "name": f"Object {i}"
                }
            )
            objects.append(obj)

        def create_object_set(obj_list):
            return ObjectSet(self.simple_type, obj_list)

        result = benchmark(create_object_set, objects)
        assert len(result.all()) == 500

    def test_complex_object_performance(self, benchmark):
        """测试复杂对象性能"""
        def create_complex_objects(count):
            objects = []
            for i in range(count):
                values = {"id": f"complex_obj_{i}"}
                for j in range(10):
                    values[f"field_{j}"] = f"value_{i}_{j}"

                obj = ObjectInstance(
                    object_type_api_name="complex_object",
                    primary_key_value=f"complex_obj_{i}",
                    property_values=values
                )
                objects.append(obj)
            return objects

        result = benchmark(create_complex_objects, 100)
        assert len(result) == 100


class TestObjectSetServicePerformanceBenchmarks:
    """ObjectSetService 性能基准测试"""

    def setup_method(self):
        """初始化服务性能测试"""
        self.service = ObjectSetService()

        self.test_type = ObjectType(
            api_name="perf_test_object",
            display_name="Performance Test Object",
            primary_key="id"
        )
        self.test_type.add_property("id", PropertyType.STRING)
        self.test_type.add_property("name", PropertyType.STRING)
        self.test_type.add_property("category", PropertyType.STRING)
        self.test_type.add_property("value", PropertyType.STRING)

    def test_indexing_performance(self, benchmark):
        """测试索引性能"""
        # 基准测试：索引1000个对象
        def index_objects(count):
            service = ObjectSetService()
            for i in range(count):
                obj = ObjectInstance(
                    object_type_api_name="perf_test_object",
                    primary_key_value=f"obj_{i}",
                    property_values={
                        "id": f"obj_{i}",
                        "name": f"Object {i}",
                        "category": f"Category {i % 10}",
                        "value": f"Value {i}"
                    }
                )
                service.index_object(obj)
            return service

        result = benchmark(index_objects, 1000)
        assert len(result._storage["perf_test_object"]) == 1000

    def test_search_performance(self, benchmark):
        """测试搜索性能"""
        # 预索引对象
        service = ObjectSetService()
        for i in range(1000):
            obj = ObjectInstance(
                object_type_api_name="perf_test_object",
                primary_key_value=f"obj_{i}",
                property_values={
                    "id": f"obj_{i}",
                    "name": f"Object {i}",
                    "category": f"Category {i % 10}",
                    "value": f"Value {i}"
                }
            )
            service.index_object(obj)

        def search_objects():
            return service.search(self.test_type, "Object")

        result = benchmark(search_objects)
        assert len(result.all()) > 0

    def test_get_base_object_set_performance(self, benchmark):
        """测试获取基础对象集性能"""
        # 预索引对象
        service = ObjectSetService()
        for i in range(1000):
            obj = ObjectInstance(
                object_type_api_name="perf_test_object",
                primary_key_value=f"obj_{i}",
                property_values={
                    "id": f"obj_{i}",
                    "name": f"Object {i}",
                    "category": f"Category {i % 10}",
                    "value": f"Value {i}"
                }
            )
            service.index_object(obj)

        def get_object_set():
            return service.get_base_object_set(self.test_type)

        result = benchmark(get_object_set)
        assert len(result.all()) == 1000


class TestActionServicePerformanceBenchmarks:
    """ActionService 性能基准测试"""

    def setup_method(self):
        """初始化动作服务性能测试"""
        self.ontology = Ontology()
        self.service = ActionService(self.ontology)

        # 创建基础对象类型
        self.user_type = ObjectType(
            api_name="user",
            display_name="User",
            primary_key="id"
        )
        self.user_type.add_property("id", PropertyType.STRING)
        self.user_type.add_property("name", PropertyType.STRING)
        self.ontology.register_object_type(self.user_type)

        # 创建测试动作
        self.test_action = ActionType(
            api_name="test_action",
            display_name="Test Action",
            target_object_types=["user"]
        )
        self.test_action.add_parameter("name", "string", required=True)
        self.ontology.register_action_type(self.test_action)

    def test_action_execution_performance(self, benchmark):
        """测试动作执行性能"""
        principal = Principal("test_user", "user")

        # 基准测试：执行100个动作
        def execute_actions(count):
            logs = []
            for i in range(count):
                with patch('time.time', return_value=1234567890 + i):
                    with patch('uuid.uuid4', return_value=f'action-uuid-{i}'):
                        log = self.service.execute_action(
                            "test_action",
                            {"name": f"User {i}"},
                            principal
                        )
                        logs.append(log)
            return logs

        result = benchmark(execute_actions, 100)
        assert len(result) == 100

    def test_multiple_action_types_performance(self, benchmark):
        """测试多种动作类型性能"""
        # 创建多个动作类型
        for i in range(10):
            action = ActionType(
                api_name=f"action_{i}",
                display_name=f"Action {i}",
                target_object_types=["user"]
            )
            action.add_parameter("param", "string", required=True)
            self.ontology.register_action_type(action)

        principal = Principal("test_user", "user")

        def execute_various_actions():
            logs = []
            for i in range(50):
                action_name = f"action_{i % 10}"
                with patch('time.time', return_value=1234567890 + i):
                    with patch('uuid.uuid4', return_value=f'action-uuid-{i}'):
                        log = self.service.execute_action(
                            action_name,
                            {"param": f"Value {i}"},
                            principal
                        )
                        logs.append(log)
            return logs

        result = benchmark(execute_various_actions)
        assert len(result) == 50


class TestApplicationsPerformanceBenchmarks:
    """应用层性能基准测试"""

    def setup_method(self):
        """初始化应用层性能测试"""
        self.explorer = ObjectExplorer()
        self.quiver = Quiver()

        self.test_type = ObjectType(
            api_name="app_perf_test",
            display_name="App Performance Test",
            primary_key="id"
        )
        self.test_type.add_property("id", PropertyType.STRING)
        self.test_type.add_property("name", PropertyType.STRING)
        self.test_type.add_property("value", PropertyType.INTEGER)

    def test_object_view_rendering_performance(self, benchmark):
        """测试对象视图渲染性能"""
        from ontology_framework.applications import ObjectView

        # 创建视图
        view = ObjectView(
            object_type=self.test_type,
            title="Performance Test View",
            widgets=["Widget 1", "Widget 2", "Widget 3", "Widget 4", "Widget 5"]
        )

        # 创建大量对象
        objects = []
        for i in range(100):
            obj = ObjectInstance(
                object_type_api_name="app_perf_test",
                primary_key_value=f"obj_{i}",
                property_values={
                    "id": f"obj_{i}",
                    "name": f"Object {i}",
                    "value": i
                }
            )
            objects.append(obj)

        object_set = ObjectSet(self.test_type, objects)

        def render_view():
            import io
            captured_output = io.StringIO()
            with patch('sys.stdout', captured_output):
                view.render(object_set)
            return captured_output.getvalue()

        result = benchmark(render_view)
        assert "Performance Test View" in result

    def test_explorer_performance(self, benchmark):
        """测试对象浏览器性能"""
        # 注册多个视图
        for i in range(10):
            from ontology_framework.applications import ObjectView

            view = ObjectView(
                object_type=self.test_type,
                title=f"View {i}",
                widgets=[f"Widget {i}"]
            )
            self.explorer.register_view(view)

        # 创建对象集
        objects = []
        for i in range(50):
            obj = ObjectInstance(
                object_type_api_name="app_perf_test",
                primary_key_value=f"obj_{i}",
                property_values={
                    "id": f"obj_{i}",
                    "name": f"Object {i}",
                    "value": i
                }
            )
            objects.append(obj)

        object_set = ObjectSet(self.test_type, objects)

        def explorer_operations():
            import io
            results = []
            for i in range(10):
                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    self.explorer.open("app_perf_test", object_set)
                results.append(captured_output.getvalue())
            return results

        result = benchmark(explorer_operations)
        assert len(result) == 10

    def test_quiver_analysis_performance(self, benchmark):
        """测试Quiver分析性能"""
        # 创建不同规模的对象集
        def test_different_sizes():
            results = []
            for size in [10, 50, 100, 500]:
                objects = []
                for i in range(size):
                    obj = ObjectInstance(
                        object_type_api_name="app_perf_test",
                        primary_key_value=f"obj_{i}",
                        property_values={
                            "id": f"obj_{i}",
                            "name": f"Object {i}",
                            "value": i
                        }
                    )
                    objects.append(obj)

                object_set = ObjectSet(self.test_type, objects)

                import io
                captured_output = io.StringIO()
                with patch('sys.stdout', captured_output):
                    self.quiver.analyze(object_set)

                results.append((size, captured_output.getvalue()))

            return results

        result = benchmark(test_different_sizes)
        assert len(result) == 4  # 4种不同规模


class TestMemoryUsageBenchmarks:
    """内存使用基准测试"""

    def test_memory_efficiency_large_dataset(self, benchmark):
        """测试大数据集的内存效率"""
        def create_large_dataset():
            objects = []
            for i in range(5000):
                obj = ObjectInstance(
                    object_type_api_name="memory_test",
                    primary_key_value=f"obj_{i}",
                    property_values={
                        "id": f"obj_{i}",
                        "name": f"Object {i}",
                        "description": f"This is a detailed description for object {i} with some additional text to simulate real-world data"
                    }
                )
                objects.append(obj)

            # 创建对象集
            simple_type = ObjectType(
                api_name="memory_test",
                display_name="Memory Test",
                primary_key="id"
            )
            simple_type.add_property("id", PropertyType.STRING)
            simple_type.add_property("name", PropertyType.STRING)
            simple_type.add_property("description", PropertyType.STRING)

            return ObjectSet(simple_type, objects)

        result = benchmark(create_large_dataset)
        assert len(result.all()) == 5000

    def test_service_memory_scaling(self, benchmark):
        """测试服务内存扩展性"""
        def test_service_scaling():
            service = ObjectSetService()

            # 逐步增加对象数量
            for batch_size in [100, 500, 1000, 2000]:
                for i in range(batch_size):
                    obj = ObjectInstance(
                        object_type_api_name="scaling_test",
                        primary_key_value=f"obj_{batch_size}_{i}",
                        property_values={
                            "id": f"obj_{batch_size}_{i}",
                            "batch": str(batch_size),
                            "index": str(i)
                        }
                    )
                    service.index_object(obj)

                # 验证对象数量
                total_objects = sum(len(obj_list) for obj_list in service._storage.values())
                assert total_objects >= batch_size

            return service

        result = benchmark(test_service_scaling)
        assert result is not None


class TestConcurrencyPerformanceBenchmarks:
    """并发性能基准测试"""

    def test_concurrent_object_creation(self, benchmark):
        """测试并发对象创建性能"""
        def create_objects_concurrently():
            import threading
            import time

            objects = []
            lock = threading.Lock()

            def worker(thread_id, count):
                local_objects = []
                for i in range(count):
                    obj = ObjectInstance(
                        object_type_api_name="concurrent_test",
                        primary_key_value=f"obj_{thread_id}_{i}",
                        property_values={
                            "id": f"obj_{thread_id}_{i}",
                            "thread_id": str(thread_id),
                            "index": str(i),
                            "timestamp": str(time.time())
                        }
                    )
                    local_objects.append(obj)

                with lock:
                    objects.extend(local_objects)

            # 创建多个线程
            threads = []
            for i in range(4):  # 4个线程
                thread = threading.Thread(target=worker, args=(i, 250))
                threads.append(thread)

            # 启动所有线程
            for thread in threads:
                thread.start()

            # 等待所有线程完成
            for thread in threads:
                thread.join()

            return objects

        result = benchmark(create_objects_concurrently)
        assert len(result) == 1000  # 4个线程 × 250个对象

    def test_concurrent_service_operations(self, benchmark):
        """测试并发服务操作性能"""
        def concurrent_service_ops():
            import threading

            services = [ObjectSetService() for _ in range(3)]

            def worker(service, thread_id):
                for i in range(100):
                    obj = ObjectInstance(
                        object_type_api_name="concurrent_service_test",
                        primary_key_value=f"obj_{thread_id}_{i}",
                        property_values={
                            "id": f"obj_{thread_id}_{i}",
                            "thread_id": str(thread_id),
                            "index": str(i)
                        }
                    )
                    service.index_object(obj)

            # 创建线程
            threads = []
            for i, service in enumerate(services):
                thread = threading.Thread(target=worker, args=(service, i))
                threads.append(thread)

            # 启动线程
            for thread in threads:
                thread.start()

            # 等待完成
            for thread in threads:
                thread.join()

            # 合并结果
            total_objects = sum(
                sum(len(obj_list) for obj_list in service._storage.values())
                for service in services
            )

            return total_objects

        result = benchmark(concurrent_service_ops)
        assert result == 300  # 3个服务 × 100个对象