#!/usr/bin/env python3
"""
溯源对账脚本:检查 ARCHITECTURE.md 中声明的模块调用关系是否与真实代码 1:1 一致。

用途(对应框架总纲 00 第 2.1 节"逆向自动对账"):
    图上声明的依赖(模块结构图中的箭头) vs 代码中真实的 import 关系,
    两边做 diff,任何"图上有代码没有"或"代码有图上没有"都报告并以退出码 1 失败。

用法:
    python tools/check_traceability.py                 # 默认:项目根目录运行
    python tools/check_traceability.py --root /path/to/project
    pytest tests/unit/test_traceability.py             # 纳入测试门禁

原理:
    1. 解析 docs/ARCHITECTURE.md 中的 mermaid 代码块,提取形如
       `main[main.py<br/>...] --> svc[services/sync_service.py<br/>...]` 的边,
       两端标签含 .py 文件名的边视为"声明的模块依赖"。
    2. 用 ast 遍历 src/ 下所有 .py 文件,提取项目内部模块之间的真实 import 边。
    3. 集合 diff,输出报告。

仅用标准库(总纲 4.7 技术选型红线)。
函数级调用图对账为 TODO 扩展点,见文件末尾说明。
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

MERMAID_BLOCK_RE = re.compile(r"```mermaid\s*\n(.*?)```", re.DOTALL)
# 匹配一条边:  nodeA[label] --> nodeB[label]   (label 可省略)
EDGE_RE = re.compile(
    r"(?P<src>\w+)\s*(?:\[(?P<src_label>[^\]]*)\])?\s*"
    r"-{1,3}>+\s*"
    r"(?:\|[^|]*\|\s*)?"
    r"(?P<dst>\w+)\s*(?:\[(?P<dst_label>[^\]]*)\])?"
)
PYFILE_IN_LABEL_RE = re.compile(r"(\S+\.py)")


# ---------------------------------------------------------------------------
# 第 1 步:从 ARCHITECTURE.md 提取"声明的模块依赖边"
# ---------------------------------------------------------------------------

def parse_declared_edges(arch_md: Path) -> set[tuple[str, str]]:
    """返回声明边集合 {(caller_module, callee_module)},模块名 = 去掉 .py 的文件名。"""
    text = arch_md.read_text(encoding="utf-8")
    node_labels: dict[str, str] = {}  # node_id -> module name
    edges_raw: list[tuple[str, str]] = []

    for block in MERMAID_BLOCK_RE.findall(text):
        for m in EDGE_RE.finditer(block):
            for node_key, label_key in (("src", "src_label"), ("dst", "dst_label")):
                node_id = m.group(node_key)
                label = _strip_label_quotes(m.group(label_key) or "")
                py_matches = PYFILE_IN_LABEL_RE.findall(label)
                # 只有恰好一个 .py 文件名才登记为"真实模块节点"；0 个(无.py)或
                # ≥2 个(黑盒/汇总节点,合并了多个文件名)都不登记,其边不参与对账——
                # 避免总图里的黑盒节点(框架总纲 3.3)把多个模块误配对成一个假模块。
                if len(py_matches) == 1:
                    node_labels[node_id] = _module_name(py_matches[0])
            edges_raw.append((m.group("src"), m.group("dst")))

    declared = set()
    for src_id, dst_id in edges_raw:
        # 只保留两端都解析为 .py 模块的边(排除 API/DB/日志等外部节点)
        if src_id in node_labels and dst_id in node_labels:
            declared.add((node_labels[src_id], node_labels[dst_id]))
    return declared


def _strip_label_quotes(label: str) -> str:
    """去掉 mermaid 节点标签两端的引号/括号包裹(如 `["main.py<br/>入口"]` 的 `"..."`，
    或圆柱形节点 `[("db.py")]` 的 `("...")`）。

    正则只按最外层 `[...]` 取内容，标签内层的引号/括号会原样留在字符串里；若不去掉，
    会被 PYFILE_IN_LABEL_RE 误吞进模块名(如 '("main' 而非 'main')，导致真实模块被
    误判为"图上未声明"。反复剥掉最多两层包裹（引号、圆柱括号）以兼容两种写法。
    """
    label = label.strip()
    for _ in range(2):
        if len(label) >= 2 and label[0] == '"' and label[-1] == '"':
            label = label[1:-1].strip()
        elif len(label) >= 2 and label[0] == "(" and label[-1] == ")":
            label = label[1:-1].strip()
    return label


def _module_name(py_path: str) -> str:
    """'services/sync_service.py' -> 'sync_service';'main.py' -> 'main'"""
    return Path(py_path).stem


# ---------------------------------------------------------------------------
# 第 2 步:从真实代码提取 import 边
# ---------------------------------------------------------------------------

def parse_actual_edges(src_dir: Path) -> tuple[set[tuple[str, str]], list[str]]:
    """遍历 src/ 下所有 .py,返回 (真实 import 边集合, 跨模块私有导入违规清单)。"""
    py_files = [p for p in src_dir.rglob("*.py") if p.name != "__init__.py"]
    project_modules = {p.stem for p in py_files}

    actual: set[tuple[str, str]] = set()
    private_violations: list[str] = []
    for py in py_files:
        caller = py.stem
        try:
            tree = ast.parse(py.read_text(encoding="utf-8"))
        except SyntaxError as e:
            print(f"[WARN] 语法错误,跳过 {py}: {e}", file=sys.stderr)
            continue
        for node in ast.walk(tree):
            targets: list[str] = []
            if isinstance(node, ast.Import):
                targets = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                # from package.module import x → module 部分
                # from .module import x     → node.module 即模块名
                # from package import module → 被导入的 name 本身是模块
                if node.module:
                    targets.append(node.module)
                targets.extend(alias.name for alias in node.names)
                # 接口最小暴露检查(00 总纲 4.9 硬指标3):
                # 跨模块导入 _ 私有名(如 from x import _helper)即违规
                source_module = (node.module or "").split(".")[-1]
                if source_module in project_modules and source_module != caller:
                    for alias in node.names:
                        if alias.name.startswith("_"):
                            private_violations.append(
                                f"{caller} 导入了 {source_module} 的私有实现 {alias.name}"
                            )
            for t in targets:
                for seg in t.split("."):
                    if seg in project_modules and seg != caller:
                        actual.add((caller, seg))
    return actual, private_violations


def find_cycle(edges: set[tuple[str, str]]) -> list[str] | None:
    """依赖单向无环检查(00 总纲 4.9 硬指标2):返回环路径如 ['a','b','a'],无环返回 None。"""
    graph: dict[str, list[str]] = {}
    for a, b in edges:
        graph.setdefault(a, []).append(b)

    unvisited, visiting, finished = 0, 1, 2
    state = {node: unvisited for node in graph}
    path: list[str] = []

    def walk_from(node: str) -> list[str] | None:
        state[node] = visiting
        path.append(node)
        for next_node in graph.get(node, []):
            if state.get(next_node, unvisited) == visiting:
                return path[path.index(next_node):] + [next_node]
            if state.get(next_node, unvisited) == unvisited:
                found_cycle = walk_from(next_node)
                if found_cycle:
                    return found_cycle
        state[node] = finished
        path.pop()
        return None

    for start_node in list(graph):
        if state[start_node] == unvisited:
            cycle = walk_from(start_node)
            if cycle:
                return cycle
    return None


# ---------------------------------------------------------------------------
# 第 3 步:diff 与报告
# ---------------------------------------------------------------------------

def run_check(root: Path) -> int:
    arch_md = root / "docs" / "ARCHITECTURE.md"
    src_dir = root / "src"

    if not arch_md.exists():
        print(f"[FAIL] 找不到 {arch_md} —— 先建立架构文档再对账。")
        return 1
    if not src_dir.exists():
        print(f"[FAIL] 找不到 {src_dir}")
        return 1

    actual, private_violations = parse_actual_edges(src_dir)

    # --- 第一部分:代码卫生检查(00 总纲 4.9,不依赖图,模板示例期也执行) ---
    hygiene_ok = True
    cycle = find_cycle(actual)
    if cycle:
        hygiene_ok = False
        print(f"❌ 检测到模块循环依赖(00 总纲 4.9 禁止): {' → '.join(cycle)}")
        print("   处理:打破环——把公共部分下沉为新模块,或用依赖注入反转方向。")
    if private_violations:
        hygiene_ok = False
        print(f"❌ 跨模块调用私有实现({len(private_violations)} 处,00 总纲 4.9 接口最小暴露):")
        for v in private_violations:
            print(f"   {v}")
        print("   处理:改为调用该模块的公开接口,"
              "或把该私有函数升级为公开接口(去掉 _ 前缀并补伪代码)。")
    if not hygiene_ok:
        return 1

    # --- 第二部分:图-代码对账(模板示例期跳过) ---
    if "TEMPLATE-EXAMPLE-CONTENT" in arch_md.read_text(encoding="utf-8"):
        print("[SKIP] ARCHITECTURE.md 仍为模板示例(含 TEMPLATE-EXAMPLE-CONTENT 标记)。"
              "替换为本项目真实的图并删除标记后,对账门禁生效。(代码卫生检查已执行:无环/无私有越界)")
        return 0

    declared = parse_declared_edges(arch_md)

    declared_cycle = find_cycle(declared)
    if declared_cycle:
        print(f"❌ 架构图本身画出了循环依赖: {' → '.join(declared_cycle)} —— 先修设计,再谈实现。")
        return 1

    if not declared:
        print("[FAIL] ARCHITECTURE.md 中未解析到任何模块依赖边。"
              "检查模块结构图节点标签是否包含 .py 文件名(如 main[main.py<br/>入口])。")
        return 1

    missing = declared - actual   # 图上声明了,代码里没有
    extra = actual - declared     # 代码里存在,图上没画

    print(f"声明边 {len(declared)} 条,真实边 {len(actual)} 条。")
    ok = True
    if missing:
        ok = False
        print(f"\n❌ 图上声明但代码中不存在的依赖({len(missing)} 条)——设计未实现或图过时:")
        for a, b in sorted(missing):
            print(f"   {a} --> {b}")
    if extra:
        ok = False
        print(f"\n❌ 代码中存在但图上未声明的依赖({len(extra)} 条)——实现漂移,先补图再合码:")
        for a, b in sorted(extra):
            print(f"   {a} --> {b}")
    if ok:
        print("✅ 图-代码模块依赖 1:1 对齐。")
        return 0
    print("\n处理原则(00 总纲):先改设计文档并经人审核,再改代码;图与代码不一致是最高优先级缺陷。")
    return 1


def main() -> None:
    parser = argparse.ArgumentParser(description="图-代码溯源对账")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent,
                        help="项目根目录(默认:本脚本所在 tools/ 的上一级)")
    args = parser.parse_args()
    sys.exit(run_check(args.root))


if __name__ == "__main__":
    main()


# ---------------------------------------------------------------------------
# TODO 扩展点(按需实现):
# 1. 函数级调用图对账:解析"函数调用关系图"中的 `模块.函数()` 节点,
#    用 ast.Call 提取真实调用链比对。
# 2. 参数传递路径对账:比对函数签名(ast.FunctionDef.args)与参数路径图声明。
# 3. Canvas 对账:docs/canvas/*.canvas 是 JSON,解析 nodes/edges 与 Mermaid 源比对,
#    保证"人审视图"与"机器图源"一致。
# ---------------------------------------------------------------------------
