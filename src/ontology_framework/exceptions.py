# 本体框架统一异常处理系统
# 提供结构化的异常类层次和错误处理机制

from enum import Enum
from typing import Any, Dict, Optional, List
import traceback
from datetime import datetime


class ErrorSeverity(Enum):
    """错误严重程度"""
    LOW = "low"           # 轻微错误，不影响核心功能
    MEDIUM = "medium"     # 中等错误，影响部分功能
    HIGH = "high"         # 严重错误，影响核心功能
    CRITICAL = "critical" # 致命错误，系统无法正常运行


class ErrorCategory(Enum):
    """错误分类"""
    VALIDATION = "validation"         # 数据验证错误
    PERMISSION = "permission"         # 权限控制错误
    NOT_FOUND = "not_found"          # 资源未找到错误
    SYSTEM = "system"                # 系统级错误
    BUSINESS = "business"            # 业务逻辑错误
    INTEGRATION = "integration"      # 集成接口错误
    CONFIGURATION = "configuration"  # 配置错误
    PERFORMANCE = "performance"      # 性能相关错误


class OntologyError(Exception):
    """
    本体框架基础异常类

    所有框架特定异常的基类，提供统一的错误信息格式和处理机制
    """

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        category: ErrorCategory = ErrorCategory.SYSTEM,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        """
        初始化异常

        Args:
            message: 错误消息
            error_code: 错误代码，用于程序化处理
            category: 错误分类
            severity: 错误严重程度
            details: 错误详细信息
            cause: 原始异常（如果有的话）
            context: 错误发生时的上下文信息
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.category = category
        self.severity = severity
        self.details = details or {}
        self.cause = cause
        self.context = context or {}
        self.timestamp = datetime.now()
        self.traceback_str = traceback.format_exc()

    def to_dict(self) -> Dict[str, Any]:
        """将异常转换为字典格式，便于日志记录和API响应"""
        return {
            "error_type": self.__class__.__name__,
            "error_code": self.error_code,
            "message": self.message,
            "category": self.category.value,
            "severity": self.severity.value,
            "details": self.details,
            "context": self.context,
            "timestamp": self.timestamp.isoformat(),
            "cause": str(self.cause) if self.cause else None
        }

    def __str__(self) -> str:
        """友好的字符串表示"""
        return f"[{self.error_code}] {self.message}"


# === 核心业务异常 ===

class ValidationError(OntologyError):
    """数据验证错误"""

    def __init__(
        self,
        message: str,
        field_name: Optional[str] = None,
        field_value: Any = None,
        expected_type: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.pop('details', {})
        if field_name:
            details['field_name'] = field_name
        if field_value is not None:
            details['field_value'] = str(field_value)
        if expected_type:
            details['expected_type'] = expected_type

        super().__init__(
            message=message,
            category=ErrorCategory.VALIDATION,
            severity=ErrorSeverity.MEDIUM,
            details=details,
            **kwargs
        )


class PermissionError(OntologyError):
    """权限控制错误"""

    def __init__(
        self,
        message: str,
        principal_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        required_permission: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.pop('details', {})
        if principal_id:
            details['principal_id'] = principal_id
        if resource_type:
            details['resource_type'] = resource_type
        if resource_id:
            details['resource_id'] = resource_id
        if required_permission:
            details['required_permission'] = required_permission

        super().__init__(
            message=message,
            category=ErrorCategory.PERMISSION,
            severity=ErrorSeverity.HIGH,
            details=details,
            **kwargs
        )


class NotFoundError(OntologyError):
    """资源未找到错误"""

    def __init__(
        self,
        message: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.pop('details', {})
        if resource_type:
            details['resource_type'] = resource_type
        if resource_id:
            details['resource_id'] = resource_id

        super().__init__(
            message=message,
            category=ErrorCategory.NOT_FOUND,
            severity=ErrorSeverity.MEDIUM,
            details=details,
            **kwargs
        )


class BusinessLogicError(OntologyError):
    """业务逻辑错误"""

    def __init__(
        self,
        message: str,
        business_rule: Optional[str] = None,
        operation: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.pop('details', {})
        if business_rule:
            details['business_rule'] = business_rule
        if operation:
            details['operation'] = operation

        super().__init__(
            message=message,
            category=ErrorCategory.BUSINESS,
            severity=ErrorSeverity.MEDIUM,
            details=details,
            **kwargs
        )


# === 系统级异常 ===

class ConfigurationError(OntologyError):
    """配置错误"""

    def __init__(
        self,
        message: str,
        config_key: Optional[str] = None,
        config_value: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.pop('details', {})
        if config_key:
            details['config_key'] = config_key
        if config_value:
            details['config_value'] = str(config_value)

        super().__init__(
            message=message,
            category=ErrorCategory.CONFIGURATION,
            severity=ErrorSeverity.HIGH,
            details=details,
            **kwargs
        )


class IntegrationError(OntologyError):
    """系统集成错误"""

    def __init__(
        self,
        message: str,
        service_name: Optional[str] = None,
        operation: Optional[str] = None,
        status_code: Optional[int] = None,
        **kwargs
    ):
        details = kwargs.pop('details', {})
        if service_name:
            details['service_name'] = service_name
        if operation:
            details['operation'] = operation
        if status_code:
            details['status_code'] = str(status_code)

        super().__init__(
            message=message,
            category=ErrorCategory.INTEGRATION,
            severity=ErrorSeverity.HIGH,
            details=details,
            **kwargs
        )


class PerformanceError(OntologyError):
    """性能相关错误"""

    def __init__(
        self,
        message: str,
        operation: Optional[str] = None,
        threshold: Optional[float] = None,
        actual_value: Optional[float] = None,
        **kwargs
    ):
        details = kwargs.pop('details', {})
        if operation:
            details['operation'] = operation
        if threshold:
            details['threshold'] = str(threshold)
        if actual_value:
            details['actual_value'] = str(actual_value)

        super().__init__(
            message=message,
            category=ErrorCategory.PERFORMANCE,
            severity=ErrorSeverity.MEDIUM,
            details=details,
            **kwargs
        )


# === 具体领域异常 ===

class ObjectTypeError(ValidationError):
    """对象类型错误"""

    def __init__(
        self,
        message: str,
        object_type_name: Optional[str] = None,
        **kwargs
    ):
        super().__init__(
            message=message,
            field_name="object_type",
            field_value=object_type_name,
            **kwargs
        )


class LinkTypeError(ValidationError):
    """链接类型错误"""

    def __init__(
        self,
        message: str,
        link_type_name: Optional[str] = None,
        **kwargs
    ):
        super().__init__(
            message=message,
            field_name="link_type",
            field_value=link_type_name,
            **kwargs
        )


class ActionTypeError(ValidationError):
    """操作类型错误"""

    def __init__(
        self,
        message: str,
        action_type_name: Optional[str] = None,
        **kwargs
    ):
        super().__init__(
            message=message,
            field_name="action_type",
            field_value=action_type_name,
            **kwargs
        )


class FunctionError(OntologyError):
    """函数执行错误"""

    def __init__(
        self,
        message: str,
        function_name: Optional[str] = None,
        arguments: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        details = kwargs.pop('details', {})
        if function_name:
            details['function_name'] = function_name
        if arguments:
            details['arguments'] = {k: str(v) for k, v in arguments.items()}

        super().__init__(
            message=message,
            category=ErrorCategory.SYSTEM,
            severity=ErrorSeverity.HIGH,
            details=details,
            **kwargs
        )


class ObjectInstanceError(ValidationError):
    """对象实例错误"""

    def __init__(
        self,
        message: str,
        object_type: Optional[str] = None,
        object_id: Optional[str] = None,
        **kwargs
    ):
        details = kwargs.pop('details', {})
        if object_type:
            details['object_type'] = object_type
        if object_id:
            details['object_id'] = object_id

        super().__init__(
            message=message,
            details=details,
            **kwargs
        )


# === 错误收集器 ===

class ErrorCollector:
    """错误收集器，用于批量收集和处理错误"""

    def __init__(self):
        self.errors: List[OntologyError] = []
        self.warnings: List[OntologyError] = []

    def add_error(self, error: OntologyError):
        """添加错误"""
        self.errors.append(error)

    def add_warning(self, warning: OntologyError):
        """添加警告"""
        warning.severity = ErrorSeverity.LOW
        self.warnings.append(warning)

    def has_errors(self) -> bool:
        """是否有错误"""
        return len(self.errors) > 0

    def has_warnings(self) -> bool:
        """是否有警告"""
        return len(self.warnings) > 0

    def get_all(self) -> List[OntologyError]:
        """获取所有错误和警告"""
        return self.errors + self.warnings

    def get_by_severity(self, severity: ErrorSeverity) -> List[OntologyError]:
        """按严重程度获取错误"""
        return [e for e in self.get_all() if e.severity == severity]

    def get_by_category(self, category: ErrorCategory) -> List[OntologyError]:
        """按分类获取错误"""
        return [e for e in self.get_all() if e.category == category]

    def clear(self):
        """清空所有错误和警告"""
        self.errors.clear()
        self.warnings.clear()

    def to_dict_list(self) -> List[Dict[str, Any]]:
        """转换为字典列表"""
        return [error.to_dict() for error in self.get_all()]


# === 错误处理工具函数 ===

def handle_exception(
    exception: Exception,
    context: Optional[Dict[str, Any]] = None,
    default_message: str = "An unexpected error occurred"
) -> OntologyError:
    """
    将普通异常转换为OntologyError

    Args:
        exception: 原始异常
        context: 错误上下文
        default_message: 默认错误消息

    Returns:
        OntologyError: 转换后的异常
    """
    if isinstance(exception, OntologyError):
        if context:
            exception.context.update(context)
        return exception

    # 根据异常类型确定分类
    category = ErrorCategory.SYSTEM
    if isinstance(exception, ValueError):
        category = ErrorCategory.VALIDATION
    elif isinstance(exception, PermissionError):
        category = ErrorCategory.PERMISSION
    elif isinstance(exception, KeyError):
        category = ErrorCategory.NOT_FOUND
    elif isinstance(exception, TypeError):
        category = ErrorCategory.VALIDATION

    return OntologyError(
        message=str(exception) or default_message,
        category=category,
        cause=exception,
        context=context
    )


def create_validation_error(
    field_name: str,
    field_value: Any,
    expected_type: str,
    message: Optional[str] = None
) -> ValidationError:
    """
    创建验证错误的便捷函数

    Args:
        field_name: 字段名
        field_value: 字段值
        expected_type: 期望类型
        message: 自定义错误消息

    Returns:
        ValidationError: 验证错误
    """
    if not message:
        message = f"Field '{field_name}' expects type {expected_type}, got {type(field_value).__name__}"

    return ValidationError(
        message=message,
        field_name=field_name,
        field_value=field_value,
        expected_type=expected_type
    )


def create_not_found_error(
    resource_type: str,
    resource_id: str,
    message: Optional[str] = None
) -> NotFoundError:
    """
    创建未找到错误的便捷函数

    Args:
        resource_type: 资源类型
        resource_id: 资源ID
        message: 自定义错误消息

    Returns:
        NotFoundError: 未找到错误
    """
    if not message:
        message = f"{resource_type} with ID '{resource_id}' not found"

    return NotFoundError(
        message=message,
        resource_type=resource_type,
        resource_id=resource_id
    )


def create_permission_error(
    principal_id: str,
    resource_type: str,
    required_permission: str,
    message: Optional[str] = None
) -> PermissionError:
    """
    创建权限错误的便捷函数

    Args:
        principal_id: 用户ID
        resource_type: 资源类型
        required_permission: 所需权限
        message: 自定义错误消息

    Returns:
        PermissionError: 权限错误
    """
    if not message:
        message = f"User '{principal_id}' lacks '{required_permission}' permission for {resource_type}"

    return PermissionError(
        message=message,
        principal_id=principal_id,
        resource_type=resource_type,
        required_permission=required_permission
    )