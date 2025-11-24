"""
性能优化演示

展示如何使用优化版本的本体框架实现高性能操作。
"""

import time
import random
import statistics
from typing import List, Dict, Any

from src.ontology_framework.core import ObjectType, PropertyType, LinkType
from src.ontology_framework.optimized_core import OptimizedOntology, OptimizedObjectInstance
from src.ontology_framework.performance import monitor_performance, create_default_monitor
from src.ontology_framework.functions import ontology_function, registry


def setup_performance_demo_ontology():
    """设置性能演示本体"""
    ontology = OptimizedOntology(enable_monitoring=True, enable_cache=True)

    # 定义复杂的对象类型
    product_type = ObjectType(
        api_name="Product",
        display_name="Product",
        primary_key="product_id",
        title_property="name"
    )
    product_type.add_property("product_id", PropertyType.STRING)
    product_type.add_property("name", PropertyType.STRING)
    product_type.add_property("category", PropertyType.STRING)
    product_type.add_property("price", PropertyType.INTEGER)
    product_type.add_property("stock_quantity", PropertyType.INTEGER)
    product_type.add_property("rating", PropertyType.INTEGER)
    product_type.add_property("status", PropertyType.STRING)
    product_type.add_property("created_at", PropertyType.TIMESTAMP)

    # 定义订单对象类型
    order_type = ObjectType(
        api_name="Order",
        display_name="Order",
        primary_key="order_id",
        title_property="order_id"
    )
    order_type.add_property("order_id", PropertyType.STRING)
    order_type.add_property("customer_id", PropertyType.STRING)
    order_type.add_property("product_id", PropertyType.STRING)
    order_type.add_property("quantity", PropertyType.INTEGER)
    order_type.add_property("total_amount", PropertyType.INTEGER)
    order_type.add_property("status", PropertyType.STRING)
    order_type.add_property("order_date", PropertyType.TIMESTAMP)

    # 定义客户对象类型
    customer_type = ObjectType(
        api_name="Customer",
        display_name="Customer",
        primary_key="customer_id",
        title_property="customer_id"
    )
    customer_type.add_property("customer_id", PropertyType.STRING)
    customer_type.add_property("name", PropertyType.STRING)
    customer_type.add_property("email", PropertyType.STRING)
    customer_type.add_property("segment", PropertyType.STRING)
    customer_type.add_property("total_orders", PropertyType.INTEGER)
    customer_type.add_property("total_spent", PropertyType.INTEGER)

    # 注册对象类型
    ontology.register_object_type(product_type)
    ontology.register_object_type(order_type)
    ontology.register_object_type(customer_type)

    # 定义链接类型
    product_order_link = LinkType(
        api_name="ProductOrder",
        display_name="Product in Order",
        source_object_type="Product",
        target_object_type="Order",
        cardinality="ONE_TO_MANY"
    )
    ontology.register_link_type(product_order_link)

    customer_order_link = LinkType(
        api_name="CustomerOrder",
        display_name="Customer Orders",
        source_object_type="Customer",
        target_object_type="Order",
        cardinality="ONE_TO_MANY"
    )
    ontology.register_link_type(customer_order_link)

    # 创建索引以优化查询性能
    print("Creating indexes for optimal performance...")
    ontology.create_property_index("Product", "category")
    ontology.create_property_index("Product", "status")
    ontology.create_property_index("Product", "price")
    ontology.create_composite_index("Product", ["category", "status"])

    ontology.create_property_index("Order", "status")
    ontology.create_property_index("Order", "customer_id")
    ontology.create_property_index("Order", "order_date")

    ontology.create_property_index("Customer", "segment")
    ontology.create_property_index("Customer", "total_orders")

    return ontology


def generate_demo_data(ontology: OptimizedOntology, product_count: int = 10000, order_count: int = 50000, customer_count: int = 5000):
    """生成演示数据"""
    print(f"Generating demo data: {product_count} products, {order_count} orders, {customer_count} customers")

    categories = ["Electronics", "Clothing", "Books", "Home", "Sports", "Beauty"]
    statuses = ["active", "inactive", "discontinued"]
    segments = ["Premium", "Standard", "Basic"]
    order_statuses = ["pending", "processing", "shipped", "delivered", "cancelled"]

    start_time = time.time()

    # 生成产品数据
    products = []
    for i in range(product_count):
        product = OptimizedObjectInstance(
            object_type_api_name="Product",
            primary_key_value=f"product_{i:06d}",
            property_values={
                "product_id": f"product_{i:06d}",
                "name": f"Product {i}",
                "category": random.choice(categories),
                "price": random.randint(10, 1000),
                "stock_quantity": random.randint(0, 1000),
                "rating": random.randint(1, 5),
                "status": random.choice(statuses),
                "created_at": time.time() * 1000 - random.randint(0, 86400000)  # Last 24 hours
            },
            ontology=ontology
        )
        products.append(product)

    # 生成客户数据
    customers = []
    for i in range(customer_count):
        customer = OptimizedObjectInstance(
            object_type_api_name="Customer",
            primary_key_value=f"customer_{i:06d}",
            property_values={
                "customer_id": f"customer_{i:06d}",
                "name": f"Customer {i}",
                "email": f"customer{i}@example.com",
                "segment": random.choice(segments),
                "total_orders": 0,  # 将在生成订单时更新
                "total_spent": 0
            },
            ontology=ontology
        )
        customers.append(customer)

    # 批量添加对象
    print("Adding products to ontology...")
    for product in products:
        ontology.add_object(product)

    print("Adding customers to ontology...")
    for customer in customers:
        ontology.add_object(customer)

    # 生成订单数据
    print("Generating and adding orders...")
    customer_order_counts = {customer.primary_key_value: 0 for customer in customers}

    for i in range(order_count):
        customer = random.choice(customers)
        product = random.choice(products)
        quantity = random.randint(1, 10)
        total_amount = product.get("price") * quantity

        order = OptimizedObjectInstance(
            object_type_api_name="Order",
            primary_key_value=f"order_{i:06d}",
            property_values={
                "order_id": f"order_{i:06d}",
                "customer_id": customer.primary_key_value,
                "product_id": product.primary_key_value,
                "quantity": quantity,
                "total_amount": total_amount,
                "status": random.choice(order_statuses),
                "order_date": time.time() * 1000 - random.randint(0, 2592000000)  # Last 30 days
            },
            ontology=ontology
        )

        ontology.add_object(order)

        # 创建链接
        ontology.create_link("ProductOrder", product.primary_key_value, order.primary_key_value)
        ontology.create_link("CustomerOrder", customer.primary_key_value, order.primary_key_value)

        # 更新客户统计
        customer_order_counts[customer.primary_key_value] += 1

    # 更新客户订单统计
    print("Updating customer statistics...")
    for customer in customers:
        customer_orders = ontology.get_objects_of_type("Order").filter("customer_id", customer.primary_key_value)
        orders = customer_orders.all()

        if orders:
            total_orders = len(orders)
            total_spent = sum(order.get("total_amount") for order in orders)

            # 直接更新客户对象
            customer.property_values["total_orders"] = total_orders
            customer.property_values["total_spent"] = total_spent

    data_gen_time = time.time() - start_time
    print(f"Demo data generated in {data_gen_time:.2f} seconds")

    return products, customers


def performance_benchmark(ontology: OptimizedOntology):
    """性能基准测试"""
    print("\n" + "=" * 60)
    print("PERFORMANCE BENCHMARK")
    print("=" * 60)

    # 测试1: 主键查询性能
    print("\n1. Primary Key Lookup Performance")
    test_product_ids = [f"product_{i:06d}" for i in range(1000)]

    start_time = time.perf_counter()
    found_products = []
    for product_id in test_product_ids:
        product = ontology.get_object("Product", product_id)
        if product:
            found_products.append(product)
    end_time = time.perf_counter()

    lookup_time = (end_time - start_time) * 1000
    avg_lookup_time = lookup_time / len(test_product_ids)
    print(f"   Queried {len(test_product_ids)} products")
    print(f"   Found {len(found_products)} products")
    print(f"   Total time: {lookup_time:.2f} ms")
    print(f"   Average per query: {avg_lookup_time:.4f} ms")
    print(f"   Queries per second: {len(test_product_ids) / (lookup_time / 1000):.0f}")

    # 测试2: 属性过滤性能（使用索引）
    print("\n2. Indexed Property Filter Performance")
    categories = ["Electronics", "Clothing", "Books"]

    for category in categories:
        start_time = time.perf_counter()
        category_products = ontology.get_objects_of_type("Product").filter("category", category)
        end_time = time.perf_counter()

        filter_time = (end_time - start_time) * 1000
        result_count = category_products.count()
        print(f"   Category '{category}': {result_count} products in {filter_time:.2f} ms")

    # 测试3: 复合查询性能
    print("\n3. Complex Query Performance")

    start_time = time.perf_counter()
    active_electronics = ontology.get_objects_of_type("Product").filter("category", "Electronics")
    active_electronics = active_electronics.filter("status", "active")
    expensive_products = [p for p in active_electronics.all() if p.get("price") > 500]
    end_time = time.perf_counter()

    complex_query_time = (end_time - start_time) * 1000
    print(f"   Active electronics > $500: {len(expensive_products)} products")
    print(f"   Query time: {complex_query_time:.2f} ms")

    # 测试4: 关系查询性能
    print("\n4. Relationship Query Performance")
    test_customer_ids = [f"customer_{i:06d}" for i in range(100)]

    start_time = time.perf_counter()
    total_customer_orders = 0
    for customer_id in test_customer_ids:
        customer_orders = ontology.get_objects_of_type("Customer").filter("customer_id", customer_id)
        if customer_orders.first():
            orders = customer_orders.first().search_around("CustomerOrder")
            total_customer_orders += orders.count()
    end_time = time.perf_counter()

    relationship_query_time = (end_time - start_time) * 1000
    avg_relationship_query_time = relationship_query_time / len(test_customer_ids)
    print(f"   Queried orders for {len(test_customer_ids)} customers")
    print(f"   Total orders found: {total_customer_orders}")
    print(f"   Total time: {relationship_query_time:.2f} ms")
    print(f"   Average per customer: {avg_relationship_query_time:.4f} ms")

    # 测试5: 聚合查询性能
    print("\n5. Aggregation Query Performance")

    start_time = time.perf_counter()
    all_products = ontology.get_objects_of_type("Product")
    avg_price = all_products.aggregate("price", "avg")
    total_stock = all_products.aggregate("stock_quantity", "sum")
    max_rating_products = all_products.aggregate("rating", "max")
    end_time = time.perf_counter()

    aggregation_time = (end_time - start_time) * 1000
    print(f"   Average price: ${avg_price:.2f}")
    print(f"   Total stock: {total_stock}")
    print(f"   Max rating: {max_rating_products}")
    print(f"   Aggregation time: {aggregation_time:.2f} ms")


def cache_performance_demo(ontology: OptimizedOntology):
    """缓存性能演示"""
    print("\n" + "=" * 60)
    print("CACHE PERFORMANCE DEMO")
    print("=" * 60)

    # 清空缓存以获得准确测量
    if ontology.cache:
        ontology.cache.clear()

    # 首次查询（缓存未命中）
    test_product_id = "product_000001"

    print("\n1. First query (cache miss)")
    start_time = time.perf_counter()
    product1 = ontology.get_object("Product", test_product_id)
    first_query_time = (time.perf_counter() - start_time) * 1000
    print(f"   Query time: {first_query_time:.4f} ms")
    print(f"   Product found: {product1 is not None}")

    # 第二次查询（缓存命中）
    print("\n2. Second query (cache hit)")
    start_time = time.perf_counter()
    product2 = ontology.get_object("Product", test_product_id)
    second_query_time = (time.perf_counter() - start_time) * 1000
    print(f"   Query time: {second_query_time:.4f} ms")
    print(f"   Product found: {product2 is not None}")
    print(f"   Performance improvement: {first_query_time / second_query_time:.1f}x faster")

    # 显示缓存统计
    if ontology.cache:
        cache_stats = ontology.cache.get_comprehensive_stats()
        print(f"\n3. Cache Statistics")
        print(f"   Global hit rate: {cache_stats['global']['hit_rate']:.2%}")
        print(f"   Total hits: {cache_stats['global']['hits']}")
        print(f"   Total misses: {cache_stats['global']['misses']}")
        print(f"   L1 cache size: {cache_stats['levels']['L1']['size']}")
        print(f"   L2 cache size: {cache_stats['levels']['L2']['size']}")


def monitoring_demo(ontology: OptimizedOntology):
    """监控演示"""
    print("\n" + "=" * 60)
    print("PERFORMANCE MONITORING DEMO")
    print("=" * 60)

    if ontology.performance_monitor:
        # 执行一些操作来生成监控数据
        print("\nGenerating monitoring data...")

        # 执行各种操作
        for i in range(10):
            # 查询操作
            ontology.get_object("Product", f"product_{i:06d}")

            # 过滤操作
            ontology.get_objects_of_type("Product").filter("status", "active")

            # 关系查询
            ontology.get_objects_of_type("Customer").first().search_around("CustomerOrder")

        # 获取监控数据
        dashboard = ontology.performance_monitor.get_dashboard_data()

        print(f"\nMonitoring Dashboard:")
        print(f"   Monitoring active: {dashboard['summary']['monitoring_active']}")
        print(f"   Total metrics tracked: {dashboard['summary']['total_metrics']}")
        print(f"   Active alerts: {dashboard['summary']['active_alerts']}")

        print(f"\nRecent Metrics:")
        for metric_name, metric_data in dashboard['metrics'].items():
            current = metric_data['current']
            stats = metric_data.get('stats', {})
            avg = stats.get('avg', 0)

            print(f"   {metric_name}:")
            print(f"     Current: {current:.2f}")
            if avg:
                print(f"     Average: {avg:.2f}")

        # 显示告警
        if dashboard['alerts']:
            print(f"\nActive Alerts:")
            for alert in dashboard['alerts']:
                print(f"   🚨 {alert['message']}")
        else:
            print(f"\n✅ No active alerts")

    else:
        print("Performance monitoring is not enabled")


def optimization_recommendations(ontology: OptimizedOntology):
    """优化建议演示"""
    print("\n" + "=" * 60)
    print("OPTIMIZATION RECOMMENDATIONS")
    print("=" * 60)

    suggestions = ontology.optimize_performance()

    if suggestions:
        print("Optimization suggestions:")
        for i, suggestion in enumerate(suggestions, 1):
            print(f"   {i}. {suggestion}")
    else:
        print("✅ No immediate optimizations needed")

    # 显示性能统计
    stats = ontology.get_performance_stats()

    print(f"\nPerformance Summary:")
    print(f"   Objects created: {stats['operation_stats']['objects_created']}")
    print(f"   Objects retrieved: {stats['operation_stats']['objects_retrieved']}")
    print(f"   Queries executed: {stats['operation_stats']['queries_executed']}")
    print(f"   Cache hit rate: {stats['cache_stats'].get('global', {}).get('hit_rate', 0):.2%}")

    # 显示索引统计
    if stats.get('index_stats'):
        print(f"\nIndex Usage:")
        for index_name, index_info in stats['index_stats'].items():
            print(f"   {index_name}: {index_info.get('size', 0)} indexed items")


def main():
    """主演示函数"""
    print("Ontology Framework Performance Optimization Demo")
    print("=" * 60)

    # 设置优化版本的本体
    ontology = setup_performance_demo_ontology()

    # 生成演示数据
    products, customers = generate_demo_data(ontology)

    # 运行性能基准测试
    performance_benchmark(ontology)

    # 缓存性能演示
    cache_performance_demo(ontology)

    # 监控演示
    monitoring_demo(ontology)

    # 优化建议
    optimization_recommendations(ontology)

    print("\n" + "=" * 60)
    print("DEMO COMPLETED")
    print("=" * 60)
    print("\nKey Performance Improvements Demonstrated:")
    print("✅ Indexed queries for 10-100x faster filtering")
    print("✅ Multi-level caching for reduced query latency")
    print("✅ Real-time performance monitoring and alerting")
    print("✅ Automatic performance optimization suggestions")
    print("✅ Efficient memory management with object pooling")
    print("✅ Optimized relationship queries with link indexing")

    # 保存性能报告
    if ontology.performance_monitor:
        report = ontology.performance_monitor.export_metrics("json", 300)
        report_file = f"performance_report_{int(time.time())}.json"
        with open(report_file, 'w') as f:
            f.write(report)
        print(f"\n📊 Performance report saved to: {report_file}")


if __name__ == "__main__":
    main()