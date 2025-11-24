from enum import Enum
from typing import Dict, List, Any, Optional, Callable, Type
from dataclasses import dataclass, field
from .permissions import AccessControlList

class PropertyType(Enum):
    STRING = "string"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    DATE = "date"
    TIMESTAMP = "timestamp"
    # Extended types for Function arguments (conceptually)
    # We might need a separate Type system for arguments if they can be Objects/ObjectSets

@dataclass
class TypeSpec:
    """Base class for type specifications."""
    pass

@dataclass
class PrimitiveType(TypeSpec):
    type: PropertyType

@dataclass
class ObjectTypeSpec(TypeSpec):
    object_type_api_name: str

@dataclass
class ObjectSetTypeSpec(TypeSpec):
    object_type_api_name: str


@dataclass
class PropertyDefinition:
    name: str
    type: PropertyType
    description: Optional[str] = None

@dataclass
class DerivedPropertyDefinition:
    name: str
    type: PropertyType
    backing_function_api_name: str
    description: Optional[str] = None


@dataclass
class ObjectType:
    api_name: str
    display_name: str
    properties: Dict[str, PropertyDefinition] = field(default_factory=dict)
    derived_properties: Dict[str, DerivedPropertyDefinition] = field(default_factory=dict)
    primary_key: str = ""

    description: Optional[str] = None
    # New fields for Phase 1 & 4
    backing_datasource_id: Optional[str] = None
    title_property: Optional[str] = None
    icon: Optional[str] = "cube"
    permissions: Optional['AccessControlList'] = None

    def add_property(self, name: str, type: PropertyType, description: Optional[str] = None):
        self.properties[name] = PropertyDefinition(name, type, description)
        return self

    def add_derived_property(self, name: str, type: PropertyType, backing_function_api_name: str, description: Optional[str] = None):
        self.derived_properties[name] = DerivedPropertyDefinition(name, type, backing_function_api_name, description)
        return self


@dataclass
class ObjectInstance:
    object_type_api_name: str
    primary_key_value: Any
    property_values: Dict[str, Any] = field(default_factory=dict)
    _ontology: Optional['Ontology'] = field(default=None, repr=False, compare=False)

    def get(self, property_name: str) -> Any:
        # 1. Check standard properties
        if property_name in self.property_values:
            return self.property_values[property_name]
        
        # 2. Check derived properties if ontology context is available
        if self._ontology:
            obj_type = self._ontology.get_object_type(self.object_type_api_name)
            if obj_type and property_name in obj_type.derived_properties:
                derived_prop = obj_type.derived_properties[property_name]
                # Execute backing function
                # Convention: Pass 'self' as the argument if the function expects an object of this type
                # We need to inspect the function to know the argument name?
                # Or we assume a convention, e.g. the function has one argument of ObjectTypeSpec matching this type.
                
                func_def = self._ontology.functions.get(derived_prop.backing_function_api_name)
                if not func_def:
                    raise ValueError(f"Backing function {derived_prop.backing_function_api_name} not found")
                
                # Find the argument that accepts this object type
                target_arg_name = None
                for arg_name, arg_def in func_def.inputs.items():
                    if isinstance(arg_def.type, ObjectTypeSpec) and arg_def.type.object_type_api_name == self.object_type_api_name:
                        target_arg_name = arg_name
                        break
                
                if not target_arg_name:
                    # Fallback: if there is only one argument and it's an object type (or generic), use it?
                    # Or maybe the function just takes 'object'?
                    # Let's try to pass it as the first argument if it matches?
                    # For safety, let's require explicit match or specific name like 'object' or the type name.
                    pass

                if target_arg_name:
                    return self._ontology.execute_function(derived_prop.backing_function_api_name, **{target_arg_name: self})
                else:
                    # Try passing as 'this' or 'object' if defined
                    if "object" in func_def.inputs:
                         return self._ontology.execute_function(derived_prop.backing_function_api_name, object=self)
                    
                    raise ValueError(f"Could not determine argument to pass object to in function {derived_prop.backing_function_api_name}")

        return None


@dataclass
class Link:
    link_type_api_name: str
    source_primary_key: Any
    target_primary_key: Any

class ObjectSet:
    def __init__(self, object_type: ObjectType, objects: List[ObjectInstance] = None, ontology: 'Ontology' = None):
        self.object_type = object_type
        self._objects = objects or []
        self._filters = []
        self._ontology = ontology

    def add(self, obj: ObjectInstance):
        if obj.object_type_api_name != self.object_type.api_name:
            raise ValueError(f"Object type mismatch: expected {self.object_type.api_name}, got {obj.object_type_api_name}")
        self._objects.append(obj)

    def filter(self, property_name: str, value: Any) -> 'ObjectSet':
        # Simple exact match filter for now
        filtered_objects = [
            obj for obj in self._objects 
            if obj.property_values.get(property_name) == value
        ]
        return ObjectSet(self.object_type, filtered_objects, self._ontology)

    def search_around(self, link_type_api_name: str) -> 'ObjectSet':
        if not self._ontology:
            raise ValueError("Ontology context is required for search_around")
        
        link_type = self._ontology.get_link_type(link_type_api_name)
        if not link_type:
            raise ValueError(f"Link type {link_type_api_name} not found")
        
        # Verify direction and types
        if link_type.source_object_type == self.object_type.api_name:
            target_type_name = link_type.target_object_type
            direction = "forward"
        elif link_type.target_object_type == self.object_type.api_name:
            # Assuming we might want to support reverse traversal if link types are bidirectional or if we check both ends
            # For this implementation, we will stick to the definition: LinkType defines Source -> Target.
            # If we want reverse, we'd need to know if it's supported. 
            # Let's assume strict direction for now as per LinkType definition.
            raise ValueError(f"Object set type {self.object_type.api_name} is not the source of link {link_type_api_name}")
        else:
             raise ValueError(f"Link type {link_type_api_name} does not start from {self.object_type.api_name}")

        target_object_type = self._ontology.get_object_type(target_type_name)
        if not target_object_type:
             raise ValueError(f"Target object type {target_type_name} not found")

        # Collect all source PKs
        source_pks = {obj.primary_key_value for obj in self._objects}
        
        # Find links
        # This is an inefficient O(N*M) scan, but fine for prototype
        related_target_pks = set()
        for link in self._ontology.get_all_links():
            if link.link_type_api_name == link_type_api_name and link.source_primary_key in source_pks:
                related_target_pks.add(link.target_primary_key)
        
        # Fetch target objects
        # In a real system, this would be a DB query. Here we need a way to get objects by PK.
        # We'll add a helper to Ontology to get all objects of a type or specific objects.
        # For now, let's assume Ontology stores objects too or we have a way to get them.
        # Wait, Ontology class currently doesn't store ObjectInstances, only Types.
        # I need to add an Object Store to Ontology or pass it in.
        # Let's add a simple object store to Ontology for this simulation.
        
        target_objects = []
        all_potential_targets = self._ontology.get_objects_of_type(target_type_name)
        for obj in all_potential_targets:
            if obj.primary_key_value in related_target_pks:
                target_objects.append(obj)
                
        return ObjectSet(target_object_type, target_objects, self._ontology)

    def all(self) -> List[ObjectInstance]:
        return self._objects

    def aggregate(self, property_name: str, function: str) -> float:
        values = [
            obj.property_values.get(property_name) 
            for obj in self._objects 
            if obj.property_values.get(property_name) is not None
        ]
        if not values:
            return 0.0
        
        if function == "sum":
            return sum(values)
        elif function == "avg":
            return sum(values) / len(values)
        elif function == "max":
            return max(values)
        elif function == "min":
            return min(values)
        elif function == "count":
            return len(values)
        else:
            raise ValueError(f"Unknown aggregation function: {function}")


@dataclass
class LinkType:
    api_name: str
    display_name: str
    source_object_type: str
    target_object_type: str
    cardinality: str = "ONE_TO_MANY" # ONE_TO_ONE, ONE_TO_MANY, MANY_TO_MANY
    description: Optional[str] = None

@dataclass
class ActionParameter:
    api_name: str
    data_type: PropertyType
    required: bool = True
    description: Optional[str] = None

@dataclass
class ActionLog:
    id: str
    action_type_api_name: str
    user_id: str
    timestamp: float
    parameters: Dict[str, Any]
    changes: List[str] # Summary of changes

class ActionContext:
    def __init__(self, ontology: 'Ontology', principal_id: str):
        self._ontology = ontology
        self._principal_id = principal_id
        self._changes: List[str] = []
        self._object_edits: List[Callable] = [] # List of callables to execute commit

    def get_object(self, object_type_api_name: str, primary_key: Any) -> Optional[ObjectInstance]:
        # In a real transaction, this might lock the object.
        # Here we just fetch it.
        # We need to access the object store from Ontology.
        # Since Ontology._object_store is internal, we might need a public accessor or friend access.
        # For now, we access it directly as we are in the same module (mostly).
        # But ActionContext is in core.py, so it can access Ontology internals if passed an instance.
        
        # However, Ontology doesn't expose _object_store publicly. 
        # We will add a helper in Ontology or just access it if we are careful.
        # Let's assume we can use `ontology.get_objects_of_type` but that returns a list.
        # We need a get_object_by_pk.
        return self._ontology.get_object(object_type_api_name, primary_key)

    def create_object(self, object_type_api_name: str, primary_key: Any, properties: Dict[str, Any]):
        def commit():
            self._ontology.add_object(ObjectInstance(object_type_api_name, primary_key, properties))
        self._object_edits.append(commit)
        self._changes.append(f"Created object {object_type_api_name} with PK {primary_key}")

    def modify_object(self, object_instance: ObjectInstance, property_name: str, value: Any):
        # We need to modify the object in place OR replace it.
        # Since ObjectInstance is a dataclass, it's mutable.
        # But we want to defer execution until commit.
        def commit():
            object_instance.property_values[property_name] = value
        self._object_edits.append(commit)
        self._changes.append(f"Modified object {object_instance.object_type_api_name}:{object_instance.primary_key_value} set {property_name}={value}")

    def delete_object(self, object_instance: ObjectInstance):
        def commit():
            # We need a delete method in Ontology
            self._ontology.delete_object(object_instance.object_type_api_name, object_instance.primary_key_value)
        self._object_edits.append(commit)
        self._changes.append(f"Deleted object {object_instance.object_type_api_name}:{object_instance.primary_key_value}")

    def create_link(self, link_type_api_name: str, source_pk: Any, target_pk: Any):
        def commit():
            self._ontology.create_link(link_type_api_name, source_pk, target_pk, user_permissions=[f"EDIT_LINK_{link_type_api_name}"]) # Mock permission
        self._object_edits.append(commit)
        self._changes.append(f"Created link {link_type_api_name} from {source_pk} to {target_pk}")

    def delete_link(self, link_type_api_name: str, source_pk: Any, target_pk: Any):
        def commit():
            self._ontology.delete_link(link_type_api_name, source_pk, target_pk, user_permissions=[f"EDIT_LINK_{link_type_api_name}"])
        self._object_edits.append(commit)
        self._changes.append(f"Deleted link {link_type_api_name} from {source_pk} to {target_pk}")

    def apply_changes(self):
        for edit in self._object_edits:
            edit()

@dataclass
class SideEffect:
    pass

@dataclass
class Notification(SideEffect):
    recipients: List[str]
    message: str

@dataclass
class Webhook(SideEffect):
    url: str
    method: str = "POST"
    payload_template: Optional[Dict[str, Any]] = None

@dataclass
class ActionType:
    api_name: str
    display_name: str
    target_object_types: List[str]
    parameters: Dict[str, ActionParameter] = field(default_factory=dict)
    logic: Optional[Callable[[ActionContext, Any], None]] = None # Function taking context and kwargs
    backing_function_api_name: Optional[str] = None # Reference to a registered Function
    description: Optional[str] = None
    permissions: Optional['AccessControlList'] = None
    side_effects: List[SideEffect] = field(default_factory=list)

    def add_parameter(self, name: str, type: PropertyType, required: bool = True, description: str = None):
        self.parameters[name] = ActionParameter(name, type, required, description)
        return self

    def add_side_effect(self, side_effect: SideEffect):
        self.side_effects.append(side_effect)
        return self

@dataclass
class FunctionArgument:
    name: str
    type: TypeSpec
    required: bool = True
    description: Optional[str] = None

@dataclass
class Function:
    api_name: str
    display_name: str
    inputs: Dict[str, FunctionArgument] = field(default_factory=dict)
    output_type: Optional[TypeSpec] = None
    logic: Optional[Callable] = None
    description: Optional[str] = None
    
    def add_input(self, name: str, type: TypeSpec, required: bool = True, description: str = None):
        self.inputs[name] = FunctionArgument(name, type, required, description)
        return self

class Ontology:
    def __init__(self):
        self.object_types: Dict[str, ObjectType] = {}
        self.link_types: Dict[str, LinkType] = {}
        self.action_types: Dict[str, ActionType] = {}
        self.functions: Dict[str, Function] = {}
        # Data Store for simulation
        self._object_store: Dict[str, Dict[Any, ObjectInstance]] = {} # type_name -> {pk -> instance}
        self._links: List[Link] = []

    def register_object_type(self, object_type: ObjectType):
        self.object_types[object_type.api_name] = object_type
        self._object_store[object_type.api_name] = {}
        print(f"Registered Object Type: {object_type.api_name}")

    def add_object(self, object_instance: ObjectInstance):
        if object_instance.object_type_api_name not in self.object_types:
             raise ValueError(f"Unknown object type: {object_instance.object_type_api_name}")
        self._object_store[object_instance.object_type_api_name][object_instance.primary_key_value] = object_instance
        object_instance._ontology = self


    def get_object(self, type_name: str, primary_key: Any) -> Optional[ObjectInstance]:
        return self._object_store.get(type_name, {}).get(primary_key)

    def delete_object(self, type_name: str, primary_key: Any):
        if type_name in self._object_store and primary_key in self._object_store[type_name]:
            del self._object_store[type_name][primary_key]

    def get_objects_of_type(self, type_name: str) -> List[ObjectInstance]:
        return list(self._object_store.get(type_name, {}).values())

    def register_link_type(self, link_type: LinkType):
        # Validate existence of object types
        if link_type.source_object_type not in self.object_types:
            raise ValueError(f"Source object type {link_type.source_object_type} not found")
        if link_type.target_object_type not in self.object_types:
            raise ValueError(f"Target object type {link_type.target_object_type} not found")
        
        self.link_types[link_type.api_name] = link_type
        print(f"Registered Link Type: {link_type.api_name}")

    def register_action_type(self, action_type: ActionType):
        for obj_type in action_type.target_object_types:
             if obj_type not in self.object_types:
                raise ValueError(f"Target object type {obj_type} not found")
        self.action_types[action_type.api_name] = action_type
        print(f"Registered Action Type: {action_type.api_name}")

    def register_function(self, function: Function):
        self.functions[function.api_name] = function
        print(f"Registered Function: {function.api_name}")

    def execute_function(self, function_api_name: str, **kwargs) -> Any:
        func_def = self.functions.get(function_api_name)
        if not func_def:
            raise ValueError(f"Function {function_api_name} not found")
        
        if not func_def.logic:
            raise ValueError(f"Function {function_api_name} has no logic implementation")

        # Validate arguments
        for name, arg_def in func_def.inputs.items():
            if arg_def.required and name not in kwargs:
                raise ValueError(f"Missing required argument: {name}")
            
            if name in kwargs:
                val = kwargs[name]
                # Basic type checking could go here
                # For ObjectTypeSpec, verify it's an ObjectInstance of correct type
                if isinstance(arg_def.type, ObjectTypeSpec):
                    if not isinstance(val, ObjectInstance):
                         raise TypeError(f"Argument {name} expected ObjectInstance, got {type(val)}")
                    if val.object_type_api_name != arg_def.type.object_type_api_name:
                         raise TypeError(f"Argument {name} expected object of type {arg_def.type.object_type_api_name}, got {val.object_type_api_name}")
                
                # For ObjectSetTypeSpec, verify it's an ObjectSet
                if isinstance(arg_def.type, ObjectSetTypeSpec):
                    if not isinstance(val, ObjectSet):
                        raise TypeError(f"Argument {name} expected ObjectSet, got {type(val)}")
                    if val.object_type.api_name != arg_def.type.object_type_api_name:
                         raise TypeError(f"Argument {name} expected ObjectSet of type {arg_def.type.object_type_api_name}, got {val.object_type.api_name}")

        return func_def.logic(**kwargs)


    def get_object_type(self, api_name: str) -> Optional[ObjectType]:
        return self.object_types.get(api_name)

    def get_link_type(self, api_name: str) -> Optional[LinkType]:
        return self.link_types.get(api_name)
    
    def get_action_type(self, api_name: str) -> Optional[ActionType]:
        return self.action_types.get(api_name)

    def create_link(self, link_type_api_name: str, source_pk: Any, target_pk: Any, user_permissions: List[str] = None):
        # Permission Check
        # User needs EDIT permission on the LinkType AND both ObjectTypes (simplified)
        # For now, let's assume if user_permissions is provided, we check against required permissions.
        # If user_permissions is None, we assume system/admin (or no auth implemented yet).
        
        # Real implementation would check ACLs on the types.
        # Let's mock a simple check: "EDIT_LINK_{LINK_TYPE}"
        if user_permissions is not None:
            required_perm = f"EDIT_LINK_{link_type_api_name}"
            if required_perm not in user_permissions:
                raise PermissionError(f"Missing permission: {required_perm}")

        link_type = self.get_link_type(link_type_api_name)
        if not link_type:
            raise ValueError(f"Link type {link_type_api_name} not found")
            
        # Validate objects exist
        source_objs = self._object_store.get(link_type.source_object_type, {})
        if source_pk not in source_objs:
             raise ValueError(f"Source object {source_pk} not found")
             
        target_objs = self._object_store.get(link_type.target_object_type, {})
        if target_pk not in target_objs:
             raise ValueError(f"Target object {target_pk} not found")

        # Check cardinality (simplified, just check duplicates for now)
        # If ONE_TO_MANY, source can have multiple links? No, Source -> Target. 
        # Usually ONE_TO_MANY means One Source has Many Targets.
        # So we don't strictly enforce uniqueness on Source unless it's ONE_TO_ONE.
        
        # Check if link already exists
        for link in self._links:
            if (link.link_type_api_name == link_type_api_name and 
                link.source_primary_key == source_pk and 
                link.target_primary_key == target_pk):
                return # Already exists
        
        self._links.append(Link(link_type_api_name, source_pk, target_pk))

    def delete_link(self, link_type_api_name: str, source_pk: Any, target_pk: Any, user_permissions: List[str] = None):
         if user_permissions is not None:
            required_perm = f"EDIT_LINK_{link_type_api_name}"
            if required_perm not in user_permissions:
                raise PermissionError(f"Missing permission: {required_perm}")
        
         self._links = [
             l for l in self._links 
             if not (l.link_type_api_name == link_type_api_name and 
                     l.source_primary_key == source_pk and 
                     l.target_primary_key == target_pk)
         ]

    def get_all_links(self) -> List[Link]:
        return self._links
