#!/usr/bin/env python3
"""Run v0.3.1 Corrected Workflow - Fixes RUN-01 through RUN-04.

Fixes implemented:
- RUN-01: Strict root JSON parse, no regex salvage, semantic anomaly detection
- RUN-02: Fact source tracking, semantic anomaly quarantine
- RUN-03: Dynamic artifact passing to QA/PM, input_artifact_ids tracking
- RUN-04: Stage-specific schemas, PM vs PM_REWORK different contracts

Usage:
    python3 run_v031_corrected.py [--model-size 0.5B|1.5B|3B]
"""

from __future__ import annotations
import json
import os
import sys
import argparse
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from boiler_fbg_workflow.v031_loader import (
    load_v031_baseline,
    build_v031_context,
    V031_EXPECTED_SHA256,
)
from boiler_fbg_workflow.strict_json_parser import (
    strict_parse_json,
    StrictParseResult,
)
from boiler_fbg_workflow.stage_schemas import (
    get_schema,
    validate_against_schema,
    get_schema_prompt_hint,
    STAGE_SCHEMAS,
)
from boiler_fbg_workflow.artifact_registry import (
    ArtifactRegistry,
    Artifact,
)
from boiler_fbg_workflow.llm_provider import (
    LLMProviderFactory,
    LLMCallRegistry,
    LLMCallTrace,
)


def run_stage(
    provider,
    llm_registry: LLMCallRegistry,
    artifact_registry: ArtifactRegistry,
    stage: str,
    role_desc: str,
    v031_context: str,
    task_prompt: str,
    max_tokens: int = 400,
    input_artifact_ids: list[str] = None,
) -> tuple[LLMCallTrace, Artifact]:
    """Run a single stage with proper validation and artifact tracking."""
    
    # Get schema for this stage
    schema = get_schema(stage)
    schema_hint = get_schema_prompt_hint(stage)
    
    # Build system prompt
    system = f"""你是燃煤锅炉水冷壁光纤测温产品研发团队的{stage}。

角色职责：{role_desc}

{v031_context}

关键约束（违反将被标记为QUARANTINED）：
1. 链路余量UNKNOWN，不可声称"影响不大"、"足够"或"充足"
2. 未知成本不可填0，必须标UNKNOWN
3. FWHM不是全谱边界保证，不可声称"满足"或"基本满足"
4. 采购NOT_READY，不可声称"已就绪"
5. 精度NOT_PROVEN，不可声称"满足±3℃"
6. 10项工程验证仍OPEN，不可声称PASS
7. 不可虚构公司名称、价格或客户证言
8. 真实限制（如NOT_READY）应放入required_disclosures，不是forbidden_claims

{schema_hint}
输出必须是有效JSON，不可包含//注释。控制在250字以内。"""

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": task_prompt},
    ]
    
    # Generate
    trace = provider.generate(
        messages=messages,
        max_tokens=max_tokens,
        temperature=0.3,
        role=stage,
        stage=f"{stage.lower()}_analysis",
    )
    llm_registry.record(trace)
    
    # RUN-01 Fix: Strict root JSON parse
    parse_result = strict_parse_json(trace.response)
    
    # RUN-04 Fix: Validate against stage-specific schema
    schema_valid = False
    validation_issues = []
    
    if parse_result.success and parse_result.parsed:
        schema_valid, validation_issues = validate_against_schema(
            parse_result.parsed, stage
        )
    else:
        validation_issues = [parse_result.error_message]
    
    # RUN-02 Fix: Convert semantic anomalies to dict format
    semantic_anomalies = [
        {
            "id": a.anomaly_id,
            "severity": a.severity,
            "pattern": a.pattern_matched,
            "conflict": a.conflict,
            "context": a.raw_context,
        }
        for a in parse_result.semantic_anomalies
    ]
    
    # RUN-03 Fix: Register artifact with tracking
    artifact = artifact_registry.register(
        source_role=stage,
        stage=f"{stage.lower()}_analysis",
        raw_response=trace.response,
        parsed_output=parse_result.parsed,
        parse_success=parse_result.success,
        schema_valid=schema_valid,
        validation_issues=validation_issues,
        semantic_anomalies=semantic_anomalies,
    )
    
    # Update trace with validation
    trace.parsed_output = parse_result.parsed or {}
    trace.parse_success = parse_result.success
    trace.validation_status = "VALID" if (parse_result.success and schema_valid) else (
        "PARSE_FAILED" if not parse_result.success else "SCHEMA_FAILED"
    )
    trace.validation_issues = validation_issues
    
    return trace, artifact


def main():
    parser = argparse.ArgumentParser(description="Run v0.3.1 corrected workflow")
    parser.add_argument(
        "--model-size",
        choices=["0.5B", "1.5B", "3B"],
        default="1.5B",
        help="Model size (default: 1.5B)",
    )
    parser.add_argument(
        "--output-dir",
        default="./outputs/v031_corrected",
        help="Output directory",
    )
    args = parser.parse_args()
    
    print("=" * 60)
    print("锅炉FBG多智能体工作流 - v0.3.1修正版")
    print("修复: RUN-01/02/03/04")
    print("=" * 60)
    
    start_time = datetime.now(timezone.utc)
    print(f"开始时间: {start_time.isoformat()}")
    
    # Step 1: Load baseline
    print("\n[步骤1] 加载v0.3.1基线...")
    baseline = load_v031_baseline()
    assert baseline.version == "v0.3.1"
    assert baseline.zip_sha256 == V031_EXPECTED_SHA256
    print(f"  版本: {baseline.version}, SHA256验证通过")
    
    v031_context = build_v031_context(baseline)
    
    # Step 2: Initialize
    print(f"\n[步骤2] 初始化模型 ({args.model_size})...")
    provider = LLMProviderFactory.create_local(args.model_size)
    llm_registry = LLMCallRegistry()
    
    run_id = f"V031-CORR-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    artifact_registry = ArtifactRegistry(run_id)
    
    print(f"  运行ID: {run_id}")
    print(f"  模型: {provider.model_id}")
    
    # Step 3: Run expert roles (concise prompts to avoid context overflow)
    print("\n[步骤3] 运行专家角色...")
    
    expert_roles = [
        ("MKT", "市场研究员", "分析市场状况。market_size标UNKNOWN若无数据。不可虚构公司名或价格。"),
        ("OPT", "光学/热工工程师", "分析技术可行性。FWHM不是全谱保证。波长预算不可声称'充足'。"),
        ("HW", "硬件集成工程师", "分析硬件设计。链路余量UNKNOWN，必须承认影响未知。"),
        ("SW", "软件开发工程师", "分析软件架构。包含blind_window_stats统计而非仅百分比。"),
        ("SCM", "供应链经理", "分析供应链。采购NOT_READY。未知成本标UNKNOWN不填0。"),
        ("MFG", "制造/NPI工程师", "评估NPI就绪状态。产品NOT_READY。"),
        ("TRN", "培训工程师", "分析培训需求。不用2023日期。具体资质而非泛化。"),
        ("FIN", "财务分析师", "财务分析。stage_risks不可为空。A0-B64全UNKNOWN。"),
        ("SLS", "销售/营销专员", "销售策略。真实限制(NOT_READY等)放required_disclosures。不可虚构客户证言。"),
        ("STR", "战略规划师", "战略分析。当前阶段为研究基线。"),
    ]
    
    expert_artifacts = {}
    
    for role, role_desc, task in expert_roles:
        print(f"  [{role}] {role_desc[:15]}...", end=" ")
        trace, artifact = run_stage(
            provider=provider,
            llm_registry=llm_registry,
            artifact_registry=artifact_registry,
            stage=role,
            role_desc=role_desc,
            v031_context=v031_context,
            task_prompt=task,
            max_tokens=350,
        )
        expert_artifacts[role] = artifact
        
        status = "✓" if artifact.trust_level == "VERIFIED" else (
            "⚠" if artifact.trust_level == "UNVERIFIED" else "✗"
        )
        print(f"{status} {artifact.trust_level} (异常:{len(artifact.semantic_anomalies)})")
    
    # Step 4: RUN-03 Fix - QA receives actual upstream outputs
    print("\n[步骤4] QA审查（接收实际上游输出）...")
    
    # Build QA input with actual upstream summaries
    upstream_summaries = artifact_registry.get_summaries_for_qa(
        ["MKT", "OPT", "HW", "SW", "SCM", "MFG", "TRN", "FIN", "SLS"]
    )
    input_artifact_ids = artifact_registry.get_input_artifact_ids("QA")
    
    qa_task = f"""基于以下实际团队输出进行QA审查：

{upstream_summaries}

输入artifact IDs: {', '.join(input_artifact_ids)}

请审查：
1. 哪些输出需要返工（列出artifact_id）
2. 文档纠正ACCEPTED vs 工程验证OPEN的区别
3. 证据缺口
4. 门禁决策（必须BLOCKED）"""

    qa_trace, qa_artifact = run_stage(
        provider=provider,
        llm_registry=llm_registry,
        artifact_registry=artifact_registry,
        stage="QA",
        role_desc="独立质量评审员",
        v031_context=v031_context,
        task_prompt=qa_task,
        max_tokens=400,
        input_artifact_ids=input_artifact_ids,
    )
    print(f"  [QA] {qa_artifact.trust_level} (输入artifacts: {len(input_artifact_ids)})")
    
    # Step 5: PM synthesis with actual upstream
    print("\n[步骤5] PM综合（接收实际团队输出）...")
    
    pm_input_ids = artifact_registry.get_input_artifact_ids("PM")
    quarantined = artifact_registry.get_quarantined()
    
    pm_task = f"""综合以下团队输出：

隔离区artifact ({len(quarantined)}个):
{[a.artifact_id + ': ' + a.quarantine_reason for a in quarantined]}

QA审查结果:
- artifact_id: {qa_artifact.artifact_id}
- 信任级别: {qa_artifact.trust_level}
- 原文摘要: {qa_artifact.raw_response[:200]}...

请综合：
1. output_summary: 各角色输出状态
2. rework_items: 需返工项目（引用artifact_id）
3. action_plan: 行动计划"""

    pm_trace, pm_artifact = run_stage(
        provider=provider,
        llm_registry=llm_registry,
        artifact_registry=artifact_registry,
        stage="PM",
        role_desc="项目经理",
        v031_context=v031_context,
        task_prompt=pm_task,
        max_tokens=400,
        input_artifact_ids=pm_input_ids,
    )
    print(f"  [PM] {pm_artifact.trust_level}")
    
    # Step 6: RUN-04 Fix - PM_REWORK with correct schema
    print("\n[步骤6] PM返工（使用正确的PM_REWORK schema）...")
    
    # Collect failed artifacts for rework
    failed_artifacts = [
        a for a in artifact_registry.get_all()
        if a.trust_level != "VERIFIED" and a.source_role not in ["QA", "PM"]
    ]
    
    rework_task = f"""执行返工闭环。

需返工的artifacts ({len(failed_artifacts)}个):
{json.dumps([{'id': a.artifact_id, 'role': a.source_role, 'reason': a.quarantine_reason or a.validation_issues[:1]} for a in failed_artifacts[:5]], ensure_ascii=False, indent=2)}

请回答（注意：PM_REWORK schema与PM不同）：
1. trigger_output: 触发返工的具体artifact_id
2. trigger_reason: 触发原因（引用具体问题）
3. correction_actions: 修正措施列表
4. needs_reqa: 是否需要再次QA审查（布尔值）"""

    rework_trace, rework_artifact = run_stage(
        provider=provider,
        llm_registry=llm_registry,
        artifact_registry=artifact_registry,
        stage="PM_REWORK",
        role_desc="项目经理执行返工",
        v031_context=v031_context,
        task_prompt=rework_task,
        max_tokens=350,
    )
    print(f"  [PM_REWORK] {rework_artifact.trust_level}")
    
    # Step 7: Compile results
    print("\n[步骤7] 编译结果...")
    
    end_time = datetime.now(timezone.utc)
    duration_ms = int((end_time - start_time).total_seconds() * 1000)
    
    llm_summary = llm_registry.get_summary()
    all_artifacts = artifact_registry.get_all()
    
    # Count by trust level
    trust_counts = {
        "VERIFIED": len([a for a in all_artifacts if a.trust_level == "VERIFIED"]),
        "UNVERIFIED": len([a for a in all_artifacts if a.trust_level == "UNVERIFIED"]),
        "QUARANTINED": len([a for a in all_artifacts if a.trust_level == "QUARANTINED"]),
    }
    
    # Count semantic anomalies
    total_anomalies = sum(len(a.semantic_anomalies) for a in all_artifacts)
    
    results = {
        "run_id": run_id,
        "fixes_applied": ["RUN-01", "RUN-02", "RUN-03", "RUN-04"],
        "start_time_utc": start_time.isoformat(),
        "end_time_utc": end_time.isoformat(),
        "duration_ms": duration_ms,
        
        "input": {
            "version": baseline.version,
            "sha256": baseline.zip_sha256,
            "verified": True,
        },
        
        "model": {
            "id": provider.model_id,
            "size": provider.model_size,
            "license": provider.model_license,
            "revision": provider.model_revision,
        },
        
        "execution": {
            "total_calls": llm_summary["total_calls"],
            "test_calls": 0,  # No separate test call
            "business_calls": llm_summary["total_calls"],
            "total_prompt_tokens": llm_summary.get("total_prompt_tokens", 0),
            "total_response_tokens": llm_summary.get("total_response_tokens", 0),
            "total_latency_ms": llm_summary.get("total_latency_ms", 0),
        },
        
        "validation": {
            "artifacts_total": len(all_artifacts),
            "verified": trust_counts["VERIFIED"],
            "unverified": trust_counts["UNVERIFIED"],
            "quarantined": trust_counts["QUARANTINED"],
            "semantic_anomalies_total": total_anomalies,
        },
        
        "gate_status": "BLOCKED",
        "gate_reason": "工程验证10项OPEN, 实体试验NOT_RUN, 采购NOT_READY",
        "gate_is_deterministic": True,
        
        "artifacts": artifact_registry.export(),
        "schemas_used": {k: {"id": v.schema_id, "version": v.schema_version} 
                        for k, v in STAGE_SCHEMAS.items()},
    }
    
    print(f"\n  运行ID: {run_id}")
    print(f"  时长: {duration_ms/1000:.1f}秒")
    print(f"  LLM调用: {llm_summary['total_calls']}次")
    print(f"\n  信任级别统计:")
    print(f"    VERIFIED: {trust_counts['VERIFIED']}")
    print(f"    UNVERIFIED: {trust_counts['UNVERIFIED']}")
    print(f"    QUARANTINED: {trust_counts['QUARANTINED']}")
    print(f"    语义异常总计: {total_anomalies}")
    print(f"\n  门禁状态: BLOCKED (确定性)")
    
    # Save outputs
    print("\n[步骤8] 保存输出...")
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Main trace
    trace_path = output_dir / f"live_trace_{run_id}.json"
    with open(trace_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"  trace: {trace_path}")
    
    # LLM calls
    calls_path = output_dir / f"llm_calls_{run_id}.json"
    llm_registry.save(str(calls_path))
    print(f"  calls: {calls_path}")
    
    # Artifacts
    artifacts_path = output_dir / f"artifacts_{run_id}.json"
    with open(artifacts_path, "w", encoding="utf-8") as f:
        json.dump(artifact_registry.export(), f, ensure_ascii=False, indent=2)
    print(f"  artifacts: {artifacts_path}")
    
    # Manifest
    manifest = {
        "run_id": run_id,
        "created_utc": end_time.isoformat(),
        "input_version": baseline.version,
        "input_sha256": baseline.zip_sha256,
        "model_id": provider.model_id,
        "model_size": provider.model_size,
        "fixes_applied": ["RUN-01", "RUN-02", "RUN-03", "RUN-04"],
        "execution": results["execution"],
        "validation": results["validation"],
        "gate_status": "BLOCKED",
    }
    manifest_path = output_dir / "model_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"  manifest: {manifest_path}")
    
    print("\n" + "=" * 60)
    print("完成")
    print("=" * 60)
    
    return results


if __name__ == "__main__":
    main()
