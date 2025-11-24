from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum

class PermissionType(Enum):
    VIEW = "view"
    EDIT = "edit"
    DELETE = "delete"
    OWNER = "owner"

@dataclass
class Principal:
    id: str
    type: str = "USER"  # USER or GROUP
    attributes: List[str] = field(default_factory=list)

@dataclass
class AccessControlList:
    # simple mapping of principal_id -> list of permissions
    permissions: dict[str, List[PermissionType]] = field(default_factory=dict)

    def grant(self, principal_id: str, permission: PermissionType):
        if principal_id not in self.permissions:
            self.permissions[principal_id] = []
        if permission not in self.permissions[principal_id]:
            self.permissions[principal_id].append(permission)

    def check(self, principal_id: str, permission: PermissionType) -> bool:
        return permission in self.permissions.get(principal_id, [])
