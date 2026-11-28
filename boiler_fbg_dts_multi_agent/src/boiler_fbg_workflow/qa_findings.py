"""Independent QA Review Findings - Real Review Results

This module contains REAL independent QA findings from the v0.2 document review.
Review ID: BOILER-QA-INDEPENDENT-v0.2-20261116

These findings are used as actual input for the QA reflection loop,
implementing Reflection Pattern (Ch4) and Multi-Agent Collaboration (Ch7).

Reference: "Agentic Design Patterns" - Antonio Gullí, Springer 2025
- Chapter 4 (P67-82): Reflection Pattern
- Chapter 7 (P113-131): Multi-Agent Collaboration
- Chapter 13 (P201-218): Human-in-the-Loop
"""

from __future__ import annotations
from typing import Any
from datetime import datetime

# Review metadata
QA_REVIEW_METADATA = {
    "review_id": "BOILER-QA-INDEPENDENT-v0.2-20261116",
    "role": "独立热工/光学系统文件质量复审（非持证第三方认证/非实物验收）",
    "timezone": "Asia/Shanghai UTC+8",
    "started_at": "2026-11-16T01:40:30.713847+08:00",
    "findings_written_at": "2026-11-16T01:46:47.449606+08:00",
    "input_version": "v0.2",
    "input_manifest_sha256": "c6685a245212c69bec73f382fa8ad548e7a15ebd461bc7cba0a5b13759b76e8e",
    "scope_exclusions": [
        "不审查或修改代码",
        "不克隆仓库",
        "不联系第三方/不外发/不采购",
        "不审v0.1旧包"
    ],
    "decision": {
        "laboratory_task_spec_review": "CONDITIONALLY_SUITABLE_FOR_REVIEW_ONLY",
        "laboratory_execution": "HOLD",
        "procurement": "NOT_READY",
        "field_installation": "HOLD",
        "product_release": "NOT_READY",
        "all_physical_tests": "NOT_RUN"
    },
    "top5": ["QA-01", "QA-03", "QA-04", "QA-02", "QA-05"],
}

# HIGH severity findings (5)
QA_FINDINGS_HIGH: list[dict[str, Any]] = [
    {
        "id": "QA-01",
        "severity": "HIGH",
        "title": "漂移准入与全寿命MPE不一致，分项通过不保证测量链仍合格",
        "locations": [
            "engineering/02_系统设计及接口基线.md §7.4（行69）",
            "engineering/03_校准验证FAT_SAT与安装SOP.md §4–5（行36、41–43）",
            "engineering/08_四点最小验证台详细规格与操作卡.md LAB02/LAB04（行63、67）"
        ],
        "original_evidence": "实验室MPE±3℃且|e|+U≤3℃；示例u短漂0.7℃、U=2.795℃；同时允许168h漂移≤2℃、1000h≤3℃。",
        "primary_evidence": [
            "research/sources/Luna_si255.pdf p2：解调性能不是完整温度链寿命指标",
            "新增 evidence/JCGM_106_2012_E.pdf §3.3.18、§7.6.5、§8.3.2：MPE及误差测量不确定度、保护带须属于明确的被测属性"
        ],
        "problem": (
            "即便初始误差为0、初始保护带合格，随后+3℃漂移仍可满足独立漂移门限，却不能保证±3℃链指标。"
            "未规定漂移期间/老化后复验全量程、误差总包络、校准有效期或何时降级。"
            "示例只分配u=0.7℃短漂，不能覆盖允许的3℃老化变化。"
            "若仅作演示把±3℃漂移视为矩形界限并替换0.7分量，U就约4.225℃；这是反例计算，不是实测分布或建议如此处理偏差。"
        ),
        "recommended_correction": (
            "把初始校准、寿命中使用和验收试验各自的被测量及U分开；给漂移独立允许分配和维护周期。"
            "CAL03完成后不准直接PASS，必须用原校准版本重新检验全温区及接触工装；"
            "必要时缩短复校周期或降低声称等级，不得静默重置消除失败。"
        ),
        "verifiable_closure_condition": (
            "形成带时间/热循环/温区的误差预算和决策表，证明初始残差+漂移/滞回等效应与对应U满足同一MPE；"
            "L07/L08新增老化后原系数全温复验的必填结果及失败动作。"
            "文件改正可文审关闭；性能证据在实物试验前仍NOT_RUN。"
        ),
        "classification": "NEW_CROSS_REQUIREMENT_DEFECT",
        "owner": "光学/计量/QA",
        "status": "OPEN",
        "physical_test_status": "NOT_RUN",
        "workflow_impact": {
            "blocks_gate": True,
            "pm_action_required": "添加老化后原校准系数全温复验任务到L07/L08",
            "test_to_add": "test_aging_recalibration_verification",
        },
    },
    {
        "id": "QA-02",
        "severity": "HIGH",
        "title": "留一循环并未留出温度点，无法支撑整个25–600℃区间的MPE",
        "locations": [
            "engineering/03_校准验证FAT_SAT与安装SOP.md CAL-02行33–36",
            "engineering/08_四点最小验证台详细规格与操作卡.md LAB02行62–63",
            "tables/四点实验逐步记录.csv L04"
        ],
        "original_evidence": "25/100/200/300/400/500/600℃同点升降3循环，前2循环拟合、第3循环盲验，允许多项式/单调查表。",
        "primary_evidence": [
            "research/sources/FiSens_1550_Ordering_Rev7.pdf：未给本配置可直接使用的全温λ–T曲线或非线性界限",
            "新增 evidence/JCGM_106_2012_E.pdf §1、§5.1：对所声称属性取得充分的判定信息"
        ],
        "problem": (
            "盲验切断了同批拟合/重复测量的直接循环论证，但所有循环仍在同一7个温度点。"
            "未经限制的多项式可在节点全部吻合而节点间明显偏离，单调插值也不自动给出节点间误差上界。"
            "现测试能证明7个设定点及循环重复性，不能证明25–600℃全域±3℃。"
        ),
        "recommended_correction": (
            "预先冻结拟合阶次/约束、有效区间和系数版本；"
            "加入未参与拟合的中间温度、温区端部与升降动态验证，依据残差/温度导数确定最差点和插值不确定度；"
            "不能验证全域时将声称限定到已验证区间/节点。"
        ),
        "verifiable_closure_condition": (
            "批准的LAB02新增独立温度留出集、模型选择规则、单调性/导数检查、最大插值误差与U评估及原始记录字段；"
            "实物阶段以冻结系数逐点保护带验收，当前NOT_RUN。"
        ),
        "classification": "NEW_TEST_COVERAGE_DEFECT",
        "owner": "热工/光学/计量",
        "status": "OPEN",
        "physical_test_status": "NOT_RUN",
        "workflow_impact": {
            "blocks_gate": True,
            "pm_action_required": "LAB02添加独立温度验证点（非拟合节点）",
            "test_to_add": "test_interpolation_validation_points",
        },
    },
    {
        "id": "QA-03",
        "severity": "HIGH",
        "title": "现场被测量和代表性未闭合，8个对照点不足以签64点壁温安全价值",
        "locations": [
            "engineering/02_系统设计及接口基线.md R04、§7.3、§8（行8、68、73–76）",
            "engineering/03_校准验证FAT_SAT与安装SOP.md MECH-01、SAT（行53–56、101–104）",
            "commercial/04_供应商BOM预算商业与培训.md 行54",
            "tables/现场点位模板.csv"
        ],
        "original_evidence": (
            "现场拟±5℃；背火测温不能等同向火最高温；"
            "试点64点配8个热电偶对照，MECH-01只规定至少两个热通量水平，未给工况矩阵和每点验证归属。"
        ),
        "primary_evidence": [
            "新增 evidence/JCGM_106_2012_E.pdf §1、§3.2.4、§3.3.18：须定义唯一充分明确的被测量及误差",
            "新增 evidence/SAMR_2024_amendments.txt 第26–30行：修改单附表注A-5区分烟气侧外壁温与计算壁温；并非所有壁温口径可互换"
        ],
        "problem": (
            "文中已正确警告背火/向火不同，缺口在于没有把该警告落实为逐点measurand、接触面积/空间平均长度、温差修正和报警限值的绑定。"
            "温源等温合格不证明有热流时贴附正确；8个近邻TC既不是全部64点真值，也可能与FBG共受保温/安装扰动。"
            "未定义其余56点可接受的等效性证据，易在SAT把少数点吻合扩写为全部壁温精度或热点安全覆盖。"
        ),
        "recommended_correction": (
            "冻结首版只报告哪个物理表面/位置/长度的温度；向火估计单列模型值与不确定度，禁止套用OEM不同口径限值。"
            "按位置/夹具/保温/热通量/外界风/启停分层验证，量化安装导致的基体温度扰动；"
            "对未直接对照点给可审查等效性证据或限定NOT_COVERED。"
        ),
        "verifiable_closure_condition": (
            "每个试点sensor_id关联measurand、机械图、参考/等效组、有效工况和适用限值；"
            "MECH计划给热通量或可溯源热边界范围/稳态和动态组合及通过标准；"
            "SAT逐点/逐组出具精度覆盖表，未覆盖不得签64点±5℃。当前全部实体项NOT_RUN。"
        ),
        "classification": "KNOWN_HOLD_DEEPENED_TO_ACCEPTANCE_GAP",
        "owner": "热工/应用/OEM/QA",
        "status": "OPEN",
        "physical_test_status": "NOT_RUN",
        "workflow_impact": {
            "blocks_gate": True,
            "pm_action_required": "为每个sensor_id绑定measurand定义；56个未直接对照点标记NOT_COVERED或提供等效性证据",
            "test_to_add": "test_measurand_coverage_per_sensor",
            "code_impact": "不能用8TC线性推断64点精度，明确NOT_COVERED点数",
        },
    },
    {
        "id": "QA-04",
        "severity": "HIGH",
        "title": "非受压工装边界正确，但夹具热胀释放尚无可检验的设计载荷",
        "locations": [
            "engineering/02_系统设计及接口基线.md ICD-02、§7.1（行47、66）",
            "engineering/03_校准验证FAT_SAT与安装SOP.md CAL-02.7/MECH-01/INST-01",
            "engineering/08_四点最小验证台详细规格与操作卡.md M01/M02、行38–39、LAB03"
        ],
        "original_evidence": (
            "禁止擅焊受压件、陶瓷不得承受螺栓载荷；夹具与纤维需自由滑移；测试加载范围待实际热膨胀估算批准。"
            "波长情景却采用剩余应变±100με。"
        ),
        "primary_evidence": [
            "research/sources/FiSens_1550_Ordering_Rev7.pdf 物理p2–3：AC外径3.3mm、长度0.1–0.6m；无高温轴向自由行程/摩擦/固定端保证；p1的SC/BI为PI纤，不能推定装AC即整段耐600℃",
            "engineering/02_系统设计及接口基线.md：0.0012nm/με和0.012nm/℃仅示例，100με约10℃假温差"
        ],
        "problem": (
            "尚无夹持跨度、热膨胀差、可用滑移量、接触载荷窗口及其与±100με假设的关系。"
            "只说松套不能证明陶瓷/金属/光纤高温摩擦和弯曲后残余应变足够小；自由纤/PI涂覆/胶/端盖的热区拓扑也未定。"
            "若图纸仅补一个扭矩而不补载荷和自由度，仍可能在非受压台架压裂陶瓷或形成数℃至更大的假温差。"
        ),
        "recommended_correction": (
            "按实际料号形成分段材料与温限图、受力/自由度图；"
            "计算ΔL=(α夹具−α基体)LΔT及装配/蠕变余量，规定最小自由行程、夹紧力窗口、保护罩接触方式、陶瓷隔载及失效处置。"
            "±100με只可保留假设，须由实测λ/机械载荷证明或重算。"
        ),
        "verifiable_closure_condition": (
            "机械/热工签署非受压台架专用图与风险分析；"
            "LAB03覆盖批准的热膨胀位移、弯曲、摩擦/装拆及冷却回程，记录力/位移/温度/全谱；原厂确认热过渡和安装边界。"
            "图纸批准前不得高温开工；实物仍NOT_RUN，现场另需OEM许可。"
        ),
        "classification": "KNOWN_HOLD_DEEPENED_TO_LOAD_CASE_GAP",
        "owner": "机械/热工/原厂/QA",
        "status": "OPEN",
        "physical_test_status": "NOT_RUN",
        "workflow_impact": {
            "blocks_gate": True,
            "pm_action_required": "添加热膨胀/应变验证实验任务到LAB03",
            "test_to_add": "test_thermal_expansion_strain_verification",
        },
    },
    {
        "id": "QA-05",
        "severity": "HIGH",
        "title": "光谱包络以FWHM作宽度，缺少与实际峰检测相联系的保护谱罩",
        "locations": [
            "engineering/02_系统设计及接口基线.md §5–6（行55–63）",
            "engineering/03_校准验证FAT_SAT与安装SOP.md OPT-01（行46–50）",
            "tables/工程计算复核.json full_envelope_nm/guard_nm",
            "tables/接口兼容性矩阵.csv IF01/IF02/IF07"
        ],
        "original_evidence": (
            "13.69/15.49nm包络使用FWHM0.8nm，700℃情景16.5nm槽余1.01nm；"
            "要求旁瓣/峰展宽试验，但未定义全谱保护谱罩、检测门限或峰选择失败的判定。"
        ),
        "primary_evidence": [
            "research/sources/FiSens_1550_Ordering_Rev7.pdf 物理p2：STD窄峰FWHM0.25–0.35nm、SLSR>15dB；累计损耗口径反射率；并非谱线在FWHM外为零",
            "research/sources/CALSENS_High_Temperature_Sensor_20230808.pdf p1：FWHM0.1–2nm、SLSR>10dB",
            "research/sources/Luna_si255.pdf p2注4：0.25nm FBG用于性能确认",
            "research/sources/HBK_FS22SI_A04249.pdf §4.3.2：SPD范围内相对最高峰阈值"
        ],
        "problem": (
            "示例算术正确，但FWHM不是谱能量/旁瓣的支撑边界；光谱尾、旁瓣、多峰/偏振分裂可能越入相邻窗口。"
            "强反射的旁瓣相对受损弱点可能被峰算法认出，独立窗口不等于物理ID保证。"
            "按当前OPT文字，只要主峰中心未交叉、观察者未发现异常就可能通过，缺少把这些条件与最差温度/衰减/检测阈值联合起来的量化规则。"
        ),
        "recommended_correction": (
            "向原厂索取全温/应变/老化/偏振全谱及返回幅值界限，按实际解调阈值定义有效谱罩和最小可分离峰条件；"
            "明确主峰/旁瓣/分裂峰处理与BAD规则；"
            "将强点+最弱点衰减+冷热反序组合列入验收，不仅在名义功率下分别试温和试衰减。"
        ),
        "verifiable_closure_condition": (
            "冻结每点允许谱罩、窗口和检测配置/固件版本；"
            "全串组合边界试验中无误峰/错ID/饱和，并给谱罩外能量判据和距离失效门限。"
            "未知数据时H2及M=UNKNOWN保持；四独立点不关闭阵列项，实体状态NOT_RUN。"
        ),
        "classification": "KNOWN_HOLD_DEEPENED_TO_SPECTRAL_ACCEPTANCE_GAP",
        "owner": "光学/解调原厂/软件/QA",
        "status": "OPEN",
        "physical_test_status": "NOT_RUN",
        "workflow_impact": {
            "blocks_gate": True,
            "pm_action_required": "定义固件版本的谱罩和峰检测阈值规格",
            "test_to_add": "test_fwhm_spectral_mask_firmware_thresholds",
            "code_impact": "FWHM不是全谱边界保证，需要固件阈值配置",
        },
    },
]

# MEDIUM severity findings (5)
QA_FINDINGS_MEDIUM: list[dict[str, Any]] = [
    {
        "id": "QA-06",
        "severity": "MEDIUM",
        "title": "法规适用版本没有完成核实，已生效修改单可由官方直接取得",
        "locations": [
            "engineering/03_校准验证FAT_SAT与安装SOP.md INST-01 A行81–82",
            "research/sources/SAMR_TSG11_announcement.html",
            "research/05_来源与下载说明.md"
        ],
        "problem": (
            "可查到的2024正式修改单未纳入当前基线。"
            "安装方案若后续改变为焊接/维修，2020公告不足以支持适用性评估。"
        ),
        "recommended_correction": (
            "法规清单改为TSG11—2020及已生效第1号修改单，取得受控现行本和逐项适用性判定。"
        ),
        "classification": "NEW_PRIMARY_SOURCE_OMISSION",
        "owner": "法规/锅监/OEM/QA",
        "status": "OPEN",
        "physical_test_status": "NOT_RUN",
        "workflow_impact": {
            "blocks_gate": False,
            "pm_action_required": "更新法规基线引用TSG11-2020第1号修改单",
        },
    },
    {
        "id": "QA-07",
        "severity": "MEDIUM",
        "title": "柜体热设计与系统级环境验证遗漏，工业IP40不等于电厂柜内可用",
        "locations": [
            "engineering/02_系统设计及接口基线.md ICD-03行48、原厂表行33/41",
            "engineering/03_校准验证FAT_SAT与安装SOP.md F05/F08",
            "tables/BOM_两档预算.csv B06/B07",
            "engineering/09_系统集成小批导入QA_QC作业卡.md §6"
        ],
        "problem": (
            "功率裕度不等于散热裕度。密闭/防尘柜加入UPS、电源和交换机后，柜内进风温度可超过设备限制；"
            "UNO的60℃有明确气流前提，不能仅用柜外环境值验收。"
        ),
        "recommended_correction": (
            "给环境等级和柜内温升模型，选定换热/过滤/冷凝控制方式与监测点；"
            "规定设备入口温度、气流、相对湿度/露点裕度、热降额与风扇故障动作。"
        ),
        "classification": "NEW_SYSTEM_QUALIFICATION_GAP",
        "owner": "电气/机柜/QA",
        "status": "OPEN",
        "physical_test_status": "NOT_RUN",
        "workflow_impact": {
            "blocks_gate": False,
            "pm_action_required": "添加系统级热设计验证任务",
        },
    },
    {
        "id": "QA-08",
        "severity": "MEDIUM",
        "title": "可用率门限允许长时间连续盲区，未给恢复/最长失联的通过标准",
        "locations": [
            "engineering/03_校准验证FAT_SAT与安装SOP.md F05行72、SAT行102/104",
            "engineering/02_系统设计及接口基线.md R03/R07"
        ],
        "original_evidence": "72h FAT有效率≥99.5%，SAT≥99%；要求报告最长失联但没有规定其接受上限。",
        "primary_evidence": [
            "原需求为局部监测/预警、≤3s数据呈现；质量位失效不能代替监测服务本身",
            "独立计算 independent_calculations.json：72h×0.5%=21.6min，30天×1%=7.2h"
        ],
        "problem": (
            "系统即便一次连续失联21.6min，仍可能满足FAT百分比；30天SAT可累计失联7.2h。"
            "STALE如实报警是必要条件，但不能单凭不静默就认为预警可用。"
            "重连时限、重启数据恢复、最长盲区与坏点恢复的门限缺失。"
        ),
        "recommended_correction": (
            "由应用风险和用户原保护边界定义最长连续盲区/恢复时间/掉点突发次数、关键工况必须覆盖比例。"
        ),
        "verifiable_closure_condition": (
            "F05/SAT统计表新增每点及整机连续失联上限与重启/重连标准，"
            "覆盖最坏故障回放和真实硬件恢复；客户在试验前同意标准。"
        ),
        "classification": "NEW_ACCEPTANCE_LOOPHOLE",
        "owner": "应用/软件/QA",
        "status": "OPEN",
        "physical_test_status": "NOT_RUN",
        "workflow_impact": {
            "blocks_gate": False,
            "pm_action_required": "定义最长连续盲区上限（如≤60s），而不只是百分比可用率",
            "test_to_add": "test_longest_blind_window_stats",
            "code_impact": "需要统计最长连续盲区而不只是总百分比",
        },
    },
    {
        "id": "QA-09",
        "severity": "MEDIUM",
        "title": "6dB衰减裕度缺少可执行的双程换算和参考平面",
        "locations": [
            "engineering/02_系统设计及接口基线.md §6行61–63",
            "engineering/03_校准验证FAT_SAT与安装SOP.md OPT-01行48",
            "engineering/08_四点最小验证台详细规格与操作卡.md O02"
        ],
        "problem": (
            "同一互易VOA置于反射光路，单程增加3dB通常使返回功率增加6dB损耗；拨盘值和返回裕度不是同一量。"
            "若有人把单程6dB照抄为双程6dB，会无谓过测；反向混用则可能虚报裕度。"
        ),
        "recommended_correction": (
            "画出参考平面和VOA拓扑，定义M_rx与单程允许损耗分别记录；"
            "标定VOA实际波长/双向损耗及新增接头，失效门限取所有错误模式中最先发生者。"
        ),
        "classification": "NEW_PROCEDURE_AMBIGUITY",
        "owner": "光学/计量/QA",
        "status": "OPEN",
        "physical_test_status": "NOT_RUN",
        "workflow_impact": {
            "blocks_gate": False,
            "pm_action_required": "明确VOA双程换算定义",
        },
    },
    {
        "id": "QA-10",
        "severity": "MEDIUM",
        "title": "两档资金情景没有与完整阶段退出条件对齐，也没有32点可执行子情景",
        "locations": [
            "commercial/04_供应商BOM预算商业与培训.md §3行53–61、行119",
            "tables/BOM_两档预算.csv A01/A04/A08/B02/B11/B13",
            "00_阅读指南与结论.md 两档预算"
        ],
        "problem": (
            "用户若用A资金额度决策，完成的究竟是初筛还是G2全验证不够一一对应；"
            "A结束到B开工之间的DVT预算缺口未汇总，32点也不能简单把64点成本除二。"
        ),
        "recommended_correction": (
            "给A0室温接口/A1四点初筛/A2完整DVT的费用边界及转段门槛，列未定实验室时长/报价项；"
            "试点分别给32/64点及可复用设备/NRE/每年维护现金流。"
        ),
        "classification": "KNOWN_SCOPE_GAP_NOT_PRICE_ARITHMETIC_ERROR",
        "owner": "财务/PM/供应链",
        "status": "OPEN",
        "physical_test_status": "NOT_RUN",
        "workflow_impact": {
            "blocks_gate": False,
            "pm_action_required": "细化A→B阶段预算边界",
        },
    },
]

# Combined findings list
QA_FINDINGS_ALL = QA_FINDINGS_HIGH + QA_FINDINGS_MEDIUM


def get_findings_summary() -> dict[str, Any]:
    """Get summary of all QA findings for agent input."""
    high_count = len(QA_FINDINGS_HIGH)
    medium_count = len(QA_FINDINGS_MEDIUM)
    
    blocking_findings = [f for f in QA_FINDINGS_ALL 
                         if f.get("workflow_impact", {}).get("blocks_gate", False)]
    
    tests_to_add = [
        f["workflow_impact"]["test_to_add"]
        for f in QA_FINDINGS_ALL
        if "test_to_add" in f.get("workflow_impact", {})
    ]
    
    pm_actions = [
        {"finding_id": f["id"], "action": f["workflow_impact"]["pm_action_required"]}
        for f in QA_FINDINGS_ALL
        if "pm_action_required" in f.get("workflow_impact", {})
    ]
    
    code_impacts = [
        {"finding_id": f["id"], "impact": f["workflow_impact"]["code_impact"]}
        for f in QA_FINDINGS_ALL
        if "code_impact" in f.get("workflow_impact", {})
    ]
    
    return {
        "review_id": QA_REVIEW_METADATA["review_id"],
        "review_decision": QA_REVIEW_METADATA["decision"],
        "total_findings": high_count + medium_count,
        "high_severity_count": high_count,
        "medium_severity_count": medium_count,
        "blocking_findings_count": len(blocking_findings),
        "blocking_finding_ids": [f["id"] for f in blocking_findings],
        "top5_priority": QA_REVIEW_METADATA["top5"],
        "tests_to_add": tests_to_add,
        "pm_actions_required": pm_actions,
        "code_impacts": code_impacts,
        "all_physical_tests": "NOT_RUN",
        "gate_status": "BLOCKED",
    }


def get_findings_for_reflection_prompt() -> str:
    """Format findings for LLM reflection prompt."""
    lines = [
        f"## 独立QA审查结果 [{QA_REVIEW_METADATA['review_id']}]",
        "",
        f"审查时间: {QA_REVIEW_METADATA['started_at']}",
        f"输入版本: {QA_REVIEW_METADATA['input_version']}",
        "",
        "### 门禁决策",
        f"- 实验室任务书评审: {QA_REVIEW_METADATA['decision']['laboratory_task_spec_review']}",
        f"- 实验室执行: {QA_REVIEW_METADATA['decision']['laboratory_execution']}",
        f"- 采购: {QA_REVIEW_METADATA['decision']['procurement']}",
        f"- 产品发布: {QA_REVIEW_METADATA['decision']['product_release']}",
        "",
        "### TOP 5 最重要问题",
    ]
    
    for finding_id in QA_REVIEW_METADATA["top5"]:
        finding = next((f for f in QA_FINDINGS_ALL if f["id"] == finding_id), None)
        if finding:
            lines.append(f"- **{finding['id']}** [{finding['severity']}]: {finding['title']}")
    
    lines.extend([
        "",
        "### HIGH严重性发现 (5项，全部阻塞门禁)",
    ])
    
    for f in QA_FINDINGS_HIGH:
        lines.extend([
            f"",
            f"**{f['id']}: {f['title']}**",
            f"- 问题: {f['problem'][:200]}...",
            f"- 建议纠正: {f['recommended_correction'][:150]}...",
            f"- PM行动: {f['workflow_impact'].get('pm_action_required', 'TBD')}",
        ])
    
    lines.extend([
        "",
        "### MEDIUM严重性发现 (5项)",
    ])
    
    for f in QA_FINDINGS_MEDIUM:
        lines.extend([
            f"",
            f"**{f['id']}: {f['title']}**",
            f"- 问题: {f['problem'][:150]}...",
            f"- PM行动: {f['workflow_impact'].get('pm_action_required', 'TBD')}",
        ])
    
    return "\n".join(lines)


def get_pm_task_revision_input() -> dict[str, Any]:
    """Get structured input for PM task revision based on QA findings."""
    return {
        "source": "independent_qa_review",
        "review_id": QA_REVIEW_METADATA["review_id"],
        "gate_status": "BLOCKED",
        "revision_required": True,
        "high_priority_actions": [
            {
                "finding_id": "QA-01",
                "action": "添加老化后原校准系数全温复验任务到L07/L08",
                "owner": "光学/计量",
                "blocking": True,
            },
            {
                "finding_id": "QA-02",
                "action": "LAB02添加独立温度验证点（非拟合节点）",
                "owner": "热工/光学",
                "blocking": True,
            },
            {
                "finding_id": "QA-03",
                "action": "为每个sensor_id绑定measurand定义；标记56个NOT_COVERED点",
                "owner": "热工/应用",
                "blocking": True,
                "code_impact": "不能用8TC线性推断64点精度",
            },
            {
                "finding_id": "QA-05",
                "action": "定义固件版本的谱罩和峰检测阈值规格",
                "owner": "光学/软件",
                "blocking": True,
                "code_impact": "FWHM不是全谱边界保证",
            },
            {
                "finding_id": "QA-08",
                "action": "定义最长连续盲区上限（建议≤60s），而不只是百分比可用率",
                "owner": "应用/软件",
                "blocking": False,
                "code_impact": "需要统计最长连续盲区",
            },
        ],
        "tests_to_implement": [
            "test_aging_recalibration_verification",
            "test_interpolation_validation_points",
            "test_measurand_coverage_per_sensor",
            "test_thermal_expansion_strain_verification",
            "test_fwhm_spectral_mask_firmware_thresholds",
            "test_longest_blind_window_stats",
        ],
    }
