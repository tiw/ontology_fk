"""
性能监控系统

提供实时性能监控、告警和统计功能。
"""

import time
import threading
import statistics
from typing import Dict, List, Any, Optional, Callable, Union
from dataclasses import dataclass, field
from collections import deque, defaultdict
from enum import Enum
import json
from contextlib import contextmanager


class AlertSeverity(Enum):
    """告警严重程度"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class MetricPoint:
    """指标数据点"""
    timestamp: float
    value: float
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class AlertRule:
    """告警规则"""
    name: str
    metric_name: str
    threshold: float
    operator: str = ">"  # >, <, >=, <=, ==, !=
    severity: AlertSeverity = AlertSeverity.MEDIUM
    duration: float = 0.0  # 持续时间(秒)，0表示立即告警
    message_template: str = "{metric_name} {operator} {threshold}: {value}"

    def evaluate(self, value: float) -> bool:
        """评估是否触发告警"""
        if self.operator == ">":
            return value > self.threshold
        elif self.operator == "<":
            return value < self.threshold
        elif self.operator == ">=":
            return value >= self.threshold
        elif self.operator == "<=":
            return value <= self.threshold
        elif self.operator == "==":
            return value == self.threshold
        elif self.operator == "!=":
            return value != self.threshold
        return False


@dataclass
class Alert:
    """告警信息"""
    rule_name: str
    metric_name: str
    current_value: float
    threshold: float
    severity: AlertSeverity
    message: str
    timestamp: float
    resolved: bool = False
    resolved_timestamp: Optional[float] = None


class TimeSeriesData:
    """时间序列数据存储"""

    def __init__(self, max_points: int = 10000):
        self.max_points = max_points
        self.data: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_points))

    def add_point(self, metric_name: str, value: float, tags: Dict[str, str] = None):
        """添加数据点"""
        point = MetricPoint(
            timestamp=time.time(),
            value=value,
            tags=tags or {}
        )
        self.data[metric_name].append(point)

    def get_recent_points(self, metric_name: str, count: int = 100) -> List[MetricPoint]:
        """获取最近的数据点"""
        return list(self.data[metric_name])[-count:]

    def get_points_in_range(self, metric_name: str, start_time: float, end_time: float) -> List[MetricPoint]:
        """获取指定时间范围内的数据点"""
        points = []
        for point in self.data[metric_name]:
            if start_time <= point.timestamp <= end_time:
                points.append(point)
        return points

    def get_latest_value(self, metric_name: str) -> Optional[float]:
        """获取最新值"""
        if self.data[metric_name]:
            return self.data[metric_name][-1].value
        return None

    def get_statistics(self, metric_name: str, duration_seconds: int = 300) -> Dict[str, float]:
        """获取统计信息"""
        cutoff_time = time.time() - duration_seconds
        recent_points = [
            point.value for point in self.data[metric_name]
            if point.timestamp >= cutoff_time
        ]

        if not recent_points:
            return {}

        return {
            'count': len(recent_points),
            'min': min(recent_points),
            'max': max(recent_points),
            'avg': statistics.mean(recent_points),
            'median': statistics.median(recent_points),
            'p95': statistics.quantiles(recent_points, n=20)[18] if len(recent_points) >= 20 else max(recent_points),
            'p99': statistics.quantiles(recent_points, n=100)[98] if len(recent_points) >= 100 else max(recent_points)
        }


class AlertManager:
    """告警管理器"""

    def __init__(self):
        self.rules: Dict[str, AlertRule] = {}
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_history: List[Alert] = []
        self.alert_handlers: List[Callable[[Alert], None]] = []
        self._lock = threading.RLock()

    def add_rule(self, rule: AlertRule):
        """添加告警规则"""
        with self._lock:
            self.rules[rule.name] = rule

    def remove_rule(self, rule_name: str):
        """移除告警规则"""
        with self._lock:
            self.rules.pop(rule_name, None)
            self.active_alerts.pop(rule_name, None)

    def add_handler(self, handler: Callable[[Alert], None]):
        """添加告警处理器"""
        self.alert_handlers.append(handler)

    def evaluate_rules(self, metrics: Dict[str, float]):
        """评估告警规则"""
        current_time = time.time()

        with self._lock:
            for rule_name, rule in self.rules.items():
                if rule.metric_name not in metrics:
                    continue

                current_value = metrics[rule.metric_name]

                if rule.evaluate(current_value):
                    # 触发告警条件
                    if rule_name not in self.active_alerts:
                        # 新告警
                        alert = Alert(
                            rule_name=rule_name,
                            metric_name=rule.metric_name,
                            current_value=current_value,
                            threshold=rule.threshold,
                            severity=rule.severity,
                            message=rule.message_template.format(
                                metric_name=rule.metric_name,
                                operator=rule.operator,
                                threshold=rule.threshold,
                                value=current_value
                            ),
                            timestamp=current_time
                        )

                        self.active_alerts[rule_name] = alert
                        self.alert_history.append(alert)

                        # 发送告警
                        for handler in self.alert_handlers:
                            try:
                                handler(alert)
                            except Exception as e:
                                print(f"Alert handler error: {e}")

                else:
                    # 恢复正常
                    if rule_name in self.active_alerts:
                        alert = self.active_alerts[rule_name]
                        alert.resolved = True
                        alert.resolved_timestamp = current_time

                        del self.active_alerts[rule_name]

                        # 发送恢复通知
                        for handler in self.alert_handlers:
                            try:
                                handler(alert)
                            except Exception as e:
                                print(f"Alert handler error: {e}")

    def get_active_alerts(self) -> List[Alert]:
        """获取活跃告警"""
        with self._lock:
            return list(self.active_alerts.values())

    def get_alert_history(self, limit: int = 100) -> List[Alert]:
        """获取告警历史"""
        with self._lock:
            return self.alert_history[-limit:]


class PerformanceMonitor:
    """性能监控器"""

    def __init__(self, sample_interval: float = 1.0):
        self.sample_interval = sample_interval
        self.metrics_data = TimeSeriesData()
        self.alert_manager = AlertManager()
        self.custom_metrics: Dict[str, Callable[[], float]] = {}

        # 内置指标
        self.builtin_metrics = {
            'query_duration_ms',
            'memory_usage_mb',
            'cache_hit_rate',
            'objects_count',
            'operations_per_second',
            'error_rate'
        }

        # 监控状态
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._lock = threading.RLock()

        # 设置默认告警规则
        self._setup_default_alerts()

    def start_monitoring(self):
        """开始监控"""
        with self._lock:
            if self._monitoring:
                return

            self._monitoring = True
            self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self._monitor_thread.start()

    def stop_monitoring(self):
        """停止监控"""
        with self._lock:
            self._monitoring = False
            if self._monitor_thread:
                self._monitor_thread.join(timeout=5.0)

    def _monitor_loop(self):
        """监控循环"""
        while self._monitoring:
            try:
                # 收集指标
                metrics = self._collect_metrics()

                # 存储指标
                for metric_name, value in metrics.items():
                    self.metrics_data.add_point(metric_name, value)

                # 评估告警
                self.alert_manager.evaluate_rules(metrics)

                time.sleep(self.sample_interval)

            except Exception as e:
                print(f"Monitor loop error: {e}")
                time.sleep(self.sample_interval)

    def _collect_metrics(self) -> Dict[str, float]:
        """收集指标"""
        metrics = {}

        # 收集自定义指标
        for metric_name, metric_func in self.custom_metrics.items():
            try:
                value = metric_func()
                if value is not None:
                    metrics[metric_name] = value
            except Exception as e:
                print(f"Error collecting metric {metric_name}: {e}")

        # 收集系统指标
        try:
            import psutil
            process = psutil.Process()

            metrics['memory_usage_mb'] = process.memory_info().rss / 1024 / 1024
            metrics['cpu_percent'] = process.cpu_percent()

        except ImportError:
            pass

        return metrics

    def _setup_default_alerts(self):
        """设置默认告警规则"""
        default_rules = [
            AlertRule(
                name="high_memory_usage",
                metric_name="memory_usage_mb",
                threshold=1024.0,  # 1GB
                operator=">",
                severity=AlertSeverity.HIGH,
                message="Memory usage too high: {value:.2f} MB"
            ),
            AlertRule(
                name="high_query_duration",
                metric_name="query_duration_ms",
                threshold=1000.0,  # 1秒
                operator=">",
                severity=AlertSeverity.MEDIUM,
                message="Query duration too long: {value:.2f} ms"
            ),
            AlertRule(
                name="low_cache_hit_rate",
                metric_name="cache_hit_rate",
                threshold=0.7,  # 70%
                operator="<",
                severity=AlertSeverity.MEDIUM,
                message="Cache hit rate too low: {value:.2%}"
            ),
            AlertRule(
                name="high_error_rate",
                metric_name="error_rate",
                threshold=0.05,  # 5%
                operator=">",
                severity=AlertSeverity.HIGH,
                message="Error rate too high: {value:.2%}"
            )
        ]

        for rule in default_rules:
            self.alert_manager.add_rule(rule)

    def add_custom_metric(self, metric_name: str, metric_func: Callable[[], float]):
        """添加自定义指标"""
        with self._lock:
            self.custom_metrics[metric_name] = metric_func

    def record_metric(self, metric_name: str, value: float, tags: Dict[str, str] = None):
        """记录指标"""
        self.metrics_data.add_point(metric_name, value, tags)

    @contextmanager
    def track_operation(self, operation_name: str, tags: Dict[str, str] = None):
        """操作性能跟踪"""
        start_time = time.perf_counter()

        try:
            yield
            success = True
        except Exception:
            success = False
            raise
        finally:
            duration = (time.perf_counter() - start_time) * 1000  # ms

            # 记录操作时长
            metric_name = f"{operation_name}_duration_ms"
            self.record_metric(metric_name, duration, tags)

            # 记录成功/失败
            status_metric = f"{operation_name}_{'success' if success else 'error'}"
            self.record_metric(status_metric, 1, tags)

    def get_metric_statistics(self, metric_name: str, duration_seconds: int = 300) -> Dict[str, float]:
        """获取指标统计信息"""
        return self.metrics_data.get_statistics(metric_name, duration_seconds)

    def get_dashboard_data(self) -> Dict[str, Any]:
        """获取仪表板数据"""
        dashboard = {
            'timestamp': time.time(),
            'metrics': {},
            'alerts': [],
            'summary': {}
        }

        # 收集最新指标值
        for metric_name in self.builtin_metrics.union(self.custom_metrics.keys()):
            latest_value = self.metrics_data.get_latest_value(metric_name)
            if latest_value is not None:
                stats = self.metrics_data.get_statistics(metric_name)
                dashboard['metrics'][metric_name] = {
                    'current': latest_value,
                    'stats': stats
                }

        # 获取活跃告警
        dashboard['alerts'] = [
            {
                'rule_name': alert.rule_name,
                'metric_name': alert.metric_name,
                'severity': alert.severity.value,
                'message': alert.message,
                'timestamp': alert.timestamp
            }
            for alert in self.alert_manager.get_active_alerts()
        ]

        # 生成摘要
        dashboard['summary'] = {
            'total_metrics': len(dashboard['metrics']),
            'active_alerts': len(dashboard['alerts']),
            'monitoring_active': self._monitoring
        }

        return dashboard

    def export_metrics(self, format: str = "json", duration_seconds: int = 3600) -> str:
        """导出指标数据"""
        cutoff_time = time.time() - duration_seconds

        exported_data = {
            'export_time': time.time(),
            'duration_seconds': duration_seconds,
            'metrics': {}
        }

        for metric_name in self.builtin_metrics.union(self.custom_metrics.keys()):
            points = self.metrics_data.get_points_in_range(metric_name, cutoff_time, time.time())
            if points:
                exported_data['metrics'][metric_name] = [
                    {
                        'timestamp': point.timestamp,
                        'value': point.value,
                        'tags': point.tags
                    }
                    for point in points
                ]

        if format.lower() == "json":
            return json.dumps(exported_data, indent=2)
        else:
            raise ValueError(f"Unsupported export format: {format}")


class RealtimeMonitor:
    """实时监控面板"""

    def __init__(self, monitor: PerformanceMonitor):
        self.monitor = monitor
        self.update_callbacks: List[Callable[[Dict[str, Any]], None]] = []
        self._auto_refresh = False
        self._refresh_interval = 5.0  # 5秒
        self._refresh_thread: Optional[threading.Thread] = None

    def start_auto_refresh(self):
        """开始自动刷新"""
        if self._auto_refresh:
            return

        self._auto_refresh = True
        self._refresh_thread = threading.Thread(target=self._refresh_loop, daemon=True)
        self._refresh_thread.start()

    def stop_auto_refresh(self):
        """停止自动刷新"""
        self._auto_refresh = False
        if self._refresh_thread:
            self._refresh_thread.join(timeout=5.0)

    def _refresh_loop(self):
        """刷新循环"""
        while self._auto_refresh:
            try:
                dashboard_data = self.monitor.get_dashboard_data()

                # 调用更新回调
                for callback in self.update_callbacks:
                    try:
                        callback(dashboard_data)
                    except Exception as e:
                        print(f"Dashboard update callback error: {e}")

                time.sleep(self._refresh_interval)

            except Exception as e:
                print(f"Dashboard refresh error: {e}")
                time.sleep(self._refresh_interval)

    def add_update_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """添加更新回调"""
        self.update_callbacks.append(callback)

    def get_current_dashboard(self) -> Dict[str, Any]:
        """获取当前仪表板数据"""
        return self.monitor.get_dashboard_data()

    def generate_simple_report(self) -> str:
        """生成简单的文本报告"""
        dashboard = self.get_current_dashboard()

        report = ["Real-time Performance Monitor Report", "=" * 50, ""]
        report.append(f"Generated at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"Monitoring Status: {'Active' if self.monitor._monitoring else 'Inactive'}")
        report.append("")

        # 指标概览
        report.append("Metrics Overview:")
        for metric_name, metric_data in dashboard['metrics'].items():
            current = metric_data['current']
            stats = metric_data['stats']

            report.append(f"  {metric_name}:")
            report.append(f"    Current: {current:.2f}")
            if 'avg' in stats:
                report.append(f"    Average (5min): {stats['avg']:.2f}")
            if 'p95' in stats:
                report.append(f"    P95 (5min): {stats['p95']:.2f}")
            report.append("")

        # 告警信息
        if dashboard['alerts']:
            report.append("Active Alerts:")
            for alert in dashboard['alerts']:
                severity_icon = {"low": "🔵", "medium": "🟡", "high": "🟠", "critical": "🔴"}[alert['severity']]
                report.append(f"  {severity_icon} [{alert['severity'].upper()}] {alert['rule_name']}")
                report.append(f"    {alert['message']}")
                report.append("")
        else:
            report.append("✅ No active alerts")
            report.append("")

        return "\n".join(report)


# 便捷的装饰器和函数
def monitor_performance(monitor: PerformanceMonitor, operation_name: str = None):
    """性能监控装饰器"""
    def decorator(func: Callable):
        nonlocal operation_name
        if operation_name is None:
            operation_name = f"{func.__module__}.{func.__name__}"

        def wrapper(*args, **kwargs):
            with monitor.track_operation(operation_name):
                return func(*args, **kwargs)
        return wrapper
    return decorator


def create_default_monitor() -> PerformanceMonitor:
    """创建默认监控器"""
    monitor = PerformanceMonitor()

    # 添加控制台告警处理器
    def console_alert_handler(alert: Alert):
        severity_icon = {
            AlertSeverity.LOW: "🔵",
            AlertSeverity.MEDIUM: "🟡",
            AlertSeverity.HIGH: "🟠",
            AlertSeverity.CRITICAL: "🔴"
        }

        if not alert.resolved:
            print(f"{severity_icon[alert.severity]} ALERT: {alert.message}")
        else:
            print(f"✅ RESOLVED: {alert.rule_name}")

    monitor.alert_manager.add_handler(console_alert_handler)

    return monitor