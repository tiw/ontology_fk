"""
多级缓存系统

提供智能缓存管理，支持多级缓存、动态TTL、缓存统计等功能。
"""

import time
import threading
import json
import hashlib
from typing import Any, Optional, Dict, List, Set, Callable
from dataclasses import dataclass, field
from collections import OrderedDict, defaultdict
from abc import ABC, abstractmethod
from queue import Queue, Empty
import pickle
import weakref

# Redis支持（可选）
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


@dataclass
class CacheEntry:
    """缓存条目"""
    key: str
    value: Any
    created_at: float
    last_accessed: float
    access_count: int = 0
    ttl: Optional[float] = None
    size: int = 0

    def is_expired(self) -> bool:
        """检查是否过期"""
        if self.ttl is None:
            return False
        return time.time() - self.created_at > self.ttl

    def touch(self):
        """更新访问信息"""
        self.last_accessed = time.time()
        self.access_count += 1


@dataclass
class CacheStats:
    """缓存统计信息"""
    hits: int = 0
    misses: int = 0
    sets: int = 0
    deletes: int = 0
    evictions: int = 0

    @property
    def hit_rate(self) -> float:
        """命中率"""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    @property
    def miss_rate(self) -> float:
        """未命中率"""
        return 1.0 - self.hit_rate

    def record_hit(self):
        """记录命中"""
        self.hits += 1

    def record_miss(self):
        """记录未命中"""
        self.misses += 1

    def record_set(self):
        """记录设置"""
        self.sets += 1

    def record_delete(self):
        """记录删除"""
        self.deletes += 1

    def record_eviction(self):
        """记录驱逐"""
        self.evictions += 1

    def reset(self):
        """重置统计信息"""
        self.hits = 0
        self.misses = 0
        self.sets = 0
        self.deletes = 0
        self.evictions = 0


class BaseCache(ABC):
    """缓存基类"""

    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        pass

    @abstractmethod
    def set(self, key: str, value: Any, ttl: Optional[float] = None):
        """设置缓存值"""
        pass

    @abstractmethod
    def delete(self, key: str) -> bool:
        """删除缓存值"""
        pass

    @abstractmethod
    def clear(self):
        """清空缓存"""
        pass

    @abstractmethod
    def size(self) -> int:
        """缓存大小"""
        pass


class LRUCache(BaseCache):
    """LRU缓存实现"""

    def __init__(self, maxsize: int = 1000, ttl: Optional[float] = None):
        self.maxsize = maxsize
        self.default_ttl = ttl
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._stats = CacheStats()
        self._lock = threading.RLock()
        self._total_memory_usage = 0

    def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        with self._lock:
            if key not in self._cache:
                self._stats.record_miss()
                return None

            entry = self._cache[key]

            # 检查过期
            if entry.is_expired():
                del self._cache[key]
                self._total_memory_usage -= entry.size
                self._stats.record_miss()
                return None

            # 更新访问信息和位置
            entry.touch()
            self._cache.move_to_end(key)
            self._stats.record_hit()

            return entry.value

    def set(self, key: str, value: Any, ttl: Optional[float] = None):
        """设置缓存值"""
        with self._lock:
            # 计算值的大小
            try:
                value_size = len(pickle.dumps(value))
            except:
                value_size = 1024  # 默认大小

            # 检查是否需要驱逐
            self._ensure_capacity(value_size)

            # 如果key已存在，更新大小
            if key in self._cache:
                self._total_memory_usage -= self._cache[key].size

            # 创建新条目
            entry = CacheEntry(
                key=key,
                value=value,
                created_at=time.time(),
                last_accessed=time.time(),
                ttl=ttl or self.default_ttl,
                size=value_size
            )

            self._cache[key] = entry
            self._cache.move_to_end(key)
            self._total_memory_usage += value_size
            self._stats.record_set()

    def delete(self, key: str) -> bool:
        """删除缓存值"""
        with self._lock:
            if key not in self._cache:
                return False

            entry = self._cache.pop(key)
            self._total_memory_usage -= entry.size
            self._stats.record_delete()
            return True

    def clear(self):
        """清空缓存"""
        with self._lock:
            self._cache.clear()
            self._total_memory_usage = 0
            self._stats = CacheStats()

    def size(self) -> int:
        """缓存大小"""
        with self._lock:
            return len(self._cache)

    def get_stats(self) -> CacheStats:
        """获取统计信息"""
        with self._lock:
            return CacheStats(
                hits=self._stats.hits,
                misses=self._stats.misses,
                sets=self._stats.sets,
                deletes=self._stats.deletes,
                evictions=self._stats.evictions
            )

    def get_memory_usage(self) -> int:
        """获取内存使用量（字节）"""
        with self._lock:
            return self._total_memory_usage

    def _ensure_capacity(self, new_item_size: int):
        """确保有足够容量"""
        while (len(self._cache) >= self.maxsize or
               self._total_memory_usage + new_item_size > self.maxsize * 1024):

            # 移除最旧的条目
            if self._cache:
                key, entry = self._cache.popitem(last=False)
                self._total_memory_usage -= entry.size
                self._stats.record_eviction()
            else:
                break

    def cleanup_expired(self):
        """清理过期条目"""
        with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items()
                if entry.is_expired()
            ]

            for key in expired_keys:
                entry = self._cache.pop(key)
                self._total_memory_usage -= entry.size
                self._stats.record_eviction()


class RedisCache(BaseCache):
    """Redis缓存实现"""

    def __init__(self, host: str = 'localhost', port: int = 6379,
                 db: int = 0, password: Optional[str] = None,
                 ttl: Optional[float] = None, prefix: str = 'ontology:'):

        if not REDIS_AVAILABLE:
            raise ImportError("Redis is not available. Install redis-py to use RedisCache.")

        self.redis_client = redis.Redis(
            host=host, port=port, db=db, password=password,
            decode_responses=False  # 保持二进制数据
        )
        self.default_ttl = ttl
        self.prefix = prefix
        self._stats = CacheStats()
        self._lock = threading.RLock()

    def _make_key(self, key: str) -> str:
        """生成Redis键"""
        return f"{self.prefix}{key}"

    def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        try:
            redis_key = self._make_key(key)
            data = self.redis_client.get(redis_key)

            if data is None:
                with self._lock:
                    self._stats.record_miss()
                return None

            # 反序列化
            value = pickle.loads(data)

            with self._lock:
                self._stats.record_hit()

            return value

        except Exception as e:
            print(f"Redis get error: {e}")
            with self._lock:
                self._stats.record_miss()
            return None

    def set(self, key: str, value: Any, ttl: Optional[float] = None):
        """设置缓存值"""
        try:
            redis_key = self._make_key(key)
            data = pickle.dumps(value)

            # 使用指定的TTL或默认TTL
            expire_time = ttl or self.default_ttl

            if expire_time:
                self.redis_client.setex(redis_key, int(expire_time), data)
            else:
                self.redis_client.set(redis_key, data)

            with self._lock:
                self._stats.record_set()

        except Exception as e:
            print(f"Redis set error: {e}")

    def delete(self, key: str) -> bool:
        """删除缓存值"""
        try:
            redis_key = self._make_key(key)
            result = self.redis_client.delete(redis_key)

            if result > 0:
                with self._lock:
                    self._stats.record_delete()
                return True
            return False

        except Exception as e:
            print(f"Redis delete error: {e}")
            return False

    def clear(self):
        """清空缓存"""
        try:
            # 删除所有带前缀的键
            pattern = f"{self.prefix}*"
            keys = self.redis_client.keys(pattern)
            if keys:
                self.redis_client.delete(*keys)

            with self._lock:
                self._stats = CacheStats()

        except Exception as e:
            print(f"Redis clear error: {e}")

    def size(self) -> int:
        """缓存大小（近似值）"""
        try:
            pattern = f"{self.prefix}*"
            keys = self.redis_client.keys(pattern)
            return len(keys)
        except Exception as e:
            print(f"Redis size error: {e}")
            return 0

    def get_stats(self) -> CacheStats:
        """获取统计信息"""
        with self._lock:
            return CacheStats(
                hits=self._stats.hits,
                misses=self._stats.misses,
                sets=self._stats.sets,
                deletes=self._stats.deletes,
                evictions=self._stats.evictions
            )


class MultiLevelCache:
    """多级缓存系统"""

    def __init__(self, l1_size: int = 100, l2_size: int = 1000,
                 l3_redis: Optional[Dict[str, Any]] = None):
        # L1: 内存缓存 (最热数据)
        self.l1_cache = LRUCache(maxsize=l1_size, ttl=300)  # 5分钟

        # L2: 内存缓存 (热数据)
        self.l2_cache = LRUCache(maxsize=l2_size, ttl=1800)  # 30分钟

        # L3: Redis缓存 (温数据)
        if l3_redis and REDIS_AVAILABLE:
            self.l3_cache = RedisCache(**l3_redis, ttl=3600)  # 1小时
        else:
            self.l3_cache = None

        # 缓存统计
        self.global_stats = CacheStats()
        self.level_stats = {
            'L1': CacheStats(),
            'L2': CacheStats(),
            'L3': CacheStats() if self.l3_cache else None
        }

        # 访问模式分析
        self.access_patterns: Dict[str, List[float]] = defaultdict(list)

        self._lock = threading.RLock()

    def get(self, key: str) -> Optional[Any]:
        """分级缓存查询"""
        with self._lock:
            # 记录访问
            self._record_access(key)

            # L1 缓存
            value = self.l1_cache.get(key)
            if value is not None:
                self.level_stats['L1'].record_hit()
                self.global_stats.record_hit()
                return value

            # L2 缓存
            value = self.l2_cache.get(key)
            if value is not None:
                self.level_stats['L2'].record_hit()
                self.global_stats.record_hit()
                # 提升到 L1
                self.l1_cache.set(key, value)
                return value

            # L3 缓存
            if self.l3_cache:
                value = self.l3_cache.get(key)
                if value is not None:
                    self.level_stats['L3'].record_hit()
                    self.global_stats.record_hit()
                    # 提升到 L2
                    self.l2_cache.set(key, value)
                    return value

            # 全部未命中
            self.global_stats.record_miss()
            return None

    def set(self, key: str, value: Any, level: str = 'L2', ttl: Optional[float] = None):
        """分级缓存设置"""
        with self._lock:
            self.global_stats.record_set()

            if level == 'L1':
                self.l1_cache.set(key, value, ttl)
                self.level_stats['L1'].record_set()
            elif level == 'L2':
                self.l2_cache.set(key, value, ttl)
                self.level_stats['L2'].record_set()
            elif level == 'L3' and self.l3_cache:
                self.l3_cache.set(key, value, ttl)
                self.level_stats['L3'].record_set()
            else:
                # 默认存储在L2
                self.l2_cache.set(key, value, ttl)
                self.level_stats['L2'].record_set()

    def delete(self, key: str) -> bool:
        """从所有层级删除"""
        with self._lock:
            l1_deleted = self.l1_cache.delete(key)
            l2_deleted = self.l2_cache.delete(key)
            l3_deleted = self.l3_cache.delete(key) if self.l3_cache else False

            if l1_deleted or l2_deleted or l3_deleted:
                self.global_stats.record_delete()
                return True

            return False

    def clear(self):
        """清空所有缓存"""
        with self._lock:
            self.l1_cache.clear()
            self.l2_cache.clear()
            if self.l3_cache:
                self.l3_cache.clear()

            self.global_stats.reset()
            for stats in self.level_stats.values():
                if stats:
                    stats.reset()

    def get_comprehensive_stats(self) -> Dict[str, Any]:
        """获取综合统计信息"""
        with self._lock:
            stats = {
                'global': {
                    'hits': self.global_stats.hits,
                    'misses': self.global_stats.misses,
                    'hit_rate': self.global_stats.hit_rate,
                    'sets': self.global_stats.sets,
                    'deletes': self.global_stats.deletes
                },
                'levels': {}
            }

            for level, cache in [('L1', self.l1_cache), ('L2', self.l2_cache)]:
                level_stats = self.level_stats[level]
                cache_stats = cache.get_stats()

                stats['levels'][level] = {
                    'size': cache.size(),
                    'memory_bytes': cache.get_memory_usage(),
                    'hit_rate': level_stats.hit_rate,
                    'hits': level_stats.hits,
                    'misses': level_stats.misses
                }

            if self.l3_cache and self.level_stats['L3']:
                level_stats = self.level_stats['L3']
                stats['levels']['L3'] = {
                    'size': self.l3_cache.size(),
                    'hit_rate': level_stats.hit_rate,
                    'hits': level_stats.hits,
                    'misses': level_stats.misses
                }

            return stats

    def cleanup_expired(self):
        """清理过期条目"""
        self.l1_cache.cleanup_expired()
        self.l2_cache.cleanup_expired()

    def _record_access(self, key: str):
        """记录访问模式"""
        current_time = time.time()
        access_history = self.access_patterns[key]

        access_history.append(current_time)

        # 保留最近100次访问记录
        if len(access_history) > 100:
            access_history[:] = access_history[-100:]

    def get_access_frequency(self, key: str, window_seconds: int = 3600) -> float:
        """获取访问频率"""
        with self._lock:
            if key not in self.access_patterns:
                return 0.0

            current_time = time.time()
            cutoff_time = current_time - window_seconds

            recent_accesses = [
                ts for ts in self.access_patterns[key]
                if ts >= cutoff_time
            ]

            return len(recent_accesses) / (window_seconds / 60)  # 每分钟访问次数


class IntelligentCache:
    """智能缓存管理器"""

    def __init__(self, cache: MultiLevelCache):
        self.cache = cache
        self.query_analyzer = QueryPatternAnalyzer()
        self.cache_policy = AdaptiveCachePolicy()

    def should_cache(self, key: str, query: Any, result_size: int) -> bool:
        """判断是否应该缓存查询结果"""
        # 分析查询模式
        pattern = self.query_analyzer.analyze(query)

        # 缓存决策
        if pattern.frequency > 5 and pattern.avg_duration > 10:
            return True

        if result_size < 1000 and pattern.frequency > 10:
            return True

        return False

    def get_cache_ttl(self, key: str, query: Any) -> int:
        """动态TTL计算"""
        pattern = self.query_analyzer.analyze(query)

        # 基础TTL
        base_ttl = 300  # 5分钟

        # 根据访问频率调整
        if pattern.frequency > 50:
            base_ttl *= 2
        elif pattern.frequency > 100:
            base_ttl *= 3

        # 根据数据类型调整
        if self._is_real_time_data(query):
            base_ttl = min(base_ttl, 60)  # 最多1分钟

        return base_ttl

    def cache_query_result(self, key: str, query: Any, result: Any):
        """缓存查询结果"""
        if self.should_cache(key, query, self._estimate_result_size(result)):
            ttl = self.get_cache_ttl(key, query)
            level = self._determine_cache_level(key, query)
            self.cache.set(key, result, level=level, ttl=ttl)

    def _estimate_result_size(self, result: Any) -> int:
        """估算结果大小"""
        try:
            return len(pickle.dumps(result))
        except:
            return 1024  # 默认大小

    def _is_real_time_data(self, query: Any) -> bool:
        """判断是否为实时数据"""
        # 简化实现，可以根据查询的具体特征判断
        return hasattr(query, 'real_time') and query.real_time

    def _determine_cache_level(self, key: str, query: Any) -> str:
        """确定缓存层级"""
        access_freq = self.cache.get_access_frequency(key)

        if access_freq > 10:  # 高频访问
            return 'L1'
        elif access_freq > 1:  # 中频访问
            return 'L2'
        else:
            return 'L3'


class QueryPatternAnalyzer:
    """查询模式分析器"""

    def __init__(self):
        self.patterns: Dict[str, QueryPattern] = {}

    def analyze(self, query: Any) -> 'QueryPattern':
        """分析查询模式"""
        query_hash = self._hash_query(query)

        if query_hash not in self.patterns:
            self.patterns[query_hash] = QueryPattern(query)

        return self.patterns[query_hash]

    def _hash_query(self, query: Any) -> str:
        """生成查询哈希"""
        try:
            query_str = json.dumps(query, sort_keys=True, default=str)
            return hashlib.md5(query_str.encode()).hexdigest()
        except:
            return str(hash(query))

    def update_pattern(self, query: Any, duration: float):
        """更新查询模式"""
        pattern = self.analyze(query)
        pattern.update(duration)


@dataclass
class QueryPattern:
    """查询模式"""
    query: Any
    frequency: int = 0
    total_duration: float = 0.0
    avg_duration: float = 0.0
    last_executed: float = 0.0

    def update(self, duration: float):
        """更新模式信息"""
        self.frequency += 1
        self.total_duration += duration
        self.avg_duration = self.total_duration / self.frequency
        self.last_executed = time.time()


class AdaptiveCachePolicy:
    """自适应缓存策略"""

    def __init__(self):
        self.hit_rate_threshold = 0.7
        self.memory_threshold = 0.8

    def adjust_cache_sizes(self, cache: MultiLevelCache):
        """自适应调整缓存大小"""
        stats = cache.get_comprehensive_stats()

        # 检查L1命中率
        l1_hit_rate = stats['levels'].get('L1', {}).get('hit_rate', 0)
        if l1_hit_rate < self.hit_rate_threshold:
            # 增加L1缓存大小
            self._resize_cache_level(cache.l1_cache, int(cache.l1_cache.maxsize * 1.2))

        # 检查内存使用
        total_memory = sum(
            level.get('memory_bytes', 0)
            for level in stats['levels'].values()
        )

        # 这里可以添加更复杂的内存管理逻辑
        if total_memory > 100 * 1024 * 1024:  # 100MB
            cache.cleanup_expired()

    def _resize_cache_level(self, cache: LRUCache, new_size: int):
        """调整缓存级别大小"""
        # 简化实现，实际中可能需要更复杂的逻辑
        cache.maxsize = new_size