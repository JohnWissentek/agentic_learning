"""Command-line interface for Boiler FBG Multi-Agent Workflow.

Usage:
    boiler-fbg run [--mode simulation|live] [--output-dir DIR]
    boiler-fbg test-temp-app [--samples N]
    boiler-fbg export-evidence [--output FILE]
    boiler-fbg --help
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich.panel import Panel


console = Console()


def run_workflow(args: argparse.Namespace) -> int:
    """Run the multi-agent R&D workflow."""
    from boiler_fbg_workflow.config import CostLedger, RuntimeDeps, WorkflowSettings
    from boiler_fbg_workflow.graph import build_boiler_fbg_graph
    
    console.print(Panel.fit(
        "[bold blue]燃煤锅炉水冷壁光纤测温产品研发多智能体工作流[/bold blue]\n"
        "基于《Agentic Design Patterns》(Antonio Gulli) 设计模式",
        title="Boiler FBG Multi-Agent Workflow",
    ))
    
    # Load settings
    settings = WorkflowSettings(
        mode=args.mode,
        output_dir=args.output_dir,
        hitl_enabled=not args.no_hitl,
    )
    
    console.print(f"\n运行模式: [bold]{settings.mode}[/bold]")
    console.print(f"输出目录: {settings.output_dir}")
    console.print(f"HITL门禁: {'启用' if settings.hitl_enabled else '禁用'}")
    
    if settings.mode == "simulation":
        console.print("\n[yellow]⚠️ 模拟模式：所有输出为预定义模板，标记为[SIMULATION][/yellow]")
    
    # Create output directory
    output_dir = Path(settings.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize dependencies
    ledger = CostLedger()
    deps = RuntimeDeps(
        settings=settings,
        ledger=ledger,
    )
    
    # Build and run graph
    graph = build_boiler_fbg_graph(deps)
    
    run_id = f"run-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
    console.print(f"\n运行ID: [bold]{run_id}[/bold]")
    
    initial_state = {
        "run_id": run_id,
        "mode": settings.mode,
        "hitl_enabled": settings.hitl_enabled,
        "output_dir": str(output_dir),
    }
    
    console.print("\n[bold green]开始执行工作流...[/bold green]\n")
    
    # Execute workflow
    try:
        config = {"configurable": {"thread_id": run_id}}
        
        for event in graph.stream(initial_state, config=config):
            for node_name, node_output in event.items():
                if node_output:
                    console.print(f"✓ 完成节点: [cyan]{node_name}[/cyan]")
                    
                    # Show stage completion
                    if "current_stage" in node_output:
                        console.print(f"  阶段: {node_output['current_stage']}")
                    
                    # Show QA results
                    if "qa_reviews" in node_output:
                        for review in node_output["qa_reviews"]:
                            status = review.get("gate_status", "unknown")
                            console.print(f"  QA审查: {status}")
                    
                    # Show HITL decisions
                    if "hitl_decisions" in node_output:
                        for decision in node_output["hitl_decisions"]:
                            d = decision.get("decision", "unknown")
                            console.print(f"  HITL决策: {d}")
        
        console.print("\n[bold green]✓ 工作流执行完成[/bold green]")
        
        # Show output files
        if output_dir.exists():
            files = list(output_dir.glob("*"))
            if files:
                console.print("\n生成的文件:")
                for f in files:
                    console.print(f"  - {f.name}")
        
        # Show cost summary
        cost_summary = ledger.get_summary()
        if cost_summary["total_api_calls"] > 0:
            console.print(f"\nAPI调用统计:")
            console.print(f"  总调用次数: {cost_summary['total_api_calls']}")
            console.print(f"  总Token数: {cost_summary['total_input_tokens'] + cost_summary['total_output_tokens']}")
            console.print(f"  预估成本: ${cost_summary['total_cost_usd']:.4f}")
        
        return 0
        
    except Exception as e:
        console.print(f"\n[bold red]✗ 工作流执行失败: {e}[/bold red]")
        import traceback
        traceback.print_exc()
        return 1


def test_temperature_app(args: argparse.Namespace) -> int:
    """Test the temperature monitoring application prototype."""
    from boiler_fbg_workflow.temperature_app import (
        SimulatedDemodulator,
        SyntheticDataGenerator,
        RiskDetector,
        QualityAnalyzer,
        AuditLogger,
    )
    from boiler_fbg_workflow.temperature_app.data_generator import DataGeneratorConfig
    
    console.print(Panel.fit(
        "[bold blue]测温数据应用原型测试[/bold blue]\n"
        "⚠️ 所有数据标记为[SYNTHETIC]，不声称电厂实测",
        title="Temperature App Test",
    ))
    
    # Initialize components
    config = DataGeneratorConfig(
        channel_count=args.channels,
        inject_over_temp_prob=0.02,  # Higher probability for testing
        inject_fast_rise_prob=0.01,
    )
    generator = SyntheticDataGenerator(config)
    detector = RiskDetector()
    quality = QualityAnalyzer()
    
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    logger = AuditLogger(output_dir / "audit_log.db")
    
    console.print(f"\n通道数: {args.channels}")
    console.print(f"采样数: {args.samples}")
    console.print(f"输出目录: {output_dir}")
    
    # Generate and analyze data
    console.print("\n[bold]开始生成合成数据并分析...[/bold]")
    
    all_alerts = []
    total_readings = 0
    
    for i, readings in enumerate(generator.generate_time_series(args.samples * 0.1)):
        # Apply quality analysis
        flagged_readings, quality_alerts = quality.analyze(readings)
        all_alerts.extend(quality_alerts)
        
        # Run risk detection
        risk_alerts = detector.analyze(flagged_readings)
        all_alerts.extend(risk_alerts)
        
        # Log data
        logger.log_readings(flagged_readings)
        logger.log_alerts(quality_alerts + risk_alerts)
        
        total_readings += len(readings)
        
        if (i + 1) % 10 == 0:
            console.print(f"  已处理 {i + 1} 批次, {total_readings} 读数, {len(all_alerts)} 告警")
    
    # Show results
    console.print("\n[bold green]测试完成[/bold green]")
    
    # Alert summary table
    alert_table = Table(title="告警汇总")
    alert_table.add_column("类型", style="cyan")
    alert_table.add_column("严重程度", style="yellow")
    alert_table.add_column("数量")
    
    alert_counts = {}
    for alert in all_alerts:
        key = (alert.alert_type, alert.severity)
        alert_counts[key] = alert_counts.get(key, 0) + 1
    
    for (atype, severity), count in sorted(alert_counts.items()):
        alert_table.add_row(atype, severity, str(count))
    
    console.print(alert_table)
    
    # Quality summary
    quality_summary = quality.get_quality_summary(readings)
    console.print(f"\n数据质量: {quality_summary['good_percentage']:.1f}% 良好")
    
    # Detector statistics
    detector_stats = detector.get_statistics()
    console.print(f"追踪通道数: {detector_stats['channels_tracked']}")
    console.print(f"生成告警数: {detector_stats['alerts_generated']}")
    
    # Audit log statistics
    audit_stats = logger.get_statistics()
    console.print(f"\n审计日志: {audit_stats['total_readings_logged']} 读数, {audit_stats['total_alerts']} 告警")
    
    # Export audit trail
    audit_path = output_dir / "audit_trail.json"
    logger.export_audit_trail(audit_path)
    console.print(f"\n审计日志已导出: {audit_path}")
    
    return 0


def export_evidence(args: argparse.Namespace) -> int:
    """Export evidence registry."""
    from boiler_fbg_workflow.tools.evidence_vault import EvidenceVault
    
    vault = EvidenceVault(args.db_path)
    vault.export_index(args.output)
    
    stats = vault.get_statistics()
    console.print(f"已导出 {stats['total']} 条证据记录到 {args.output}")
    
    return 0


def main() -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="燃煤锅炉水冷壁光纤测温产品研发多智能体工作流",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    subparsers = parser.add_subparsers(dest="command", help="可用命令")
    
    # Run workflow
    run_parser = subparsers.add_parser("run", help="运行多智能体工作流")
    run_parser.add_argument(
        "--mode",
        choices=["simulation", "offline-replay", "live"],
        default="simulation",
        help="运行模式 (默认: simulation)",
    )
    run_parser.add_argument(
        "--output-dir",
        default="./outputs",
        help="输出目录 (默认: ./outputs)",
    )
    run_parser.add_argument(
        "--no-hitl",
        action="store_true",
        help="禁用HITL门禁",
    )
    
    # Test temperature app
    temp_parser = subparsers.add_parser("test-temp-app", help="测试测温数据应用原型")
    temp_parser.add_argument(
        "--samples",
        type=int,
        default=100,
        help="生成的采样批次数 (默认: 100)",
    )
    temp_parser.add_argument(
        "--channels",
        type=int,
        default=64,
        help="传感器通道数 (默认: 64)",
    )
    temp_parser.add_argument(
        "--output-dir",
        default="./outputs/temp_app_test",
        help="输出目录",
    )
    
    # Export evidence
    export_parser = subparsers.add_parser("export-evidence", help="导出证据注册表")
    export_parser.add_argument(
        "--db-path",
        default="./evidence_registry/evidence.db",
        help="证据数据库路径",
    )
    export_parser.add_argument(
        "--output",
        default="./outputs/evidence_index.json",
        help="输出文件路径",
    )
    
    args = parser.parse_args()
    
    if args.command == "run":
        return run_workflow(args)
    elif args.command == "test-temp-app":
        return test_temperature_app(args)
    elif args.command == "export-evidence":
        return export_evidence(args)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
