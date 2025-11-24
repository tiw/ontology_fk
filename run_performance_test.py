#!/usr/bin/env python3
"""
运行性能测试的便捷脚本
"""

import sys
import os
import time

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    """主函数"""
    print("🚀 Starting Ontology Framework Performance Test")
    print("=" * 60)

    try:
        # 导入并运行性能演示
        from examples.performance_demo import main as demo_main
        demo_main()

        print("\n✅ Performance test completed successfully!")

    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("\nMake sure all dependencies are installed:")
        print("pip install psutil redis")

    except Exception as e:
        print(f"❌ Error running performance test: {e}")
        import traceback
        traceback.print_exc()

    print("\n📊 Check the generated reports for detailed performance metrics.")


if __name__ == "__main__":
    main()