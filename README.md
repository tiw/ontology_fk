# Ontology Framework

A Python-based framework for defining and managing a semantic Ontology, inspired by Palantir Foundry. This framework allows you to define Object Types, Link Types, Action Types, and Functions to model complex business logic and data relationships.

## Core Concepts

- **Object Types**: Definitions of entities (e.g., Employee, Flight) with properties.
- **Link Types**: Relationships between objects (e.g., Employee works_for Department).
- **Action Types**: Transactional operations that modify objects or links.
- **Functions**: Code logic embedded in the ontology for calculations, edits, and integrations.

## Installation

To use this library in other projects, you can install it directly from the source.

### Local Development (Editable Mode)
Recommended if you plan to modify the framework code while using it.
```bash
pip install -e /path/to/ontology_fk
```

### Install as a Package
If you just want to use the library without modifying it:
```bash
pip install /path/to/ontology_fk
```

### Build and Install
You can also build a wheel file to distribute:
1. Build the package: `python -m build`
2. Install the generated wheel: `pip install dist/ontology_fk-0.1.0-py3-none-any.whl`

## Getting Started

```python
from ontology_framework.core import Ontology, ObjectType, PropertyType

# Initialize Ontology
ontology = Ontology()

# Define an Object Type
employee = ObjectType(api_name="employee", display_name="Employee", primary_key="id")
employee.add_property("name", PropertyType.STRING)
ontology.register_object_type(employee)
```

## Using Functions

Functions allow you to encapsulate business logic, perform calculations on objects, and execute complex ontology edits.

### 1. Defining Functions

Use the `@ontology_function` decorator to register functions. You can specify input types using `PrimitiveType`, `ObjectTypeSpec`, or `ObjectSetTypeSpec`.

```python
from ontology_framework.functions import ontology_function
from ontology_framework.core import PrimitiveType, PropertyType, ObjectTypeSpec, ObjectInstance, ActionContext

# Simple calculation function
@ontology_function(
    api_name="calculate_bonus",
    inputs={"salary": PrimitiveType(PropertyType.INTEGER)},
    display_name="Calculate Bonus"
)
def calculate_bonus(salary: int) -> int:
    return int(salary * 0.15)

# Function operating on an Object
@ontology_function(
    api_name="promote_employee",
    inputs={"employee": ObjectTypeSpec("employee")},
    display_name="Promote Employee"
)
def promote_employee(employee: ObjectInstance) -> str:
    return f"Promoting {employee.primary_key_value}"
```

### 2. Functions with Side Effects (Ontology Edits)

To modify the ontology (create/edit/delete objects or links), your function must accept an `ActionContext`.

```python
@ontology_function(
    api_name="create_employee",
    inputs={
        "id": PrimitiveType(PropertyType.STRING),
        "name": PrimitiveType(PropertyType.STRING)
    }
)
def create_employee(ctx: ActionContext, id: str, name: str):
    # Stage a creation
    ctx.create_object("employee", id, {"id": id, "name": name})
    
    # Changes are applied when the context is committed
```

### 3. Executing Functions

You can execute functions directly via the `Ontology` instance.

```python
# Execute calculation
bonus = ontology.execute_function("calculate_bonus", salary=50000)

# Execute with Context (for edits)
ctx = ActionContext(ontology, "user_id")
ontology.execute_function("create_employee", ctx=ctx, id="emp_001", name="Alice")
ctx.apply_changes() # Commit changes
```

### 4. Function-backed Actions

You can link an `ActionType` to a function to expose it as a user action.

```python
from ontology_framework.core import ActionType

action = ActionType(
    api_name="hire_employee_action",
    display_name="Hire Employee",
    target_object_types=["employee"],
    backing_function_api_name="create_employee"
)
ontology.register_action_type(action)
```

### 5. 函数驱动的治理与评分

LinkType 现支持直接声明 `validation_functions` 与 `scoring_function_api_name`。当 Agent 通过 `ObjectSet.search_around()` 或 FastMCP 的 `get_related_objects` 遍历链接时，这些函数会被自动执行，只有通过验证的对象才会被返回，同时评分结果也会写入对象的 `runtime_metadata`：

```python
@ontology_function(
    api_name="validate_order_merchant_link",
    inputs={
        "order": ObjectTypeSpec("Order"),
        "merchant": ObjectTypeSpec("Merchant"),
    }
)
def validate_order_merchant_link(order, merchant) -> bool:
    return order.get("merchant_id") == merchant.get("merchant_id")

@ontology_function(
    api_name="score_order_rider_timeliness",
    inputs={
        "order": ObjectTypeSpec("Order"),
        "rider": ObjectTypeSpec("Rider")
    },
    output_type=PrimitiveType(PropertyType.INTEGER)
)
def score_order_rider_timeliness(order, rider):
    return max(-30, min(30, order.get("t_gap_min") or 0))

link = LinkType(
    api_name="OrderHasRider",
    display_name="Order Rider",
    source_object_type="Order",
    target_object_type="Rider",
    validation_functions=["validate_order_rider_assignment"],
    scoring_function_api_name="score_order_rider_timeliness",
)
```

验证函数可以返回 `False`、`0` 或 `{"valid": False}` 来阻断结果；评分函数的输出则以 `function_scores[link_type_api_name]` 的形式附着在对象快照上，便于 LLM/前端直接消费。

## FastMCP 集成：让本体能力服务 LLM

为了让 LLM 能够直接查询/编辑本体数据，本仓库新增了一个 FastMCP Server（基于 `fastmcp>=2.13`）。它会加载 `example/order_delivery` 场景的完整 ontology，并暴露安全的工具与结构化资源。

### 快速启动

```bash
# 安装依赖（只需一次）
uv pip install -e .[dev]

# 启动 FastMCP Server（stdio，适合 Claude Desktop 等直接连接）
uv run python example/order_delivery/fastmcp_server.py --transport stdio

# 如需 HTTP/SSE，附带 host/port
uv run python example/order_delivery/fastmcp_server.py --transport http --host 127.0.0.1 --port 8765
```

启动后，MCP 客户端会在连接时读取 `resource://ontology/schema` 与 `resource://ontology/guide` 获取结构信息，从而“知道”有哪些对象、动作与派生函数可用，再通过工具实现读写。

### 工具一览

| 工具 | 说明 |
| --- | --- |
| `list_object_types` / `list_link_types` | 浏览对象/链接 Schema 及字段 |
| `list_actions` / `list_functions` | 查看可执行 Action、函数的参数约束 |
| `list_objects` / `get_object` | 查询实体实例，可附 `filters_json` |
| `get_related_objects` | 沿链接（如 `OrderHasMerchant`）遍历关联对象 |
| `execute_action` | 执行动作（如 `CreateOrder`、`RiderDeliver`），参数以 JSON 传入 |
| `invoke_function` | 调用函数（如 `calculate_t_gap`），支持对象引用 |

所有工具都返回 JSON，方便 LLM 二次推理；对 Action/Function 的参数校验也遵循 ontology 中的类型定义，避免脏写。

### 新增：治理绑定与运行时注解

- `get_related_objects` 现使用 `ObjectSet.search_around()`，自动执行 LinkType 的 `validation_functions` / `scoring_function_api_name`，并把每个关联对象的 `runtime_metadata.function_scores` 一并返回。
- `get_object` / `list_objects` 默认附带 `runtime_metadata`，且 `filters_json` 支持 `derived.xxx` 语法，Agent 可以直接对派生指标/治理输出进行过滤。
- `limit` 与 `direction` 参数可精细化控制遍历结果，避免在 LLM 工作流中出现“未治理”的脏对象。

### 结构化资源

- `resource://ontology/schema`：`Ontology.export_schema_for_llm()` 的 JSON 输出，囊括对象、属性、链接与动作。
- `resource://ontology/guide`：Markdown 指南，列出示例调用、推荐工作流。

LLM 在调用工具前应优先读取这些资源，以便理解字段含义、派生属性和动作依赖，从而“更聪明”地使用本体能力。

## Ontology SDK (OSDK)

`OntologySDK` 为 Agent/AIP Logic 提供类型安全的调用方式，它会基于函数签名与对象类型自动执行校验：

```python
from ontology_framework.osdk import OntologySDK

sdk = OntologySDK(ontology)

# 严格校验对象是否存在
order = sdk.get_object("Order", "ord_fast")

# 自动解析函数参数（支持 primary_key / ObjectInstance）
result = sdk.execute_function(
    "calculate_t_gap",
    order={"object_type": "Order", "primary_key": "ord_fast"}
)

# 输出包含函数/治理策略的 schema，供 Agent 做 prompt 规划
schema_payload = sdk.describe_schema()
```

若参数缺失、类型不匹配或引用了不存在的对象，SDK 会抛出 `ValidationError`/`NotFoundError`，阻止 Agent 生成不合法的调用。

## 新增亮点速览

- **Functions 治理**：LinkType 遍历时自动执行验证/评分，结果对象随带 `runtime_metadata`，LLM 获取的即是“已治理”数据。
- **ActionContext 扩展**：`create_object` 既可指定 PK，也可直接传入属性字典，框架会自动补齐主键并在必要时临时注册对象类型，方便治理函数或 Action 快速生成临时实体。
- **Performance Monitor 升级**：支持 `add_custom_metric`、`track_operation`、监控仪表盘导出；`IndexManager` 增加 `create_property_index` 与 `get_index_stats` 以对接 `PerformanceOptimizerAdapter`。
- **FastMCP 工具增强**：`get_related_objects` 支持 `filters_json`/limit，并返回 Anchor/Related 的派生属性与治理分数，便于前端或 LLM 直接消费。
