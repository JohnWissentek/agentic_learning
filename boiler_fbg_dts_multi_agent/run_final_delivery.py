#!/usr/bin/env python3
"""Final Delivery Runner - Complete 12-Role Team Workflow with v0.3 Data.

This script:
1. Verifies model availability and downloads if needed
2. Runs complete 12-role team workflow
3. Generates all required artifacts
4. Creates acceptance report

Artifacts generated:
- live_trace.json / live_trace.jsonl
- model_manifest.json
- pytest results
- acceptance report (Chinese)
"""

import sys
import os
import json
import subprocess
import shutil
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def verify_model():
    """Verify model is available."""
    print("=" * 60)
    print("步骤 1: 验证模型可用性")
    print("=" * 60)
    
    try:
        from transformers import AutoTokenizer, AutoModelForCausalLM
        from boiler_fbg_workflow.model_manifest import MODEL_MANIFEST
        
        model_id = MODEL_MANIFEST["model_id"]
        revision = MODEL_MANIFEST["model_revision"]
        
        print(f"  模型: {model_id}")
        print(f"  版本: {revision}")
        print(f"  许可: {MODEL_MANIFEST['model_license']}")
        print("")
        
        print("  正在加载tokenizer...")
        tokenizer = AutoTokenizer.from_pretrained(model_id, revision=revision)
        print(f"  ✓ Tokenizer加载成功 (vocab_size: {tokenizer.vocab_size})")
        
        return {
            "status": "available",
            "model_id": model_id,
            "revision": revision,
            "vocab_size": tokenizer.vocab_size,
            "license": MODEL_MANIFEST["model_license"],
        }
    except Exception as e:
        print(f"  ✗ 模型验证失败: {e}")
        return {"status": "error", "error": str(e)}


def run_pytest():
    """Run pytest and capture output."""
    print("")
    print("=" * 60)
    print("步骤 2: 运行测试套件")
    print("=" * 60)
    
    result = subprocess.run(
        ["python3", "-m", "pytest", "tests/", "-v", "--tb=short"],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent,
    )
    
    output = result.stdout + result.stderr
    
    # Parse results
    passed = output.count(" PASSED")
    failed = output.count(" FAILED")
    
    print(f"  通过: {passed}")
    print(f"  失败: {failed}")
    
    return {
        "exit_code": result.returncode,
        "passed": passed,
        "failed": failed,
        "output": output,
    }


def run_full_workflow():
    """Run full 12-role workflow."""
    print("")
    print("=" * 60)
    print("步骤 3: 运行12角色团队工作流")
    print("=" * 60)
    
    from boiler_fbg_workflow.llm_provider import LLMProviderFactory, ProviderType
    from boiler_fbg_workflow.full_team_agents import run_full_team_workflow
    from boiler_fbg_workflow.model_manifest import V03_BASELINE
    
    print(f"  v0.3基线版本: {V03_BASELINE['version']}")
    print(f"  v0.3 ZIP SHA256: {V03_BASELINE['zip_sha256'][:32]}...")
    print("")
    
    provider = LLMProviderFactory.create(ProviderType.LOCAL)
    
    start_time = datetime.now()
    results = run_full_team_workflow(
        provider=provider,
        output_dir="./outputs/final_delivery",
    )
    end_time = datetime.now()
    
    duration = (end_time - start_time).total_seconds()
    results["duration_seconds"] = duration
    
    print("")
    print(f"  运行时长: {duration:.1f}秒")
    print(f"  角色执行: {len(results['roles_executed'])}/12")
    print(f"  LLM调用: {results['quality_summary']['llm_calls'].get('call_count', 'N/A')}")
    print(f"  门禁状态: {results['final_gate_status']}")
    
    return results


def create_model_manifest(output_dir: Path, model_info: dict):
    """Create model manifest file."""
    from boiler_fbg_workflow.model_manifest import MODEL_MANIFEST
    
    manifest = {
        "created": datetime.now().isoformat(),
        "model": MODEL_MANIFEST,
        "verification": model_info,
    }
    
    manifest_path = output_dir / "model_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    
    return manifest_path


def create_acceptance_report(output_dir: Path, model_info: dict, pytest_results: dict, workflow_results: dict):
    """Create Chinese acceptance report."""
    from boiler_fbg_workflow.model_manifest import MODEL_MANIFEST, V03_BASELINE
    
    report_lines = [
        "# 锅炉FBG多智能体工作流最终验收报告",
        "",
        f"生成时间: {datetime.now().isoformat()}",
        "",
        "## 1. 模型信息",
        "",
        f"- 模型ID: `{MODEL_MANIFEST['model_id']}`",
        f"- 版本: `{MODEL_MANIFEST['model_revision']}`",
        f"- 许可: {MODEL_MANIFEST['model_license']}",
        f"- 参数量: {MODEL_MANIFEST['parameters']}",
        f"- 推理设备: {MODEL_MANIFEST['device']}",
        "",
        "### 模型下载脚本",
        "```python",
        MODEL_MANIFEST['python_download_script'].strip(),
        "```",
        "",
        "## 2. 输入数据版本",
        "",
        f"- 基线版本: {V03_BASELINE['version']}",
        f"- ZIP SHA256: `{V03_BASELINE['zip_sha256']}`",
        f"- 文档纠正: {V03_BASELINE['status']['document_responses_implemented']}项已实施",
        f"- 独立复查: {V03_BASELINE['status']['independent_recheck_accepted']}项已接受",
        f"- 实体试验: {V03_BASELINE['status']['physical_tests']}",
        f"- 采购状态: {V03_BASELINE['status']['procurement']}",
        f"- 产品交付: {V03_BASELINE['status']['product_release']}",
        "",
        "## 3. 测试结果",
        "",
        f"- pytest退出码: {pytest_results['exit_code']}",
        f"- 通过测试: {pytest_results['passed']}",
        f"- 失败测试: {pytest_results['failed']}",
        "",
        "## 4. 工作流执行",
        "",
        f"- 运行ID: {workflow_results['run_id']}",
        f"- 执行时长: {workflow_results.get('duration_seconds', 'N/A'):.1f}秒",
        f"- 角色执行: {len(workflow_results['roles_executed'])}/12",
        "",
        "### 角色表",
        "",
        "| 角色 | 阶段 | 输出质量 | 需审查 |",
        "|------|------|----------|--------|",
    ]
    
    for role in workflow_results['roles_executed']:
        q = workflow_results['quality_summary'].get(role, {})
        quality = q.get('quality', 'UNKNOWN')
        needs_review = "是" if q.get('needs_review', True) else "否"
        report_lines.append(f"| {role} | 完成 | {quality} | {needs_review} |")
    
    llm_summary = workflow_results['quality_summary'].get('llm_calls', {})
    
    report_lines.extend([
        "",
        "### LLM调用统计",
        "",
        f"- 总调用次数: {llm_summary.get('call_count', 'N/A')}",
        f"- 总输入tokens: {llm_summary.get('total_input_tokens', 'N/A')}",
        f"- 总输出tokens: {llm_summary.get('total_output_tokens', 'N/A')}",
        f"- 总延迟: {llm_summary.get('total_latency_ms', 'N/A')}ms",
        "",
        "## 5. 质量门禁状态",
        "",
        f"- 门禁决策: **{workflow_results['final_gate_status']}**",
        f"- 确定性决策: {workflow_results['gate_is_deterministic']}",
        f"- 反思循环: {'已执行' if workflow_results.get('reflection_loop_executed') else '未执行'}",
        "",
        "### v0.3 Findings状态",
        "",
        "| Finding | 文档纠正 | 独立复查 | 实体 | 工程关闭 |",
        "|---------|----------|----------|------|----------|",
    ])
    
    for fid, status in V03_BASELINE['findings_status'].items():
        report_lines.append(
            f"| {fid} | {status['doc']} | {status['recheck']} | {status['physical']} | {status['engineering']} |"
        )
    
    report_lines.extend([
        "",
        "## 6. 关键约束确认",
        "",
        "- [ ] 文档纠正 ≠ 工程验证通过",
        "- [ ] 所有HOLD状态保留",
        "- [ ] 采购NOT_READY",
        "- [ ] 产品交付NOT_READY",
        "- [ ] 竞争力UNVERIFIED",
        "- [ ] 模型执行成功 ≠ 专业产物合格",
        "",
        "## 7. 输出文件",
        "",
        f"- live_trace.json: `{workflow_results.get('trace_path', 'N/A')}`",
        f"- live_trace.jsonl: `{workflow_results.get('jsonl_path', 'N/A')}`",
        f"- llm_calls.json: `{workflow_results.get('calls_path', 'N/A')}`",
        f"- model_manifest.json: `{output_dir / 'model_manifest.json'}`",
        "",
        "## 8. 免责声明",
        "",
        "```",
        "⚠️ 研发工作流演示：本输出由Qwen2.5-0.5B-Instruct小模型生成，",
        "未经工程验证，不代表已审查研究基线的专业质量。",
        "模型执行成功≠专业产物合格。所有HOLD项继续保留。",
        "```",
    ])
    
    report_path = output_dir / "验收报告_最终.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))
    
    return report_path


def main():
    """Main entry point."""
    print("=" * 60)
    print("锅炉FBG多智能体工作流 - 最终交付")
    print("=" * 60)
    print(f"开始时间: {datetime.now().isoformat()}")
    print("")
    
    output_dir = Path(__file__).parent / "outputs" / "final_delivery"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Step 1: Verify model
    model_info = verify_model()
    if model_info["status"] != "available":
        print("模型不可用，退出")
        sys.exit(1)
    
    # Step 2: Run pytest
    pytest_results = run_pytest()
    
    # Save pytest output
    pytest_log_path = output_dir / "pytest_full_results.txt"
    with open(pytest_log_path, "w", encoding="utf-8") as f:
        f.write(pytest_results["output"])
    
    # Step 3: Run workflow
    workflow_results = run_full_workflow()
    
    # Step 4: Create model manifest
    manifest_path = create_model_manifest(output_dir, model_info)
    
    # Step 5: Create acceptance report
    report_path = create_acceptance_report(output_dir, model_info, pytest_results, workflow_results)
    
    # Summary
    print("")
    print("=" * 60)
    print("最终交付完成")
    print("=" * 60)
    print(f"输出目录: {output_dir}")
    print(f"验收报告: {report_path}")
    print(f"模型清单: {manifest_path}")
    print(f"测试日志: {pytest_log_path}")
    print(f"工作流trace: {workflow_results.get('trace_path')}")
    print(f"工作流JSONL: {workflow_results.get('jsonl_path')}")
    print("")
    print(f"结束时间: {datetime.now().isoformat()}")
    
    return {
        "output_dir": str(output_dir),
        "model_info": model_info,
        "pytest_results": pytest_results,
        "workflow_results": workflow_results,
        "report_path": str(report_path),
        "manifest_path": str(manifest_path),
    }


if __name__ == "__main__":
    main()
