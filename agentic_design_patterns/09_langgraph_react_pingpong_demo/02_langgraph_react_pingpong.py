#!/usr/bin/env python3
"""示例 02：标准 LangChain + LangGraph “打乒乓球” ReAct 状态机完整示例。

严格对照《Learning LangChain》(O'Reilly) 第 6 章（P167–170）经典结构，并加上
Harness Engineering 必备的“安全计算器 + 步数上限熔断 (max_steps) + 内存检查点”。

支持两种运行方式：
1. 离线零成本演示模式（默认，无需任何 API Key，直接观察真实 LangGraph 节点流转）：
       /Users/john/Desktop/agentic_learning/power_semiconductor_opportunities/.venv/bin/python \
           02_langgraph_react_pingpong.py --mock

2. 接入真实大模型模式（需配置 OPENAI_API_KEY 或 DashScope 兼容接口）：
       /Users/john/Desktop/agentic_learning/power_semiconductor_opportunities/.venv/bin/python \
           02_langgraph_react_pingpong.py --live
"""

from __future__ import annotations

import argparse
import ast
import operator
import os
from typing import Annotated, Literal, TypedDict

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

# =============================================================================
# 第 1 步（LangChain 负责）：用 @tool 把普通 Python 函数包装成大模型看得懂的“标准菜单”
# =============================================================================

_SAFE_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}


@tool
def web_search(query: str) -> str:
    """查询历史人物、公开事实与时间信息。输入为简明的中文或英文检索词。"""
    # 为确保离线可直接运行且结果确定，这里内置演示知识片段；
    # 生产环境只需替换为 DuckDuckGo / Metaso / Serper API 调用即可。
    if "30" in query or "柯立芝" in query or "president" in query.lower():
        return (
            "卡尔文·柯立芝（Calvin Coolidge），美国第 30 任总统，"
            "1872年7月4日出生，1933年1月5日逝世。"
        )
    return f"未检索到与 `{query}` 相关的条目。"


@tool
def calculator(expression: str) -> str:
    """执行精确四则运算（支持 + - * /）。输入必须是纯数学表达式，如 '1933 - 1872'。"""
    node = ast.parse(expression.strip(), mode="eval").body

    def _eval(n: ast.AST) -> float:
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return float(n.value)
        if isinstance(n, ast.BinOp) and type(n.op) in _SAFE_OPS:
            return _SAFE_OPS[type(n.op)](_eval(n.left), _eval(n.right))
        raise ValueError(f"非法数学表达式：{expression}")

    val = _eval(node)
    return str(int(val)) if val.is_integer() else str(round(val, 4))


TOOLS = [web_search, calculator]


# =============================================================================
# 第 2 步：定义“共享白板”与“大脑模型”（支持 --mock 离线模拟 / --live 真模型）
# =============================================================================


class AgentState(TypedDict):
    """LangGraph 全局状态（挂在墙上的共享白板）。

    `Annotated[list[AnyMessage], add_messages]` 的含义：
    每次有节点返回新消息时，不是覆盖旧记录，而是按顺序【追加】到白板末尾。
    """

    messages: Annotated[list[AnyMessage], add_messages]
    step_count: int  # Harness 计步器：记录大脑被唤醒了几轮，用于强制熔断


class MockPingPongModel:
    """离线模拟已绑定工具菜单的大模型（无需 API Key，完整演示真实 AIMessage(tool_calls=...)）。"""

    def invoke(self, messages: list[AnyMessage]) -> AIMessage:
        tool_msgs = [m for m in messages if isinstance(m, ToolMessage)]

        if len(tool_msgs) == 0:
            # 第 1 拍：发出标准工具调用请求（点菜单）
            return AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "call_step_1_search",
                        "name": "web_search",
                        "args": {"query": "美国第30任总统 出生与去世日期"},
                        "type": "tool_call",
                    }
                ],
            )

        if len(tool_msgs) == 1:
            # 第 2 拍：看到搜索结果后，决定再点计算器核实年份差
            return AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "call_step_2_calc",
                        "name": "calculator",
                        "args": {"expression": "1933 - 1872"},
                        "type": "tool_call",
                    }
                ],
            )

        # 第 3 拍：所有外部事实与计算齐全 → 不再附带 tool_calls，输出最终答复
        return AIMessage(
            content=(
                "美国第 30 任总统是卡尔文·柯立芝（Calvin Coolidge），"
                "生于 1872 年 7 月 4 日，逝世于 1933 年 1 月 5 日。"
                "年份差为 61 年，因去世时还未到当年的 7 月 4 日生日，因此享年 60 岁。"
            )
        )


def _build_llm(live: bool):
    if not live:
        return MockPingPongModel()
    from langchain_openai import ChatOpenAI

    # LangChain 核心一步：bind_tools(TOOLS) 把工具说明书打包塞进大模型菜单
    return ChatOpenAI(
        model=os.getenv("DEMO_LLM_MODEL", "gpt-4o-mini"),
        temperature=0.0,
    ).bind_tools(TOOLS)


# =============================================================================
# 第 3 步（LangGraph 负责）：盖两个房间 + 放一个门卫 + 拉一条回头线 + 装熔断器
# =============================================================================


def build_pingpong_graph(*, live: bool = False, max_steps: int = 5):
    llm = _build_llm(live=live)

    # 房间 A：大脑室（把白板全部记录递给大模型，步数 +1）
    def model_node(state: AgentState) -> dict:
        ai_reply = llm.invoke(state["messages"])
        return {
            "messages": [ai_reply],
            "step_count": state.get("step_count", 0) + 1,
        }

    # 门卫函数（等价于内置 tools_condition + Harness 步数上限熔断）
    def gatekeeper(state: AgentState) -> Literal["tools", "__end__"]:
        last_msg = state["messages"][-1]
        has_tool_calls = isinstance(last_msg, AIMessage) and bool(last_msg.tool_calls)
        if has_tool_calls and state.get("step_count", 0) < max_steps:
            return "tools"  # 有点菜单且未撞上限 → 放进工具车间
        return END          # 无点菜单或已达步数天花板 → 直接出门交卷

    # 房间 B：LangGraph 内置自动工具车间（自动按点菜单找函数执行，报错自动包装成 ToolMessage）
    tool_workshop = ToolNode(TOOLS)

    # ---- 核心 6 行搭台代码（与《Learning LangChain》P167 完全一致）----
    builder = StateGraph(AgentState)
    builder.add_node("model", model_node)                  # 1. 盖房间 A：大脑室
    builder.add_node("tools", tool_workshop)               # 2. 盖房间 B：工具车间
    builder.add_edge(START, "model")                       # 3. 进门先去大脑室
    builder.add_conditional_edges(                         # 4. 大脑室门口放门卫
        "model",
        gatekeeper,
        {"tools": "tools", END: END},
    )
    builder.add_edge("tools", "model")                     # 5. 回头线：车间干完自动回大脑室

    # 6. 编译成可运行图，并挂载内存检查点（Checkpointer：每步自动存盘，支撑暂停/回滚）
    return builder.compile(checkpointer=MemorySaver())


# =============================================================================
# 第 4 步：流式运行，实时打印每一拍“打乒乓球”的完整轨迹
# =============================================================================


def main() -> None:
    parser = argparse.ArgumentParser(description="LangGraph ReAct 打乒乓球可视化演示")
    parser.add_argument("--live", action="store_true", help="使用真实 LLM API（默认离线 --mock 演示）")
    parser.add_argument("--max-steps", type=int, default=5, help="Harness 最大回合步数上限")
    parser.add_argument("--question", default="美国第 30 任总统去世时几岁？", help="测试问题")
    args = parser.parse_args()

    graph = build_pingpong_graph(live=args.live, max_steps=args.max_steps)
    mode_label = "真实模型模式 (--live)" if args.live else "离线模拟模式 (--mock，零费用)"
    print(f"🚀 启动 LangGraph ReAct 演示 | {mode_label} | 熔断上限={args.max_steps} 步")
    print(f"👤 [用户提问] {args.question}\n" + "=" * 72)

    config = {"configurable": {"thread_id": "demo-pingpong-001"}, "recursion_limit": args.max_steps * 2 + 2}
    initial_input = {"messages": [HumanMessage(content=args.question)], "step_count": 0}

    for event in graph.stream(initial_input, config=config, stream_mode="updates"):
        for node_name, update in event.items():
            if node_name == "model":
                step_no = update.get("step_count", "?")
                msg: AIMessage = update["messages"][-1]
                if msg.tool_calls:
                    if isinstance(step_no, int) and step_no >= args.max_steps:
                        print(f"\n🧠 [节点: model | 第 {step_no} 轮] 大脑仍想调工具，但已触及熔断上限 ({args.max_steps} 步)：")
                        for tc in msg.tool_calls:
                            print(f"    • 被拦截的工具请求={tc['name']} | 参数={tc['args']}")
                        print("🛑 [门卫熔断] 触发 Harness 步数天花板 → 强制放行至 END 安全停机（绝不死循环）！")
                    else:
                        print(f"\n🧠 [节点: model | 第 {step_no} 轮] 大脑开出【点菜单】→ 交由门卫放行至 tools：")
                        for tc in msg.tool_calls:
                            print(f"    • 工具={tc['name']} | 参数={tc['args']} | id={tc['id']}")
                else:
                    print(f"\n🧠 [节点: model | 第 {step_no} 轮] 大脑未开点菜单 → 门卫放行至 END 交卷！")
                    print("=" * 72)
                    print(f"✅ [最终呈交用户的答案]\n{msg.content}")
            elif node_name == "tools":
                for tmsg in update["messages"]:
                    print(f"🔧 [节点: tools] 真实工具 `{tmsg.name}` 执行完毕，结果贴回白板并沿回头线送回 model：")
                    print(f"    • 返回内容：{tmsg.content}")


if __name__ == "__main__":
    main()
