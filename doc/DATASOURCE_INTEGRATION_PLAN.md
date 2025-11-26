## 列式数据源接入计划

### 目标
在保持现有内存数据模型 API 不变的前提下，引入可插拔的数据源层，优先支持 DuckDB 等列式存储，实现大规模数据按需下推查询。

### 阶段拆解
1. **抽象数据源接口**
   - 定义 `DataSourceAdapter` 协议，覆盖基本的对象读取、扫描、聚合、写入能力。
   - 提供 `InMemoryDataSource` 适配现有 `_object_store`，作为默认实现。

2. **DuckDB 适配层**
   - 引入 `DuckDBDataSource`，支持基于配置的表/列映射、过滤条件下推与 `LIMIT`。
   - 约定 `DuckDBTableConfig`，明确主键列与属性映射关系。

3. **Ontology 改造**
   - 添加数据源注册/查找逻辑，将 `ObjectType.backing_datasource_id` 绑定到对应 adapter。
   - `add_object/get_object/get_objects_of_type`、`delete_object` 等入口通过数据源路由。
   - 创建对象时若缺少数据源默认回落到内存实现。

4. **ObjectSet 查询计划化**
   - 让 `ObjectSet` 持有数据源引用与查询参数（filters、limit），`all()` 时才物化。
   - `filter`、`aggregate`、`search_around` 等 API 调用数据源能力下推。

5. **链接与写入策略**
   - 优先支持只读 DuckDB，对写入操作抛出清晰异常。
   - 逐步拓展到写回/混合模式（可选）。

6. **验证与样例**
   - 提供示例配置（如 `examples/factory_ontology.py`）展示如何为对象类型绑定 DuckDB 表。
   - 增加基础单元测试覆盖 InMemory 与 DuckDB adapter 的关键路径（后续步骤）。

### 当前里程碑
- [x] 阶段 1：接口与内存 adapter
- [x] 阶段 2：DuckDB adapter
- [x] 阶段 3：Ontology 改造
- [x] 阶段 4：ObjectSet 查询下推
- [x] 阶段 5：链接/写入策略
- [x] 阶段 6：验证示例

