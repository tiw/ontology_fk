# Ontology Framework API Reference

This document provides a detailed reference for the public API of the `ontology_framework` library.

## Core Components (`ontology_framework.core`)

### `Ontology`

The main entry point for managing the ontology.

```python
class Ontology()
```

**Methods:**

-   **`register_object_type(object_type: ObjectType)`**
    Registers a new Object Type definition.
    
-   **`register_link_type(link_type: LinkType)`**
    Registers a new Link Type definition.
    
-   **`register_action_type(action_type: ActionType)`**
    Registers a new Action Type definition.
    
-   **`register_function(function: Function)`**
    Registers a Function definition.

-   **`execute_function(function_api_name: str, **kwargs) -> Any`**
    Executes a registered function by its API name. Arguments are passed as keyword arguments.

-   **`get_object_type(api_name: str) -> Optional[ObjectType]`**
    Retrieves a registered Object Type.

-   **`get_link_type(api_name: str) -> Optional[LinkType]`**
    Retrieves a registered Link Type.

-   **`get_action_type(api_name: str) -> Optional[ActionType]`**
    Retrieves a registered Action Type.

---

### `ObjectType`

Defines the schema for an entity in the ontology.

```python
class ObjectType(
    api_name: str,
    display_name: str,
    primary_key: str = "",
    description: Optional[str] = None,
    icon: Optional[str] = "cube"
)
```

**Methods:**

-   **`add_property(name: str, type: PropertyType, description: str = None) -> ObjectType`**
    Adds a property to the object type. Returns `self` for chaining.

-   **`add_derived_property(name: str, type: PropertyType, backing_function_api_name: str, description: str = None) -> ObjectType`**
    Adds a derived property calculated by a function.

---

### `PropertyType`

Enum defining supported data types for properties.

-   `STRING`
-   `INTEGER`
-   `BOOLEAN`
-   `DATE`
-   `TIMESTAMP`

---

### `LinkType`

Defines a relationship between two Object Types.

```python
class LinkType(
    api_name: str,
    display_name: str,
    source_object_type: str,
    target_object_type: str,
    cardinality: str = "ONE_TO_MANY",
    description: Optional[str] = None
)
```

-   **`cardinality`**: Can be `"ONE_TO_ONE"`, `"ONE_TO_MANY"`, or `"MANY_TO_MANY"`.

---

### `ActionType`

Defines a transactional operation that can modify the ontology.

```python
class ActionType(
    api_name: str,
    display_name: str,
    target_object_types: List[str],
    backing_function_api_name: Optional[str] = None,
    description: Optional[str] = None
)
```

**Methods:**

-   **`add_parameter(name: str, type: PropertyType, required: bool = True, description: str = None) -> ActionType`**
    Adds a parameter that must be provided when executing the action.

-   **`add_side_effect(side_effect: SideEffect) -> ActionType`**
    Adds a side effect (e.g., Notification, Webhook) to the action.

---

### `ActionContext`

Passed to functions that perform ontology edits. Allows staging changes that are committed transactionally.

**Methods:**

-   **`create_object(object_type_api_name: str, primary_key: Any, properties: Dict[str, Any])`**
    Stages the creation of a new object.

-   **`modify_object(object_instance: ObjectInstance, property_name: str, value: Any)`**
    Stages a modification to an existing object.

-   **`delete_object(object_instance: ObjectInstance)`**
    Stages the deletion of an object.

-   **`create_link(link_type_api_name: str, source_pk: Any, target_pk: Any)`**
    Stages the creation of a link.

-   **`delete_link(link_type_api_name: str, source_pk: Any, target_pk: Any)`**
    Stages the deletion of a link.

---

### `ObjectSet`

Represents a collection of objects, supporting filtering and traversal.

**Methods:**

-   **`filter(property_name: str, value: Any) -> ObjectSet`**
    Returns a new ObjectSet containing only objects where the property matches the value.

-   **`search_around(link_type_api_name: str) -> ObjectSet`**
    Traverses links to find related objects.

-   **`aggregate(property_name: str, function: str) -> float`**
    Performs an aggregation (`sum`, `avg`, `max`, `min`, `count`) on a property.

-   **`all() -> List[ObjectInstance]`**
    Returns the list of objects in the set.

---

## Functions (`ontology_framework.functions`)

### `@ontology_function`

Decorator to register a Python function as an Ontology Function.

```python
@ontology_function(
    api_name: str,
    display_name: str = None,
    description: str = None,
    inputs: Dict[str, TypeSpec] = None
)
def my_function(...):
    ...
```

**Arguments:**

-   **`api_name`**: Unique identifier for the function.
-   **`inputs`**: Dictionary mapping argument names to their types (e.g., `PrimitiveType`, `ObjectTypeSpec`).

**Example:**

```python
from ontology_framework.functions import ontology_function
from ontology_framework.core import PrimitiveType, PropertyType

@ontology_function(
    api_name="calculate_sum",
    inputs={"a": PrimitiveType(PropertyType.INTEGER), "b": PrimitiveType(PropertyType.INTEGER)}
)
def calculate_sum(a, b):
    return a + b
```
