# Ontology Framework 用户指南

## 概述

本指南将帮助您快速上手 Ontology Framework，从基础概念到高级功能，逐步掌握这个强大的语义本体管理平台。

## 目录

1. [快速开始](#快速开始)
2. [核心概念](#核心概念)
3. [基础教程](#基础教程)
4. [高级功能](#高级功能)
5. [最佳实践](#最佳实践)
6. [故障排除](#故障排除)
7. [API参考](#api参考)

## 快速开始

### 安装

```bash
# 使用pip安装
pip install ontology-framework

# 或从源码安装
git clone https://github.com/your-org/ontology-framework.git
cd ontology-framework
pip install -e .
```

### 第一个示例

```python
from ontology_framework import Ontology, ObjectType, PropertyType

# 1. 创建本体
ontology = Ontology()

# 2. 定义员工对象类型
employee = ObjectType(
    api_name="employee",
    display_name="Employee",
    primary_key="employee_id"
)
employee.add_property("employee_id", PropertyType.STRING)
employee.add_property("name", PropertyType.STRING)
employee.add_property("department", PropertyType.STRING)
employee.add_property("salary", PropertyType.INTEGER)

# 3. 注册对象类型
ontology.register_object_type(employee)

# 4. 创建员工实例
emp = ObjectInstance(
    object_type_api_name="employee",
    primary_key_value="EMP001",
    property_values={
        "employee_id": "EMP001",
        "name": "张三",
        "department": "技术部",
        "salary": 50000
    }
)

# 5. 添加到本体
ontology.add_object(emp)

# 6. 获取所有员工
employees = ontology.get_objects_of_type("employee")
print(f"总员工数: {len(employees.all())}")
```

## 核心概念

### 1. 本体 (Ontology)
本体是整个框架的核心，负责管理所有类型定义和对象实例。

```python
from ontology_framework import Ontology

ontology = Ontology()
```

### 2. 对象类型 (ObjectType)
对象类型定义了实体的结构和属性。

```python
from ontology_framework import ObjectType, PropertyType

product = ObjectType(
    api_name="product",
    display_name="Product",
    primary_key="product_id"
)
```

### 3. 属性类型 (PropertyType)
支持的数据类型枚举：

- `STRING`: 字符串
- `INTEGER`: 整数
- `BOOLEAN`: 布尔值
- `DATE`: 日期
- `TIMESTAMP`: 时间戳

### 4. 对象实例 (ObjectInstance)
对象实例是对象类型的具体实现。

```python
from ontology_framework import ObjectInstance

product_instance = ObjectInstance(
    object_type_api_name="product",
    primary_key_value="PROD001",
    property_values={
        "product_id": "PROD001",
        "name": "Laptop",
        "price": 999.99
    }
)
```

### 5. 对象集合 (ObjectSet)
对象集合提供了查询、过滤和聚合功能。

```python
from ontology_framework import ObjectSet

products = ObjectSet(product_type, [product_instance])
filtered = products.filter("category", "Electronics")
count = products.aggregate("price", "sum")
```

## 基础教程

### 教程1: 定义复杂对象类型

```python
from ontology_framework import Ontology, ObjectType, PropertyType

ontology = Ontology()

# 定义客户对象类型
customer = ObjectType(
    api_name="customer",
    display_name="Customer",
    primary_key="customer_id"
)

# 添加基础属性
customer.add_property("customer_id", PropertyType.STRING, description="客户ID")
customer.add_property("name", PropertyType.STRING, description="客户姓名")
customer.add_property("email", PropertyType.STRING, description="邮箱")
customer.add_property("phone", PropertyType.STRING, description="电话")
customer.add_property("created_at", PropertyType.DATE, description="创建日期")

# 注册对象类型
ontology.register_object_type(customer)

print(f"已注册 {len(ontology.object_types)} 个对象类型")
```

### 教程2: 管理对象关系

```python
from ontology_framework import LinkType

# 定义客户-订单关系
customer_orders = LinkType(
    api_name="customer_orders",
    display_name="Customer Orders",
    source_object_type="customer",
    target_object_type="order",
    cardinality="ONE_TO_MANY"
)

# 注册链接类型
ontology.register_link_type(customer_orders)

# 创建订单对象类型
order = ObjectType(
    api_name="order",
    display_name="Order",
    primary_key="order_id"
)
order.add_property("order_id", PropertyType.STRING)
order.add_property("order_date", PropertyType.DATE)
order.add_property("total_amount", PropertyType.INTEGER)

ontology.register_object_type(order)

# 创建实例和链接
customer = ObjectInstance(
    object_type_api_name="customer",
    primary_key_value="CUST001",
    property_values={"name": "张三", "email": "zhangsan@example.com"}
)

order = ObjectInstance(
    object_type_api_name="order",
    primary_key_value("ORDER001"),
    property_values={"order_date": "2024-01-01", "total_amount": 1000}
)

# 创建链接
ontology.create_link("customer_orders", "CUST001", "ORDER001")

# 导航关系
customer_orders = ontology.search_around("customer", "CUST001", link_type="customer_orders")
```

### 教程3: 使用函数和动作

```python
from ontology_framework.functions import ontology_function
from ontology_framework.core import ActionType, ActionContext

# 定义计算函数
@ontology_function(
    api_name="calculate_total",
    inputs={"items": PrimitiveType(PropertyType.STRING)}
)
def calculate_total(items):
    """计算订单总金额"""
    import json
    items_list = json.loads(items)
    return sum(item.get("price", 0) for item in items_list)

# 注册函数
ontology.register_function(calculate_total)

# 定义订单创建动作
create_order = ActionType(
    api_name="create_order",
    display_name="Create Order",
    target_object_types=["order"]
)
create_order.add_parameter("customer_id", "string", required=True)
create_order.add_parameter("items", "string", required=True)

def create_order_logic(context: ActionContext, **kwargs):
    """订单创建逻辑"""
    order_id = f"ORD_{int(time.time())}"
    total_amount = calculate_total(kwargs["items"])

    context.create_object("order", order_id, {
        "customer_id": kwargs["customer_id"],
        "items": kwargs["items"],
        "total_amount": total_amount,
        "status": "created"
    })

create_order.logic = create_order_logic
ontology.register_action_type(create_order)

# 执行动作
action_log = ontology.execute_action(
    "create_order",
    {
        "customer_id": "CUST001",
        "items": '[{"name": "Product A", "price": 500}, {"name": "Product B", "price": 300}]'
    },
    Principal("admin", "admin")
)
```

## 高级功能

### 1. 权限管理

```python
from ontology_framework.permissions import AccessControlList, Principal, PermissionType

# 创建ACL
acl = AccessControlList()

# 授予权限
acl.grant("admin", PermissionType.ADMIN)
acl.grant("manager", PermissionType.EDIT)
acl.grant("user", PermissionType.VIEW)

# 应用权限
customer.permissions = acl

# 检查权限
principal = Principal("manager", "manager")
if customer.permissions.check(principal.id, PermissionType.EDIT):
    print("有编辑权限")
else:
    print("无编辑权限")
```

### 2. 结构化日志

```python
from ontology_framework.logging_config import LoggingContext, main_logger

# 使用日志上下文
with LoggingContext(user_id="user123", operation="create_object"):
    main_logger.info("开始创建对象")

    # 执行业务逻辑
    ontology.add_object(obj_instance)

    main_logger.info("对象创建完成", extra={"object_id": obj_instance.primary_key_value})
```

### 3. 错误处理和恢复

```python
from ontology_framework.error_recovery import with_retry, with_circuit_breaker
from ontology_framework.exceptions import OntologyError

# 使用重试机制
@with_retry(max_attempts=3, base_delay=1.0)
def risky_operation():
    # 可能失败的操作
    pass

# 使用熔断器
@with_circuit_breaker(failure_threshold=5, recovery_timeout=60)
def protected_service():
    # 受保护的服务调用
    pass

try:
    risky_operation()
except OntologyError as e:
    print(f"操作失败: {e}")
```

### 4. 应用层组件

```python
from ontology_framework.applications import ObjectView, ObjectExplorer, Quiver

# 创建对象视图
product_view = ObjectView(
    object_type=product_type,
    title="产品列表视图",
    widgets=["产品表格", "价格图表", "库存状态"]
)

# 创建对象浏览器
explorer = ObjectExplorer()
explorer.register_view(product_view)

# 使用分析工具
quiver = Quiver()

# 浏览和分析数据
products = ontology.get_objects_of_type("product")
explorer.open("product", products)
quiver.analyze(products)
```

## 最佳实践

### 1. 对象设计原则

#### 1.1 命名规范
```python
# 好的命名
api_name="user_profile"          # 使用下划线分隔
display_name="User Profile"      # 人类可读

# 避免的命名
api_name="UserProfile"           # 驿免驼峰命名
display_name="userprofile"        # 缺少可读性
```

#### 1.2 属性设计
```python
# 为查询优化设计属性
user_type.add_property("email", PropertyType.STRING)  # 可索引
user_type.add_property("age", PropertyType.INTEGER)   # 可计算
user_type.add_property("metadata", PropertyType.STRING)  # 避免索引
```

#### 1.3 主键选择
```python
# 推荐主键类型
primary_key="id"                  # 简单ID
primary_key="uuid"               # 唯一标识
primary_key="composite_id"        # 复合主键

# 避免使用
primary_key="name"               # 可能重复
primary_key="timestamp"           # 不稳定
```

### 2. 性能优化

#### 2.1 批量操作
```python
# 好的做法 - 批量处理
objects = [ObjectInstance(...) for _ in range(1000)]
for obj in objects:
    ontology.add_object(obj)

# 避免的做法 - 单个处理
for i in range(1000):
    obj = ObjectInstance(...)
    ontology.add_object(obj)
```

#### 2.2 缓存使用
```python
# 利用对象集缓存
employees = ontology.get_objects_of_type("employee")
# 后续操作直接使用缓存的集合
filtered_employees = employees.filter("department", "Engineering")
```

#### 2.3 查询优化
```python
# 使用过滤而不是遍历
# 好的做法
high_salary_employees = employees.filter("salary", lambda x: x > 50000)

# 避免的做法
high_salary_employees = []
for emp in employees.all():
    if emp.property_values.get("salary", 0) > 50000:
        high_salary_employees.append(emp)
```

### 3. 错误处理

#### 3.1 异常处理模式
```python
try:
    result = ontology.execute_function("risky_function", **params)
except ValidationError as e:
    logger.error(f"验证错误: {e}")
    # 处理验证错误
except OntologyError as e:
    logger.error(f"本体错误: {e}")
    # 处理本体错误
```

#### 3.2 日志记录
```python
import logging

# 记录关键操作
logger = logging.getLogger(__name__)
logger.info("开始处理数据", extra={"data_size": len(data)})
try:
    # 处理逻辑
    pass
    logger.info("数据处理完成")
except Exception as e:
    logger.error(f"数据处理失败: {e}", exc_info=True)
```

### 4. 测试策略

#### 4.1 单元测试
```python
import pytest
from ontology_framework import ObjectType, PropertyType, ObjectInstance

def test_object_creation():
    # 准备
    obj_type = ObjectType("test", "Test", "id")
    obj_type.add_property("name", PropertyType.STRING)

    # 执行
    instance = ObjectInstance("test", "1", {"name": "test"})

    # 验证
    assert instance.object_type_api_name == "test"
    assert instance.primary_key_value == "1"
    assert instance.property_values["name"] == "test"
```

#### 4.2 集成测试
```python
def test_end_to_end_workflow():
    # 完整工作流测试
    ontology = Ontology()

    # 定义类型
    # 创建实例
    # 执行动作
    # 验证结果
    pass
```

## 故障排除

### 常见问题

#### 1. 导入错误
```python
# 错误
ImportError: cannot import name 'Ontology'

# 解决方案
from ontology_framework import Ontology  # 确保从正确位置导入
```

#### 2. 类型注册错误
```python
# 错误
ValueError: Target object type not found

# 解决方案
# 确保在使用前注册所有依赖的对象类型
ontology.register_object_type(target_type)
```

#### 3. 权限错误
```python
# 错误
PermissionError: User has no permission

# 解决方案
# 检查权限设置和用户身份
if not obj_type.permissions.check(user.id, PermissionType.EDIT):
    # 处理权限不足的情况
    raise PermissionError("权限不足")
```

### 调试技巧

#### 1. 使用调试工具
```python
from ontology_framework.debug_tools import debug, profile

@debug
def debug_function():
    # 调试函数执行
    pass

@profile
def profile_function():
    # 性能分析
    pass
```

#### 2. 日志分析
```python
# 启用详细日志
import logging
logging.basicConfig(level=logging.DEBUG)

# 使用结构化日志
from ontology_framework.logging_config import LoggingContext

with LoggingContext(user_id="debug_user"):
    # 执行需要调试的代码
    pass
```

## API参考

详细的API参考文档请参见：
- [完整API参考](./API_REFERENCE_UPDATED.md)
- [架构设计文档](./ARCHITECTURE_DESIGN.md)

## 社区和资源

- **GitHub**: [https://github.com/your-org/ontology-framework](https://github.com/your-org/ontology-framework)
- **文档**: [https://ontology-framework.readthedocs.io](https://ontology-framework.readthedocs.io)
- **问题反馈**: [GitHub Issues](https://github.com/your-org/ontology-framework/issues)

## 贡献指南

我们欢迎社区贡献！请参考 [CONTRIBUTING.md](./CONTRIBUTING.md) 了解如何参与项目开发。

## 许可证

本项目采用 [MIT License](./LICENSE) 开源许可证。