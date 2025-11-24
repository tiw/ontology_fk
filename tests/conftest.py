"""
Ontology Framework 测试配置文件

提供统一的测试夹具、测试数据和工具函数。
"""

import shutil
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Generator, List
from unittest.mock import MagicMock, Mock

import pytest

# 导入项目核心模块
from ontology_framework.core import (
    ActionContext,
    ActionType,
    Function,
    Link,
    LinkType,
    ObjectInstance,
    ObjectSet,
    ObjectType,
    Ontology,
    PrimitiveType,
    PropertyType,
)
from ontology_framework.functions import ontology_function, registry
from ontology_framework.permissions import AccessControlList, PermissionType, Principal
from ontology_framework.services import ObjectSetService


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """创建临时目录夹具"""
    temp_path = Path(tempfile.mkdtemp())
    try:
        yield temp_path
    finally:
        shutil.rmtree(temp_path)


@pytest.fixture
def basic_ontology() -> Ontology:
    """创建基础本体夹具"""
    ontology = Ontology()

    # 注册测试用的对象类型
    employee_type = ObjectType(
        api_name="employee",
        display_name="Employee",
        primary_key="id",
        title_property="name",
    )
    employee_type.add_property("id", PropertyType.STRING)
    employee_type.add_property("name", PropertyType.STRING)
    employee_type.add_property("salary", PropertyType.INTEGER)
    employee_type.add_property("department", PropertyType.STRING)

    department_type = ObjectType(
        api_name="department",
        display_name="Department",
        primary_key="id",
        title_property="name",
    )
    department_type.add_property("id", PropertyType.STRING)
    department_type.add_property("name", PropertyType.STRING)
    department_type.add_property("budget", PropertyType.INTEGER)

    # 注册链接类型
    works_for_link = LinkType(
        api_name="works_for",
        display_name="Works For",
        source_object_type="employee",
        target_object_type="department",
    )

    # 注册操作类型
    hire_action = ActionType(
        api_name="hire_employee",
        display_name="Hire Employee",
        target_object_types=["employee"],
    )

    # 注册到本体
    ontology.register_object_type(employee_type)
    ontology.register_object_type(department_type)
    ontology.register_link_type(works_for_link)
    ontology.register_action_type(hire_action)

    return ontology


@pytest.fixture
def sample_employee_data() -> Dict[str, Any]:
    """提供示例员工数据"""
    return {
        "id": "emp001",
        "name": "John Doe",
        "salary": 50000,
        "department": "Engineering",
    }


@pytest.fixture
def sample_department_data() -> Dict[str, Any]:
    """提供示例部门数据"""
    return {"id": "dept001", "name": "Engineering", "budget": 1000000}


@pytest.fixture
def employee_instance(basic_ontology, sample_employee_data) -> ObjectInstance:
    """创建员工对象实例夹具"""
    return ObjectInstance(
        object_type_api_name="employee",
        primary_key_value="emp001",
        property_values=sample_employee_data,
        ontology=basic_ontology,
    )


@pytest.fixture
def department_instance(basic_ontology, sample_department_data) -> ObjectInstance:
    """创建部门对象实例夹具"""
    return ObjectInstance(
        object_type_api_name="department",
        primary_key_value="dept001",
        property_values=sample_department_data,
        ontology=basic_ontology,
    )


@pytest.fixture
def access_control_list():
    """创建访问控制列表夹具"""
    acl = AccessControlList()

    # 添加示例权限
    acl.grant("user_001", PermissionType.VIEW)
    acl.grant("user_001", PermissionType.EDIT)
    acl.grant("user_002", PermissionType.VIEW)
    acl.grant("admin_001", PermissionType.OWNER)

    return acl


@pytest.fixture
def sample_principals():
    """示例主体夹具"""
    return {
        "user_001": Principal("user_001", "USER", ["employee", "engineering"]),
        "user_002": Principal("user_002", "USER", ["employee", "hr"]),
        "admin_001": Principal("admin_001", "USER", ["admin", "employee"]),
    }


@pytest.fixture
def mock_function_registry():
    """创建模拟函数注册表"""
    return Mock()


# 测试数据工厂函数
def create_employee_object_type(
    api_name: str = "employee", properties: Dict[str, Any] = None
) -> ObjectType:
    """创建员工对象类型的工厂函数"""
    obj_type = ObjectType(
        api_name=api_name,
        display_name=api_name.title(),
        primary_key="id",
        title_property="name",
    )

    default_properties = {
        "id": PropertyType.STRING,
        "name": PropertyType.STRING,
        "salary": PropertyType.INTEGER,
        "department": PropertyType.STRING,
    }

    properties = properties or default_properties
    for prop_name, prop_type in properties.items():
        obj_type.add_property(prop_name, prop_type)

    return obj_type


def create_link_type(api_name: str, source_type: str, target_type: str) -> LinkType:
    """创建链接类型的工厂函数"""
    return LinkType(
        api_name=api_name,
        display_name=api_name.replace("_", " ").title(),
        source_object_type=source_type,
        target_object_type=target_type,
    )


def create_action_type(api_name: str, target_types: list = None) -> ActionType:
    """创建操作类型的工厂函数"""
    return ActionType(
        api_name=api_name,
        display_name=api_name.replace("_", " ").title(),
        target_object_types=target_types or [],
    )


# 测试标记定义
pytest_plugins = []


def pytest_configure(config):
    """配置pytest标记"""
    config.addinivalue_line("markers", "unit: 单元测试标记")
    config.addinivalue_line("markers", "integration: 集成测试标记")
    config.addinivalue_line("markers", "performance: 性能测试标记")
    config.addinivalue_line("markers", "slow: 慢速测试标记")
    config.addinivalue_line("markers", "security: 安全测试标记")


# 测试收集钩子
def pytest_collection_modifyitems(config, items):
    """修改测试收集，为没有标记的测试添加unit标记"""
    for item in items:
        if not any(item.iter_markers()):
            item.add_marker(pytest.mark.unit)


# 跳过条件函数
def pytest_runtest_setup(item):
    """测试前的设置钩子"""
    # 检查是否有标记为slow的测试，在没有--run-slow参数时跳过
    if item.get_closest_marker("slow") and not item.config.getoption("--run-slow"):
        pytest.skip("需要 --run-slow 选项来运行慢速测试")


# 添加命令行选项
def pytest_addoption(parser):
    """添加命令行选项"""
    parser.addoption(
        "--run-slow", action="store_true", default=False, help="运行慢速测试"
    )
    parser.addoption(
        "--run-performance", action="store_true", default=False, help="运行性能测试"
    )
    parser.addoption(
        "--integration-only", action="store_true", default=False, help="只运行集成测试"
    )


# 通用测试工具函数
class TestUtils:
    """测试工具类"""

    @staticmethod
    def assert_object_instance_equals(
        instance1: ObjectInstance, instance2: ObjectInstance
    ):
        """断言两个对象实例相等"""
        assert instance1.object_type_api_name == instance2.object_type_api_name
        assert instance1.primary_key_value == instance2.primary_key_value
        assert instance1.property_values == instance2.property_values

    @staticmethod
    def create_test_ontology_with_multiple_objects():
        """创建包含多个对象类型的测试本体"""
        ontology = Ontology()

        # 员工类型
        employee = create_employee_object_type()
        ontology.register_object_type(employee)

        # 部门类型
        department = ObjectType(
            api_name="department", display_name="Department", primary_key="id"
        )
        department.add_property("id", PropertyType.STRING)
        department.add_property("name", PropertyType.STRING)
        ontology.register_object_type(department)

        # 项目类型
        project = ObjectType(
            api_name="project", display_name="Project", primary_key="id"
        )
        project.add_property("id", PropertyType.STRING)
        project.add_property("name", PropertyType.STRING)
        project.add_property("status", PropertyType.STRING)
        ontology.register_object_type(project)

        # 关系
        works_in = create_link_type("works_in", "employee", "department")
        assigned_to = create_link_type("assigned_to", "employee", "project")

        ontology.register_link_type(works_in)
        ontology.register_link_type(assigned_to)

        return ontology

    @staticmethod
    def create_performance_test_data(size: int = 1000):
        """创建性能测试数据"""
        data = []
        for i in range(size):
            data.append(
                {
                    "id": f"obj_{i:04d}",
                    "name": f"Object {i}",
                    "value": i * 10,
                    "category": f"Category {i % 10}",
                }
            )
        return data


@pytest.fixture
def test_utils():
    """测试工具夹具"""
    return TestUtils()


# 高级测试夹具
@pytest.fixture
def sample_ontology_with_objects() -> tuple[Ontology, Dict[str, ObjectInstance]]:
    """包含完整示例对象的本体夹具"""
    ontology = TestUtils.create_test_ontology_with_multiple_objects()

    objects = {}

    # 创建部门
    objects["dept_tech"] = ontology.create_object(
        "department", {"id": "tech_001", "name": "技术部"}
    )

    objects["dept_hr"] = ontology.create_object(
        "department", {"id": "hr_001", "name": "人事部"}
    )

    # 创建员工
    objects["emp_001"] = ontology.create_object(
        "employee",
        {"id": "emp_001", "name": "张三", "salary": 80000, "department": "tech_001"},
    )

    objects["emp_002"] = ontology.create_object(
        "employee",
        {"id": "emp_002", "name": "李四", "salary": 60000, "department": "hr_001"},
    )

    # 创建项目
    objects["proj_001"] = ontology.create_object(
        "project", {"id": "proj_001", "name": "本体框架项目", "status": "active"}
    )

    # 创建关系
    ontology.create_link("works_in", objects["emp_001"], objects["dept_tech"])
    ontology.create_link("works_in", objects["emp_002"], objects["dept_hr"])
    ontology.create_link("assigned_to", objects["emp_001"], objects["proj_001"])

    return ontology, objects


@pytest.fixture
def performance_ontology():
    """性能测试专用本体夹具"""
    ontology = Ontology()

    # 简单对象类型用于性能测试
    perf_type = ObjectType(
        api_name="PerfObject", display_name="性能测试对象", primary_key="id"
    )
    perf_type.add_property("id", PrimitiveType.STRING)
    perf_type.add_property("name", PrimitiveType.STRING)
    perf_type.add_property("value", PrimitiveType.INTEGER)
    perf_type.add_property("category", PrimitiveType.STRING)
    perf_type.add_property("timestamp", PrimitiveType.TIMESTAMP)

    ontology.register_object_type(perf_type)
    return ontology


@pytest.fixture
def large_object_set(performance_ontology):
    """大对象集合夹具，用于性能测试"""
    objects = []

    # 创建大量测试对象
    for i in range(1000):  # 1000个对象
        obj = performance_ontology.create_object(
            "PerfObject",
            {
                "id": f"perf_obj_{i:06d}",
                "name": f"性能测试对象 {i}",
                "value": i * 7,
                "category": f"category_{i % 20}",
                "timestamp": f"2024-01-{(i % 28) + 1:02d}T10:00:00Z",
            },
        )
        objects.append(obj)

    return objects


@pytest.fixture
def benchmark_timer():
    """基准测试计时器夹具"""

    class BenchmarkTimer:
        def __init__(self):
            self.times = []

        def start(self):
            """开始计时"""
            self.start_time = time.perf_counter()

        def stop(self):
            """停止计时并返回耗时"""
            end_time = time.perf_counter()
            elapsed = end_time - self.start_time
            self.times.append(elapsed)
            return elapsed

        def get_stats(self):
            """获取计时统计"""
            if not self.times:
                return {}

            return {
                "count": len(self.times),
                "total": sum(self.times),
                "average": sum(self.times) / len(self.times),
                "min": min(self.times),
                "max": max(self.times),
            }

    return BenchmarkTimer()


@pytest.fixture(autouse=True)
def cleanup_function_registry():
    """自动清理函数注册表"""
    registry.clear()
    yield
    registry.clear()


# 测试标记定义
pytest.mark.unit = pytest.mark.unit
pytest.mark.integration = pytest.mark.integration
pytest.mark.performance = pytest.mark.performance
pytest.mark.slow = pytest.mark.slow
pytest.mark.security = pytest.mark.security


# 性能测试装饰器
def performance_test(expected_max_time: float = None):
    """性能测试装饰器"""

    def decorator(func):
        def wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            result = func(*args, **kwargs)
            end_time = time.perf_counter()

            execution_time = end_time - start_time

            if expected_max_time and execution_time > expected_max_time:
                pytest.fail(
                    f"性能测试失败: 执行时间 {execution_time:.4f}s 超过预期最大时间 {expected_max_time:.4f}s"
                )

            print(f"\n性能测试 {func.__name__}: 执行时间 {execution_time:.4f}s")
            return result

        return wrapper

    return decorator


# 基准测试工具
class BenchmarkHelper:
    """基准测试辅助工具"""

    @staticmethod
    def measure_execution_time(func, *args, iterations=1, **kwargs):
        """测量函数执行时间"""
        times = []

        for _ in range(iterations):
            start_time = time.perf_counter()
            result = func(*args, **kwargs)
            end_time = time.perf_counter()

            times.append(end_time - start_time)

        return {
            "result": result,
            "times": times,
            "average": sum(times) / len(times),
            "min": min(times),
            "max": max(times),
        }

    @staticmethod
    def benchmark_memory_usage():
        """基准测试内存使用"""
        import os

        import psutil

        process = psutil.Process(os.getpid())
        return {
            "rss": process.memory_info().rss,
            "vms": process.memory_info().vms,
            "percent": process.memory_percent(),
        }


@pytest.fixture
def benchmark_helper():
    """基准测试辅助工具夹具"""
    return BenchmarkHelper()
