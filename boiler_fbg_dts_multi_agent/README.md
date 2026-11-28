# 燃煤锅炉水冷壁光纤测温产品研发多智能体工作流

**boiler-fbg-workflow** — 基于 《Agentic Design Patterns》 设计模式的多智能体产品研发团队系统

---

## 一、书籍来源与设计模式映射

### 1.1 原始书籍信息

| 字段 | 内容 |
|------|------|
| **书名** | *Agentic Design Patterns: A Hands-On Guide to Building Intelligent Systems* |
| **中文译名** | 智能体设计模式：构建智能系统的实战指南 |
| **作者** | **Antonio Gulli**（Google 首席技术官办公室 Office of the CTO 工程总监） |
| **出版信息** | 482 页，21 个核心智能体设计模式章节 |
| **说明** | 本书为 Antonio Gulli 个人专著，非 Google 官方出版物 |

### 1.2 核心设计模式引用与实现映射

| 书籍章节 | 页码 | 设计模式 | 本项目实现位置 | 实现说明 |
|----------|------|----------|----------------|----------|
| **Chapter 7** | P113–P131 | Multi-Agent Collaboration | `graph.py`, `nodes/` | 层级主管 + 流水线交接 + 批评者-审查员三重拓扑混合 |
| **Chapter 6** | P100–P112 | Planning | `nodes/planner.py` | 动态研发阶段规划，支持重规划 |
| **Chapter 4** | P65–P78 | Reflection | `nodes/quality_reviewer.py` | 独立质量评审智能体对所有阶段产物的对抗检查 |
| **Chapter 13** | P204–P212 | Human-in-the-Loop | `nodes/hitl_gate.py` | 关键决策门禁（采购审批、设计评审、安全合规） |
| **Chapter 12** | P196–P203 | Exception Handling | `tools/resilience.py` | 三级容错（重试→回退→优雅降级→升级上报） |
| **Chapter 5** | P79–P99 | Tool Use | `tools/` | 确定性计算工具、数据适配器、证据库 |
| **Chapter 11** | P183–P195 | Goal Monitoring | `tools/milestone_tracker.py` | 研发里程碑追踪与偏离告警 |
| **Chapter 3** | P50–P64 | Parallelization | `graph.py` | 阶段内多角色并行（如硬件+软件+供应链并发） |
| **Chapter 1** | P23–P35 | Prompt Chaining | `graph.py` | 阶段间严格因果依赖的流水线编排 |

### 1.3 架构选型取舍分析

**评估的三种候选架构**：

#### 方案 A：纯层级主管模式（Hierarchical Supervisor）
- **来源**：书籍 Chapter 7, P117 Fig.2 "Hierarchical"
- **描述**：PM 作为顶层主管，各职能组作为工人智能体，所有任务经 PM 分派和汇总
- **优点**：责任链清晰，决策归口明确
- **缺点**：PM 成为单点瓶颈和故障点，串行等待导致延迟高
- **决策**：❌ 不采用 — 不适合需要并行协作的产品研发

#### 方案 B：阶段流水线 + 并行混合模式（Pipeline + Parallel Hybrid）
- **来源**：书籍 Chapter 1 (P23-35) + Chapter 3 (P50-64) + Chapter 7 (P114) Sequential Handoffs
- **描述**：研发按阶段串行推进（需求→设计→采购→开发→测试→导入），每阶段内部多角色并行
- **优点**：兼顾阶段依赖和并行效率，符合产品研发 V 模型
- **缺点**：阶段划分需预定义，灵活性有限

#### 方案 C：辩论与批评者-审查员模式（Debate + Critic-Reviewer）
- **来源**：书籍 Chapter 4 (P65-78) + Chapter 7 (P116) Critic-Reviewer
- **描述**：独立质量评审与所有角色形成对抗检查，多视角辩论达成共识
- **优点**：输出质量高，显著降低幻觉和错误
- **缺点**：成本和周期较高

**最终选择**：✅ **方案 B + C 混合架构**

- 采用阶段流水线（Chapter 1）确保研发因果依赖
- 阶段内多角色并行（Chapter 3）提升效率
- 全程贯穿独立质量评审的对抗检查（Chapter 4）确保质量
- 关键节点设置人在回路门禁（Chapter 13）保障安全

---

## 二、产品约束与边界声明

### 2.1 产品范围

| 约束项 | 说明 |
|--------|------|
| **应用场景** | 中国燃煤锅炉水冷壁高温区域光纤分布式测温 |
| **推荐首场景** | 待调研后推荐（无预设试点） |
| **技术路线** | 优先 FBG（光纤布拉格光栅），如有证据支持可选 DTS（分布式温度传感）或其他 |
| **硬件策略** | 国际可靠原厂采购，软件自主研发 |
| **AI 功能边界** | 仅限监测/预警/优化建议，人工决策，**绝不直接控制或替代锅炉保护系统** |
| **预算分档** | 最小验证样机 / 商用试点 两档 |

### 2.2 安全红线

```
⚠️ 严禁事项：
1. AI 系统不得直接发送控制指令到锅炉 DCS/SIS 系统
2. 不得绕过或替代锅炉安全联锁保护
3. 不得在无人监督下自动执行高风险操作
4. 所有告警和建议必须经人工确认后方可执行
```

### 2.3 待验证技术关键项

| 技术项 | 待验证内容 | 状态 |
|--------|------------|------|
| 高温 FBG 适用性 | 工作温度范围（目标 ≥500°C）、长期漂移、寿命 | 🔍 待确认 |
| 应变-温度解耦 | 热膨胀和机械应变分离方法 | 🔍 待确认 |
| 安装工艺 | 焊接/压力部件审批、高温粘结剂/封装 | 🔍 待确认 |
| 供应商可靠性 | 国际原厂产品线、交期、技术支持 | 🔍 待确认 |

---

## 三、多智能体团队角色定义

### 3.1 角色列表与职责

| 角色 ID | 角色名称 | 主要职责 | 输入契约 | 输出契约 | 证据要求 |
|---------|----------|----------|----------|----------|----------|
| `PM` | 项目经理 | 研发阶段编排、里程碑追踪、资源协调、风险登记 | 用户需求、团队状态 | 研发计划、状态报告、风险登记簿 | 阶段审批记录 |
| `MKT` | 市场研究 | 市场规模、客户痛点、竞品分析、场景推荐 | 外部市场数据注入点 | 市场分析报告、客户画像、竞品矩阵 | 数据源标注 |
| `OPT` | 光学测温/热工 | FBG/DTS 选型、热工建模、传感器布局设计 | 技术规格、温度要求 | 光学设计方案、热工分析报告 | 计算依据 |
| `HW` | 硬件集成 | 解调仪选型、线缆路由、供电防护、接口定义 | 光学方案、环境条件 | 硬件 BOM、接口规格、布线图 | 供应商数据表引用 |
| `SW` | 软件与 AI | 数据采集、算法开发、预警逻辑、可视化 | 硬件接口、功能需求 | 软件架构、算法规格、测试用例 | 代码审查记录 |
| `SCM` | 供应链 | 供应商筛选、询价、交期管理、BOM 成本 | 硬件 BOM、质量要求 | 供应商清单、报价、采购计划 | 报价单存档 |
| `QA` | 独立质量评审 | 独立审查所有产物、合规检查、异议返工 | 所有阶段产物 | 审查报告、不符合项、HOLD 标识 | 审查记录 |
| `MFG` | 制造导入 | 生产工艺评审、DFM 检查、试产计划 | 设计方案、BOM | 工艺评审报告、试产 SOP | 工艺验证记录 |
| `TRN` | 工程培训 | 安装培训材料、运维手册、客户培训 | 技术方案、产品文档 | 培训课件、运维手册 | 培训效果评估 |
| `FIN` | 财务 | 成本核算、预算管理、ROI 分析 | BOM、人工成本 | 成本分析、预算表、投资回报分析 | 计算依据 |
| `SLS` | 销售培训 | 销售话术、演示方案、客户沟通培训 | 产品特性、市场分析 | 销售工具包、演示脚本 | 培训材料 |
| `STR` | 营销策略 | 定位策略、推广计划、渠道规划 | 市场分析、竞品情报 | 营销计划、渠道策略 | 策略依据 |

### 3.2 角色依赖关系图

```
                    ┌─────────────────────────────────────────────┐
                    │                   PM                        │
                    │         (项目经理 - 主管协调)                │
                    └──────────────────┬──────────────────────────┘
                                       │
        ┌──────────────────────────────┼──────────────────────────────┐
        │                              │                              │
        ▼                              ▼                              ▼
   ┌─────────┐                  ┌─────────────┐                ┌──────────┐
   │   MKT   │──────────────────│     OPT     │────────────────│    FIN   │
   │ 市场研究 │                  │ 光学测温/热工│                │   财务   │
   └────┬────┘                  └──────┬──────┘                └─────┬────┘
        │                              │                              │
        │                              ▼                              │
        │                       ┌─────────────┐                       │
        │                       │     HW      │                       │
        │                       │  硬件集成   │                       │
        │                       └──────┬──────┘                       │
        │                              │                              │
        │         ┌────────────────────┼────────────────────┐         │
        │         │                    │                    │         │
        │         ▼                    ▼                    ▼         │
        │    ┌─────────┐         ┌─────────┐         ┌─────────┐     │
        │    │   SW    │         │   SCM   │         │   MFG   │     │
        │    │软件与AI │         │ 供应链  │         │ 制造导入 │     │
        │    └────┬────┘         └────┬────┘         └────┬────┘     │
        │         │                   │                   │          │
        │         └───────────────────┴───────────────────┘          │
        │                             │                              │
        │                             ▼                              │
        │                     ┌───────────────┐                      │
        │                     │      QA       │◄─────────────────────┘
        │                     │ 独立质量评审  │
        │                     └───────────────┘
        │                             │
        ▼                             ▼
   ┌─────────────────────────────────────────────────────┐
   │                下游交付角色（并行）                  │
   │  ┌─────────┐    ┌─────────┐    ┌─────────┐         │
   │  │   TRN   │    │   SLS   │    │   STR   │         │
   │  │工程培训 │    │销售培训 │    │营销策略 │         │
   │  └─────────┘    └─────────┘    └─────────┘         │
   └─────────────────────────────────────────────────────┘
```

---

## 四、工作流阶段定义

### 4.1 阶段流水线

```
Stage 0: 需求分析与市场研究
    ├── MKT: 市场调研（并行）
    ├── OPT: 技术可行性初评（并行）
    └── QA: 需求完整性审查
         └── HITL Gate: 需求确认

Stage 1: 概念设计
    ├── OPT: 光学方案设计（并行）
    ├── HW: 系统架构设计（并行）
    ├── SW: 软件架构设计（并行）
    └── QA: 设计评审
         └── HITL Gate: 设计批准

Stage 2: 详细设计与采购评审
    ├── OPT: 详细光学设计（并行）
    ├── HW: 详细硬件设计 + BOM（并行）
    ├── SCM: 供应商筛选 + 报价（并行）
    ├── FIN: 成本分析（依赖 BOM）
    └── QA: BOM 合规审查 + HOLD/BLOCKED 标识
         └── HITL Gate: 采购批准

Stage 3: 开发实现
    ├── HW: 硬件集成测试
    ├── SW: 软件开发 + 单元测试
    └── QA: 代码审查 + 集成测试监督

Stage 4: 系统测试与验证
    ├── 实验室验证用例执行
    ├── 合成数据测试
    └── QA: 测试结果审查
         └── HITL Gate: 测试通过确认

Stage 5: 生产导入与培训
    ├── MFG: 工艺验证 + 试产
    ├── TRN: 培训材料开发
    ├── SLS: 销售工具开发
    ├── STR: 营销策略制定
    └── QA: 上市准备度审查
         └── HITL Gate: 上市批准
```

### 4.2 质量门禁与返工机制

```python
# 质量门禁逻辑（基于 Chapter 4 Reflection + Chapter 13 HITL）
def quality_gate(stage_outputs, qa_review):
    if qa_review.has_critical_issues:
        return "BLOCKED"  # 阻塞，必须返工
    elif qa_review.has_major_issues:
        return "HOLD"     # 暂停，等待人工决策
    elif qa_review.has_minor_issues:
        return "CONDITIONAL_PASS"  # 条件通过，需跟踪
    else:
        return "PASS"     # 通过
```

---

## 五、证据注册表与可追溯性

### 5.1 证据分类

| 证据类型代码 | 说明 | 示例 |
|--------------|------|------|
| `[EV-LIT-*]` | 公开文献/论文 | 期刊论文、技术白皮书 |
| `[EV-DS-*]` | 供应商数据表 | 产品规格书、性能曲线 |
| `[EV-CALC-*]` | 确定性计算结果 | 市场规模计算、ROI 计算 |
| `[EV-SYNTH-*]` | 合成/模拟数据 | 温度数据生成、故障注入 |
| `[EV-TEST-*]` | 测试结果 | 单元测试、集成测试日志 |
| `[EV-REVIEW-*]` | 审查记录 | QA 审查报告、设计评审 |
| `[EV-HITL-*]` | 人工决策记录 | 审批记录、手动覆盖 |
| `[EV-UNKNOWN-*]` | 待确认/未验证 | 标记为需要后续验证 |

### 5.2 证据注册表结构

```json
{
  "ev_id": "[EV-LIT-001]",
  "type": "literature",
  "title": "High-Temperature FBG Sensors for Power Plant Applications",
  "source": "IEEE Sensors Journal",
  "url": "待注入",
  "date": "待注入",
  "hash": "sha256:...",
  "status": "PENDING_VERIFICATION",
  "referenced_by": ["OPT-design-001", "QA-review-002"]
}
```

---

## 六、测温数据应用原型

### 6.1 功能范围

| 功能 | 说明 | 实现状态 |
|------|------|----------|
| 数据采集模拟 | FBG/DTS 解调仪适配器契约 + 合成数据源 | ✅ 含 SYNTHETIC 标记 |
| 温度/应变风险检测 | 超温、温升异常、温度梯度异常 | ✅ 算法脚本 |
| 质量标志 | 丢点、断纤、漂移检测 | ✅ 算法脚本 |
| 建议输出 | 预警等级、建议措施（人工决策参考） | ✅ 仅建议 |
| 审计日志 | 所有检测结果和建议的完整记录 | ✅ 时间戳+hash |
| 本地仪表盘 | Streamlit 可选仪表盘 | ⚙️ 可选依赖 |

### 6.2 适配器契约定义

```python
# 硬件适配器接口契约 - 不声称已支持实际硬件
class DemodulatorAdapter(Protocol):
    """FBG/DTS 解调仪适配器接口 - 契约定义
    
    ⚠️ 说明：本接口定义供应商适配器契约
    当前仅提供模拟数据源实现，实际硬件集成需：
    1. 获取供应商 SDK/API 文档
    2. 实现具体适配器
    3. 进行实际硬件联调测试
    """
    def connect(self, config: dict) -> bool: ...
    def read_wavelengths(self) -> list[float]: ...
    def read_temperatures(self) -> list[float]: ...
    def get_channel_status(self) -> list[ChannelStatus]: ...
```

---

## 七、快速启动

```bash
# 1. 安装依赖
cd boiler_fbg_dts_multi_agent
uv sync --python 3.12 --extra dev

# 2. 运行离线单元测试（零成本，无 LLM 调用）
uv run pytest -v

# 3. 运行工作流演练（模拟模式）
uv run boiler-fbg run --mode simulation

# 4. 可选：启动本地仪表盘
uv sync --extra dashboard
uv run streamlit run src/boiler_fbg_workflow/dashboard/app.py
```

---

## 八、运行模式说明

| 模式 | 说明 | 证据标记 |
|------|------|----------|
| `simulation` | 离线模拟，所有角色输出预定义模板 | `[SIMULATION]` |
| `offline-replay` | 重放历史 trace，验证流程 | `[OFFLINE-REPLAY]` |
| `live` | 真实 LLM 调用（需配置模型端点） | `[LIVE-LLM]` |

**重要声明**：
- 若环境不具备合法可用的模型调用路径，将诚实标记为离线演练
- 不会把离线脚本称为真实 LLM 智能体运行
- 研究/推理过程不是交付程序 live 调用的证据

---

## 九、限制、未知项与风险登记

### 9.1 当前限制

| 限制项 | 说明 |
|--------|------|
| 无实际硬件测试 | 适配器仅为契约定义，需实际硬件联调 |
| 无现场数据 | 合成数据带 SYNTHETIC 标记，不声称电厂实测 |
| 供应商参数未验证 | 高温 FBG 规格需原厂确认 |
| 市场数据待注入 | 市场份额、价格等待父级任务提供 |

### 9.2 风险登记簿模板

| 风险 ID | 风险描述 | 影响 | 可能性 | 缓解措施 | 状态 |
|---------|----------|------|--------|----------|------|
| R-001 | 高温 FBG 温度上限不足 | 高 | 中 | 评估 DTS 替代方案 | 待调研 |
| R-002 | 供应商交期超长 | 中 | 中 | 备选供应商清单 | 待调研 |
| R-003 | 安装工艺审批复杂 | 高 | 高 | 早期与电厂沟通 | 待启动 |

---

## 十、文件结构

```
boiler_fbg_dts_multi_agent/
├── pyproject.toml              # 项目配置与依赖
├── README.md                   # 本文档
├── configs/
│   ├── settings.yaml           # 工作流配置
│   └── roles.yaml              # 角色定义
├── docs/
│   ├── DESIGN_SPEC.md          # 详细设计规格
│   ├── PATTERN_MAPPING.md      # 设计模式映射
│   └── ARCHITECTURE_DECISION.md # 架构决策记录
├── evidence_registry/
│   └── evidence_index.json     # 证据注册表
├── outputs/                    # 运行输出目录
├── synthetic_data/             # 合成测试数据
├── src/boiler_fbg_workflow/
│   ├── __init__.py
│   ├── cli.py                  # 命令行入口
│   ├── config.py               # 配置管理
│   ├── schemas.py              # 数据模型
│   ├── graph.py                # LangGraph 工作流
│   ├── nodes/                  # 节点实现
│   │   ├── __init__.py
│   │   ├── planner.py          # PM 规划节点
│   │   ├── market_researcher.py # MKT 市场研究
│   │   ├── optical_engineer.py  # OPT 光学工程
│   │   ├── hardware_integrator.py # HW 硬件集成
│   │   ├── software_developer.py  # SW 软件开发
│   │   ├── supply_chain.py     # SCM 供应链
│   │   ├── quality_reviewer.py # QA 质量评审
│   │   ├── manufacturing.py    # MFG 制造导入
│   │   ├── training.py         # TRN/SLS 培训
│   │   ├── finance.py          # FIN 财务
│   │   ├── marketing.py        # STR 营销
│   │   └── hitl_gate.py        # HITL 人工门禁
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── evidence_vault.py   # 证据库
│   │   ├── cost_calculator.py  # 成本计算器
│   │   ├── resilience.py       # 容错工具
│   │   └── milestone_tracker.py # 里程碑追踪
│   ├── prompts/
│   │   ├── __init__.py
│   │   └── templates.py        # 提示词模板
│   └── temperature_app/        # 测温数据应用
│       ├── __init__.py
│       ├── adapters.py         # 硬件适配器契约
│       ├── data_generator.py   # 合成数据生成
│       ├── risk_detector.py    # 风险检测算法
│       ├── quality_flags.py    # 质量标志检测
│       └── audit_logger.py     # 审计日志
└── tests/
    ├── test_schemas.py
    ├── test_graph_trajectory.py
    ├── test_temperature_app.py
    └── test_risk_detector.py
```

---

## 十一、版本与更新记录

| 版本 | 日期 | 更新内容 |
|------|------|----------|
| 0.1.0 | 2026-11-15 | 初始架构设计与核心实现 |

---

*本文档基于《Agentic Design Patterns: A Hands-On Guide to Building Intelligent Systems》(Antonio Gulli) 设计模式构建*
