# 性能基准测试
# 使用pytest-benchmark进行性能测试和基准建立

import pytest
import time
from typing import List

from src.ontology_framework.core import (
    PropertyType, PropertyDefinition, ObjectType, LinkType, ActionType,
    ObjectInstance, ObjectSet, Ontology, PrimitiveType, ObjectTypeSpec
)
from src.ontology_framework.permissions import AccessControlList, PermissionType


class TestPerformanceBenchmarks:
    """性能基准测试类"""

    def test_large_scale_object_creation(self, benchmark):
        """测试大规模对象创建性能"""
        ontology = Ontology()

        # 创建对象类型
        user_type = ObjectType(
            api_name="user",
            display_name="用户",
            properties={
                "id": PropertyDefinition("id", PropertyType.STRING),
                "name": PropertyDefinition("name", PropertyType.STRING),
                "email": PropertyDefinition("email", PropertyType.STRING),
                "department": PropertyDefinition("department", PropertyType.STRING),
                "salary": PropertyDefinition("salary", PropertyType.INTEGER)
            },
            primary_key="id"
        )
        ontology.register_object_type(user_type)

        def create_large_number_of_objects():
            """创建大量对象的函数"""
            objects = []
            for i in range(1000):
                obj = ObjectInstance(
                    object_type_api_name="user",
                    primary_key_value=f"user_{i}",
                    property_values={
                        "id": f"user_{i}",
                        "name": f"用户{i}",
                        "email": f"user{i}@example.com",
                        "department": f"部门{i % 10}",
                        "salary": 50000 + (i % 100) * 1000
                    }
                )
                objects.append(obj)
                ontology.add_object(obj)
            return objects

        # 基准测试：创建1000个对象
        result = benchmark(create_large_number_of_objects)
        assert len(result) == 1000

    def test_object_set_filtering_performance(self, benchmark):
        """测试对象集合过滤性能"""
        # 创建预置数据
        ontology = Ontology()
        user_type = ObjectType(
            api_name="user",
            display_name="用户",
            properties={
                "id": PropertyDefinition("id", PropertyType.STRING),
                "department": PropertyDefinition("department", PropertyType.STRING),
                "salary": PropertyDefinition("salary", PropertyType.INTEGER)
            },
            primary_key="id"
        )
        ontology.register_object_type(user_type)

        # 创建5000个对象
        objects = []
        departments = ["工程", "销售", "市场", "人事", "财务"]
        for i in range(5000):
            obj = ObjectInstance(
                object_type_api_name="user",
                primary_key_value=f"user_{i}",
                property_values={
                    "id": f"user_{i}",
                    "department": departments[i % len(departments)],
                    "salary": 40000 + (i % 200) * 1000
                }
            )
            objects.append(obj)
            ontology.add_object(obj)

        # 创建ObjectSet
        obj_set = ObjectSet(user_type, objects)

        def filter_objects():
            """过滤对象的函数"""
            return obj_set.filter("department", "工程")

        # 基准测试：过滤操作
        result = benchmark(filter_objects)
        # 应该有1000个工程部门员工 (5000 / 5 departments)
        assert len(result.all()) == 1000

    def test_ontology_registration_performance(self, benchmark):
        """测试本体注册性能"""
        ontology = Ontology()

        def register_many_types():
            """注册多种类型的函数"""
            # 注册对象类型
            for i in range(50):
                obj_type = ObjectType(
                    api_name=f"type_{i}",
                    display_name=f"类型{i}",
                    properties={
                        "id": PropertyDefinition("id", PropertyType.STRING),
                        "name": PropertyDefinition("name", PropertyType.STRING)
                    },
                    primary_key="id"
                )
                ontology.register_object_type(obj_type)

            # 注册链接类型
            for i in range(30):
                link_type = LinkType(
                    api_name=f"link_{i}",
                    display_name=f"链接{i}",
                    source_object_type=f"type_{i % 10}",
                    target_object_type=f"type_{(i + 1) % 10}"
                )
                ontology.register_link_type(link_type)

            # 注册操作类型
            for i in range(20):
                action_type = ActionType(
                    api_name=f"action_{i}",
                    display_name=f"操作{i}",
                    target_object_types=[f"type_{i % 10}"]
                )
                ontology.register_action_type(action_type)

            return ontology

        # 基准测试：注册多种类型
        result = benchmark(register_many_types)
        assert len(result.object_types) == 50
        assert len(result.link_types) == 30
        assert len(result.action_types) == 20

    def test_object_aggregation_performance(self, benchmark):
        """测试对象聚合性能"""
        # 创建测试数据
        user_type = ObjectType(
            api_name="user",
            display_name="用户",
            properties={
                "id": PropertyDefinition("id", PropertyType.STRING),
                "salary": PropertyDefinition("salary", PropertyType.INTEGER)
            },
            primary_key="id"
        )

        objects = []
        for i in range(2000):
            obj = ObjectInstance(
                object_type_api_name="user",
                primary_key_value=f"user_{i}",
                property_values={
                    "id": f"user_{i}",
                    "salary": 30000 + (i % 100) * 1000  # 30k-129k范围
                }
            )
            objects.append(obj)

        obj_set = ObjectSet(user_type, objects)

        def perform_aggregations():
            """执行多种聚合操作"""
            sum_result = obj_set.aggregate("salary", "sum")
            avg_result = obj_set.aggregate("salary", "avg")
            max_result = obj_set.aggregate("salary", "max")
            min_result = obj_set.aggregate("salary", "min")
            count_result = obj_set.aggregate("salary", "count")

            return {
                "sum": sum_result,
                "avg": avg_result,
                "max": max_result,
                "min": min_result,
                "count": count_result
            }

        # 基准测试：聚合操作
        result = benchmark(perform_aggregations)
        assert result["count"] == 2000
        assert 30000 <= result["min"] < 40000
        assert 120000 <= result["max"] < 130000

    def test_permission_check_performance(self, benchmark):
        """测试权限检查性能"""
        # 创建大型ACL
        acl = AccessControlList()

        # 为大量用户授予权限
        for i in range(1000):
            user_id = f"user_{i}"
            acl.grant(user_id, PermissionType.VIEW)
            if i % 2 == 0:
                acl.grant(user_id, PermissionType.EDIT)
            if i % 5 == 0:
                acl.grant(user_id, PermissionType.DELETE)

        def check_multiple_permissions():
            """检查多个权限"""
            check_count = 0
            success_count = 0

            for i in range(500):
                user_id = f"user_{i * 2}"  # 检查偶数用户
                check_count += 1

                if acl.check(user_id, PermissionType.VIEW):
                    success_count += 1
                if acl.check(user_id, PermissionType.EDIT):
                    success_count += 1
                if acl.check(user_id, PermissionType.DELETE):
                    success_count += 1

            return check_count, success_count

        # 基准测试：权限检查
        result = benchmark(check_multiple_permissions)
        checks, successes = result
        assert checks == 500
        assert successes > 0  # 至少有一些权限检查成功

    def test_object_retrieval_performance(self, benchmark):
        """测试对象检索性能"""
        ontology = Ontology()

        # 创建对象类型
        user_type = ObjectType(
            api_name="user",
            display_name="用户",
            properties={
                "id": PropertyDefinition("id", PropertyType.STRING),
                "name": PropertyDefinition("name", PropertyType.STRING)
            },
            primary_key="id"
        )
        ontology.register_object_type(user_type)

        # 添加大量对象
        user_objects = []
        for i in range(3000):
            obj = ObjectInstance(
                object_type_api_name="user",
                primary_key_value=f"user_{i}",
                property_values={
                    "id": f"user_{i}",
                    "name": f"用户{i}"
                }
            )
            user_objects.append(obj)
            ontology.add_object(obj)

        def retrieve_random_objects():
            """检索随机对象"""
            retrieved_count = 0

            # 检索一些特定对象
            test_ids = [100, 500, 1000, 1500, 2000, 2500]
            for test_id in test_ids:
                if test_id < 3000:
                    obj = ontology.get_object("user", f"user_{test_id}")
                    if obj is not None:
                        retrieved_count += 1

            return retrieved_count

        # 基准测试：对象检索
        result = benchmark(retrieve_random_objects)
        assert result == 6  # 应该找到所有6个测试对象

    def test_search_around_performance(self, benchmark):
        """测试关系搜索性能"""
        ontology = Ontology()

        # 创建对象类型
        user_type = ObjectType("user", "用户", primary_key="id")
        project_type = ObjectType("project", "项目", primary_key="id")

        ontology.register_object_type(user_type)
        ontology.register_object_type(project_type)

        # 创建链接类型
        works_on = LinkType(
            api_name="works_on",
            display_name="参与项目",
            source_object_type="user",
            target_object_type="project"
        )
        ontology.register_link_type(works_on)

        # 创建对象
        users = []
        projects = []

        for i in range(100):
            user = ObjectInstance("user", f"user_{i}", {"id": f"user_{i}"})
            users.append(user)
            ontology.add_object(user)

        for i in range(20):
            project = ObjectInstance("project", f"project_{i}", {"id": f"project_{i}"})
            projects.append(project)
            ontology.add_object(project)

        # 创建大量链接关系
        for i, user in enumerate(users):
            # 每个用户参与2-4个项目
            for j in range(2 + (i % 3)):
                project_id = f"project_{(i + j) % 20}"
                ontology.create_link("works_on", user.primary_key_value, project_id)

        # 创建ObjectSet进行搜索（需要传递ontology上下文）
        user_set = ObjectSet(user_type, users, ontology)

        def perform_search_around():
            """执行关系搜索"""
            return user_set.search_around("works_on")

        # 基准测试：关系搜索
        result = benchmark(perform_search_around)
        # 验证返回了项目对象集合
        assert result.object_type.api_name == "project"


class TestMemoryUsage:
    """内存使用测试"""

    def test_memory_efficiency_large_dataset(self):
        """测试大数据集的内存效率"""
        import sys

        ontology = Ontology()

        # 创建简单对象类型
        simple_type = ObjectType(
            api_name="simple",
            display_name="简单对象",
            properties={
                "id": PropertyDefinition("id", PropertyType.STRING)
            },
            primary_key="id"
        )
        ontology.register_object_type(simple_type)

        # 测量创建大量对象的内存使用
        objects = []
        memory_before = sys.getsizeof(ontology._object_store)

        for i in range(5000):
            obj = ObjectInstance(
                object_type_api_name="simple",
                primary_key_value=f"obj_{i}",
                property_values={"id": f"obj_{i}"}
            )
            objects.append(obj)
            ontology.add_object(obj)

        memory_after = sys.getsizeof(ontology._object_store)
        memory_increase = memory_after - memory_before

        # 验证内存增长在合理范围内
        # 每个对象应该占用合理的内存空间
        avg_memory_per_object = memory_increase / 5000
        assert avg_memory_per_object > 0  # 确保确实使用了内存
        assert avg_memory_per_object < 10000  # 每个对象不超过10KB

        # 验证所有对象都能正确检索
        assert len(ontology.get_objects_of_type("simple")) == 5000


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--benchmark-only"])