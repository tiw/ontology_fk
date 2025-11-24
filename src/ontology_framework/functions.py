from typing import Callable, Optional, Dict, Any, Type
from .core import Ontology, Function, FunctionArgument, TypeSpec, PrimitiveType, ObjectTypeSpec, ObjectSetTypeSpec, PropertyType

# Helper to map python types to TypeSpec
def _map_python_type(py_type: Type) -> TypeSpec:
    if py_type == str:
        return PrimitiveType(PropertyType.STRING)
    elif py_type == int:
        return PrimitiveType(PropertyType.INTEGER)
    elif py_type == bool:
        return PrimitiveType(PropertyType.BOOLEAN)
    # For Objects and ObjectSets, we might need custom annotations or hints
    # For now, default to String if unknown, or let user specify manually in decorator
    return PrimitiveType(PropertyType.STRING)

class FunctionRegistry:
    def __init__(self):
        self._pending_functions: Dict[str, Function] = {}

    def register(self, api_name: str, **kwargs):
        def decorator(func: Callable):
            # Create Function definition
            # We can inspect func signature here to infer inputs if not provided
            # For this prototype, we rely on manual definition in kwargs or simple defaults
            
            f = Function(
                api_name=api_name,
                display_name=kwargs.get('display_name', api_name),
                description=kwargs.get('description'),
                logic=func
            )
            
            # Add inputs if specified
            inputs = kwargs.get('inputs', {})
            for name, type_spec in inputs.items():
                f.add_input(name, type_spec)
                
            self._pending_functions[api_name] = f
            return func
        return decorator

    def register_all_to_ontology(self, ontology: Ontology):
        for f in self._pending_functions.values():
            ontology.register_function(f)

# Global registry
registry = FunctionRegistry()

def ontology_function(api_name: str, **kwargs):
    return registry.register(api_name, **kwargs)
