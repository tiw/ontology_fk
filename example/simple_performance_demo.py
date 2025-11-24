#!/usr/bin/env python3
"""
简化的性能优化演示脚本

直接从性能模块导入，避免循环导入问题。
"""

import sys
import os
import time

# 添加src目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

def test_lru_cache():
    """测试LRU缓存功能"""
    print("\n🔍 LRU缓存功能测试")
    print("=" * 40)

    try:
        from ontology_framework.performance import LRUCache

        # 创建缓存
        cache = LRUCache(max_size=3, ttl_seconds=2)
        print("✅ 创建LRU缓存成功")

        # 测试基本操作
        cache.put("key1", "value1")
        cache.put("key2", "value2")
        cache.put("key3", "value3")

        print(f"获取key1: {cache.get('key1')}")
        print(f"获取key2: {cache.get('key2')}")

        # 测试LRU淘汰
        cache.put("key4", "value4")
        print(f"添加key4后，key1是否被淘汰: {cache.get('key1') is None}")

        # 显示统计
        stats = cache.get_stats()
        print(f"缓存统计: 大小={stats['size']}, 命中率={stats['hit_rate']:.2%}")

        return True

    except Exception as e:
        print(f"❌ LRU缓存测试失败: {e}")
        return False


def test_index_manager():
    """测试索引管理器"""
    print("\n🔍 索引管理器测试")
    print("=" * 40)

    try:
        from ontology_framework.performance import IndexManager, IndexDefinition

        # 创建索引管理器
        manager = IndexManager()
        print("✅ 创建索引管理器成功")

        # 创建索引
        index_def = IndexDefinition(
            name="test_index",
            property_name="name",
            index_type="hash",
            unique=False
        )
        index = manager.create_index(index_def)
        print("✅ 创建索引成功")

        # 测试索引操作
        index.add("Alice", "obj1")
        index.add("Bob", "obj2")
        index.add("Alice", "obj3")

        alice_objects = index.find("Alice")
        print(f"查询Alice: {alice_objects}")

        # 显示索引统计
        stats = index.get_stats()
        print(f"索引统计: {stats}")

        return True

    except Exception as e:
        print(f"❌ 索引管理器测试失败: {e}")
        return False


def test_performance_monitoring():
    """测试性能监控"""
    print("\n🔍 性能监控测试")
    print("=" * 40)

    try:
        from ontology_framework.performance import PerformanceMonitor

        # 创建性能监控器
        monitor = PerformanceMonitor()
        print("✅ 创建性能监控器成功")

        # 记录一些操作
        monitor.record_operation("test_operation", 0.05, True)
        monitor.record_operation("test_operation", 0.08, True)
        monitor.record_operation("test_operation", 0.12, True)

        # 获取指标
        metrics = monitor.get_metrics("test_operation")
        print(f"操作统计: 次数={metrics.operation_count}, 平均耗时={metrics.avg_time:.3f}s")

        return True

    except Exception as e:
        print(f"❌ 性能监控测试失败: {e}")
        return False


def test_cached_decorator():
    """测试缓存装饰器"""
    print("\n🔍 缓存装饰器测试")
    print("=" * 40)

    try:
        from ontology_framework.performance import cached

        call_count = 0

        @cached(cache_name="test_func", ttl_seconds=1)
        def expensive_function(x, y):
            nonlocal call_count
            call_count += 1
            time.sleep(0.1)  # 模拟耗时操作
            return x + y

        print("✅ 创建缓存装饰器成功")

        # 第一次调用
        start = time.time()
        result1 = expensive_function(10, 20)
        time1 = time.time() - start

        # 第二次调用（应该从缓存获取）
        start = time.time()
        result2 = expensive_function(10, 20)
        time2 = time.time() - start

        print(f"第一次调用: 结果={result1}, 耗时={time1:.3f}s, 调用次数={call_count}")
        print(f"第二次调用: 结果={result2}, 耗时={time2:.3f}s, 调用次数={call_count}")

        if call_count == 1 and time2 < time1 / 2:
            print("✅ 缓存装饰器工作正常")
            return True
        else:
            print("❌ 缓存装饰器未正常工作")
            return False

    except Exception as e:
        print(f"❌ 缓存装饰器测试失败: {e}")
        return False


def test_performance_advisor():
    """测试性能优化建议"""
    print("\n🔍 性能优化建议测试")
    print("=" * 40)

    try:
        from ontology_framework.performance import PerformanceAdvisor

        advisor = PerformanceAdvisor()
        print("✅ 创建性能优化建议器成功")

        # 生成一些性能数据
        monitor = advisor.performance_monitor
        for i in range(5):
            monitor.record_operation("slow_operation", 0.15, True)  # 150ms，较慢

        # 生成建议报告
        report = advisor.generate_optimization_report()
        print("优化报告:")
        print(report[:200] + "..." if len(report) > 200 else report)

        return True

    except Exception as e:
        print(f"❌ 性能优化建议测试失败: {e}")
        return False


def main():
    """主测试函数"""
    print("🚀 Ontology Framework 性能优化功能测试")
    print("=" * 50)

    tests = [
        ("LRU缓存", test_lru_cache),
        ("索引管理器", test_index_manager),
        ("性能监控", test_performance_monitoring),
        ("缓存装饰器", test_cached_decorator),
        ("性能优化建议", test_performance_advisor),
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        print(f"\n正在测试: {test_name}")
        try:
            if test_func():
                passed += 1
                print(f"✅ {test_name} 测试通过")
            else:
                print(f"❌ {test_name} 测试失败")
        except Exception as e:
            print(f"❌ {test_name} 测试出错: {e}")

    print(f"\n📊 测试结果总结:")
    print(f"通过: {passed}/{total}")
    print(f"成功率: {passed/total:.1%}")

    if passed == total:
        print("\n🎉 所有性能优化功能测试通过！")
    else:
        print(f"\n⚠️  有 {total-passed} 个测试失败")


if __name__ == "__main__":
    main()