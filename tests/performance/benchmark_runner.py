"""
性能基准测试框架

提供全面的性能测试和回归检测功能。
"""

import asyncio
import concurrent.futures
import csv
import json
import random
import statistics
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from src.ontology_framework.core import (
    Link,
    LinkType,
    ObjectInstance,
    ObjectType,
    Ontology,
    PropertyType,
)
from src.ontology_framework.performance import (
    AdvancedIndexManager,
    MultiLevelCache,
    PerformanceMonitor,
)


@dataclass
class BenchmarkResult:
    """基准测试结果"""

    test_name: str
    data_size: int
    execution_time: float  # ms
    memory_usage: float  # MB
    operations_per_second: float
    success_count: int
    error_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TestScenario:
    """测试场景定义"""

    name: str
    description: str
    data_generator: Callable
    test_function: Callable
    expected_duration: float  # ms
    memory_limit: float  # MB


class TestDataGenerator:
    """测试数据生成器"""

    def __init__(self):
        self.object_types = {}
        self.link_types = {}

    def setup_ontology_schema(self, ontology: Ontology):
        """设置本体模式"""
        # 创建测试对象类型
        test_object = ObjectType(
            api_name="TestObject", display_name="Test Object", primary_key="id"
        )
        test_object.add_property("id", PropertyType.STRING)
        test_object.add_property("name", PropertyType.STRING)
        test_object.add_property("value", PropertyType.INTEGER)
        test_object.add_property("status", PropertyType.STRING)
        test_object.add_property("category", PropertyType.STRING)

        ontology.register_object_type(test_object)
        self.object_types["TestObject"] = test_object

        # 创建复杂对象类型
        complex_object = ObjectType(
            api_name="ComplexObject", display_name="Complex Object", primary_key="id"
        )
        complex_object.add_property("id", PropertyType.STRING)
        complex_object.add_property("title", PropertyType.STRING)
        complex_object.add_property("description", PropertyType.STRING)
        complex_object.add_property("timestamp", PropertyType.TIMESTAMP)
        complex_object.add_property("tags", PropertyType.STRING)
        complex_object.add_property("priority", PropertyType.INTEGER)

        ontology.register_object_type(complex_object)
        self.object_types["ComplexObject"] = complex_object

        # 创建链接类型
        link_type = LinkType(
            api_name="TestLink",
            display_name="Test Link",
            source_object_type="TestObject",
            target_object_type="TestObject",
            cardinality="ONE_TO_MANY",
        )
        ontology.register_link_type(link_type)
        self.link_types["TestLink"] = link_type

    def generate_objects(
        self, count: int, object_type: str = "TestObject"
    ) -> List[ObjectInstance]:
        """生成测试对象"""
        objects = []
        categories = ["active", "inactive", "pending", "completed"]
        priorities = [1, 2, 3, 4, 5]

        for i in range(count):
            if object_type == "TestObject":
                obj = ObjectInstance(
                    object_type_api_name=object_type,
                    primary_key_value=f"obj_{i:06d}",
                    property_values={
                        "id": f"obj_{i:06d}",
                        "name": f"Test Object {i}",
                        "value": random.randint(1, 1000),
                        "status": random.choice(categories),
                        "category": f"category_{i % 10}",
                    },
                )
            else:  # ComplexObject
                obj = ObjectInstance(
                    object_type_api_name=object_type,
                    primary_key_value=f"complex_{i:06d}",
                    property_values={
                        "id": f"complex_{i:06d}",
                        "title": f"Complex Object {i}",
                        "description": f"This is a complex object with number {i}",
                        "timestamp": time.time() * 1000 + i,
                        "tags": f"tag_{i % 20},type_{i % 5}",
                        "priority": random.choice(priorities),
                    },
                )
            objects.append(obj)

        return objects

    def generate_links(
        self,
        source_objects: List[ObjectInstance],
        target_objects: List[ObjectInstance],
        link_type: str = "TestLink",
        link_ratio: float = 0.3,
    ) -> List[Link]:
        """生成测试链接"""
        links = []
        link_count = int(len(source_objects) * link_ratio)

        for i in range(link_count):
            source = random.choice(source_objects)
            target = random.choice(target_objects)

            links.append(
                Link(
                    link_type_api_name=link_type,
                    source_primary_key=source.primary_key_value,
                    target_primary_key=target.primary_key_value,
                )
            )

        return links


class PerformanceBenchmark:
    """性能基准测试器"""

    def __init__(self, output_dir: str = "benchmark_results"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.data_generator = TestDataGenerator()
        self.results: List[BenchmarkResult] = []

    def run_all_benchmarks(
        self, sizes: List[int] = None
    ) -> Dict[str, List[BenchmarkResult]]:
        """运行所有基准测试"""
        if sizes is None:
            sizes = [1000, 5000, 10000, 50000]

        test_scenarios = self._get_test_scenarios()
        all_results = {}

        for scenario in test_scenarios:
            print(f"Running benchmark: {scenario.name}")
            scenario_results = []

            for size in sizes:
                print(f"  Data size: {size}")
                try:
                    result = self._run_scenario(scenario, size)
                    scenario_results.append(result)
                    self.results.append(result)
                except Exception as e:
                    print(f"  Error: {e}")
                    error_result = BenchmarkResult(
                        test_name=scenario.name,
                        data_size=size,
                        execution_time=-1,
                        memory_usage=-1,
                        operations_per_second=0,
                        success_count=0,
                        error_count=1,
                        metadata={"error": str(e)},
                    )
                    scenario_results.append(error_result)

            all_results[scenario.name] = scenario_results

        # 保存结果
        self._save_results(all_results)

        return all_results

    def _get_test_scenarios(self) -> List[TestScenario]:
        """获取测试场景"""
        return [
            TestScenario(
                name="object_creation",
                description="对象创建性能测试",
                data_generator=lambda n: self.data_generator.generate_objects(n),
                test_function=self._test_object_creation,
                expected_duration=100.0,
                memory_limit=100.0,
            ),
            TestScenario(
                name="primary_key_lookup",
                description="主键查询性能测试",
                data_generator=lambda n: self.data_generator.generate_objects(n),
                test_function=self._test_primary_key_lookup,
                expected_duration=10.0,
                memory_limit=50.0,
            ),
            TestScenario(
                name="property_filter",
                description="属性过滤性能测试",
                data_generator=lambda n: self.data_generator.generate_objects(n),
                test_function=self._test_property_filter,
                expected_duration=50.0,
                memory_limit=50.0,
            ),
            TestScenario(
                name="complex_query",
                description="复杂查询性能测试",
                data_generator=lambda n: self.data_generator.generate_objects(n),
                test_function=self._test_complex_query,
                expected_duration=200.0,
                memory_limit=100.0,
            ),
            TestScenario(
                name="relationship_query",
                description="关系查询性能测试",
                data_generator=self._generate_linked_data,
                test_function=self._test_relationship_query,
                expected_duration=150.0,
                memory_limit=100.0,
            ),
            TestScenario(
                name="bulk_operations",
                description="批量操作性能测试",
                data_generator=lambda n: self.data_generator.generate_objects(n),
                test_function=self._test_bulk_operations,
                expected_duration=300.0,
                memory_limit=200.0,
            ),
        ]

    @contextmanager
    def _measure_performance(self):
        """性能测量上下文管理器"""
        import gc

        import psutil

        process = psutil.Process()

        # 测量前内存
        gc.collect()
        memory_before = process.memory_info().rss / 1024 / 1024  # MB

        start_time = time.perf_counter()

        yield

        end_time = time.perf_counter()
        memory_after = process.memory_info().rss / 1024 / 1024  # MB

        execution_time = (end_time - start_time) * 1000  # ms
        memory_usage = memory_after - memory_before

        return execution_time, memory_usage

    def _run_scenario(self, scenario: TestScenario, data_size: int) -> BenchmarkResult:
        """运行单个测试场景"""
        # 生成测试数据
        test_data = scenario.data_generator(data_size)

        with self._measure_performance() as (execution_time, memory_usage):
            success_count, error_count = scenario.test_function(test_data)

        operations_per_second = (success_count + error_count) / (execution_time / 1000)

        return BenchmarkResult(
            test_name=scenario.name,
            data_size=data_size,
            execution_time=execution_time,
            memory_usage=memory_usage,
            operations_per_second=operations_per_second,
            success_count=success_count,
            error_count=error_count,
            metadata={
                "description": scenario.description,
                "expected_duration": scenario.expected_duration,
                "memory_limit": scenario.memory_limit,
            },
        )

    def _test_object_creation(self, objects: List[ObjectInstance]) -> Tuple[int, int]:
        """测试对象创建"""
        ontology = Ontology()
        self.data_generator.setup_ontology_schema(ontology)

        success_count = 0
        error_count = 0

        for obj in objects:
            try:
                ontology.add_object(obj)
                success_count += 1
            except Exception as e:
                error_count += 1

        return success_count, error_count

    def _test_primary_key_lookup(
        self, objects: List[ObjectInstance]
    ) -> Tuple[int, int]:
        """测试主键查询"""
        ontology = Ontology()
        self.data_generator.setup_ontology_schema(ontology)

        # 添加所有对象
        for obj in objects:
            ontology.add_object(obj)

        # 执行查询
        test_keys = [obj.primary_key_value for obj in objects[:100]]  # 测试前100个
        success_count = 0
        error_count = 0

        for key in test_keys:
            try:
                result = ontology.get_object("TestObject", key)
                if result:
                    success_count += 1
                else:
                    error_count += 1
            except Exception:
                error_count += 1

        return success_count, error_count

    def _test_property_filter(self, objects: List[ObjectInstance]) -> Tuple[int, int]:
        """测试属性过滤"""
        ontology = Ontology()
        self.data_generator.setup_ontology_schema(ontology)

        # 添加所有对象
        for obj in objects:
            ontology.add_object(obj)

        # 执行过滤查询
        test_values = ["active", "inactive", "pending", "completed"]
        success_count = 0
        error_count = 0

        for value in test_values:
            try:
                all_objects = ontology.get_objects_of_type("TestObject")
                filtered = [obj for obj in all_objects if obj.get("status") == value]
                success_count += 1
            except Exception:
                error_count += 1

        return success_count, error_count

    def _test_complex_query(self, objects: List[ObjectInstance]) -> Tuple[int, int]:
        """测试复杂查询"""
        ontology = Ontology()
        self.data_generator.setup_ontology_schema(ontology)

        # 添加所有对象
        for obj in objects:
            ontology.add_object(obj)

        success_count = 0
        error_count = 0

        # 复杂查询场景
        complex_queries = [
            lambda: [
                obj
                for obj in ontology.get_objects_of_type("TestObject")
                if obj.get("value") > 500 and obj.get("status") == "active"
            ],
            lambda: [
                obj
                for obj in ontology.get_objects_of_type("TestObject")
                if obj.get("category").startswith("category_")
                and obj.get("value") % 2 == 0
            ],
            lambda: len(
                [
                    obj
                    for obj in ontology.get_objects_of_type("TestObject")
                    if obj.get("status") in ["active", "pending"]
                    and obj.get("value") > 100
                ]
            ),
        ]

        for query_func in complex_queries:
            try:
                result = query_func()
                success_count += 1
            except Exception:
                error_count += 1

        return success_count, error_count

    def _generate_linked_data(self, n: int) -> Tuple[List[ObjectInstance], List[Link]]:
        """生成带链接的测试数据"""
        objects = self.data_generator.generate_objects(n)
        links = self.data_generator.generate_links(objects, objects)
        return objects, links

    def _test_relationship_query(
        self, data: Tuple[List[ObjectInstance], List[Link]]
    ) -> Tuple[int, int]:
        """测试关系查询"""
        objects, links = data

        ontology = Ontology()
        self.data_generator.setup_ontology_schema(ontology)

        # 添加对象和链接
        for obj in objects:
            ontology.add_object(obj)

        for link in links:
            ontology.create_link(
                link.link_type_api_name,
                link.source_primary_key,
                link.target_primary_key,
            )

        success_count = 0
        error_count = 0

        # 关系查询测试
        try:
            # 查询所有链接
            all_links = ontology.get_all_links()
            success_count += 1

            # 查询特定对象的关联对象
            test_objects = objects[:10]
            for obj in test_objects:
                related_links = [
                    link
                    for link in all_links
                    if link.source_primary_key == obj.primary_key_value
                    or link.target_primary_key == obj.primary_key_value
                ]
                success_count += 1

        except Exception:
            error_count += 1

        return success_count, error_count

    def _test_bulk_operations(self, objects: List[ObjectInstance]) -> Tuple[int, int]:
        """测试批量操作"""
        ontology = Ontology()
        self.data_generator.setup_ontology_schema(ontology)

        success_count = 0
        error_count = 0

        # 批量添加
        try:
            for obj in objects:
                ontology.add_object(obj)
            success_count += len(objects)
        except Exception:
            error_count += len(objects)

        # 批量查询
        try:
            all_objects = ontology.get_objects_of_type("TestObject")
            success_count += 1
        except Exception:
            error_count += 1

        # 批量更新（模拟）
        try:
            for obj in all_objects[:100]:  # 更新前100个对象
                obj.property_values["status"] = "updated"
            success_count += 100
        except Exception:
            error_count += 100

        return success_count, error_count

    def _save_results(self, all_results: Dict[str, List[BenchmarkResult]]):
        """保存测试结果"""
        timestamp = time.strftime("%Y%m%d_%H%M%S")

        # 保存JSON格式
        json_file = self.output_dir / f"benchmark_results_{timestamp}.json"
        json_data = {
            "timestamp": timestamp,
            "summary": {
                "total_tests": len(self.results),
                "average_duration": statistics.mean(
                    [r.execution_time for r in self.results if r.execution_time > 0]
                ),
                "total_errors": sum([r.error_count for r in self.results]),
            },
            "results": {
                scenario: [
                    {
                        "data_size": r.data_size,
                        "execution_time": r.execution_time,
                        "memory_usage": r.memory_usage,
                        "operations_per_second": r.operations_per_second,
                        "success_count": r.success_count,
                        "error_count": r.error_count,
                        "metadata": r.metadata,
                    }
                    for r in results
                ]
                for scenario, results in all_results.items()
            },
        }

        with open(json_file, "w") as f:
            json.dump(json_data, f, indent=2)

        # 保存CSV格式
        csv_file = self.output_dir / f"benchmark_results_{timestamp}.csv"
        with open(csv_file, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "test_name",
                    "data_size",
                    "execution_time_ms",
                    "memory_usage_mb",
                    "operations_per_second",
                    "success_count",
                    "error_count",
                ]
            )

            for result in self.results:
                writer.writerow(
                    [
                        result.test_name,
                        result.data_size,
                        result.execution_time,
                        result.memory_usage,
                        result.operations_per_second,
                        result.success_count,
                        result.error_count,
                    ]
                )

        print(f"Results saved to {json_file} and {csv_file}")

    def generate_report(self) -> str:
        """生成性能报告"""
        if not self.results:
            return "No benchmark results available."

        report = ["# Ontology Framework Performance Benchmark Report\n"]
        report.append(f"Generated at: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")

        # 汇总统计
        total_tests = len(self.results)
        successful_tests = len([r for r in self.results if r.execution_time > 0])
        avg_duration = statistics.mean(
            [r.execution_time for r in self.results if r.execution_time > 0]
        )

        report.append("## Summary")
        report.append(f"- Total Tests: {total_tests}")
        report.append(f"- Successful Tests: {successful_tests}")
        report.append(f"- Average Duration: {avg_duration:.2f} ms\n")

        # 按测试类型分组
        results_by_test = {}
        for result in self.results:
            if result.test_name not in results_by_test:
                results_by_test[result.test_name] = []
            results_by_test[result.test_name].append(result)

        report.append("## Test Results by Type\n")

        for test_name, test_results in results_by_test.items():
            report.append(f"### {test_name}")

            # 性能数据
            durations = [r.execution_time for r in test_results if r.execution_time > 0]
            sizes = [r.data_size for r in test_results]

            if durations:
                report.append(f"- Data Sizes: {min(sizes)} - {max(sizes)}")
                report.append(
                    f"- Duration Range: {min(durations):.2f} - {max(durations):.2f} ms"
                )
                report.append(
                    f"- Average Duration: {statistics.mean(durations):.2f} ms"
                )

                # 性能趋势
                if len(durations) > 1:
                    report.append(
                        f"- Performance Trend: {self._calculate_trend(sizes, durations)}"
                    )

            report.append("")

        return "\n".join(report)

    def _calculate_trend(self, sizes: List[int], durations: List[float]) -> str:
        """计算性能趋势"""
        if len(sizes) != len(durations) or len(sizes) < 2:
            return "Insufficient data"

        # 简单的线性回归
        n = len(sizes)
        sum_x = sum(sizes)
        sum_y = sum(durations)
        sum_xy = sum(x * y for x, y in zip(sizes, durations))
        sum_x2 = sum(x * x for x in sizes)

        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)

        if slope > 0.01:
            return f"Degrading (+{slope:.4f} ms/size)"
        elif slope < -0.01:
            return f"Improving ({slope:.4f} ms/size)"
        else:
            return "Stable"


class LoadTestScenario:
    """负载测试场景"""

    def __init__(self, benchmark: PerformanceBenchmark):
        self.benchmark = benchmark

    async def test_concurrent_reads(
        self, user_count: int = 50, duration: int = 60, operations_per_user: int = 100
    ) -> Dict[str, Any]:
        """并发读取测试"""
        # 准备测试数据
        ontology = Ontology()
        self.benchmark.data_generator.setup_ontology_schema(ontology)
        test_objects = self.benchmark.data_generator.generate_objects(10000)

        for obj in test_objects:
            ontology.add_object(obj)

        async def user_simulation(user_id: int) -> Dict[str, Any]:
            """模拟用户读取操作"""
            operations = 0
            errors = 0
            start_time = time.time()

            while (
                time.time() - start_time < duration and operations < operations_per_user
            ):

                try:
                    # 随机查询操作
                    operation = random.choice(
                        [
                            self._pk_lookup_test,
                            self._filter_test,
                            self._relationship_test,
                        ]
                    )

                    result = await asyncio.get_event_loop().run_in_executor(
                        None, operation, ontology, test_objects
                    )

                    if result:
                        operations += 1
                    else:
                        errors += 1

                except Exception:
                    errors += 1

                # 模拟用户思考时间
                await asyncio.sleep(0.01)

            return {
                "user_id": user_id,
                "operations": operations,
                "errors": errors,
                "duration": time.time() - start_time,
            }

        # 启动并发用户
        start_time = time.time()
        tasks = [user_simulation(i) for i in range(user_count)]
        user_results = await asyncio.gather(*tasks)
        total_time = time.time() - start_time

        # 统计结果
        total_operations = sum(result["operations"] for result in user_results)
        total_errors = sum(result["errors"] for result in user_results)

        return {
            "total_operations": total_operations,
            "total_errors": total_errors,
            "operations_per_second": total_operations / total_time,
            "error_rate": (
                total_errors / (total_operations + total_errors)
                if total_operations + total_errors > 0
                else 0
            ),
            "average_user_latency": sum(result["duration"] for result in user_results)
            / len(user_results)
            * 1000,
            "user_results": user_results,
        }

    def _pk_lookup_test(
        self, ontology: Ontology, test_objects: List[ObjectInstance]
    ) -> bool:
        """主键查询测试"""
        random_obj = random.choice(test_objects)
        result = ontology.get_object("TestObject", random_obj.primary_key_value)
        return result is not None

    def _filter_test(
        self, ontology: Ontology, test_objects: List[ObjectInstance]
    ) -> bool:
        """过滤查询测试"""
        all_objects = ontology.get_objects_of_type("TestObject")
        filtered = [obj for obj in all_objects if obj.get("status") == "active"]
        return len(filtered) >= 0

    def _relationship_test(
        self, ontology: Ontology, test_objects: List[ObjectInstance]
    ) -> bool:
        """关系查询测试"""
        links = ontology.get_all_links()
        return len(links) >= 0


def main():
    """主函数"""
    print("Ontology Framework Performance Benchmark")
    print("=" * 50)

    # 创建基准测试器
    benchmark = PerformanceBenchmark()

    # 运行基准测试
    print("Running benchmarks...")
    results = benchmark.run_all_benchmarks()

    # 生成报告
    report = benchmark.generate_report()
    print("\n" + report)

    # 保存报告
    report_file = (
        Path("benchmark_results") / f"report_{time.strftime('%Y%m%d_%H%M%S')}.md"
    )
    with open(report_file, "w") as f:
        f.write(report)

    print(f"\nReport saved to {report_file}")

    # 运行负载测试
    print("\nRunning load tests...")
    load_test = LoadTestScenario(benchmark)

    # 使用异步运行负载测试
    async def run_load_test():
        return await load_test.test_concurrent_reads(user_count=20, duration=30)

    load_result = asyncio.run(run_load_test())

    print(f"Load Test Results:")
    print(f"  Total Operations: {load_result['total_operations']}")
    print(f"  Operations/Second: {load_result['operations_per_second']:.2f}")
    print(f"  Error Rate: {load_result['error_rate']:.2%}")
    print(f"  Average Latency: {load_result['average_user_latency']:.2f} ms")


if __name__ == "__main__":
    main()
