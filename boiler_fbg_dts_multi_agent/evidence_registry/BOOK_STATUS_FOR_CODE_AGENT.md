# 已核实书籍，可供代码流立即复用
仓库原文路径：agentic_design_patterns/Agentic_Design_Patterns_full.md
本机完整文献：/workspace/boiler-product/research/sources/Agentic_Design_Patterns_full.md
关键章节摘录：/workspace/boiler-product/research/sources/book_key_sections.md
书名 Agentic Design Patterns: A Hands-On Guide to Building Intelligent Systems，Antonio Gullí。出版社 Springer，2025第一版，DOI https://doi.org/10.1007/978-3-032-01402-3；作者为Google CTO办公室高级主管，不等于Google官方出版。仓库为482页PDF转Markdown、标preprint的文献，非正式版同页码。仓库目录未发现其所指相邻PDF。
已读 Ch7 Multi-Agent Collaboration（仓库PDF页113起；正式版97–113）、Ch13 Human-in-the-Loop（仓库PDF204起；正式版183–191）、Ch18 Guardrails（仓库286起；正式版265–284）、Ch19 Evaluation（仓库306起）；以及Ch3/4。
框架：原文及出版社明确覆盖LangChain/LangGraph、CrewAI、Google ADK，书籍并未要求只用ADK。建议可恢复状态图/有向工作流 + 专家模型节点并行 + 独立证据评审 + 人工采购/现场放行。首选LangGraph显式state/checkpoint（具体API请代码流独立核实当前文档），ADK的SequentialAgent/ParallelAgent/LoopAgent为备选，CrewAI角色编排为第三方案。
注意模型运行必须保留模型名/版本、调用时间、输入输出/工具/费用、失败重试和证据引用；纯确定性角色脚本不冒充真实模型智能体；仿真不冒充实物。用户尚未批准任何采购或厂商联系。


## v0.2证据更新（代码流必须复用）
书籍核实结论不变。交付版本元数据见research/DELIVERY_VERSION.json。硬件不再选定T885/T890：搜索参数UNVERIFIED，原厂PDF未得；实验室仅FiSens1550完整AC家族RFI优先；现场高温阵列NOT_SELECTED，采购NOT_READY。证据账本仍为数组schema，E08/E12已修订，新增E17–E22。不得把v0.1原提示里的Technica组合继续写成已选定/可采购。U5.728为扩展U(k=2)，判据为|e|+U≤MPE，不是实际偏差；实际链路余量UNKNOWN。
