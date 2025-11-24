# 本体框架结构化日志配置
# 提供统一的日志记录接口和配置

import logging
import sys
from typing import Any, Dict, Optional, Union
from datetime import datetime
from pathlib import Path
import structlog
from structlog.stdlib import LoggerFactory
from contextvars import ContextVar
import json

from .exceptions import OntologyError, ErrorSeverity, ErrorCategory


# 上下文变量，用于追踪请求/操作
REQUEST_ID: ContextVar[Optional[str]] = ContextVar('request_id', default=None)
USER_ID: ContextVar[Optional[str]] = ContextVar('user_id', default=None)
OPERATION: ContextVar[Optional[str]] = ContextVar('operation', default=None)


class OntologyLogger:
    """本体框架专用日志器"""

    def __init__(self, name: str = "ontology_framework"):
        self.name = name
        self.logger = structlog.get_logger(name)
        self._setup_logging()

    def _setup_logging(self):
        """配置结构化日志"""
        # 配置structlog处理器
        structlog.configure(
            processors=[
                # 添加上下文变量
                structlog.stdlib.add_log_level,
                structlog.stdlib.add_logger_name,
                self._add_context_vars,
                self._add_timestamp,
                # 格式化输出
                structlog.processors.StackInfoRenderer(),
                structlog.dev.set_exc_info,
                structlog.processors.UnicodeDecoder(),
                # 根据环境选择输出格式
                structlog.processors.JSONRenderer() if not self._is_debug()
                else structlog.dev.ConsoleRenderer(colors=True),
            ],
            context_class=dict,
            logger_factory=LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )

        # 配置标准库logging
        logging.basicConfig(
            format="%(message)s",
            stream=sys.stdout,
            level=logging.DEBUG if self._is_debug() else logging.INFO,
        )

    def _is_debug(self) -> bool:
        """判断是否为调试模式"""
        import os
        return os.getenv('ONTOLOGY_DEBUG', '').lower() in ('true', '1', 'yes')

    def _add_context_vars(self, logger, method_name: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
        """添加上下文变量到日志"""
        request_id = REQUEST_ID.get()
        user_id = USER_ID.get()
        operation = OPERATION.get()

        if request_id:
            event_dict['request_id'] = request_id
        if user_id:
            event_dict['user_id'] = user_id
        if operation:
            event_dict['operation'] = operation

        return event_dict

    def _add_timestamp(self, logger, method_name: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
        """添加时间戳"""
        event_dict['timestamp'] = datetime.utcnow().isoformat()
        return event_dict

    def info(self, message: str, **kwargs):
        """信息日志"""
        self.logger.info(message, **kwargs)

    def warning(self, message: str, **kwargs):
        """警告日志"""
        self.logger.warning(message, **kwargs)

    def error(self, message: str, **kwargs):
        """错误日志"""
        self.logger.error(message, **kwargs)

    def debug(self, message: str, **kwargs):
        """调试日志"""
        self.logger.debug(message, **kwargs)

    def critical(self, message: str, **kwargs):
        """严重错误日志"""
        self.logger.critical(message, **kwargs)

    def exception(self, message: str, **kwargs):
        """异常日志（自动包含堆栈跟踪）"""
        self.logger.exception(message, **kwargs)


class ErrorLogger:
    """专门的错误日志记录器"""

    def __init__(self, logger: OntologyLogger):
        self.logger = logger

    def log_error(
        self,
        error: Union[OntologyError, Exception],
        context: Optional[Dict[str, Any]] = None,
        include_traceback: bool = True
    ):
        """
        记录错误日志

        Args:
            error: 异常对象
            context: 额外的上下文信息
            include_traceback: 是否包含堆栈跟踪
        """
        if isinstance(error, OntologyError):
            # 如果是OntologyError，使用其结构化信息
            error_data = error.to_dict()
            if context:
                error_data['additional_context'] = context

            self.logger.error(
                f"OntologyError: {error.message}",
                error_type=error_data['error_type'],
                error_code=error_data['error_code'],
                category=error_data['category'],
                severity=error_data['severity'],
                details=error_data['details'],
                context_info=error_data['context'],
                cause=error_data['cause'],
                **{k: v for k, v in context.items() if k not in error_data}
            )
        else:
            # 普通异常
            self.logger.error(
                f"Exception: {str(error)}",
                exception_type=type(error).__name__,
                exception_message=str(error),
                context=context or {},
                include_traceback=include_traceback
            )

    def log_validation_error(
        self,
        field_name: str,
        field_value: Any,
        expected_type: str,
        object_type: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        """
        记录验证错误

        Args:
            field_name: 字段名
            field_value: 字段值
            expected_type: 期望类型
            object_type: 对象类型
            context: 额外上下文
        """
        self.logger.warning(
            f"Validation failed for field '{field_name}'",
            field_name=field_name,
            field_value=str(field_value),
            expected_type=expected_type,
            object_type=object_type,
            context=context or {}
        )

    def log_permission_denied(
        self,
        principal_id: str,
        resource_type: str,
        required_permission: str,
        resource_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        """
        记录权限拒绝错误

        Args:
            principal_id: 用户ID
            resource_type: 资源类型
            required_permission: 所需权限
            resource_id: 资源ID
            context: 额外上下文
        """
        self.logger.warning(
            f"Permission denied for user '{principal_id}' on {resource_type}",
            principal_id=principal_id,
            resource_type=resource_type,
            required_permission=required_permission,
            resource_id=resource_id,
            context=context or {}
        )

    def log_performance_issue(
        self,
        operation: str,
        duration: float,
        threshold: float,
        context: Optional[Dict[str, Any]] = None
    ):
        """
        记录性能问题

        Args:
            operation: 操作名称
            duration: 实际耗时（秒）
            threshold: 阈值（秒）
            context: 额外上下文
        """
        self.logger.warning(
            f"Performance issue detected: {operation} took {duration:.3f}s (threshold: {threshold:.3f}s)",
            operation=operation,
            duration=duration,
            threshold=threshold,
            performance_ratio=duration / threshold,
            context=context or {}
        )


class AuditLogger:
    """审计日志记录器，用于记录重要的业务操作"""

    def __init__(self, logger: OntologyLogger):
        self.logger = logger

    def log_operation(
        self,
        operation: str,
        principal_id: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        result: str = "success"
    ):
        """
        记录业务操作

        Args:
            operation: 操作类型
            principal_id: 执行者ID
            resource_type: 资源类型
            resource_id: 资源ID
            details: 操作详情
            result: 操作结果 (success/failure)
        """
        self.logger.info(
            f"Operation completed: {operation}",
            operation=operation,
            principal_id=principal_id,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details or {},
            result=result,
            event_type="audit"
        )

    def log_data_access(
        self,
        principal_id: str,
        resource_type: str,
        access_type: str,  # read/write/delete
        resource_count: int = 1,
        context: Optional[Dict[str, Any]] = None
    ):
        """
        记录数据访问

        Args:
            principal_id: 用户ID
            resource_type: 资源类型
            access_type: 访问类型
            resource_count: 访问的资源数量
            context: 额外上下文
        """
        self.logger.info(
            f"Data access: {access_type} on {resource_count} {resource_type} resources",
            principal_id=principal_id,
            resource_type=resource_type,
            access_type=access_type,
            resource_count=resource_count,
            context=context or {},
            event_type="data_access"
        )

    def log_configuration_change(
        self,
        principal_id: str,
        config_key: str,
        old_value: Any,
        new_value: Any,
        context: Optional[Dict[str, Any]] = None
    ):
        """
        记录配置变更

        Args:
            principal_id: 执行者ID
            config_key: 配置键
            old_value: 旧值
            new_value: 新值
            context: 额外上下文
        """
        self.logger.info(
            f"Configuration changed: {config_key}",
            principal_id=principal_id,
            config_key=config_key,
            old_value=str(old_value),
            new_value=str(new_value),
            context=context or {},
            event_type="config_change"
        )


class PerformanceLogger:
    """性能日志记录器"""

    def __init__(self, logger: OntologyLogger):
        self.logger = logger

    def log_operation_timing(
        self,
        operation: str,
        duration: float,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        记录操作耗时

        Args:
            operation: 操作名称
            duration: 耗时（秒）
            metadata: 元数据
        """
        self.logger.info(
            f"Operation timing: {operation}",
            operation=operation,
            duration=duration,
            duration_ms=duration * 1000,
            metadata=metadata or {},
            event_type="performance"
        )

    def log_query_performance(
        self,
        query_type: str,
        object_count: int,
        duration: float,
        filters: Optional[Dict[str, Any]] = None
    ):
        """
        记录查询性能

        Args:
            query_type: 查询类型
            object_count: 对象数量
            duration: 耗时（秒）
            filters: 过滤条件
        """
        self.logger.info(
            f"Query performance: {query_type}",
            query_type=query_type,
            object_count=object_count,
            duration=duration,
            objects_per_second=object_count / duration if duration > 0 else 0,
            filters=filters or {},
            event_type="query_performance"
        )


# 全局日志器实例
main_logger = OntologyLogger()
error_logger = ErrorLogger(main_logger)
audit_logger = AuditLogger(main_logger)
performance_logger = PerformanceLogger(main_logger)


# 上下文管理器
class LoggingContext:
    """日志上下文管理器，用于设置上下文变量"""

    def __init__(
        self,
        request_id: Optional[str] = None,
        user_id: Optional[str] = None,
        operation: Optional[str] = None
    ):
        self.request_id = request_id
        self.user_id = user_id
        self.operation = operation
        self.tokens = []

    def __enter__(self):
        if self.request_id:
            self.tokens.append(REQUEST_ID.set(self.request_id))
        if self.user_id:
            self.tokens.append(USER_ID.set(self.user_id))
        if self.operation:
            self.tokens.append(OPERATION.set(self.operation))
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        for token in self.tokens:
            token.var.reset(token)


# 便捷函数
def get_logger(name: str = "ontology_framework") -> OntologyLogger:
    """获取日志器实例"""
    return OntologyLogger(name)


def log_operation_start(operation: str, **kwargs):
    """记录操作开始"""
    main_logger.info(f"Starting operation: {operation}", operation=operation, **kwargs)


def log_operation_end(operation: str, success: bool = True, **kwargs):
    """记录操作结束"""
    status = "completed" if success else "failed"
    main_logger.info(f"Operation {status}: {operation}", operation=operation, success=success, **kwargs)


# 装饰器
def logged(operation_name: Optional[str] = None):
    """
    日志装饰器，自动记录函数执行

    Args:
        operation_name: 操作名称，默认使用函数名
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            op_name = operation_name or f"{func.__module__}.{func.__name__}"

            with LoggingContext(operation=op_name):
                log_operation_start(op_name, args_count=len(args), kwargs_keys=list(kwargs.keys()))

                start_time = datetime.now()
                try:
                    result = func(*args, **kwargs)
                    duration = (datetime.now() - start_time).total_seconds()

                    performance_logger.log_operation_timing(op_name, duration, {
                        'args_count': len(args),
                        'kwargs_count': len(kwargs),
                        'success': True
                    })

                    log_operation_end(op_name, success=True, duration=duration)
                    return result

                except Exception as e:
                    duration = (datetime.now() - start_time).total_seconds()

                    error_logger.log_error(e, {
                        'operation': op_name,
                        'args_count': len(args),
                        'kwargs_count': len(kwargs),
                        'duration': duration
                    })

                    performance_logger.log_operation_timing(op_name, duration, {
                        'args_count': len(args),
                        'kwargs_count': len(kwargs),
                        'success': False,
                        'error_type': type(e).__name__
                    })

                    log_operation_end(op_name, success=False, duration=duration, error=str(e))
                    raise

        return wrapper
    return decorator