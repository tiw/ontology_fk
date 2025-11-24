from dataclasses import dataclass, field
from typing import List, Optional, Dict
from .core import ObjectType, ObjectSet

@dataclass
class ObjectView:
    object_type: ObjectType
    title: str
    widgets: List[str] = field(default_factory=list)
    
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

    def open(self, object_type_api_name: str, object_set: ObjectSet):
        if object_type_api_name in self.views:
            self.views[object_type_api_name].render(object_set)
        else:
            print(f"No custom view for {object_type_api_name}, showing default list.")
            for obj in object_set.all():
                print(f" - {obj.primary_key_value}: {obj.property_values}")

class Quiver:
    def analyze(self, object_set: ObjectSet):
        print("--- Quiver Analysis ---")
        print(f"Analyzing {len(object_set.all())} objects of type {object_set.object_type.api_name}")
        # Mock analysis
        print("Generating charts... [Done]")
        print("-----------------------")
