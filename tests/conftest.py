"""
Pytest 配置文件

提供测试夹具、测试配置和通用测试工具。
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock
from typing import Dict, Any, Generator

# 导入项目核心模块
from ontology_framework.core import (
    Ontology, ObjectType, LinkType, ActionType,
    ObjectInstance, ObjectSet, PropertyType
)
from ontology_framework.functions import ontology_function
from ontology_framework.permissions import PermissionManager


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
        title_property="name"
    )
    employee_type.add_property("id", PropertyType.STRING)
    employee_type.add_property("name", PropertyType.STRING)
    employee_type.add_property("salary", PropertyType.INTEGER)
    employee_type.add_property("department", PropertyType.STRING)

    department_type = ObjectType(
        api_name="department",
        display_name="Department",
        primary_key="id",
        title_property="name"
    )
    department_type.add_property("id", PropertyType.STRING)
    department_type.add_property("name", PropertyType.STRING)
    department_type.add_property("budget", PropertyType.INTEGER)

    # 注册链接类型
    works_for_link = LinkType(
        api_name="works_for",
        display_name="Works For",
        source_object_type="employee",
        target_object_type="department"
    )

    # 注册操作类型
    hire_action = ActionType(
        api_name="hire_employee",
        display_name="Hire Employee",
        target_object_types=["employee"]
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
        "department": "Engineering"
    }


@pytest.fixture
def sample_department_data() -> Dict[str, Any]:
    """提供示例部门数据"""
    return {
        "id": "dept001",
        "name": "Engineering",
        "budget": 1000000
    }


@pytest.fixture
def employee_instance(basic_ontology, sample_employee_data) -> ObjectInstance:
    """创建员工对象实例夹具"""
    return ObjectInstance(
        object_type_api_name="employee",
        primary_key_value="emp001",
        property_values=sample_employee_data,
        ontology=basic_ontology
    )


@pytest.fixture
def department_instance(basic_ontology, sample_department_data) -> ObjectInstance:
    """创建部门对象实例夹具"""
    return ObjectInstance(
        object_type_api_name="department",
        primary_key_value="dept001",
        property_values=sample_department_data,
        ontology=basic_ontology
    )


@pytest.fixture
def permission_manager():
    """创建权限管理器夹具"""
    return PermissionManager()


@pytest.fixture
def mock_function_registry():
    """创建模拟函数注册表"""
    return Mock()


# 测试数据工厂函数
def create_employee_object_type(api_name: str = "employee", properties: Dict[str, Any] = None) -> ObjectType:
    """创建员工对象类型的工厂函数"""
    obj_type = ObjectType(
        api_name=api_name,
        display_name=api_name.title(),
        primary_key="id",
        title_property="name"
    )

    default_properties = {
        "id": PropertyType.STRING,
        "name": PropertyType.STRING,
        "salary": PropertyType.INTEGER,
        "department": PropertyType.STRING
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
        target_object_type=target_type
    )


def create_action_type(api_name: str, target_types: list = None) -> ActionType:
    """创建操作类型的工厂函数"""
    return ActionType(
        api_name=api_name,
        display_name=api_name.replace("_", " ").title(),
        target_object_types=target_types or []
    )


# 测试标记定义
pytest_plugins = []

def pytest_configure(config):
    """配置pytest标记"""
    config.addinivalue_line(
        "markers", "unit: 单元测试标记"
    )
    config.addinivalue_line(
        "markers", "integration: 集成测试标记"
    )
    config.addinivalue_line(
        "markers", "performance: 性能测试标记"
    )
    config.addinivalue_line(
        "markers", "slow: 慢速测试标记"
    )
    config.addinivalue_line(
        "markers", "security: 安全测试标记"
    )


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
        "--run-slow",
        action="store_true",
        default=False,
        help="运行慢速测试"
    )
    parser.addoption(
        "--run-performance",
        action="store_true",
        default=False,
        help="运行性能测试"
    )
    parser.addoption(
        "--integration-only",
        action="store_true",
        default=False,
        help="只运行集成测试"
    )


# 通用测试工具函数
class TestUtils:
    """测试工具类"""

    @staticmethod
    def assert_object_instance_equals(instance1: ObjectInstance, instance2: ObjectInstance):
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
            api_name="department",
            display_name="Department",
            primary_key="id"
        )
        department.add_property("id", PropertyType.STRING)
        department.add_property("name", PropertyType.STRING)
        ontology.register_object_type(department)

        # 项目类型
        project = ObjectType(
            api_name="project",
            display_name="Project",
            primary_key="id"
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
            data.append({
                "id": f"obj_{i:04d}",
                "name": f"Object {i}",
                "value": i * 10,
                "category": f"Category {i % 10}"
            })
        return data


@pytest.fixture
def test_utils():
    """测试工具夹具"""
    return TestUtils()