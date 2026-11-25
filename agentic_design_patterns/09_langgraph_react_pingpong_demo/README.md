# LangGraph “打乒乓球” ReAct 循环实战示例包

本目录是 [09_LangChain与LangGraph打乒乓球循环原理解析与逐行对照.md](../09_LangChain与LangGraph打乒乓球循环原理解析与逐行对照.md) 的配套代码与逐行伪代码目录，零编程基础也可直接运行并亲眼看到每一拍的真实流转轨迹。

## 目录内容

1. [01_pure_python_pingpong.py](./01_pure_python_pingpong.py) — **纯 Python 零依赖原理版**（约 140 行含详尽中文注释），证明 ReAct 循环底层没有任何黑魔法。
2. [02_langgraph_react_pingpong.py](./02_langgraph_react_pingpong.py) — **标准 LangChain + LangGraph 状态机版**（严格对照《Learning LangChain》P167–170，外加安全计算器、步数上限熔断与检查点存盘；支持离线 `--mock` 零费用运行与 `--live` 真实模型运行）。
3. [03_pseudocode_line_by_line.md](./03_pseudocode_line_by_line.md) — **逐行白话伪代码对照手册**，把两份代码拆成逐行大白话与职责归属表。

## 10 秒快速试跑

```bash
cd /Users/john/Desktop/agentic_learning/agentic_design_patterns/09_langgraph_react_pingpong_demo

# 1. 运行纯 Python 原理版（系统自带 python3 即可，零依赖）
python3 01_pure_python_pingpong.py

# 2. 运行 LangGraph 标准版（离线 --mock 模式，无需任何 API Key，直接看真实 LangGraph 节点流转）
/Users/john/Desktop/agentic_learning/power_semiconductor_opportunities/.venv/bin/python \
    02_langgraph_react_pingpong.py --mock
```
