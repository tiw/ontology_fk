"""
高级索引系统

提供多层次、自适应的索引管理功能，显著提升查询性能。
"""

from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass
from collections import defaultdict
import time
import threading
from abc import ABC, abstractmethod

from ..core import ObjectInstance, ObjectType, Link


@dataclass
class QueryStats:
    """查询统计信息"""
    query_hash: str
    query: 'Query'
    frequency: int = 0
    total_duration: float = 0.0
    avg_duration: float = 0.0
    last_executed: float = 0.0

    def update(self, duration: float):
        self.frequency += 1
        self.total_duration += duration
        self.avg_duration = self.total_duration / self.frequency
        self.last_executed = time.time()


@dataclass
class IndexDefinition:
    """索引定义"""
    object_type: str
    properties: List[str]
    index_type: str = 'btree'  # btree, hash, composite
    unique: bool = False
    case_sensitive: bool = True

    def __hash__(self):
        return hash((self.object_type, tuple(self.properties), self.index_type))


class BaseIndex(ABC):
    """索引基类"""

    @abstractmethod
    def add(self, obj: ObjectInstance):
        """添加对象到索引"""
        pass

    @abstractmethod
    def remove(self, obj: ObjectInstance):
        """从索引中移除对象"""
        pass

    @abstractmethod
    def query(self, **filters) -> Set[Any]:
        """根据条件查询"""
        pass

    @abstractmethod
    def size(self) -> int:
        """索引大小"""
        pass


class BTreeIndex(BaseIndex):
    """B树索引实现"""

    def __init__(self, object_type: str, property_name: str):
        self.object_type = object_type
        self.property_name = property_name
        self._index: Dict[Any, Set[Any]] = defaultdict(set)
        self._lock = threading.RLock()

    def add(self, obj: ObjectInstance):
        """添加对象到索引"""
        if obj.object_type_api_name != self.object_type:
            return

        value = obj.property_values.get(self.property_name)
        if value is not None:
            with self._lock:
                self._index[value].add(obj.primary_key_value)

    def remove(self, obj: ObjectInstance):
        """从索引中移除对象"""
        if obj.object_type_api_name != self.object_type:
            return

        value = obj.property_values.get(self.property_name)
        if value is not None:
            with self._lock:
                self._index[value].discard(obj.primary_key_value)
                if not self._index[value]:
                    del self._index[value]

    def query(self, value: Any) -> Set[Any]:
        """精确匹配查询"""
        with self._lock:
            return self._index.get(value, set())

    def range_query(self, min_val: Any, max_val: Any) -> Set[Any]:
        """范围查询"""
        with self._lock:
            result = set()
            for value, pks in self._index.items():
                if min_val <= value <= max_val:
                    result.update(pks)
            return result

    def size(self) -> int:
        """索引大小"""
        with self._lock:
            return sum(len(pks) for pks in self._index.values())


class CompositeIndex(BaseIndex):
    """复合索引实现"""

    def __init__(self, object_type: str, properties: List[str]):
        self.object_type = object_type
        self.properties = properties
        self._index: Dict[Tuple, Set[Any]] = defaultdict(set)
        self._lock = threading.RLock()

    def _create_key(self, obj: ObjectInstance) -> Optional[Tuple]:
        """创建复合键"""
        key_parts = []
        for prop in self.properties:
            value = obj.property_values.get(prop)
            if value is None:
                return None
            key_parts.append(value)
        return tuple(key_parts)

    def add(self, obj: ObjectInstance):
        """添加对象到复合索引"""
        if obj.object_type_api_name != self.object_type:
            return

        key = self._create_key(obj)
        if key is not None:
            with self._lock:
                self._index[key].add(obj.primary_key_value)

    def remove(self, obj: ObjectInstance):
        """从复合索引中移除对象"""
        if obj.object_type_api_name != self.object_type:
            return

        key = self._create_key(obj)
        if key is not None:
            with self._lock:
                self._index[key].discard(obj.primary_key_value)
                if not self._index[key]:
                    del self._index[key]

    def query(self, **filters) -> Set[Any]:
        """复合条件查询"""
        if not all(prop in filters for prop in self.properties):
            return set()

        key = tuple(filters[prop] for prop in self.properties)
        with self._lock:
            return self._index.get(key, set())

    def partial_query(self, **filters) -> Set[Any]:
        """部分条件查询（前缀匹配）"""
        if not filters:
            return set()

        # 检查是否为前缀条件
        filter_props = list(filters.keys())
        if not all(prop in self.properties[:len(filter_props)] for prop in filter_props):
            return set()

        prefix_key = tuple(filters[prop] for prop in filter_props)
        result = set()

        with self._lock:
            for key, pks in self._index.items():
                if key[:len(prefix_key)] == prefix_key:
                    result.update(pks)

        return result

    def size(self) -> int:
        """索引大小"""
        with self._lock:
            return sum(len(pks) for pks in self._index.values())


class AdvancedIndexManager:
    """高级索引管理器"""

    def __init__(self):
        # 主键索引
        self.primary_index: Dict[str, Dict[Any, ObjectInstance]] = {}

        # 属性索引
        self.property_index: Dict[str, BaseIndex] = {}

        # 复合索引
        self.composite_index: Dict[str, CompositeIndex] = {}

        # 链接索引
        self.link_index: Dict[str, Dict[str, Dict[Any, Set[Any]]]] = defaultdict(lambda: defaultdict(dict))

        # 索引注册表
        self.index_registry: Dict[str, IndexDefinition] = {}

        # 索引统计
        self.index_stats: Dict[str, Dict[str, Any]] = defaultdict(dict)

        # 查询统计
        self.query_stats: Dict[str, QueryStats] = {}

        self._lock = threading.RLock()

    def register_object_type(self, object_type: ObjectType):
        """注册对象类型，初始化主键索引"""
        with self._lock:
            self.primary_index[object_type.api_name] = {}

    def create_property_index(self, object_type: str, property_name: str,
                            index_type: str = 'btree') -> str:
        """创建属性索引"""
        index_key = f"{object_type}.{property_name}"

        with self._lock:
            if index_key in self.property_index:
                return index_key

            if index_type == 'btree':
                index = BTreeIndex(object_type, property_name)
            else:
                raise ValueError(f"Unsupported index type: {index_type}")

            self.property_index[index_key] = index

            # 注册索引定义
            index_def = IndexDefinition(object_type, [property_name], index_type)
            self.index_registry[index_key] = index_def

            # 初始化统计信息
            self.index_stats[index_key] = {
                'created_at': time.time(),
                'size': 0,
                'usage_count': 0
            }

        return index_key

    def create_composite_index(self, object_type: str, properties: List[str]) -> str:
        """创建复合索引"""
        if len(properties) < 2:
            raise ValueError("Composite index requires at least 2 properties")

        properties.sort()  # 保证属性顺序一致
        index_key = f"{object_type}.composite.{'_'.join(properties)}"

        with self._lock:
            if index_key in self.composite_index:
                return index_key

            index = CompositeIndex(object_type, properties)
            self.composite_index[index_key] = index

            # 注册索引定义
            index_def = IndexDefinition(object_type, properties, 'composite')
            self.index_registry[index_key] = index_def

            # 初始化统计信息
            self.index_stats[index_key] = {
                'created_at': time.time(),
                'size': 0,
                'usage_count': 0
            }

        return index_key

    def index_object(self, obj: ObjectInstance):
        """索引对象"""
        obj_type = obj.object_type_api_name

        # 添加到主键索引
        with self._lock:
            if obj_type in self.primary_index:
                self.primary_index[obj_type][obj.primary_key_value] = obj

        # 添加到属性索引
        for index_key, index in self.property_index.items():
            if obj_type in index_key:
                index.add(obj)
                self._update_index_stats(index_key, 'add')

        # 添加到复合索引
        for index_key, index in self.composite_index.items():
            if obj_type in index_key:
                index.add(obj)
                self._update_index_stats(index_key, 'add')

    def remove_object(self, obj: ObjectInstance):
        """从索引中移除对象"""
        obj_type = obj.object_type_api_name

        # 从主键索引移除
        with self._lock:
            if obj_type in self.primary_index:
                self.primary_index[obj_type].pop(obj.primary_key_value, None)

        # 从属性索引移除
        for index_key, index in self.property_index.items():
            if obj_type in index_key:
                index.remove(obj)
                self._update_index_stats(index_key, 'remove')

        # 从复合索引移除
        for index_key, index in self.composite_index.items():
            if obj_type in index_key:
                index.remove(obj)
                self._update_index_stats(index_key, 'remove')

    def index_link(self, link: Link):
        """索引链接"""
        with self._lock:
            link_type = link.link_type_api_name
            self.link_index[link_type]['source'][link.source_primary_key].add(link.target_primary_key)
            self.link_index[link_type]['target'][link.target_primary_key].add(link.source_primary_key)

    def remove_link(self, link: Link):
        """从索引中移除链接"""
        with self._lock:
            link_type = link.link_type_api_name
            self.link_index[link_type]['source'][link.source_primary_key].discard(link.target_primary_key)
            self.link_index[link_type]['target'][link.target_primary_key].discard(link.source_primary_key)

    def find_objects_by_primary_key(self, object_type: str, primary_keys: List[Any]) -> List[ObjectInstance]:
        """根据主键批量查找对象"""
        with self._lock:
            obj_store = self.primary_index.get(object_type, {})
            return [obj_store.get(pk) for pk in primary_keys if pk in obj_store]

    def query_with_index(self, object_type: str, filters: Dict[str, Any]) -> Set[Any]:
        """使用索引进行查询"""
        start_time = time.perf_counter()

        # 查找最佳索引
        index_key = self._find_best_index(object_type, filters)

        if index_key:
            # 使用索引查询
            if index_key in self.property_index:
                # 单属性索引
                prop_name = index_key.split('.')[1]
                if prop_name in filters:
                    result = self.property_index[index_key].query(filters[prop_name])
                else:
                    result = set()
            elif index_key in self.composite_index:
                # 复合索引
                index = self.composite_index[index_key]
                if all(prop in filters for prop in index.properties):
                    result = index.query(**filters)
                else:
                    # 部分查询
                    result = index.partial_query(**filters)
            else:
                result = set()
        else:
            # 无可用索引，返回空集（需要全表扫描）
            result = set()

        # 更新统计信息
        duration = (time.perf_counter() - start_time) * 1000
        self._update_query_stats(object_type, filters, duration)

        return result

    def _find_best_index(self, object_type: str, filters: Dict[str, Any]) -> Optional[str]:
        """选择最佳索引"""
        filter_props = set(filters.keys())

        # 优先级1: 完全匹配的复合索引
        for index_key, index in self.composite_index.items():
            if object_type in index_key:
                index_props = set(index.properties)
                if index_props == filter_props:
                    return index_key

        # 优先级2: 部分匹配的复合索引
        for index_key, index in self.composite_index.items():
            if object_type in index_key:
                index_props = set(index.properties)
                if filter_props.issubset(index_props):
                    return index_key

        # 优先级3: 单属性索引
        for prop in filters.keys():
            index_key = f"{object_type}.{prop}"
            if index_key in self.property_index:
                return index_key

        return None

    def get_related_objects(self, link_type: str, source_pks: List[Any],
                          direction: str = 'forward') -> Dict[Any, Set[Any]]:
        """获取相关对象"""
        with self._lock:
            if link_type not in self.link_index:
                return {}

            link_index = self.link_index[link_type]
            result = {}

            if direction == 'forward':
                # 源 -> 目标
                for pk in source_pks:
                    result[pk] = link_index['source'].get(pk, set())
            else:
                # 目标 -> 源
                for pk in source_pks:
                    result[pk] = link_index['target'].get(pk, set())

            return result

    def get_index_stats(self) -> Dict[str, Dict[str, Any]]:
        """获取索引统计信息"""
        with self._lock:
            stats = {}

            # 属性索引统计
            for index_key, index in self.property_index.items():
                stats[index_key] = {
                    **self.index_stats[index_key],
                    'type': 'property',
                    'size': index.size()
                }

            # 复合索引统计
            for index_key, index in self.composite_index.items():
                stats[index_key] = {
                    **self.index_stats[index_key],
                    'type': 'composite',
                    'properties': index.properties,
                    'size': index.size()
                }

            return stats

    def _update_index_stats(self, index_key: str, operation: str):
        """更新索引统计信息"""
        if index_key in self.index_stats:
            if operation == 'add':
                self.index_stats[index_key]['size'] += 1
            elif operation == 'remove':
                self.index_stats[index_key]['size'] = max(0, self.index_stats[index_key]['size'] - 1)

    def _update_query_stats(self, object_type: str, filters: Dict[str, Any], duration: float):
        """更新查询统计信息"""
        query_hash = hash((object_type, tuple(sorted(filters.items()))))

        if query_hash not in self.query_stats:
            self.query_stats[query_hash] = QueryStats(
                query_hash=query_hash,
                query=type('Query', (), {'object_type': object_type, 'filters': filters})()
            )

        self.query_stats[query_hash].update(duration)

    def get_query_stats(self) -> Dict[str, Dict[str, Any]]:
        """获取查询统计信息"""
        with self._lock:
            return {
                qid: {
                    'frequency': stats.frequency,
                    'avg_duration': stats.avg_duration,
                    'total_duration': stats.total_duration,
                    'last_executed': stats.last_executed
                }
                for qid, stats in self.query_stats.items()
            }


class HierarchicalIndex:
    """分层索引架构"""

    def __init__(self, hot_threshold: int = 100, warm_threshold: int = 10):
        self.hot_threshold = hot_threshold
        self.warm_threshold = warm_threshold

        # 三层索引
        self.hot_index = AdvancedIndexManager()
        self.warm_index = AdvancedIndexManager()
        self.cold_index = AdvancedIndexManager()

        # 访问跟踪
        self.access_tracker: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

        self._lock = threading.RLock()

    def index_object(self, obj: ObjectInstance):
        """智能索引分层"""
        obj_type = obj.object_type_api_name
        pk = obj.primary_key_value

        with self._lock:
            access_freq = self.access_tracker[obj_type][pk]

            # 根据访问频率选择层级
            if access_freq >= self.hot_threshold:
                self.hot_index.index_object(obj)
                # 从其他层级移除
                self.warm_index.remove_object(obj)
                self.cold_index.remove_object(obj)
            elif access_freq >= self.warm_threshold:
                self.warm_index.index_object(obj)
                # 从其他层级移除
                self.hot_index.remove_object(obj)
                self.cold_index.remove_object(obj)
            else:
                self.cold_index.index_object(obj)
                # 从其他层级移除
                self.hot_index.remove_object(obj)
                self.warm_index.remove_object(obj)

    def record_access(self, object_type: str, primary_key: Any):
        """记录对象访问"""
        with self._lock:
            self.access_tracker[object_type][primary_key] += 1

            # 检查是否需要重新分层
            current_freq = self.access_tracker[object_type][primary_key]

            # 从冷到温
            if current_freq == self.warm_threshold:
                self._promote_to_warm(object_type, primary_key)

            # 从温到热
            elif current_freq == self.hot_threshold:
                self._promote_to_hot(object_type, primary_key)

    def query(self, object_type: str, filters: Dict[str, Any]) -> List[ObjectInstance]:
        """分层查询"""
        # 优先查询热数据
        hot_pks = self.hot_index.query_with_index(object_type, filters)
        warm_pks = self.warm_index.query_with_index(object_type, filters)
        cold_pks = self.cold_index.query_with_index(object_type, filters)

        # 合并结果
        all_pks = hot_pks | warm_pks | cold_pks

        # 记录访问
        for pk in all_pks:
            self.record_access(object_type, pk)

        # 获取实际对象
        result = []
        result.extend(self.hot_index.find_objects_by_primary_key(object_type, list(hot_pks)))
        result.extend(self.warm_index.find_objects_by_primary_key(object_type, list(warm_pks)))
        result.extend(self.cold_index.find_objects_by_primary_key(object_type, list(cold_pks)))

        return [obj for obj in result if obj is not None]

    def _promote_to_warm(self, object_type: str, primary_key: Any):
        """提升到温数据层"""
        obj = self.cold_index.find_objects_by_primary_key(object_type, [primary_key])
        if obj:
            self.warm_index.index_object(obj[0])
            self.cold_index.remove_object(obj[0])

    def _promote_to_hot(self, object_type: str, primary_key: Any):
        """提升到热数据层"""
        # 尝试从温数据层获取
        obj = self.warm_index.find_objects_by_primary_key(object_type, [primary_key])
        if obj:
            self.hot_index.index_object(obj[0])
            self.warm_index.remove_object(obj[0])
        else:
            # 尝试从冷数据层获取
            obj = self.cold_index.find_objects_by_primary_key(object_type, [primary_key])
            if obj:
                self.hot_index.index_object(obj[0])
                self.cold_index.remove_object(obj[0])


class AdaptiveIndexManager:
    """自适应索引管理器"""

    def __init__(self, index_manager: AdvancedIndexManager):
        self.index_manager = index_manager
        self.query_patterns: Dict[str, Dict[str, Any]] = {}
        self.index_suggestions: List[IndexDefinition] = []

        self._analysis_interval = 300  # 5分钟分析一次
        self._last_analysis = 0

    def analyze_query_patterns(self):
        """分析查询模式，建议索引"""
        current_time = time.time()
        if current_time - self._last_analysis < self._analysis_interval:
            return

        self._last_analysis = current_time
        query_stats = self.index_manager.get_query_stats()

        # 分析高频慢查询
        for query_id, stats in query_stats.items():
            if stats['frequency'] > 10 and stats['avg_duration'] > 50:
                # 这里应该从查询中提取过滤条件
                # 简化实现，假设我们有一个方法来获取查询详情
                suggested_indexes = self._suggest_indexes_from_query(query_id)

                for index_def in suggested_indexes:
                    if self._should_create_index(index_def):
                        self.index_suggestions.append(index_def)

    def _suggest_indexes_from_query(self, query_id: str) -> List[IndexDefinition]:
        """根据查询建议索引"""
        # 这里应该解析查询ID来获取对象类型和过滤条件
        # 简化实现
        return [
            IndexDefinition("TestObject", ["property1"]),
            IndexDefinition("TestObject", ["property1", "property2"], "composite")
        ]

    def _should_create_index(self, index_def: IndexDefinition) -> bool:
        """判断是否应该创建索引"""
        index_key = f"{index_def.object_type}.{'_'.join(index_def.properties)}"

        # 检查索引是否已存在
        if index_key in self.index_manager.index_registry:
            return False

        # 简单的启发式规则
        if len(index_def.properties) == 1:
            return True  # 单属性索引总是有益的
        elif len(index_def.properties) == 2:
            return True  # 双属性复合索引通常有益
        else:
            return False  # 三属性以上需要更仔细的考虑

    def get_index_suggestions(self) -> List[IndexDefinition]:
        """获取索引建议"""
        return self.index_suggestions.copy()

    def create_suggested_indexes(self) -> List[str]:
        """创建建议的索引"""
        created_indexes = []

        for index_def in self.index_suggestions:
            try:
                if len(index_def.properties) == 1:
                    index_key = self.index_manager.create_property_index(
                        index_def.object_type,
                        index_def.properties[0]
                    )
                else:
                    index_key = self.index_manager.create_composite_index(
                        index_def.object_type,
                        index_def.properties
                    )

                created_indexes.append(index_key)
            except Exception as e:
                print(f"Failed to create index {index_def}: {e}")

        # 清空建议列表
        self.index_suggestions.clear()

        return created_indexes