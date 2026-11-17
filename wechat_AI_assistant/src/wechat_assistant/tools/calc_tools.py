"""Group 2 Deterministic Calculation Tools: Excel quote row-level diff & tax math."""

from __future__ import annotations

from typing import Any


def _to_float(val: Any) -> float | None:
    if isinstance(val, (int, float)) and not isinstance(val, bool):
        return float(val)
    if isinstance(val, str):
        cleaned = val.replace(",", "").replace("¥", "").replace("$", "").strip()
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def analyze_excel_quote(
    old_rows: list[dict[str, Any]],
    new_rows: list[dict[str, Any]],
    *,
    key_col: str | None = None,
    amount_col: str | None = None,
) -> dict[str, Any]:
    """Perform exact row-by-row diff and numeric total audit between two quote tables."""
    if not old_rows and not new_rows:
        return {"added": [], "removed": [], "changed": [], "old_total": 0.0, "new_total": 0.0, "total_delta": 0.0}

    sample = new_rows[0] if new_rows else old_rows[0]
    cols = [c for c in sample.keys() if c != "_row_num"]
    if key_col is None:
        key_col = next((c for c in cols if any(k in c for k in ("名称", "物料", "型号", "项目", "Item", "Name"))), cols[0])
    if amount_col is None:
        amount_col = next((c for c in cols if any(k in c for k in ("小计", "总价", "金额", "合计", "Amount", "Total"))), "")

    old_map = {str(r.get(key_col, f"row_{i}")).strip(): r for i, r in enumerate(old_rows, 1)}
    new_map = {str(r.get(key_col, f"row_{i}")).strip(): r for i, r in enumerate(new_rows, 1)}

    added = [new_map[k] for k in new_map if k not in old_map]
    removed = [old_map[k] for k in old_map if k not in new_map]
    changed: list[dict[str, Any]] = []

    for k in new_map:
        if k not in old_map:
            continue
        r_old, r_new = old_map[k], new_map[k]
        diffs: list[dict[str, Any]] = []
        for col in set(r_old.keys()) | set(r_new.keys()):
            if col == "_row_num":
                continue
            v_old, v_new = r_old.get(col), r_new.get(col)
            if v_old != v_new:
                f_old, f_new = _to_float(v_old), _to_float(v_new)
                entry: dict[str, Any] = {"field": col, "old": v_old, "new": v_new}
                if f_old is not None and f_new is not None:
                    entry["delta"] = round(f_new - f_old, 4)
                    if f_old != 0:
                        entry["pct_change"] = round(((f_new - f_old) / f_old) * 100.0, 2)
                diffs.append(entry)
        if diffs:
            changed.append({"key": k, "row_num": r_new.get("_row_num"), "diffs": diffs})

    old_total = sum((_to_float(r.get(amount_col)) or 0.0) for r in old_rows) if amount_col else 0.0
    new_total = sum((_to_float(r.get(amount_col)) or 0.0) for r in new_rows) if amount_col else 0.0
    return {
        "key_col": key_col,
        "amount_col": amount_col,
        "added": added,
        "removed": removed,
        "changed": changed,
        "old_total": round(old_total, 2),
        "new_total": round(new_total, 2),
        "total_delta": round(new_total - old_total, 2),
    }
