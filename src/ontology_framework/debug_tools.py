# 本体框架调试工具
# 提供开发调试、性能分析和问题诊断的工具

import inspect
import time
import functools
from typing import Any, Callable, Dict, List, Optional, Union
from datetime import datetime
from dataclasses import dataclass, field
import json
from contextlib import contextmanager

from .logging_config import main_logger, performance_logger, LoggingContext
from .exceptions import OntologyError


@dataclass
class DebugInfo:
    """调试信息容器"""
    function_name: str
    execution_time: float = 0.0
    arguments: Dict[str, Any] = field(default_factory=dict)
    result: Any = None
    exception: Optional[Exception] = None
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    memory_usage: Optional[Dict[str, Any]] = None
    stack_trace: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "function_name": self.function_name,
            "execution_time": self.execution_time,
            "arguments": self._serialize_values(self.arguments),
            "result": self._serialize_values(self.result),
            "exception": str(self.exception) if self.exception else None,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "memory_usage": self.memory_usage,
            "stack_trace": self.stack_trace
        }

    def _serialize_values(self, value: Any) -> Any:
        """序列化值为JSON可兼容格式"""
        try:
            if hasattr(value, '__dict__'):
                return f"{value.__class__.__name__}({str(value)})"
            elif isinstance(value, (list, tuple)):
                return [self._serialize_values(item) for item in value]
            elif isinstance(value, dict):
                return {k: self._serialize_values(v) for k, v in value.items()}
            else:
                return str(value)
        except Exception:
            return f"<unserializable: {type(value).__name__}>"


class DebugSession:
    """调试会话管理器"""

    def __init__(self, name: str):
        self.name = name
        self.debug_infos: List[DebugInfo] = []
        self.session_start = datetime.now()
        self.context: Dict[str, Any] = {}

    def add_debug_info(self, debug_info: DebugInfo):
        """添加调试信息"""
        self.debug_infos.append(debug_info)

    def get_session_summary(self) -> Dict[str, Any]:
        """获取会话摘要"""
        total_time = sum(info.execution_time for info in self.debug_infos)
        successful_calls = sum(1 for info in self.debug_infos if info.exception is None)
        failed_calls = len(self.debug_infos) - successful_calls

        return {
            "session_name": self.name,
            "session_start": self.session_start.isoformat(),
            "total_calls": len(self.debug_infos),
            "successful_calls": successful_calls,
            "failed_calls": failed_calls,
            "success_rate": successful_calls / len(self.debug_infos) if self.debug_infos else 0,
            "total_execution_time": total_time,
            "average_execution_time": total_time / len(self.debug_infos) if self.debug_infos else 0,
            "context": self.context
        }

    def export_debug_data(self, filename: str = None) -> str:
        """导出调试数据"""
        debug_data = {
            "session_summary": self.get_session_summary(),
            "debug_infos": [info.to_dict() for info in self.debug_infos]
        }

        json_data = json.dumps(debug_data, indent=2, default=str)

        if filename:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(json_data)
            main_logger.info(f"Debug data exported to {filename}")

        return json_data


class DebugTracker:
    """调试追踪器，用于函数级别的调试"""

    def __init__(self, session: DebugSession = None):
        self.session = session
        self._active_debug_info: Optional[DebugInfo] = None

    @contextmanager
    def track_function(self, func_name: str, *args, **kwargs):
        """函数执行追踪上下文管理器"""
        debug_info = DebugInfo(
            function_name=func_name,
            arguments=self._extract_function_args(func_name, args, kwargs),
            start_time=datetime.now()
        )

        if self.session:
            self.session.add_debug_info(debug_info)

        self._active_debug_info = debug_info

        try:
            # 记录调用栈
            debug_info.stack_trace = "".join(
                f"File {frame.filename}, line {frame.lineno}, in {frame.function}\n"
                for frame in inspect.stack()[2:]  # 跳过当前框架和上下文管理器框架
            )

            start_time = time.time()
            yield debug_info

        except Exception as e:
            debug_info.exception = e
            main_logger.error(f"Exception in function {func_name}", exception=str(e))
            raise

        finally:
            end_time = time.time()
            debug_info.execution_time = end_time - start_time
            debug_info.end_time = datetime.now()

            # 记录内存使用情况
            try:
                import psutil
                process = psutil.Process()
                debug_info.memory_usage = {
                    "rss_mb": process.memory_info().rss / 1024 / 1024,
                    "vms_mb": process.memory_info().vms / 1024 / 1024
                }
            except ImportError:
                # psutil不可用，跳过内存统计
                pass
            except Exception as e:
                main_logger.warning(f"Could not collect memory usage: {e}")

        self._active_debug_info = None

    def _extract_function_args(self, func_name: str, args: tuple, kwargs: dict) -> Dict[str, Any]:
        """提取函数参数信息"""
        try:
            # 尝试获取函数签名
            frame = inspect.currentframe()
            while frame:
                if frame.f_code.co_name == func_name:
                    sig = inspect.signature(frame.f_code)
                    bound_args = sig.bind_partial(*args, **kwargs)
                    return dict(bound_args.arguments)
                frame = frame.f_back
        except Exception:
            # 如果无法提取签名信息，返回简化版本
            pass

        # 简化版本：只返回数量
        return {
            "args_count": len(args),
            "kwargs_keys": list(kwargs.keys()),
            "args_preview": [str(arg)[:100] for arg in args[:3]],
            "kwargs_preview": {k: str(v)[:100] for k, v in list(kwargs.items())[:3]}
        }


def debug_function(
    session: Optional[DebugSession] = None,
    include_args: bool = True,
    include_result: bool = False,
    log_performance: bool = True
):
    """
    函数调试装饰器

    Args:
        session: 调试会话
        include_args: 是否包含参数信息
        include_result: 是否包含返回值
        log_performance: 是否记录性能日志
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            tracker = DebugTracker(session)

            with tracker.track_function(func.__name__, *args, **kwargs) as debug_info:
                try:
                    result = func(*args, **kwargs)

                    if include_result:
                        debug_info.result = result

                    if log_performance:
                        performance_logger.log_operation_timing(
                            func.__name__,
                            debug_info.execution_time,
                            {
                                "args_count": len(args),
                                "kwargs_count": len(kwargs),
                                "success": True
                            }
                        )

                    return result

                except Exception as e:
                    if log_performance:
                        performance_logger.log_operation_timing(
                            func.__name__,
                            debug_info.execution_time,
                            {
                                "args_count": len(args),
                                "kwargs_count": len(kwargs),
                                "success": False,
                                "error_type": type(e).__name__
                            }
                        )
                    raise

        return wrapper
    return decorator


class PerformanceProfiler:
    """性能分析器"""

    def __init__(self):
        self.profiles: Dict[str, List[Dict[str, Any]]] = {}

    def profile_function(self, name: str = None):
        """函数性能分析装饰器"""
        def decorator(func: Callable) -> Callable:
            profile_name = name or f"{func.__module__}.{func.__name__}"

            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                start_time = time.time()
                start_memory = self._get_memory_usage()

                try:
                    result = func(*args, **kwargs)
                    success = True
                    return result
                except Exception as e:
                    success = False
                    raise
                finally:
                    end_time = time.time()
                    end_memory = self._get_memory_usage()

                    profile_data = {
                        "function": profile_name,
                        "execution_time": end_time - start_time,
                        "memory_delta": end_memory - start_memory if end_memory and start_memory else 0,
                        "timestamp": datetime.now().isoformat(),
                        "success": success,
                        "args_count": len(args),
                        "kwargs_count": len(kwargs)
                    }

                    if profile_name not in self.profiles:
                        self.profiles[profile_name] = []
                    self.profiles[profile_name].append(profile_data)

            return wrapper
        return decorator

    def _get_memory_usage(self) -> Optional[int]:
        """获取内存使用量（字节）"""
        try:
            import psutil
            process = psutil.Process()
            return process.memory_info().rss
        except ImportError:
            return None
        except Exception:
            return None

    def get_profile_summary(self, function_name: str = None) -> Dict[str, Any]:
        """获取性能分析摘要"""
        if function_name:
            profiles = self.profiles.get(function_name, [])
        else:
            # 合并所有函数的性能数据
            profiles = []
            for func_profiles in self.profiles.values():
                profiles.extend(func_profiles)

        if not profiles:
            return {"message": "No performance data available"}

        execution_times = [p["execution_time"] for p in profiles]
        memory_deltas = [p["memory_delta"] for p in profiles if p["memory_delta"] is not None]
        success_count = sum(1 for p in profiles if p["success"])

        return {
            "function_name": function_name or "all_functions",
            "call_count": len(profiles),
            "success_count": success_count,
            "success_rate": success_count / len(profiles),
            "execution_time": {
                "min": min(execution_times),
                "max": max(execution_times),
                "avg": sum(execution_times) / len(execution_times),
                "total": sum(execution_times)
            },
            "memory": {
                "min_delta": min(memory_deltas) if memory_deltas else None,
                "max_delta": max(memory_deltas) if memory_deltas else None,
                "avg_delta": sum(memory_deltas) / len(memory_deltas) if memory_deltas else None,
                "total_delta": sum(memory_deltas) if memory_deltas else None
            },
            "first_call": profiles[0]["timestamp"],
            "last_call": profiles[-1]["timestamp"]
        }


class Inspector:
    """代码检查器，用于分析代码质量和潜在问题"""

    def __init__(self, ontology_instance: Any):
        self.ontology = ontology_instance

    def inspect_object_types(self) -> Dict[str, Any]:
        """检查对象类型定义"""
        inspection = {
            "object_types_count": len(self.ontology.object_types),
            "object_types": {},
            "issues": []
        }

        for name, obj_type in self.ontology.object_types.items():
            type_info = {
                "api_name": obj_type.api_name,
                "display_name": obj_type.display_name,
                "properties_count": len(obj_type.properties),
                "derived_properties_count": len(obj_type.derived_properties),
                "has_primary_key": bool(obj_type.primary_key),
                "has_permissions": obj_type.permissions is not None,
                "has_description": obj_type.description is not None
            }

            # 检查潜在问题
            if not obj_type.primary_key:
                inspection["issues"].append(f"Object type '{name}' has no primary key")

            if not obj_type.properties and not obj_type.derived_properties:
                inspection["issues"].append(f"Object type '{name}' has no properties")

            if obj_type.api_name != name:
                inspection["issues"].append(f"Object type '{name}' API name mismatch")

            inspection["object_types"][name] = type_info

        return inspection

    def inspect_object_instances(self) -> Dict[str, Any]:
        """检查对象实例"""
        inspection = {
            "total_objects": 0,
            "objects_by_type": {},
            "issues": []
        }

        for type_name, objects in self.ontology._object_store.items():
            type_info = {
                "count": len(objects),
                "sample_objects": list(objects.keys())[:5]  # 只显示前5个
            }
            inspection["objects_by_type"][type_name] = type_info
            inspection["total_objects"] += len(objects)

        return inspection

    def inspect_links(self) -> Dict[str, Any]:
        """检查链接关系"""
        inspection = {
            "total_links": len(self.ontology._links),
            "link_types": {},
            "issues": []
        }

        link_type_counts = {}
        for link in self.ontology._links:
            link_type = link.link_type_api_name
            link_type_counts[link_type] = link_type_counts.get(link_type, 0) + 1

        for link_type, count in link_type_counts.items():
            inspection["link_types"][link_type] = {"count": count}

        return inspection

    def get_full_inspection_report(self) -> Dict[str, Any]:
        """获取完整的检查报告"""
        return {
            "timestamp": datetime.now().isoformat(),
            "object_types": self.inspect_object_types(),
            "object_instances": self.inspect_object_instances(),
            "links": self.inspect_links(),
            "system_health": self._assess_system_health()
        }

    def _assess_system_health(self) -> Dict[str, Any]:
        """评估系统健康状况"""
        health_score = 100
        issues = []

        # 检查对象类型健康度
        object_types = self.inspect_object_types()
        if object_types["issues"]:
            health_score -= len(object_types["issues"]) * 5
            issues.extend(object_types["issues"])

        # 检查链接健康度
        links = self.inspect_links()
        if links["total_links"] == 0 and len(self.ontology.object_types) > 1:
            health_score -= 10
            issues.append("No links defined between object types")

        # 检查对象实例健康度
        instances = self.inspect_object_instances()
        if instances["total_objects"] == 0:
            health_score -= 5
            issues.append("No object instances found")

        health_status = "excellent"
        if health_score < 70:
            health_status = "poor"
        elif health_score < 85:
            health_status = "fair"
        elif health_score < 95:
            health_status = "good"

        return {
            "health_score": max(0, health_score),
            "health_status": health_status,
            "issues": issues,
            "recommendations": self._generate_recommendations(issues)
        }

    def _generate_recommendations(self, issues: List[str]) -> List[str]:
        """基于问题生成建议"""
        recommendations = []

        if any("primary key" in issue for issue in issues):
            recommendations.append("Add primary keys to object types for better data integrity")

        if any("no properties" in issue for issue in issues):
            recommendations.append("Define properties for object types to make them useful")

        if any("No links" in issue for issue in issues):
            recommendations.append("Define relationships between object types using link types")

        if any("No object instances" in issue for issue in issues):
            recommendations.append("Create some object instances to test the system")

        return recommendations


# 全局调试会话
current_debug_session: Optional[DebugSession] = None

# 全局性能分析器
performance_profiler = PerformanceProfiler()


def start_debug_session(name: str) -> DebugSession:
    """开始新的调试会话"""
    global current_debug_session
    current_debug_session = DebugSession(name)
    main_logger.info(f"Started debug session: {name}")
    return current_debug_session


def end_debug_session() -> Dict[str, Any]:
    """结束当前调试会话"""
    global current_debug_session
    if current_debug_session:
        summary = current_debug_session.get_session_summary()
        main_logger.info(f"Ended debug session: {current_debug_session.name}")
        current_debug_session = None
        return summary
    return {"message": "No active debug session"}


def get_current_debug_session() -> Optional[DebugSession]:
    """获取当前调试会话"""
    return current_debug_session


def export_debug_data(filename: str = None) -> Optional[str]:
    """导出调试数据"""
    global current_debug_session
    if current_debug_session:
        return current_debug_session.export_debug_data(filename)
    return None


# 便捷函数
def debug(session: Optional[DebugSession] = None):
    """便捷的调试装饰器"""
    return debug_function(session=session)


def profile(name: str = None):
    """便捷的性能分析装饰器"""
    return performance_profiler.profile_function(name)


def inspect() -> Dict[str, Any]:
    """便捷的系统检查函数"""
    # 这里需要一个ontology实例，实际使用时应该传入
    # return Inspector(ontology_instance).get_full_inspection_report()
    return {"message": "Pass ontology instance to inspect() function"}