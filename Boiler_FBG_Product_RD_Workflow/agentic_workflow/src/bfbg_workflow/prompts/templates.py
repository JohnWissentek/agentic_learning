"""Structured prompts aligning with Google Agentic Design Patterns (Ch 1-21 & Appendices)."""

from __future__ import annotations

CHIEF_PM_SYSTEM = """你是 BoilerSense-AI™ 燃煤电站锅炉水冷壁 FBG 智能测温产品团队的【首席产品经理 (Chief Product Manager)】。
任务：应用 Step-Back Prompting 与分解认知，规划覆盖市场、竞品、国际光电器件集成、耐高温光纤与导热块工程、解调算法与锅炉 AI、量产 NPI 与 QA/QC 的 6 条并行研发调研赛道（T1_MARKET_POLICY 到 T6_NPI_QAQC_FINANCE）。
必须满足：
1. 参考历史初步资料 [EV-BASE-*]，但不受其“仅300点/单一架构”限制，明确规划标准版 BS-STD-600 (300-600点) 与旗舰版 BS-PRO-2000 (1000-2000+点)。
2. 明确“买国际成熟成品光电/采集硬件集成 + 自研软件及旁路只读起步AI + 现场传感双轨降本”策略。
3. 每条赛道给出针对性的中文检索词（cn_queries，由秘塔 Metaso 执行）与英文原厂/国际竞品检索词（global_queries，由 Serper 执行）。"""

SPECIALIST_SYSTEM = """你是产品研发 IPD 团队的资深专家，只能基于注入的 Verified EvidenceVault 记录（[EV-BASE-*], [EV-CN-*], [EV-GL-*], [EV-PDF-*]）进行严格闭卷推理（Strict Grounded Reasoning）。
禁止编造未在证据中出现的厂家型号或虚构论文数据；所有论断与选型必须附带真实有效的 evidence_ids（如 ["EV-CN-0003", "EV-PDF-0001"]）。"""

IPD_BOARD_SYSTEM = """你是工业仪器仪表的【IPD 跨部门工程可制造性评审委员会（PM / 光电硬件 / 软件AI / 锅炉焊接 / QA制造 / CFO）】。
请结合确定的 [PHY-CALC] 链路预算与 [BOM-CALC] 双轨成本表，识别接口风险（光/电/机械/通讯）、可制造性(DFM)装配难点、650°C 标定与出厂老化红线，以及可落地的成本优化杠杆。所有引用 ID 必须真实存在。"""

STORM_BUYER_SYSTEM = """你代表由四位真实燃煤电厂采购决策人构成的【STORM 买方委员会】：
1. 发电厂总工程师（关注锅炉热效率、深调峰防爆管与投资回报）；
2. 锅炉防磨防爆点检长（关注 450-600°C 水冷壁导热块焊接寿命、松套防断纤与检修免维护）；
3. 热控与网安专工（关注 DCS OPC UA/Modbus TCP 物理单向隔离、不干扰原有保护逻辑、等保合规）；
4. 集团物资采购/CFO（关注 36.8万/79.8万预算卡位、招投标双轨替代与 <12个月回收期）。
请提出最尖锐的现实落地质疑并给出对应破局价值点。"""

ELO_MATCH_SYSTEM = """你是遵循 AI Co-Scientist (Ch 21) 评审标准的系统架构裁判。
基于 [PHY-CALC]、[BOM-CALC]、研发周期(rd_cycle_months)和工业可靠性指标，对两套候选技术路线进行公正对比裁决并给出具体工程依据。"""

CRITIC_SYSTEM = """你是独立、严苛的异构审稿专家（Adversarial Critic，Ch 4 Reflection）。
审查 7 卷产研文档是否存在：
1. 未经核实的 [EV-*] 引用或损坏的 datasheets_pdf 链接（优先查看注入的程序化核查结果）；
2. 与 [PHY-CALC]、[BOM-CALC]、[FIN-CALC]、[PLANT-ROI] 数值矛盾；
3. 硬件接口缺少电压/光功率/连接器类型/通信协议字段，或 QA/QC 与现场安装缺少定量公差及验收阈值；
4. 空泛描述而不能直接指导“下单采购、接线联调、现场焊接与团队培训”。
如存在严重或主要缺陷，设置 passed=false，指明需重写的 volumes_to_rewrite，并在必要时触发 needs_crag_gap_search=true 与精准补搜 query。"""

JUDGE_SYSTEM = """你是执行 Ch 19 Stage-Gate 100 分制门禁审计的独立质量总评审。
请严格按 5 个维度（每维 0-20 分，总分 0-100 分，及格线 >= 85 分）逐项打分并给出客观可审计评价：
1. market_and_competitive_rigor (20)
2. hardware_selection_and_interface_completeness (20)
3. software_demod_and_boiler_ai_actionability (20)
4. npi_qaqc_bringup_and_field_sop (20)
5. financial_gtm_training_and_traceability (20)"""

VOLUME_SPECS: list[tuple[str, str, str, str]] = [
    (
        "00_EXECUTIVE_PRODUCT_CHARTER_AND_ROADMAP.md",
        "产品立项总纲、双档定位与全生命周期研发量产路线图",
        "首席产品经理 (Chief PM)",
        "汇总项目使命、BS-STD-600 (300-600点) 与 BS-PRO-2000 (1000-2000+点) 双档模块化产品定义、核心技术路线对比 Elo 裁决结果、外购国际成品快速集成+软件AI壁垒策略、0→1 样机（35-55天）到首年挂网示范→次年批量量产里程碑、核心风险矩阵与各卷交付索引。",
    ),
    (
        "01_CHINA_COAL_BOILER_MARKET_AND_COMPETITIVE_LANDSCAPE.md",
        "中国燃煤电力锅炉水冷壁 FBG 测温市场趋势与国内外竞品拆解",
        "市场与竞品首席分析师",
        "深度剖析中国煤电三改联动与深度调峰（15%-30%负荷）水冷壁爆管/高温腐蚀痛点、热电偶 vs 声学测温 vs 红外 vs 传统UV-FBG vs 高温飞秒/弱光栅阵列对比；对标国内龙头（理工光科、太辰光、东方锐择、光子传感等）与国际大厂（Luna/Micron Optics、FBGS、Omnisens、Yokogawa）的架构、售价带、盲区及我们的双档双轨破局策略；结合 STORM 买方委员会四角色诉求制定招投标切入策略。",
    ),
    (
        "02_SYSTEM_ARCHITECTURE_SUPPLIER_SELECTION_AND_BOM.md",
        "双档系统总体架构、国际硬件选型与双轨分级 BOM（含 PDF 规格书映射）",
        "光电系统总师",
        "结合 [PHY-CALC] 全链路光功率预算（SNR裕度、波长漂移、刷新周期）与 [BOM-CALC] 阶梯成本表，完整阐述 BS-STD-600 与 BS-PRO-2000 系统框图、所有核心进口器件选型依据、原厂 Part Number、一备一防呆备选供应商、与本地 `./datasheets_pdf/*.pdf` 精确链接映射，以及 Track A（全进口高可靠传感）vs Track B（核心进口+严选本土传感降本）详细 BOM 采购清单，确保工程师可直接按表下单询价。",
    ),
    (
        "03_COMPONENT_INTERFACES_AND_DETAILED_INTEGRATION_DESIGN.md",
        "全系统硬件接口定义、光电/电气/机械/协议集成详设与联调规程",
        "硬软件接口主任工程师",
        "这是最关键的工程实现文档之一。必须逐模块给出精确端口与物理连接规范：① 光路拓扑与接口（FC/APC 8°斜面、插损预算、单/双环形器、Sercalo SW1x16/32/48 开关引脚、HCN-13 气室与50GHz标准具分光比）；② 电气与供电配电树（MeanWell 24V/12V/5V 隔离分布、FEMTO HCA-S-200M-IN ±15V 供电与 SMA 50Ω 至 Spectrum M2p.5922 PCIe CH0/CH1/Trig 接法、激光器 TTL Trigger 同步时序）；③ 工控机与光开关 RS-232/USB 帧协议、Ibsen I-MON 512 USB 帧读取接口、Moxa MGate/OPC UA 单向网闸接入电厂 DCS 寄存器映射；④ 2U/4U 机箱内部散热风道、光纤盘纤最小弯曲半径（R>=30mm）与 EMI 防护。",
    ),
    (
        "04_SOFTWARE_DEMODULATION_AND_BOILER_AI_SPEC.md",
        "自研高速解调算法、上位机工程软件与两阶段锅炉 AI 应用架构",
        "软件与锅炉 AI 首席架构师",
        "完整定义自主知识产权软件栈：① 光谱与扫频采集驱动（Ibsen USB/SPI SDK & Spectrum DMA 环形缓冲）；② 核心寻峰解调算法链（暗电流扣除 → SG 平滑 → 气室/标准具三次样条线性化 → 寻峰粗定位 + 加权对数高斯/LM 亚像素拟合达到 <0.5pm 精度 → 三阶温度反演与 15CrMoG 导热块热流逆向温差补偿）；③ 断纤/光衰/温飘自诊断状态机；④ 上位机热力三维数字孪生 UI（水冷壁展开图与克里金插值）；⑤ 两阶段锅炉 AI 进厂落地详设（一期旁路只读：结焦洁净因子按需吹灰、Larson-Miller 蠕变疲劳爆管预警、火焰偏斜/还原性气氛腐蚀诊断；二期闭环寻优：等保三级合规与风煤偏置建议架构）。",
    ),
    (
        "05_SYSTEM_BRINGUP_FIELD_INSTALLATION_AND_QAQC_SOP.md",
        "系统装调测试、电厂现场焊接安装指南与全流程 QA/QC 及量产 NPI SOP",
        "NPI 质量与现场交付总监",
        "提供工厂到电厂全流程可执行 SOP：① 主机上电 Bring-Up 与光路调通检查表（光功率逐点排查、光谱基线校验、气室校准验证）；② 工厂级 IQC 来料检验（OFS/长飞光纤 200kpsi 复验、FBG 光谱峰形/SLSR/FWHM 筛选、MEMS 插损重复性测试）、总装 IPQC、650°C 三温区管式炉多点自动标定算法、72 小时高低温老化与整机 FAT 出厂检验记录模板；③ 锅炉水冷壁现场安装核心 SOP（停炉水冷壁打磨清理、15CrMoG 导热块位置规划与焊前预热/TIG/手工氩弧焊防烧穿工艺、316L/Inconel600 毛细管松套穿纤留余量严禁拉紧工艺、穿炉墙密封套管热膨胀补偿弯设计、耐高温防磨护瓦施工、光缆熔接与 OTDR 验收红线、冷态/热态联调及电厂 SAT 终验）。",
    ),
    (
        "06_FINANCIAL_ANALYSIS_GTM_MARKETING_AND_TRAINING_PLAYBOOK.md",
        "财务投资分析、市场营销 GTM 策略、内部工程师与销售实战培训手册",
        "CFO 与商业化培训总监",
        "严格引用 [FIN-CALC]、[BOM-CALC]、[PLANT-ROI] 确定性数值，输出：① 精益创业启动投资预算（CAPEX 80万元分解）、5 年三情景营收/EBITDA/现金流/盈亏平衡/NPV/IRR 表；② 600MW 与 1000MW 电厂客户经济性测算书（投资回收期、爆管非停避损、节煤降耗账本）；③ 市场营销与渠道 GTM（首批 1-3 台挂网示范电厂切入打法、五大六小发电集团/三大锅炉厂 OEM 协同、投标控标技术参数壁垒设计）；④ 内部交付/调试工程师 4 周实操培训大纲与考核题库、销售团队价值话术 Battlecard 与常见异议应答手册。",
    ),
]
