# 本体框架核心模块更正测试
# 基于实际API创建的准确测试用例

import pytest
import time
from datetime import datetime, timezone
from typing import Any, Dict, List

from src.ontology_framework.core import (
    PropertyType, PropertyDefinition, DerivedPropertyDefinition,
    ObjectType, LinkType, ActionType, ActionParameter,
    ObjectInstance, ObjectSet, Ontology,
    PrimitiveType, ObjectTypeSpec, ObjectSetTypeSpec
)
from src.ontology_framework.permissions import AccessControlList, Principal, PermissionType


class TestObjectTypeCorrected:
    """ObjectType类正确API测试"""

    def test_object_type_creation_with_dict_properties(self):
        """测试使用字典属性的ObjectType创建"""
        properties = {
            "id": PropertyDefinition("id", PropertyType.STRING, "Primary ID"),
            "name": PropertyDefinition("name", PropertyType.STRING, "Display name"),
            "email": PropertyDefinition("email", PropertyType.STRING, "Email address")
        }

        obj_type = ObjectType(
            api_name="user",
            display_name="用户",
            properties=properties,
            primary_key="id"
        )

        assert obj_type.api_name == "user"
        assert obj_type.display_name == "用户"
        assert len(obj_type.properties) == 3
        assert obj_type.properties["name"].type == PropertyType.STRING
        assert obj_type.primary_key == "id"

    def test_object_type_add_property_method(self):
        """测试add_property方法"""
        obj_type = ObjectType(
            api_name="product",
            display_name="产品",
            primary_key="product_id"
        )

        # 使用链式调用添加属性
        obj_type.add_property("product_id", PropertyType.STRING, "Product ID")
        obj_type.add_property("name", PropertyType.STRING, "Product name")
        obj_type.add_property("price", PropertyType.INTEGER, "Price in cents")

        assert len(obj_type.properties) == 3
        assert obj_type.properties["price"].type == PropertyType.INTEGER
        assert obj_type.properties["price"].description == "Price in cents"

    def test_object_type_add_derived_property(self):
        """测试添加派生属性"""
        obj_type = ObjectType(
            api_name="order",
            display_name="订单",
            primary_key="order_id"
        )

        obj_type.add_derived_property(
            "total",
            PropertyType.INTEGER,
            "calculate_order_total",
            "订单总金额"
        )

        assert len(obj_type.derived_properties) == 1
        derived_prop = obj_type.derived_properties["total"]
        assert derived_prop.name == "total"
        assert derived_prop.type == PropertyType.INTEGER
        assert derived_prop.backing_function_api_name == "calculate_order_total"

    def test_object_type_with_permissions(self):
        """测试带权限的ObjectType"""
        acl = AccessControlList()
        acl.grant("admin", PermissionType.VIEW)
        acl.grant("admin", PermissionType.EDIT)

        obj_type = ObjectType(
            api_name="secret_data",
            display_name="机密数据",
            properties={},
            permissions=acl
        )

        assert obj_type.permissions is not None
        assert obj_type.permissions.check("admin", PermissionType.EDIT)  # 使用check方法


class TestActionTypeCorrected:
    """ActionType类正确API测试"""

    def test_action_type_creation(self):
        """测试ActionType创建"""
        action = ActionType(
            api_name="create_user",
            display_name="创建用户",
            target_object_types=["user"]
        )

        assert action.api_name == "create_user"
        assert action.display_name == "创建用户"
        assert "user" in action.target_object_types

    def test_action_parameter_data_type_attribute(self):
        """测试ActionParameter的data_type属性"""
        param = ActionParameter(
            api_name="username",
            data_type=PropertyType.STRING,
            required=True,
            description="用户名"
        )

        assert param.api_name == "username"
        assert param.data_type == PropertyType.STRING  # 注意是data_type不是type
        assert param.required is True

    def test_action_type_add_parameter(self):
        """测试ActionType添加参数"""
        action = ActionType(
            api_name="update_product",
            display_name="更新产品",
            target_object_types=["product"]
        )

        action.add_parameter("product_id", PropertyType.STRING, True, "产品ID")
        action.add_parameter("name", PropertyType.STRING, False, "产品名称")
        action.add_parameter("price", PropertyType.INTEGER, False, "价格")

        assert len(action.parameters) == 3
        assert action.parameters["price"].data_type == PropertyType.INTEGER
        assert action.parameters["name"].required is False


class TestObjectInstanceCorrected:
    """ObjectInstance类正确API测试"""

    def test_object_instance_creation(self):
        """测试ObjectInstance创建"""
        obj = ObjectInstance(
            object_type_api_name="user",
            primary_key_value="user123",
            property_values={
                "id": "user123",
                "name": "张三",
                "email": "zhangsan@example.com"
            }
        )

        assert obj.object_type_api_name == "user"
        assert obj.primary_key_value == "user123"
        assert obj.property_values["name"] == "张三"

    def test_object_instance_get_method(self):
        """测试ObjectInstance.get方法"""
        ontology = Ontology()

        # 注册对象类型
        user_type = ObjectType(
            api_name="user",
            display_name="用户",
            properties={
                "id": PropertyDefinition("id", PropertyType.STRING),
                "name": PropertyDefinition("name", PropertyType.STRING),
                "status": PropertyDefinition("status", PropertyType.STRING)
            },
            primary_key="id"
        )
        ontology.register_object_type(user_type)

        # 创建对象实例
        obj = ObjectInstance(
            object_type_api_name="user",
            primary_key_value="user123",
            property_values={
                "id": "user123",
                "name": "李四",
                "status": "active"
            },
            _ontology=ontology
        )

        # 测试get方法
        assert obj.get("id") == "user123"
        assert obj.get("name") == "李四"
        assert obj.get("status") == "active"
        assert obj.get("nonexistent") is None


class TestObjectSetCorrected:
    """ObjectSet类正确API测试"""

    def test_object_set_creation(self):
        """测试ObjectSet创建"""
        user_type = ObjectType(
            api_name="user",
            display_name="用户",
            primary_key="id"
        )

        objects = [
            ObjectInstance("user", "1", {"name": "张三"}),
            ObjectInstance("user", "2", {"name": "李四"})
        ]

        obj_set = ObjectSet(user_type, objects)

        assert obj_set.object_type.api_name == "user"
        assert len(obj_set.all()) == 2
        assert obj_set.all()[0].primary_key_value == "1"

    def test_object_set_filter_two_params(self):
        """测试ObjectSet.filter方法（只有2个参数）"""
        user_type = ObjectType(
            api_name="user",
            display_name="用户",
            primary_key="id"
        )

        objects = [
            ObjectInstance("user", "1", {"name": "张三", "dept": "工程"}),
            ObjectInstance("user", "2", {"name": "李四", "dept": "销售"}),
            ObjectInstance("user", "3", {"name": "王五", "dept": "工程"})
        ]

        obj_set = ObjectSet(user_type, objects)

        # filter方法只接受property_name和value两个参数
        engineers = obj_set.filter("dept", "工程")
        assert len(engineers.all()) == 2
        assert all(obj.property_values.get("dept") == "工程" for obj in engineers.all())

    def test_object_set_aggregation(self):
        """测试ObjectSet聚合功能"""
        product_type = ObjectType(
            api_name="product",
            display_name="产品",
            primary_key="id"
        )

        objects = [
            ObjectInstance("product", "1", {"name": "产品A", "price": 100}),
            ObjectInstance("product", "2", {"name": "产品B", "price": 200}),
            ObjectInstance("product", "3", {"name": "产品C", "price": 300})
        ]

        obj_set = ObjectSet(product_type, objects)

        # 测试聚合函数
        assert obj_set.aggregate("price", "sum") == 600
        assert obj_set.aggregate("price", "avg") == 200
        assert obj_set.aggregate("price", "max") == 300
        assert obj_set.aggregate("price", "min") == 100
        assert obj_set.aggregate("price", "count") == 3


class TestOntologyCorrected:
    """Ontology类正确API测试"""

    def test_ontology_type_registration(self):
        """测试本体类型注册"""
        ontology = Ontology()

        # 注册对象类型
        user_type = ObjectType(
            api_name="user",
            display_name="用户",
            properties={
                "id": PropertyDefinition("id", PropertyType.STRING)
            },
            primary_key="id"
        )
        ontology.register_object_type(user_type)

        # 注册链接类型
        friendship_type = LinkType(
            api_name="friendship",
            display_name="友谊关系",
            source_object_type="user",
            target_object_type="user"
        )
        ontology.register_link_type(friendship_type)

        # 注册操作类型
        greet_action = ActionType(
            api_name="greet",
            display_name="问候",
            target_object_types=["user"]
        )
        ontology.register_action_type(greet_action)

        # 验证注册成功
        retrieved_user = ontology.get_object_type("user")
        assert retrieved_user is not None
        assert retrieved_user.display_name == "用户"

        retrieved_link = ontology.get_link_type("friendship")
        assert retrieved_link is not None
        assert retrieved_link.display_name == "友谊关系"

        retrieved_action = ontology.get_action_type("greet")
        assert retrieved_action is not None
        assert retrieved_action.display_name == "问候"

    def test_ontology_object_management(self):
        """测试本体对象管理"""
        ontology = Ontology()

        # 注册对象类型
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

        # 添加对象
        user1 = ObjectInstance("user", "1", {"id": "1", "name": "张三"})
        user2 = ObjectInstance("user", "2", {"id": "2", "name": "李四"})

        ontology.add_object(user1)
        ontology.add_object(user2)

        # 获取对象
        retrieved_user = ontology.get_object("user", "1")
        assert retrieved_user is not None
        assert retrieved_user.property_values["name"] == "张三"

        # 获取对象集合 - get_objects_of_type返回List[ObjectInstance]，不是ObjectSet
        users = ontology.get_objects_of_type("user")
        assert len(users) == 2  # 直接使用len()，不需要.all()


class TestParameterizedCorrected:
    """参数化测试"""

    @pytest.mark.parametrize("api_name,display_name,primary_key", [
        ("user", "用户", "user_id"),
        ("product", "产品", "product_id"),
        ("order", "订单", "order_id")
    ])
    def test_object_type_variations(self, api_name, display_name, primary_key):
        """测试不同类型的ObjectType创建"""
        obj_type = ObjectType(
            api_name=api_name,
            display_name=display_name,
            properties={
                primary_key: PropertyDefinition(primary_key, PropertyType.STRING)
            },
            primary_key=primary_key
        )

        assert obj_type.api_name == api_name
        assert obj_type.display_name == display_name
        assert obj_type.primary_key == primary_key
        assert primary_key in obj_type.properties

    @pytest.mark.parametrize("property_type,value", [
        (PropertyType.STRING, "test_string"),
        (PropertyType.INTEGER, 42),
        (PropertyType.BOOLEAN, True)
    ])
    def test_property_definition_types(self, property_type, value):
        """测试不同属性类型定义"""
        prop_def = PropertyDefinition("test_prop", property_type, "Test property")

        assert prop_def.name == "test_prop"
        assert prop_def.type == property_type
        assert prop_def.description == "Test property"


class TestErrorHandlingCorrected:
    """错误处理测试"""

    def test_object_type_not_found(self):
        """测试对象类型不存在的错误"""
        ontology = Ontology()

        # get_object_type返回None而不是抛出KeyError
        result = ontology.get_object_type("nonexistent_type")
        assert result is None

    def test_link_type_not_found(self):
        """测试链接类型不存在的错误"""
        ontology = Ontology()

        # get_link_type返回None而不是抛出KeyError
        result = ontology.get_link_type("nonexistent_link")
        assert result is None

    def test_action_type_not_found(self):
        """测试操作类型不存在的错误"""
        ontology = Ontology()

        # get_action_type返回None而不是抛出KeyError
        result = ontology.get_action_type("nonexistent_action")
        assert result is None

    def test_object_set_filter_type_mismatch(self):
        """测试对象集合类型不匹配错误"""
        user_type = ObjectType("user", "用户", primary_key="id")
        product_type = ObjectType("product", "产品", primary_key="id")

        product_obj = ObjectInstance("product", "1", {"name": "产品A"})
        obj_set = ObjectSet(user_type, [])

        with pytest.raises(ValueError, match="Object type mismatch"):
            obj_set.add(product_obj)


class TestSimpleIntegrationCorrected:
    """简单集成测试"""

    def test_complete_workflow_simple(self):
        """测试完整工作流程（简化版）"""
        ontology = Ontology()

        # 1. 定义和注册对象类型
        user_type = ObjectType(
            api_name="user",
            display_name="用户",
            properties={
                "id": PropertyDefinition("id", PropertyType.STRING),
                "name": PropertyDefinition("name", PropertyType.STRING),
                "department": PropertyDefinition("department", PropertyType.STRING)
            },
            primary_key="id"
        )
        ontology.register_object_type(user_type)

        # 2. 创建用户对象
        users = [
            ObjectInstance("user", "1", {"id": "1", "name": "张三", "department": "工程"}),
            ObjectInstance("user", "2", {"id": "2", "name": "李四", "department": "销售"}),
            ObjectInstance("user", "3", {"id": "3", "name": "王五", "department": "工程"})
        ]

        for user in users:
            ontology.add_object(user)

        # 3. 查询 - get_objects_of_type返回List，不是ObjectSet
        all_users_list = ontology.get_objects_of_type("user")
        assert len(all_users_list) == 3

        # 4. 创建ObjectSet进行过滤
        user_set = ObjectSet(user_type, all_users_list)
        engineers_set = user_set.filter("department", "工程")
        assert len(engineers_set.all()) == 2

        # 5. 聚合查询
        user_count = engineers_set.aggregate("id", "count")
        assert user_count == 2  # engineers_set 有2个对象

        # 6. 验证具体对象
        retrieved_user = ontology.get_object("user", "1")
        assert retrieved_user.property_values["name"] == "张三"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])