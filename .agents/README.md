# `.agents/` 系统级工程规则、子智能体与技能包总览

本目录存放工作区 `agentic_learning` 的系统级 AI 定制资产（原生兼容 **Antigravity IDE** 自动发现机制，同时可作为 Cursor / Claude Code 等 AI Agent 的工程提示词基准），对应完整方法论文档见 [../solo_agentic_engineering_guide/README.md](../solo_agentic_engineering_guide/README.md)。

设计融合了 GitHub 社区高口碑开源工程体系（`obra/superpowers` 的 *Iron Law of TDD* 与 *Verification Before Completion*、`github/spec-kit` 的工程宪章与规格先行、`addyosmani/agent-skills` 的行为边界测试规范），并针对**「1 名独立开发者 + AI Agent」**场景进行了轻量化与防串谋改造。

---

## 目录结构与加载机制一览

```text
.agents/
├── README.md                                          # 本说明文档
├── rules/                                             # 自动注入的工程约束规则
│   ├── git_push_automation.md                         # Git 单主干提交与 github_push 推送红线
│   ├── solo_production_guardrails.md                  # [always_on] 生产级五大铁律（薄切片/红区隔离/禁改测试/防御基线/实证完工）
│   └── anti_collusion_testing.md                      # [glob: tests] 触碰测试文件自动激活：测试奖杯配比与防假测试准则
├── agents/                                            # 物理隔离上下文的专用子智能体系统提示词
│   ├── blind-test-author.md                           # 独立黑盒测试编写官（只看红区契约与中文矩阵写红灯测试）
│   └── adversarial-code-auditor.md                    # 独立挑刺审计官（只读权限，零客套对比需求与源码找细节漏洞）
└── skills/                                            # 按需渐进式激活的三大标准工作流技能
    ├── spec-thin-slice/                               # 技能 1：立项反问排雷 + 红区契约先行 + 垂直薄切片拆解
    │   ├── SKILL.md
    │   └── references/slice-spec-template.md
    ├── red-green-tdd/                                 # 技能 2：免手写读写隔离 TDD（Red → Green → Refactor → 实证）
    │   ├── SKILL.md
    │   └── references/anti-rationalization-checklist.md
    └── blind-audit-and-trace/                         # 技能 3：红黄绿三区分拣 + 独立盲审对账 + 黄金样本实弹轨迹表
        ├── SKILL.md
        └── references/golden-trace-template.md
```

---

## 各组件协同分工速查

| 你所处的研发阶段 | 自动生效 / 按需调用的组件 | 解决什么痛点？ |
| :--- | :--- | :--- |
| **任何对话轮次** | `rules/solo_production_guardrails.md` (`always_on`) | 防止 AI 未经确认一次倾倒几千行代码、防止把提示词/白名单散落写死在胶水代码里、防止没跑命令就嘴硬说“已修好” |
| **新项目/大特性开荒** | `skills/spec-thin-slice` | 先反问 3～5 个模糊边界，先交付 <=300 行的 🔴 红区契约给你精读，再拆成 150～300 行/片的垂直薄片 |
| **开发薄片 / 修 Bug** | `skills/red-green-tdd` + `agents/blind-test-author` + `rules/anti_collusion_testing.md` | 你不用手写一行测试代码；由独立盲测官先出红灯测试，主 Agent 锁死 `tests/` 写最小生产代码变绿，彻底根除同源串谋 |
| **接管存量代码 / 上线验收** | `skills/blind-audit-and-trace` + `agents/adversarial-code-auditor` | 不用通读几千行源码；自动分拣出 10% 必读红区，派只读审计官找茬对账，并用 10 条真实样本轨迹表 3 分钟看穿全部细节 |

---

## 迁移到未来独立新仓库的方法

以后你在工作区外单独新建任何独立 Git 项目时，只需将本目录下的 `rules/`、`agents/`、`skills/` 原样复制到新项目根目录的 `.agents/` 下（并在根目录保留 `AGENTS.md`），整套生产级防失控体系即可在新项目中零配置即刻生效。
