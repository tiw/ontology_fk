#!/usr/bin/env python3
"""
性能优化演示脚本

展示新实现的性能优化功能，包括缓存、索引、批量处理等。
"""

import sys
import os
import time

# 添加src目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

try:
    from ontology_framework.performance import (
        CacheManager, LRUCache, IndexManager, IndexDefinition,
        PerformanceAdvisor, BatchProcessor, BatchConfig,
        cached, performance_monitored
    )
    from ontology_framework.optimized_core import OptimizedOntology
    from ontology_framework.core import ObjectType, ObjectInstance, PropertyType
    print("✅ 所有模块导入成功")
except ImportError as e:
    print(f"❌ 模块导入失败: {e}")
    sys.exit(1)


def demonstrate_caching():
    """演示缓存功能"""
    print("\n🔍 缓存功能演示")
    print("=" * 40)

    # 1. 基本缓存操作
    cache = LRUCache(max_size=5, ttl_seconds=2)
    print("创建LRU缓存: 最大容量=5, TTL=2秒")

    # 添加数据
    cache.put("user:1", "Alice")
    cache.put("user:2", "Bob")
    cache.put("user:3", "Charlie")
    print("添加3个用户数据")

    # 获取数据
    print(f"获取用户1: {cache.get('user:1')}")
    print(f"获取用户2: {cache.get('user:2')}")

    # 显示统计信息
    stats = cache.get_stats()
    print(f"缓存统计: 大小={stats['size']}, 命中率={stats['hit_rate']:.2%}")

    # 2. 缓存装饰器
    print("\n缓存装饰器演示:")
    call_count = 0

    @cached(cache_name="expensive_calc", ttl_seconds=1)
    def expensive_calculation(x, y):
        nonlocal call_count
        call_count += 1
        time.sleep(0.1)  # 模拟耗时计算
        return x * y

    # 第一次调用
    start = time.time()
    result1 = expensive_calculation(10, 20)
    time1 = time.time() - start
    print(f"第一次调用: {result1}, 耗时={time1:.3f}s, 调用次数={call_count}")

    # 第二次调用（应该从缓存获取）
    start = time.time()
    result2 = expensive_calculation(10, 20)
    time2 = time.time() - start
    print(f"第二次调用: {result2}, 耗时={time2:.3f}s, 调用次数={call_count}")

    print(f"缓存加速比: {time1/time2:.1f}x")


def demonstrate_indexing():
    """演示索引功能"""
    print("\n🔍 索引功能演示")
    print("=" * 40)

    # 创建索引管理器
    index_manager = IndexManager()

    # 创建用户名索引
    name_index_def = IndexDefinition(
        name="user_name_index",
        property_name="name",
        index_type="hash",
        unique=False
    )
    name_index = index_manager.create_index(name_index_def)
    print("创建用户名索引")

    # 添加索引数据
    users = [
        ("Alice", "user1"),
        ("Bob", "user2"),
        ("Alice", "user3"),  # 重名用户
        ("Charlie", "user4"),
        ("Bob", "user5")
    ]

    for name, user_id in users:
        name_index.add(name, user_id)

    print(f"添加了{len(users)}个用户到索引")

    # 查询演示
    alice_users = name_index.find("Alice")
    bob_users = name_index.find("Bob")
    unknown_users = name_index.find("Unknown")

    print(f"查询 'Alice': {alice_users}")
    print(f"查询 'Bob': {bob_users}")
    print(f"查询 'Unknown': {unknown_users}")

    # 显示索引统计
    stats = name_index.get_stats()
    print(f"索引统计: 总值={stats['total_values']}, 总对象={stats['total_objects']}")


def demonstrate_batch_processing():
    """演示批量处理功能"""
    print("\n🔍 批量处理功能演示")
    print("=" * 40)

    # 创建优化的本体
    ontology = OptimizedOntology(enable_monitoring=True)

    # 定义员工对象类型
    employee_type = ObjectType("employee", "Employee", "employee_id")
    employee_type.add_property("employee_id", PropertyType.STRING)
    employee_type.add_property("name", PropertyType.STRING)
    employee_type.add_property("department", PropertyType.STRING)
    employee_type.add_property("salary", PropertyType.INTEGER)
    ontology.register_object_type(employee_type)

    print("注册员工对象类型")

    # 批量创建员工数据
    departments = ["Engineering", "Sales", "Marketing", "HR"]
    employees = []

    for i in range(50):
        dept = departments[i % len(departments)]
        employee = ObjectInstance(
            object_type_api_name="employee",
            primary_key_value=f"emp_{i:03d}",
            property_values={
                "employee_id": f"emp_{i:03d}",
                "name": f"Employee {i}",
                "department": dept,
                "salary": 50000 + (i * 500)
            }
        )
        employees.append(employee)

    print(f"创建了{len(employees)}个员工对象")

    # 批量添加
    batch_config = BatchConfig(batch_size=20)
    processor = BatchProcessor(batch_config)

    start_time = time.time()
    result = processor.batch_add_objects(ontology, employees)
    batch_time = time.time() - start_time

    print(f"批量添加结果:")
    print(f"  - 总数: {result['total_objects']}")
    print(f"  - 成功: {result['success_count']}")
    print(f"  - 失败: {result['error_count']}")
    print(f"  - 耗时: {batch_time:.3f}s")
    print(f"  - 吞吐量: {result['throughput']:.1f} objects/sec")

    # 验证数据
    stored_employees = ontology.get_objects_of_type("employee")
    print(f"存储的员工数量: {len(stored_employees.all())}")


def demonstrate_performance_monitoring():
    """演示性能监控功能"""
    print("\n🔍 性能监控功能演示")
    print("=" * 40)

    from ontology_framework.performance import get_performance_monitor

    monitor = get_performance_monitor()

    # 模拟一些操作
    operations = [
        ("database_query", 0.05, True),
        ("database_query", 0.08, True),
        ("database_query", 0.12, True),  # 慢查询
        ("api_call", 0.02, True),
        ("api_call", 0.03, True),
        ("file_operation", 0.15, False),  # 失败操作
        ("calculation", 0.001, True),
        ("calculation", 0.002, True),
    ]

    for op_name, exec_time, success in operations:
        monitor.record_operation(op_name, exec_time, success)

    print("记录了8个操作的性能数据")

    # 显示性能指标
    all_metrics = monitor.get_all_metrics()
    for op_name, metrics in all_metrics.items():
        print(f"\n{op_name}:")
        print(f"  - 操作次数: {metrics.operation_count}")
        print(f"  - 平均耗时: {metrics.avg_time:.3f}s")
        print(f"  - 最小耗时: {metrics.min_time:.3f}s")
        print(f"  - 最大耗时: {metrics.max_time:.3f}s")
        print(f"  - 错误率: {metrics.error_rate:.2%}")


def demonstrate_performance_advisor():
    """演示性能优化建议"""
    print("\n🔍 性能优化建议演示")
    print("=" * 40)

    advisor = PerformanceAdvisor()

    # 生成一些性能问题
    monitor = advisor.performance_monitor

    # 模拟慢操作
    for i in range(10):
        monitor.record_operation("slow_api_call", 0.2 + (i * 0.01), True)

    # 模拟高错误率操作
    for i in range(20):
        monitor.record_operation("unstable_operation", 0.05, i < 15)  # 15个失败，5个成功

    # 生成优化报告
    report = advisor.generate_optimization_report()
    print("性能优化建议报告:")
    print(report)


def main():
    """主演示函数"""
    print("🚀 Ontology Framework 性能优化功能演示")
    print("=" * 50)

    try:
        demonstrate_caching()
        demonstrate_indexing()
        demonstrate_batch_processing()
        demonstrate_performance_monitoring()
        demonstrate_performance_advisor()

        print("\n✅ 所有演示完成！")
        print("\n📊 性能优化功能总结:")
        print("  - ✅ LRU缓存系统")
        print("  - ✅ 缓存装饰器")
        print("  - ✅ 属性索引管理")
        print("  - ✅ 批量数据处理")
        print("  - ✅ 性能监控")
        print("  - ✅ 智能优化建议")

    except Exception as e:
        print(f"\n❌ 演示过程中出现错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()