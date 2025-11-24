"""
扩展的核心模块单元测试

补充原有的测试文件，提高测试覆盖率，重点测试边缘条件和错误处理。
"""

import pytest
from unittest.mock import Mock, patch
from typing import Dict, Any

from ontology_framework.core import (
    Ontology, ObjectType, LinkType, ActionType,
    ObjectInstance, ObjectSet, PropertyType,
    TypeSpec, PrimitiveType, ObjectTypeSpec, ObjectSetTypeSpec,
    ActionContext
)


class TestObjectTypeEdgeCases:
    """测试ObjectType的边缘条件"""

    def test_object_type_empty_api_name(self):
        """测试空API名称"""
        with pytest.raises(ValueError, match="API名称不能为空"):
            ObjectType(api_name="", display_name="Test")

    def test_object_type_invalid_primary_key(self):
        """测试无效的主键"""
        obj_type = ObjectType(api_name="test", display_name="Test")
        with pytest.raises(KeyError, match="属性 'invalid_key' 不存在"):
            obj_type.primary_key = "invalid_key"

    def test_object_type_duplicate_property(self):
        """测试重复添加属性"""
        obj_type = ObjectType(api_name="test", display_name="Test")
        obj_type.add_property("name", PropertyType.STRING)

        with pytest.raises(ValueError, match="属性 'name' 已存在"):
            obj_type.add_property("name", PropertyType.INTEGER)

    def test_object_type_invalid_property_type(self):
        """测试无效的属性类型"""
        obj_type = ObjectType(api_name="test", display_name="Test")
        with pytest.raises(TypeError, match="属性类型必须是PropertyType枚举值"):
            obj_type.add_property("invalid", "invalid_type")

    def test_object_type_derived_property_missing_function(self):
        """测试缺少函数的派生属性"""
        obj_type = ObjectType(api_name="test", display_name="Test")
        with pytest.raises(ValueError, match="派生属性必须指定函数API名称"):
            obj_type.add_derived_property("derived", PropertyType.INTEGER, None)

    def test_object_type_get_property_nonexistent(self):
        """测试获取不存在的属性"""
        obj_type = ObjectType(api_name="test", display_name="Test")
        obj_type.add_property("name", PropertyType.STRING)

        with pytest.raises(KeyError):
            obj_type.get_property_spec("nonexistent")

    def test_object_type_validation_with_data(self):
        """测试对象类型数据验证"""
        obj_type = ObjectType(api_name="test", display_name="Test")
        obj_type.add_property("name", PropertyType.STRING, required=True)
        obj_type.add_property("age", PropertyType.INTEGER)

        # 正常数据
        valid_data = {"name": "test", "age": 25}
        assert obj_type.validate_data(valid_data) == []

        # 缺少必填字段
        invalid_data = {"age": 25}
        errors = obj_type.validate_data(invalid_data)
        assert len(errors) > 0
        assert any("name" in str(error) for error in errors)

        # 类型错误
        invalid_type_data = {"name": "test", "age": "invalid"}
        errors = obj_type.validate_data(invalid_type_data)
        assert len(errors) > 0


class TestLinkTypeEdgeCases:
    """测试LinkType的边缘条件"""

    def test_link_type_circular_reference(self):
        """测试循环引用"""
        # 创建两个链接类型，相互引用
        link1 = LinkType(
            api_name="link1",
            display_name="Link 1",
            source_object_type="type1",
            target_object_type="type2"
        )

        # 在实际实现中，这应该在注册时检查
        assert link1.source_object_type == "type1"
        assert link1.target_object_type == "type2"

    def test_link_type_self_reference(self):
        """测试自引用链接"""
        link = LinkType(
            api_name="self_ref",
            display_name="Self Reference",
            source_object_type="employee",
            target_object_type="employee"
        )

        assert link.source_object_type == link.target_object_type

    def test_link_type_bidirectional_properties(self):
        """测试双向链接属性"""
        link = LinkType(
            api_name="bidirectional",
            display_name="Bidirectional",
            source_object_type="type1",
            target_object_type="type2"
        )

        # 设置双向链接
        link.bidirectional = True
        link.reverse_link_api_name = "reverse_link"

        assert link.bidirectional is True
        assert link.reverse_link_api_name == "reverse_link"


class TestActionTypeEdgeCases:
    """测试ActionType的边缘条件"""

    def test_action_type_empty_target_types(self):
        """测试空目标类型列表"""
        action = ActionType(
            api_name="test_action",
            display_name="Test Action",
            target_object_types=[]
        )

        assert action.target_object_types == []

    def test_action_type_invalid_target_type(self):
        """测试无效目标类型"""
        action = ActionType(
            api_name="test_action",
            display_name="Test Action",
            target_object_types=["nonexistent_type"]
        )

        # 这应该在执行时验证，注册时不应该失败
        assert "nonexistent_type" in action.target_object_types

    def test_action_type_function_validation(self):
        """测试函数绑定验证"""
        action = ActionType(
            api_name="test_action",
            display_name="Test Action",
            backing_function_api_name="nonexistent_function"
        )

        assert action.backing_function_api_name == "nonexistent_function"


class TestObjectInstanceEdgeCases:
    """测试ObjectInstance的边缘条件"""

    def test_object_instance_invalid_primary_key(self):
        """测试无效的主键值"""
        with pytest.raises(ValueError, match="主键值不能为空"):
            ObjectInstance(
                object_type_api_name="test",
                primary_key_value="",
                property_values={}
            )

    def test_object_instance_missing_ontology_context(self):
        """测试缺少本体上下文"""
        instance = ObjectInstance(
            object_type_api_name="test",
            primary_key_value="test_id",
            property_values={"name": "test"}
            # 没有提供ontology参数
        )

        # 这应该在访问派生属性时失败
        assert instance.ontology is None

    def test_object_instance_invalid_property_access(self):
        """测试无效属性访问"""
        obj_type = ObjectType(api_name="test", display_name="Test")
        obj_type.add_property("name", PropertyType.STRING)

        instance = ObjectInstance(
            object_type_api_name="test",
            primary_key_value="test_id",
            property_values={"name": "test"}
        )

        with pytest.raises(KeyError):
            _ = instance.nonexistent_property

    def test_object_instance_property_type_validation(self):
        """测试属性类型验证"""
        obj_type = ObjectType(api_name="test", display_name="Test")
        obj_type.add_property("age", PropertyType.INTEGER)

        # 类型不匹配的数据
        with pytest.raises(TypeError, match="属性 'age' 的类型不匹配"):
            ObjectInstance(
                object_type_api_name="test",
                primary_key_value="test_id",
                property_values={"age": "invalid_string"}
            )

    def test_object_instance_derived_property_circular_dependency(self):
        """测试派生属性的循环依赖"""
        obj_type = ObjectType(api_name="test", display_name="Test")

        # 创建模拟的本体，返回循环依赖的函数
        mock_ontology = Mock()
        mock_ontology.execute_function.side_effect = ValueError("检测到循环依赖")

        instance = ObjectInstance(
            object_type_api_name="test",
            primary_key_value="test_id",
            property_values={"name": "test"},
            ontology=mock_ontology
        )

        with patch.object(obj_type, 'get_property_spec') as mock_get_spec:
            mock_spec = Mock()
            mock_spec.is_derived = True
            mock_spec.function_api_name = "circular_function"
            mock_get_spec.return_value = mock_spec

            with pytest.raises(ValueError, match="检测到循环依赖"):
                _ = instance.derived_property

    def test_object_instance_equality_comparison(self):
        """测试对象实例相等性比较"""
        instance1 = ObjectInstance(
            object_type_api_name="test",
            primary_key_value="test_id",
            property_values={"name": "test"}
        )

        instance2 = ObjectInstance(
            object_type_api_name="test",
            primary_key_value="test_id",
            property_values={"name": "test"}
        )

        instance3 = ObjectInstance(
            object_type_api_name="test",
            primary_key_value="different_id",
            property_values={"name": "test"}
        )

        assert instance1 == instance2
        assert instance1 != instance3
        assert hash(instance1) == hash(instance2)
        assert hash(instance1) != hash(instance3)

    def test_object_instance_string_representation(self):
        """测试对象实例字符串表示"""
        instance = ObjectInstance(
            object_type_api_name="employee",
            primary_key_value="emp001",
            property_values={"name": "John Doe"}
        )

        str_repr = str(instance)
        assert "emp001" in str_repr
        assert "employee" in str_repr
        assert "John Doe" in str_repr


class TestObjectSetEdgeCases:
    """测试ObjectSet的边缘条件"""

    def test_object_set_empty_filter(self):
        """测试空过滤条件"""
        obj_type = ObjectType(api_name="test", display_name="Test")
        obj_set = ObjectSet(obj_type, [])

        filtered = obj_set.filter("nonexistent", "value")
        assert len(filtered.objects) == 0

    def test_object_set_search_around_invalid_link(self):
        """测试搜索无效链接"""
        obj_type = ObjectType(api_name="test", display_name="Test")
        obj_set = ObjectSet(obj_type, [])

        mock_ontology = Mock()
        mock_ontology.get_link_type.side_effect = KeyError("链接类型不存在")

        with pytest.raises(KeyError, match="链接类型不存在"):
            obj_set.search_around("invalid_link", ontology=mock_ontology)

    def test_object_set_chain_operations(self):
        """测试链式操作"""
        obj_type = ObjectType(api_name="test", display_name="Test")
        obj_type.add_property("category", PropertyType.STRING)
        obj_type.add_property("value", PropertyType.INTEGER)

        objects = [
            ObjectInstance("test", "id1", {"category": "A", "value": 10}),
            ObjectInstance("test", "id2", {"category": "B", "value": 20}),
            ObjectInstance("test", "id3", {"category": "A", "value": 30}),
        ]

        obj_set = ObjectSet(obj_type, objects)

        # 链式过滤
        filtered = obj_set.filter("category", "A").filter("value", 10)
        assert len(filtered.objects) == 1
        assert filtered.objects[0].primary_key_value == "id1"

    def test_object_set_iteration(self):
        """测试对象集合迭代"""
        obj_type = ObjectType(api_name="test", display_name="Test")

        objects = [
            ObjectInstance("test", "id1", {"name": "test1"}),
            ObjectInstance("test", "id2", {"name": "test2"}),
        ]

        obj_set = ObjectSet(obj_type, objects)

        # 测试迭代
        count = 0
        for obj in obj_set:
            count += 1
            assert isinstance(obj, ObjectInstance)

        assert count == 2

    def test_object_set_len_and_bool(self):
        """测试对象集合长度和布尔值"""
        obj_type = ObjectType(api_name="test", display_name="Test")

        empty_set = ObjectSet(obj_type, [])
        non_empty_set = ObjectSet(obj_type, [ObjectInstance("test", "id1", {})])

        assert len(empty_set) == 0
        assert len(non_empty_set) == 1
        assert not empty_set
        assert non_empty_set


class TestOntologyEdgeCases:
    """测试Ontology的边缘条件"""

    def test_ontology_duplicate_registration(self):
        """测试重复注册"""
        ontology = Ontology()
        obj_type = ObjectType(api_name="test", display_name="Test")

        ontology.register_object_type(obj_type)

        with pytest.raises(ValueError, match="对象类型 'test' 已存在"):
            ontology.register_object_type(obj_type)

    def test_ontology_get_nonexistent_type(self):
        """测试获取不存在的类型"""
        ontology = Ontology()

        with pytest.raises(KeyError, match="对象类型 'nonexistent' 不存在"):
            ontology.get_object_type("nonexistent")

    def test_ontology_execute_nonexistent_function(self):
        """测试执行不存在的函数"""
        ontology = Ontology()

        with pytest.raises(KeyError, match="函数 'nonexistent' 不存在"):
            ontology.execute_function("nonexistent")

    def test_ontology_function_execution_with_invalid_args(self):
        """测试函数执行参数验证"""
        ontology = Ontology()

        # 模拟函数注册
        mock_function = Mock()
        mock_function.signature = {"arg1": "string"}
        ontology._functions["test_func"] = mock_function

        with pytest.raises(ValueError, match="参数验证失败"):
            ontology.execute_function("test_func", invalid_arg="value")

    def test_ontology_type_validation_complex_scenarios(self):
        """测试复杂类型验证场景"""
        ontology = Ontology()

        # 创建复杂的对象类型层次结构
        base_type = ObjectType(api_name="base", display_name="Base")
        base_type.add_property("id", PropertyType.STRING, required=True)

        derived_type = ObjectType(api_name="derived", display_name="Derived")
        derived_type.add_property("id", PropertyType.STRING, required=True)
        derived_type.add_property("base_ref", PropertyType.STRING)

        ontology.register_object_type(base_type)
        ontology.register_object_type(derived_type)

        # 测试验证
        valid_data = {"id": "test", "base_ref": "base_id"}
        errors = derived_type.validate_data(valid_data)
        assert len(errors) == 0

    def test_ontology_memory_management(self):
        """测试内存管理"""
        ontology = Ontology()

        # 注册大量类型
        for i in range(100):
            obj_type = ObjectType(
                api_name=f"type_{i}",
                display_name=f"Type {i}"
            )
            obj_type.add_property("id", PropertyType.STRING)
            ontology.register_object_type(obj_type)

        # 验证所有类型都已注册
        assert len(ontology.object_types) == 100

    def test_ontology_concurrent_registration(self):
        """测试并发注册（模拟）"""
        ontology = Ontology()

        # 模拟并发注册（在单线程环境中测试）
        obj_types = []
        for i in range(10):
            obj_type = ObjectType(
                api_name=f"concurrent_type_{i}",
                display_name=f"Concurrent Type {i}"
            )
            obj_types.append(obj_type)

        # 快速连续注册
        for obj_type in obj_types:
            ontology.register_object_type(obj_type)

        # 验证所有类型都已注册
        for i in range(10):
            assert f"concurrent_type_{i}" in ontology.object_types


class TestActionContextEdgeCases:
    """测试ActionContext的边缘条件"""

    def test_action_context_empty_operations(self):
        """测试空操作上下文"""
        ontology = Ontology()
        context = ActionContext(ontology, "user_id")

        # 应用空操作不应该失败
        context.apply_changes()

        assert len(context.operations) == 0

    def test_action_context_invalid_operation_type(self):
        """测试无效操作类型"""
        ontology = Ontology()
        context = ActionContext(ontology, "user_id")

        with pytest.raises(ValueError, match="无效的操作类型"):
            context._add_operation("invalid_operation", {})

    def test_action_context_rollback_no_operations(self):
        """测试无操作时的回滚"""
        ontology = Ontology()
        context = ActionContext(ontology, "user_id")

        # 回滚空操作不应该失败
        context.rollback()

    def test_action_context_multiple_operations(self):
        """测试多个操作"""
        ontology = Ontology()
        context = ActionContext(ontology, "user_id")

        # 创建对象类型
        obj_type = ObjectType(api_name="test", display_name="Test")
        obj_type.add_property("id", PropertyType.STRING)
        obj_type.add_property("name", PropertyType.STRING)
        ontology.register_object_type(obj_type)

        # 添加多个操作
        context.create_object("test", "id1", {"id": "id1", "name": "test1"})
        context.create_object("test", "id2", {"id": "id2", "name": "test2"})
        context.update_object("test", "id1", {"name": "updated_test1"})

        assert len(context.operations) == 3

    def test_action_context_operation_order(self):
        """测试操作顺序"""
        ontology = Ontology()
        context = ActionContext(ontology, "user_id")

        obj_type = ObjectType(api_name="test", display_name="Test")
        obj_type.add_property("id", PropertyType.STRING)
        ontology.register_object_type(obj_type)

        # 添加操作
        context.create_object("test", "id1", {"id": "id1"})
        context.update_object("test", "id1", {"name": "test"})
        context.delete_object("test", "id1")

        # 验证操作顺序
        operations = context.operations
        assert operations[0]["type"] == "create"
        assert operations[1]["type"] == "update"
        assert operations[2]["type"] == "delete"


# 性能测试相关
class TestPerformanceEdgeCases:
    """性能相关边缘情况测试"""

    def test_large_object_set_filtering(self):
        """测试大对象集过滤性能"""
        obj_type = ObjectType(api_name="test", display_name="Test")
        obj_type.add_property("category", PropertyType.STRING)

        # 创建大量对象
        objects = []
        for i in range(1000):
            objects.append(ObjectInstance(
                "test", f"id_{i}", {"category": f"cat_{i % 10}"}
            ))

        obj_set = ObjectSet(obj_type, objects)

        # 测试过滤性能
        filtered = obj_set.filter("category", "cat_5")
        assert len(filtered.objects) == 100

    @pytest.mark.slow
    def test_memory_usage_with_large_ontology(self):
        """测试大本体的内存使用"""
        import psutil
        import os

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss

        ontology = Ontology()

        # 注册大量类型
        for i in range(100):
            obj_type = ObjectType(api_name=f"type_{i}", display_name=f"Type {i}")
            for j in range(10):
                obj_type.add_property(f"prop_{j}", PropertyType.STRING)
            ontology.register_object_type(obj_type)

        final_memory = process.memory_info().rss
        memory_increase = (final_memory - initial_memory) / 1024 / 1024  # MB

        # 内存增长应该在合理范围内
        assert memory_increase < 50  # 小于50MB


# 测试工具函数
def create_test_data(size: int = 100) -> Dict[str, Any]:
    """创建测试数据的辅助函数"""
    return {
        "objects": [
            {"id": f"id_{i}", "name": f"Name {i}", "value": i}
            for i in range(size)
        ]
    }


def mock_ontology_with_types():
    """创建包含模拟类型的本体"""
    ontology = Ontology()

    # 添加模拟对象类型
    obj_type = ObjectType(api_name="mock_type", display_name="Mock Type")
    obj_type.add_property("id", PropertyType.STRING)
    obj_type.add_property("name", PropertyType.STRING)
    ontology.register_object_type(obj_type)

    return ontology


if __name__ == "__main__":
    pytest.main([__file__])