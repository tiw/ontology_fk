from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Type, Protocol
import uuid

from .permissions import AccessControlList
from .datasources import DataSourceAdapter, InMemoryDataSource, DataSourceError


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
    """
    A derived property is a property that is calculated by a function.
    """

    name: str
    type: PropertyType
    backing_function_api_name: str
    description: Optional[str] = None


@dataclass
class ObjectType:
    api_name: str
    display_name: str
    properties: Dict[str, PropertyDefinition] = field(default_factory=dict)
    derived_properties: Dict[str, DerivedPropertyDefinition] = field(
        default_factory=dict
    )
    primary_key: str = ""

    description: Optional[str] = None
    # New fields for Phase 1 & 4
    backing_datasource_id: Optional[str] = None
    title_property: Optional[str] = None
    icon: Optional[str] = "cube"
    permissions: Optional["AccessControlList"] = None

    def __post_init__(self):
        # 兼容 tests 中以位置参数传主键的写法（即第三个参数是 primary_key）
        if isinstance(self.properties, str) and not self.primary_key:
            self.primary_key = self.properties
            self.properties = {}

    def add_property(
        self, name: str, type: PropertyType, description: Optional[str] = None
    ):
        self.properties[name] = PropertyDefinition(name, type, description)
        return self

    def add_derived_property(
        self,
        name: str,
        type: PropertyType,
        backing_function_api_name: str,
        description: Optional[str] = None,
    ):
        self.derived_properties[name] = DerivedPropertyDefinition(
            name, type, backing_function_api_name, description
        )
        return self


@dataclass
class ObjectInstance:
    object_type_api_name: str
    primary_key_value: Any
    property_values: Dict[str, Any] = field(default_factory=dict)
    _ontology: Optional["Ontology"] = field(default=None, repr=False, compare=False)
    runtime_metadata: Dict[str, Any] = field(default_factory=dict, repr=False, compare=False)

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

                func_def = self._ontology.functions.get(
                    derived_prop.backing_function_api_name
                )
                if not func_def:
                    raise ValueError(
                        f"Backing function {derived_prop.backing_function_api_name} not found"
                    )

                # Find the argument that accepts this object type
                target_arg_name = None
                for arg_name, arg_def in func_def.inputs.items():
                    if (
                        isinstance(arg_def.type, ObjectTypeSpec)
                        and arg_def.type.object_type_api_name
                        == self.object_type_api_name
                    ):
                        target_arg_name = arg_name
                        break

                if not target_arg_name:
                    # Fallback: if there is only one argument and it's an object type (or generic), use it?
                    # Or maybe the function just takes 'object'?
                    # Let's try to pass it as the first argument if it matches?
                    # For safety, let's require explicit match or specific name like 'object' or the type name.
                    pass

                if target_arg_name:
                    return self._ontology.execute_function(
                        derived_prop.backing_function_api_name,
                        **{target_arg_name: self},
                    )
                else:
                    # Try passing as 'this' or 'object' if defined
                    if "object" in func_def.inputs:
                        return self._ontology.execute_function(
                            derived_prop.backing_function_api_name, object=self
                        )

                    raise ValueError(
                        f"Could not determine argument to pass object to in function {derived_prop.backing_function_api_name}"
                    )

        return None

    def annotate(self, key: str, value: Any) -> None:
        """Write lightweight runtime metadata (e.g. scores, validation traces)."""
        self.runtime_metadata[key] = value

    def get_annotation(self, key: str, default: Any = None) -> Any:
        """Read runtime metadata that does not belong to schema properties."""
        return self.runtime_metadata.get(key, default)


@dataclass
class Link:
    link_type_api_name: str
    source_primary_key: Any
    target_primary_key: Any


class LinkStore(Protocol):
    """抽象链接存储，便于替换为外部介质。"""

    def list_links(self, link_type_api_name: Optional[str] = None) -> List[Link]:
        ...

    def add_link(self, link: Link) -> None:
        ...

    def delete_link(self, link_type_api_name: str, source_pk: Any, target_pk: Any) -> None:
        ...


class InMemoryLinkStore:
    """默认的内存链接存储实现。"""

    def __init__(self):
        self._links: List[Link] = []

    def list_links(self, link_type_api_name: Optional[str] = None) -> List[Link]:
        if not link_type_api_name:
            return list(self._links)
        return [link for link in self._links if link.link_type_api_name == link_type_api_name]

    def add_link(self, link: Link) -> None:
        self._links.append(link)

    def delete_link(self, link_type_api_name: str, source_pk: Any, target_pk: Any) -> None:
        self._links = [
            l
            for l in self._links
            if not (
                l.link_type_api_name == link_type_api_name
                and l.source_primary_key == source_pk
                and l.target_primary_key == target_pk
            )
        ]


class ObjectSet:
    def __init__(
        self,
        object_type: ObjectType,
        objects: List[ObjectInstance] = None,
        ontology: "Ontology" = None,
        filters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
        lazy: bool = False,
    ):
        self.object_type = object_type
        self._objects = list(objects) if objects else []
        self._ontology = ontology
        self._lazy = lazy
        self._query_filters = dict(filters or {}) if lazy else {}
        self._lazy_limit = limit if lazy else None

    def add(self, obj: ObjectInstance):
        if obj.object_type_api_name != self.object_type.api_name:
            raise ValueError(
                f"Object type mismatch: expected {self.object_type.api_name}, got {obj.object_type_api_name}"
            )
        self._objects.append(obj)

    @property
    def ontology(self) -> Optional["Ontology"]:
        """Expose the bound Ontology so upper layers can drive pivot/graph logic."""
        return self._ontology

    def filter(self, property_name: str, value: Any) -> "ObjectSet":
        if self._lazy and self._ontology:
            merged_filters = dict(self._query_filters)
            merged_filters[property_name] = value
            return ObjectSet(
                self.object_type,
                objects=None,
                ontology=self._ontology,
                filters=merged_filters,
                limit=self._lazy_limit,
                lazy=True,
            )

        filtered_objects = [
            obj for obj in self.all() if obj.property_values.get(property_name) == value
        ]
        return ObjectSet(self.object_type, filtered_objects, self._ontology)

    def search_around(
        self, link_type_api_name: str, limit: Optional[int] = None, **filters
    ) -> "ObjectSet":
        if not self._ontology:
            raise ValueError("Ontology context is required for search_around")

        link_type = self._ontology.get_link_type(link_type_api_name)
        if not link_type:
            raise ValueError(f"Link type {link_type_api_name} not found")

        # Determine direction
        direction = None
        target_type_name = None

        if link_type.source_object_type == self.object_type.api_name:
            direction = "forward"
            target_type_name = link_type.target_object_type
        elif link_type.target_object_type == self.object_type.api_name:
            direction = "reverse"
            target_type_name = link_type.source_object_type
        else:
            raise ValueError(
                f"Link type {link_type_api_name} does not connect to {self.object_type.api_name}"
            )

        target_object_type = self._ontology.get_object_type(target_type_name)
        if not target_object_type:
            raise ValueError(f"Target object type {target_type_name} not found")

        if limit is not None and limit <= 0:
            return ObjectSet(target_object_type, [], self._ontology)

        current_obj_map = {obj.primary_key_value: obj for obj in self.all()}
        target_objects: List[ObjectInstance] = []
        seen_target_pks: Set[Any] = set()

        for link in self._ontology.get_all_links():
            if link.link_type_api_name != link_type_api_name:
                continue

            source_obj: Optional[ObjectInstance] = None
            target_obj: Optional[ObjectInstance] = None

            if direction == "forward" and link.source_primary_key in current_obj_map:
                source_obj = current_obj_map[link.source_primary_key]
                target_obj = self._ontology.get_object(
                    link_type.target_object_type, link.target_primary_key
                )
            elif direction == "reverse" and link.target_primary_key in current_obj_map:
                source_obj = self._ontology.get_object(
                    link_type.source_object_type, link.source_primary_key
                )
                target_obj = current_obj_map[link.target_primary_key]

            if not source_obj or not target_obj:
                continue

            if not self._passes_link_validations(link_type, source_obj, target_obj):
                continue

            if not self._matches_filters(target_obj, filters):
                continue

            self._attach_link_scores(link_type, source_obj, target_obj)

            if target_obj.primary_key_value in seen_target_pks:
                continue

            target_objects.append(target_obj)
            seen_target_pks.add(target_obj.primary_key_value)

            if limit is not None and len(target_objects) >= limit:
                break

        return ObjectSet(target_object_type, target_objects, self._ontology)

    @staticmethod
    def _matches_filters(obj: ObjectInstance, filters: Dict[str, Any]) -> bool:
        if not filters:
            return True
        for prop, val in filters.items():
            if obj.get(prop) != val:
                return False
        return True

    def _passes_link_validations(
        self, link_type: "LinkType", source_obj: ObjectInstance, target_obj: ObjectInstance
    ) -> bool:
        if not link_type.validation_functions:
            return True
        for fn_name in link_type.validation_functions:
            result = self._execute_link_function(
                fn_name, link_type, source_obj, target_obj
            )
            if isinstance(result, dict):
                valid = result.get("valid", True)
            else:
                valid = bool(result)
            if not valid:
                return False
        return True

    def _attach_link_scores(
        self, link_type: "LinkType", source_obj: ObjectInstance, target_obj: ObjectInstance
    ) -> None:
        if not link_type.scoring_function_api_name:
            return
        score = self._execute_link_function(
            link_type.scoring_function_api_name, link_type, source_obj, target_obj
        )
        scores = target_obj.get_annotation("function_scores", {})
        scores[link_type.api_name] = score
        target_obj.annotate("function_scores", scores)

    def _execute_link_function(
        self,
        function_api_name: str,
        link_type: "LinkType",
        source_obj: ObjectInstance,
        target_obj: ObjectInstance,
    ) -> Any:
        func_def = self._ontology.get_function(function_api_name)
        if not func_def:
            raise ValueError(f"Function {function_api_name} not found")

        prepared_args: Dict[str, Any] = {}
        for arg_name, arg_def in func_def.inputs.items():
            value = self._auto_fill_link_argument(
                arg_name, arg_def.type, link_type, source_obj, target_obj
            )
            if value is None:
                if arg_def.required:
                    raise ValueError(
                        f"Unable to auto-fill required argument '{arg_name}' "
                        f"for function {function_api_name}"
                    )
                continue
            prepared_args[arg_name] = value

        return self._ontology.execute_function(function_api_name, **prepared_args)

    @staticmethod
    def _auto_fill_link_argument(
        arg_name: str,
        type_spec: TypeSpec,
        link_type: "LinkType",
        source_obj: ObjectInstance,
        target_obj: ObjectInstance,
    ) -> Any:
        normalized_name = arg_name.lower()
        if normalized_name in {"source", "source_object"}:
            return source_obj
        if normalized_name in {"target", "target_object"}:
            return target_obj

        if isinstance(type_spec, ObjectTypeSpec):
            if type_spec.object_type_api_name == source_obj.object_type_api_name:
                return source_obj
            if type_spec.object_type_api_name == target_obj.object_type_api_name:
                return target_obj

        if isinstance(type_spec, PrimitiveType):
            if normalized_name in {"link_type", "link_type_api_name"}:
                return link_type.api_name

        # Optional arguments are allowed to return None
        return None

    def all(self) -> List[ObjectInstance]:
        if self._lazy and self._ontology:
            self._objects = self._ontology.scan_objects(
                self.object_type.api_name, self._query_filters, self._lazy_limit
            )
            self._lazy = False
            self._query_filters = {}
            self._lazy_limit = None
        return self._objects

    def aggregate(self, property_name: str, function: str) -> float:
        values = [
            obj.property_values.get(property_name)
            for obj in self.all()
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
    cardinality: str = "ONE_TO_MANY"  # ONE_TO_ONE, ONE_TO_MANY, MANY_TO_MANY
    description: Optional[str] = None
    validation_functions: List[str] = field(default_factory=list)
    scoring_function_api_name: Optional[str] = None


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
    changes: List[str]  # Summary of changes


class ActionContext:
    def __init__(self, ontology: "Ontology", principal_id: str):
        self._ontology = ontology
        self._principal_id = principal_id
        self._changes: List[str] = []
        self._object_edits: List[Callable] = []  # List of callables to execute commit

    def get_object(
        self, object_type_api_name: str, primary_key: Any
    ) -> Optional[ObjectInstance]:
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

    def create_object(
        self,
        object_type_api_name: str,
        primary_key_or_properties: Any,
        properties: Optional[Dict[str, Any]] = None,
    ):
        if properties is None:
            resolved_properties = dict(primary_key_or_properties)
            obj_type = self._ontology.get_object_type(object_type_api_name)
            if obj_type is None:
                obj_type = (
                    ObjectType(
                        api_name=object_type_api_name,
                        display_name=object_type_api_name,
                        primary_key="id",
                    ).add_property("id", PropertyType.STRING)
                )
                self._ontology.register_object_type(obj_type)
            pk_field = obj_type.primary_key if obj_type else None
            candidate_keys = [
                resolved_properties.get(pk_field) if pk_field else None,
                resolved_properties.get("id"),
                resolved_properties.get("primary_key"),
            ]
            primary_key = next((pk for pk in candidate_keys if pk is not None), None)
            if primary_key is None:
                primary_key = f"ctx_{uuid.uuid4()}"
            if pk_field and pk_field not in resolved_properties:
                resolved_properties[pk_field] = primary_key
            resolved_properties.setdefault("id", primary_key)
        else:
            primary_key = primary_key_or_properties
            resolved_properties = dict(properties)

        def commit():
            self._ontology.add_object(
                ObjectInstance(object_type_api_name, primary_key, resolved_properties)
            )

        self._object_edits.append(commit)
        self._changes.append(
            f"Created object {object_type_api_name} with PK {primary_key}"
        )

    def modify_object(
        self, object_instance: ObjectInstance, property_name: str, value: Any
    ):
        self._ontology.ensure_object_type_writable(object_instance.object_type_api_name)

        # We need to modify the object in place OR replace it.
        # Since ObjectInstance is a dataclass, it's mutable.
        # But we want to defer execution until commit.
        def commit():
            object_instance.property_values[property_name] = value

        self._object_edits.append(commit)
        self._changes.append(
            f"Modified object {object_instance.object_type_api_name}:{object_instance.primary_key_value} set {property_name}={value}"
        )

    def delete_object(self, object_instance: ObjectInstance):
        def commit():
            # We need a delete method in Ontology
            self._ontology.delete_object(
                object_instance.object_type_api_name, object_instance.primary_key_value
            )

        self._object_edits.append(commit)
        self._changes.append(
            f"Deleted object {object_instance.object_type_api_name}:{object_instance.primary_key_value}"
        )

    def create_link(self, link_type_api_name: str, source_pk: Any, target_pk: Any):
        def commit():
            self._ontology.create_link(
                link_type_api_name,
                source_pk,
                target_pk,
                user_permissions=[f"EDIT_LINK_{link_type_api_name}"],
            )  # Mock permission

        self._object_edits.append(commit)
        self._changes.append(
            f"Created link {link_type_api_name} from {source_pk} to {target_pk}"
        )

    def delete_link(self, link_type_api_name: str, source_pk: Any, target_pk: Any):
        def commit():
            self._ontology.delete_link(
                link_type_api_name,
                source_pk,
                target_pk,
                user_permissions=[f"EDIT_LINK_{link_type_api_name}"],
            )

        self._object_edits.append(commit)
        self._changes.append(
            f"Deleted link {link_type_api_name} from {source_pk} to {target_pk}"
        )

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
    logic: Optional[Callable[[ActionContext, Any], None]] = (
        None  # Function taking context and kwargs
    )
    backing_function_api_name: Optional[str] = (
        None  # Reference to a registered Function
    )
    description: Optional[str] = None
    permissions: Optional["AccessControlList"] = None
    side_effects: List[SideEffect] = field(default_factory=list)

    def add_parameter(
        self,
        name: str,
        type: PropertyType,
        required: bool = True,
        description: str = None,
    ):
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

    def add_input(
        self, name: str, type: TypeSpec, required: bool = True, description: str = None
    ):
        self.inputs[name] = FunctionArgument(name, type, required, description)
        return self


class Ontology:
    def __init__(self):
        self.object_types: Dict[str, ObjectType] = {}
        self.link_types: Dict[str, LinkType] = {}
        self.action_types: Dict[str, ActionType] = {}
        self.functions: Dict[str, Function] = {}
        # Data Store for simulation
        self._object_store: Dict[str, Dict[Any, ObjectInstance]] = (
            {}
        )  # type_name -> {pk -> instance}
        self._link_store: LinkStore = InMemoryLinkStore()
        self._datasources: Dict[str, DataSourceAdapter] = {}
        self._default_datasource_id = "__memory__"
        self._memory_datasource = InMemoryDataSource(
            self._object_store, adapter_id=self._default_datasource_id
        )
        self.register_datasource(self._memory_datasource)

    def register_datasource(self, adapter: DataSourceAdapter):
        self._datasources[adapter.id] = adapter

    def set_link_store(self, link_store: LinkStore):
        self._link_store = link_store

    def get_datasource(self, adapter_id: str) -> DataSourceAdapter:
        if adapter_id not in self._datasources:
            raise ValueError(f"Datasource {adapter_id} not registered")
        return self._datasources[adapter_id]

    def _get_datasource_for_type(self, object_type: ObjectType) -> DataSourceAdapter:
        datasource_id = object_type.backing_datasource_id or self._default_datasource_id
        if datasource_id not in self._datasources:
            raise ValueError(
                f"Datasource {datasource_id} not available for {object_type.api_name}"
            )
        return self._datasources[datasource_id]

    def _attach_context(self, obj: Optional[ObjectInstance]) -> Optional[ObjectInstance]:
        if obj:
            obj._ontology = self
        return obj

    def _attach_context_many(self, objects: List[ObjectInstance]) -> List[ObjectInstance]:
        for obj in objects:
            obj._ontology = self
        return objects

    def is_type_read_only(self, object_type_api_name: str) -> bool:
        obj_type = self.object_types.get(object_type_api_name)
        if not obj_type:
            return True
        datasource = self._get_datasource_for_type(obj_type)
        return datasource.read_only

    def ensure_object_type_writable(self, object_type_api_name: str):
        obj_type = self.object_types.get(object_type_api_name)
        if not obj_type:
            raise ValueError(f"Unknown object type: {object_type_api_name}")
        self._ensure_writable(obj_type)

    def _ensure_writable(self, object_type: ObjectType):
        datasource = self._get_datasource_for_type(object_type)
        if datasource.read_only:
            raise DataSourceError(
                f"Datasource '{datasource.id}' backing '{object_type.api_name}' is read-only"
            )

    def register_object_type(self, object_type: ObjectType):
        if not object_type.backing_datasource_id:
            object_type.backing_datasource_id = self._default_datasource_id
        self.object_types[object_type.api_name] = object_type
        self._object_store.setdefault(object_type.api_name, {})
        print(f"Registered Object Type: {object_type.api_name}")

    def add_object(self, object_instance: ObjectInstance):
        obj_type = self.object_types.get(object_instance.object_type_api_name)
        if not obj_type:
            raise ValueError(
                f"Unknown object type: {object_instance.object_type_api_name}"
            )
        self._ensure_writable(obj_type)
        datasource = self._get_datasource_for_type(obj_type)
        datasource.upsert(obj_type, object_instance)
        object_instance._ontology = self

    def get_object(self, type_name: str, primary_key: Any) -> Optional[ObjectInstance]:
        obj_type = self.object_types.get(type_name)
        if not obj_type:
            return None
        datasource = self._get_datasource_for_type(obj_type)
        obj = datasource.fetch_object(obj_type, primary_key)
        return self._attach_context(obj)

    def delete_object(self, type_name: str, primary_key: Any):
        obj_type = self.object_types.get(type_name)
        if not obj_type:
            return
        self._ensure_writable(obj_type)
        datasource = self._get_datasource_for_type(obj_type)
        datasource.delete(obj_type, primary_key)

    def scan_objects(
        self,
        object_type_api_name: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
    ) -> List[ObjectInstance]:
        obj_type = self.object_types.get(object_type_api_name)
        if not obj_type:
            return []
        datasource = self._get_datasource_for_type(obj_type)
        objects = list(datasource.scan(obj_type, filters=filters, limit=limit))
        return self._attach_context_many(objects)

    def get_objects_of_type(self, type_name: str) -> List[ObjectInstance]:
        return self.scan_objects(type_name)

    def build_object_set(
        self,
        object_type_api_name: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
        lazy: bool = True,
    ) -> ObjectSet:
        obj_type = self.object_types.get(object_type_api_name)
        if not obj_type:
            raise ValueError(f"Unknown object type: {object_type_api_name}")
        if not lazy:
            objects = self.scan_objects(object_type_api_name, filters=filters, limit=limit)
            return ObjectSet(obj_type, objects, self)
        return ObjectSet(
            obj_type,
            objects=None,
            ontology=self,
            filters=filters,
            limit=limit,
            lazy=True,
        )

    def register_link_type(self, link_type: LinkType):
        # Validate existence of object types
        if link_type.source_object_type not in self.object_types:
            raise ValueError(
                f"Source object type {link_type.source_object_type} not found"
            )
        if link_type.target_object_type not in self.object_types:
            raise ValueError(
                f"Target object type {link_type.target_object_type} not found"
            )

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
            raise ValueError(
                f"Function {function_api_name} has no logic implementation"
            )

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
                        raise TypeError(
                            f"Argument {name} expected ObjectInstance, got {type(val)}"
                        )
                    if val.object_type_api_name != arg_def.type.object_type_api_name:
                        raise TypeError(
                            f"Argument {name} expected object of type {arg_def.type.object_type_api_name}, got {val.object_type_api_name}"
                        )

                # For ObjectSetTypeSpec, verify it's an ObjectSet
                if isinstance(arg_def.type, ObjectSetTypeSpec):
                    if not isinstance(val, ObjectSet):
                        raise TypeError(
                            f"Argument {name} expected ObjectSet, got {type(val)}"
                        )
                    if val.object_type.api_name != arg_def.type.object_type_api_name:
                        raise TypeError(
                            f"Argument {name} expected ObjectSet of type {arg_def.type.object_type_api_name}, got {val.object_type.api_name}"
                        )

        return func_def.logic(**kwargs)

    def get_object_type(self, api_name: str) -> Optional[ObjectType]:
        return self.object_types.get(api_name)

    def get_link_type(self, api_name: str) -> Optional[LinkType]:
        return self.link_types.get(api_name)

    def get_action_type(self, api_name: str) -> Optional[ActionType]:
        return self.action_types.get(api_name)

    def get_function(self, api_name: str) -> Optional[Function]:
        return self.functions.get(api_name)

    def create_link(
        self,
        link_type_api_name: str,
        source_pk: Any,
        target_pk: Any,
        user_permissions: List[str] = None,
    ):
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
        if not self.get_object(link_type.source_object_type, source_pk):
            raise ValueError(f"Source object {source_pk} not found")

        if not self.get_object(link_type.target_object_type, target_pk):
            raise ValueError(f"Target object {target_pk} not found")

        # Check cardinality (simplified, just check duplicates for now)
        # If ONE_TO_MANY, source can have multiple links? No, Source -> Target.
        # Usually ONE_TO_MANY means One Source has Many Targets.
        # So we don't strictly enforce uniqueness on Source unless it's ONE_TO_ONE.

        # Check if link already exists
        for link in self._link_store.list_links(link_type_api_name):
            if (
                link.link_type_api_name == link_type_api_name
                and link.source_primary_key == source_pk
                and link.target_primary_key == target_pk
            ):
                return  # Already exists

        self._link_store.add_link(Link(link_type_api_name, source_pk, target_pk))

    def delete_link(
        self,
        link_type_api_name: str,
        source_pk: Any,
        target_pk: Any,
        user_permissions: List[str] = None,
    ):
        if user_permissions is not None:
            required_perm = f"EDIT_LINK_{link_type_api_name}"
            if required_perm not in user_permissions:
                raise PermissionError(f"Missing permission: {required_perm}")

        self._link_store.delete_link(link_type_api_name, source_pk, target_pk)

    def get_all_links(self) -> List[Link]:
        return self._link_store.list_links()

    def get_link_types_for_object(self, object_type_api_name: str) -> List[LinkType]:
        """Return every LinkType touching the given object type (any direction)."""
        return [
            link_type
            for link_type in self.link_types.values()
            if link_type.source_object_type == object_type_api_name
            or link_type.target_object_type == object_type_api_name
        ]

    def export_schema_for_llm(self) -> Dict[str, Any]:
        """Exports the ontology schema in a format suitable for LLM prompts."""

        def _render_type_spec(type_spec: Optional[TypeSpec]) -> str:
            if isinstance(type_spec, PrimitiveType):
                return type_spec.type.value
            if isinstance(type_spec, ObjectTypeSpec):
                return f"object:{type_spec.object_type_api_name}"
            if isinstance(type_spec, ObjectSetTypeSpec):
                return f"object_set:{type_spec.object_type_api_name}"
            return "unknown"

        schema = {"object_types": [], "link_types": [], "action_types": [], "functions": []}

        for ot in self.object_types.values():
            obj_def = {
                "api_name": ot.api_name,
                "display_name": ot.display_name,
                "description": ot.description,
                "primary_key": ot.primary_key,
                "properties": [
                    {"name": p.name, "type": p.type.value, "description": p.description}
                    for p in ot.properties.values()
                ],
                "derived_properties": [
                    {"name": p.name, "type": p.type.value, "description": p.description}
                    for p in ot.derived_properties.values()
                ],
            }
            schema["object_types"].append(obj_def)

        for lt in self.link_types.values():
            link_def = {
                "api_name": lt.api_name,
                "display_name": lt.display_name,
                "source": lt.source_object_type,
                "target": lt.target_object_type,
                "cardinality": lt.cardinality,
                "description": lt.description,
                "validation_functions": list(lt.validation_functions),
                "scoring_function": lt.scoring_function_api_name,
            }
            schema["link_types"].append(link_def)

        for at in self.action_types.values():
            action_def = {
                "api_name": at.api_name,
                "display_name": at.display_name,
                "description": at.description,
                "targets": at.target_object_types,
                "parameters": [
                    {
                        "name": p.api_name,
                        "type": p.data_type.value,
                        "required": p.required,
                        "description": p.description,
                    }
                    for p in at.parameters.values()
                ],
            }
            schema["action_types"].append(action_def)

        for fn in self.functions.values():
            func_def = {
                "api_name": fn.api_name,
                "display_name": fn.display_name,
                "description": fn.description,
                "inputs": [
                    {
                        "name": arg.name,
                        "type": _render_type_spec(arg.type),
                        "required": arg.required,
                        "description": arg.description,
                    }
                    for arg in fn.inputs.values()
                ],
            }
            schema["functions"].append(func_def)

        return schema
