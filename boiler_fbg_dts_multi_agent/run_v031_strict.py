#!/usr/bin/env python3
"""Run v0.3.1 Strict Workflow - Real data, strict validation, evidence checks.

This script:
1. LOADS v0.3.1 baseline from extracted directory (not hardcoded)
2. ASSERTS version and SHA256 match
3. Uses larger model (1.5B default) for better quality
4. STRICT validation - no empty {} as VALID, truncation = TRUNCATED
5. Evidence constraint checking
6. Auto-computed statistics (not manually filled)

Usage:
    python3 run_v031_strict.py [--model-size 0.5B|1.5B|3B]
"""

from __future__ import annotations
import json
import os
import sys
import argparse
from datetime import datetime, timezone
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from boiler_fbg_workflow.v031_loader import (
    load_v031_baseline,
    build_v031_context,
    check_evidence_violations,
    V031_EXPECTED_SHA256,
)
from boiler_fbg_workflow.strict_validator import (
    validate_output,
    OutputStatus,
    ValidationResult,
)
from boiler_fbg_workflow.llm_provider import (
    LLMProviderFactory,
    LLMCallRegistry,
    ProviderType,
)


def create_agent_prompt(
    role: str,
    role_desc: str,
    v031_context: str,
    task_prompt: str,
) -> list[dict[str, str]]:
    """Create agent prompt with v0.3.1 context."""
    system = f"""你是燃煤锅炉水冷壁光纤测温产品研发团队的{role}。

角色职责：{role_desc}

{v031_context}

关键约束（不可违反）：
1. 链路余量UNKNOWN，不可声称"影响不大"或"无需关注"
2. 未知成本不可填0，必须标UNKNOWN
3. FWHM不是全谱边界保证，不可声称"满足"或"基本满足"
4. 采购NOT_READY，不可声称"已就绪"
5. 精度NOT_PROVEN，不可声称"满足±3℃"或"±5℃可达"
6. 文档纠正ACCEPTED ≠ 工程验证PASS

请用JSON格式回答，控制在300字以内。"""

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": task_prompt},
    ]


def run_single_agent(
    provider,
    registry: LLMCallRegistry,
    role: str,
    role_desc: str,
    v031_context: str,
    task_prompt: str,
    max_tokens: int = 500,
) -> dict:
    """Run single agent with strict validation."""
    messages = create_agent_prompt(role, role_desc, v031_context, task_prompt)
    
    # Generate
    trace = provider.generate(
        messages=messages,
        max_tokens=max_tokens,
        temperature=0.3,
        role=role,
        stage=f"{role.lower()}_analysis",
    )
    registry.record(trace)
    
    # Strict validation
    validation = validate_output(
        raw_response=trace.response,
        finish_reason=trace.finish_reason,
        token_count=trace.response_tokens,
        role=role,
        check_evidence=True,
    )
    
    # Update trace with validation results
    trace.parsed_output = validation.parsed_output or {}
    trace.parse_success = validation.parse_success
    trace.validation_status = validation.status.value
    trace.validation_issues = validation.issues
    
    return {
        "role": role,
        "stage": f"{role.lower()}_analysis",
        "trace": trace.to_dict(),
        "raw_response": trace.response,
        "parsed_output": validation.parsed_output,
        "validation": validation.to_dict(),
        "evidence_violations": validation.evidence_violations,
        "is_valid": validation.is_valid,
        "is_usable": validation.is_usable,
    }


def main():
    parser = argparse.ArgumentParser(description="Run v0.3.1 strict workflow")
    parser.add_argument(
        "--model-size",
        choices=["0.5B", "1.5B", "3B"],
        default="1.5B",
        help="Model size to use (default: 1.5B)",
    )
    parser.add_argument(
        "--output-dir",
        default="./outputs/v031_strict",
        help="Output directory",
    )
    args = parser.parse_args()
    
    print("=" * 60)
    print("锅炉FBG多智能体工作流 - v0.3.1严格验证")
    print("=" * 60)
    
    start_time = datetime.now(timezone.utc)
    print(f"开始时间: {start_time.isoformat()}")
    print()
    
    # Step 1: Load and verify v0.3.1 baseline
    print("=" * 60)
    print("步骤 1: 加载并验证v0.3.1基线")
    print("=" * 60)
    
    try:
        baseline = load_v031_baseline()
        print(f"  版本: {baseline.version}")
        print(f"  SHA256: {baseline.zip_sha256}")
        print(f"  独立复查已接受: {baseline.independent_review_accepted}/10")
        print(f"  工程验证OPEN: {baseline.engineering_open}/10")
        print(f"  实体试验: {baseline.physical_not_run}项NOT_RUN")
        print(f"  采购状态: {baseline.procurement_status}")
        print(f"  产品交付: {baseline.product_release}")
        
        # Strict assertion
        assert baseline.version == "v0.3.1", f"版本不匹配: {baseline.version}"
        assert baseline.zip_sha256 == V031_EXPECTED_SHA256, "SHA256不匹配"
        assert baseline.independent_review_accepted == 10, "独立复查接受数不匹配"
        
        print()
        print("  ✓ v0.3.1基线验证通过")
    except Exception as e:
        print(f"  ✗ 基线验证失败: {e}")
        sys.exit(1)
    
    v031_context = build_v031_context(baseline)
    print()
    
    # Step 2: Initialize provider
    print("=" * 60)
    print(f"步骤 2: 初始化模型 ({args.model_size})")
    print("=" * 60)
    
    provider = LLMProviderFactory.create_local(args.model_size)
    registry = LLMCallRegistry()
    
    print(f"  模型: {provider.model_id}")
    print(f"  大小: {provider.model_size}")
    print(f"  许可: {provider.model_license}")
    print()
    
    # Step 3: Run test sample first
    print("=" * 60)
    print("步骤 3: 测试样本验证")
    print("=" * 60)
    
    test_result = run_single_agent(
        provider=provider,
        registry=registry,
        role="TEST",
        role_desc="测试角色",
        v031_context=v031_context,
        task_prompt='请回答一个简单的JSON: {"test": "ok", "version": "v0.3.1"}',
        max_tokens=100,
    )
    
    print(f"  测试验证状态: {test_result['validation']['status']}")
    print(f"  解析成功: {test_result['validation']['parse_success']}")
    if test_result['validation']['issues']:
        print(f"  问题: {test_result['validation']['issues']}")
    print()
    
    # Step 4: Run 12-role team
    print("=" * 60)
    print("步骤 4: 运行12角色团队")
    print("=" * 60)
    
    # Role definitions
    roles = [
        ("MKT", "市场研究员", f"""基于v0.3.1研究数据分析市场状况：
目标场景：660MW超临界水冷壁FBG监测
请分析：1.市场容量(UNKNOWN则标明) 2.竞品状态 3.客户痛点 4.进入风险
用JSON格式回答，包含market_size, competitors, pain_points, entry_risks字段。"""),
        
        ("OPT", "光学/热工工程师", f"""分析技术可行性：
- FWHM: 0.8nm (注意：不是全谱边界保证)
- 链路余量: UNKNOWN (不可声称影响不大)
- 现场精度: NOT_PROVEN

请分析：1.FWHM vs 全谱罩区别 2.波长预算状态 3.不确定度状态 4.待完成验证
用JSON格式回答，包含fwhm_analysis, wavelength_budget, uncertainty_status字段。"""),
        
        ("HW", "硬件集成工程师", f"""分析硬件设计：
- 链路余量: UNKNOWN (必须承认影响未知，不可轻忽)
- 机械设计: 热胀释放待验证
- 解调仪: Luna/HBK均HOLD

请分析：1.热胀设计要点 2.链路余量UNKNOWN的真实影响 3.集成风险 4.待完成任务
用JSON格式回答，包含thermal_design, link_margin_impact, integration_risks字段。"""),
        
        ("SW", "软件开发工程师", f"""分析软件架构：
- 可用率: 99.5%/99.0% (proposal未批准)
- 最长盲区: 10s (需统计而非仅百分比)
- AI隔离: 不在关键路径

请分析：1.盲区统计实现 2.数据流设计 3.AI安全隔离 4.待实现功能
用JSON格式回答，包含blind_window_stats, data_flow, ai_isolation字段。"""),
        
        ("SCM", "供应链经理", f"""分析供应链：
- 采购状态: NOT_READY
- A0/A1/A2/B32/B64: 全部UNKNOWN (不可填0)
- Technica: 已撤销

请分析：1.可用供应商 2.采购阻塞项 3.资金不确定性(未知不填0) 4.待办任务
用JSON格式回答，包含available_vendors, blocking_items, funding_uncertainty字段。"""),
        
        ("MFG", "制造/NPI工程师", f"""评估NPI就绪：
- 产品交付: NOT_READY
- BOM: 预算占位
- DVT/PVT/FAT/SAT: 全部NOT_RUN

请分析：1.NPI阻塞项 2.前置条件 3.测试清单 4.待办任务
用JSON格式回答，包含npi_blockers, prerequisites, test_checklist字段。"""),
        
        ("TRN", "培训工程师", f"""分析培训需求：
- 首版AI: 监测/预警/建议，人工决策
- 不得闭环控制DCS
- 需遵守锅监/OEM许可

请分析：1.培训模块 2.安全操作要点 3.所需认证 4.待办任务
用JSON格式回答，包含training_modules, safety_points, certifications字段。"""),
        
        ("FIN", "财务分析师", f"""进行财务分析：
- A0/A1/A2/B32/B64: 全部UNKNOWN
- 未知成本不得填0
- 竞争力: UNVERIFIED

请分析：1.资金缺口(哪些UNKNOWN) 2.阶段风险 3.竞争力状态(UNVERIFIED原因) 4.待办任务
用JSON格式回答，包含funding_gaps, stage_risks, competitiveness_status字段。"""),
        
        ("SLS", "销售/营销专员", f"""分析销售策略：
- 产品交付: NOT_READY
- 竞争力: UNVERIFIED
- 无真实项目业绩

请分析：1.可用营销材料 2.不可宣称内容(列出) 3.客户开发前置条件 4.待办任务
用JSON格式回答，包含available_materials, forbidden_claims, prerequisites字段。"""),
        
        ("QA", "独立质量评审员", f"""基于v0.3.1进行QA审查：
- 文档纠正: 10/10 ACCEPTED (独立复审)
- 工程验证: 10项OPEN
- 实体试验: 10项NOT_RUN
- 采购/产品: NOT_READY

请审查：1.需返工项目 2.文档纠正vs工程验证区别 3.证据缺口 4.门禁决策(必须BLOCKED)
用JSON格式回答，包含rework_required, doc_vs_engineering, evidence_gaps, gate_decision字段。"""),
        
        ("PM", "项目经理", f"""综合团队输出：
- 文档纠正ACCEPTED ≠ 工程验证PASS
- QA门禁: BLOCKED (确定性)

请综合：1.各角色输出状态 2.需返工项目 3.行动计划
用JSON格式回答，包含output_summary, rework_items, action_plan字段。"""),
        
        ("STR", "战略规划师", f"""进行战略分析：
- 当前阶段: 研究基线v0.3.1
- 工程验证: 全部OPEN
- 采购/产品: NOT_READY

请分析：1.当前阶段定位 2.关键里程碑 3.Go/No-Go决策点 4.建议
用JSON格式回答，包含current_phase, milestones, go_nogo_points字段。"""),
    ]
    
    team_outputs = {}
    
    for i, (role, role_desc, task_prompt) in enumerate(roles, 1):
        print(f"  [{i}/12] {role}: {role_desc[:20]}...")
        
        result = run_single_agent(
            provider=provider,
            registry=registry,
            role=role,
            role_desc=role_desc,
            v031_context=v031_context,
            task_prompt=task_prompt,
            max_tokens=500,
        )
        
        team_outputs[role] = result
        
        # Print validation status
        status = result['validation']['status']
        status_emoji = "✓" if result['is_valid'] else ("⚠" if result['is_usable'] else "✗")
        print(f"       {status_emoji} 状态: {status}")
        
        if result['evidence_violations']:
            for v in result['evidence_violations']:
                print(f"       ⚠ 证据违规: {v['finding']}")
    
    print()
    
    # Step 5: Reflection loop
    print("=" * 60)
    print("步骤 5: 反思闭环 (Reflection Pattern)")
    print("=" * 60)
    
    # Collect issues for reflection
    issues_for_reflection = []
    for role, result in team_outputs.items():
        if not result['is_valid']:
            issues_for_reflection.append({
                "role": role,
                "status": result['validation']['status'],
                "issues": result['validation']['issues'],
            })
        if result['evidence_violations']:
            for v in result['evidence_violations']:
                issues_for_reflection.append({
                    "role": role,
                    "type": "evidence_violation",
                    "violation": v,
                })
    
    print(f"  发现{len(issues_for_reflection)}个需返工项目:")
    for issue in issues_for_reflection[:5]:
        print(f"    - {issue['role']}: {issue.get('status', issue.get('type', ''))}")
    if len(issues_for_reflection) > 5:
        print(f"    ... 等{len(issues_for_reflection) - 5}项")
    
    # PM rework execution
    rework_result = run_single_agent(
        provider=provider,
        registry=registry,
        role="PM",
        role_desc="项目经理执行返工闭环",
        v031_context=v031_context,
        task_prompt=f"""执行返工闭环 (Reflection Pattern, Ch4 P67-82)：

发现的问题 ({len(issues_for_reflection)}项):
{json.dumps(issues_for_reflection[:5], ensure_ascii=False, indent=2)}

请：
1. 明确哪个角色的输出触发返工
2. 返工原因(引用具体QA finding或证据约束)
3. 修正措施
4. 是否需再次审查

用JSON格式回答，包含trigger_output, trigger_reason, correction_actions, needs_reqa字段。""",
        max_tokens=500,
    )
    
    team_outputs["PM_REWORK"] = rework_result
    print(f"  PM返工执行: {rework_result['validation']['status']}")
    print()
    
    # Step 6: Compile results
    print("=" * 60)
    print("步骤 6: 编译结果")
    print("=" * 60)
    
    end_time = datetime.now(timezone.utc)
    duration_ms = int((end_time - start_time).total_seconds() * 1000)
    
    # Auto-compute statistics from registry
    llm_summary = registry.get_summary()
    
    # Compute validation statistics
    valid_count = sum(1 for r in team_outputs.values() if r['is_valid'])
    truncated_count = sum(1 for r in team_outputs.values() 
                        if r['validation']['status'] == OutputStatus.TRUNCATED.value)
    parse_failed_count = sum(1 for r in team_outputs.values()
                            if r['validation']['status'] == OutputStatus.PARSE_FAILED.value)
    evidence_violation_count = sum(1 for r in team_outputs.values()
                                  if r['evidence_violations'])
    
    results = {
        "run_id": f"V031-STRICT-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "start_time_utc": start_time.isoformat(),
        "end_time_utc": end_time.isoformat(),
        "duration_ms": duration_ms,
        
        "input": {
            "version": baseline.version,
            "sha256": baseline.zip_sha256,
            "independent_review_accepted": baseline.independent_review_accepted,
            "engineering_open": baseline.engineering_open,
            "physical_not_run": baseline.physical_not_run,
            "procurement_status": baseline.procurement_status,
            "product_release": baseline.product_release,
        },
        
        "model": {
            "id": provider.model_id,
            "size": provider.model_size,
            "license": provider.model_license,
        },
        
        "execution": {
            "roles_executed": len(team_outputs),
            "llm_calls": llm_summary["total_calls"],
            "total_prompt_tokens": llm_summary.get("total_prompt_tokens", 0),
            "total_response_tokens": llm_summary.get("total_response_tokens", 0),
            "total_latency_ms": llm_summary.get("total_latency_ms", 0),
            "avg_latency_ms": llm_summary.get("avg_latency_ms", 0),
        },
        
        "validation": {
            "valid": valid_count,
            "truncated": truncated_count,
            "parse_failed": parse_failed_count,
            "evidence_violations": evidence_violation_count,
            "total": len(team_outputs),
        },
        
        "gate_status": "BLOCKED",
        "gate_reason": "工程验证10项OPEN, 实体试验NOT_RUN, 采购NOT_READY",
        "gate_is_deterministic": True,
        
        "reflection_loop": {
            "executed": True,
            "issues_found": len(issues_for_reflection),
            "pattern": "Chapter 4 (P67-82) - Reflection Pattern",
        },
        
        "team_outputs": team_outputs,
    }
    
    print(f"  运行ID: {results['run_id']}")
    print(f"  时长: {duration_ms/1000:.1f}秒")
    print(f"  LLM调用: {llm_summary['total_calls']}次")
    print(f"  输入tokens: {llm_summary.get('total_prompt_tokens', 0)}")
    print(f"  输出tokens: {llm_summary.get('total_response_tokens', 0)}")
    print()
    print(f"  验证统计:")
    print(f"    VALID: {valid_count}")
    print(f"    TRUNCATED: {truncated_count}")
    print(f"    PARSE_FAILED: {parse_failed_count}")
    print(f"    证据违规: {evidence_violation_count}")
    print()
    print(f"  门禁状态: BLOCKED (确定性)")
    print()
    
    # Step 7: Save outputs
    print("=" * 60)
    print("步骤 7: 保存输出")
    print("=" * 60)
    
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    run_id = results["run_id"]
    
    # Save main trace
    trace_path = output_dir / f"live_trace_{run_id}.json"
    with open(trace_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"  trace: {trace_path}")
    
    # Save JSONL
    jsonl_path = output_dir / f"live_trace_{run_id}.jsonl"
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for role, output in team_outputs.items():
            entry = {
                "run_id": run_id,
                "role": role,
                "validation_status": output['validation']['status'],
                "is_valid": output['is_valid'],
                "parse_success": output['validation']['parse_success'],
                "evidence_violations": len(output['evidence_violations']),
                "raw_response_preview": output['raw_response'][:200],
            }
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(f"  jsonl: {jsonl_path}")
    
    # Save LLM calls
    calls_path = output_dir / f"llm_calls_{run_id}.json"
    registry.save(str(calls_path))
    print(f"  calls: {calls_path}")
    
    # Save model manifest
    manifest = {
        "run_id": run_id,
        "created_utc": end_time.isoformat(),
        "input_version": baseline.version,
        "input_sha256": baseline.zip_sha256,
        "model_id": provider.model_id,
        "model_size": provider.model_size,
        "model_license": provider.model_license,
        "execution": results["execution"],
        "validation": results["validation"],
        "gate_status": "BLOCKED",
    }
    manifest_path = output_dir / "model_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"  manifest: {manifest_path}")
    
    print()
    print("=" * 60)
    print("完成")
    print("=" * 60)
    
    return results


if __name__ == "__main__":
    main()
