"""
性能优化实施测试

验证新实现的性能优化功能，包括缓存、索引、批量处理和内存优化。
"""

import time
import pytest
from ontology_framework.performance import (
    CacheManager, IndexManager, QueryOptimizer, IndexDefinition,
    LRUCache, PerformanceAdvisor, PerformanceOptimizerAdapter,
    BatchProcessor, BatchConfig, MemoryOptimizer,
    cached, performance_monitored
)
from ontology_framework.core import (
    Ontology, ObjectType, ObjectInstance, PropertyType
)
from ontology_framework.optimized_core import OptimizedOntology


class TestCacheManager:
    """缓存管理器测试"""

    def test_cache_basic_operations(self):
        """测试缓存基本操作"""
        cache = LRUCache(max_size=3, ttl_seconds=1)

        # 测试添加和获取
        cache.put("key1", "value1")
        cache.put("key2", "value2")
        cache.put("key3", "value3")

        assert cache.get("key1") == "value1"
        assert cache.get("key2") == "value2"
        assert cache.get("key3") == "value3"

        # 测试LRU淘汰
        cache.put("key4", "value4")
        assert cache.get("key1") is None  # key1应该被淘汰
        assert cache.get("key4") == "value4"

        # 测试统计信息
        stats = cache.get_stats()
        assert stats["size"] == 3
        assert stats["max_size"] == 3
        assert stats["hits"] > 0

    def test_cache_expiration(self):
        """测试缓存过期"""
        cache = LRUCache(max_size=10, ttl_seconds=0.1)  # 0.1秒过期

        cache.put("key1", "value1")
        assert cache.get("key1") == "value1"

        # 等待过期
        time.sleep(0.2)
        assert cache.get("key1") is None

    def test_cache_manager(self):
        """测试缓存管理器"""
        manager = CacheManager()

        cache1 = manager.get_cache("test1")
        cache2 = manager.get_cache("test1")
        cache3 = manager.get_cache("test2")

        # 相同名称应该返回同一个缓存实例
        assert cache1 is cache2
        assert cache1 is not cache3

        cache1.put("key", "value")
        assert cache2.get("key") == "value"

        # 测试统计信息
        all_stats = manager.get_all_stats()
        assert "test1" in all_stats
        assert "test2" in all_stats

    def test_cached_decorator(self):
        """测试缓存装饰器"""
        call_count = 0

        @cached(cache_name="test_func", ttl_seconds=1)
        def expensive_function(x, y):
            nonlocal call_count
            call_count += 1
            return x + y

        # 第一次调用，应该执行函数
        result1 = expensive_function(1, 2)
        assert result1 == 3
        assert call_count == 1

        # 第二次调用相同参数，应该从缓存获取
        result2 = expensive_function(1, 2)
        assert result2 == 3
        assert call_count == 1  # 没有增加

        # 不同参数，应该执行函数
        result3 = expensive_function(2, 3)
        assert result3 == 5
        assert call_count == 2


class TestIndexManager:
    """索引管理器测试"""

    def test_create_index(self):
        """测试创建索引"""
        manager = IndexManager()

        # 创建哈希索引
        index_def = IndexDefinition(
            name="test_index",
            property_name="name",
            index_type="hash",
            unique=False
        )

        index = manager.create_index(index_def)
        assert index is not None
        assert index.definition.name == "test_index"

        # 重复创建应该失败
        with pytest.raises(ValueError):
            manager.create_index(index_def)

    def test_index_operations(self):
        """测试索引操作"""
        manager = IndexManager()
        index_def = IndexDefinition("test_index", "name", "hash", False)
        index = manager.create_index(index_def)

        # 添加索引项
        index.add("Alice", "obj1")
        index.add("Bob", "obj2")
        index.add("Alice", "obj3")  # 允许重复

        # 查找
        alice_objects = index.find("Alice")
        assert set(alice_objects) == {"obj1", "obj3"}

        bob_objects = index.find("Bob")
        assert bob_objects == ["obj2"]

        # 删除
        index.remove("Alice", "obj1")
        alice_objects = index.find("Alice")
        assert alice_objects == ["obj3"]

    def test_unique_index(self):
        """测试唯一索引"""
        manager = IndexManager()
        index_def = IndexDefinition("unique_index", "email", "hash", True)
        index = manager.create_index(index_def)

        # 添加唯一值
        index.add("alice@example.com", "obj1")

        # 重复值应该抛出异常
        with pytest.raises(ValueError):
            index.add("alice@example.com", "obj2")

    def test_case_sensitive_index(self):
        """测试大小写敏感性"""
        manager = IndexManager()

        # 大小写敏感
        sensitive_def = IndexDefinition("sensitive", "name", "hash", False, case_sensitive=True)
        sensitive_index = manager.create_index(sensitive_def)
        sensitive_index.add("Alice", "obj1")
        sensitive_index.add("alice", "obj2")

        assert sensitive_index.find("Alice") == ["obj1"]
        assert sensitive_index.find("alice") == ["obj2"]

        # 大小写不敏感
        insensitive_def = IndexDefinition("insensitive", "name", "hash", False, case_sensitive=False)
        insensitive_index = manager.create_index(insensitive_def)
        insensitive_index.add("Alice", "obj1")
        insensitive_index.add("alice", "obj2")  # 应该覆盖

        assert insensitive_index.find("Alice") == ["obj2"]
        assert insensitive_index.find("alice") == ["obj2"]


class TestPerformanceAdvisor:
    """性能优化建议器测试"""

    def test_analyze_cache_performance(self):
        """测试缓存性能分析"""
        advisor = PerformanceAdvisor()

        # 模拟低命中率缓存
        cache = advisor.cache_manager.get_cache("test_cache")

        # 添加一些数据但制造低命中率
        for i in range(100):
            cache.put(f"key_{i}", f"value_{i}")

        # 只访问少数几个键，造成低命中率
        for i in range(5):
            cache.get(f"key_{i}")

        recommendations = advisor.analyze_performance()

        # 应该有缓存命中率过低的建议
        cache_recs = [r for r in recommendations if r["type"] == "cache"]
        assert len(cache_recs) > 0
        assert any("命中率过低" in rec["issue"] for rec in cache_recs)

    def test_generate_optimization_report(self):
        """测试生成优化报告"""
        advisor = PerformanceAdvisor()

        # 模拟一些性能问题
        advisor.performance_monitor.record_operation("slow_operation", 0.2, True)  # 200ms
        advisor.performance_monitor.record_operation("slow_operation", 0.15, True)

        report = advisor.generate_optimization_report()

        assert "性能优化建议报告" in report
        assert "高优先级" in report
        assert "平均响应时间过长" in report


class TestBatchProcessor:
    """批量处理器测试"""

    def test_batch_add_objects(self):
        """测试批量添加对象"""
        ontology = OptimizedOntology()
        processor = BatchProcessor()

        # 创建对象类型
        obj_type = ObjectType("test_obj", "Test Object", "id")
        obj_type.add_property("id", PropertyType.STRING)
        obj_type.add_property("name", PropertyType.STRING)
        ontology.register_object_type(obj_type)

        # 创建测试对象
        objects = []
        for i in range(10):
            obj = ObjectInstance(
                object_type_api_name="test_obj",
                primary_key_value=f"obj_{i}",
                property_values={
                    "id": f"obj_{i}",
                    "name": f"Object {i}"
                }
            )
            objects.append(obj)

        # 批量添加
        result = processor.batch_add_objects(ontology, objects)

        assert result["total_objects"] == 10
        assert result["success_count"] == 10
        assert result["error_count"] == 0
        assert result["execution_time"] > 0
        assert result["throughput"] > 0

        # 验证对象已添加
        stored_objects = ontology.get_objects_of_type("test_obj")
        assert len(stored_objects.all()) == 10

    def test_batch_query(self):
        """测试批量查询"""
        ontology = OptimizedOntology()
        processor = BatchProcessor()

        # 创建对象类型
        obj_type = ObjectType("test_obj", "Test Object", "id")
        obj_type.add_property("id", PropertyType.STRING)
        obj_type.add_property("category", PropertyType.STRING)
        ontology.register_object_type(obj_type)

        # 添加测试数据
        categories = ["A", "B", "C"]
        for i, category in enumerate(categories):
            for j in range(3):
                obj = ObjectInstance(
                    object_type_api_name="test_obj",
                    primary_key_value=f"obj_{i}_{j}",
                    property_values={
                        "id": f"obj_{i}_{j}",
                        "category": category
                    }
                )
                ontology.add_object(obj)

        # 批量查询
        queries = [
            {"category": "A"},
            {"category": "B"},
            {"category": "C"}
        ]

        results = processor.batch_query(ontology, "test_obj", queries)

        # 验证结果
        assert len(results) == 9  # 每个类别3个对象
        categories_found = set(obj.get("category") for obj in results)
        assert categories_found == {"A", "B", "C"}


class TestMemoryOptimizer:
    """内存优化器测试"""

    def test_analyze_memory_usage(self):
        """测试内存使用分析"""
        ontology = OptimizedOntology()
        optimizer = MemoryOptimizer(ontology)

        # 创建一些测试数据
        obj_type = ObjectType("test_obj", "Test Object", "id")
        obj_type.add_property("id", PropertyType.STRING)
        ontology.register_object_type(obj_type)

        for i in range(5):
            obj = ObjectInstance(
                object_type_api_name="test_obj",
                primary_key_value=f"obj_{i}",
                property_values={"id": f"obj_{i}"}
            )
            ontology.add_object(obj)

        # 分析内存使用
        memory_stats = optimizer.analyze_memory_usage()

        assert "test_obj" in memory_stats
        assert memory_stats["test_obj"]["object_count"] == 5
        assert memory_stats["test_obj"]["memory_usage"] > 0
        assert memory_stats["test_obj"]["avg_memory_per_object"] > 0

        assert "summary" in memory_stats
        assert memory_stats["summary"]["total_objects"] == 5

    def test_optimize_memory_usage(self):
        """测试内存使用优化"""
        ontology = OptimizedOntology()
        optimizer = MemoryOptimizer(ontology)

        # 创建一些测试数据并填充缓存
        obj_type = ObjectType("test_obj", "Test Object", "id")
        ontology.register_object_type(obj_type)

        for i in range(3):
            obj = ObjectInstance(
                object_type_api_name="test_obj",
                primary_key_value=f"obj_{i}",
                property_values={"id": f"obj_{i}"}
            )
            ontology.add_object(obj)

        # 优化内存使用
        optimizations = optimizer.optimize_memory_usage()

        # 验证优化操作
        assert len(optimizations) > 0
        assert any("清理缓存" in opt for opt in optimizations)

    def test_suggest_memory_optimizations(self):
        """测试内存优化建议"""
        ontology = OptimizedOntology()
        optimizer = MemoryOptimizer(ontology)

        suggestions = optimizer.suggest_memory_optimizations()

        # 即使没有数据，也应该返回建议列表
        assert isinstance(suggestions, list)


class TestPerformanceMonitoring:
    """性能监控测试"""

    def test_performance_monitored_decorator(self):
        """测试性能监控装饰器"""
        @performance_monitored("test_operation")
        def test_function(x):
            time.sleep(0.01)  # 模拟一些处理时间
            return x * 2

        # 执行函数
        result = test_function(5)
        assert result == 10

        # 检查性能指标
        monitor = get_performance_monitor()
        metrics = monitor.get_metrics("test_operation")

        assert metrics is not None
        assert metrics.operation_count == 1
        assert metrics.avg_time > 0.01  # 至少睡了0.01秒
        assert metrics.error_rate == 0.0

    def test_error_tracking(self):
        """测试错误跟踪"""
        @performance_monitored("error_operation")
        def error_function():
            raise ValueError("测试错误")

        # 执行会抛出异常的函数
        with pytest.raises(ValueError):
            error_function()

        # 检查错误统计
        monitor = get_performance_monitor()
        metrics = monitor.get_metrics("error_operation")

        assert metrics is not None
        assert metrics.operation_count == 1
        assert metrics.error_count == 1
        assert metrics.error_rate == 1.0


class TestPerformanceOptimizerAdapter:
    """性能优化适配器测试"""

    def test_install_optimizations(self):
        """测试安装优化"""
        ontology = OptimizedOntology()
        adapter = PerformanceOptimizerAdapter(ontology)

        # 创建测试对象类型
        obj_type = ObjectType("test_obj", "Test Object", "id")
        obj_type.add_property("id", PropertyType.STRING)
        obj_type.add_property("name", PropertyType.STRING)
        ontology.register_object_type(obj_type)

        # 安装优化
        adapter.install_optimizations()

        # 验证索引已创建
        indexes = adapter.ontology.index_manager.get_index_stats()
        assert len(indexes) > 0

    def test_get_optimization_recommendations(self):
        """测试获取优化建议"""
        ontology = OptimizedOntology()
        adapter = PerformanceOptimizerAdapter(ontology)

        recommendations = adapter.get_optimization_recommendations()

        # 应该返回建议列表
        assert isinstance(recommendations, list)

    def test_apply_auto_optimizations(self):
        """测试应用自动优化"""
        ontology = OptimizedOntology()
        adapter = PerformanceOptimizerAdapter(ontology)

        # 应用自动优化（不应该抛出异常）
        adapter.apply_auto_optimizations()


# 工具函数
def get_performance_monitor():
    """获取全局性能监控器"""
    from ontology_framework.performance import get_performance_monitor
    return get_performance_monitor()


class TestEndToEndPerformanceOptimizations:
    """端到端性能优化测试"""

    def test_complete_performance_workflow(self):
        """测试完整的性能工作流"""
        # 1. 创建优化的本体
        ontology = OptimizedOntology(enable_monitoring=True, enable_cache=True)

        # 2. 创建对象类型
        employee_type = ObjectType("employee", "Employee", "employee_id")
        employee_type.add_property("employee_id", PropertyType.STRING)
        employee_type.add_property("name", PropertyType.STRING)
        employee_type.add_property("department", PropertyType.STRING)
        employee_type.add_property("salary", PropertyType.INTEGER)
        ontology.register_object_type(employee_type)

        # 3. 创建性能优化适配器
        adapter = PerformanceOptimizerAdapter(ontology)
        adapter.install_optimizations()

        # 4. 批量添加员工数据
        processor = BatchProcessor()
        employees = []
        departments = ["Engineering", "Sales", "Marketing"]

        for i in range(100):
            dept = departments[i % len(departments)]
            employee = ObjectInstance(
                object_type_api_name="employee",
                primary_key_value=f"emp_{i:03d}",
                property_values={
                    "employee_id": f"emp_{i:03d}",
                    "name": f"Employee {i}",
                    "department": dept,
                    "salary": 50000 + (i * 1000)
                }
            )
            employees.append(employee)

        # 批量添加
        batch_result = processor.batch_add_objects(ontology, employees)
        assert batch_result["success_count"] == 100

        # 5. 测试查询性能
        start_time = time.time()
        engineering_employees = ontology.get_objects_of_type("employee")
        filtered = engineering_employees.filter("department", "Engineering")
        query_time = time.time() - start_time

        assert len(filtered.all()) > 30
        assert query_time < 0.1  # 应该在100ms内完成

        # 6. 测试批量查询
        queries = [
            {"department": "Engineering"},
            {"department": "Sales"},
            {"department": "Marketing"}
        ]
        batch_results = processor.batch_query(ontology, "employee", queries)
        assert len(batch_results) == 100

        # 7. 分析性能
        stats = ontology.get_performance_stats()
        assert "operation_stats" in stats
        assert "cache_stats" in stats
        assert "index_stats" in stats

        # 8. 内存优化
        memory_optimizer = MemoryOptimizer(ontology)
        memory_stats = memory_optimizer.analyze_memory_usage()
        assert memory_stats["summary"]["total_objects"] == 100

        optimizations = memory_optimizer.optimize_memory_usage()
        assert len(optimizations) > 0

        # 9. 生成优化报告
        advisor = PerformanceAdvisor()
        report = advisor.generate_optimization_report()
        assert len(report) > 0

        print(f"✅ 性能测试完成:")
        print(f"   - 批量添加吞吐量: {batch_result['throughput']:.1f} objects/sec")
        print(f"   - 查询响应时间: {query_time:.3f}s")
        print(f"   - 内存使用: {memory_stats['summary']['total_memory']} bytes")
        print(f"   - 优化报告: {len(report)} 字符")