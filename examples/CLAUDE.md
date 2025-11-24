[根目录](../../CLAUDE.md) > **examples** > **工厂本体示例**

# 工厂本体管理示例

## 示例概述

本示例演示如何使用 Ontology Framework 构建一个完整的工厂管理系统，展示框架的权限控制、数据管理、查询分析等核心功能的实际应用场景。

## 业务背景

工厂管理系统需要管理：
- 工厂基础信息（位置、产能、状态等）
- 生产设备及其状态
- 生产订单和流程
- 员工信息和权限管理
- 数据分析和报表

## 核心功能演示

### 1. 权限控制系统
```python
from ontology_framework import AccessControlList, PermissionType

# 创建访问控制列表
factory_acl = AccessControlList()
factory_acl.grant("user_1", PermissionType.VIEW)
factory_acl.grant("user_1", PermissionType.EDIT)
factory_acl.grant("admin_1", PermissionType.OWNER)

# 应用权限到对象类型
factory = ObjectType(
    api_name="Factory",
    display_name="Factory",
    primary_key="factory_id",
    permissions=factory_acl
)
```

**权限类型**:
- **VIEW**: 查看权限
- **EDIT**: 编辑权限
- **DELETE**: 删除权限
- **OWNER**: 所有者权限（包含所有权限）

### 2. 对象类型定义
```python
# 工厂对象类型
factory = ObjectType(
    api_name="Factory",
    display_name="Factory",
    primary_key="factory_id",
    title_property="location",
    icon="factory",
    backing_datasource_id="ri.foundry.main.dataset.1234",  # 模拟数据源绑定
    permissions=factory_acl
)
factory.add_property("factory_id", PropertyType.STRING)
factory.add_property("location", PropertyType.STRING)
factory.add_property("capacity", PropertyType.INTEGER)
factory.add_property("status", PropertyType.STRING)

# 设备对象类型
equipment = ObjectType(
    api_name="Equipment",
    display_name="Production Equipment",
    primary_key="equipment_id",
    title_property="name"
)
equipment.add_property("equipment_id", PropertyType.STRING)
equipment.add_property("name", PropertyType.STRING)
equipment.add_property("type", PropertyType.STRING)
equipment.add_property("factory_id", PropertyType.STRING)
equipment.add_property("status", PropertyType.STRING)
```

### 3. 对象实例创建和索引
```python
# 创建工厂实例
f1 = ObjectInstance("Factory", "F1", {
    "factory_id": "F1",
    "location": "New York",
    "capacity": 100
})

# 使用 ObjectSetService 进行索引管理
oss = ObjectSetService()
oss.index_object(f1)
oss.index_object(f2)
oss.index_object(f3)
```

### 4. 权限验证的数据访问
```python
try:
    # 无权限用户访问（应该抛出异常）
    base_set = oss.get_base_object_set(factory, principal_id="user_2")
except PermissionError as e:
    print(f"Expected Error: {e}")

# 有权限用户访问
base_set = oss.get_base_object_set(factory, principal_id="user_1")
print(f"Accessible factories: {len(base_set.all())}")
```

### 5. 查询和分析功能
```python
# 基础过滤查询
large_factories = base_set.filter("capacity", lambda x: x > 150)

# 语义搜索（基于文本匹配）
search_results = oss.search(factory, "New York")

# 数据分析集成
explorer = ObjectExplorer()
quiver = Quiver()

explorer.open("Factory", base_set)
quiver.analyze(large_factories)
```

## 高级功能演示

### 1. 函数集成的数据分析
```python
@ontology_function(
    api_name="calculate_utilization",
    inputs={"factory": ObjectTypeSpec("Factory")},
    display_name="计算工厂利用率"
)
def calculate_utilization(factory: ObjectInstance) -> float:
    """根据当前生产量计算工厂利用率"""
    # 模拟：当前生产量 / 最大产能
    current_production = get_current_production(factory.primary_key_value)
    max_capacity = factory.get("capacity")

    return (current_production / max_capacity) * 100 if max_capacity > 0 else 0

# 注册派生属性
factory.add_derived_property("utilization_rate", PropertyType.INTEGER, "calculate_utilization")
```

### 2. 事务操作
```python
@ontology_function(
    api_name="update_factory_status",
    inputs={
        "ctx": ActionContext(),
        "factory": ObjectTypeSpec("Factory"),
        "new_status": PrimitiveType(PropertyType.STRING)
    },
    display_name="更新工厂状态"
)
def update_factory_status(ctx: ActionContext, factory: ObjectInstance, new_status: str):
    """更新工厂状态，记录操作日志"""
    old_status = factory.get("status")

    # 更新状态
    ctx.update_object("Factory", factory.primary_key_value, {
        "status": new_status
    })

    # 记录日志
    ctx.log_action(
        action_type="status_update",
        object_id=factory.primary_key_value,
        details=f"Status changed from {old_status} to {new_status}"
    )
```

### 3. 关系导航
```python
# 定义工厂-设备关系
equipment_link = LinkType(
    api_name="factory_equipment",
    display_name="Factory Equipment",
    source_object_type="Factory",
    target_object_type="Equipment"
)

# 查询某个工厂的所有设备
factory = base_set.filter("location", "New York").first()
factory_equipment = factory.search_around("factory_equipment", type="production")
```

## 应用层集成

### 1. 自定义视图
```python
class FactoryDashboardView:
    def __init__(self):
        self.widgets = ["capacity_chart", "status_summary", "utilization_gauge"]

    def render(self, object_set: ObjectSet):
        print(f"--- 工厂仪表板 ---")
        print(f"工厂总数: {len(object_set.all())}")

        # 计算统计数据
        total_capacity = sum(f.get("capacity") for f in object_set.all())
        active_count = len([f for f in object_set.all() if f.get("status") == "active"])

        print(f"总产能: {total_capacity}")
        print(f"活跃工厂数: {active_count}")
        print("------------------")

# 注册自定义视图
dashboard_view = FactoryDashboardView()
explorer.register_view(ObjectView(factory, "工厂仪表板", ["容量图表", "状态统计", "利用率"]))
```

### 2. 数据分析组件
```python
class FactoryAnalysis(Quiver):
    def analyze_efficiency(self, object_set: ObjectSet):
        """分析工厂效率"""
        print("--- 工厂效率分析 ---")

        for factory in object_set.all():
            utilization = factory.get("utilization_rate") or 0
            capacity = factory.get("capacity")

            print(f"工厂 {factory.get('location')}:")
            print(f"  产能: {capacity}")
            print(f"  利用率: {utilization:.1f}%")

            # 优化建议
            if utilization < 50:
                print(f"  建议: 产能利用率偏低，考虑优化生产计划")
            elif utilization > 90:
                print(f"  警告: 产能利用率过高，考虑扩容")

        print("---------------------")

# 使用分析组件
analysis = FactoryAnalysis()
analysis.analyze_efficiency(base_set)
```

## 完整工作流程

### 1. 系统初始化
```python
def initialize_system():
    """初始化工厂管理系统"""
    ontology = Ontology()
    oss = ObjectSetService()
    explorer = ObjectExplorer()
    quiver = Quiver()

    # 注册对象类型
    ontology.register_object_type(factory)
    ontology.register_object_type(equipment)

    # 注册关系类型
    ontology.register_link_type(equipment_link)

    # 注册函数
    registry.register_all_to_ontology(ontology)

    return ontology, oss, explorer, quiver
```

### 2. 数据管理
```python
def setup_sample_data():
    """设置示例数据"""
    # 创建工厂数据
    factories = [
        {"id": "F1", "location": "New York", "capacity": 100, "status": "active"},
        {"id": "F2", "location": "London", "capacity": 200, "status": "active"},
        {"id": "F3", "location": "Tokyo", "capacity": 150, "status": "maintenance"}
    ]

    for f_data in factories:
        factory_obj = ObjectInstance("Factory", f_data["id"], {
            "factory_id": f_data["id"],
            "location": f_data["location"],
            "capacity": f_data["capacity"],
            "status": f_data["status"]
        })
        oss.index_object(factory_obj)
```

### 3. 权限管理
```python
def setup_permissions():
    """设置用户权限"""
    # 管理员权限
    admin_acl = AccessControlList()
    admin_acl.grant("admin_1", PermissionType.OWNER)

    # 运营人员权限
    ops_acl = AccessControlList()
    ops_acl.grant("ops_user_1", PermissionType.VIEW)
    ops_acl.grant("ops_user_1", PermissionType.EDIT)

    # 只读用户权限
    readonly_acl = AccessControlList()
    readonly_acl.grant("viewer_1", PermissionType.VIEW)

    return admin_acl, ops_acl, readonly_acl
```

## 扩展场景

### 1. 实时监控
- 设备状态实时更新
- 生产数据实时采集
- 异常情况预警

### 2. 报表系统
- 生产效率报表
- 设备维护报表
- 成本分析报表

### 3. 预测分析
- 产能需求预测
- 设备故障预测
- 维护计划优化

## 技术特点

### 1. 模块化设计
- 权限、数据、查询、分析各模块分离
- 支持独立开发和测试
- 易于扩展和维护

### 2. 类型安全
- 强类型定义确保数据一致性
- 编译时类型检查
- 运行时类型验证

### 3. 可扩展性
- 插件式函数注册
- 自定义视图组件
- 灵活的权限模型

## 最佳实践

### 1. 权限设计
- 遵循最小权限原则
- 定期审查权限分配
- 使用组权限简化管理

### 2. 数据建模
- 明确主键和外键关系
- 合理使用派生属性
- 保持数据一致性

### 3. 性能优化
- 建立合适的索引
- 使用批量操作
- 实现查询缓存

## 文件说明

- **factory_ontology.py**: 完整的工厂本体管理系统示例
- 演示了权限控制、数据管理、查询分析等核心功能
- 提供了可直接运行的完整代码

## 相关模块

- **权限系统**: `src/ontology_framework/permissions.py`
- **服务层**: `src/ontology_framework/services.py`
- **应用层**: `src/ontology_framework/applications.py`
- **核心框架**: `src/ontology_framework/core.py`

## 变更记录 (Changelog)

- **2025-11-24**: 初始工厂本体示例文档完成
  - 完成权限控制演示
  - 记录数据管理流程
  - 提供扩展场景建议