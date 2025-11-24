[根目录](../../../CLAUDE.md) > [example](../../) > [order_delivery](../) > **订单配送示例**

# 订单配送本体示例

## 模块职责

本示例展示如何使用 Ontology Framework 建模一个完整的订单配送业务场景。包含订单、商家、骑手等核心业务实体，以及它们之间的复杂关系和状态流转。

## 业务场景

订单配送系统是一个典型的实时业务流程，涉及：
- **用户下单**: 用户创建订单
- **商家接单**: 商家确认并准备订单
- **骑手配送**: 骑手取货并配送给用户
- **完成交付**: 订单完成，用户确认收货

## 核心实体模型

### 1. Order (订单)
**主要属性**:
- 基础信息: `order_id`, `user_id`, `merchant_id`, `rider_id`
- 状态信息: `status`
- 商品信息: `items`
- 时间追踪: `ts_created`, `ts_merchant_accepted`, `ts_rider_called`, `ts_merchant_out`, `ts_rider_arrived_store`, `ts_rider_picked`, `ts_delivered`
- 期望时效: `user_expected_t_min`
- **派生属性**: `actual_t_min` (实际配送时长), `t_gap_min` (时效差)

### 2. Merchant (商家/餐厅)
**主要属性**:
- `merchant_id`: 商家ID
- `name`: 商家名称
- `address`: 商家地址

### 3. Rider (骑手)
**主要属性**:
- `rider_id`: 骑手ID
- `name`: 骑手姓名
- `status`: 当前状态
- `location`: 当前位置

### 4. User (用户)
**主要属性**:
- `user_id`: 用户ID
- `name`: 用户姓名
- `address`: 用户地址

## 关系定义

### 1. Order → Merchant
- **关系**: "ordered_from"
- **方向**: Order -> Merchant
- **描述**: 订单从哪个商家下单

### 2. Order → Rider
- **关系**: "delivered_by"
- **方向**: Order -> Rider
- **描述**: 订单由哪个骑手配送

### 3. Order → User
- **关系**: "belongs_to"
- **方向**: Order -> User
- **描述**: 订单属于哪个用户

## 业务函数

### 1. 时效计算函数
```python
@ontology_function(
    api_name="calculate_actual_t",
    inputs={"order": ObjectTypeSpec("Order")},
    display_name="计算实际配送时长"
)
def calculate_actual_t(order: ObjectInstance) -> int:
    """计算订单的实际配送时长（分钟）"""
    created_time = order.get("ts_created")
    delivered_time = order.get("ts_delivered")

    if created_time and delivered_time:
        return int((delivered_time - created_time) / 60000)  # 转换为分钟
    return 0
```

### 2. 时效差分析函数
```python
@ontology_function(
    api_name="calculate_t_gap",
    inputs={"order": ObjectTypeSpec("Order")},
    display_name="计算时效差"
)
def calculate_t_gap(order: ObjectInstance) -> int:
    """计算期望时效与实际时效的差值"""
    expected = order.get("user_expected_t_min")
    actual = order.get("actual_t_min")

    if expected and actual:
        return actual - expected
    return 0
```

### 3. 商家接单操作
```python
@ontology_function(
    api_name="merchant_accept_order",
    inputs={
        "ctx": ActionContext(),
        "order": ObjectTypeSpec("Order"),
        "merchant": ObjectTypeSpec("Merchant")
    },
    display_name="商家接单"
)
def merchant_accept_order(ctx: ActionContext, order: ObjectInstance, merchant: ObjectInstance):
    """商家接受订单，更新订单状态和接单时间"""
    import time

    # 验证订单状态
    if order.get("status") != "created":
        raise ValueError("只有新创建的订单才能被接单")

    # 更新订单
    ctx.update_object("Order", order.primary_key_value, {
        "status": "merchant_accepted",
        "ts_merchant_accepted": int(time.time() * 1000)
    })
```

## 状态流转

### 订单状态
1. **created**: 订单已创建
2. **merchant_accepted**: 商家已接单
3. **rider_called**: 已呼叫骑手
4. **merchant_out**: 商家出餐
5. **rider_arrived_store**: 骑手到店
6. **rider_picked**: 骑手取货
7. **delivered**: 已配送完成

### 业务规则
- 状态只能按顺序流转
- 每个状态变更都需要记录时间戳
- 支持状态回滚（异常情况）

## 数据分析场景

### 1. 配送效率分析
```python
# 查询所有已完成的订单
completed_orders = ontology.get_objects_of_type("Order").filter("status", "delivered")

# 计算平均配送时长
total_time = sum(order.get("actual_t_min") for order in completed_orders.all())
avg_delivery_time = total_time / len(completed_orders.all())

# 分析时效差
gap_orders = [order for order in completed_orders.all()
              if order.get("t_gap_min") > 10]  # 超时10分钟以上的订单
```

### 2. 商家表现分析
```python
# 按商家分析订单量和平均时效
merchant_stats = {}
for order in completed_orders.all():
    merchant_id = order.get("merchant_id")
    if merchant_id not in merchant_stats:
        merchant_stats[merchant_id] = {
            "order_count": 0,
            "total_time": 0,
            "delays": 0
        }

    stats = merchant_stats[merchant_id]
    stats["order_count"] += 1
    stats["total_time"] += order.get("actual_t_min")

    if order.get("t_gap_min") > 10:
        stats["delays"] += 1
```

### 3. 骑手绩效分析
```python
# 分析骑手配送效率
rider_performance = {}
for order in completed_orders.all():
    rider_id = order.get("rider_id")
    if rider_id not in rider_performance:
        rider_performance[rider_id] = {
            "orders": 0,
            "avg_time": 0,
            "on_time_rate": 0
        }

    perf = rider_performance[rider_id]
    perf["orders"] += 1

    # 更新平均时间
    if perf["orders"] == 1:
        perf["avg_time"] = order.get("actual_t_min")
    else:
        perf["avg_time"] = (perf["avg_time"] * (perf["orders"] - 1) + order.get("actual_t_min")) / perf["orders"]

    # 计算准时率
    if order.get("t_gap_min") <= 0:
        perf["on_time_rate"] += 1 / perf["orders"]
```

## 扩展场景

### 1. 实时监控
- 订单状态变更通知
- 配送超时预警
- 骑手位置追踪

### 2. 智能调度
- 基于骑手位置和负载的智能派单
- 预计配送时间计算
- 路径优化建议

### 3. 质量管控
- 用户评价系统
- 配送质量评分
- 异常事件追踪

## 技术特点

### 1. 时间序列数据
- 完整记录订单生命周期各节点时间
- 支持时效分析和性能监控
- 时间戳精度到毫秒

### 2. 派生属性应用
- 通过函数实现动态计算
- 支持复杂的业务逻辑
- 保持数据一致性

### 3. 关系导航
- 支持跨实体查询
- 高效的数据关联
- 灵活的过滤条件

## 文件说明

- **schema.py**: 本体模型定义，包含所有对象类型和关系定义
- **run.py**: 示例运行脚本，演示完整的业务流程
- **simulation.py**: 模拟器，生成测试数据和业务场景
- **verify_oag.py**: OAG（Ontology Application Guide）验证脚本

## 使用场景

### 1. 业务分析
- 配送效率分析
- 商家和骑手绩效评估
- 时效优化建议

### 2. 实时监控
- 订单状态实时追踪
- 异常情况预警
- KPI 监控仪表板

### 3. 决策支持
- 资源调度优化
- 业务流程改进
- 客户服务质量提升

## 最佳实践

### 1. 状态管理
- 使用枚举定义状态常量
- 实现状态转换验证
- 记录状态变更历史

### 2. 时间处理
- 统一时间戳格式（毫秒）
- 考虑时区问题
- 实现时间计算工具函数

### 3. 性能优化
- 建立时间戳索引
- 使用批量查询减少数据库访问
- 实现缓存机制

## 扩展建议

### 1. 地理信息集成
- 集成地图服务
- 计算配送距离
- 路径规划算法

### 2. 通知系统
- 状态变更通知
- 推送消息服务
- 邮件和短信集成

### 3. 报表系统
- 定时报表生成
- 数据可视化
- 趋势分析

## 变更记录 (Changelog)

- **2025-11-24**: 初始订单配送示例文档完成
  - 完成业务模型分析
  - 记录函数实现细节
  - 提供数据分析场景