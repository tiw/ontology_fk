#!/usr/bin/env python3
"""
性能优化集成演示

展示如何将性能优化功能集成到实际的 Ontology Framework 应用中。
"""

import sys
import os
import time

# 添加src目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from ontology_framework.optimized_core import OptimizedOntology
from ontology_framework.performance import (
    PerformanceOptimizerAdapter, BatchProcessor, BatchConfig,
    MemoryOptimizer, get_performance_monitor
)
from ontology_framework.core import ObjectType, ObjectInstance, PropertyType


def demonstrate_optimized_employee_management():
    """演示优化的员工管理系统"""
    print("\n🏢 优化的员工管理系统演示")
    print("=" * 50)

    # 创建优化的本体
    ontology = OptimizedOntology(enable_monitoring=True, enable_cache=True)
    print("✅ 创建优化的本体成功")

    # 定义员工对象类型
    employee_type = ObjectType("employee", "Employee", "employee_id")
    employee_type.add_property("employee_id", PropertyType.STRING, description="员工ID")
    employee_type.add_property("name", PropertyType.STRING, description="姓名")
    employee_type.add_property("department", PropertyType.STRING, description="部门")
    employee_type.add_property("position", PropertyType.STRING, description="职位")
    employee_type.add_property("salary", PropertyType.INTEGER, description="薪资")
    employee_type.add_property("hire_date", PropertyType.DATE, description="入职日期")
    ontology.register_object_type(employee_type)

    # 定义部门对象类型
    department_type = ObjectType("department", "Department", "dept_id")
    department_type.add_property("dept_id", PropertyType.STRING, description="部门ID")
    department_type.add_property("name", PropertyType.STRING, description="部门名称")
    department_type.add_property("manager", PropertyType.STRING, description="部门经理")
    ontology.register_object_type(department_type)

    print("✅ 注册对象类型成功")

    # 创建性能优化适配器并安装优化
    adapter = PerformanceOptimizerAdapter(ontology)
    adapter.install_optimizations()
    print("✅ 安装性能优化成功")

    # 批量创建部门数据
    departments = [
        ("dept001", "Engineering", "Alice Johnson"),
        ("dept002", "Sales", "Bob Smith"),
        ("dept003", "Marketing", "Carol Davis"),
        ("dept004", "HR", "David Wilson"),
    ]

    department_objects = []
    for dept_id, name, manager in departments:
        dept = ObjectInstance(
            object_type_api_name="department",
            primary_key_value=dept_id,
            property_values={
                "dept_id": dept_id,
                "name": name,
                "manager": manager
            }
        )
        department_objects.append(dept)

    # 批量添加部门
    batch_processor = BatchProcessor(BatchConfig(batch_size=10))
    dept_result = batch_processor.batch_add_objects(ontology, department_objects)
    print(f"✅ 批量添加部门成功: {dept_result['success_count']}/{dept_result['total_objects']}")

    # 批量创建员工数据
    employees = []
    positions = ["Engineer", "Senior Engineer", "Manager", "Director", "Analyst"]
    departments_list = ["Engineering", "Sales", "Marketing", "HR"]

    for i in range(200):
        dept = departments_list[i % len(departments_list)]
        position = positions[i % len(positions)]

        employee = ObjectInstance(
            object_type_api_name="employee",
            primary_key_value=f"emp_{i:04d}",
            property_values={
                "employee_id": f"emp_{i:04d}",
                "name": f"Employee {i}",
                "department": dept,
                "position": position,
                "salary": 50000 + (i * 100) + (len(position) * 5000),
                "hire_date": f"2020-{(i % 12) + 1:02d}-15"
            }
        )
        employees.append(employee)

    # 批量添加员工
    start_time = time.time()
    emp_result = batch_processor.batch_add_objects(ontology, employees)
    batch_time = time.time() - start_time

    print(f"✅ 批量添加员工成功:")
    print(f"   - 总数: {emp_result['total_objects']}")
    print(f"   - 成功: {emp_result['success_count']}")
    print(f"   - 耗时: {batch_time:.3f}s")
    print(f"   - 吞吐量: {emp_result['throughput']:.1f} employees/sec")

    return ontology, adapter


def demonstrate_query_performance(ontology, adapter):
    """演示查询性能"""
    print("\n⚡ 查询性能演示")
    print("=" * 40)

    # 测试部门查询
    departments = ["Engineering", "Sales", "Marketing", "HR"]

    for dept in departments:
        start_time = time.time()
        dept_employees = ontology.get_objects_of_type("employee")
        filtered = dept_employees.filter("department", dept)
        query_time = time.time() - start_time

        print(f"查询 {dept} 部门员工:")
        print(f"   - 结果数量: {len(filtered.all())}")
        print(f"   - 查询时间: {query_time:.4f}s")
        print(f"   - 平均每个员工: {query_time/max(1, len(filtered.all()))*1000:.2f}ms")

    # 批量查询测试
    print(f"\n批量查询测试:")
    queries = [
        {"department": "Engineering"},
        {"position": "Engineer"},
        {"salary": 60000},  # 这可能不会匹配任何结果
    ]

    start_time = time.time()
    batch_results = batch_processor.batch_query(ontology, "employee", queries)
    batch_query_time = time.time() - start_time

    print(f"批量 {len(queries)} 个查询耗时: {batch_query_time:.4f}s")
    print(f"总结果数量: {len(batch_results)}")


def demonstrate_memory_optimization(ontology):
    """演示内存优化"""
    print("\n💾 内存优化演示")
    print("=" * 40)

    # 分析内存使用
    memory_optimizer = MemoryOptimizer(ontology)
    memory_stats = memory_optimizer.analyze_memory_usage()

    print("内存使用分析:")
    if "summary" in memory_stats:
        summary = memory_stats["summary"]
        print(f"   - 总对象数: {summary['total_objects']}")
        print(f"   - 总内存使用: {summary['total_memory'] / 1024:.1f} KB")
        print(f"   - 平均每个对象: {summary['avg_memory_per_object']} bytes")

    # 获取优化建议
    suggestions = memory_optimizer.suggest_memory_optimizations()
    if suggestions:
        print("内存优化建议:")
        for suggestion in suggestions:
            print(f"   - {suggestion}")
    else:
        print("✅ 内存使用良好，无需优化建议")

    # 执行内存优化
    optimizations = memory_optimizer.optimize_memory_usage()
    if optimizations:
        print("已执行的内存优化:")
        for opt in optimizations:
            print(f"   - {opt}")


def demonstrate_performance_monitoring(ontology):
    """演示性能监控"""
    print("\n📊 性能监控演示")
    print("=" * 40)

    # 执行一些操作来生成性能数据
    monitor = get_performance_monitor()

    # 模拟各种操作
    for i in range(10):
        # 获取对象操作
        start = time.time()
        employees = ontology.get_objects_of_type("employee")
        if employees.all():
            first_employee = employees.all()[0]
            first_employee.get("name")
        monitor.record_operation("get_object", time.time() - start, True)

        # 过滤操作
        start = time.time()
        filtered = employees.filter("department", "Engineering")
        monitor.record_operation("filter_query", time.time() - start, True)

    # 模拟一些慢操作
    for i in range(3):
        start = time.time()
        time.sleep(0.01)  # 模拟10ms的处理时间
        monitor.record_operation("complex_calculation", time.time() - start, True)

    # 获取性能统计
    stats = ontology.get_performance_stats()
    print("性能统计:")

    if "operation_stats" in stats:
        op_stats = stats["operation_stats"]
        print(f"   - 对象创建: {op_stats.get('objects_created', 0)}")
        print(f"   - 对象获取: {op_stats.get('objects_retrieved', 0)}")
        print(f"   - 查询执行: {op_stats.get('queries_executed', 0)}")

    # 显示监控指标
    all_metrics = monitor.get_all_metrics()
    print("\n操作性能指标:")
    for op_name, metrics in all_metrics.items():
        if metrics.operation_count > 0:
            print(f"   - {op_name}:")
            print(f"     * 执行次数: {metrics.operation_count}")
            print(f"     * 平均耗时: {metrics.avg_time*1000:.2f}ms")
            print(f"     * 最大耗时: {metrics.max_time*1000:.2f}ms")
            if metrics.error_count > 0:
                print(f"     * 错误率: {metrics.error_rate:.1%}")


def demonstrate_optimization_recommendations(adapter):
    """演示优化建议"""
    print("\n🔧 优化建议演示")
    print("=" * 40)

    # 获取优化建议
    recommendations = adapter.get_optimization_recommendations()

    if recommendations:
        print("当前系统优化建议:")
        for i, rec in enumerate(recommendations, 1):
            print(f"   {i}. {rec}")
    else:
        print("✅ 系统性能良好，暂无优化建议")

    # 应用自动优化
    print("\n应用自动优化...")
    adapter.apply_auto_optimizations()
    print("✅ 自动优化应用完成")


def main():
    """主演示函数"""
    print("🚀 Ontology Framework 性能优化集成演示")
    print("=" * 60)

    try:
        # 1. 创建优化的员工管理系统
        ontology, adapter = demonstrate_optimized_employee_management()

        # 2. 演示查询性能
        demonstrate_query_performance(ontology, adapter)

        # 3. 演示内存优化
        demonstrate_memory_optimization(ontology)

        # 4. 演示性能监控
        demonstrate_performance_monitoring(ontology)

        # 5. 演示优化建议
        demonstrate_optimization_recommendations(adapter)

        print("\n🎉 性能优化集成演示完成！")
        print("\n📈 集成效果总结:")
        print("  - ✅ 优化的本体管理")
        print("  - ✅ 自动索引创建")
        print("  - ✅ 高效批量处理")
        print("  - ✅ 智能缓存管理")
        print("  - ✅ 实时性能监控")
        print("  - ✅ 内存使用优化")
        print("  - ✅ 自动优化建议")

        # 获取最终性能报告
        final_stats = ontology.get_performance_stats()
        if "cache_stats" in final_stats:
            cache_stats = final_stats["cache_stats"]
            print(f"\n📊 最终性能指标:")
            print(f"   - 缓存统计: {len(cache_stats)} 个缓存")
            print(f"   - 总对象数: {sum(len(objs) for objs in ontology._object_store.values())}")

    except Exception as e:
        print(f"\n❌ 演示过程中出现错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()