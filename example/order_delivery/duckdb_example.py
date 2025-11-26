from __future__ import annotations

import duckdb

from ontology_framework.core import ObjectInstance, Ontology
from ontology_framework.datasources import DuckDBDataSource, DuckDBTableConfig
from example.order_delivery.schema import setup_ontology


def _create_duckdb_tables(conn: duckdb.DuckDBPyConnection):
    conn.execute(
        """
        CREATE TABLE orders (
            order_id TEXT PRIMARY KEY,
            user_id TEXT,
            merchant_id TEXT,
            rider_id TEXT,
            status TEXT,
            items TEXT,
            user_expected_t_min INTEGER,
            ts_created DOUBLE,
            ts_merchant_accepted DOUBLE,
            ts_rider_called DOUBLE,
            ts_merchant_out DOUBLE,
            ts_rider_arrived_store DOUBLE,
            ts_rider_picked DOUBLE,
            ts_delivered DOUBLE
        );
        """
    )
    conn.execute(
        """
        CREATE TABLE merchants (
            merchant_id TEXT PRIMARY KEY,
            name TEXT,
            address TEXT
        );
        """
    )
    conn.execute(
        """
        CREATE TABLE riders (
            rider_id TEXT PRIMARY KEY,
            name TEXT,
            phone TEXT
        );
        """
    )


def _duckdb_configs() -> dict[str, DuckDBTableConfig]:
    return {
        "Order": DuckDBTableConfig(
            table="orders",
            primary_key_column="order_id",
            column_mapping={
                "order_id": "order_id",
                "user_id": "user_id",
                "merchant_id": "merchant_id",
                "rider_id": "rider_id",
                "status": "status",
                "items": "items",
                "user_expected_t_min": "user_expected_t_min",
                "ts_created": "ts_created",
                "ts_merchant_accepted": "ts_merchant_accepted",
                "ts_rider_called": "ts_rider_called",
                "ts_merchant_out": "ts_merchant_out",
                "ts_rider_arrived_store": "ts_rider_arrived_store",
                "ts_rider_picked": "ts_rider_picked",
                "ts_delivered": "ts_delivered",
            },
        ),
        "Merchant": DuckDBTableConfig(
            table="merchants",
            primary_key_column="merchant_id",
            column_mapping={
                "merchant_id": "merchant_id",
                "name": "name",
                "address": "address",
            },
        ),
        "Rider": DuckDBTableConfig(
            table="riders",
            primary_key_column="rider_id",
            column_mapping={
                "rider_id": "rider_id",
                "name": "name",
                "phone": "phone",
            },
        ),
    }


def bind_order_demo_types(ontology: Ontology, datasource_id: str):
    for type_name in ("Order", "Merchant", "Rider"):
        if type_name in ontology.object_types:
            ontology.object_types[type_name].backing_datasource_id = datasource_id


def seed_sample_data(ontology: Ontology):
    merchants = [
        ObjectInstance(
            "Merchant",
            "merchant_shanghai",
            {
                "merchant_id": "merchant_shanghai",
                "name": "Shanghai Snacks",
                "address": "No.1 Bund",
            },
        ),
        ObjectInstance(
            "Merchant",
            "merchant_beijing",
            {
                "merchant_id": "merchant_beijing",
                "name": "Beijing Buns",
                "address": "Chaoyang Plaza",
            },
        ),
    ]
    for merchant in merchants:
        ontology.add_object(merchant)

    riders = [
        ObjectInstance(
            "Rider",
            "rider_anna",
            {"rider_id": "rider_anna", "name": "Anna", "phone": "555-1001"},
        ),
        ObjectInstance(
            "Rider",
            "rider_li",
            {"rider_id": "rider_li", "name": "Li", "phone": "555-1002"},
        ),
    ]
    for rider in riders:
        ontology.add_object(rider)

    base_ts = 1_700_000_000.0
    orders = [
        ObjectInstance(
            "Order",
            "order_duck_1",
            {
                "order_id": "order_duck_1",
                "user_id": "user_01",
                "merchant_id": "merchant_shanghai",
                "rider_id": "rider_anna",
                "status": "COMPLETED",
                "items": "noodles",
                "user_expected_t_min": 30,
                "ts_created": base_ts,
                "ts_merchant_accepted": base_ts + 120,
                "ts_rider_called": base_ts + 240,
                "ts_merchant_out": base_ts + 600,
                "ts_rider_arrived_store": base_ts + 660,
                "ts_rider_picked": base_ts + 720,
                "ts_delivered": base_ts + 1_200,
            },
        ),
        ObjectInstance(
            "Order",
            "order_duck_2",
            {
                "order_id": "order_duck_2",
                "user_id": "user_02",
                "merchant_id": "merchant_beijing",
                "rider_id": "rider_li",
                "status": "COMPLETED",
                "items": "dumplings",
                "user_expected_t_min": 25,
                "ts_created": base_ts + 3_600,
                "ts_merchant_accepted": base_ts + 3_750,
                "ts_rider_called": base_ts + 3_900,
                "ts_merchant_out": base_ts + 4_500,
                "ts_rider_arrived_store": base_ts + 4_520,
                "ts_rider_picked": base_ts + 4_560,
                "ts_delivered": base_ts + 4_800,
            },
        ),
    ]

    for order in orders:
        ontology.add_object(order)
        ontology.create_link(
            "OrderHasMerchant", order.primary_key_value, order.property_values["merchant_id"]
        )
        ontology.create_link(
            "OrderHasRider", order.primary_key_value, order.property_values["rider_id"]
        )


def demonstrate_queries(ontology: Ontology):
    print("\n== Completed Orders from DuckDB ==")
    completed_orders = ontology.build_object_set("Order", filters={"status": "COMPLETED"})
    for obj in completed_orders.all():
        print(
            f"- {obj.primary_key_value} | merchant={obj.get('merchant_id')} "
            f"| rider={obj.get('rider_id')} | t_gap={obj.get('t_gap_min')} min"
        )

    avg_expectation = completed_orders.aggregate("user_expected_t_min", "avg")
    print(f"Average user expectation: {avg_expectation:.1f} minutes")

    print("\n== Pivoting to Merchants ==")
    shanghai_orders = ontology.build_object_set(
        "Order", filters={"merchant_id": "merchant_shanghai"}
    )
    merchant_links = shanghai_orders.search_around("OrderHasMerchant")
    for merchant in merchant_links.all():
        print(f"- Merchant node: {merchant.get('name')} ({merchant.primary_key_value})")

    print("\n== Lazy filtering stays in DuckDB ==")
    dumpling_orders = ontology.build_object_set("Order", filters={"items": "dumplings"})
    print(f"Orders with dumplings: {len(dumpling_orders.all())}")


def main():
    ontology = Ontology()

    conn = duckdb.connect(database=":memory:")
    _create_duckdb_tables(conn)
    duckdb_source = DuckDBDataSource(
        adapter_id="duckdb_demo",
        connection=conn,
        table_configs=_duckdb_configs(),
        read_only=False,
    )
    ontology.register_datasource(duckdb_source)

    setup_ontology(ontology)
    bind_order_demo_types(ontology, duckdb_source.id)

    seed_sample_data(ontology)
    demonstrate_queries(ontology)

    total_orders = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    print(f"\nDuckDB table currently has {total_orders} rows")


if __name__ == "__main__":
    main()

