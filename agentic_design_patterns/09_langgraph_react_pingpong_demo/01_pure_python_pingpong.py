#!/usr/bin/env python3
"""示例 01：纯 Python 零依赖“打乒乓球”原理版（不依赖任何框架）。

用途：让零编程基础的读者一眼看穿 ReAct 循环底层没有任何黑魔法——
本质上就是一个“白板记录 + 最多 N 步的 while 循环 + 真实工具执行函数”。

运行方式：
    python3 01_pure_python_pingpong.py
"""

from __future__ import annotations

import ast
import operator
from typing import Any

# =============================================================================
# 第 1 部分：工具箱（100% 由人类/代码编写的真实工具，大模型自己无法直接执行）
# =============================================================================

_SAFE_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}


def tool_web_search(query: str) -> str:
    """工具 1：模拟网页搜索（真实项目中这里会调用秘塔 Metaso / Serper / DuckDuckGo API）。"""
    if "30" in query or "柯立芝" in query or "president" in query.lower():
        return (
            "维基百科摘要：卡尔文·柯立芝（Calvin Coolidge）是美国第 30 任总统，"
            "出生于 1872 年 7 月 4 日，逝世于 1933 年 1 月 5 日。"
        )
    return f"未找到与 `{query}` 直接相关的记录。"


def tool_calculator(expression: str) -> str:
    """工具 2：安全四则运算计算器（绝不用危险的 eval，仅允许纯数字与 +-*/）。"""
    node = ast.parse(expression.strip(), mode="eval").body

    def _eval(n: ast.AST) -> float:
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return float(n.value)
        if isinstance(n, ast.BinOp) and type(n.op) in _SAFE_OPS:
            return _SAFE_OPS[type(n.op)](_eval(n.left), _eval(n.right))
        raise ValueError(f"不支持的算式节点：{expression}")

    val = _eval(node)
    return str(int(val)) if val.is_integer() else str(round(val, 4))


# 工具注册表：把“工具名”映射到真正的 Python 函数
TOOL_REGISTRY = {
    "web_search": tool_web_search,
    "calculator": tool_calculator,
}


# =============================================================================
# 第 2 部分：模拟“大模型大脑”（只看白板历史，返回【点菜单】或【最终人话答案】）
# =============================================================================


def fake_llm_brain(whiteboard: list[dict[str, Any]]) -> dict[str, Any]:
    """模拟大模型单次被唤醒时的思考与输出。

    注意：大模型每次被唤醒只做一件事——看白板，然后决定：
      - 情况 A：信息不够 → 开一张 tool_calls 点菜单（不自己执行工具！）
      - 情况 B：信息足够 → 不开点菜单，直接输出最终答案 content
    """
    tool_results = [msg["content"] for msg in whiteboard if msg["role"] == "tool"]

    # 第 1 回合：白板上还没有任何外部事实 → 先点【搜索】
    if len(tool_results) == 0:
        return {
            "role": "assistant",
            "thought": "我不确定第30任总统的准确生卒年，别靠记忆猜，先调搜索工具核实。",
            "content": "",
            "tool_calls": [
                {"name": "web_search", "args": {"query": "美国第30任总统 生卒年"}}
            ],
        }

    # 第 2 回合：看到搜索返回的 1872 与 1933 → 再点【计算器】避免心算出错
    if len(tool_results) == 1:
        return {
            "role": "assistant",
            "thought": "已拿到 1872-07-04 生、1933-01-05 逝，先用计算器算年份差 1933 - 1872，再核对是否满生日。",
            "content": "",
            "tool_calls": [
                {"name": "calculator", "args": {"expression": "1933 - 1872"}}
            ],
        }

    # 第 3 回合：事实与算术都齐了 → 不再发 tool_calls，直接交卷！
    return {
        "role": "assistant",
        "thought": "年份差 61 年，但 1 月 5 日尚未到 7 月 4 日生日，实际享年 60 岁。信息完整，可以交卷！",
        "content": (
            "美国第 30 任总统是卡尔文·柯立芝（Calvin Coolidge），生于 1872 年 7 月 4 日，"
            "逝世于 1933 年 1 月 5 日。年份相减为 61 年，因去世时尚未过当年生日，享年 60 岁。"
        ),
        "tool_calls": [],
    }


# =============================================================================
# 第 3 部分：外层“打乒乓球”循环骨架（纯好硬编码：只管传球 + 步数熔断，不猜语义）
# =============================================================================


def run_pingpong_agent(user_question: str, *, max_steps: int = 5) -> str:
    """极简 15 行乒乓球引擎：大模型 ↔ 真实工具 来回接力，带硬步数上限熔断。"""
    whiteboard: list[dict[str, Any]] = [{"role": "user", "content": user_question}]
    print(f"👤 [用户提问] {user_question}\n" + "=" * 68)

    for step in range(1, max_steps + 1):
        # 1) 唤醒大脑（把白板全部记录交给模型看一次）
        reply = fake_llm_brain(whiteboard)
        whiteboard.append(reply)
        print(f"\n🏓 [第 {step} 回合 · 大脑室] 内部思考：{reply['thought']}")

        # 2) 门卫检查：有没有【点菜单】？没有就直接跳出循环交卷！
        tool_calls = reply.get("tool_calls") or []
        if not tool_calls:
            print("🚪 [门卫判定] 无工具请求 → 跳出循环，呈交最终答案！")
            return str(reply["content"])

        # 3) 工具车间：逐条真正执行点菜单，并把结果（或报错）贴回白板
        for call in tool_calls:
            fn_name = call["name"]
            fn_args = call["args"]
            print(f"🔧 [第 {step} 回合 · 工具车间] 真正执行 `{fn_name}({fn_args})` ...")
            try:
                result = TOOL_REGISTRY[fn_name](**fn_args)
            except Exception as exc:
                # Harness 铁律：工具报错不崩溃，而是把客观报错原文贴回白板让大脑自己修
                result = f"[TOOL_ERROR] {exc}"
            print(f"📋 [写回白板] {result}")
            whiteboard.append({"role": "tool", "name": fn_name, "content": result})

    # 4) 熔断兜底：超过 max_steps 仍未结束，强制刹车，绝不死循环
    return f"⚠️ 已达到最大步数上限（{max_steps} 步），安全熔断停止，请人工介入检查。"


if __name__ == "__main__":
    final_answer = run_pingpong_agent("美国第 30 任总统去世时几岁？", max_steps=5)
    print("\n" + "=" * 68)
    print(f"✅ [最终呈交用户的答案]\n{final_answer}")
