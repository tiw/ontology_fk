"""
优化版本的核心模块

集成了性能优化功能的本体框架核心实现。
"""

import threading
import time
import weakref
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Type

from .core import (
    ActionContext,
    ActionType,
    Link,
    LinkType,
    ObjectInstance,
    ObjectType,
)
from .core import Ontology as BaseOntology
from .core import (
    PropertyType,
)
from .performance import (
    IndexManager, CacheManager, PerformanceMonitor,
    cached, performance_monitored
)


class OptimizedObjectInstance(ObjectInstance):
    """优化版本的对象实例"""

    def __init__(
        self,
        object_type_api_name: str,
        primary_key: Any,
        property_values: Dict[str, Any] = None,
        ontology: "OptimizedOntology" = None,
        lazy_loaded: bool = False,
    ):

        super().__init__(object_type_api_name, primary_key, property_values)
        self._ontology = ontology
        self._lazy_loaded = lazy_loaded
        self._derived_properties_cache: Dict[str, Any] = {}
        self._cache_timestamps: Dict[str, float] = {}
        self._last_accessed = time.time()

    @property
    def last_accessed(self) -> float:
        """获取最后访问时间"""
        self._last_accessed = time.time()
        return self._last_accessed

    def get(self, property_name: str) -> Any:
        """获取属性值，支持缓存和延迟加载"""
        self.last_accessed  # 更新访问时间

        # 1. 检查标准属性
        if property_name in self.property_values:
            return self.property_values[property_name]

        # 2. 检查派生属性缓存
        if property_name in self._derived_properties_cache:
            # 检查缓存是否过期（5分钟）
            if time.time() - self._cache_timestamps.get(property_name, 0) < 300:
                return self._derived_properties_cache[property_name]
            else:
                # 缓存过期，清除
                del self._derived_properties_cache[property_name]
                del self._cache_timestamps[property_name]

        # 3. 计算派生属性
        if self._ontology and not self._lazy_loaded:
            return self._compute_derived_property(property_name)

        return None

    def _compute_derived_property(self, property_name: str) -> Any:
        """计算派生属性值"""
        obj_type = self._ontology.get_object_type(self.object_type_api_name)
        if not obj_type or property_name not in obj_type.derived_properties:
            return None

        derived_prop = obj_type.derived_properties[property_name]

        # 检查函数是否存在
        func_def = self._ontology.functions.get(derived_prop.backing_function_api_name)
        if not func_def:
            raise ValueError(
                f"Backing function {derived_prop.backing_function_api_name} not found"
            )

        # 查找目标参数
        target_arg_name = self._find_target_argument(func_def)

        if target_arg_name:
            # 执行函数
            with self._ontology.performance_monitor.track_operation(
                "derived_property_calculation"
            ):
                result = self._ontology.execute_function(
                    derived_prop.backing_function_api_name, **{target_arg_name: self}
                )

            # 缓存结果
            self._derived_properties_cache[property_name] = result
            self._cache_timestamps[property_name] = time.time()

            return result

        return None

    def _find_target_argument(self, func_def) -> Optional[str]:
        """查找目标参数名"""
        from .core import ObjectTypeSpec

        for arg_name, arg_def in func_def.inputs.items():
            if (
                hasattr(arg_def, "type")
                and isinstance(arg_def.type, ObjectTypeSpec)
                and arg_def.type.object_type_api_name == self.object_type_api_name
            ):
                return arg_name

        # 回退策略
        if "object" in func_def.inputs:
            return "object"
        elif "instance" in func_def.inputs:
            return "instance"

        return None

    def invalidate_cache(self, property_name: str = None):
        """使缓存失效"""
        if property_name:
            self._derived_properties_cache.pop(property_name, None)
            self._cache_timestamps.pop(property_name, None)
        else:
            self._derived_properties_cache.clear()
            self._cache_timestamps.clear()

    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        return {
            "cached_properties": len(self._derived_properties_cache),
            "cache_keys": list(self._derived_properties_cache.keys()),
            "last_accessed": self._last_accessed,
        }


class OptimizedObjectSet:
    """优化版本的对象集合"""

    def __init__(
        self,
        object_type: ObjectType,
        objects: List[OptimizedObjectInstance] = None,
        ontology: "OptimizedOntology" = None,
    ):
        self.object_type = object_type
        self._objects = objects or []
        self._ontology = ontology
        self._filters = []
        self._cached_results: Dict[str, List[OptimizedObjectInstance]] = {}
        self._cache_timestamps: Dict[str, float] = {}

    @contextmanager
    def _measure_query(self, query_type: str):
        """测量查询性能"""
        if self._ontology and hasattr(self._ontology, "performance_monitor"):
            with self._ontology.performance_monitor.track_operation(
                f"object_set_{query_type}"
            ):
                yield
        else:
            yield

    def filter(self, property_name: str, value: Any) -> "OptimizedObjectSet":
        """过滤对象，支持索引优化"""
        with self._measure_query("filter"):
            # 如果有索引管理器，使用索引查询
            if self._ontology and hasattr(self._ontology, "index_manager"):
                index_key = f"{self.object_type.api_name}.{property_name}"
                if index_key in self._ontology.index_manager.property_index or any(
                    f"{self.object_type.api_name}.composite." in key
                    and property_name in key
                    for key in self._ontology.index_manager.composite_index
                ):

                    # 使用索引查询
                    matching_pks = self._ontology.index_manager.query_with_index(
                        self.object_type.api_name, {property_name: value}
                    )
                    matching_objects = (
                        self._ontology.index_manager.find_objects_by_primary_key(
                            self.object_type.api_name, list(matching_pks)
                        )
                    )
                    return OptimizedObjectSet(
                        self.object_type, matching_objects, self._ontology
                    )

            # 回退到内存过滤
            cache_key = f"filter_{property_name}_{value}"
            cached_result = self._get_cached_result(cache_key)
            if cached_result is not None:
                return OptimizedObjectSet(
                    self.object_type, cached_result, self._ontology
                )

            filtered_objects = [
                obj for obj in self._objects if obj.get(property_name) == value
            ]

            self._cache_result(cache_key, filtered_objects)
            return OptimizedObjectSet(
                self.object_type, filtered_objects, self._ontology
            )

    def search_around(self, link_type_api_name: str, **filters) -> "OptimizedObjectSet":
        """关系导航查询，使用索引优化"""
        if not self._ontology:
            raise ValueError("Ontology context is required for search_around")

        with self._measure_query("search_around"):
            link_type = self._ontology.get_link_type(link_type_api_name)
            if not link_type:
                raise ValueError(f"Link type {link_type_api_name} not found")

            # 确定查询方向
            direction = None
            target_type_name = None

            if link_type.source_object_type == self.object_type.api_name:
                direction = "forward"
                target_type_name = link_type.target_object_type
            elif link_type.target_object_type == self.object_type.api_name:
                direction = "reverse"
                target_type_name = link_type.source_object_type
            else:
                raise ValueError(
                    f"Link type {link_type_api_name} does not connect to {self.object_type.api_name}"
                )

            target_object_type = self._ontology.get_object_type(target_type_name)
            if not target_object_type:
                raise ValueError(f"Target object type {target_type_name} not found")

            # 使用索引查询相关对象
            current_pks = {obj.primary_key_value for obj in self._objects}

            if hasattr(self._ontology, "index_manager"):
                related_pks = self._ontology.index_manager.get_related_objects(
                    link_type_api_name, list(current_pks), direction
                )

                # 合并所有相关主键
                all_related_pks = set()
                for pk, related_set in related_pks.items():
                    all_related_pks.update(related_set)
            else:
                # 回退到传统方法
                all_related_pks = self._traditional_search_around(
                    link_type_api_name, current_pks, direction
                )

            # 获取目标对象
            target_objects = []
            if hasattr(self._ontology, "index_manager"):
                target_objects = (
                    self._ontology.index_manager.find_objects_by_primary_key(
                        target_type_name, list(all_related_pks)
                    )
                )
            else:
                all_potential_targets = self._ontology.get_objects_of_type(
                    target_type_name
                )
                target_objects = [
                    obj
                    for obj in all_potential_targets
                    if obj.primary_key_value in all_related_pks
                ]

            # 应用额外过滤条件
            if filters:
                filtered_target_objects = []
                for obj in target_objects:
                    match = True
                    for prop, val in filters.items():
                        if obj.get(prop) != val:
                            match = False
                            break
                    if match:
                        filtered_target_objects.append(obj)
                target_objects = filtered_target_objects

            return OptimizedObjectSet(
                target_object_type, target_objects, self._ontology
            )

    def _traditional_search_around(
        self, link_type_api_name: str, current_pks: Set[Any], direction: str
    ) -> Set[Any]:
        """传统的搜索周围方法（回退方案）"""
        related_target_pks = set()
        all_links = self._ontology.get_all_links()

        for link in all_links:
            if link.link_type_api_name == link_type_api_name:
                if direction == "forward" and link.source_primary_key in current_pks:
                    related_target_pks.add(link.target_primary_key)
                elif direction == "reverse" and link.target_primary_key in current_pks:
                    related_target_pks.add(link.source_primary_key)

        return related_target_pks

    def all(self) -> List[OptimizedObjectInstance]:
        """获取所有对象"""
        with self._measure_query("all"):
            return self._objects.copy()

    def aggregate(self, property_name: str, function: str) -> float:
        """聚合操作"""
        with self._measure_query("aggregate"):
            values = [
                obj.get(property_name)
                for obj in self._objects
                if obj.get(property_name) is not None
            ]

            if not values:
                return 0.0

            if function == "sum":
                return sum(values)
            elif function == "avg":
                return sum(values) / len(values)
            elif function == "max":
                return max(values)
            elif function == "min":
                return min(values)
            elif function == "count":
                return len(values)
            else:
                raise ValueError(f"Unknown aggregation function: {function}")

    def count(self) -> int:
        """对象数量"""
        return len(self._objects)

    def first(self) -> Optional[OptimizedObjectInstance]:
        """获取第一个对象"""
        return self._objects[0] if self._objects else None

    def _get_cached_result(
        self, cache_key: str
    ) -> Optional[List[OptimizedObjectInstance]]:
        """获取缓存结果"""
        if cache_key in self._cached_results:
            # 检查缓存是否过期（2分钟）
            if time.time() - self._cache_timestamps.get(cache_key, 0) < 120:
                return self._cached_results[cache_key]
            else:
                del self._cached_results[cache_key]
                del self._cache_timestamps[cache_key]

        return None

    def _cache_result(self, cache_key: str, result: List[OptimizedObjectInstance]):
        """缓存结果"""
        # 限制缓存大小
        if len(self._cached_results) > 100:
            # 删除最旧的缓存
            oldest_key = min(
                self._cache_timestamps.keys(), key=lambda k: self._cache_timestamps[k]
            )
            del self._cached_results[oldest_key]
            del self._cache_timestamps[oldest_key]

        self._cached_results[cache_key] = result.copy()
        self._cache_timestamps[cache_key] = time.time()

    def clear_cache(self):
        """清除缓存"""
        self._cached_results.clear()
        self._cache_timestamps.clear()


class OptimizedOntology(BaseOntology):
    """优化版本的本体管理器"""

    def __init__(self, enable_monitoring: bool = True, enable_cache: bool = True):
        super().__init__()

        # 性能优化组件
        self.index_manager = IndexManager()
        self.performance_monitor = PerformanceMonitor() if enable_monitoring else None
        self.cache_manager = CacheManager() if enable_cache else None

        # 统计信息
        self.operation_stats = {
            "objects_created": 0,
            "objects_retrieved": 0,
            "queries_executed": 0,
            "cache_hits": 0,
            "cache_misses": 0,
        }

        # 添加自定义指标
        if self.performance_monitor:
            self._setup_custom_metrics()

    def register_object_type(self, object_type: ObjectType):
        """注册对象类型"""
        super().register_object_type(object_type)

    def add_object(self, object_instance: ObjectInstance):
        """添加对象，支持索引和缓存"""
        with self._performance_track("add_object"):
            # 使用优化的对象实例
            if not isinstance(object_instance, OptimizedObjectInstance):
                object_instance = OptimizedObjectInstance(
                    object_instance.object_type_api_name,
                    object_instance.primary_key_value,
                    object_instance.property_values,
                    self,
                )

            # 添加到基础存储
            super().add_object(object_instance)

            # 添加到索引
            self.index_manager.index_object(object_instance)

            # 添加到缓存
            if self.cache_manager:
                cache_key = f"object:{object_instance.object_type_api_name}:{object_instance.primary_key_value}"
                cache = self.cache_manager.get_cache("objects")
                cache.put(cache_key, object_instance)

            self.operation_stats["objects_created"] += 1

    def get_object(
        self, type_name: str, primary_key: Any
    ) -> Optional[OptimizedObjectInstance]:
        """获取对象，支持缓存和对象池"""
        with self._performance_track("get_object"):
            # 尝试从缓存获取
            if self.cache:
                cache_key = f"object:{type_name}:{primary_key}"
                cached_object = self.cache.get(cache_key)
                if cached_object:
                    self.operation_stats["cache_hits"] += 1
                    self.operation_stats["objects_retrieved"] += 1
                    return cached_object
                else:
                    self.operation_stats["cache_misses"] += 1

            # 从索引或基础存储获取
            if hasattr(self.index_manager, "find_objects_by_primary_key"):
                objects = self.index_manager.find_objects_by_primary_key(
                    type_name, [primary_key]
                )
                obj = objects[0] if objects else None
            else:
                obj = super().get_object(type_name, primary_key)

            if obj:
                # 缓存结果
                if self.cache:
                    cache_key = f"object:{type_name}:{primary_key}"
                    self.cache.set(cache_key, obj, level="L2")

                self.operation_stats["objects_retrieved"] += 1

            return obj

    def get_objects_of_type(self, type_name: str) -> OptimizedObjectSet:
        """获取对象集合"""
        with self._performance_track("get_objects_of_type"):
            object_type = self.get_object_type(type_name)
            if not object_type:
                return OptimizedObjectSet(
                    ObjectType(type_name, type_name, ""), [], self
                )

            # 尝试从缓存获取
            if self.cache:
                cache_key = f"objects_of_type:{type_name}"
                cached_objects = self.cache.get(cache_key)
                if cached_objects:
                    self.operation_stats["cache_hits"] += 1
                    return OptimizedObjectSet(object_type, cached_objects, self)
                else:
                    self.operation_stats["cache_misses"] += 1

            # 从索引获取或回退到基础存储
            objects = super().get_objects_of_type(type_name)

            # 转换为优化版本
            optimized_objects = []
            for obj in objects:
                if not isinstance(obj, OptimizedObjectInstance):
                    optimized_obj = OptimizedObjectInstance(
                        obj.object_type_api_name,
                        obj.primary_key_value,
                        obj.property_values,
                        self,
                    )
                    optimized_objects.append(optimized_obj)
                else:
                    optimized_objects.append(obj)

            result_set = OptimizedObjectSet(object_type, optimized_objects, self)

            # 缓存结果（如果对象数量不太大）
            if self.cache and len(optimized_objects) < 1000:
                cache_key = f"objects_of_type:{type_name}"
                self.cache.set(cache_key, optimized_objects, level="L2")

            self.operation_stats["queries_executed"] += 1

            return result_set

    def create_link(
        self,
        link_type_api_name: str,
        source_pk: Any,
        target_pk: Any,
        user_permissions: List[str] = None,
    ):
        """创建链接，支持索引"""
        with self._performance_track("create_link"):
            super().create_link(
                link_type_api_name, source_pk, target_pk, user_permissions
            )

            # 添加到链接索引
            if hasattr(self, "_links") and self._links:
                link = self._links[-1]  # 最后添加的链接
                self.index_manager.index_link(link)

    def execute_function(self, function_api_name: str, **kwargs) -> Any:
        """执行函数，支持性能监控"""
        with self._performance_track(f"execute_function:{function_api_name}"):
            return super().execute_function(function_api_name, **kwargs)

    def create_property_index(self, object_type: str, property_name: str):
        """创建属性索引"""
        return self.index_manager.create_property_index(object_type, property_name)

    def create_composite_index(self, object_type: str, properties: List[str]):
        """创建复合索引"""
        return self.index_manager.create_composite_index(object_type, properties)

    def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计信息"""
        stats = {
            "operation_stats": self.operation_stats.copy(),
            "cache_stats": {},
            "index_stats": {},
        }

        # 缓存统计
        if self.cache:
            stats["cache_stats"] = self.cache.get_comprehensive_stats()

        # 索引统计
        if hasattr(self.index_manager, "get_index_stats"):
            stats["index_stats"] = self.index_manager.get_index_stats()

        # 监控统计
        if self.performance_monitor:
            stats["monitoring_stats"] = self.performance_monitor.get_dashboard_data()

        return stats

    def optimize_performance(self):
        """执行性能优化"""
        suggestions = []

        # 分析查询模式并建议索引
        if hasattr(self.index_manager, "query_stats"):
            high_frequency_queries = [
                query_id
                for query_id, stats in self.index_manager.query_stats.items()
                if stats.frequency > 10 and stats.avg_duration > 50
            ]

            if high_frequency_queries:
                suggestions.append("发现高频慢查询，建议创建索引")

        # 检查缓存命中率
        if self.cache:
            cache_stats = self.cache.get_comprehensive_stats()
            if cache_stats["global"]["hit_rate"] < 0.7:
                suggestions.append("缓存命中率较低，考虑优化缓存策略")

        # 清理过期缓存
        if self.cache:
            self.cache.cleanup_expired()

        # 清理过期的对象缓存
        for objects in self._object_store.values():
            for obj in objects.values():
                if isinstance(obj, OptimizedObjectInstance):
                    obj.invalidate_cache()

        return suggestions

    @contextmanager
    def _performance_track(self, operation_name: str):
        """性能跟踪上下文管理器"""
        if self.performance_monitor:
            with self.performance_monitor.track_operation(operation_name):
                yield
        else:
            yield

    def _setup_custom_metrics(self):
        """设置自定义指标"""

        def cache_hit_rate_metric():
            if self.cache:
                stats = self.cache.get_comprehensive_stats()
                return stats["global"]["hit_rate"]
            return 0.0

        def objects_count_metric():
            return sum(len(objects) for objects in self._object_store.values())

        def links_count_metric():
            return len(self._links) if hasattr(self, "_links") else 0

        def error_rate_metric():
            total = (
                self.operation_stats["objects_created"]
                + self.operation_stats["queries_executed"]
            )
            if total == 0:
                return 0.0
            # 简化实现，实际中应该有错误计数
            return 0.0

        self.performance_monitor.add_custom_metric(
            "cache_hit_rate", cache_hit_rate_metric
        )
        self.performance_monitor.add_custom_metric(
            "objects_count", objects_count_metric
        )
        self.performance_monitor.add_custom_metric("links_count", links_count_metric)
        self.performance_monitor.add_custom_metric("error_rate", error_rate_metric)

    def __del__(self):
        """清理资源"""
        if self.performance_monitor:
            self.performance_monitor.stop_monitoring()
