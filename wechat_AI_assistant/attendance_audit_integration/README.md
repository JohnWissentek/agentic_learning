# attendance_audit_integration

企业微信考勤与假勤审计集成系统。

- **一阶段（当前主线）**：基于企业微信独立完成考勤分析（打卡流水、请假/外出/出差/加班审批、假期余额与逾期台账、工作日报、现场工作报告）。
- **二阶段（后续联动）**：待金蝶实现 Agent 自动化报销与数据分析后，再合并执行差旅报销双向自动化交叉审计（F15，现阶段由财务人工核对，代码保留只读骨架）。

## 文档导航

| 路径 | 说明 |
|---|---|
| [`docs/PRD.md`](docs/PRD.md) | 产品需求与业务规则（唯一事实来源，v0.7） |
| [`docs/AUDIT_AND_UPGRADE_PLAN.md`](docs/AUDIT_AND_UPGRADE_PLAN.md) | 现网实盘审计报告、6 大根因缺陷与两阶段升级方案（含手动操作清单） |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | 系统架构图、模块依赖与失败策略 |
| [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) | 部署、真实表结构、CLI/Cron 与运维手册 |
| [`docs/STATUS.md`](docs/STATUS.md) | 当前进度、待办队列与开发日志 |
| [`docs/reference/wecom_openapi.md`](docs/reference/wecom_openapi.md) | 企业微信 OpenAPI 契约与当前代码实现对照表 |
| [`docs/reference/wecom_live_inventory.md`](docs/reference/wecom_live_inventory.md) | 企业微信现网考勤模块只读盘点（2026-11-29 实测模板 ID / 规则 / 权限） |
| [`docs/proposals/`](docs/proposals/) | 待立项与远期预研（F16 假期台账重建、多模态/LLM 预研） |
| [`docs/archive/`](docs/archive/) | 历史与旧版 v2 脚手架归档（只读） |

## 快速开始

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # 填入真实凭证，禁止提交 .env
```

## 常用命令

```bash
# CLI 帮助与任务执行
PYTHONPATH=src python -m attendance_audit_integration.cli --help

# 单元测试（含架构图↔代码溯源对账门禁）
PYTHONPATH=src pytest -m unit

# 脱敏自检诊断包
PYTHONPATH=src python -m attendance_audit_integration.diagnostics
```
