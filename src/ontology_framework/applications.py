from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .core import ObjectInstance, ObjectSet, ObjectType, Ontology


def _object_snapshot(
    obj: ObjectInstance, properties: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Convert an ObjectInstance into a lightweight dict for agent consumption."""
    if properties:
        props = {prop: obj.get(prop) for prop in properties}
    else:
        props = dict(obj.property_values)
        if obj._ontology:
            obj_type = obj._ontology.get_object_type(obj.object_type_api_name)
            if obj_type:
                for derived_name in obj_type.derived_properties.keys():
                    props[derived_name] = obj.get(derived_name)

    snapshot = {"primary_key": obj.primary_key_value, "properties": props}
    if obj.runtime_metadata:
        snapshot["annotations"] = dict(obj.runtime_metadata)
    return snapshot


@dataclass
class PivotAggregationPlan:
    """
    Declare how ObjectExplorer should pivot along a link and which metrics to surface.
    """

    link_type_api_name: str
    metrics: Dict[str, str] = field(default_factory=dict)
    properties: Optional[List[str]] = None
    limit: int = 20


@dataclass
class VertexSimulation:
    """Metadata for simulations that Vertex can run and optionally bind back."""

    name: str
    runner: Callable[..., Dict[str, Any]]
    description: Optional[str] = None
    binding_handler: Optional[
        Callable[[Ontology, Dict[str, Any], Dict[str, Any]], None]
    ] = None


@dataclass
class ObjectView:
    object_type: ObjectType
    title: str
    widgets: List[str] = field(default_factory=list)

    def schema(self) -> Dict[str, Any]:
        """Structured description shared across applications."""
        return {
            "object_type": self.object_type.api_name,
            "title": self.title,
            "widgets": list(self.widgets),
            "properties": list(self.object_type.properties.keys()),
            "derived_properties": list(self.object_type.derived_properties.keys()),
        }

    def render(self, object_set: ObjectSet):
        print(f"--- Object View: {self.title} ---")
        print(f"Object Type: {self.object_type.display_name}")
        print(f"Total Objects: {len(object_set.all())}")
        print("Widgets:")
        for widget in self.widgets:
            print(f" - [Widget] {widget}")
        print("-------------------------------")


class ObjectExplorer:
    def __init__(self):
        self.views: Dict[str, ObjectView] = {}

    def register_view(self, view: ObjectView):
        self.views[view.object_type.api_name] = view

    def describe_view(
        self, object_type: Optional[ObjectType] = None, object_set: Optional[ObjectSet] = None
    ) -> Dict[str, Any]:
        target_type = object_type or (object_set.object_type if object_set else None)
        if not target_type:
            raise ValueError("Either object_type or object_set must be provided")

        if target_type.api_name in self.views:
            return self.views[target_type.api_name].schema()

        return self._build_default_view(target_type).schema()

    def _build_default_view(self, object_type: ObjectType) -> ObjectView:
        widgets = ["standard_table", "property_cards", "link_overview"]
        return ObjectView(
            object_type=object_type,
            title=f"{object_type.display_name} (Normalized View)",
            widgets=widgets,
        )

    def open(self, object_type_api_name: str, object_set: ObjectSet):
        if object_type_api_name in self.views:
            self.views[object_type_api_name].render(object_set)
        else:
            print(
                f"No custom view for {object_type_api_name}, using normalized Object View."
            )
            self._build_default_view(object_set.object_type).render(object_set)

    def pivot_context(
        self,
        object_set: ObjectSet,
        plans: List[PivotAggregationPlan],
        include_root_properties: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        if not object_set.ontology:
            raise ValueError("ObjectSet must carry an ontology for pivoting")

        ontology = object_set.ontology
        context_bundle = {
            "root": {
                "object_type": object_set.object_type.api_name,
                "count": len(object_set.all()),
                "objects": [
                    _object_snapshot(obj, include_root_properties) for obj in object_set.all()
                ],
            },
            "pivots": [],
        }

        for plan in plans:
            link_type = ontology.get_link_type(plan.link_type_api_name)
            if not link_type:
                raise ValueError(f"Unknown link type: {plan.link_type_api_name}")

            related_set = object_set.search_around(plan.link_type_api_name, limit=plan.limit)
            metrics = {
                prop: related_set.aggregate(prop, agg)
                for prop, agg in plan.metrics.items()
            }
            pivot_payload = {
                "link_type": {
                    "api_name": link_type.api_name,
                    "display_name": link_type.display_name,
                    "source": link_type.source_object_type,
                    "target": link_type.target_object_type,
                },
                "target_object_type": related_set.object_type.api_name,
                "objects": [
                    _object_snapshot(obj, plan.properties) for obj in related_set.all()
                ],
                "metrics": metrics,
            }
            context_bundle["pivots"].append(pivot_payload)

        return context_bundle


class Quiver:
    def analyze(self, object_set: ObjectSet):
        print("--- Quiver Analysis ---")
        print(
            f"Analyzing {len(object_set.all())} objects of type {object_set.object_type.api_name}"
        )
        # Mock analysis
        print("Generating charts... [Done]")
        print("-----------------------")


class Vertex:
    """Graph & simulation helper mirroring the Vertex app semantics."""

    def __init__(self, ontology: Ontology):
        self._ontology = ontology
        self._simulations: Dict[str, VertexSimulation] = {}

    def register_simulation(self, simulation: VertexSimulation):
        self._simulations[simulation.name] = simulation

    def register_function_backed_simulation(
        self,
        name: str,
        function_api_name: str,
        description: Optional[str] = None,
        binding_handler: Optional[
            Callable[[Ontology, Dict[str, Any], Dict[str, Any]], None]
        ] = None,
    ):
        def runner(**kwargs):
            return self._ontology.execute_function(function_api_name, **kwargs)

        simulation = VertexSimulation(
            name=name,
            runner=runner,
            description=description or f"Backed by function {function_api_name}",
            binding_handler=binding_handler,
        )
        self.register_simulation(simulation)
        return simulation

    def run_simulation(self, name: str, bind: bool = True, **kwargs) -> Dict[str, Any]:
        if name not in self._simulations:
            raise ValueError(f"Simulation {name} not registered")

        simulation = self._simulations[name]
        result = simulation.runner(**kwargs)

        if bind and simulation.binding_handler:
            simulation.binding_handler(self._ontology, result, kwargs)

        return {
            "simulation": name,
            "description": simulation.description,
            "result": result,
            "bound": bool(bind and simulation.binding_handler),
        }

    def generate_system_graph(
        self,
        seed_set: ObjectSet,
        max_depth: int = 1,
        include_properties: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        if seed_set.ontology is None:
            raise ValueError("Seed ObjectSet must include ontology context")
        if seed_set.ontology is not self._ontology:
            raise ValueError("Seed ObjectSet must belong to the same ontology")

        nodes: Dict[str, Dict[str, Any]] = {}
        edges: List[Dict[str, Any]] = []
        queue: List[tuple[ObjectInstance, int]] = []
        visited: set[str] = set()

        for obj in seed_set.all():
            node_id = self._node_id(obj)
            nodes[node_id] = self._build_node_payload(obj, 0, include_properties)
            queue.append((obj, 0))

        while queue:
            current_obj, depth = queue.pop(0)
            current_id = self._node_id(current_obj)
            if current_id in visited or depth > max_depth:
                continue

            link_types = self._ontology.get_link_types_for_object(
                current_obj.object_type_api_name
            )
            for link_type in link_types:
                for link in self._ontology.get_all_links():
                    if link.link_type_api_name != link_type.api_name:
                        continue

                    neighbor, direction = self._resolve_neighbor(
                        current_obj, link, link_type
                    )
                    if not neighbor:
                        continue

                    neighbor_id = self._node_id(neighbor)
                    if neighbor_id not in nodes:
                        nodes[neighbor_id] = self._build_node_payload(
                            neighbor, depth + 1, include_properties
                        )
                    if neighbor_id not in visited and depth + 1 <= max_depth:
                        queue.append((neighbor, depth + 1))

                    edge_payload = {
                        "link_type": link_type.api_name,
                        "source": current_id if direction == "outbound" else neighbor_id,
                        "target": neighbor_id if direction == "outbound" else current_id,
                        "direction": direction,
                    }
                    edges.append(edge_payload)

            visited.add(current_id)

        return {"nodes": nodes, "edges": edges}

    @staticmethod
    def _node_id(obj: ObjectInstance) -> str:
        return f"{obj.object_type_api_name}:{obj.primary_key_value}"

    @staticmethod
    def _build_node_payload(
        obj: ObjectInstance, depth: int, include_properties: Optional[List[str]]
    ) -> Dict[str, Any]:
        return {
            "id": Vertex._node_id(obj),
            "object_type": obj.object_type_api_name,
            "depth": depth,
            "properties": _object_snapshot(obj, include_properties)["properties"],
        }

    def _resolve_neighbor(
        self, current_obj: ObjectInstance, link, link_type
    ) -> tuple[Optional[ObjectInstance], Optional[str]]:
        if (
            link_type.source_object_type == current_obj.object_type_api_name
            and link.source_primary_key == current_obj.primary_key_value
        ):
            neighbor = self._ontology.get_object(
                link_type.target_object_type, link.target_primary_key
            )
            return neighbor, "outbound"

        if (
            link_type.target_object_type == current_obj.object_type_api_name
            and link.target_primary_key == current_obj.primary_key_value
        ):
            neighbor = self._ontology.get_object(
                link_type.source_object_type, link.source_primary_key
            )
            return neighbor, "inbound"

        return None, None
