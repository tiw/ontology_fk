from typing import Dict, List, Any, Optional
import uuid
import time
from .core import ObjectType, ObjectInstance, ObjectSet, ActionType, ActionContext, ActionLog, Ontology
from .permissions import AccessControlList, PermissionType, Principal

class ObjectSetService:
    def __init__(self):
        # Mock storage: object_type_api_name -> List[ObjectInstance]
        self._storage: Dict[str, List[ObjectInstance]] = {}
        # Mock index: object_type_api_name -> property_name -> value -> List[ObjectInstance]
        self._index: Dict[str, Dict[str, Dict[Any, List[ObjectInstance]]]] = {}

    def index_object(self, obj: ObjectInstance):
        """Simulates Object Storage V2 indexing."""
        api_name = obj.object_type_api_name
        if api_name not in self._storage:
            self._storage[api_name] = []
            self._index[api_name] = {}
        
        self._storage[api_name].append(obj)

        # Simple indexing for all properties
        for prop, value in obj.property_values.items():
            if prop not in self._index[api_name]:
                self._index[api_name][prop] = {}
            if value not in self._index[api_name][prop]:
                self._index[api_name][prop][value] = []
            self._index[api_name][prop][value].append(obj)

    def get_base_object_set(self, object_type: ObjectType, principal_id: str = None) -> ObjectSet:
        """Returns the base ObjectSet for a type, checking permissions."""
        # Permission check (Phase 4)
        if object_type.permissions and principal_id:
            if not object_type.permissions.check(principal_id, PermissionType.VIEW):
                raise PermissionError(f"User {principal_id} does not have VIEW permission for {object_type.api_name}")

        objects = self._storage.get(object_type.api_name, [])
        return ObjectSet(object_type, objects)

    def search(self, object_type: ObjectType, query: str) -> ObjectSet:
        """Semantic search simulation."""
        # In a real system, this would use embeddings/vector search.
        # Here we just do a naive string match across all properties.
        all_objects = self._storage.get(object_type.api_name, [])
        results = []
        for obj in all_objects:
            match = False
            for val in obj.property_values.values():
                if str(val).lower().find(query.lower()) != -1:
                    match = True
                    break
            if match:
                results.append(obj)
        return ObjectSet(object_type, results)

class ActionService:
    def __init__(self, ontology: Ontology):
        self.ontology = ontology
        self.action_logs: List[ActionLog] = []

    def execute_action(self, action_type_api_name: str, parameters: Dict[str, Any], principal: Principal) -> ActionLog:
        action_type = self.ontology.get_action_type(action_type_api_name)
        if not action_type:
            raise ValueError(f"Action type {action_type_api_name} not found")

        # 1. Permission Check
        if action_type.permissions:
            if not action_type.permissions.check(principal.id, PermissionType.EDIT): # Assuming EDIT permission needed for Action
                 raise PermissionError(f"User {principal.id} does not have permission to execute action {action_type_api_name}")

        # 2. Parameter Validation
        for param_name, param_def in action_type.parameters.items():
            if param_def.required and param_name not in parameters:
                raise ValueError(f"Missing required parameter: {param_name}")
            # Type checking could go here (simplified)
        
        # 3. Execution Context
        context = ActionContext(self.ontology, principal.id)
        
        # 4. Execute Logic
        if action_type.logic:
            action_type.logic(context, **parameters)
        
        # 5. Commit Changes
        context.apply_changes()

        # 6. Log Action
        log = ActionLog(
            id=str(uuid.uuid4()),
            action_type_api_name=action_type_api_name,
            user_id=principal.id,
            timestamp=time.time(),
            parameters=parameters,
            changes=context._changes
        )
        self.action_logs.append(log)

        # 7. Execute Side Effects
        for effect in action_type.side_effects:
            # In a real system, these would be async tasks
            if hasattr(effect, 'recipients'): # Notification
                print(f"[Notification] Sending to {effect.recipients}: {effect.message}")
            elif hasattr(effect, 'url'): # Webhook
                print(f"[Webhook] {effect.method} {effect.url}")

        return log
