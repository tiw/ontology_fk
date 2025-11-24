#!/usr/bin/env python3
"""
质量监控脚本

定期生成质量报告，监控项目质量指标变化趋势。
包含代码质量、测试覆盖率、性能指标等多个维度的监控。
"""

import json
import subprocess
import sqlite3
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Any
import sys
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class QualityMetricsCollector:
    """质量指标收集器"""

    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root).resolve()
        self.db_path = self.project_root / "quality_metrics.db"
        self.init_database()

    def init_database(self) -> None:
        """初始化质量指标数据库"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS quality_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                metric_category TEXT NOT NULL,
                metric_name TEXT NOT NULL,
                metric_value REAL NOT NULL,
                metric_metadata TEXT,
                git_commit TEXT,
                git_branch TEXT
            )
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_timestamp
            ON quality_metrics(timestamp)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_category_name
            ON quality_metrics(metric_category, metric_name)
        ''')

        conn.commit()
        conn.close()

    def run_command(self, cmd: List[str], cwd: str = None) -> Tuple[int, str, str]:
        """执行命令并返回结果"""
        try:
            work_dir = cwd or str(self.project_root)
            result = subprocess.run(
                cmd,
                cwd=work_dir,
                capture_output=True,
                text=True,
                timeout=300  # 5分钟超时
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            logger.error(f"命令执行超时: {' '.join(cmd)}")
            return -1, "", "Command timeout"
        except Exception as e:
            logger.error(f"命令执行失败: {e}")
            return -1, "", str(e)

    def get_git_info(self) -> Tuple[str, str]:
        """获取当前Git信息"""
        try:
            # 获取当前提交哈希
            returncode, commit_hash, _ = self.run_command([
                "git", "rev-parse", "HEAD"
            ])
            if returncode != 0:
                commit_hash = "unknown"

            # 获取当前分支名
            returncode, branch_name, _ = self.run_command([
                "git", "rev-parse", "--abbrev-ref", "HEAD"
            ])
            if returncode != 0:
                branch_name = "unknown"

            return commit_hash.strip(), branch_name.strip()
        except Exception:
            return "unknown", "unknown"

    def record_metric(
        self,
        category: str,
        name: str,
        value: float,
        metadata: Dict[str, Any] = None,
        git_commit: str = None,
        git_branch: str = None
    ) -> None:
        """记录质量指标到数据库"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        if git_commit is None or git_branch is None:
            git_commit, git_branch = self.get_git_info()

        cursor.execute('''
            INSERT INTO quality_metrics
            (timestamp, metric_category, metric_name, metric_value,
             metric_metadata, git_commit, git_branch)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            datetime.now().isoformat(),
            category,
            name,
            float(value),
            json.dumps(metadata or {}),
            git_commit,
            git_branch
        ))

        conn.commit()
        conn.close()
        logger.info(f"记录指标: {category}/{name} = {value}")

    def collect_test_coverage(self) -> None:
        """收集测试覆盖率数据"""
        logger.info("收集测试覆盖率数据...")

        returncode, stdout, stderr = self.run_command([
            "uv", "run", "pytest",
            "--cov=src/ontology_framework",
            "--cov-report=json",
            "--cov-report=term"
        ])

        if returncode == 0:
            try:
                coverage_data = json.loads(stdout)
                totals = coverage_data.get("totals", {})

                # 记录总覆盖率
                self.record_metric(
                    "test_coverage",
                    "total_coverage",
                    totals.get("percent_covered", 0),
                    {"covered_lines": totals.get("covered_lines", 0),
                     "num_statements": totals.get("num_statements", 0)}
                )

                # 记录各模块覆盖率
                files = coverage_data.get("files", {})
                for file_path, file_data in files.items():
                    module_name = Path(file_path).stem
                    self.record_metric(
                        "test_coverage",
                        f"module_{module_name}",
                        file_data.get("summary", {}).get("percent_covered", 0)
                    )

            except json.JSONDecodeError as e:
                logger.error(f"解析覆盖率数据失败: {e}")
        else:
            logger.error(f"运行测试覆盖率失败: {stderr}")

    def collect_code_complexity(self) -> None:
        """收集代码复杂度数据"""
        logger.info("收集代码复杂度数据...")

        # 尝试使用radon收集复杂度指标
        try:
            returncode, stdout, stderr = self.run_command([
                "radon", "cc", "src", "--json"
            ])

            if returncode == 0:
                complexity_data = json.loads(stdout)

                total_complexity = 0
                max_complexity = 0
                file_count = len(complexity_data)

                for file_path, file_data in complexity_data.items():
                    for item in file_data:
                        complexity = item.get("complexity", 0)
                        total_complexity += complexity
                        max_complexity = max(max_complexity, complexity)

                avg_complexity = total_complexity / max(file_count, 1)

                self.record_metric(
                    "code_complexity",
                    "average_complexity",
                    avg_complexity,
                    {"max_complexity": max_complexity,
                     "total_files": file_count}
                )

                self.record_metric(
                    "code_complexity",
                    "max_complexity",
                    max_complexity
                )

        except (subprocess.CalledProcessError, json.JSONDecodeError, FileNotFoundError):
            logger.warning("radon不可用，跳过复杂度分析")

    def collect_security_metrics(self) -> None:
        """收集安全相关指标"""
        logger.info("收集安全指标...")

        # 使用bandit进行安全扫描
        returncode, stdout, stderr = self.run_command([
            "bandit", "-r", "src", "-f", "json"
        ])

        if returncode in [0, 1]:  # bandit返回1表示发现问题但扫描成功
            try:
                security_data = json.loads(stdout)
                results = security_data.get("results", [])

                high_issues = len([r for r in results if r.get("issue_severity") == "HIGH"])
                medium_issues = len([r for r in results if r.get("issue_severity") == "MEDIUM"])
                low_issues = len([r for r in results if r.get("issue_severity") == "LOW"])

                self.record_metric("security", "high_risk_issues", high_issues)
                self.record_metric("security", "medium_risk_issues", medium_issues)
                self.record_metric("security", "low_risk_issues", low_issues)
                self.record_metric("security", "total_issues", len(results))

            except json.JSONDecodeError:
                logger.error("解析安全扫描结果失败")

    def collect_performance_metrics(self) -> None:
        """收集性能指标"""
        logger.info("收集性能指标...")

        # 运行性能基准测试
        returncode, stdout, stderr = self.run_command([
            "uv", "run", "pytest",
            "--benchmark-only",
            "--benchmark-json=/tmp/benchmark.json"
        ])

        if returncode == 0:
            try:
                with open("/tmp/benchmark.json", "r") as f:
                    benchmark_data = json.load(f)

                benchmarks = benchmark_data.get("benchmarks", [])

                for benchmark in benchmarks:
                    name = benchmark.get("name", "unknown")
                    min_time = benchmark.get("stats", {}).get("min", 0)
                    mean_time = benchmark.get("stats", {}).get("mean", 0)

                    self.record_metric(
                        "performance",
                        f"benchmark_{name}_min",
                        min_time,
                        {"benchmark_name": name}
                    )
                    self.record_metric(
                        "performance",
                        f"benchmark_{name}_mean",
                        mean_time,
                        {"benchmark_name": name}
                    )

            except (json.JSONDecodeError, FileNotFoundError):
                logger.error("解析性能基准测试结果失败")

    def collect_code_quality_metrics(self) -> None:
        """收集代码质量指标"""
        logger.info("收集代码质量指标...")

        # 统计代码行数
        try:
            returncode, stdout, stderr = self.run_command([
                "find", "src", "-name", "*.py", "-exec", "wc", "-l", "{}", "+"
            ])

            if returncode == 0:
                lines = stdout.strip().split('\n')
                total_lines = sum(int(line.split()[0]) for line in lines if line.strip())

                self.record_metric(
                    "code_volume",
                    "total_lines",
                    total_lines
                )

        except Exception:
            logger.warning("统计代码行数失败")

        # 统计文件数量
        try:
            returncode, stdout, stderr = self.run_command([
                "find", "src", "-name", "*.py"
            ])

            if returncode == 0:
                file_count = len([line for line in stdout.strip().split('\n') if line.strip()])
                self.record_metric(
                    "code_volume",
                    "python_files",
                    file_count
                )

        except Exception:
            logger.warning("统计文件数量失败")

    def generate_trend_report(
        self,
        days: int = 30,
        output_file: str = "quality_trend_report.md"
    ) -> None:
        """生成质量趋势报告"""
        logger.info(f"生成质量趋势报告 ({days} 天)...")

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        since_date = (datetime.now() - timedelta(days=days)).isoformat()

        # 获取关键指标的趋势数据
        key_metrics = [
            ("test_coverage", "total_coverage"),
            ("code_complexity", "average_complexity"),
            ("security", "high_risk_issues"),
            ("security", "medium_risk_issues")
        ]

        report_lines = [
            "# 质量趋势报告",
            "",
            f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"统计周期: {days} 天",
            "",
            "## 关键指标趋势",
            ""
        ]

        for category, name in key_metrics:
            cursor.execute('''
                SELECT timestamp, metric_value
                FROM quality_metrics
                WHERE metric_category = ? AND metric_name = ? AND timestamp > ?
                ORDER BY timestamp
            ''', (category, name, since_date))

            data = cursor.fetchall()

            if data:
                report_lines.append(f"### {category}.{name}")
                latest_value = data[-1][1] if data else 0

                if data:
                    # 计算趋势
                    values = [row[1] for row in data]
                    if len(values) >= 2:
                        trend = ((values[-1] - values[0]) / values[0]) * 100 if values[0] != 0 else 0
                        trend_symbol = "📈" if trend > 0 else "📉" if trend < 0 else "➡️"
                        report_lines.append(f"- 当前值: {latest_value:.2f}")
                        report_lines.append(f"- 趋势: {trend_symbol} {trend:+.1f}%")
                    else:
                        report_lines.append(f"- 当前值: {latest_value:.2f}")
                        report_lines.append("- 趋势: 数据不足")
                else:
                    report_lines.append("- 数据不足")

                report_lines.append("")

        # 添加最新质量检查摘要
        cursor.execute('''
            SELECT metric_category, metric_name, metric_value, timestamp
            FROM quality_metrics
            WHERE timestamp > datetime('now', '-1 day')
            ORDER BY timestamp DESC
            LIMIT 20
        ''')

        recent_metrics = cursor.fetchall()

        if recent_metrics:
            report_lines.extend([
                "## 最新质量指标",
                "",
                "| 类别 | 指标 | 值 | 时间 |",
                "|------|------|----|----|"
            ])

            for category, name, value, timestamp in recent_metrics:
                formatted_time = timestamp.split('T')[1][:5] if 'T' in timestamp else "N/A"
                report_lines.append(f"| {category} | {name} | {value:.2f} | {formatted_time} |")

        report_content = "\n".join(report_lines)

        # 写入报告文件
        report_path = self.project_root / output_file
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report_content)

        logger.info(f"质量趋势报告已生成: {report_path}")

        conn.close()

    def get_health_score(self) -> Dict[str, Any]:
        """计算项目质量健康评分"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # 获取最新的关键指标
        cursor.execute('''
            SELECT metric_category, metric_name, metric_value
            FROM quality_metrics
            WHERE (metric_category, metric_name) IN (
                ('test_coverage', 'total_coverage'),
                ('code_complexity', 'average_complexity'),
                ('security', 'high_risk_issues')
            )
            ORDER BY timestamp DESC
            LIMIT 20
        ''')

        latest_metrics = {}
        for category, name, value in cursor.fetchall():
            latest_metrics[f"{category}.{name}"] = value

        conn.close()

        # 计算健康评分
        scores = {}

        # 测试覆盖率评分 (90% = 满分)
        coverage = latest_metrics.get("test_coverage.total_coverage", 0)
        scores["coverage"] = min(coverage / 90, 1.0)

        # 代码复杂度评分 (5 = 满分)
        complexity = latest_metrics.get("code_complexity.average_complexity", 10)
        scores["complexity"] = max(0, 1 - (complexity - 5) / 10)

        # 安全性评分 (0问题 = 满分)
        security_issues = latest_metrics.get("security.high_risk_issues", 5)
        scores["security"] = max(0, 1 - security_issues / 10)

        # 计算加权总分
        weights = {
            "coverage": 0.4,
            "complexity": 0.3,
            "security": 0.3
        }

        total_score = sum(
            scores[category] * weights[category]
            for category in scores
        )

        return {
            "total_score": total_score,
            "category_scores": scores,
            "health_level": self._get_health_level(total_score),
            "latest_metrics": latest_metrics
        }

    def _get_health_level(self, score: float) -> str:
        """获取健康等级"""
        if score >= 0.9:
            return "优秀 (A)"
        elif score >= 0.8:
            return "良好 (B)"
        elif score >= 0.7:
            return "合格 (C)"
        elif score >= 0.6:
            return "需改进 (D)"
        else:
            return "不合格 (F)"

    def run_full_collection(self) -> None:
        """运行完整的质量指标收集"""
        logger.info("开始收集质量指标...")

        try:
            self.collect_test_coverage()
            self.collect_code_complexity()
            self.collect_security_metrics()
            self.collect_performance_metrics()
            self.collect_code_quality_metrics()

            logger.info("质量指标收集完成")

            # 生成健康评分
            health_score = self.get_health_score()
            logger.info(f"项目健康评分: {health_score['total_score']:.2f} ({health_score['health_level']})")

        except Exception as e:
            logger.error(f"质量指标收集失败: {e}")
            raise


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="质量监控脚本")
    parser.add_argument(
        "--project-root",
        default=".",
        help="项目根目录路径"
    )
    parser.add_argument(
        "--collect",
        action="store_true",
        help="收集质量指标"
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="生成质量趋势报告"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="报告统计天数"
    )
    parser.add_argument(
        "--output",
        default="quality_trend_report.md",
        help="报告输出文件名"
    )
    parser.add_argument(
        "--health",
        action="store_true",
        help="显示项目健康评分"
    )

    args = parser.parse_args()

    collector = QualityMetricsCollector(args.project_root)

    if args.collect:
        collector.run_full_collection()

    if args.report:
        collector.generate_trend_report(args.days, args.output)

    if args.health:
        health_score = collector.get_health_score()
        print(f"项目健康评分: {health_score['total_score']:.2f} ({health_score['health_level']})")
        print("\n各维度评分:")
        for category, score in health_score['category_scores'].items():
            print(f"  {category}: {score:.2f}")

    if not any([args.collect, args.report, args.health]):
        # 默认行为：收集指标并生成报告
        collector.run_full_collection()
        collector.generate_trend_report()


if __name__ == "__main__":
    main()