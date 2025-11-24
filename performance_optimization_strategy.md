# Ontology Framework 性能优化策略

## 项目概述

Ontology Framework 是一个基于 Python 的语义本体管理框架，支持复杂对象关系查询、函数系统和权限管理。本文档制定了全面的性能优化策略，以解决当前存在的性能问题，支持大规模数据处理。

---

## 1. 性能分析

### 1.1 当前架构分析

**核心组件**：
- **Ontology**: 中央管理器，负责类型注册和对象存储
- **ObjectInstance**: 运行时对象实例，支持派生属性计算
- **ObjectSet**: 对象集合，提供查询和导航功能
- **ObjectSetService**: 索引和查询服务
- **Functions**: 函数系统，支持业务逻辑封装

**存储架构**：
```python
# 当前内存存储结构
_ object_store: Dict[str, Dict[Any, ObjectInstance]]  # 类型 -> {主键 -> 实例}
_ links: List[Link]  # 链接列表
_ index: Dict[str, Dict[str, Dict[Any, List[ObjectInstance]]]]  # 简单索引
```

### 1.2 性能瓶颈识别

#### 关键瓶颈点

**1. 对象查询瓶颈 (O(n) 复杂度)**
```python
# 当前实现 - 线性扫描
def get_objects_of_type(self, type_name: str) -> List[ObjectInstance]:
    return list(self._object_store.get(type_name, {}).values())

# search_around 中的性能问题
for link in self._ontology.get_all_links():  # O(m) 链接遍历
    if link.link_type_api_name == link_type_api_name:  # O(m) 比较
```

**2. 派生属性计算瓶颈**
```python
# 每次访问都重新计算
def get(self, property_name: str) -> Any:
    if property_name in obj_type.derived_properties:
        # 函数调用没有缓存，重复计算
        return self._ontology.execute_function(derived_prop.backing_function_api_name, **{target_arg_name: self})
```

**3. 索引系统不足**
```python
# 当前索引结构过于简单，无法支持复合查询
self._index[api_name][prop][value] = []  # 只支持单属性精确匹配
```

**4. 内存使用效率**
- 所有对象常驻内存
- 没有延迟加载机制
- 重复数据存储

**5. 函数执行开销**
- 函数参数验证开销大
- 没有函数结果缓存
- 类型检查重复执行

### 1.3 基准性能指标

**当前性能基准**：
- 10K 对象查询：~100ms
- 1K 链接遍历：~50ms
- 派生属性计算：~10ms/次
- 复杂关系查询：~200ms+

**目标性能指标**：
- 10K 对象查询：<10ms (10x 提升)
- 1K 链接遍历：<5ms (10x 提升)
- 派生属性计算：<1ms/次 (10x 提升)
- 复杂关系查询：<20ms (10x 提升)

---

## 2. 性能监控指标体系

### 2.1 核心监控指标

#### 查询性能指标
```python
@dataclass
class QueryMetrics:
    query_type: str  # 查询类型
    execution_time: float  # 执行时间(ms)
    objects_scanned: int  # 扫描对象数
    objects_returned: int  # 返回对象数
    index_used: bool  # 是否使用索引
    cache_hit: bool  # 是否命中缓存

class PerformanceMonitor:
    def track_query(self, query_type: str, func):
        """查询性能装饰器"""
        def wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            result = func(*args, **kwargs)
            end_time = time.perf_counter()

            # 记录指标
            self.record_metric({
                'type': 'query',
                'query_type': query_type,
                'duration': (end_time - start_time) * 1000,
                'timestamp': time.time()
            })
            return result
        return wrapper
```

#### 系统性能指标
```python
@dataclass
class SystemMetrics:
    memory_usage_mb: float  # 内存使用量
    object_count_total: int  # 总对象数
    object_count_by_type: Dict[str, int]  # 按类型统计
    link_count_total: int  # 总链接数
    cache_hit_rate: float  # 缓存命中率
    index_utilization: float  # 索引利用率

    function_call_count: int  # 函数调用次数
    function_avg_duration: float  # 函数平均执行时间

    concurrent_users: int  # 并发用户数
    active_transactions: int  # 活跃事务数
```

### 2.2 实时监控系统

```python
class RealtimeMonitor:
    def __init__(self):
        self.metrics_collector = MetricsCollector()
        self.alert_manager = AlertManager()

    def setup_alerts(self):
        """设置性能告警阈值"""
        self.alert_manager.add_threshold('query_duration', 100.0)  # 100ms
        self.alert_manager.add_threshold('memory_usage', 1024.0)  # 1GB
        self.alert_manager.add_threshold('cache_hit_rate', 0.8)  # 80%

    def generate_dashboard(self):
        """生成性能监控面板"""
        return {
            'query_performance': self.get_query_stats(),
            'system_resources': self.get_system_stats(),
            'cache_performance': self.get_cache_stats(),
            'trend_analysis': self.get_trend_analysis()
        }
```

---

## 3. 优化策略

### 3.1 查询算法优化

#### 1. 索引驱动的查询引擎

```python
class AdvancedIndexManager:
    def __init__(self):
        # 多级索引结构
        self.primary_index: Dict[str, Dict[Any, ObjectInstance]] = {}  # 主键索引
        self.property_index: Dict[str, Dict[str, Dict[Any, Set[Any]]]] = {}  # 属性索引
        self.composite_index: Dict[str, Dict[Tuple, Set[Any]]] = {}  # 复合索引
        self.link_index: Dict[str, Dict[str, Set[Any]]] = {}  # 链接索引

    def create_composite_index(self, object_type: str, properties: List[str]):
        """创建复合索引"""
        index_key = f"{object_type}_{'_'.join(properties)}"
        self.composite_index[index_key] = {}

    def query_with_index(self, object_type: str, filters: Dict[str, Any]) -> List[ObjectInstance]:
        """使用索引进行优化查询"""
        # 检查是否有可用索引
        index_key = self._find_best_index(object_type, filters)
        if index_key:
            return self._indexed_query(object_type, index_key, filters)
        else:
            return self._fallback_query(object_type, filters)

    def _find_best_index(self, object_type: str, filters: Dict[str, Any]) -> Optional[str]:
        """选择最优索引"""
        # 优先级：复合索引 > 单属性索引 > 全表扫描
        filter_props = set(filters.keys())

        # 检查复合索引
        for index_key in self.composite_index:
            if object_type in index_key:
                index_props = set(index_key.split('_')[1:])
                if filter_props.issubset(index_props):
                    return index_key

        # 检查单属性索引
        for prop in filters.keys():
            if f"{object_type}_{prop}" in self.property_index:
                return f"{object_type}_{prop}"

        return None
```

#### 2. 查询优化器

```python
class QueryOptimizer:
    def __init__(self, index_manager: AdvancedIndexManager):
        self.index_manager = index_manager
        self.query_plans: Dict[str, QueryPlan] = {}

    def optimize_query(self, query: Query) -> QueryPlan:
        """优化查询执行计划"""
        query_hash = query.hash()

        # 检查缓存的执行计划
        if query_hash in self.query_plans:
            return self.query_plans[query_hash]

        # 生成新的执行计划
        plan = self._generate_optimal_plan(query)
        self.query_plans[query_hash] = plan
        return plan

    def _generate_optimal_plan(self, query: Query) -> QueryPlan:
        """生成最优执行计划"""
        steps = []

        # 1. 最小化扫描范围
        if query.filters:
            best_index = self.index_manager._find_best_index(
                query.object_type, query.filters
            )
            if best_index:
                steps.append(IndexScanStep(best_index, query.filters))
            else:
                steps.append(FilterStep(query.filters))
        else:
            steps.append(FullTableScanStep())

        # 2. 关系查询优化
        if query.joins:
            steps.extend(self._optimize_joins(query.joins))

        # 3. 排序和分页
        if query.order_by:
            steps.append(SortStep(query.order_by))

        if query.limit:
            steps.append(LimitStep(query.limit))

        return QueryPlan(steps)
```

### 3.2 索引系统设计

#### 1. 多层次索引架构

```python
class HierarchicalIndex:
    """分层索引架构"""

    def __init__(self):
        # L1: 内存热数据索引
        self.hot_index: Dict[str, L1Index] = {}

        # L2: 温数据索引 (压缩存储)
        self.warm_index: Dict[str, L2Index] = {}

        # L3: 冷数据索引 (磁盘存储)
        self.cold_index: Dict[str, L3Index] = {}

        self.access_tracker = AccessTracker()

    def index_object(self, obj: ObjectInstance):
        """智能索引分层"""
        access_freq = self.access_tracker.get_frequency(obj.object_type_api_name, obj.primary_key_value)

        if access_freq > 100:  # 热数据
            self.hot_index.setdefault(obj.object_type_api_name, L1Index()).add(obj)
        elif access_freq > 10:  # 温数据
            self.warm_index.setdefault(obj.object_type_api_name, L2Index()).add(obj)
        else:  # 冷数据
            self.cold_index.setdefault(obj.object_type_api_name, L3Index()).add(obj)

    def query(self, object_type: str, query: Query) -> List[ObjectInstance]:
        """分层查询"""
        results = []

        # 优先查询热数据
        if object_type in self.hot_index:
            results.extend(self.hot_index[object_type].query(query))

        # 如果需要更多数据，查询温数据
        if len(results) < query.limit or not query.limit:
            if object_type in self.warm_index:
                results.extend(self.warm_index[object_type].query(query))

        # 最后查询冷数据
        if len(results) < query.limit or not query.limit:
            if object_type in self.cold_index:
                results.extend(self.cold_index[object_type].query(query))

        return results
```

#### 2. 自适应索引

```python
class AdaptiveIndexManager:
    """自适应索引管理器"""

    def __init__(self):
        self.query_stats: Dict[str, QueryStats] = {}
        self.index_usage_stats: Dict[str, IndexUsageStats] = {}

    def analyze_query_patterns(self):
        """分析查询模式，自动创建索引"""
        for query_hash, stats in self.query_stats.items():
            if stats.frequency > 10 and stats.avg_duration > 50:  # 高频慢查询
                suggested_indexes = self._suggest_indexes(query_hash)
                for index_def in suggested_indexes:
                    if self._should_create_index(index_def):
                        self.create_index(index_def)

    def _suggest_indexes(self, query_hash: str) -> List[IndexDefinition]:
        """根据查询模式建议索引"""
        query = self.query_stats[query_hash].query
        suggestions = []

        # 单属性索引建议
        for prop in query.filters.keys():
            suggestions.append(IndexDefinition(
                object_type=query.object_type,
                properties=[prop],
                index_type='btree'
            ))

        # 复合索引建议
        if len(query.filters) > 1:
            suggestions.append(IndexDefinition(
                object_type=query.object_type,
                properties=list(query.filters.keys()),
                index_type='composite'
            ))

        return suggestions
```

### 3.3 缓存机制实现

#### 1. 多级缓存系统

```python
class MultiLevelCache:
    """多级缓存系统"""

    def __init__(self):
        # L1: 内存缓存 (最热数据)
        self.l1_cache = LRUCache(maxsize=1000, ttl=300)  # 5分钟

        # L2: 内存缓存 (热数据)
        self.l2_cache = LRUCache(maxsize=10000, ttl=1800)  # 30分钟

        # L3: Redis 缓存 (温数据)
        self.l3_cache = RedisCache(ttl=3600)  # 1小时

        # 缓存统计
        self.cache_stats = CacheStats()

    def get(self, key: str) -> Optional[Any]:
        """分级缓存查询"""
        # L1 缓存
        value = self.l1_cache.get(key)
        if value is not None:
            self.cache_stats.record_hit('L1')
            return value

        # L2 缓存
        value = self.l2_cache.get(key)
        if value is not None:
            self.cache_stats.record_hit('L2')
            # 提升到 L1
            self.l1_cache.set(key, value)
            return value

        # L3 缓存
        value = self.l3_cache.get(key)
        if value is not None:
            self.cache_stats.record_hit('L3')
            # 提升到 L2
            self.l2_cache.set(key, value)
            return value

        self.cache_stats.record_miss()
        return None

    def set(self, key: str, value: Any, level: str = 'L2'):
        """分级缓存设置"""
        if level == 'L1':
            self.l1_cache.set(key, value)
        elif level == 'L2':
            self.l2_cache.set(key, value)
        else:
            self.l3_cache.set(key, value)
```

#### 2. 智能缓存策略

```python
class IntelligentCache:
    """智能缓存管理器"""

    def __init__(self):
        self.access_pattern_analyzer = AccessPatternAnalyzer()
        self.cache_policy = AdaptiveCachePolicy()

    def should_cache(self, query: Query, result_size: int) -> bool:
        """判断是否应该缓存查询结果"""
        # 分析查询模式
        pattern = self.access_pattern_analyzer.analyze(query)

        # 缓存决策
        if pattern.frequency > 5 and pattern.avg_duration > 10:
            return True

        if result_size < 1000 and pattern.frequency > 10:
            return True

        return False

    def get_cache_ttl(self, query: Query) -> int:
        """动态TTL计算"""
        pattern = self.access_pattern_analyzer.analyze(query)

        # 基础TTL
        base_ttl = 300  # 5分钟

        # 根据访问频率调整
        if pattern.frequency > 50:
            base_ttl *= 2
        elif pattern.frequency > 100:
            base_ttl *= 3

        # 根据数据更新频率调整
        update_freq = self.get_data_update_frequency(query.object_type)
        if update_freq > 0.1:  # 高频更新
            base_ttl = min(base_ttl, 60)  # 最多1分钟

        return base_ttl
```

### 3.4 内存管理优化

#### 1. 对象池化

```python
class ObjectPool:
    """对象实例池"""

    def __init__(self, object_type: ObjectType, initial_size: int = 100):
        self.object_type = object_type
        self.pool = Queue()
        self.in_use = set()

        # 预分配对象
        for _ in range(initial_size):
            obj = self._create_object()
            self.pool.put(obj)

    def acquire(self, primary_key: Any, properties: Dict[str, Any]) -> ObjectInstance:
        """获取对象实例"""
        try:
            obj = self.pool.get_nowait()
        except Empty:
            obj = self._create_object()

        # 重置对象状态
        obj.primary_key_value = primary_key
        obj.property_values.clear()
        obj.property_values.update(properties)

        self.in_use.add(id(obj))
        return obj

    def release(self, obj: ObjectInstance):
        """释放对象实例"""
        if id(obj) in self.in_use:
            # 清理敏感数据
            obj.property_values.clear()
            self.in_use.remove(id(obj))
            self.pool.put(obj)
```

#### 2. 延迟加载

```python
class LazyObjectInstance(ObjectInstance):
    """延迟加载对象实例"""

    def __init__(self, object_type: str, primary_key: Any,
                 data_loader: Callable, ontology: 'Ontology' = None):
        super().__init__(object_type, primary_key)
        self._data_loader = data_loader
        self._loaded = False
        self._ontology = ontology

    def get(self, property_name: str) -> Any:
        """延迟属性加载"""
        if not self._loaded:
            self._load_properties()

        return super().get(property_name)

    def _load_properties(self):
        """加载对象属性"""
        if not self._loaded:
            properties = self._data_loader(self.object_type_api_name, self.primary_key_value)
            self.property_values.update(properties)
            self._loaded = True
```

#### 3. 内存监控

```python
class MemoryManager:
    """内存管理器"""

    def __init__(self, max_memory_mb: float = 1024):
        self.max_memory_mb = max_memory_mb
        self.current_usage_mb = 0
        self.object_sizes = {}

    def track_object_allocation(self, obj: ObjectInstance):
        """跟踪对象内存分配"""
        size = self._estimate_object_size(obj)
        self.current_usage_mb += size / (1024 * 1024)

        # 检查内存限制
        if self.current_usage_mb > self.max_memory_mb:
            self._trigger_gc()

    def _trigger_gc(self):
        """触发垃圾回收"""
        # 1. 清理过期缓存
        cache_manager.cleanup_expired()

        # 2. 释放不活跃对象
        self._release_inactive_objects()

        # 3. 强制Python GC
        import gc
        gc.collect()

    def _release_inactive_objects(self):
        """释放不活跃对象"""
        # 根据LRU策略释放对象
        threshold_time = time.time() - 300  # 5分钟未访问

        for obj_type, objects in self.object_store.items():
            inactive_keys = [
                key for key, obj in objects.items()
                if obj.last_accessed < threshold_time
            ]

            for key in inactive_keys:
                del objects[key]
```

---

## 4. 性能测试

### 4.1 基准测试设计

```python
class PerformanceBenchmark:
    """性能基准测试"""

    def __init__(self):
        self.test_data_generator = TestDataGenerator()
        self.results_collector = BenchmarkResults()

    def run_all_benchmarks(self):
        """运行所有基准测试"""
        test_scenarios = [
            self.benchmark_object_creation,
            self.benchmark_object_retrieval,
            self.benchmark_complex_queries,
            self.benchmark_relationship_queries,
            self.benchmark_derived_properties,
            self.benchmark_concurrent_access
        ]

        results = {}
        for scenario in test_scenarios:
            result = scenario()
            results[scenario.__name__] = result

        return results

    def benchmark_object_retrieval(self):
        """对象检索基准测试"""
        sizes = [1000, 5000, 10000, 50000]
        results = {}

        for size in sizes:
            # 准备测试数据
            ontology = self._create_test_ontology(size)

            # 测试不同查询场景
            test_cases = [
                ('primary_key_lookup', self._test_pk_lookup),
                ('property_filter', self._test_property_filter),
                ('range_query', self._test_range_query),
                ('full_scan', self._test_full_scan)
            ]

            case_results = {}
            for case_name, test_func in test_cases:
                duration = self._measure_time(test_func, ontology)
                case_results[case_name] = duration

            results[size] = case_results

        return results

    def _test_pk_lookup(self, ontology: Ontology) -> float:
        """主键查询测试"""
        start_time = time.perf_counter()

        for i in range(1000):
            pk = f"test_obj_{i % 100}"
            obj = ontology.get_object("TestObject", pk)

        end_time = time.perf_counter()
        return (end_time - start_time) * 1000  # ms
```

### 4.2 负载测试场景

```python
class LoadTestScenario:
    """负载测试场景"""

    def __init__(self):
        self.concurrent_users = 0
        self.operations_per_second = 0

    def test_concurrent_reads(self, user_count: int = 100, duration: int = 60):
        """并发读取测试"""
        ontology = self._create_large_dataset()

        async def user_simulation(user_id: int):
            """模拟用户操作"""
            operations = 0
            start_time = time.time()

            while time.time() - start_time < duration:
                # 随机查询操作
                query_type = random.choice(['pk_lookup', 'filter', 'search_around'])

                if query_type == 'pk_lookup':
                    pk = f"obj_{random.randint(1, 10000)}"
                    ontology.get_object("TestObject", pk)

                elif query_type == 'filter':
                    objects = ontology.get_objects_of_type("TestObject")
                    filtered = [obj for obj in objects if obj.get("status") == "active"]

                elif query_type == 'search_around':
                    base_objects = ontology.get_objects_of_type("TestObject")[:10]
                    for obj in base_objects:
                        obj.search_around("test_link")

                operations += 1
                await asyncio.sleep(0.01)  # 10ms间隔

            return operations

        # 启动并发用户
        tasks = [user_simulation(i) for i in range(user_count)]
        results = await asyncio.gather(*tasks)

        total_operations = sum(results)
        ops_per_second = total_operations / duration

        return {
            'total_operations': total_operations,
            'operations_per_second': ops_per_second,
            'average_latency': (user_count * duration * 1000) / total_operations  # ms
        }
```

### 4.3 性能回归检测

```python
class PerformanceRegressionDetector:
    """性能回归检测器"""

    def __init__(self):
        self.baseline_results = {}
        self.regression_threshold = 0.1  # 10%性能下降阈值

    def set_baseline(self, test_name: str, results: Dict[str, float]):
        """设置性能基线"""
        self.baseline_results[test_name] = results

    def check_regression(self, test_name: str, current_results: Dict[str, float]) -> List[RegressionReport]:
        """检查性能回归"""
        regressions = []

        if test_name not in self.baseline_results:
            return regressions

        baseline = self.baseline_results[test_name]

        for metric, current_value in current_results.items():
            if metric in baseline:
                baseline_value = baseline[metric]

                # 计算性能变化
                if baseline_value > 0:  # 时间类指标，越小越好
                    change_ratio = (current_value - baseline_value) / baseline_value
                    if change_ratio > self.regression_threshold:
                        regressions.append(RegressionReport(
                            metric=metric,
                            baseline_value=baseline_value,
                            current_value=current_value,
                            change_ratio=change_ratio,
                            severity='high' if change_ratio > 0.2 else 'medium'
                        ))

        return regressions

    def generate_regression_report(self, regressions: List[RegressionReport]) -> str:
        """生成回归报告"""
        if not regressions:
            return "✅ 未发现性能回归"

        report = ["🚨 检测到性能回归:", ""]

        for regression in regressions:
            severity_icon = "🔴" if regression.severity == 'high' else "🟡"
            report.append(
                f"{severity_icon} {regression.metric}: "
                f"{regression.baseline_value:.2f}ms → {regression.current_value:.2f}ms "
                f"(+{regression.change_ratio:.1%})"
            )

        report.append("")
        report.append("建议立即分析代码变更并优化性能瓶颈。")

        return "\n".join(report)
```

---

## 5. 实施计划

### 5.1 第一阶段：基础优化 (2周)

**目标**：解决最明显的性能瓶颈

**任务清单**：
- [ ] 实现基础索引系统
- [ ] 优化对象查询算法
- [ ] 添加简单缓存机制
- [ ] 建立性能监控基础设施

**预期收益**：
- 查询性能提升 5-10x
- 内存使用减少 20-30%

### 5.2 第二阶段：高级优化 (3周)

**目标**：实现全面的性能优化

**任务清单**：
- [ ] 实现多级缓存系统
- [ ] 优化派生属性计算
- [ ] 实现对象池化和延迟加载
- [ ] 完善索引系统

**预期收益**：
- 整体性能提升 10-20x
- 内存使用减少 40-50%
- 支持 100K+ 对象规模

### 5.3 第三阶段：生产优化 (2周)

**目标**：生产环境稳定性优化

**任务清单**：
- [ ] 实现完整的性能监控系统
- [ ] 建立自动化测试和回归检测
- [ ] 优化并发处理能力
- [ ] 文档和最佳实践完善

**预期收益**：
- 生产环境稳定性提升
- 支持高并发访问
- 完善的性能监控和告警

---

## 6. 监控和维护

### 6.1 持续性能监控

```python
class ContinuousPerformanceMonitor:
    """持续性能监控"""

    def __init__(self):
        self.metrics_history = TimeSeriesData()
        self.alert_system = AlertSystem()

    def setup_monitoring(self):
        """设置监控指标"""
        # 核心性能指标
        self.monitor_metric('query_response_time', threshold_ms=100)
        self.monitor_metric('memory_usage_percent', threshold=80)
        self.monitor_metric('cache_hit_rate', threshold=0.7)
        self.monitor_metric('error_rate', threshold=0.01)

    def monitor_metric(self, metric_name: str, threshold: float):
        """监控单个指标"""
        def alert_if_needed(current_value: float):
            if current_value > threshold:
                self.alert_system.send_alert(
                    severity='high',
                    message=f'{metric_name} 超过阈值: {current_value:.2f} > {threshold:.2f}',
                    metric=metric_name,
                    value=current_value
                )

        self.alert_system.add_rule(metric_name, alert_if_needed)
```

### 6.2 性能调优建议

#### 定期优化任务

1. **每周**：
   - 分析慢查询日志
   - 检查缓存命中率
   - 监控内存使用趋势

2. **每月**：
   - 分析查询模式变化
   - 优化索引配置
   - 更新性能基线

3. **每季度**：
   - 全面性能评估
   - 架构优化评估
   - 技术债务清理

#### 性能优化最佳实践

1. **查询优化**：
   - 总是使用索引查询
   - 避免全表扫描
   - 合理使用分页

2. **缓存策略**：
   - 缓存热点数据
   - 设置合理的TTL
   - 监控缓存命中率

3. **内存管理**：
   - 及时释放不用的对象
   - 使用对象池
   - 监控内存泄漏

---

## 7. 总结

本性能优化策略通过系统性的分析和优化，预期可以实现：

- **查询性能提升 10-20x**
- **内存使用减少 40-50%**
- **支持 100K+ 对象规模**
- **高并发访问能力**
- **完善的监控告警体系**

通过分阶段实施，确保系统在优化的同时保持稳定性和可维护性。持续的监控和维护将保证系统长期保持高性能运行。

---

## 附录：关键文件清单

### 实施文件
- `/src/ontology_framework/performance/` - 性能优化模块
- `/src/ontology_framework/indexing/` - 索引系统
- `/src/ontology_framework/cache/` - 缓存系统
- `/tests/performance/` - 性能测试套件

### 配置文件
- `/config/performance.yaml` - 性能配置
- `/config/monitoring.yaml` - 监控配置
- `/config/cache.yaml` - 缓存配置

### 监控脚本
- `/scripts/performance_monitor.py` - 性能监控
- `/scripts/benchmark_runner.py` - 基准测试
- `/scripts/regression_detector.py` - 回归检测