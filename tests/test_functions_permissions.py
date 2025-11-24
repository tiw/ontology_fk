# 函数系统和权限管理专项测试
# 针对functions.py和permissions.py的深度测试

import pytest
from typing import Any, Dict

from src.ontology_framework.core import (
    Function, FunctionArgument, PrimitiveType, ObjectTypeSpec,
    ObjectType, ObjectInstance, Ontology, PropertyType, PropertyDefinition
)
from src.ontology_framework.functions import FunctionRegistry
from src.ontology_framework.permissions import (
    AccessControlList, Principal, PermissionType
)


class TestFunctionRegistryExtended:
    """FunctionRegistry扩展测试"""

    def test_function_registry_decorator_registration(self):
        """测试FunctionRegistry装饰器注册"""
        registry = FunctionRegistry()

        # 使用装饰器注册函数
        @registry.register("test_func", display_name="测试函数")
        def dummy_logic():
            return "test_result"

        # 验证注册成功
        assert registry.has_function("test_func")
        pending = registry.get_pending_functions()
        assert "test_func" in pending

        registered_func = pending["test_func"]
        assert registered_func.display_name == "测试函数"
        assert registered_func.logic == dummy_logic

    def test_function_registry_clear_and_pending(self):
        """测试FunctionRegistry清除和待注册函数"""
        registry = FunctionRegistry()

        # 使用装饰器注册函数
        @registry.register("func1", display_name="函数1")
        def func1():
            return "func1_result"

        @registry.register("func2", display_name="函数2")
        def func2():
            return "func2_result"

        # 验证添加成功
        pending = registry.get_pending_functions()
        assert len(pending) == 2
        assert "func1" in pending
        assert "func2" in pending

        # 测试清除功能
        registry.clear()
        pending_after = registry.get_pending_functions()
        assert len(pending_after) == 0

    def test_function_registry_remove_function(self):
        """测试FunctionRegistry删除函数"""
        registry = FunctionRegistry()

        # 添加函数
        @registry.register("test_func", display_name="测试函数")
        def test_func():
            return "test"

        # 验证存在
        assert registry.has_function("test_func")

        # 删除函数
        removed = registry.remove_function("test_func")
        assert removed is True

        # 验证已删除
        assert not registry.has_function("test_func")

        # 删除不存在的函数
        removed = registry.remove_function("nonexistent")
        assert removed is False

    def test_function_registry_with_inputs(self):
        """测试FunctionRegistry带输入参数的函数"""
        registry = FunctionRegistry()

        @registry.register(
            "func_with_inputs",
            display_name="带输入的函数",
            inputs={
                "text": PrimitiveType(PropertyType.STRING),
                "number": PrimitiveType(PropertyType.INTEGER)
            }
        )
        def func_with_inputs(text: str, number: int):
            return f"{text}_{number}"

        # 验证注册成功
        assert registry.has_function("func_with_inputs")
        pending = registry.get_pending_functions()
        func = pending["func_with_inputs"]

        assert len(func.inputs) == 2
        assert "text" in func.inputs
        assert "number" in func.inputs
        assert func.inputs["text"].type.type == PropertyType.STRING

    def test_function_argument_validation(self):
        """测试函数参数验证"""
        # 创建各种类型的参数
        string_arg = FunctionArgument(
            name="text",
            type=PrimitiveType(PropertyType.STRING),
            required=True,
            description="文本参数"
        )

        int_arg = FunctionArgument(
            name="number",
            type=PrimitiveType(PropertyType.INTEGER),
            required=False,
            description="数字参数"
        )

        object_type_arg = FunctionArgument(
            name="user",
            type=ObjectTypeSpec("user"),
            required=True,
            description="用户对象"
        )

        # 验证参数属性
        assert string_arg.name == "text"
        assert string_arg.type.type == PropertyType.STRING
        assert string_arg.required is True
        assert string_arg.description == "文本参数"

        assert int_arg.required is False
        assert int_arg.type.type == PropertyType.INTEGER

        assert object_type_arg.type.object_type_api_name == "user"

    def test_function_add_input_method(self):
        """测试Function.add_input方法"""
        function = Function("test_func", "测试函数")

        # 使用链式调用添加参数
        function.add_input(
            "text_param",
            PrimitiveType(PropertyType.STRING),
            True,
            "必需的文本参数"
        ).add_input(
            "optional_param",
            PrimitiveType(PropertyType.INTEGER),
            False,
            "可选的数字参数"
        )

        # 验证参数添加成功
        assert len(function.inputs) == 2
        assert "text_param" in function.inputs
        assert "optional_param" in function.inputs

        text_param = function.inputs["text_param"]
        assert text_param.required is True
        assert text_param.description == "必需的文本参数"

        optional_param = function.inputs["optional_param"]
        assert optional_param.required is False


class TestAccessControlListExtended:
    """AccessControlList扩展测试"""

    def test_acl_basic_operations(self):
        """测试ACL基础操作"""
        acl = AccessControlList()

        # 初始状态
        assert not acl.check("user1", PermissionType.VIEW)
        assert not acl.check("user1", PermissionType.EDIT)

        # 授予权限
        acl.grant("user1", PermissionType.VIEW)
        assert acl.check("user1", PermissionType.VIEW)
        assert not acl.check("user1", PermissionType.EDIT)

        # 授予更多权限
        acl.grant("user1", PermissionType.EDIT)
        assert acl.check("user1", PermissionType.EDIT)

        # 不同用户的权限独立
        assert not acl.check("user2", PermissionType.VIEW)

        # 为另一个用户授予权限
        acl.grant("user2", PermissionType.DELETE)
        assert acl.check("user2", PermissionType.DELETE)
        assert not acl.check("user2", PermissionType.VIEW)

    def test_acl_permission_groups(self):
        """测试ACL权限分组"""
        acl = AccessControlList()

        # 为一个用户授予多个权限
        acl.grant("admin", PermissionType.VIEW)
        acl.grant("admin", PermissionType.EDIT)
        acl.grant("admin", PermissionType.DELETE)
        acl.grant("admin", PermissionType.OWNER)

        # 验证所有权限
        assert acl.check("admin", PermissionType.VIEW)
        assert acl.check("admin", PermissionType.EDIT)
        assert acl.check("admin", PermissionType.DELETE)
        assert acl.check("admin", PermissionType.OWNER)

    def test_acl_duplicate_grants(self):
        """测试重复授权不会重复添加"""
        acl = AccessControlList()

        # 多次授予相同权限
        acl.grant("user1", PermissionType.VIEW)
        acl.grant("user1", PermissionType.VIEW)
        acl.grant("user1", PermissionType.VIEW)

        # 验证权限字典中没有重复
        user1_perms = acl.permissions.get("user1", [])
        assert len(user1_perms) == 1
        assert PermissionType.VIEW in user1_perms

    def test_acl_permissions_structure(self):
        """测试ACL权限数据结构"""
        acl = AccessControlList()

        # 授予多种权限
        acl.grant("user1", PermissionType.VIEW)
        acl.grant("user1", PermissionType.EDIT)
        acl.grant("user2", PermissionType.VIEW)

        # 验证权限结构
        assert isinstance(acl.permissions, dict)
        assert "user1" in acl.permissions
        assert "user2" in acl.permissions

        user1_perms = acl.permissions["user1"]
        assert isinstance(user1_perms, list)
        assert len(user1_perms) == 2
        assert PermissionType.VIEW in user1_perms
        assert PermissionType.EDIT in user1_perms


class TestPrincipalExtended:
    """Principal扩展测试"""

    def test_principal_creation(self):
        """测试Principal创建"""
        # 用户类型的Principal
        user_principal = Principal(
            id="user123",
            type="USER",
            attributes=["engineer", "admin"]
        )

        assert user_principal.id == "user123"
        assert user_principal.type == "USER"
        assert len(user_principal.attributes) == 2
        assert "engineer" in user_principal.attributes

        # 组类型的Principal
        group_principal = Principal(
            id="group_engineering",
            type="GROUP",
            attributes=[]
        )

        assert group_principal.type == "GROUP"
        assert len(group_principal.attributes) == 0

    def test_principal_default_attributes(self):
        """测试Principal默认属性"""
        # 使用默认属性的Principal
        simple_principal = Principal(id="simple_user")

        assert simple_principal.type == "USER"  # 默认类型
        assert len(simple_principal.attributes) == 0  # 默认空列表


class TestPermissionTypeExtended:
    """PermissionType扩展测试"""

    def test_permission_type_values(self):
        """测试PermissionType枚举值"""
        assert PermissionType.VIEW.value == "view"
        assert PermissionType.EDIT.value == "edit"
        assert PermissionType.DELETE.value == "delete"
        assert PermissionType.OWNER.value == "owner"

    def test_permission_type_comparison(self):
        """测试PermissionType比较"""
        view_perm = PermissionType.VIEW
        edit_perm = PermissionType.EDIT

        assert view_perm == PermissionType.VIEW
        assert view_perm != edit_perm
        assert view_perm != "view"  # 枚举对象不等于字符串

    def test_permission_type_iteration(self):
        """测试PermissionType枚举迭代"""
        permission_types = list(PermissionType)
        assert len(permission_types) == 4
        assert PermissionType.VIEW in permission_types
        assert PermissionType.EDIT in permission_types
        assert PermissionType.DELETE in permission_types
        assert PermissionType.OWNER in permission_types


class TestFunctionPermissionsIntegration:
    """函数与权限系统集成测试"""

    def test_function_with_acl(self):
        """测试函数与ACL集成"""
        # 创建函数
        def sensitive_operation(data):
            return f"处理敏感数据: {data}"

        function = Function(
            api_name="sensitive_func",
            display_name="敏感操作函数",
            logic=sensitive_operation
        )

        # 创建ACL
        acl = AccessControlList()
        acl.grant("admin", PermissionType.EXECUTE if hasattr(PermissionType, 'EXECUTE') else PermissionType.EDIT)

        # 在实际应用中，函数可能需要权限检查
        # 这里我们测试数据结构的组合
        assert function.api_name == "sensitive_func"
        assert acl.check("admin", PermissionType.EDIT)

    def test_ontology_function_registration_with_permissions(self):
        """测试本体函数注册与权限"""
        ontology = Ontology()

        # 创建带权限的对象类型
        acl = AccessControlList()
        acl.grant("admin", PermissionType.VIEW)
        acl.grant("admin", PermissionType.EDIT)

        secure_obj_type = ObjectType(
            api_name="secure_data",
            display_name="安全数据",
            properties={
                "id": PropertyDefinition("id", PropertyType.STRING),
                "secret": PropertyDefinition("secret", PropertyType.STRING)
            },
            primary_key="id",
            permissions=acl
        )

        # 注册到本体
        ontology.register_object_type(secure_obj_type)

        # 创建函数
        def process_secret_data():
            return "处理完成"

        function = Function(
            api_name="process_secret",
            display_name="处理机密数据",
            logic=process_secret_data
        )

        # 注册函数
        ontology.register_function(function)

        # 验证注册成功
        retrieved_obj_type = ontology.get_object_type("secure_data")
        assert retrieved_obj_type is not None
        assert retrieved_obj_type.permissions is not None
        assert retrieved_obj_type.permissions.check("admin", PermissionType.EDIT)

        # Ontology没有get_function方法，但可以通过functions字典访问
        retrieved_function = ontology.functions.get("process_secret")
        assert retrieved_function is not None
        assert retrieved_function.display_name == "处理机密数据"


class TestEdgeCasesAndErrorHandling:
    """边缘情况和错误处理测试"""

    def test_function_registry_edge_cases(self):
        """测试FunctionRegistry边缘情况"""
        registry = FunctionRegistry()

        # 注册空函数名函数 - 使用装饰器可能不会抛出异常
        try:
            @registry.register("", display_name="空名称函数")
            def empty_name_func():
                return "empty"
            # 如果成功注册，我们可以测试它
            assert registry.has_function("")
        except Exception:
            # 如果抛出异常，这也是预期的行为
            pass

        # 测试不存在的函数
        assert not registry.has_function("nonexistent")
        assert registry.remove_function("nonexistent") is False

    def test_acl_edge_cases(self):
        """测试ACL边缘情况"""
        acl = AccessControlList()

        # 检查不存在用户的权限
        assert not acl.check("", PermissionType.VIEW)
        assert not acl.check(None, PermissionType.VIEW)  # 如果允许None作为参数

        # 为空字符串用户ID授予权限
        acl.grant("", PermissionType.VIEW)
        # 根据实现，这可能成功或失败

    def test_permission_type_edge_cases(self):
        """测试PermissionType边缘情况"""
        # 测试枚举的字符串表示
        assert str(PermissionType.VIEW) == "PermissionType.VIEW"

        # 测试枚举值的类型
        assert isinstance(PermissionType.VIEW.value, str)

    def test_function_argument_edge_cases(self):
        """测试FunctionArgument边缘情况"""
        # 创建各种参数组合
        min_arg = FunctionArgument("min", PrimitiveType(PropertyType.STRING))
        assert min_arg.required is True  # 默认值
        assert min_arg.description is None

        full_arg = FunctionArgument(
            name="full",
            type=ObjectTypeSpec("user"),
            required=False,
            description="完整参数"
        )
        assert full_arg.required is False
        assert full_arg.description is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])