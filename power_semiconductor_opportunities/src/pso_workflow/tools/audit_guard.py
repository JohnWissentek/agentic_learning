"""Red-Zone objective audit guardrails & untrusted data isolation (V4.0).

Pure deterministic functions enforcing:
1. Untrusted external web/search data physical fencing (`[UNTRUSTED_EXTERNAL_DATA_START/END]`).
2. Full-corpus `[EV-CN/GL/GLOBAL-xxx]` citation extraction & Vault membership verification.
3. Deterministic `[ROI-CALC]` consistency verification against Python PALMs ledger.
4. Real track coverage & objective contract compliance (zero tautologies, zero silent swallowing).
"""

from __future__ import annotations

import re
from typing import Any

_START_TAG_RE = re.compile(r"\[UNTRUSTED_EXTERNAL_DATA_START:[^\]]*\]", flags=re.IGNORECASE)
_END_TAG_RE = re.compile(r"\[UNTRUSTED_EXTERNAL_DATA_END\]", flags=re.IGNORECASE)
_CITATION_RE = re.compile(r"\bEV-(?:CN|GL|GLOBAL)-\d{3,4}\b")
# Case-sensitive lowercase `m` so uppercase `3M` (company name) or `10M` (million) is NEVER misparsed as months;
# negative lookbehind skips range upper-bounds (e.g. "10.9–25.3 月", "53.4-61.4 个月") and thresholds ("≤24 个月")
_PAYBACK_NUM_RE = re.compile(
    r"(?<![0-9.\-–—~≤≥<>])(\d+(?:\.\d+)?)\s*(?:个月|月|months?\b|(?<![A-Za-z])m\b)"
)
_TRIPLET_PAYBACK_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)\s*(?:个月|月|m\b)?"
)


def wrap_untrusted_evidence(text: str, *, label: str = "EXTERNAL_WEB_EVIDENCE") -> str:
    """Wrap external untrusted text with explicit physical boundary tags.

    Neutralizes any embedded start/end boundary tags inside the raw text so untrusted
    web content cannot break out of the sandboxed context frame.
    """
    safe_label = re.sub(r"[\]\r\n]+", "_", str(label or "EXTERNAL_WEB_EVIDENCE")).strip() or "EXTERNAL_WEB_EVIDENCE"
    sanitized = _START_TAG_RE.sub("(redacted-untrusted-start-tag)", text or "")
    sanitized = _END_TAG_RE.sub("(redacted-untrusted-end-tag)", sanitized)
    return f"[UNTRUSTED_EXTERNAL_DATA_START: {safe_label}]\n{sanitized}\n[UNTRUSTED_EXTERNAL_DATA_END]"


def extract_citation_ids(texts: list[str]) -> set[str]:
    """Extract all EV-CN-xxx, EV-GL-xxx, and legacy EV-GLOBAL-xxx citation IDs without truncation."""
    found: set[str] = set()
    for t in texts:
        if not t:
            continue
        found.update(_CITATION_RE.findall(t))
    return found


def audit_report_citations(
    *,
    drafts: dict[str, str],
    valid_ev_ids: set[str],
) -> dict[str, Any]:
    """Verify every cited evidence ID across full report drafts exists in EvidenceVault."""
    main_texts = [
        v for k, v in drafts.items()
        if not str(k).startswith("05_")
    ]
    cited = extract_citation_ids(main_texts)
    valid_set = set(valid_ev_ids)
    broken = sorted(eid for eid in cited if eid not in valid_set)
    valid_cited = sorted(eid for eid in cited if eid in valid_set)
    return {
        "cited_ids": sorted(cited),
        "valid_cited_count": len(valid_cited),
        "broken_ids": broken,
        "all_citations_valid": len(broken) == 0,
    }


def audit_roi_consistency(
    *,
    drafts: dict[str, str],
    evaluated_opps: list[dict[str, Any]],
    tolerance_months: float = 0.2,
) -> dict[str, Any]:
    """Verify shortlisted opportunity payback metrics in reports match Python PALMs ledger."""
    if not evaluated_opps:
        return {"roi_consistency_pass": True, "checked_opps": 0, "mismatches": []}

    target_texts = [
        (k, v)
        for k, v in sorted(drafts.items())
        if str(k).startswith(("00_", "03_"))
    ]
    if not target_texts:
        target_texts = [(k, v) for k, v in sorted(drafts.items()) if not str(k).startswith("05_")]

    mismatches: list[dict[str, Any]] = []
    checked = 0

    all_opp_ids = sorted(
        {
            str((item.get("seed") or {}).get("opp_id", "")).strip()
            for item in evaluated_opps
            if str((item.get("seed") or {}).get("opp_id", "")).strip()
        },
        key=len,
        reverse=True,
    )
    any_opp_pattern = (
        re.compile(r"(?<![A-Za-z0-9_-])(?:" + "|".join(re.escape(oid) for oid in all_opp_ids) + r")(?![A-Za-z0-9_-])")
        if all_opp_ids
        else None
    )

    for item in evaluated_opps:
        seed = item.get("seed") or {}
        roi = item.get("roi") or {}
        opp_id = str(seed.get("opp_id", "")).strip()
        if not opp_id or "payback_months" not in roi:
            continue
        expected_base = float(roi["payback_months"])
        rr = item.get("roi_range") or {}
        expected_opt = float((rr.get("optimistic") or {}).get("payback_months", expected_base))
        expected_cons = float((rr.get("conservative") or {}).get("payback_months", expected_base))
        expected_set = (expected_opt, expected_base, expected_cons)

        opp_pattern = re.compile(rf"(?<![A-Za-z0-9_-]){re.escape(opp_id)}(?![A-Za-z0-9_-])")
        for vol_name, content in target_texts:
            for line_no, line in enumerate(content.splitlines(), start=1):
                if not opp_pattern.search(line):
                    continue

                # If multiple opportunities appear on the same prose line, scope parsing
                # strictly to the clause(s) belonging to this opp_id (stopping at the next opp_id,
                # sentence boundary `。`, or Markdown cell separator `|`) so we never cross-attribute
                # another opportunity's payback triplet or portfolio summary range.
                segments: list[str]
                if any_opp_pattern is not None:
                    mentions = list(any_opp_pattern.finditer(line))
                    distinct_ids = {m.group(0) for m in mentions}
                    if len(distinct_ids) > 1:
                        segments = []
                        for idx, m in enumerate(mentions):
                            if m.group(0) != opp_id:
                                continue
                            end_pos = mentions[idx + 1].start() if idx + 1 < len(mentions) else len(line)
                            raw_seg = line[m.start() : end_pos]
                            for sep in ("|", "。"):
                                sep_idx = raw_seg.find(sep)
                                if sep_idx != -1:
                                    raw_seg = raw_seg[:sep_idx]
                            segments.append(raw_seg)
                    else:
                        segments = [line]
                else:
                    segments = [line]

                line_has_roi_context = "[ROI-CALC]" in line or "回收期" in line
                line_matched_exact = False
                pending_line_mismatches: list[dict[str, Any]] = []
                for seg in segments:
                    triplets = _TRIPLET_PAYBACK_RE.findall(seg)
                    if triplets:
                        checked += 1
                        seg_ok = True
                        for t_opt, t_base, t_cons in triplets:
                            if (
                                abs(float(t_opt) - expected_opt) > tolerance_months
                                or abs(float(t_base) - expected_base) > tolerance_months
                                or abs(float(t_cons) - expected_cons) > tolerance_months
                            ):
                                seg_ok = False
                                pending_line_mismatches.append(
                                    {
                                        "opp_id": opp_id,
                                        "volume": vol_name,
                                        "line": line_no,
                                        "expected": f"{expected_opt}/{expected_base}/{expected_cons}",
                                        "reported": f"{t_opt}/{t_base}/{t_cons}",
                                    }
                                )
                        if seg_ok:
                            line_matched_exact = True
                        continue

                    seg_has_roi_tag = "[ROI-CALC]" in seg or "回收期" in seg or line_has_roi_context
                    seg_has_huiben = "回本" in seg
                    if seg_has_roi_tag or seg_has_huiben:
                        # Skip R&D cycle comparisons (e.g. "10个月 vs 24个月") unless explicitly citing [ROI-CALC]/回收期
                        if ("研发" in seg or " vs " in seg.lower()) and "回收期" not in seg and "[ROI-CALC]" not in seg:
                            continue
                        # Skip commercial Spec-in target/ceiling clauses (e.g. "把保守回本压回 48 月内", "压低至 18 个月内回本")
                        # when not an explicit [ROI-CALC] / 回收期 ledger line
                        if not seg_has_roi_tag and any(
                            kw in seg for kw in ("压回", "压低", "压减", "月内", "以内", "目标", "跑通")
                        ):
                            continue
                        nums = _PAYBACK_NUM_RE.findall(seg)
                        if not nums:
                            continue
                        checked += 1
                        reported_vals = [float(n) for n in nums]
                        has_match = any(
                            any(abs(val - exp) <= tolerance_months for exp in expected_set)
                            for val in reported_vals
                        )
                        if has_match:
                            line_matched_exact = True
                        else:
                            pending_line_mismatches.append(
                                {
                                    "opp_id": opp_id,
                                    "volume": vol_name,
                                    "line": line_no,
                                    "expected": expected_base,
                                    "reported": reported_vals,
                                }
                            )
                if pending_line_mismatches and not line_matched_exact:
                    mismatches.extend(pending_line_mismatches)

    return {
        "roi_consistency_pass": len(mismatches) == 0,
        "checked_opps": checked,
        "mismatches": mismatches,
    }


def run_full_objective_audit(
    *,
    vault_stats: dict[str, Any],
    valid_ev_ids: set[str],
    drafts: dict[str, str],
    evaluated_opps: list[dict[str, Any]],
    contract: dict[str, Any],
    target_tracks: int | None = None,
    expected_volumes: int = 5,
) -> dict[str, Any]:
    """Execute 100% objective full-corpus audit with zero truncation and zero tautologies."""
    gates = (contract or {}).get("quality_gates", {}) or {}
    min_ev = int(gates.get("min_total_evidences", 48))
    min_cn_ratio = float(gates.get("min_china_evidence_ratio", 0.45))
    expected_tracks = (
        int(target_tracks)
        if target_tracks is not None
        else int(gates.get("min_tracks_covered", 8))
    )

    by_track = vault_stats.get("by_track", {}) or {}
    research_tracks = {k for k in by_track if k != "RECON"}
    tracks_covered = len(research_tracks)
    tracks_covered_pass = tracks_covered >= expected_tracks

    effective_min_ev = min_ev if expected_tracks >= 6 else max(16, min_ev // 2)
    total_evidences_pass = int(vault_stats.get("total", 0)) >= effective_min_ev
    china_ratio_pass = float(vault_stats.get("cn_ratio", 0.0)) >= min_cn_ratio

    main_texts = [
        v for k, v in sorted(drafts.items())
        if str(k).startswith(("00_", "01_", "02_", "03_", "04_"))
    ]
    all_volumes_non_empty = len(main_texts) == expected_volumes and all(len(t) > 500 for t in main_texts)

    cite_audit = audit_report_citations(drafts=drafts, valid_ev_ids=valid_ev_ids)
    roi_audit = audit_roi_consistency(drafts=drafts, evaluated_opps=evaluated_opps)
    roi_tags = sum(t.count("[ROI-CALC]") for t in main_texts)

    hard_failures: list[str] = []
    if not total_evidences_pass:
        hard_failures.append(
            f"证据总量不足: {vault_stats.get('total', 0)} < {effective_min_ev}"
        )
    if not china_ratio_pass:
        hard_failures.append(
            f"中国信源占比不足: {vault_stats.get('cn_ratio', 0.0):.2%} < {min_cn_ratio:.2%}"
        )
    if not tracks_covered_pass:
        hard_failures.append(
            f"动态赛道覆盖不足(不含RECON): 实际 {tracks_covered} 条 < 目标 {expected_tracks} 条"
        )
    if not all_volumes_non_empty:
        hard_failures.append(
            f"报告分卷不完整或过短: 实际非空主卷数 {len(main_texts)} / 期望 {expected_volumes}"
        )
    if not cite_audit["all_citations_valid"]:
        hard_failures.append(
            f"存在未入库/伪造引用编号: {', '.join(cite_audit['broken_ids'])}"
        )
    if not roi_audit["roi_consistency_pass"]:
        hard_failures.append(
            f"存在 [ROI-CALC] 财务数字漂移/篡改: {roi_audit['mismatches'][:5]}"
        )

    return {
        "passed": len(hard_failures) == 0,
        "hard_failures": hard_failures,
        "total_evidences_pass": total_evidences_pass,
        "china_ratio_pass": china_ratio_pass,
        "tracks_covered": tracks_covered,
        "expected_tracks": expected_tracks,
        "tracks_covered_pass": tracks_covered_pass,
        "opportunities_ranked_count": len(evaluated_opps),
        "citations_used_count": cite_audit["valid_cited_count"],
        "broken_citation_ids": cite_audit["broken_ids"],
        "all_citations_valid": cite_audit["all_citations_valid"],
        "roi_calc_tags_count": roi_tags,
        "roi_consistency_pass": roi_audit["roi_consistency_pass"],
        "roi_mismatches": roi_audit["mismatches"],
        "all_5_volumes_non_empty": all_volumes_non_empty,
    }
