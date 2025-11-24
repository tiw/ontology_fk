"""
性能优化模块

提供缓存、索引、连接池等性能优化功能，实现架构设计文档中定义的性能策略。
"""

import time
import threading
import hashlib
import json
from typing import Any, Dict, List, Optional, Callable, Union, Tuple
from dataclasses import dataclass, field
from collections import defaultdict, OrderedDict
from functools import wraps
import weakref

# 导入需要的框架组件
from .core import ObjectInstance

# 缓存配置
@dataclass
class CacheConfig:
    """缓存配置"""
    max_size: int = 1000
    ttl_seconds: int = 300  # 5分钟
    cleanup_interval: int = 60  # 1分钟清理一次
    enable_stats: bool = True


class LRUCache:
    """LRU缓存实现"""

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 300):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.cache: OrderedDict = OrderedDict()
        self.timestamps: Dict[str, float] = {}
        self.lock = threading.RLock()
        self.hits = 0
        self.misses = 0

    def _is_expired(self, key: str) -> bool:
        """检查缓存项是否过期"""
        return time.time() - self.timestamps.get(key, 0) > self.ttl_seconds

    def _cleanup_expired(self):
        """清理过期项"""
        current_time = time.time()
        expired_keys = [
            key for key, timestamp in self.timestamps.items()
            if current_time - timestamp > self.ttl_seconds
        ]

        for key in expired_keys:
            if key in self.cache:
                del self.cache[key]
            del self.timestamps[key]

    def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        with self.lock:
            self._cleanup_expired()

            if key not in self.cache:
                self.misses += 1
                return None

            if self._is_expired(key):
                del self.cache[key]
                del self.timestamps[key]
                self.misses += 1
                return None

            # 移动到末尾（最近使用）
            value = self.cache.pop(key)
            self.cache[key] = value
            self.hits += 1
            return value

    def put(self, key: str, value: Any):
        """存储缓存值"""
        with self.lock:
            current_time = time.time()

            # 如果已存在，更新时间戳
            if key in self.cache:
                self.cache[key] = value
                self.timestamps[key] = current_time
                return

            # 清理过期项
            self._cleanup_expired()

            # 如果达到最大容量，删除最久未使用的项
            if len(self.cache) >= self.max_size:
                oldest_key = next(iter(self.cache))
                del self.cache[oldest_key]
                del self.timestamps[oldest_key]

            self.cache[key] = value
            self.timestamps[key] = current_time

    def clear(self):
        """清空缓存"""
        with self.lock:
            self.cache.clear()
            self.timestamps.clear()
            self.hits = 0
            self.misses = 0

    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        with self.lock:
            total_requests = self.hits + self.misses
            hit_rate = self.hits / total_requests if total_requests > 0 else 0

            return {
                "size": len(self.cache),
                "max_size": self.max_size,
                "hits": self.hits,
                "misses": self.misses,
                "hit_rate": hit_rate,
                "ttl_seconds": self.ttl_seconds
            }


class CacheManager:
    """缓存管理器"""

    def __init__(self, config: Optional[CacheConfig] = None):
        self.config = config or CacheConfig()
        self.caches: Dict[str, LRUCache] = {}
        self.lock = threading.RLock()

    def get_cache(self, name: str) -> LRUCache:
        """获取或创建缓存"""
        with self.lock:
            if name not in self.caches:
                self.caches[name] = LRUCache(
                    max_size=self.config.max_size,
                    ttl_seconds=self.config.ttl_seconds
                )
            return self.caches[name]

    def clear_all(self):
        """清空所有缓存"""
        with self.lock:
            for cache in self.caches.values():
                cache.clear()

    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """获取所有缓存统计信息"""
        with self.lock:
            return {name: cache.get_stats() for name, cache in self.caches.items()}


# 全局缓存管理器实例
_cache_manager = CacheManager()


def cached(cache_name: str = "default", key_func: Optional[Callable] = None, ttl_seconds: Optional[int] = None):
    """缓存装饰器"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 生成缓存键
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                # 默认使用函数名和参数的哈希作为键
                key_data = f"{func.__name__}:{str(args)}:{str(sorted(kwargs.items()))}"
                cache_key = hashlib.md5(key_data.encode()).hexdigest()

            # 获取缓存
            cache = _cache_manager.get_cache(cache_name)

            # 尝试从缓存获取
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                return cached_result

            # 执行函数并缓存结果
            result = func(*args, **kwargs)
            cache.put(cache_key, result)

            return result

        # 添加缓存管理方法
        wrapper.cache_clear = lambda: _cache_manager.get_cache(cache_name).clear()
        wrapper.cache_stats = lambda: _cache_manager.get_cache(cache_name).get_stats()

        return wrapper
    return decorator


# 索引系统
@dataclass
class IndexDefinition:
    """索引定义"""
    name: str
    property_name: str
    index_type: str = "hash"  # hash, btree, fulltext
    unique: bool = False
    case_sensitive: bool = True


class PropertyIndex:
    """属性索引"""

    def __init__(self, definition: IndexDefinition):
        self.definition = definition
        self.index: Dict[Any, List[Any]] = defaultdict(list)
        self.lock = threading.RLock()

    def add(self, value: Any, object_id: Any):
        """添加索引项"""
        with self.lock:
            # 处理大小写敏感性
            if isinstance(value, str) and not self.definition.case_sensitive:
                value = value.lower()

            if self.definition.unique:
                # 唯一索引
                if value in self.index:
                    raise ValueError(f"唯一索引冲突: {self.definition.name} = {value}")
                self.index[value] = object_id
            else:
                # 非唯一索引
                self.index[value].append(object_id)

    def remove(self, value: Any, object_id: Any):
        """移除索引项"""
        with self.lock:
            if isinstance(value, str) and not self.definition.case_sensitive:
                value = value.lower()

            if value in self.index:
                if self.definition.unique:
                    del self.index[value]
                else:
                    try:
                        self.index[value].remove(object_id)
                        if not self.index[value]:  # 如果列表为空，删除键
                            del self.index[value]
                    except ValueError:
                        pass  # 对象ID不存在

    def find(self, value: Any) -> List[Any]:
        """查找索引项"""
        with self.lock:
            if isinstance(value, str) and not self.definition.case_sensitive:
                value = value.lower()

            result = self.index.get(value, [])
            if self.definition.unique:
                return [result] if result else []
            return result.copy()

    def find_range(self, min_value: Any, max_value: Any) -> List[Any]:
        """范围查找（仅支持可比较的值）"""
        if self.definition.index_type != "btree":
            return []

        with self.lock:
            result = []
            for value, object_ids in self.index.items():
                if min_value <= value <= max_value:
                    result.extend(object_ids if not self.definition.unique else [object_ids])
            return result

    def get_stats(self) -> Dict[str, Any]:
        """获取索引统计信息"""
        with self.lock:
            total_values = len(self.index)
            total_objects = sum(
                len(object_ids) if not self.definition.unique else 1
                for object_ids in self.index.values()
            )

            return {
                "name": self.definition.name,
                "type": self.definition.index_type,
                "unique": self.definition.unique,
                "total_values": total_values,
                "total_objects": total_objects,
                "case_sensitive": self.definition.case_sensitive
            }


class IndexManager:
    """索引管理器"""

    def __init__(self):
        self.indexes: Dict[str, PropertyIndex] = {}
        self.lock = threading.RLock()

    def create_index(self, definition: IndexDefinition) -> PropertyIndex:
        """创建索引"""
        with self.lock:
            if definition.name in self.indexes:
                raise ValueError(f"索引已存在: {definition.name}")

            index = PropertyIndex(definition)
            self.indexes[definition.name] = index
            return index

    def get_index(self, name: str) -> Optional[PropertyIndex]:
        """获取索引"""
        with self.lock:
            return self.indexes.get(name)

    def drop_index(self, name: str) -> bool:
        """删除索引"""
        with self.lock:
            if name in self.indexes:
                del self.indexes[name]
                return True
            return False

    def list_indexes(self) -> List[str]:
        """列出所有索引名称"""
        with self.lock:
            return list(self.indexes.keys())

    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """获取所有索引统计信息"""
        with self.lock:
            return {name: index.get_stats() for name, index in self.indexes.items()}


# 查询优化器
class QueryOptimizer:
    """查询优化器"""

    def __init__(self, index_manager: IndexManager):
        self.index_manager = index_manager

    def optimize_filter_query(self, object_type: str, filters: Dict[str, Any]) -> Tuple[str, List[Any]]:
        """优化过滤查询，选择最佳索引"""
        best_index = None
        best_index_name = None
        min_expected_results = float('inf')

        # 查找适用的索引
        for index_name in self.index_manager.list_indexes():
            index = self.index_manager.get_index(index_name)

            # 检查是否有匹配的索引
            for property_name, value in filters.items():
                if index and index.definition.property_name == property_name:
                    # 估算结果数量
                    estimated_results = self._estimate_selectivity(index, value)

                    if estimated_results < min_expected_results:
                        min_expected_results = estimated_results
                        best_index = index
                        best_index_name = index_name

        if best_index:
            return best_index_name, best_index.find(filters.get(best_index.definition.property_name))

        return None, []

    def _estimate_selectivity(self, index: PropertyIndex, value: Any) -> int:
        """估算索引选择性"""
        stats = index.get_stats()
        total_objects = stats["total_objects"]

        if total_objects == 0:
            return 0

        # 简单启发式：如果值在索引中，假设返回10%的数据
        if value in index.index:
            return max(1, total_objects // 10)

        # 如果值不在索引中，假设返回0
        return 0


# 连接池
@dataclass
class ConnectionConfig:
    """连接配置"""
    max_connections: int = 10
    min_connections: int = 2
    max_idle_time: int = 300  # 5分钟
    connection_timeout: int = 30  # 30秒
    health_check_interval: int = 60  # 1分钟


class ConnectionPool:
    """通用连接池"""

    def __init__(self, config: ConnectionConfig, connection_factory: Callable):
        self.config = config
        self.connection_factory = connection_factory

        self.available_connections: List[Any] = []
        self.used_connections: weakref.WeakSet = weakref.WeakSet()
        self.connection_timestamps: Dict[int, float] = {}

        self.lock = threading.RLock()
        self.last_health_check = time.time()

        # 初始化最小连接数
        self._initialize_pool()

    def _initialize_pool(self):
        """初始化连接池"""
        for _ in range(self.config.min_connections):
            try:
                conn = self.connection_factory()
                self.available_connections.append(conn)
            except Exception as e:
                print(f"初始化连接失败: {e}")

    def _create_connection(self) -> Any:
        """创建新连接"""
        return self.connection_factory()

    def _is_connection_healthy(self, connection: Any) -> bool:
        """检查连接健康状态"""
        try:
            # 简单的健康检查（需要根据具体连接类型实现）
            return hasattr(connection, 'ping') or connection is not None
        except:
            return False

    def _cleanup_idle_connections(self):
        """清理空闲连接"""
        current_time = time.time()
        idle_connections = []

        for i, conn in enumerate(self.available_connections):
            conn_id = id(conn)
            last_used = self.connection_timestamps.get(conn_id, 0)

            if current_time - last_used > self.config.max_idle_time:
                idle_connections.append(i)

        # 从后往前删除，避免索引问题
        for i in reversed(idle_connections):
            conn = self.available_connections.pop(i)
            try:
                # 尝试关闭连接
                if hasattr(conn, 'close'):
                    conn.close()
            except:
                pass

    def _health_check(self):
        """健康检查"""
        current_time = time.time()

        # 如果距离上次检查时间不足间隔时间，跳过
        if current_time - self.last_health_check < self.config.health_check_interval:
            return

        # 清理空闲连接
        self._cleanup_idle_connections()

        # 检查可用连接健康状态
        healthy_connections = []
        for conn in self.available_connections:
            if self._is_connection_healthy(conn):
                healthy_connections.append(conn)
            else:
                # 移除不健康的连接
                conn_id = id(conn)
                self.connection_timestamps.pop(conn_id, None)

        self.available_connections = healthy_connections

        # 确保最小连接数
        while len(self.available_connections) < self.config.min_connections:
            try:
                conn = self._create_connection()
                self.available_connections.append(conn)
            except Exception as e:
                print(f"创建连接失败: {e}")
                break

        self.last_health_check = current_time

    def get_connection(self) -> Any:
        """获取连接"""
        with self.lock:
            self._health_check()

            # 尝试从可用连接中获取
            if self.available_connections:
                conn = self.available_connections.pop()
                self.used_connections.add(conn)
                self.connection_timestamps[id(conn)] = time.time()
                return conn

            # 如果没有可用连接且未达到最大连接数，创建新连接
            if len(self.used_connections) < self.config.max_connections:
                try:
                    conn = self._create_connection()
                    self.used_connections.add(conn)
                    self.connection_timestamps[id(conn)] = time.time()
                    return conn
                except Exception as e:
                    raise RuntimeError(f"创建连接失败: {e}")

            # 达到最大连接数，等待可用连接
            raise RuntimeError("连接池已满，无法获取连接")

    def return_connection(self, connection: Any):
        """归还连接"""
        with self.lock:
            if connection in self.used_connections:
                self.used_connections.discard(connection)

                if self._is_connection_healthy(connection):
                    self.available_connections.append(connection)
                    self.connection_timestamps[id(connection)] = time.time()
                else:
                    # 连接不健康，关闭它
                    try:
                        if hasattr(connection, 'close'):
                            connection.close()
                    except:
                        pass
                    conn_id = id(connection)
                    self.connection_timestamps.pop(conn_id, None)

    def close_all(self):
        """关闭所有连接"""
        with self.lock:
            all_connections = self.available_connections + list(self.used_connections)

            for conn in all_connections:
                try:
                    if hasattr(conn, 'close'):
                        conn.close()
                except:
                    pass

            self.available_connections.clear()
            self.used_connections.clear()
            self.connection_timestamps.clear()

    def get_stats(self) -> Dict[str, Any]:
        """获取连接池统计信息"""
        with self.lock:
            return {
                "available_connections": len(self.available_connections),
                "used_connections": len(self.used_connections),
                "max_connections": self.config.max_connections,
                "min_connections": self.config.min_connections,
                "connection_timestamps": len(self.connection_timestamps)
            }


# 性能监控
@dataclass
class PerformanceMetrics:
    """性能指标"""
    operation_count: int = 0
    total_time: float = 0.0
    min_time: float = float('inf')
    max_time: float = 0.0
    error_count: int = 0

    def update(self, execution_time: float, success: bool = True):
        """更新指标"""
        self.operation_count += 1
        self.total_time += execution_time
        self.min_time = min(self.min_time, execution_time)
        self.max_time = max(self.max_time, execution_time)

        if not success:
            self.error_count += 1

    @property
    def avg_time(self) -> float:
        """平均时间"""
        return self.total_time / self.operation_count if self.operation_count > 0 else 0.0

    @property
    def error_rate(self) -> float:
        """错误率"""
        return self.error_count / self.operation_count if self.operation_count > 0 else 0.0


class PerformanceMonitor:
    """性能监控器"""

    def __init__(self):
        self.metrics: Dict[str, PerformanceMetrics] = {}
        self.lock = threading.RLock()

    def record_operation(self, operation_name: str, execution_time: float, success: bool = True):
        """记录操作"""
        with self.lock:
            if operation_name not in self.metrics:
                self.metrics[operation_name] = PerformanceMetrics()

            self.metrics[operation_name].update(execution_time, success)

    def get_metrics(self, operation_name: str) -> Optional[PerformanceMetrics]:
        """获取操作指标"""
        with self.lock:
            return self.metrics.get(operation_name)

    def get_all_metrics(self) -> Dict[str, PerformanceMetrics]:
        """获取所有指标"""
        with self.lock:
            return self.metrics.copy()

    def clear_metrics(self, operation_name: Optional[str] = None):
        """清除指标"""
        with self.lock:
            if operation_name:
                self.metrics.pop(operation_name, None)
            else:
                self.metrics.clear()


def performance_monitored(operation_name: Optional[str] = None):
    """性能监控装饰器"""
    def decorator(func: Callable) -> Callable:
        name = operation_name or f"{func.__module__}.{func.__name__}"

        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            success = False

            try:
                result = func(*args, **kwargs)
                success = True
                return result
            finally:
                execution_time = time.time() - start_time
                _performance_monitor.record_operation(name, execution_time, success)

        return wrapper
    return decorator


# 全局实例
_cache_manager = CacheManager()
_performance_monitor = PerformanceMonitor()


def get_cache_manager() -> CacheManager:
    """获取全局缓存管理器"""
    return _cache_manager


def get_performance_monitor() -> PerformanceMonitor:
    """获取全局性能监控器"""
    return _performance_monitor


# 性能优化建议
class PerformanceAdvisor:
    """性能优化建议器"""

    def __init__(self):
        self.cache_manager = get_cache_manager()
        self.performance_monitor = get_performance_monitor()

    def analyze_performance(self) -> List[Dict[str, Any]]:
        """分析性能并提供建议"""
        recommendations = []

        # 分析缓存性能
        cache_stats = self.cache_manager.get_all_stats()
        for cache_name, stats in cache_stats.items():
            if stats["hit_rate"] < 0.7:  # 命中率低于70%
                recommendations.append({
                    "type": "cache",
                    "severity": "medium",
                    "component": cache_name,
                    "issue": f"缓存命中率过低: {stats['hit_rate']:.2%}",
                    "recommendation": "考虑增加缓存大小或调整TTL时间",
                    "current_stats": stats
                })

        # 分析操作性能
        performance_metrics = self.performance_monitor.get_all_metrics()
        for operation_name, metrics in performance_metrics.items():
            if metrics.avg_time > 0.1:  # 平均响应时间超过100ms
                recommendations.append({
                    "type": "performance",
                    "severity": "high",
                    "component": operation_name,
                    "issue": f"平均响应时间过长: {metrics.avg_time:.3f}s",
                    "recommendation": "考虑添加缓存、优化查询或使用索引",
                    "current_metrics": {
                        "avg_time": metrics.avg_time,
                        "operation_count": metrics.operation_count,
                        "error_rate": metrics.error_rate
                    }
                })

            if metrics.error_rate > 0.05:  # 错误率超过5%
                recommendations.append({
                    "type": "reliability",
                    "severity": "high",
                    "component": operation_name,
                    "issue": f"错误率过高: {metrics.error_rate:.2%}",
                    "recommendation": "检查错误处理逻辑和重试机制",
                    "current_metrics": {
                        "error_rate": metrics.error_rate,
                        "error_count": metrics.error_count,
                        "operation_count": metrics.operation_count
                    }
                })

        return recommendations

    def generate_optimization_report(self) -> str:
        """生成优化报告"""
        recommendations = self.analyze_performance()

        if not recommendations:
            return "✅ 性能表现良好，无需优化建议"

        report = ["🔍 性能优化建议报告", "=" * 40, ""]

        # 按严重程度分组
        by_severity = defaultdict(list)
        for rec in recommendations:
            by_severity[rec["severity"]].append(rec)

        for severity in ["high", "medium", "low"]:
            if severity in by_severity:
                severity_text = {"high": "🔴 高优先级", "medium": "🟡 中优先级", "low": "🟢 低优先级"}
                report.append(f"{severity_text[severity]}:")

                for rec in by_severity[severity]:
                    report.append(f"  • 组件: {rec['component']}")
                    report.append(f"    问题: {rec['issue']}")
                    report.append(f"    建议: {rec['recommendation']}")
                    report.append("")

        return "\n".join(report)


# 与现有 optimized_core.py 集成的适配器
class PerformanceOptimizerAdapter:
    """性能优化适配器，集成新的性能模块到现有系统"""

    def __init__(self, ontology):
        self.ontology = ontology
        self.advisor = PerformanceAdvisor()

    def install_optimizations(self):
        """安装性能优化"""
        # 为现有对象创建缓存
        if hasattr(self.ontology, '_object_store'):
            for object_type_name, objects in self.ontology._object_store.items():
                # 为每个对象类型创建缓存
                cache_name = f"objects_{object_type_name}"
                self.ontology._cache_manager.get_cache(cache_name)

        # 为常用查询创建索引
        if hasattr(self.ontology, 'object_types'):
            for object_type_name, object_type in self.ontology.object_types.items():
                # 为主键创建索引
                if object_type.primary_key:
                    self.create_optimized_index(object_type_name, object_type.primary_key, unique=True)

                # 为常用属性创建索引
                common_properties = ['name', 'email', 'status', 'type']
                for prop in common_properties:
                    if prop in object_type.properties:
                        self.create_optimized_index(object_type_name, prop)

    def create_optimized_index(self, object_type_name: str, property_name: str, unique: bool = False):
        """创建优化的索引"""
        if hasattr(self.ontology, 'index_manager'):
            return self.ontology.index_manager.create_property_index(object_type_name, property_name)
        return False

    def get_optimization_recommendations(self) -> List[str]:
        """获取优化建议"""
        recommendations = []
        analysis = self.advisor.analyze_performance()

        for rec in analysis:
            if rec["severity"] == "high":
                recommendations.append(f"紧急: {rec['issue']}")
            elif rec["severity"] == "medium":
                recommendations.append(f"建议: {rec['issue']}")

        return recommendations

    def apply_auto_optimizations(self):
        """应用自动优化"""
        # 清理过期缓存
        if hasattr(self.ontology, '_cache_manager'):
            self.ontology._cache_manager.clear_all()

        # 重建索引
        if hasattr(self.ontology, 'index_manager'):
            # 这里可以添加索引重建逻辑
            pass

        # 优化对象集合
        if hasattr(self.ontology, '_object_store'):
            for object_type_name in self.ontology._object_store:
                objects = self.ontology.get_objects_of_type(object_type_name)
                if hasattr(objects, 'invalidate_cache'):
                    objects.invalidate_cache()


# 批量操作优化
@dataclass
class BatchConfig:
    """批量操作配置"""
    batch_size: int = 1000
    max_memory_usage: int = 100 * 1024 * 1024  # 100MB
    enable_parallel: bool = True
    parallel_workers: int = 4


class BatchProcessor:
    """批量处理器"""

    def __init__(self, config: BatchConfig = None):
        self.config = config or BatchConfig()

    @performance_monitored("batch_add_objects")
    def batch_add_objects(self, ontology, objects: List[ObjectInstance]) -> Dict[str, Any]:
        """批量添加对象"""
        start_time = time.time()
        success_count = 0
        error_count = 0

        # 分批处理
        for i in range(0, len(objects), self.config.batch_size):
            batch = objects[i:i + self.config.batch_size]

            try:
                for obj in batch:
                    ontology.add_object(obj)
                    success_count += 1
            except Exception as e:
                error_count += len(batch)
                print(f"批量添加出错: {e}")

        execution_time = time.time() - start_time

        return {
            "total_objects": len(objects),
            "success_count": success_count,
            "error_count": error_count,
            "execution_time": execution_time,
            "throughput": len(objects) / execution_time if execution_time > 0 else 0
        }

    @performance_monitored("batch_query")
    def batch_query(self, ontology, object_type_name: str, queries: List[Dict[str, Any]]) -> List[ObjectInstance]:
        """批量查询"""
        results = []

        # 如果有索引，优先使用索引查询
        if hasattr(ontology, 'index_manager'):
            for query in queries:
                # 尝试使用索引
                if len(query) == 1:  # 单条件查询
                    prop_name, prop_value = next(iter(query.items()))
                    index_key = f"{object_type_name}.{prop_name}"

                    if hasattr(ontology.index_manager, 'property_index') and index_key in ontology.index_manager.property_index:
                        matching_pks = ontology.index_manager.query_with_index(object_type_name, query)
                        matching_objects = ontology.index_manager.find_objects_by_primary_key(object_type_name, list(matching_pks))
                        results.extend(matching_objects)
                        continue

                # 回退到标准查询
                objects = ontology.get_objects_of_type(object_type_name)
                filtered = objects
                for prop_name, prop_value in query.items():
                    filtered = filtered.filter(prop_name, prop_value)
                results.extend(filtered.all())
        else:
            # 没有索引，使用标准查询
            objects = ontology.get_objects_of_type(object_type_name)
            for query in queries:
                filtered = objects
                for prop_name, prop_value in query.items():
                    filtered = filtered.filter(prop_name, prop_value)
                results.extend(filtered.all())

        return results


# 内存优化器
class MemoryOptimizer:
    """内存优化器"""

    def __init__(self, ontology):
        self.ontology = ontology

    def analyze_memory_usage(self) -> Dict[str, Any]:
        """分析内存使用情况"""
        import sys

        memory_stats = {}

        # 分析对象存储
        if hasattr(self.ontology, '_object_store'):
            total_objects = 0
            total_memory = 0

            for object_type_name, objects in self.ontology._object_store.items():
                object_count = len(objects)
                object_memory = sum(sys.getsizeof(obj) for obj in objects.values())

                total_objects += object_count
                total_memory += object_memory

                memory_stats[object_type_name] = {
                    "object_count": object_count,
                    "memory_usage": object_memory,
                    "avg_memory_per_object": object_memory / object_count if object_count > 0 else 0
                }

            memory_stats["summary"] = {
                "total_objects": total_objects,
                "total_memory": total_memory,
                "avg_memory_per_object": total_memory / total_objects if total_objects > 0 else 0
            }

        # 分析缓存使用
        if hasattr(self.ontology, '_cache_manager'):
            cache_stats = self.ontology._cache_manager.get_all_stats()
            memory_stats["cache_summary"] = cache_stats

        return memory_stats

    def optimize_memory_usage(self) -> List[str]:
        """优化内存使用"""
        optimizations = []

        # 清理过期缓存
        if hasattr(self.ontology, '_cache_manager'):
            old_cache_size = sum(len(cache.cache) for cache in self.ontology._cache_manager.caches.values())
            self.ontology._cache_manager.clear_all()
            optimizations.append(f"清理缓存，释放了 {old_cache_size} 个缓存项")

        # 清理对象缓存
        if hasattr(self.ontology, '_object_store'):
            cleared_objects = 0
            for objects in self.ontology._object_store.values():
                for obj in objects.values():
                    if hasattr(obj, '_derived_properties_cache'):
                        cache_size = len(obj._derived_properties_cache)
                        obj._derived_properties_cache.clear()
                        obj._cache_timestamps.clear()
                        cleared_objects += cache_size

            optimizations.append(f"清理了 {cleared_objects} 个对象的派生属性缓存")

        return optimizations

    def suggest_memory_optimizations(self) -> List[str]:
        """建议内存优化"""
        suggestions = []
        memory_stats = self.analyze_memory_usage()

        if "summary" in memory_stats:
            total_memory = memory_stats["summary"]["total_memory"]
            if total_memory > 50 * 1024 * 1024:  # 超过50MB
                suggestions.append("内存使用量较高，考虑使用对象池或延迟加载")

        # 检查大对象
        for object_type_name, stats in memory_stats.items():
            if object_type_name == "summary" or object_type_name == "cache_summary":
                continue

            avg_memory = stats["avg_memory_per_object"]
            if avg_memory > 1024:  # 平均每个对象超过1KB
                suggestions.append(f"对象类型 {object_type_name} 平均内存使用较高 ({avg_memory} bytes)，考虑优化属性存储")

        return suggestions