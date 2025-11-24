"""
Ontology Framework Performance Module

性能优化模块，提供查询优化、索引管理、缓存机制等功能。
"""

from .indexing import AdvancedIndexManager, HierarchicalIndex, AdaptiveIndexManager
from .cache import MultiLevelCache, IntelligentCache, CacheStats
from .monitoring import PerformanceMonitor, RealtimeMonitor
from .optimization import QueryOptimizer, LazyObjectInstance, ObjectPool

__all__ = [
    'AdvancedIndexManager',
    'HierarchicalIndex',
    'AdaptiveIndexManager',
    'MultiLevelCache',
    'IntelligentCache',
    'CacheStats',
    'PerformanceMonitor',
    'RealtimeMonitor',
    'QueryOptimizer',
    'LazyObjectInstance',
    'ObjectPool',
]