from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Protocol, Tuple, runtime_checkable, TYPE_CHECKING

try:  # pragma: no cover - optional dependency
    import duckdb  # type: ignore
except ImportError:  # pragma: no cover
    duckdb = None

if TYPE_CHECKING:  # pragma: no cover
    from .core import ObjectInstance, ObjectType


class DataSourceError(RuntimeError):
    """统一的数据源异常，便于上层捕获并转换。"""


@runtime_checkable
class DataSourceAdapter(Protocol):
    """所有数据源实现都需要遵循的协议。"""

    id: str
    read_only: bool

    def fetch_object(self, object_type: "ObjectType", primary_key: Any) -> Optional["ObjectInstance"]:
        ...

    def scan(
        self,
        object_type: "ObjectType",
        filters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
    ) -> Iterable["ObjectInstance"]:
        ...

    def aggregate(
        self,
        object_type: "ObjectType",
        property_name: str,
        function: str,
        filters: Optional[Dict[str, Any]] = None,
    ) -> float:
        ...

    def upsert(self, object_type: "ObjectType", instance: "ObjectInstance") -> None:
        ...

    def delete(self, object_type: "ObjectType", primary_key: Any) -> None:
        ...


class InMemoryDataSource:
    """复用既有 _object_store 的内存实现，充当默认数据源。"""

    def __init__(self, storage: Dict[str, Dict[Any, "ObjectInstance"]], adapter_id: str = "__memory__"):
        self._storage = storage
        self.id = adapter_id
        self.read_only = False

    def fetch_object(self, object_type: "ObjectType", primary_key: Any) -> Optional["ObjectInstance"]:
        return self._storage.get(object_type.api_name, {}).get(primary_key)

    def scan(
        self,
        object_type: "ObjectType",
        filters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
    ) -> Iterable["ObjectInstance"]:
        items = list(self._storage.get(object_type.api_name, {}).values())
        if filters:
            items = [
                obj
                for obj in items
                if all(obj.property_values.get(k) == v for k, v in filters.items())
            ]
        if limit is not None:
            items = items[:limit]
        return items

    def aggregate(
        self,
        object_type: "ObjectType",
        property_name: str,
        function: str,
        filters: Optional[Dict[str, Any]] = None,
    ) -> float:
        values = [
            obj.property_values.get(property_name)
            for obj in self.scan(object_type, filters)
            if obj.property_values.get(property_name) is not None
        ]
        if not values:
            return 0.0

        if function == "sum":
            return float(sum(values))
        if function == "avg":
            return float(sum(values) / len(values))
        if function == "max":
            return float(max(values))
        if function == "min":
            return float(min(values))
        if function == "count":
            return float(len(values))
        raise ValueError(f"Unsupported aggregation function: {function}")

    def upsert(self, object_type: "ObjectType", instance: "ObjectInstance") -> None:
        self._storage.setdefault(object_type.api_name, {})[instance.primary_key_value] = instance

    def delete(self, object_type: "ObjectType", primary_key: Any) -> None:
        self._storage.get(object_type.api_name, {}).pop(primary_key, None)


@dataclass
class DuckDBTableConfig:
    """描述对象类型与 DuckDB 表的映射关系。"""

    table: str
    primary_key_column: str
    column_mapping: Dict[str, str]

    def resolve_column(self, property_name: str) -> str:
        if property_name not in self.column_mapping:
            raise DataSourceError(
                f"Property '{property_name}' not mapped for DuckDB table {self.table}"
            )
        return self.column_mapping[property_name]


class DuckDBDataSource:
    """基于 DuckDB 的数据源实现，默认只读。"""

    def __init__(
        self,
        adapter_id: str,
        connection: "duckdb.DuckDBPyConnection",
        table_configs: Dict[str, DuckDBTableConfig],
        read_only: bool = True,
    ):
        if duckdb is None:
            raise ImportError("duckdb python 包未安装，无法使用 DuckDBDataSource")

        self.id = adapter_id
        self._conn = connection
        self._configs = table_configs
        self.read_only = read_only

    def _config_for(self, object_type: "ObjectType") -> DuckDBTableConfig:
        if object_type.api_name not in self._configs:
            raise DataSourceError(f"No DuckDB mapping for object type {object_type.api_name}")
        return self._configs[object_type.api_name]

    def _build_select_clause(self, config: DuckDBTableConfig) -> str:
        parts = []
        for prop, column in config.column_mapping.items():
            parts.append(f"{column} AS {prop}")
        return ", ".join(parts)

    def _build_filters(
        self,
        config: DuckDBTableConfig,
        filters: Optional[Dict[str, Any]],
    ) -> Tuple[str, List[Any]]:
        if not filters:
            return "", []
        clauses: List[str] = []
        params: List[Any] = []
        for prop, value in filters.items():
            column = config.resolve_column(prop)
            clauses.append(f"{column} = ?")
            params.append(value)
        return " WHERE " + " AND ".join(clauses), params

    def fetch_object(self, object_type: "ObjectType", primary_key: Any) -> Optional["ObjectInstance"]:
        pk_prop = object_type.primary_key or next(iter(object_type.properties.keys()), None)
        if not pk_prop:
            raise DataSourceError(f"Object type {object_type.api_name} 缺少主键信息，无法查询")
        filters = {pk_prop: primary_key}
        rows = list(self.scan(object_type, filters=filters, limit=1))
        return rows[0] if rows else None

    def scan(
        self,
        object_type: "ObjectType",
        filters: Optional[Dict[str, Any]] = None,
        limit: Optional[int] = None,
    ) -> Iterable["ObjectInstance"]:
        from .core import ObjectInstance  # 延迟导入避免循环依赖

        config = self._config_for(object_type)
        select_clause = self._build_select_clause(config)
        where_clause, params = self._build_filters(config, filters)
        sql = f"SELECT {select_clause} FROM {config.table}{where_clause}"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)

        cursor = self._conn.execute(sql, params)
        props = list(config.column_mapping.keys())
        for row in cursor.fetchall():
            row_dict = {prop: row[idx] for idx, prop in enumerate(props)}
            pk_prop = object_type.primary_key
            if not pk_prop:
                raise DataSourceError(f"Object type {object_type.api_name} 缺少 primary_key")
            pk_value = row_dict.get(pk_prop)
            yield ObjectInstance(
                object_type_api_name=object_type.api_name,
                primary_key_value=pk_value,
                property_values=row_dict,
            )

    def aggregate(
        self,
        object_type: "ObjectType",
        property_name: str,
        function: str,
        filters: Optional[Dict[str, Any]] = None,
    ) -> float:
        config = self._config_for(object_type)
        column = config.resolve_column(property_name)
        where_clause, params = self._build_filters(config, filters)
        sql = f"SELECT {function.upper()}({column}) FROM {config.table}{where_clause}"
        cursor = self._conn.execute(sql, params)
        value = cursor.fetchone()[0]
        return float(value or 0.0)

    def upsert(self, object_type: "ObjectType", instance: "ObjectInstance") -> None:
        if self.read_only:
            raise DataSourceError("DuckDBDataSource 当前为只读，无法写入")
        config = self._config_for(object_type)
        columns = list(config.column_mapping.values())
        placeholders = ", ".join(["?"] * len(columns))
        sql = f"INSERT OR REPLACE INTO {config.table} ({', '.join(columns)}) VALUES ({placeholders})"
        values = [instance.property_values.get(prop) for prop in config.column_mapping.keys()]
        self._conn.execute(sql, values)

    def delete(self, object_type: "ObjectType", primary_key: Any) -> None:
        if self.read_only:
            raise DataSourceError("DuckDBDataSource 当前为只读，无法删除")
        config = self._config_for(object_type)
        pk_column = config.primary_key_column
        sql = f"DELETE FROM {config.table} WHERE {pk_column} = ?"
        self._conn.execute(sql, [primary_key])

