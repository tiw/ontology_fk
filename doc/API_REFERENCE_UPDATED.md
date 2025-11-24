# Ontology Framework API Reference

本文档提供 Ontology Framework 的完整 API 参考文档。

## 目录

1. [Ontology](#ontology) - 核心本体管理器
2. [ObjectType](#objecttype) - 对象类型定义
3. [LinkType](#linktype) - 链接类型定义
4. [ActionType](#actiontype) - 动作类型定义
5. [ObjectInstance](#objectinstance) - 对象实例
6. [ObjectSet](#objectset) - 对象集合
7. [PropertyType](#propertytype) - 属性类型枚举
8. [ObjectSetService](#objectsetservice) - 对象集合服务
9. [ActionService](#actionservice) - 动作服务
10. [ObjectView](#objectview) - 对象视图
11. [ObjectExplorer](#objectexplorer) - 对象浏览器
12. [Quiver](#quiver) - 数据分析工具
13. [AccessControlList](#accesscontrollist) - 访问控制列表
14. [Principal](#principal) - 主体
15. [PermissionType](#permissiontype) - 权限类型
16. [OntologyError](#ontologyerror) - 基础异常类
17. [ValidationError](#validationerror) - 验证错误
18. [PermissionError](#permissionerror) - 权限错误
19. [OntologyLogger](#ontologylogger) - 结构化日志器
20. [LoggingContext](#loggingcontext) - 日志上下文管理
21. [RetryMechanism](#retrymechanism) - 重试机制
22. [CircuitBreaker](#circuitbreaker) - 熔断器
23. [DebugSession](#debugsession) - 调试会话
24. [PerformanceProfiler](#performanceprofiler) - 性能分析器

---

## Ontology

核心本体管理器

**构造函数**:
```python
Ontology(self)
```

**公共方法**:

### `add_object`

```python
add_object(self, object_instance: ontology_framework.core.ObjectInstance)
```

---

### `create_link`

```python
create_link(self, link_type_api_name: str, source_pk: Any, target_pk: Any, user_permissions: List[str] = None)
```

---

### `delete_link`

```python
delete_link(self, link_type_api_name: str, source_pk: Any, target_pk: Any, user_permissions: List[str] = None)
```

---

### `delete_object`

```python
delete_object(self, type_name: str, primary_key: Any)
```

---

### `execute_function`

```python
execute_function(self, function_api_name: str, **kwargs) -> Any
```

**返回值**: `typing.Any`

---

### `export_schema_for_llm`

```python
export_schema_for_llm(self) -> Dict[str, Any]
```

Exports the ontology schema in a format suitable for LLM prompts.

**返回值**: `typing.Dict[str, typing.Any]`

---

### `get_action_type`

```python
get_action_type(self, api_name: str) -> Optional[ontology_framework.core.ActionType]
```

**返回值**: `typing.Optional[ontology_framework.core.ActionType]`

---

### `get_all_links`

```python
get_all_links(self) -> List[ontology_framework.core.Link]
```

**返回值**: `typing.List[ontology_framework.core.Link]`

---

### `get_link_type`

```python
get_link_type(self, api_name: str) -> Optional[ontology_framework.core.LinkType]
```

**返回值**: `typing.Optional[ontology_framework.core.LinkType]`

---

### `get_object`

```python
get_object(self, type_name: str, primary_key: Any) -> Optional[ontology_framework.core.ObjectInstance]
```

**返回值**: `typing.Optional[ontology_framework.core.ObjectInstance]`

---

### `get_object_type`

```python
get_object_type(self, api_name: str) -> Optional[ontology_framework.core.ObjectType]
```

**返回值**: `typing.Optional[ontology_framework.core.ObjectType]`

---

### `get_objects_of_type`

```python
get_objects_of_type(self, type_name: str) -> List[ontology_framework.core.ObjectInstance]
```

**返回值**: `typing.List[ontology_framework.core.ObjectInstance]`

---

### `register_action_type`

```python
register_action_type(self, action_type: ontology_framework.core.ActionType)
```

---

### `register_function`

```python
register_function(self, function: ontology_framework.core.Function)
```

---

### `register_link_type`

```python
register_link_type(self, link_type: ontology_framework.core.LinkType)
```

---

### `register_object_type`

```python
register_object_type(self, object_type: ontology_framework.core.ObjectType)
```

---

---

## ObjectType

对象类型定义

**说明**: ObjectType(api_name: str, display_name: str, properties: Dict[str, ontology_framework.core.PropertyDefinition] = <factory>, derived_properties: Dict[str, ontology_framework.core.DerivedPropertyDefinition] = <factory>, primary_key: str = '', description: Optional[str] = None, backing_datasource_id: Optional[str] = None, title_property: Optional[str] = None, icon: Optional[str] = 'cube', permissions: Optional[ForwardRef('AccessControlList')] = None)

**构造函数**:
```python
ObjectType(self, api_name: str, display_name: str, properties: Dict[str, ontology_framework.core.PropertyDefinition] = <factory>, derived_properties: Dict[str, ontology_framework.core.DerivedPropertyDefinition] = <factory>, primary_key: str = '', description: Optional[str] = None, backing_datasource_id: Optional[str] = None, title_property: Optional[str] = None, icon: Optional[str] = 'cube', permissions: Optional[ForwardRef('AccessControlList')] = None) -> None
```

**类型**: `@dataclass`

**字段**:

- `api_name` (str): factory()
- `display_name` (str): factory()
- `properties` (Dict): <dataclasses._MISSING_TYPE object at 0x1013efad0>
- `derived_properties` (Dict): <dataclasses._MISSING_TYPE object at 0x1013efad0>
- `primary_key` (str): 
- `description` (Optional): None
- `backing_datasource_id` (Optional): None
- `title_property` (Optional): None
- `icon` (Optional): cube
- `permissions` (Optional): None

**公共方法**:

### `add_derived_property`

```python
add_derived_property(self, name: str, type: ontology_framework.core.PropertyType, backing_function_api_name: str, description: Optional[str] = None)
```

---

### `add_property`

```python
add_property(self, name: str, type: ontology_framework.core.PropertyType, description: Optional[str] = None)
```

---

---

## LinkType

链接类型定义

**说明**: LinkType(api_name: str, display_name: str, source_object_type: str, target_object_type: str, cardinality: str = 'ONE_TO_MANY', description: Optional[str] = None)

**构造函数**:
```python
LinkType(self, api_name: str, display_name: str, source_object_type: str, target_object_type: str, cardinality: str = 'ONE_TO_MANY', description: Optional[str] = None) -> None
```

**类型**: `@dataclass`

**字段**:

- `api_name` (str): factory()
- `display_name` (str): factory()
- `source_object_type` (str): factory()
- `target_object_type` (str): factory()
- `cardinality` (str): ONE_TO_MANY
- `description` (Optional): None

---

## ActionType

动作类型定义

**说明**: ActionType(api_name: str, display_name: str, target_object_types: List[str], parameters: Dict[str, ontology_framework.core.ActionParameter] = <factory>, logic: Optional[Callable[[ontology_framework.core.ActionContext, Any], NoneType]] = None, backing_function_api_name: Optional[str] = None, description: Optional[str] = None, permissions: Optional[ForwardRef('AccessControlList')] = None, side_effects: List[ontology_framework.core.SideEffect] = <factory>)

**构造函数**:
```python
ActionType(self, api_name: str, display_name: str, target_object_types: List[str], parameters: Dict[str, ontology_framework.core.ActionParameter] = <factory>, logic: Optional[Callable[[ontology_framework.core.ActionContext, Any], NoneType]] = None, backing_function_api_name: Optional[str] = None, description: Optional[str] = None, permissions: Optional[ForwardRef('AccessControlList')] = None, side_effects: List[ontology_framework.core.SideEffect] = <factory>) -> None
```

**类型**: `@dataclass`

**字段**:

- `api_name` (str): factory()
- `display_name` (str): factory()
- `target_object_types` (List): factory()
- `parameters` (Dict): <dataclasses._MISSING_TYPE object at 0x1013efad0>
- `logic` (Optional): None
- `backing_function_api_name` (Optional): None
- `description` (Optional): None
- `permissions` (Optional): None
- `side_effects` (List): <dataclasses._MISSING_TYPE object at 0x1013efad0>

**公共方法**:

### `add_parameter`

```python
add_parameter(self, name: str, type: ontology_framework.core.PropertyType, required: bool = True, description: str = None)
```

---

### `add_side_effect`

```python
add_side_effect(self, side_effect: ontology_framework.core.SideEffect)
```

---

---

## ObjectInstance

对象实例

**说明**: ObjectInstance(object_type_api_name: str, primary_key_value: Any, property_values: Dict[str, Any] = <factory>, _ontology: Optional[ForwardRef('Ontology')] = None)

**构造函数**:
```python
ObjectInstance(self, object_type_api_name: str, primary_key_value: Any, property_values: Dict[str, Any] = <factory>, _ontology: Optional[ForwardRef('Ontology')] = None) -> None
```

**类型**: `@dataclass`

**字段**:

- `object_type_api_name` (str): factory()
- `primary_key_value` (Any): factory()
- `property_values` (Dict): <dataclasses._MISSING_TYPE object at 0x1013efad0>
- `_ontology` (Optional): None

**公共方法**:

### `get`

```python
get(self, property_name: str) -> Any
```

**返回值**: `typing.Any`

---

---

## ObjectSet

对象集合

**构造函数**:
```python
ObjectSet(self, object_type: ontology_framework.core.ObjectType, objects: List[ontology_framework.core.ObjectInstance] = None, ontology: 'Ontology' = None)
```

**公共方法**:

### `add`

```python
add(self, obj: ontology_framework.core.ObjectInstance)
```

---

### `aggregate`

```python
aggregate(self, property_name: str, function: str) -> float
```

**返回值**: `<class 'float'>`

---

### `all`

```python
all(self) -> List[ontology_framework.core.ObjectInstance]
```

**返回值**: `typing.List[ontology_framework.core.ObjectInstance]`

---

### `filter`

```python
filter(self, property_name: str, value: Any) -> 'ObjectSet'
```

**返回值**: `ObjectSet`

---

### `search_around`

```python
search_around(self, link_type_api_name: str, **filters) -> 'ObjectSet'
```

**返回值**: `ObjectSet`

---

---

## PropertyType

属性类型枚举

**构造函数**:
```python
PropertyType(self, *args, **kwds)
```

---

## ObjectSetService

对象集合服务

**构造函数**:
```python
ObjectSetService(self)
```

**公共方法**:

### `get_base_object_set`

```python
get_base_object_set(self, object_type: ontology_framework.core.ObjectType, principal_id: str = None) -> ontology_framework.core.ObjectSet
```

Returns the base ObjectSet for a type, checking permissions.

**返回值**: `<class 'ontology_framework.core.ObjectSet'>`

---

### `index_object`

```python
index_object(self, obj: ontology_framework.core.ObjectInstance)
```

Simulates Object Storage V2 indexing.

---

### `search`

```python
search(self, object_type: ontology_framework.core.ObjectType, query: str) -> ontology_framework.core.ObjectSet
```

Semantic search simulation.

**返回值**: `<class 'ontology_framework.core.ObjectSet'>`

---

---

## ActionService

动作服务

**构造函数**:
```python
ActionService(self, ontology: ontology_framework.core.Ontology)
```

**公共方法**:

### `execute_action`

```python
execute_action(self, action_type_api_name: str, parameters: Dict[str, Any], principal: ontology_framework.permissions.Principal) -> ontology_framework.core.ActionLog
```

**返回值**: `<class 'ontology_framework.core.ActionLog'>`

---

---

## ObjectView

对象视图

**说明**: ObjectView(object_type: ontology_framework.core.ObjectType, title: str, widgets: List[str] = <factory>)

**构造函数**:
```python
ObjectView(self, object_type: ontology_framework.core.ObjectType, title: str, widgets: List[str] = <factory>) -> None
```

**类型**: `@dataclass`

**字段**:

- `object_type` (ObjectType): factory()
- `title` (str): factory()
- `widgets` (List): <dataclasses._MISSING_TYPE object at 0x1013efad0>

**公共方法**:

### `render`

```python
render(self, object_set: ontology_framework.core.ObjectSet)
```

---

---

## ObjectExplorer

对象浏览器

**构造函数**:
```python
ObjectExplorer(self)
```

**公共方法**:

### `open`

```python
open(self, object_type_api_name: str, object_set: ontology_framework.core.ObjectSet)
```

---

### `register_view`

```python
register_view(self, view: ontology_framework.applications.ObjectView)
```

---

---

## Quiver

数据分析工具

**构造函数**:
```python
Quiver(self, /, *args, **kwargs)
```

**公共方法**:

### `analyze`

```python
analyze(self, object_set: ontology_framework.core.ObjectSet)
```

---

---

## AccessControlList

访问控制列表

**说明**: AccessControlList(permissions: dict[str, typing.List[ontology_framework.permissions.PermissionType]] = <factory>)

**构造函数**:
```python
AccessControlList(self, permissions: dict[str, typing.List[ontology_framework.permissions.PermissionType]] = <factory>) -> None
```

**类型**: `@dataclass`

**字段**:

- `permissions` (dict): <dataclasses._MISSING_TYPE object at 0x1013efad0>

**公共方法**:

### `check`

```python
check(self, principal_id: str, permission: ontology_framework.permissions.PermissionType) -> bool
```

**返回值**: `<class 'bool'>`

---

### `grant`

```python
grant(self, principal_id: str, permission: ontology_framework.permissions.PermissionType)
```

---

---

## Principal

主体

**说明**: Principal(id: str, type: str = 'USER', attributes: List[str] = <factory>)

**构造函数**:
```python
Principal(self, id: str, type: str = 'USER', attributes: List[str] = <factory>) -> None
```

**类型**: `@dataclass`

**字段**:

- `id` (str): factory()
- `type` (str): USER
- `attributes` (List): <dataclasses._MISSING_TYPE object at 0x1013efad0>

---

## PermissionType

权限类型

**构造函数**:
```python
PermissionType(self, *args, **kwds)
```

---

## OntologyError

基础异常类

**说明**: 
    本体框架基础异常类

    所有框架特定异常的基类，提供统一的错误信息格式和处理机制
    

**构造函数**:
```python
OntologyError(self, message: str, error_code: Optional[str] = None, category: ontology_framework.exceptions.ErrorCategory = <ErrorCategory.SYSTEM: 'system'>, severity: ontology_framework.exceptions.ErrorSeverity = <ErrorSeverity.MEDIUM: 'medium'>, details: Optional[Dict[str, Any]] = None, cause: Optional[Exception] = None, context: Optional[Dict[str, Any]] = None)
```

**公共方法**:

### `to_dict`

```python
to_dict(self) -> Dict[str, Any]
```

将异常转换为字典格式，便于日志记录和API响应

**返回值**: `typing.Dict[str, typing.Any]`

---

---

## ValidationError

验证错误

**说明**: 数据验证错误

**构造函数**:
```python
ValidationError(self, message: str, field_name: Optional[str] = None, field_value: Any = None, expected_type: Optional[str] = None, **kwargs)
```

**公共方法**:

### `to_dict`

```python
to_dict(self) -> Dict[str, Any]
```

将异常转换为字典格式，便于日志记录和API响应

**返回值**: `typing.Dict[str, typing.Any]`

---

---

## PermissionError

权限错误

**说明**: 权限控制错误

**构造函数**:
```python
PermissionError(self, message: str, principal_id: Optional[str] = None, resource_type: Optional[str] = None, resource_id: Optional[str] = None, required_permission: Optional[str] = None, **kwargs)
```

**公共方法**:

### `to_dict`

```python
to_dict(self) -> Dict[str, Any]
```

将异常转换为字典格式，便于日志记录和API响应

**返回值**: `typing.Dict[str, typing.Any]`

---

---

## OntologyLogger

结构化日志器

**说明**: 本体框架专用日志器

**构造函数**:
```python
OntologyLogger(self, name: str = 'ontology_framework')
```

**公共方法**:

### `critical`

```python
critical(self, message: str, **kwargs)
```

严重错误日志

---

### `debug`

```python
debug(self, message: str, **kwargs)
```

调试日志

---

### `error`

```python
error(self, message: str, **kwargs)
```

错误日志

---

### `exception`

```python
exception(self, message: str, **kwargs)
```

异常日志（自动包含堆栈跟踪）

---

### `info`

```python
info(self, message: str, **kwargs)
```

信息日志

---

### `warning`

```python
warning(self, message: str, **kwargs)
```

警告日志

---

---

## LoggingContext

日志上下文管理

**说明**: 日志上下文管理器，用于设置上下文变量

**构造函数**:
```python
LoggingContext(self, request_id: Optional[str] = None, user_id: Optional[str] = None, operation: Optional[str] = None)
```

---

## RetryMechanism

重试机制

**说明**: 重试机制

**构造函数**:
```python
RetryMechanism(self, config: ontology_framework.error_recovery.RetryConfig)
```

**公共方法**:

### `execute_with_retry`

```python
execute_with_retry(self, func: Callable, *args, **kwargs) -> Any
```

执行函数并在失败时重试

**返回值**: `typing.Any`

---

---

## CircuitBreaker

熔断器

**说明**: 熔断器实现

**构造函数**:
```python
CircuitBreaker(self, config: ontology_framework.error_recovery.CircuitBreakerConfig)
```

**公共方法**:

### `call`

```python
call(self, func: Callable, *args, **kwargs) -> Any
```

通过熔断器调用函数

**返回值**: `typing.Any`

---

---

## DebugSession

调试会话

**说明**: 调试会话管理器

**构造函数**:
```python
DebugSession(self, name: str)
```

**公共方法**:

### `add_debug_info`

```python
add_debug_info(self, debug_info: ontology_framework.debug_tools.DebugInfo)
```

添加调试信息

---

### `export_debug_data`

```python
export_debug_data(self, filename: str = None) -> str
```

导出调试数据

**返回值**: `<class 'str'>`

---

### `get_session_summary`

```python
get_session_summary(self) -> Dict[str, Any]
```

获取会话摘要

**返回值**: `typing.Dict[str, typing.Any]`

---

---

## PerformanceProfiler

性能分析器

**说明**: 性能分析器

**构造函数**:
```python
PerformanceProfiler(self)
```

**公共方法**:

### `get_profile_summary`

```python
get_profile_summary(self, function_name: str = None) -> Dict[str, Any]
```

获取性能分析摘要

**返回值**: `typing.Dict[str, typing.Any]`

---

### `profile_function`

```python
profile_function(self, name: str = None)
```

函数性能分析装饰器

---

---

