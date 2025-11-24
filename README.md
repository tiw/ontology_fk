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
