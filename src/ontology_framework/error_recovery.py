# 本体框架错误恢复机制
# 提供重试、熔断、降级等错误恢复策略

import time
import asyncio
from typing import Any, Callable, Dict, List, Optional, TypeVar, Union, Type
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
import threading
from datetime import datetime, timedelta

from .exceptions import OntologyError, ErrorSeverity, ErrorCategory
from .logging_config import main_logger, error_logger, LoggingContext


T = TypeVar('T')


class RecoveryStrategy(Enum):
    """恢复策略"""
    RETRY = "retry"              # 重试
    CIRCUIT_BREAKER = "circuit_breaker"  # 熔断器
    FALLBACK = "fallback"        # 降级处理
    TIMEOUT = "timeout"          # 超时重试
    EXPONENTIAL_BACKOFF = "exponential_backoff"  # 指数退避


@dataclass
class RetryConfig:
    """重试配置"""
    max_attempts: int = 3
    base_delay: float = 1.0  # 基础延迟（秒）
    max_delay: float = 60.0   # 最大延迟（秒）
    exponential_base: float = 2.0  # 指数退避基数
    jitter: bool = True        # 添加随机抖动
    retry_on: List[Type[Exception]] = field(default_factory=lambda: [Exception])


@dataclass
class CircuitBreakerConfig:
    """熔断器配置"""
    failure_threshold: int = 5    # 失败阈值
    recovery_timeout: float = 60.0  # 恢复超时（秒）
    expected_exception: Type[Exception] = Exception
    success_threshold: int = 3     # 成功阈值（半开状态）


class CircuitBreakerState(Enum):
    """熔断器状态"""
    CLOSED = "closed"      # 关闭状态（正常）
    OPEN = "open"          # 打开状态（熔断）
    HALF_OPEN = "half_open"  # 半开状态（试探性恢复）


@dataclass
class FallbackConfig:
    """降级配置"""
    fallback_function: Optional[Callable] = None
    fallback_value: Any = None
    use_cache: bool = False
    cache_ttl: float = 300.0  # 缓存TTL（秒）


class CircuitBreaker:
    """熔断器实现"""

    def __init__(self, config: CircuitBreakerConfig):
        self.config = config
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self._lock = threading.Lock()

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """通过熔断器调用函数"""
        with self._lock:
            if self.state == CircuitBreakerState.OPEN:
                if self._should_attempt_reset():
                    self.state = CircuitBreakerState.HALF_OPEN
                    self.success_count = 0
                    main_logger.info("Circuit breaker transitioning to HALF_OPEN")
                else:
                    raise OntologyError(
                        f"Circuit breaker is OPEN for {func.__name__}",
                        error_code="CIRCUIT_BREAKER_OPEN",
                        category=ErrorCategory.SYSTEM,
                        severity=ErrorSeverity.HIGH,
                        context={
                            "failure_count": self.failure_count,
                            "time_until_retry": self._get_time_until_retry()
                        }
                    )

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.config.expected_exception as e:
            self._on_failure()
            raise

    def _should_attempt_reset(self) -> bool:
        """判断是否应该尝试重置熔断器"""
        if self.last_failure_time is None:
            return True
        time_since_failure = datetime.now() - self.last_failure_time
        return time_since_failure.total_seconds() >= self.config.recovery_timeout

    def _get_time_until_retry(self) -> float:
        """获取距离下次重试的时间"""
        if self.last_failure_time is None:
            return 0.0
        time_since_failure = datetime.now() - self.last_failure_time
        remaining = self.config.recovery_timeout - time_since_failure.total_seconds()
        return max(0.0, remaining)

    def _on_success(self):
        """成功时的处理"""
        with self._lock:
            if self.state == CircuitBreakerState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.config.success_threshold:
                    self.state = CircuitBreakerState.CLOSED
                    self.failure_count = 0
                    main_logger.info("Circuit breaker transitioning to CLOSED")
            else:
                self.failure_count = 0

    def _on_failure(self):
        """失败时的处理"""
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = datetime.now()

            if self.state == CircuitBreakerState.HALF_OPEN:
                self.state = CircuitBreakerState.OPEN
                main_logger.warning("Circuit breaker transitioning back to OPEN")
            elif (self.state == CircuitBreakerState.CLOSED and
                  self.failure_count >= self.config.failure_threshold):
                self.state = CircuitBreakerState.OPEN
                main_logger.warning(f"Circuit breaker transitioning to OPEN after {self.failure_count} failures")


class RetryMechanism:
    """重试机制"""

    def __init__(self, config: RetryConfig):
        self.config = config

    def execute_with_retry(self, func: Callable, *args, **kwargs) -> Any:
        """执行函数并在失败时重试"""
        last_exception = None

        for attempt in range(self.config.max_attempts):
            try:
                if attempt > 0:
                    delay = self._calculate_delay(attempt)
                    main_logger.info(f"Retrying operation (attempt {attempt + 1}/{self.config.max_attempts}) after {delay:.2f}s")
                    time.sleep(delay)

                result = func(*args, **kwargs)

                if attempt > 0:
                    main_logger.info(f"Operation succeeded on attempt {attempt + 1}")

                return result

            except Exception as e:
                last_exception = e

                # 检查是否应该重试这个异常
                if not self._should_retry(e):
                    main_logger.error(f"Exception {type(e).__name__} not configured for retry")
                    raise

                if attempt < self.config.max_attempts - 1:
                    error_logger.log_error(e, {
                        "retry_attempt": attempt + 1,
                        "max_attempts": self.config.max_attempts,
                        "next_delay": self._calculate_delay(attempt + 1)
                    })

        # 所有重试都失败了
        error_logger.log_error(last_exception, {
            "final_failure": True,
            "total_attempts": self.config.max_attempts
        })

        raise OntologyError(
            f"Operation failed after {self.config.max_attempts} attempts: {str(last_exception)}",
            error_code="RETRY_EXHAUSTED",
            category=ErrorCategory.SYSTEM,
            severity=ErrorSeverity.HIGH,
            cause=last_exception,
            context={
                "max_attempts": self.config.max_attempts,
                "final_exception": str(last_exception)
            }
        )

    def _calculate_delay(self, attempt: int) -> float:
        """计算延迟时间"""
        delay = self.config.base_delay * (self.config.exponential_base ** (attempt - 1))

        # 应用最大延迟限制
        delay = min(delay, self.config.max_delay)

        # 添加随机抖动
        if self.config.jitter:
            import random
            jitter_factor = 0.1 * delay
            delay += random.uniform(-jitter_factor, jitter_factor)

        return max(0, delay)

    def _should_retry(self, exception: Exception) -> bool:
        """判断是否应该重试异常"""
        return any(isinstance(exception, retry_type) for retry_type in self.config.retry_on)


class FallbackHandler:
    """降级处理器"""

    def __init__(self, config: FallbackConfig):
        self.config = config
        self._cache: Dict[str, Any] = {}
        self._cache_timestamps: Dict[str, datetime] = {}

    def execute_with_fallback(self, func: Callable, *args, **kwargs) -> Any:
        """执行函数，失败时使用降级策略"""
        cache_key = self._generate_cache_key(func, args, kwargs)

        # 检查缓存
        if self.config.use_cache and cache_key in self._cache:
            if self._is_cache_valid(cache_key):
                main_logger.info(f"Using cached fallback result for {func.__name__}")
                return self._cache[cache_key]
            else:
                # 缓存过期，删除
                del self._cache[cache_key]
                del self._cache_timestamps[cache_key]

        try:
            result = func(*args, **kwargs)

            # 缓存成功结果
            if self.config.use_cache:
                self._cache[cache_key] = result
                self._cache_timestamps[cache_key] = datetime.now()

            return result

        except Exception as e:
            error_logger.log_error(e, {
                "fallback_triggered": True,
                "function": func.__name__,
                "cache_hit": cache_key in self._cache
            })

            # 执行降级策略
            return self._execute_fallback(func, e, *args, **kwargs)

    def _generate_cache_key(self, func: Callable, args: tuple, kwargs: dict) -> str:
        """生成缓存键"""
        import hashlib
        key_data = f"{func.__module__}.{func.__name__}:{str(args)}:{str(sorted(kwargs.items()))}"
        return hashlib.md5(key_data.encode()).hexdigest()

    def _is_cache_valid(self, cache_key: str) -> bool:
        """检查缓存是否有效"""
        if cache_key not in self._cache_timestamps:
            return False

        age = datetime.now() - self._cache_timestamps[cache_key]
        return age.total_seconds() < self.config.cache_ttl

    def _execute_fallback(self, func: Callable, original_error: Exception, *args, **kwargs) -> Any:
        """执行降级逻辑"""
        if self.config.fallback_function:
            try:
                main_logger.info(f"Executing fallback function for {func.__name__}")
                return self.config.fallback_function(*args, **kwargs)
            except Exception as fallback_error:
                error_logger.log_error(fallback_error, {
                    "fallback_function_failed": True,
                    "original_function": func.__name__
                })

                # 如果降级函数也失败了，返回降级值
                if self.config.fallback_value is not None:
                    main_logger.warning(f"Using fallback value for {func.__name__}")
                    return self.config.fallback_value

                # 既没有降级函数也没有降级值，重新抛出原始错误
                raise original_error

        elif self.config.fallback_value is not None:
            main_logger.warning(f"Using fallback value for {func.__name__}")
            return self.config.fallback_value

        # 没有降级策略，重新抛出原始错误
        raise original_error


class ErrorRecoveryManager:
    """错误恢复管理器，统一管理各种恢复策略"""

    def __init__(self):
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.retry_mechanisms: Dict[str, RetryMechanism] = {}
        self.fallback_handlers: Dict[str, FallbackHandler] = {}

    def register_circuit_breaker(self, name: str, config: CircuitBreakerConfig):
        """注册熔断器"""
        self.circuit_breakers[name] = CircuitBreaker(config)
        main_logger.info(f"Registered circuit breaker: {name}")

    def register_retry_mechanism(self, name: str, config: RetryConfig):
        """注册重试机制"""
        self.retry_mechanisms[name] = RetryMechanism(config)
        main_logger.info(f"Registered retry mechanism: {name}")

    def register_fallback_handler(self, name: str, config: FallbackConfig):
        """注册降级处理器"""
        self.fallback_handlers[name] = FallbackHandler(config)
        main_logger.info(f"Registered fallback handler: {name}")

    def execute_with_protection(
        self,
        func: Callable,
        strategies: List[RecoveryStrategy],
        strategy_configs: Optional[Dict[str, Any]] = None,
        *args,
        **kwargs
    ) -> Any:
        """使用指定策略执行函数"""
        strategy_configs = strategy_configs or {}
        result = func
        context = {"original_function": func.__name__}

        # 按顺序应用策略
        for strategy in strategies:
            try:
                if strategy == RecoveryStrategy.CIRCUIT_BREAKER:
                    breaker_name = strategy_configs.get("circuit_breaker_name", "default")
                    if breaker_name in self.circuit_breakers:
                        result = self.circuit_breakers[breaker_name].call(result, *args, **kwargs)
                        context["circuit_breaker_applied"] = True

                elif strategy == RecoveryStrategy.RETRY:
                    retry_name = strategy_configs.get("retry_name", "default")
                    if retry_name in self.retry_mechanisms:
                        if callable(result):
                            result = lambda *a, **k: self.retry_mechanisms[retry_name].execute_with_retry(result, *a, **k)
                        else:
                            # 如果result不是函数，创建一个包装器
                            def wrapper(*a, **k):
                                return result
                            result = lambda *a, **k: self.retry_mechanisms[retry_name].execute_with_retry(wrapper, *a, **k)
                        context["retry_applied"] = True

                elif strategy == RecoveryStrategy.FALLBACK:
                    fallback_name = strategy_configs.get("fallback_name", "default")
                    if fallback_name in self.fallback_handlers:
                        if callable(result):
                            result = lambda *a, **k: self.fallback_handlers[fallback_name].execute_with_fallback(result, *a, **k)
                        else:
                            def wrapper(*a, **k):
                                return result
                            result = lambda *a, **k: self.fallback_handlers[fallback_name].execute_with_fallback(wrapper, *a, **k)
                        context["fallback_applied"] = True

            except Exception as e:
                error_logger.log_error(e, {
                    "recovery_strategy": strategy.value,
                    "function": func.__name__,
                    "context": context
                })
                raise

        # 如果result仍然是函数，调用它
        if callable(result):
            return result(*args, **kwargs)
        return result

    def get_status(self) -> Dict[str, Any]:
        """获取所有恢复组件的状态"""
        status = {
            "circuit_breakers": {},
            "retry_mechanisms": list(self.retry_mechanisms.keys()),
            "fallback_handlers": list(self.fallback_handlers.keys())
        }

        for name, breaker in self.circuit_breakers.items():
            status["circuit_breakers"][name] = {
                "state": breaker.state.value,
                "failure_count": breaker.failure_count,
                "success_count": breaker.success_count,
                "last_failure_time": breaker.last_failure_time.isoformat() if breaker.last_failure_time else None
            }

        return status


# 全局错误恢复管理器
recovery_manager = ErrorRecoveryManager()

# 默认配置
DEFAULT_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    base_delay=1.0,
    exponential_base=2.0,
    jitter=True
)

DEFAULT_CIRCUIT_BREAKER_CONFIG = CircuitBreakerConfig(
    failure_threshold=5,
    recovery_timeout=60.0,
    success_threshold=3
)

DEFAULT_FALLBACK_CONFIG = FallbackConfig(
    fallback_value=None,
    use_cache=False
)


# 装饰器
def with_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    retry_on: Optional[List[Type[Exception]]] = None,
    config_name: str = "default"
):
    """重试装饰器"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            config = RetryConfig(
                max_attempts=max_attempts,
                base_delay=base_delay,
                retry_on=retry_on or [Exception]
            )

            if config_name not in recovery_manager.retry_mechanisms:
                recovery_manager.register_retry_mechanism(config_name, config)

            return recovery_manager.retry_mechanisms[config_name].execute_with_retry(func, *args, **kwargs)
        return wrapper
    return decorator


def with_circuit_breaker(
    failure_threshold: int = 5,
    recovery_timeout: float = 60.0,
    config_name: str = "default"
):
    """熔断器装饰器"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            config = CircuitBreakerConfig(
                failure_threshold=failure_threshold,
                recovery_timeout=recovery_timeout
            )

            if config_name not in recovery_manager.circuit_breakers:
                recovery_manager.register_circuit_breaker(config_name, config)

            return recovery_manager.circuit_breakers[config_name].call(func, *args, **kwargs)
        return wrapper
    return decorator


def with_fallback(
    fallback_function: Optional[Callable] = None,
    fallback_value: Any = None,
    use_cache: bool = False,
    cache_ttl: float = 300.0,
    config_name: str = "default"
):
    """降级装饰器"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            config = FallbackConfig(
                fallback_function=fallback_function,
                fallback_value=fallback_value,
                use_cache=use_cache,
                cache_ttl=cache_ttl
            )

            if config_name not in recovery_manager.fallback_handlers:
                recovery_manager.register_fallback_handler(config_name, config)

            return recovery_manager.fallback_handlers[config_name].execute_with_fallback(func, *args, **kwargs)
        return wrapper
    return decorator


def combined_protection(
    strategies: List[RecoveryStrategy],
    retry_config: Optional[Dict[str, Any]] = None,
    circuit_breaker_config: Optional[Dict[str, Any]] = None,
    fallback_config: Optional[Dict[str, Any]] = None
):
    """组合保护装饰器"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            strategy_configs = {}

            # 根据策略设置配置
            if RecoveryStrategy.RETRY in strategies:
                retry_name = retry_config.get("name", "default") if retry_config else "default"
                strategy_configs["retry_name"] = retry_name

                if retry_name not in recovery_manager.retry_mechanisms:
                    config = RetryConfig(**(retry_config or {}))
                    recovery_manager.register_retry_mechanism(retry_name, config)

            if RecoveryStrategy.CIRCUIT_BREAKER in strategies:
                cb_name = circuit_breaker_config.get("name", "default") if circuit_breaker_config else "default"
                strategy_configs["circuit_breaker_name"] = cb_name

                if cb_name not in recovery_manager.circuit_breakers:
                    config = CircuitBreakerConfig(**(circuit_breaker_config or {}))
                    recovery_manager.register_circuit_breaker(cb_name, config)

            if RecoveryStrategy.FALLBACK in strategies:
                fb_name = fallback_config.get("name", "default") if fallback_config else "default"
                strategy_configs["fallback_name"] = fb_name

                if fb_name not in recovery_manager.fallback_handlers:
                    config = FallbackConfig(**(fallback_config or {}))
                    recovery_manager.register_fallback_handler(fb_name, config)

            return recovery_manager.execute_with_protection(
                func, strategies, strategy_configs, *args, **kwargs
            )
        return wrapper
    return decorator


# 初始化默认配置
recovery_manager.register_retry_mechanism("default", DEFAULT_RETRY_CONFIG)
recovery_manager.register_circuit_breaker("default", DEFAULT_CIRCUIT_BREAKER_CONFIG)
recovery_manager.register_fallback_handler("default", DEFAULT_FALLBACK_CONFIG)