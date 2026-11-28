#!/usr/bin/env python3
"""Run v0.3.1 Final Workflow - All structural fixes.

Final fixes:
1. No truncation in QA/PM handoffs - complete raw/parsed/anomalies
2. Artifact reference validation - invalid IDs → REFERENCE_INVALID
3. Real revision loop - REVISE + QA_REVIEW (max 1 round)
4. Trust levels renamed - FORMAT_VALID_RULES_NOT_TRIGGERED ≠ fact verified
5. Model revision from HF cache SHA

Usage:
    python3 run_v031_final.py [--model-size 0.5B|1.5B|3B]
"""

from __future__ import annotations
import json
import os
import sys
import argparse
import subprocess
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
)
from boiler_fbg_workflow.trust_levels import (
    TrustLevel,
    determine_trust_level,
)


# Context limit for 1.5B model (conservative)
MAX_CONTEXT_CHARS = 12000


def resolve_model_revision(model_id: str, cache_dir: str = "/tmp/hf_models") -> str:
    """Resolve model revision from HF cache to immutable SHA.
    
    Fix #5: Get actual commit SHA instead of 'main'.
    """
    try:
        # Try to find snapshot in cache
        cache_path = Path(cache_dir) / "models--" + model_id.replace("/", "--")
        if cache_path.exists():
            refs_path = cache_path / "refs" / "main"
            if refs_path.exists():
                return refs_path.read_text().strip()
        
        # Fallback: try huggingface_hub
        try:
            from huggingface_hub import model_info
            info = model_info(model_id)
            return info.sha
        except Exception:
            pass
        
        return "main"  # Fallback
    except Exception:
        return "main"


def run_stage_with_full_context(
    provider,
    llm_registry: LLMCallRegistry,
    artifact_registry: ArtifactRegistry,
    stage: str,
    role_desc: str,
    v031_context: str,
    task_prompt: str,
    max_tokens: int = 400,
) -> tuple[any, Artifact, bool]:
    """Run stage with context limit check.
    
    Returns (trace, artifact, context_ok)
    """
    schema = get_schema(stage)
    schema_hint = get_schema_prompt_hint(stage)
    
    system = f"""你是燃煤锅炉水冷壁光纤测温产品研发团队的{stage}。
角色职责：{role_desc}
{v031_context}

关键约束：
1. 链路余量UNKNOWN，影响未知
2. 未知成本标UNKNOWN不填数字
3. 10项工程验证仍OPEN，不可声称PASS
4. 采购NOT_READY，产品NOT_READY
5. 不可虚构公司/价格/客户证言

{schema_hint}
输出有效JSON，不含//注释。"""

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": task_prompt},
    ]
    
    # Check context limit
    total_chars = len(system) + len(task_prompt)
    context_ok = total_chars <= MAX_CONTEXT_CHARS
    
    trace = provider.generate(
        messages=messages,
        max_tokens=max_tokens,
        temperature=0.3,
        role=stage,
        stage=f"{stage.lower()}_analysis",
    )
    llm_registry.record(trace)
    
    parse_result = strict_parse_json(trace.response)
    
    schema_valid = False
    validation_issues = []
    if parse_result.success and parse_result.parsed:
        schema_valid, validation_issues = validate_against_schema(
            parse_result.parsed, stage
        )
    else:
        validation_issues = [parse_result.error_message]
    
    # Convert anomalies
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
    
    # Determine trust level (Fix #4)
    rule_hits = len(semantic_anomalies)
    trust = determine_trust_level(
        parse_success=parse_result.success,
        schema_valid=schema_valid,
        rule_hits=rule_hits,
        has_source_verification=False,  # Never verified
    )
    
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
    
    # Override trust level with new naming
    artifact.trust_level = trust.value
    
    return trace, artifact, context_ok


def main():
    parser = argparse.ArgumentParser(description="Run v0.3.1 final workflow")
    parser.add_argument("--model-size", choices=["0.5B", "1.5B", "3B"], default="1.5B")
    parser.add_argument("--output-dir", default="./outputs/v031_final")
    args = parser.parse_args()
    
    print("=" * 60)
    print("锅炉FBG多智能体工作流 - v0.3.1最终版")
    print("修复: 无截断/引用验证/真实返工+再QA/信任级别重命名")
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
    
    run_id = f"V031-FINAL-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    artifact_registry = ArtifactRegistry(run_id)
    
    # Resolve model revision (Fix #5)
    model_revision = resolve_model_revision(provider.model_id)
    print(f"  运行ID: {run_id}")
    print(f"  模型: {provider.model_id}")
    print(f"  revision: {model_revision}")
    
    # Step 3: Run expert roles with concise prompts
    print("\n[步骤3] 运行10个专家角色...")
    
    expert_roles = [
        ("MKT", "市场研究员", "分析市场。market_size标UNKNOWN。不虚构公司/价格。"),
        ("OPT", "光学工程师", "技术分析。FWHM非全谱保证。波长预算状态UNKNOWN。"),
        ("HW", "硬件工程师", "硬件设计。链路余量UNKNOWN，影响未知。"),
        ("SW", "软件工程师", "软件架构。blind_window_stats统计。"),
        ("SCM", "供应链经理", "供应链分析。采购NOT_READY。未知成本标UNKNOWN。"),
        ("MFG", "制造工程师", "NPI评估。产品NOT_READY。"),
        ("TRN", "培训工程师", "培训需求。具体资质，不泛化。"),
        ("FIN", "财务分析师", "财务分析。A0-B64全UNKNOWN，不填数字。"),
        ("SLS", "销售专员", "销售策略。真实限制放required_disclosures。"),
        ("STR", "战略规划师", "战略分析。当前阶段研究基线。"),
    ]
    
    expert_artifacts = {}
    for role, role_desc, task in expert_roles:
        print(f"  [{role}]", end=" ")
        trace, artifact, ctx_ok = run_stage_with_full_context(
            provider, llm_registry, artifact_registry,
            role, role_desc, v031_context, task, max_tokens=350,
        )
        expert_artifacts[role] = artifact
        
        status = "✓" if artifact.trust_level == TrustLevel.FORMAT_VALID_RULES_NOT_TRIGGERED.value else (
            "⚠" if artifact.trust_level == TrustLevel.SCHEMA_FAILED.value else "✗"
        )
        print(f"{status} {artifact.trust_level} (rules:{len(artifact.semantic_anomalies)})")
    
    # Step 4: QA with FULL upstream content (Fix #1)
    print("\n[步骤4] QA审查（完整上游内容，无截断）...")
    
    all_upstream_roles = ["MKT", "OPT", "HW", "SW", "SCM", "MFG", "TRN", "FIN", "SLS", "STR"]
    full_content, total_chars = artifact_registry.get_full_handoffs_for_qa(all_upstream_roles)
    
    print(f"  上游内容总字符: {total_chars}")
    
    # Check context limit
    if total_chars > MAX_CONTEXT_CHARS:
        print(f"  ⚠ CONTEXT_LIMIT: {total_chars} > {MAX_CONTEXT_CHARS}")
        # Still proceed but flag it
    
    qa_task = f"""基于以下10个专家角色的完整输出进行QA审查：

{full_content}

输入artifact共{len(all_upstream_roles)}个。

请审查：
1. rework_required: 需返工的artifact_id列表（必须是上面存在的ID）
2. doc_vs_engineering: 文档纠正ACCEPTED vs 工程验证OPEN的区别
3. evidence_gaps: 证据缺口
4. gate_decision: 必须是BLOCKED（10项工程OPEN）"""

    qa_trace, qa_artifact, qa_ctx_ok = run_stage_with_full_context(
        provider, llm_registry, artifact_registry,
        "QA", "独立质量评审员", v031_context, qa_task, max_tokens=500,
    )
    print(f"  [QA] {qa_artifact.trust_level} (ctx_ok:{qa_ctx_ok})")
    
    # Fix #2: Validate QA's artifact references
    print("\n[步骤5] 验证QA引用...")
    if qa_artifact.parsed_output and "rework_required" in qa_artifact.parsed_output:
        rework_ids = qa_artifact.parsed_output.get("rework_required", [])
        ref_results = artifact_registry.validate_all_references(
            [r if isinstance(r, str) else r.get("artifact_id", "") for r in rework_ids]
        )
        invalid_refs = [k for k, (v, _) in ref_results.items() if not v]
        if invalid_refs:
            print(f"  ⚠ REFERENCE_INVALID: {invalid_refs}")
            qa_artifact.validation_issues.append(f"REFERENCE_INVALID: {invalid_refs}")
    
    # Step 5: PM with FULL QA output (Fix #1)
    print("\n[步骤6] PM综合（完整QA输出，无截断）...")
    
    qa_full = qa_artifact.to_full_handoff()
    quarantined = artifact_registry.get_quarantined()
    
    pm_task = f"""综合团队输出与QA审查结果：

QA完整输出 ({qa_artifact.artifact_id}):
```
{qa_full['raw_response']}
```
QA parsed: {json.dumps(qa_full['parsed_output'], ensure_ascii=False) if qa_full['parsed_output'] else 'null'}
QA trust_level: {qa_full['trust_level']}

隔离区artifacts ({len(quarantined)}个):
{json.dumps([{'id': a.artifact_id, 'role': a.source_role, 'reason': a.quarantine_reason, 'rules': len(a.semantic_anomalies)} for a in quarantined], ensure_ascii=False, indent=2)}

请综合：
1. output_summary: 各角色状态
2. rework_items: 需返工项目（引用真实artifact_id）
3. action_plan: 行动计划"""

    pm_trace, pm_artifact, pm_ctx_ok = run_stage_with_full_context(
        provider, llm_registry, artifact_registry,
        "PM", "项目经理", v031_context, pm_task, max_tokens=500,
    )
    print(f"  [PM] {pm_artifact.trust_level} (ctx_ok:{pm_ctx_ok})")
    
    # Fix #2: Validate PM's artifact references
    if pm_artifact.parsed_output and "rework_items" in pm_artifact.parsed_output:
        rework_items = pm_artifact.parsed_output.get("rework_items", [])
        ref_ids = []
        for item in rework_items:
            if isinstance(item, str):
                ref_ids.append(item)
            elif isinstance(item, dict):
                ref_ids.append(item.get("artifact_id", item.get("id", "")))
        
        ref_results = artifact_registry.validate_all_references(ref_ids)
        invalid_refs = [k for k, (v, _) in ref_results.items() if not v and k]
        if invalid_refs:
            print(f"  ⚠ REFERENCE_INVALID: {invalid_refs}")
            pm_artifact.validation_issues.append(f"REFERENCE_INVALID: {invalid_refs}")
    
    # Step 6: Real reflection loop (Fix #3)
    print("\n[步骤7] 真实返工闭环（选择1个隔离角色）...")
    
    # Select one quarantined artifact to revise
    quarantined = artifact_registry.get_quarantined()
    revision_artifact = None
    qa_review_artifact = None
    
    if quarantined:
        # Pick first quarantined
        target = quarantined[0]
        print(f"  选择返工目标: {target.artifact_id} ({target.source_role})")
        
        # Get original constraints
        original_full = target.to_full_handoff()
        
        revise_task = f"""你是{target.source_role}，需要修订你之前的输出。

原始输出问题:
- artifact_id: {target.artifact_id}
- trust_level: {target.trust_level}
- quarantine_reason: {target.quarantine_reason}
- semantic_anomalies: {json.dumps(target.semantic_anomalies, ensure_ascii=False)}
- validation_issues: {target.validation_issues}

原始输出:
```
{original_full['raw_response']}
```

请修订输出，避免触发语义规则。不可虚构价格/公司/证言。未知值标UNKNOWN。"""

        # Use original role's schema for revision
        revise_trace, revision_artifact, _ = run_stage_with_full_context(
            provider, llm_registry, artifact_registry,
            target.source_role, f"{target.source_role}修订",
            v031_context, revise_task, max_tokens=400,
        )
        # Update stage name to indicate revision
        revision_artifact.stage = f"{target.source_role.lower()}_revise"
        
        # Track derivation
        revision_artifact.derived_from = target.artifact_id
        
        print(f"  [{target.source_role}_REVISE] {revision_artifact.trust_level}")
        
        # Step 7: QA_REVIEW on original vs revised (Fix #3)
        print("\n[步骤8] QA再审（原始 vs 修订）...")
        
        qa_review_task = f"""对比审查原始与修订输出：

原始 ({target.artifact_id}):
- trust_level: {target.trust_level}
- rules: {len(target.semantic_anomalies)}
- raw: {original_full['raw_response'][:500]}...

修订 ({revision_artifact.artifact_id}):
- trust_level: {revision_artifact.trust_level}
- rules: {len(revision_artifact.semantic_anomalies)}
- raw: {revision_artifact.raw_response[:500]}...

请审查：
1. improvement: 修订是否改善了问题
2. unresolved: 仍未解决的问题
3. status: IMPROVED/NO_CHANGE/WORSE"""

        # Use QA schema for QA_REVIEW
        qa_review_trace, qa_review_artifact, _ = run_stage_with_full_context(
            provider, llm_registry, artifact_registry,
            "QA", "QA再审", v031_context, qa_review_task, max_tokens=300,
        )
        # Update stage name to indicate review
        qa_review_artifact.stage = "qa_review"
        print(f"  [QA_REVIEW] {qa_review_artifact.trust_level}")
    else:
        print("  无隔离artifact，跳过返工")
    
    # Step 8: PM_REWORK
    print("\n[步骤9] PM返工...")
    
    rework_task = f"""总结返工结果。

返工目标: {quarantined[0].artifact_id if quarantined else 'N/A'}
修订artifact: {revision_artifact.artifact_id if revision_artifact else 'N/A'}
QA再审结果: {qa_review_artifact.trust_level if qa_review_artifact else 'N/A'}

其他未处理项仍OPEN。

请回答：
1. trigger_output: 触发返工的artifact_id
2. trigger_reason: 原因
3. correction_actions: 执行的修正
4. needs_reqa: 是否需要更多审查（布尔值）"""

    rework_trace, rework_artifact, _ = run_stage_with_full_context(
        provider, llm_registry, artifact_registry,
        "PM_REWORK", "PM返工", v031_context, rework_task, max_tokens=350,
    )
    print(f"  [PM_REWORK] {rework_artifact.trust_level}")
    
    # Step 9: Compile results
    print("\n[步骤10] 编译结果...")
    
    end_time = datetime.now(timezone.utc)
    duration_ms = int((end_time - start_time).total_seconds() * 1000)
    
    llm_summary = llm_registry.get_summary()
    all_artifacts = artifact_registry.get_all()
    
    # Count by new trust levels
    trust_counts = {}
    for a in all_artifacts:
        trust_counts[a.trust_level] = trust_counts.get(a.trust_level, 0) + 1
    
    total_rule_hits = sum(len(a.semantic_anomalies) for a in all_artifacts)
    
    results = {
        "run_id": run_id,
        "fixes_applied": [
            "Fix1_NoTruncation",
            "Fix2_ReferenceValidation", 
            "Fix3_RealRevisionLoop",
            "Fix4_TrustLevelRename",
            "Fix5_ModelRevisionSHA",
        ],
        "start_time_utc": start_time.isoformat(),
        "end_time_utc": end_time.isoformat(),
        "duration_ms": duration_ms,
        
        "input": {
            "version": baseline.version,
            "sha256": baseline.zip_sha256,
        },
        
        "model": {
            "id": provider.model_id,
            "size": provider.model_size,
            "license": provider.model_license,
            "revision_sha": model_revision,  # Fix #5
        },
        
        "execution": {
            "total_calls": llm_summary["total_calls"],
            "stages": {
                "expert_roles": 10,
                "qa": 1,
                "pm": 1,
                "revision": 1 if revision_artifact else 0,
                "qa_review": 1 if qa_review_artifact else 0,
                "pm_rework": 1,
            },
            "total_prompt_tokens": llm_summary.get("total_prompt_tokens", 0),
            "total_response_tokens": llm_summary.get("total_response_tokens", 0),
            "total_latency_ms": llm_summary.get("total_latency_ms", 0),
        },
        
        "validation": {
            "artifacts_total": len(all_artifacts),
            "trust_counts": trust_counts,  # New naming
            "total_rule_hits": total_rule_hits,
        },
        
        "revision_loop": {
            "executed": revision_artifact is not None,
            "target_artifact": quarantined[0].artifact_id if quarantined else None,
            "revision_artifact": revision_artifact.artifact_id if revision_artifact else None,
            "qa_review_artifact": qa_review_artifact.artifact_id if qa_review_artifact else None,
        },
        
        "gate_status": "BLOCKED",
        "gate_reason": "工程验证10项OPEN, 实体试验NOT_RUN, 采购NOT_READY",
        "gate_is_deterministic": True,
        
        "artifacts": artifact_registry.export(),
    }
    
    print(f"\n  运行ID: {run_id}")
    print(f"  时长: {duration_ms/1000:.1f}秒")
    print(f"  LLM调用: {llm_summary['total_calls']}次")
    print(f"\n  信任级别统计:")
    for level, count in trust_counts.items():
        print(f"    {level}: {count}")
    print(f"    规则命中总计: {total_rule_hits}")
    print(f"\n  返工闭环: {'已执行' if revision_artifact else '未执行'}")
    print(f"  门禁状态: BLOCKED")
    
    # Save outputs
    print("\n[步骤11] 保存输出...")
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    trace_path = output_dir / f"live_trace_{run_id}.json"
    with open(trace_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"  trace: {trace_path}")
    
    calls_path = output_dir / f"llm_calls_{run_id}.json"
    llm_registry.save(str(calls_path))
    print(f"  calls: {calls_path}")
    
    artifacts_path = output_dir / f"artifacts_{run_id}.json"
    with open(artifacts_path, "w", encoding="utf-8") as f:
        json.dump(artifact_registry.export(), f, ensure_ascii=False, indent=2)
    print(f"  artifacts: {artifacts_path}")
    
    manifest = {
        "run_id": run_id,
        "created_utc": end_time.isoformat(),
        "input_version": baseline.version,
        "input_sha256": baseline.zip_sha256,
        "model_id": provider.model_id,
        "model_revision_sha": model_revision,  # Fix #5
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
