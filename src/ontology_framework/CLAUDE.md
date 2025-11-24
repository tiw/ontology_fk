[根目录](../../../CLAUDE.md) > [src](../../) > [ontology_framework](../) > **核心框架**

# Ontology Framework - 核心模块

## 模块职责

本模块是整个本体框架的核心，提供了定义和管理语义本体的基础组件。包括对象类型、链接类型、操作类型的定义，以及对象的实例化和查询功能。

## 架构概览

### 核心类层次结构

```
Ontology
├── ObjectType (注册的对象类型)
├── LinkType (注册的链接类型)
├── ActionType (注册的操作类型)
├── Function (注册的函数)
└── ObjectInstance (运行时对象实例)
```

## 关键组件

### 1. Ontology 类
**作用**: 本体的中央管理器，负责注册和管理所有类型定义。

**主要方法**:
- `register_object_type(object_type)`: 注册对象类型
- `register_link_type(link_type)`: 注册链接类型
- `register_action_type(action_type)`: 注册操作类型
- `register_function(function)`: 注册函数
- `execute_function(api_name, **kwargs)`: 执行已注册的函数
- `get_object_type(api_name)`: 获取对象类型定义
- `get_link_type(api_name)`: 获取链接类型定义
- `get_action_type(api_name)`: 获取操作类型定义

### 2. ObjectType 类
**作用**: 定义业务实体（如员工、订单、产品）的 schema。

**关键特性**:
- 支持基础属性（STRING, INTEGER, BOOLEAN, DATE, TIMESTAMP）
- 支持派生属性（由函数支持的动态计算属性）
- 集成权限控制（ACL）
- 支持数据源绑定和 UI 配置

**示例**:
```python
employee = ObjectType(
    api_name="employee",
    display_name="Employee",
    primary_key="id",
    title_property="name",
    icon="user",
    backing_datasource_id="ri.foundry.main.dataset.1234"
)
employee.add_property("name", PropertyType.STRING)
employee.add_property("salary", PropertyType.INTEGER)
```

### 3. LinkType 类
**作用**: 定义对象间的关系类型。

**核心属性**:
- `source_object_type`: 源对象类型
- `target_object_type`: 目标对象类型
- 支持方向性关系定义

### 4. ActionType 类
**作用**: 定义事务操作，可与函数关联以实现自动化业务逻辑。

**特性**:
- 支持目标对象类型限制
- 可绑定到具体函数实现
- 提供操作级别的权限控制

### 5. ObjectInstance 类
**作用**: 对象的运行时实例，支持动态属性访问。

**关键功能**:
- 自动处理派生属性计算
- 支持延迟计算
- 集成本体上下文进行函数调用

### 6. ObjectSet 类
**作用**: 对象集合，提供查询和导航功能。

**查询方法**:
- `filter(property_name, value)`: 属性过滤
- `search_around(link_type, **filters)`: 基于关系的导航查询
- 支持链式查询

## 类型系统

### PropertyType 枚举
```python
class PropertyType(Enum):
    STRING = "string"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    DATE = "date"
    TIMESTAMP = "timestamp"
```

### TypeSpec 层次结构
- `PrimitiveType`: 基础数据类型
- `ObjectTypeSpec`: 对象类型规范
- `ObjectSetTypeSpec`: 对象集合类型规范

## 设计模式

### 1. 注册表模式
Ontology 类使用注册表模式管理类型定义，确保类型名称的唯一性和一致性。

### 2. 策略模式
派生属性使用策略模式，通过函数动态计算属性值。

### 3. 代理模式
ObjectInstance 作为对象的代理，透明地处理属性访问和派生属性计算。

### 4. 建造者模式
ObjectType 提供 `add_property()` 和 `add_derived_property()` 方法，支持链式调用。

## 使用示例

### 基础对象定义
```python
from ontology_framework.core import Ontology, ObjectType, PropertyType

ontology = Ontology()

# 定义对象类型
employee = ObjectType(
    api_name="employee",
    display_name="Employee",
    primary_key="employee_id"
)
employee.add_property("employee_id", PropertyType.STRING)
employee.add_property("name", PropertyType.STRING)
employee.add_property("department", PropertyType.STRING)

# 注册到本体
ontology.register_object_type(employee)
```

### 创建对象实例
```python
# 创建员工实例
emp = ObjectInstance(
    object_type_api_name="employee",
    primary_key_value="EMP001",
    property_values={
        "employee_id": "EMP001",
        "name": "John Doe",
        "department": "Engineering"
    }
)
```

### 查询和导航
```python
# 获取对象集合
employees = ontology.get_objects_of_type("employee")

# 过滤查询
engineers = employees.filter("department", "Engineering")

# 关系导航（如果有定义工作关系链接）
projects = engineers.search_around("works_on", status="active")
```

## 扩展性

### 自定义属性类型
可以通过扩展 PropertyType 枚举来支持自定义数据类型。

### 派生属性
通过绑定函数实现复杂的业务逻辑计算，支持：
- 基于其他属性的计算
- 跨表查询
- 实时数据获取

### 集成点
- **数据源**: 支持外部数据源绑定
- **权限**: 集成 ACL 权限系统
- **函数**: 与函数系统深度集成
- **应用层**: 支持视图和分析组件

## 性能考虑

### 内存优化
- 使用 dataclass 减少内存占用
- 延迟计算派生属性
- 对象集合支持迭代器模式

### 查询优化
- 支持属性索引（通过 ObjectSetService）
- 链式查询减少中间结果
- 查询结果缓存

## 错误处理

### 异常类型
- `ValueError`: 类型验证错误
- `KeyError`: 属性不存在
- `TypeError`: 类型不匹配
- `PermissionError`: 权限不足

### 最佳实践
- 总是在注册前验证类型定义
- 使用类型注解提高代码安全性
- 实现自定义异常处理逻辑

## 测试策略

### 单元测试重点
- 类型注册和检索
- 属性访问和设置
- 查询和过滤逻辑
- 派生属性计算

### 集成测试场景
- 复杂查询链
- 跨模块功能
- 权限控制集成

## 相关文件清单

- `__init__.py`: 模块导出定义
- `core.py`: 核心组件实现
- `functions.py`: 函数系统集成
- `permissions.py`: 权限管理
- `services.py`: 服务层实现
- `applications.py`: 应用层组件

## 变更记录 (Changelog)

- **2025-11-24**: 初始模块文档完成
  - 完成核心组件分析
  - 记录使用示例和最佳实践
  - 识别扩展点和集成方式