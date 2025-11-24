# 异常处理和错误恢复系统测试
# 测试统一异常类层次结构和错误恢复机制

import pytest
import time
from typing import Any, Dict
from unittest.mock import Mock, patch

from src.ontology_framework.exceptions import (
    OntologyError, ValidationError, PermissionError, NotFoundError,
    BusinessLogicError, ConfigurationError, IntegrationError, PerformanceError,
    ObjectTypeError, LinkTypeError, ActionTypeError, FunctionError, ObjectInstanceError,
    ErrorSeverity, ErrorCategory, ErrorCollector,
    handle_exception, create_validation_error, create_not_found_error, create_permission_error
)
from src.ontology_framework.logging_config import (
    OntologyLogger, ErrorLogger, AuditLogger, PerformanceLogger, LoggingContext,
    main_logger, error_logger, audit_logger
)
from src.ontology_framework.error_recovery import (
    RecoveryStrategy, RetryConfig, CircuitBreakerConfig, FallbackConfig,
    CircuitBreaker, CircuitBreakerState, RetryMechanism, FallbackHandler,
    ErrorRecoveryManager, recovery_manager,
    with_retry, with_circuit_breaker, with_fallback, combined_protection
)


class TestOntologyError:
    """OntologyError基础异常测试"""

    def test_ontology_error_creation(self):
        """测试OntologyError创建"""
        error = OntologyError(
            message="Test error message",
            error_code="TEST_ERROR",
            category=ErrorCategory.VALIDATION,
            severity=ErrorSeverity.MEDIUM,
            details={"field": "test_field"},
            context={"operation": "test_operation"}
        )

        assert error.message == "Test error message"
        assert error.error_code == "TEST_ERROR"
        assert error.category == ErrorCategory.VALIDATION
        assert error.severity == ErrorSeverity.MEDIUM
        assert error.details["field"] == "test_field"
        assert error.context["operation"] == "test_operation"

    def test_ontology_error_to_dict(self):
        """测试OntologyError转换为字典"""
        error = OntologyError(
            message="Test error",
            error_code="TEST_001",
            category=ErrorCategory.SYSTEM,
            severity=ErrorSeverity.HIGH,
            details={"key": "value"}
        )

        error_dict = error.to_dict()

        assert error_dict["error_type"] == "OntologyError"
        assert error_dict["error_code"] == "TEST_001"
        assert error_dict["message"] == "Test error"
        assert error_dict["category"] == "system"
        assert error_dict["severity"] == "high"
        assert error_dict["details"]["key"] == "value"

    def test_ontology_error_string_representation(self):
        """测试OntologyError字符串表示"""
        error = OntologyError("Test message", error_code="ERR_001")
        assert str(error) == "[ERR_001] Test message"


class TestSpecificExceptions:
    """具体异常类测试"""

    def test_validation_error(self):
        """测试ValidationError"""
        error = ValidationError(
            message="Invalid email format",
            field_name="email",
            field_value="invalid_email",
            expected_type="email"
        )

        assert error.category == ErrorCategory.VALIDATION
        assert error.details["field_name"] == "email"
        assert error.details["field_value"] == "invalid_email"
        assert error.details["expected_type"] == "email"

    def test_permission_error(self):
        """测试PermissionError"""
        error = PermissionError(
            message="Access denied",
            principal_id="user_123",
            resource_type="document",
            required_permission="EDIT"
        )

        assert error.category == ErrorCategory.PERMISSION
        assert error.severity == ErrorSeverity.HIGH
        assert error.details["principal_id"] == "user_123"
        assert error.details["resource_type"] == "document"
        assert error.details["required_permission"] == "EDIT"

    def test_not_found_error(self):
        """测试NotFoundError"""
        error = NotFoundError(
            message="User not found",
            resource_type="User",
            resource_id="user_456"
        )

        assert error.category == ErrorCategory.NOT_FOUND
        assert error.severity == ErrorSeverity.MEDIUM
        assert error.details["resource_type"] == "User"
        assert error.details["resource_id"] == "user_456"

    def test_business_logic_error(self):
        """测试BusinessLogicError"""
        error = BusinessLogicError(
            message="Cannot delete user with active orders",
            business_rule="USER_DELETE_RESTRICTION",
            operation="delete_user"
        )

        assert error.category == ErrorCategory.BUSINESS
        assert error.details["business_rule"] == "USER_DELETE_RESTRICTION"
        assert error.details["operation"] == "delete_user"

    def test_configuration_error(self):
        """测试ConfigurationError"""
        error = ConfigurationError(
            message="Missing database configuration",
            config_key="database.url"
        )

        assert error.category == ErrorCategory.CONFIGURATION
        assert error.severity == ErrorSeverity.HIGH
        assert error.details["config_key"] == "database.url"

    def test_integration_error(self):
        """测试IntegrationError"""
        error = IntegrationError(
            message="External API call failed",
            service_name="payment_gateway",
            operation="charge",
            status_code=500
        )

        assert error.category == ErrorCategory.INTEGRATION
        assert error.severity == ErrorSeverity.HIGH
        assert error.details["service_name"] == "payment_gateway"
        assert error.details["operation"] == "charge"
        assert error.details["status_code"] == "500"

    def test_performance_error(self):
        """测试PerformanceError"""
        error = PerformanceError(
            message="Query timeout exceeded",
            operation="complex_search",
            threshold=5.0,
            actual_value=8.5
        )

        assert error.category == ErrorCategory.PERFORMANCE
        assert error.details["operation"] == "complex_search"
        assert error.details["threshold"] == "5.0"
        assert error.details["actual_value"] == "8.5"


class TestErrorCollector:
    """ErrorCollector测试"""

    def test_error_collector_basic_operations(self):
        """测试ErrorCollector基础操作"""
        collector = ErrorCollector()

        assert not collector.has_errors()
        assert not collector.has_warnings()

        # 添加错误
        error1 = ValidationError("Error 1")
        error2 = BusinessLogicError("Error 2")

        collector.add_error(error1)
        collector.add_error(error2)

        assert collector.has_errors()
        assert len(collector.errors) == 2
        assert not collector.has_warnings()

        # 添加警告
        warning = ValidationError("Warning")
        collector.add_warning(warning)

        assert collector.has_warnings()
        assert len(collector.warnings) == 1
        assert len(collector.get_all()) == 3

    def test_error_collector_filtering(self):
        """测试ErrorCollector过滤功能"""
        collector = ErrorCollector()

        # 添加不同类型和严重程度的错误
        collector.add_error(ValidationError("Validation error"))
        collector.add_error(PermissionError("Permission error"))
        collector.add_warning(ValidationError("Warning"))

        # 按严重程度过滤
        high_severity = collector.get_by_severity(ErrorSeverity.HIGH)
        assert len(high_severity) == 1
        assert isinstance(high_severity[0], PermissionError)

        low_severity = collector.get_by_severity(ErrorSeverity.LOW)
        assert len(low_severity) == 1

        # 按分类过滤
        validation_errors = collector.get_by_category(ErrorCategory.VALIDATION)
        assert len(validation_errors) == 2

    def test_error_collector_clear(self):
        """测试ErrorCollector清空功能"""
        collector = ErrorCollector()

        collector.add_error(ValidationError("Error"))
        collector.add_warning(ValidationError("Warning"))

        assert collector.has_errors()
        assert collector.has_warnings()

        collector.clear()

        assert not collector.has_errors()
        assert not collector.has_warnings()
        assert len(collector.errors) == 0
        assert len(collector.warnings) == 0

    def test_error_collector_to_dict_list(self):
        """测试ErrorCollector转换为字典列表"""
        collector = ErrorCollector()

        error = ValidationError("Test error", error_code="TEST_001")
        collector.add_error(error)

        dict_list = collector.to_dict_list()
        assert len(dict_list) == 1
        assert dict_list[0]["error_code"] == "TEST_001"
        assert dict_list[0]["message"] == "Test error"


class TestExceptionUtilities:
    """异常处理工具函数测试"""

    def test_handle_exception_with_ontology_error(self):
        """测试handle_exception处理OntologyError"""
        original_error = ValidationError("Original error", field_name="test")

        handled_error = handle_exception(original_error, {"additional": "context"})

        assert isinstance(handled_error, ValidationError)
        assert handled_error == original_error
        assert handled_error.context["additional"] == "context"

    def test_handle_exception_with_regular_exception(self):
        """测试handle_exception处理普通异常"""
        original_error = ValueError("Regular error")

        handled_error = handle_exception(
            original_error,
            context={"operation": "test"},
            default_message="Default error message"
        )

        assert isinstance(handled_error, OntologyError)
        assert handled_error.message == "Regular error"
        assert handled_error.category == ErrorCategory.VALIDATION
        assert handled_error.cause == original_error
        assert handled_error.context["operation"] == "test"

    def test_create_validation_error(self):
        """测试create_validation_error便捷函数"""
        error = create_validation_error("email", "invalid_email", "email_format")

        assert isinstance(error, ValidationError)
        assert error.details["field_name"] == "email"
        assert error.details["field_value"] == "invalid_email"
        assert error.details["expected_type"] == "email_format"

    def test_create_not_found_error(self):
        """测试create_not_found_error便捷函数"""
        error = create_not_found_error("User", "user_123")

        assert isinstance(error, NotFoundError)
        assert error.details["resource_type"] == "User"
        assert error.details["resource_id"] == "user_123"

    def test_create_permission_error(self):
        """测试create_permission_error便捷函数"""
        error = create_permission_error("user_456", "Document", "VIEW")

        assert isinstance(error, PermissionError)
        assert error.details["principal_id"] == "user_456"
        assert error.details["resource_type"] == "Document"
        assert error.details["required_permission"] == "VIEW"


class TestCircuitBreaker:
    """熔断器测试"""

    def test_circuit_breaker_initial_state(self):
        """测试熔断器初始状态"""
        config = CircuitBreakerConfig(failure_threshold=3, recovery_timeout=1.0)
        breaker = CircuitBreaker(config)

        assert breaker.state == CircuitBreakerState.CLOSED
        assert breaker.failure_count == 0

    def test_circuit_breaker_success(self):
        """测试熔断器成功调用"""
        config = CircuitBreakerConfig(failure_threshold=3, recovery_timeout=1.0)
        breaker = CircuitBreaker(config)

        def success_func():
            return "success"

        result = breaker.call(success_func)
        assert result == "success"
        assert breaker.state == CircuitBreakerState.CLOSED
        assert breaker.failure_count == 0

    def test_circuit_breaker_failure_and_trip(self):
        """测试熔断器失败和触发"""
        config = CircuitBreakerConfig(failure_threshold=2, recovery_timeout=0.1)
        breaker = CircuitBreaker(config)

        def failing_func():
            raise ValueError("Test failure")

        # 第一次失败
        with pytest.raises(ValueError):
            breaker.call(failing_func)
        assert breaker.state == CircuitBreakerState.CLOSED
        assert breaker.failure_count == 1

        # 第二次失败，应该触发熔断
        with pytest.raises(ValueError):
            breaker.call(failing_func)
        assert breaker.state == CircuitBreakerState.OPEN
        assert breaker.failure_count == 2

    def test_circuit_breaker_open_state(self):
        """测试熔断器打开状态"""
        config = CircuitBreakerConfig(failure_threshold=1, recovery_timeout=0.1)
        breaker = CircuitBreaker(config)

        def failing_func():
            raise ValueError("Test failure")

        # 触发熔断
        with pytest.raises(ValueError):
            breaker.call(failing_func)

        assert breaker.state == CircuitBreakerState.OPEN

        # 在打开状态，直接抛出异常
        with pytest.raises(OntologyError) as exc_info:
            breaker.call(failing_func)

        assert "CIRCUIT_BREAKER_OPEN" in str(exc_info.value)


class TestRetryMechanism:
    """重试机制测试"""

    def test_retry_success_on_first_attempt(self):
        """测试重试机制首次成功"""
        config = RetryConfig(max_attempts=3, base_delay=0.01)
        retry = RetryMechanism(config)

        def success_func():
            return "success"

        result = retry.execute_with_retry(success_func)
        assert result == "success"

    def test_retry_success_after_failure(self):
        """测试重试机制失败后成功"""
        config = RetryConfig(max_attempts=3, base_delay=0.01, jitter=False)
        retry = RetryMechanism(config)

        call_count = 0

        def failing_then_success():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Temporary failure")
            return "success"

        result = retry.execute_with_retry(failing_then_success)
        assert result == "success"
        assert call_count == 2

    def test_retry_exhausted(self):
        """测试重试耗尽"""
        config = RetryConfig(max_attempts=2, base_delay=0.01, jitter=False)
        retry = RetryMechanism(config)

        def always_failing():
            raise ValueError("Permanent failure")

        with pytest.raises(OntologyError) as exc_info:
            retry.execute_with_retry(always_failing)

        assert exc_info.value.error_code == "RETRY_EXHAUSTED"
        assert "Operation failed after 2 attempts" in str(exc_info.value)

    def test_retry_specific_exception_types(self):
        """测试重试特定异常类型"""
        config = RetryConfig(
            max_attempts=2,
            base_delay=0.01,
            retry_on=[ValueError]  # 只重试ValueError
        )
        retry = RetryMechanism(config)

        def raise_type_error():
            raise TypeError("Should not retry")

        with pytest.raises(TypeError):
            retry.execute_with_retry(raise_type_error)


class TestFallbackHandler:
    """降级处理器测试"""

    def test_fallback_success(self):
        """测试降级处理器成功情况"""
        config = FallbackConfig()
        fallback = FallbackHandler(config)

        def success_func():
            return "success"

        result = fallback.execute_with_fallback(success_func)
        assert result == "success"

    def test_fallback_with_function(self):
        """测试使用降级函数"""
        fallback_func = Mock(return_value="fallback_result")
        config = FallbackConfig(fallback_function=fallback_func)
        fallback = FallbackHandler(config)

        def failing_func():
            raise ValueError("Original error")

        result = fallback.execute_with_fallback(failing_func)
        assert result == "fallback_result"
        fallback_func.assert_called_once()

    def test_fallback_with_value(self):
        """测试使用降级值"""
        config = FallbackConfig(fallback_value="default_value")
        fallback = FallbackHandler(config)

        def failing_func():
            raise ValueError("Original error")

        result = fallback.execute_with_fallback(failing_func)
        assert result == "default_value"

    def test_fallback_no_fallback_configured(self):
        """测试没有配置降级策略"""
        config = FallbackConfig()
        fallback = FallbackHandler(config)

        def failing_func():
            raise ValueError("Original error")

        with pytest.raises(ValueError):
            fallback.execute_with_fallback(failing_func)


class TestErrorRecoveryManager:
    """错误恢复管理器测试"""

    def test_register_and_use_components(self):
        """测试注册和使用恢复组件"""
        manager = ErrorRecoveryManager()

        # 注册组件
        retry_config = RetryConfig(max_attempts=2, base_delay=0.01, jitter=False)
        circuit_config = CircuitBreakerConfig(failure_threshold=2, recovery_timeout=0.1)
        fallback_config = FallbackConfig(fallback_value="fallback")

        manager.register_retry_mechanism("test_retry", retry_config)
        manager.register_circuit_breaker("test_circuit", circuit_config)
        manager.register_fallback_handler("test_fallback", fallback_config)

        # 验证注册成功
        assert "test_retry" in manager.retry_mechanisms
        assert "test_circuit" in manager.circuit_breakers
        assert "test_fallback" in manager.fallback_handlers

    def test_recovery_manager_status(self):
        """测试恢复管理器状态"""
        manager = ErrorRecoveryManager()
        manager.register_circuit_breaker("test", CircuitBreakerConfig())

        status = manager.get_status()
        assert "circuit_breakers" in status
        assert "retry_mechanisms" in status
        assert "fallback_handlers" in status
        assert "test" in status["circuit_breakers"]


class TestDecorators:
    """装饰器测试"""

    def test_with_retry_decorator(self):
        """测试重试装饰器"""
        call_count = 0

        @with_retry(max_attempts=3, base_delay=0.01)
        def failing_function():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Temporary failure")
            return "success"

        result = failing_function()
        assert result == "success"
        assert call_count == 2

    def test_with_circuit_breaker_decorator(self):
        """测试熔断器装饰器"""
        @with_circuit_breaker(failure_threshold=2, recovery_timeout=0.1)
        def failing_function():
            raise ValueError("Always fails")

        # 前两次调用触发熔断
        with pytest.raises(ValueError):
            failing_function()
        with pytest.raises(ValueError):
            failing_function()

        # 第三次调用应该被熔断器阻止
        with pytest.raises(OntologyError) as exc_info:
            failing_function()
        assert "CIRCUIT_BREAKER_OPEN" in str(exc_info.value)

    def test_with_fallback_decorator(self):
        """测试降级装饰器"""
        @with_fallback(fallback_value="fallback_result")
        def failing_function():
            raise ValueError("Original error")

        result = failing_function()
        assert result == "fallback_result"

    def test_combined_protection_decorator(self):
        """测试组合保护装饰器"""
        call_count = 0

        @combined_protection(
            strategies=[RecoveryStrategy.RETRY, RecoveryStrategy.FALLBACK],
            retry_config={"max_attempts": 2, "base_delay": 0.01},
            fallback_config={"fallback_value": "fallback"}
        )
        def partially_failing_function():
            nonlocal call_count
            call_count += 1
            if call_count < 1:  # 只在第一次调用失败
                raise ValueError("Temporary failure")
            return "success"

        result = partially_failing_function()
        assert result == "success"
        assert call_count == 2


class TestLoggingIntegration:
    """日志集成测试"""

    def test_logging_context(self):
        """测试日志上下文管理器"""
        with LoggingContext(request_id="req_123", user_id="user_456", operation="test_op"):
            # 在这个上下文中，日志应该包含上下文信息
            main_logger.info("Test message in context")
            # 实际的上下文验证需要在日志输出中检查
            # 这里我们只测试上下文设置不抛出异常
            assert True

    def test_error_logger_integration(self):
        """测试错误日志记录器集成"""
        error = ValidationError("Test error", field_name="test_field")

        # 这应该不会抛出异常
        error_logger.log_error(error, {"additional": "context"})

    def test_audit_logger_integration(self):
        """测试审计日志记录器集成"""
        # 这应该不会抛出异常
        audit_logger.log_operation(
            operation="create_object",
            principal_id="user_123",
            resource_type="ObjectType",
            details={"name": "test_object"}
        )


class TestEdgeCasesAndErrorHandling:
    """边缘情况和错误处理测试"""

    def test_empty_error_collector(self):
        """测试空错误收集器"""
        collector = ErrorCollector()
        assert len(collector.to_dict_list()) == 0
        assert len(collector.get_by_severity(ErrorSeverity.HIGH)) == 0
        assert len(collector.get_by_category(ErrorCategory.VALIDATION)) == 0

    def test_exception_without_message(self):
        """测试没有消息的异常"""
        try:
            raise ValueError()
        except ValueError as e:
            handled = handle_exception(e)
            assert handled.message == "An unexpected error occurred"

    def test_circuit_breaker_without_failures(self):
        """测试没有失败的熔断器"""
        config = CircuitBreakerConfig(failure_threshold=5, recovery_timeout=1.0)
        breaker = CircuitBreaker(config)

        # 成功调用应该保持熔断器关闭
        for i in range(10):
            result = breaker.call(lambda: f"success_{i}")
            assert breaker.state == CircuitBreakerState.CLOSED
            assert breaker.failure_count == 0

    def test_retry_with_zero_attempts(self):
        """测试零次重试配置"""
        config = RetryConfig(max_attempts=1)  # 只有初始尝试
        retry = RetryMechanism(config)

        def failing_func():
            raise ValueError("Always fails")

        with pytest.raises(OntologyError):
            retry.execute_with_retry(failing_func)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])