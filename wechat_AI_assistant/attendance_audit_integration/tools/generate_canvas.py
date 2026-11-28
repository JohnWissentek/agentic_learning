#!/usr/bin/env python3
"""生成真正的 Obsidian Canvas 文件：每个模块/函数=独立卡片，连接用 edges，分组用 groups。

Canvas JSON 格式：
  nodes: [{id, type:"text"|"group", x, y, width, height, text, color?, label?}]
  edges: [{id, fromNode, toNode, fromSide, toSide, label?, color?}]

颜色约定（Obsidian 预设 1-6）：
  1=红(入口)  2=橙(服务)  3=黄(注释)  4=绿(工具)  5=青(基础)  6=紫(外部)

拆图约定（`code_dev_audit_framework_v2` 框架总纲 3.1/3.3，2026-07-14 对齐）：
  一图一文件，与 ARCHITECTURE.md 的每张 Mermaid 图一一对应；单图 ≤12 卡片、≤15 连线、
  单卡片连线数(进+出) ≤6；总图把子系统黑盒化为单卡片（标注"📦详见 X"），细节放子图。
"""
import json
from pathlib import Path

CANVAS_DIR = Path(__file__).resolve().parent.parent / "docs" / "canvas"


def _node(nid, text, x, y, w=250, h=60, color=None):
    n = {"id": nid, "type": "text", "x": x, "y": y, "width": w, "height": h, "text": text}
    if color:
        n["color"] = str(color)
    return n


def _group(gid, label, x, y, w, h, color=None):
    g = {"id": gid, "type": "group", "x": x, "y": y, "width": w, "height": h, "label": label}
    if color:
        g["color"] = str(color)
    return g


def _edge(eid, src, dst, label="", from_side="bottom", to_side="top", color=None):
    e = {"id": eid, "fromNode": src, "toNode": dst, "fromSide": from_side, "toSide": to_side}
    if label:
        e["label"] = label
    if color:
        e["color"] = str(color)
    return e


def _note(nid, text, x, y, w=300, h=100):
    """📖 图解注释卡片（黄色）。框架总纲 3.3：Canvas 侧游离的图解文字卡不计入复杂度红线。"""
    return _node(nid, text, x, y, w, h, color=3)


# ═══════════════════════════════════════════════════════════════════
# Canvas 01：系统上下文图（ARCHITECTURE §2）
# ═══════════════════════════════════════════════════════════════════
def build_system_context():
    nodes = [
        _node("trigger", "⏰ **触发源 Trigger**\nCron 定时器 / 管理员手动", -400, -50, 280, 70, color=6),
        _node("app", "🖥️ **AttendanceAuditEngine**\n考勤审计系统（本程序）", -20, -50, 350, 80, color=1),
        _node("wecom", "☁️ **企业微信 OpenAPI**\n打卡/审批/成员/日报", 430, -220, 280, 70, color=6),
        _node("db", "🗄️ **PostgreSQL**\n业务数据持久化", 430, -50, 250, 70, color=6),
        _node("smtp", "📧 **企业邮箱 SMTP**\n告警邮件 & 审计报表", 430, 130, 280, 70, color=6),
        _node("roster", "📋 **本地花名册 JSON**\nemployee_roster.json", -400, 130, 280, 70, color=6),
        _note("note_gps",
              "📌 花名册已改本地 JSON\n代码/脚本禁止再读 xlsx",
              -400, 260, 280, 70),
        _note("note1",
              "📖 **图解**\n\n触发源（Cron 或管理员）启动本程序；\n"
              "程序对外只做四件事：向企微「要」数据、\n"
              "往数据库「写」业务数据、用邮件「发」\n"
              "告警与报表、从本地花名册 JSON「导入」\n"
              "姓名邮箱映射。企微 Webhook 是可选的\n反向回调，不是必须依赖。",
              -20, 260, 350, 200),
    ]
    edges = [
        _edge("e1", "trigger", "app", "触发运行"),
        _edge("e2", "app", "wecom", "拉取打卡与审批", "right", "left"),
        _edge("e3", "app", "db", "读写业务数据", "right", "left"),
        _edge("e4", "app", "smtp", "发送告警与报表", "right", "left"),
        _edge("e5", "wecom", "app", "可选Webhook回调", "left", "right"),
        _edge("e6", "roster", "app", "导入姓名邮箱", "right", "left"),
    ]
    return {"nodes": nodes, "edges": edges}


# ═══════════════════════════════════════════════════════════════════
# Canvas 02 系列：模块结构图（ARCHITECTURE §3，9 张小图，与新复杂度红线对齐）
# ═══════════════════════════════════════════════════════════════════
def build_module_overview():
    """§3.0 总图：入口层（main/cli/mock/diagnostics）自身依赖"""
    nodes = [
        _group("g_entry", "入口层", -420, -260, 900, 160),
        _node("main", "**main.py**\n入口：调度审计/收Webhook", -390, -220, 260, 60, color=1),
        _node("cli", "**cli.py**\n入口：命令行触发", -90, -220, 220, 60, color=1),
        _node("mock", "**mock_data_populator.py**\n测试数据填充:真实优先", 180, -220, 260, 60, color=4),
        _node("diag", "**diagnostics.py**\n诊断包导出", 480, -220, 220, 60, color=4),
        _node("facade", "**audit_engine.py**\n门面 📦分发详见02a/re-export详见02b", -90, -60, 420, 60, color=2),
        _group("g_base", "入口自身底座", -420, 60, 900, 160),
        _node("config", "**config.py**", -390, 100, 160, 55, color=5),
        _node("db", "**db.py**", -190, 100, 140, 55, color=5),
        _node("logger", "**logger.py**", -10, 100, 140, 55, color=5),
        _node("mail", "**mail_sender.py**", 170, 100, 200, 55, color=5),
        _node("wxbiz", "**wxbiz_msg_crypt.py**\n回调加解密", 410, 100, 240, 55, color=4),
        _note("note_ov",
              "📖 **总图**\n\n只画 main/cli/mock/diagnostics 自己\n直接碰的模块。业务分发（门面→5个\nservice）见 02a；工具 re-export 见 02b。\n各 service 内部依赖见 02c–02h。",
              780, -260, 300, 200),
    ]
    edges = [
        _edge("e_m2f", "main", "facade", "调度"),
        _edge("e_c2f", "cli", "facade", "命令行触发"),
        _edge("e_m2wx", "main", "wxbiz", "解密验签", "right", "left"),
        _edge("e_m2cf", "main", "config", "读配置", "bottom", "top"),
        _edge("e_m2db", "main", "db", "读写库", "bottom", "top"),
        _edge("e_m2lg", "main", "logger", "打日志", "bottom", "top"),
        _edge("e_m2ml", "main", "mail", "发邮件", "bottom", "top"),
        _edge("e_c2cf", "cli", "config", "读配置", "bottom", "top"),
        _edge("e_c2db", "cli", "db", "初始化库", "bottom", "top"),
        _edge("e_c2lg", "cli", "logger", "打日志", "bottom", "top"),
        _edge("e_mk2db", "mock", "db", "写场景缺口+溯源标记", "bottom", "top"),
        _edge("e_mk2f", "mock", "facade", "复用真实拉取/工作日判定", "left", "right"),
        _edge("e_mk2lg", "mock", "logger", "打日志", "bottom", "top"),
        _edge("e_dg2lg", "diag", "logger", "打包摘要", "bottom", "top"),
    ]
    return {"nodes": nodes, "edges": edges}


def build_module_facade_dispatch():
    """§3.0a：门面 → 5 个 Service 分发"""
    nodes = [
        _node("facade", "**audit_engine.py**\n门面", 260, -40, 220, 60, color=2),
        _node("daily", "**services/daily_audit.py**\n📦详见02c/02d", -60, 100, 260, 60, color=2),
        _node("weekly", "**services/weekly_audit.py**\n📦详见02g", 220, 100, 240, 60, color=2),
        _node("monthly", "**services/monthly_audit.py**\n📦详见02e/02f", 480, 100, 260, 60, color=2),
        _node("expiry", "**services/expiry_checker.py**\n📦详见02g", 740, 100, 260, 60, color=2),
        _node("roster_svc", "**services/roster_sync.py**\n📦详见02d", 1000, 100, 240, 60, color=2),
        _note("note_a", "📖 **门面分发**\n\n5 类审计任务各自代理给独立\nservice 文件；Services 之间\n互不调用（无横向依赖）。",
              260, 200, 300, 130),
    ]
    edges = [
        _edge("f1", "facade", "daily", "代理日审"),
        _edge("f2", "facade", "weekly", "代理周审"),
        _edge("f3", "facade", "monthly", "代理月审"),
        _edge("f4", "facade", "expiry", "代理调休检查"),
        _edge("f5", "facade", "roster_svc", "代理花名册同步"),
    ]
    return {"nodes": nodes, "edges": edges}


def build_module_facade_reexport():
    """§3.0b：门面 re-export 工具函数"""
    nodes = [
        _node("facade", "**audit_engine.py**\n门面", 260, -40, 220, 60, color=2),
        _node("geo", "**geo.py**\nHaversine距离计算", -40, 100, 240, 55, color=4),
        _node("holiday", "**holiday.py**\n工作日/法定假判定", 220, 100, 260, 55, color=4),
        _node("comp", "**compensatory.py**\n调休入账决策", 500, 100, 240, 55, color=4),
        _node("payroll", "**payroll_cycle.py**\n薪资周期/封账", 760, 100, 240, 55, color=4),
        _note("note_b", "📖 **工具 re-export**\n\n门面把 4 个纯函数工具模块原样导出，\n向后兼容重构前的旧 import 路径。",
              260, 190, 340, 100),
    ]
    edges = [
        _edge("r1", "facade", "geo", "re-export"),
        _edge("r2", "facade", "holiday", "re-export"),
        _edge("r3", "facade", "comp", "re-export"),
        _edge("r4", "facade", "payroll", "re-export"),
    ]
    return {"nodes": nodes, "edges": edges}


def build_module_daily_business_deps():
    """§3.1：日审业务依赖"""
    nodes = [
        _node("daily", "**services/daily_audit.py**\n日审业务流程", 200, -40, 280, 60, color=2),
        _node("wecom", "**wecom_api.py**", -80, 120, 220, 55, color=5),
        _node("geo", "**geo.py**", 180, 120, 180, 55, color=4),
        _node("holiday", "**holiday.py**", 400, 120, 200, 55, color=4),
        _node("roster_svc", "**services/roster_sync.py**\n📦详见02d", 620, 120, 260, 60, color=2),
        _note("note_a", "📖 **子图**\n\n日审业务侧依赖：拉打卡、瞬移检测、\n工作日判定，并先调 roster_sync 确保\n花名册最新。基础设施依赖见 02d。",
              200, 240, 320, 130),
    ]
    edges = [
        _edge("a1", "daily", "wecom", "拉取企微数据"),
        _edge("a2", "daily", "geo", "距离计算"),
        _edge("a3", "daily", "holiday", "工作日判定"),
        _edge("a4", "daily", "roster_svc", "调用花名册同步"),
    ]
    return {"nodes": nodes, "edges": edges}


def build_module_daily_infra_deps():
    """§3.1b：日审 + 花名册同步的基础设施依赖"""
    nodes = [
        _node("daily", "**services/daily_audit.py**", -80, -40, 260, 55, color=2),
        _node("roster_svc", "**services/roster_sync.py**\n花名册同步", 340, -40, 280, 55, color=2),
        _node("mail", "**mail_sender.py**", -220, 120, 200, 55, color=5),
        _node("db", "**db.py**", -20, 120, 140, 55, color=5),
        _node("logger", "**logger.py**", 140, 120, 150, 55, color=5),
        _node("config", "**config.py**", -140, 220, 160, 55, color=5),
        _node("wecom", "**wecom_api.py**", 320, 120, 200, 55, color=5),
        _node("roster", "**roster.py**\n读JSON花名册", 540, 120, 220, 55, color=5),
        _note("note_ab", "📖 **子图**\n\ndaily_audit 通过基础设施四件套\n落地异常邮件与数据；roster_sync\n还依赖 wecom_api（拉通讯录）和\nroster（读本地 JSON 花名册）。",
              600, -40, 320, 150),
    ]
    edges = [
        _edge("b1", "daily", "mail", "发邮件"),
        _edge("b2", "daily", "db", "读写库"),
        _edge("b3", "daily", "logger", "打日志"),
        _edge("b4", "daily", "config", "读配置", "bottom", "left"),
        _edge("b5", "roster_svc", "wecom", "拉取企微通讯录", "left", "top"),
        _edge("b6", "roster_svc", "roster", "读JSON花名册"),
        _edge("b7", "roster_svc", "db", "读写库", "bottom", "top"),
        _edge("b8", "roster_svc", "logger", "打日志", "bottom", "top"),
        _edge("b9", "roster_svc", "config", "读配置", "bottom", "right"),
    ]
    return {"nodes": nodes, "edges": edges}


def build_module_monthly_business_deps():
    """§3.2：月审业务依赖"""
    nodes = [
        _node("monthly", "**services/monthly_audit.py**\n月审业务流程", 220, -40, 300, 60, color=2),
        _node("comp", "**compensatory.py**\n调休入账决策", -60, 120, 240, 55, color=4),
        _node("payroll", "**payroll_cycle.py**\n📦infra详见02f", 220, 120, 240, 60, color=4),
        _node("holiday", "**holiday.py**\n📦infra详见02f", 500, 120, 220, 60, color=4),
        _node("mail", "**mail_sender.py**", 760, 120, 200, 55, color=5),
        _note("note_b", "📖 **子图**\n\n月审的特有依赖：compensatory（调休\n入账决策）+ payroll_cycle（周期与\n封账），复用 holiday 判定法定假。\n三者自身的基础设施依赖见 02f。",
              220, 220, 340, 140),
    ]
    edges = [
        _edge("c1", "monthly", "comp", "调休决策"),
        _edge("c2", "monthly", "payroll", "周期与封账"),
        _edge("c3", "monthly", "holiday", "法定假判定"),
        _edge("c4", "monthly", "mail", "发邮件"),
    ]
    return {"nodes": nodes, "edges": edges}


def build_module_monthly_infra_deps():
    """§3.2b：月审 + holiday/payroll_cycle 的基础设施依赖"""
    nodes = [
        _node("monthly", "**services/monthly_audit.py**", -60, -40, 280, 55, color=2),
        _node("holiday", "**holiday.py**", 340, -40, 200, 55, color=4),
        _node("payroll", "**payroll_cycle.py**", 640, -40, 220, 55, color=4),
        _node("db", "**db.py**", -60, 120, 160, 55, color=5),
        _node("config", "**config.py**", 140, 120, 160, 55, color=5),
        _node("logger", "**logger.py**", 340, 120, 160, 55, color=5),
        _node("mail", "**mail_sender.py**\n年底维护提醒", 540, 120, 240, 55, color=5),
        _note("note_bb", "📖 **子图**\n\nholiday 自身也依赖 db（存节假日表）\n和 mail_sender（每年 12-31 提醒徐宏玮\n维护下一年日历）；payroll_cycle 只\n打日志，是最轻的工具模块。",
              640, 60, 320, 150),
    ]
    edges = [
        _edge("d1", "monthly", "db", "读写库"),
        _edge("d2", "monthly", "config", "读配置"),
        _edge("d3", "monthly", "logger", "打日志", "bottom", "left"),
        _edge("d4", "holiday", "db", "读写库", "left", "top"),
        _edge("d5", "holiday", "config", "读配置", "bottom", "top"),
        _edge("d6", "holiday", "logger", "打日志", "bottom", "right"),
        _edge("d7", "holiday", "mail", "年底提醒", "right", "left"),
        _edge("d8", "payroll", "logger", "打日志", "left", "top"),
    ]
    return {"nodes": nodes, "edges": edges}


def build_module_weekly_expiry_deps():
    """§3.3a：周审 + 调休催用的业务与邮件依赖"""
    nodes = [
        _node("weekly", "**services/weekly_audit.py**\n周审业务流程", -60, -40, 260, 60, color=2),
        _node("expiry", "**services/expiry_checker.py**\nF11调休催用", 340, -40, 280, 60, color=2),
        _node("payroll", "**payroll_cycle.py**", -60, 120, 220, 55, color=4),
        _node("mail", "**mail_sender.py**\n催用仅TO孔紫初/王楠", 220, 120, 280, 55, color=5),
        _node("db", "**db.py**", 560, 120, 150, 55, color=5),
        _node("config", "**config.py**", -60, 220, 160, 55, color=5),
        _node("logger", "**logger.py**", 140, 220, 160, 55, color=5),
        _note("note_c", "📖 **子图**\n\n周审和调休催用是最轻的两个 service，\n各自只依赖 mail_sender+db+config+\nlogger 四件基础设施；催用收件人规则\n见 PRD §4.2 第 6 条。基础设施彼此\n的内部依赖见 02h。",
              560, 200, 340, 170),
    ]
    edges = [
        _edge("e1", "weekly", "payroll", "周期计算"),
        _edge("e2", "weekly", "mail", "发邮件", "right", "left"),
        _edge("e3", "weekly", "db", "读写库", "right", "left"),
        _edge("e4", "weekly", "config", "读配置", "bottom", "left"),
        _edge("e5", "weekly", "logger", "打日志", "bottom", "left"),
        _edge("e6", "expiry", "mail", "催用邮件仅TO孔紫初/王楠", "left", "right"),
        _edge("e7", "expiry", "db", "读写库", "bottom", "right"),
        _edge("e8", "expiry", "config", "读配置", "bottom", "right"),
        _edge("e9", "expiry", "logger", "打日志", "bottom", "right"),
    ]
    return {"nodes": nodes, "edges": edges}


def build_module_infra_internal():
    """§3.3b：基础设施模块内部依赖"""
    nodes = [
        _node("roster", "**roster.py**\n读JSON花名册", -280, -40, 220, 55, color=5),
        _node("wecom", "**wecom_api.py**\n企微HTTP+重试", -20, -40, 240, 55, color=5),
        _node("mail", "**mail_sender.py**\n模板渲染+SMTP", 260, -40, 240, 55, color=5),
        _node("db", "**db.py**\nPostgreSQL读写", 540, -40, 220, 55, color=5),
        _node("config", "**config.py**", 100, 100, 180, 55, color=5),
        _node("logger", "**logger.py**", 100, 220, 180, 55, color=5),
        _note("note_d", "📖 **子图**\n\n所有基础设施模块统一通过 config\n读配置、通过 logger 打日志；config\n自身只依赖 logger。所有依赖方向\n严格从上到下，无环——这是 02–02h\n九张图共同遵守的铁律，\ntools/check_traceability.py 会自动\n检测循环依赖。",
              540, 100, 340, 220),
    ]
    edges = [
        _edge("g1", "roster", "config", "读配置", "right", "left"),
        _edge("g2", "roster", "logger", "打日志", "bottom", "top"),
        _edge("g3", "wecom", "config", "读配置"),
        _edge("g4", "wecom", "logger", "打日志", "bottom", "top"),
        _edge("g5", "mail", "config", "读配置", "left", "right"),
        _edge("g6", "mail", "logger", "打日志", "bottom", "top"),
        _edge("g7", "db", "config", "读配置", "left", "right"),
        _edge("g8", "db", "logger", "打日志", "bottom", "right"),
        _edge("g9", "config", "logger", "打日志"),
    ]
    return {"nodes": nodes, "edges": edges}


# ═══════════════════════════════════════════════════════════════════
# Canvas 03 系列：核心流程与审计规则（ARCHITECTURE §4）
# ═══════════════════════════════════════════════════════════════════
def build_daily_audit_flow():
    """§4.1 日审总流程 + §4.2 单人判定总图（黑盒节点承接 4.2a）"""
    nodes = [
        _node("d_cron", "🕙 **Cron 触发**\n每天09:00,对象=昨日T-1", -60, -40, 230, 55, color=1),
        _node("d_pull", "📥 **拉取企微**\nT-1打卡+已通过审批", 220, -40, 230, 55, color=2),
        _node("d_match", "🔄 **逐人勾稽 📦**\n详见 03a 防作弊子图\n+ 请假/出差/工作日判定", 500, -40, 260, 75, color=2),
        _node("d_punches", "🔢 **打卡条数判定**\n0/1条=缺卡；≥2条=正常", 500, 80, 260, 60, color=4),
        _node("d_persist", "💾 **UPSERT daily_attendance**\n幂等键=userid+日期", 220, 80, 260, 55, color=5),
        _node("d_anomaly_mail", "📧 **个人异常邮件**\n截止T+2当日18:00", 500, 190, 260, 55, color=5),
        _node("d_summary", "📊 **公司日汇总邮件**\n→ ADMIN", 220, 190, 230, 55, color=5),
        _note("note_daily",
              "📖 **图解**\n\n每天09:00对昨天做勾稽：防作弊/请假/\n出差/工作日判定黑盒化，详见03a；\n工作日才数打卡条数，0/1条触发个人\n异常邮件，最终无论有无异常都汇总\n成公司日报。",
              -60, 100, 380, 200),
    ]
    edges = [
        _edge("ed1", "d_cron", "d_pull", "拉取"),
        _edge("ed2", "d_pull", "d_match", "成功"),
        _edge("ed3", "d_match", "d_punches", "工作日才数打卡"),
        _edge("ed4", "d_match", "d_persist", "写库", "bottom", "top"),
        _edge("ed5", "d_punches", "d_anomaly_mail", "0或1条", "bottom", "top"),
        _edge("ed6", "d_persist", "d_summary", "汇总", "bottom", "top"),
        _edge("ed7", "d_anomaly_mail", "d_summary", "汇总", "left", "right"),
    ]
    return {"nodes": nodes, "edges": edges}


def build_monthly_close_and_recall():
    """§4.5 月审与封账（复合校验黑盒承接 4.4）+ F11 调休催用（4.4 尾段）"""
    nodes = [
        _node("m_start", "🚀 **月审入口**\ncli monthly [--final]", -60, -40, 230, 55, color=1),
        _node("m_range", "📅 **周期计算**\n上月26日→本月25日", 220, -40, 230, 55, color=4),
        _node("m_locked", "🔒 **封账检查**\nis_payroll_period_locked()", 500, -40, 260, 55, color=4),
        _node("m_reject", "❌ **拒绝重复终审**\nRuntimeError E18", 500, 60, 230, 55, color=1),
        _node("m_compound", "🔍 **复合校验 📦**\n加班→调休(见4.4)+出差日报\n水印(E7)+旷工折算", 820, -40, 280, 75, color=2),
        _node("m_report", "📊 **终审邮件+封账**\nrender→lock→发送→ADMIN", 820, 80, 280, 55, color=5),
        _node("f11_release", "⚖️ **调休入账**\n非法定假+客户签字→released", 220, 200, 280, 55, color=4),
        _node("f11_chk", "⏰ **催用时钟**\n第7/15/30天仍有剩余", 550, 200, 260, 55, color=2),
        _node("f11_to", "📧 **TO孔紫初、王楠**\n❌禁止发/抄送被催员工", 850, 200, 300, 55, color=1),
        _note("note_monthly",
              "📖 **图解**\n\n账期永远是「上月26号到本月25号」，\n25号草稿、26号终审；终审先查有没有\n重复上锁（有则拒绝，E18），复合校验\n（加班转调休见4.4+出差日报+旷工）\n黑盒化。调休入账后进入催用时钟：\n第7/15/30天仍有剩余才催，只发孔紫\n初、王楠，禁止发给或抄送被催员工\n本人。",
              -60, 100, 400, 260),
    ]
    edges = [
        _edge("em1", "m_start", "m_range", "算周期"),
        _edge("em2", "m_range", "m_locked", "判类型"),
        _edge("em3", "m_locked", "m_reject", "已锁:拒绝", "bottom", "top"),
        _edge("em4", "m_locked", "m_compound", "未锁:放行", "right", "left"),
        _edge("em5", "m_compound", "m_report", "汇总", "bottom", "top"),
        _edge("ef1", "f11_release", "f11_chk", "起算accrual_date"),
        _edge("ef2", "f11_chk", "f11_to", "催用邮件"),
    ]
    return {"nodes": nodes, "edges": edges}


def build_daily_anti_fraud():
    """§4.2a：防作弊检测 F2 内部逻辑（对应 4.2 总图 📦 节点）"""
    nodes = [
        _node("in", "⬅️ **入口：来自4.2📦**\n输入：员工T-1打卡记录", -60, -40, 280, 55, color=1),
        _node("chk_dev", "❓ **设备异常?**\nexception_type非空且非未打卡", 300, -40, 260, 60, color=4),
        _node("dev", "⚠️ **device_anomaly E11**", 620, -40, 240, 50, color=2),
        _node("chk_loc", "❓ **位置异常?**\n相邻打卡时速>350km/h", 300, 80, 260, 60, color=4),
        _node("loc", "⚠️ **location_anomaly E12**", 620, 80, 240, 50, color=2),
        _node("chk_ip", "❓ **可疑IP?**\n外勤IP与申报地不符", 300, 200, 260, 60, color=4),
        _node("ip", "⚠️ **E13 可疑日志**\n不单独否决日状态", 620, 200, 240, 50, color=2),
        _node("out", "➡️ **出口：返回4.2**\n输出：打标记后的打卡记录", 940, 80, 280, 55, color=1),
        _note("note_2a",
              "📖 **图解**\n\n"
              "三道独立检查依次走：设备异常（企微\n上报的exception_type）、位置异常\n（相邻打卡时速超350km/h=瞬移）、\n可疑IP（外勤IP与申报地不符）。三道\n检查互不阻断——查到异常只打标记\n继续走，不会让流程中断，最终交回\n4.2总图主线继续判定请假/出差/工作日。\n\n审核要点：E13明确标注「不单独否决\n日状态」，避免误伤正常外勤。",
              300, 300, 400, 220),
    ]
    edges = [
        _edge("i1", "in", "chk_dev", "先查设备"),
        _edge("i2", "chk_dev", "dev", "是:打标记"),
        _edge("i3", "chk_dev", "chk_loc", "否/标记后", "bottom", "top"),
        _edge("i4", "dev", "chk_loc", "标记后继续", "bottom", "top"),
        _edge("i5", "chk_loc", "loc", "是:打标记"),
        _edge("i6", "chk_loc", "chk_ip", "否/标记后", "bottom", "top"),
        _edge("i7", "loc", "chk_ip", "标记后继续", "bottom", "top"),
        _edge("i8", "chk_ip", "ip", "是:记可疑日志"),
        _edge("i9", "chk_ip", "out", "否/记录后", "right", "left"),
        _edge("i10", "ip", "out", "记录后继续", "right", "left"),
    ]
    return {"nodes": nodes, "edges": edges}


def build_gps_fence():
    """§4.3：外勤 GPS 围栏（含 200 米硬阈值）"""
    nodes = [
        _node("need", "📍 **外勤/出差打卡**\n须有审批锁定目的地\n坐标系GCJ-02", -60, -40, 260, 70, color=1),
        _node("punch", "📌 **打卡点lat/lng**\n企微微度须÷1e6", 260, -40, 240, 60, color=4),
        _node("dest", "🎯 **审批单目的地lat/lng**\n腾讯地图POI锁定", 560, -40, 260, 60, color=4),
        _node("dist", "📏 **Haversine大圆距离**\n单位:米,地球半径6371km", 860, -40, 260, 60, color=4),
        _node("gate", "❓ **distance_m ≤ 200?**", 860, 80, 240, 55, color=2),
        _node("valid", "✅ **判定:有效valid**\n计入出勤勾稽", 660, 180, 220, 55, color=5),
        _node("invalid", "❌ **判定:无效invalid E14**\n无100~500m人工审中间带", 1000, 180, 280, 55, color=1),
        _note("note_43",
              "📖 **图解**\n\n"
              "只认200米以内的外勤打卡；超过半寸\n都不行，没有「再远一点找主管」的\n缓冲带。计算方法：打卡坐标(企微原始\n微度需÷1e6换算) vs 审批单锁定的\n目的地坐标，用Haversine大圆距离\n公式算出米数，200米是唯一硬阈值。\n\n⚠ 本图对应PRD F13，属二期功能，\n一期不做强校验，仅记录距离供人工\n参考。",
              -60, 100, 380, 220),
    ]
    edges = [
        _edge("g1", "need", "punch", "打卡"),
        _edge("g2", "punch", "dest", "对照"),
        _edge("g3", "dest", "dist", "计算距离"),
        _edge("g4", "dist", "gate", "判定"),
        _edge("g5", "gate", "valid", "是≤200m", "left", "top"),
        _edge("g6", "gate", "invalid", "否>200m", "right", "top"),
    ]
    return {"nodes": nodes, "edges": edges}


def build_absence_appeal():
    """§4.6：缺卡申诉与旷工（含 T+2 18:00 与折算）"""
    nodes = [
        _node("miss", "🔍 **日审检出absent/late**\n审计日=T-1,邮件日≈T09:00后", -60, -40, 280, 60, color=1),
        _node("mail", "📧 **个人催告邮件**\n截止:T+2当日18:00", 280, -40, 260, 55, color=5),
        _node("win", "❓ **截止前是否办妥?**", 640, -40, 240, 55, color=2),
        _node("leave_ok", "✅ **转请假抵扣 E15**\n不再按旷工", 940, -140, 240, 55, color=5),
        _node("unpaid", "💰 **事假扣薪参考 E16**\n月薪÷21.75×缺勤天数", 940, -40, 260, 55, color=5),
        _node("absent_mark", "❌ **确认旷工记录 E17**\nlate=0.5天,absent=1.0天", 940, 60, 280, 55, color=1),
        _note("note_46",
              "📖 **图解**\n\n"
              "系统9点左右报昨天的缺卡，给到后天\n傍晚6点补手续。三条出口：年假/调休\n审批通过→转请假抵扣，不算旷工；\n事假审批→扣薪不罚款（月薪÷21.75×\n缺勤天数，禁止多倍扣款）；逾期什么\n审批都没有→确认旷工，单侧缺卡记\n0.5天、全日无卡记1.0天。",
              -60, 140, 380, 200),
    ]
    edges = [
        _edge("h1", "miss", "mail", "催告"),
        _edge("h2", "mail", "win", "等待"),
        _edge("h3", "win", "leave_ok", "年假/调休审批通过", "right", "left"),
        _edge("h4", "win", "unpaid", "事假审批", "right", "left"),
        _edge("h5", "win", "absent_mark", "逾期无审批", "right", "left"),
    ]
    return {"nodes": nodes, "edges": edges}


# ═══════════════════════════════════════════════════════════════════
# Canvas 04 系列：函数调用关系图（ARCHITECTURE §5）
# ═══════════════════════════════════════════════════════════════════
def build_function_calls_overview():
    """§5.0 总图：CLI 分发（鸟瞰），不含各命令内部调用链"""
    nodes = [
        _node("cli", "🚀 **cli.main()**\n命令行总入口", 200, -280, 240, 60, color=1),
        _group("g_dispatch", "CLI 分发目标（各命令内部见 04a/04b/04c）", -200, -120, 1000, 160),
        _node("fn_daily", "**run_daily_audit()**\n日审 → 04a", -170, -80, 220, 55, color=2),
        _node("fn_weekly", "**run_weekly_audit()**\n周审 → 04c", 80, -80, 220, 55, color=2),
        _node("fn_monthly", "**run_monthly_audit()**\n月审 → 04b", 330, -80, 230, 55, color=2),
        _node("fn_expiry", "**check_compensatory_leave_expiry()**\n调休催用 → 04c", 590, -80, 300, 55, color=2),
        _node("fn_sync", "**sync_employee_roster()**\nsync-roster", -170, 20, 250, 55, color=2),
        _node("fn_initdb", "**db.init_db()**\ninit-db", 330, 20, 180, 55, color=5),
        _note(
            "note_ov",
            "📖 **总图**\n\n"
            "cli.main() 按子命令分发，\n"
            "各命令互不交叉调用。\n"
            "详情：04a 日审 / 04b 月审 / 04c 周审+催用",
            820,
            -280,
            300,
            180,
        ),
    ]
    edges = [
        _edge("ec1", "cli", "fn_daily", "daily"),
        _edge("ec2", "cli", "fn_weekly", "weekly"),
        _edge("ec3", "cli", "fn_monthly", "monthly"),
        _edge("ec4", "cli", "fn_expiry", "check-expiry"),
        _edge("ec5", "cli", "fn_sync", "sync-roster", "bottom", "top"),
        _edge("ec6", "cli", "fn_initdb", "init-db", "bottom", "top"),
    ]
    return {"nodes": nodes, "edges": edges}


def build_function_daily_chain():
    """§5.1 子图 A：日审调用链（render_anomaly + render_daily 合并为 render_mail，控制度≤6）"""
    nodes = [
        _group("g_a", "子图 A：日审调用链", -100, -80, 780, 520),
        _node("fn_daily", "**run_daily_audit()**", 200, -40, 240, 55, color=2),
        _node("fn_sync", "**sync_employee_roster()**", -60, 80, 250, 55, color=2),
        _node("fn_fetch", "**fetch_punches()**", 240, 80, 220, 55, color=5),
        _node("fn_haver", "**calculate_haversine_distance()**", 500, 80, 260, 55, color=4),
        _node("fn_iswork", "**is_workday_db()**", 500, 180, 220, 55, color=4),
        _node("fn_render", "**render_individual_anomaly_email()**\n+ render_daily_summary_email()", 200, 200, 320, 65, color=5),
        _node("fn_send", "**send_html_email()**", 200, 320, 220, 55, color=5),
        _node("fn_fuser", "**fetch_users()**", -60, 200, 200, 55, color=5),
        _node("fn_loadr", "**load_employee_roster()**", -60, 300, 230, 55, color=5),
        _node("fn_retry", "**_retry_request()**\n1s→2s→4s ×3", -60, 400, 220, 60, color=5),
        _note(
            "note_a",
            "📖 **日审链**\n\n同步花名册 → 拉打卡 →\n工作日+瞬移 → 渲染异常/日报邮件 →\n统一发送。企微 HTTP 统一走重试。",
            820,
            -40,
            280,
            160,
        ),
    ]
    edges = [
        _edge("d1", "fn_daily", "fn_sync", "先同步", "left", "top"),
        _edge("d2", "fn_daily", "fn_fetch", "拉打卡"),
        _edge("d3", "fn_daily", "fn_haver", "瞬移检测", "right", "top"),
        _edge("d4", "fn_daily", "fn_iswork", "工作日", "right", "left"),
        _edge("d5", "fn_daily", "fn_render", "渲染异常/日报邮件"),
        _edge("d6", "fn_daily", "fn_send", "发送邮件", "bottom", "left"),
        _edge("d7", "fn_sync", "fn_fuser", "拉通讯录"),
        _edge("d8", "fn_sync", "fn_loadr", "读 JSON"),
        _edge("d9", "fn_fetch", "fn_retry", "重试", "left", "top"),
        _edge("d10", "fn_fuser", "fn_retry", "重试"),
    ]
    return {"nodes": nodes, "edges": edges}


def build_function_monthly_chain():
    """§5.2 子图 B：月审调用链"""
    nodes = [
        _group("g_b", "子图 B：月审调用链", -80, -80, 720, 480),
        _node("fn_monthly", "**run_monthly_audit()**", 180, -40, 260, 55, color=2),
        _node("fn_cycle", "**get_monthly_cycle_range()**", -40, 80, 260, 55, color=4),
        _node("fn_lock", "**is_payroll_period_locked()**", 260, 80, 260, 55, color=4),
        _node("fn_comp_chk", "**_run_final_compound_checks()**", 180, 180, 300, 55, color=2),
        _node("fn_decide", "**decide_compensatory_accrual()**", -40, 280, 280, 55, color=4),
        _node("fn_stat", "**is_statutory_holiday()**", 280, 280, 240, 55, color=4),
        _node("fn_iswork", "**is_workday_db()**", 280, 360, 220, 55, color=4),
        _node("fn_lockp", "**lock_payroll_period()**", 520, 180, 240, 55, color=4),
        _node("fn_render_m", "**render_monthly_finalized_email()**", 180, 400, 300, 55, color=5),
        _note(
            "note_b",
            "📖 **月审链**\n\n定周期 → 查封账 → 复合校验\n（调休决策+法定假）→ 封账 → 月报。",
            780,
            -40,
            280,
            140,
        ),
    ]
    edges = [
        _edge("m1", "fn_monthly", "fn_cycle", "定周期", "left", "top"),
        _edge("m2", "fn_monthly", "fn_lock", "查封账"),
        _edge("m3", "fn_monthly", "fn_comp_chk", "复合校验"),
        _edge("m4", "fn_comp_chk", "fn_decide", "调休决策", "left", "top"),
        _edge("m5", "fn_comp_chk", "fn_stat", "法定假"),
        _edge("m6", "fn_comp_chk", "fn_iswork", "工作日"),
        _edge("m7", "fn_monthly", "fn_lockp", "终审封账", "right", "left"),
        _edge("m8", "fn_monthly", "fn_render_m", "月报"),
    ]
    return {"nodes": nodes, "edges": edges}


def build_function_weekly_expiry_chain():
    """§5.3 子图 C：周审 + 调休催用"""
    nodes = [
        _group("g_c", "子图 C：周审 + 调休催用", -80, -80, 700, 360),
        _node("fn_weekly", "**run_weekly_audit()**", -40, -40, 240, 55, color=2),
        _node("fn_expiry", "**check_compensatory_leave_expiry()**", 280, -40, 300, 55, color=2),
        _node("fn_cystart", "**get_payroll_cycle_start()**", -40, 80, 260, 55, color=4),
        _node("fn_render_w", "**render_weekly_summary_email()**", -40, 180, 280, 55, color=5),
        _node("fn_send", "**send_html_email()**\n催用 TO: 孔紫初、王楠\n❌ 不发被催员工", 280, 140, 300, 90, color=5),
        _note(
            "note_c",
            "📖 **周审+催用**\n\n周审：周期起点 → 周报 → 发信。\n催用：查库后直接发信给项目经理。",
            640,
            -40,
            280,
            140,
        ),
    ]
    edges = [
        _edge("w1", "fn_weekly", "fn_cystart", "周期起始"),
        _edge("w2", "fn_weekly", "fn_render_w", "渲染周报"),
        _edge("w3", "fn_render_w", "fn_send", "发送", "right", "left"),
        _edge("w4", "fn_expiry", "fn_send", "催用邮件"),
    ]
    return {"nodes": nodes, "edges": edges}


# ═══════════════════════════════════════════════════════════════════
# Canvas 05 系列：参数传递路径图（ARCHITECTURE §6，拆为配置流/数据流）
# ═══════════════════════════════════════════════════════════════════
def build_param_config_flow():
    """§6a：配置参数流（.env → 各模块）"""
    nodes = [
        _node("env", "📄 **.env 文件**\n敏感凭证", -360, -40, 260, 60, color=6),
        _node("settings", "⚙️ **config.Settings**\nPydantic校验", -20, -40, 260, 60, color=5),
        _node("targets", "🎯 **WeComAPIClient/mail_sender/\ndb/services层/roster_sync**\n📦按前缀分发,见下表", 340, -40, 340, 70, color=2),
        _node("cli_args", "💻 **CLI参数**\n--date/--final", -360, 100, 260, 55, color=1),
        _node("cli", "🚀 **cli.main()**", -20, 100, 220, 55, color=1),
        _note("note_cfg",
              "📖 **图解**\n\n敏感凭证（企微密钥、SMTP密码）只在\n.env出现，代码零硬编码；Settings统一\n校验后按字段前缀分发给各模块：\nWECOM_*→WeComAPIClient，SMTP_*→\nmail_sender，DATABASE_URL→db，\nADMIN_EMAILS/EXCLUDED_NAMES→\nservices层，DEFAULT_COMPANY_A/B→\nroster_sync。CLI的--date/--final走\n另一条路径，传入service层控制审计\n目标日和月审类型。",
              340, 80, 340, 260),
    ]
    edges = [
        _edge("e1", "env", "settings", "加载"),
        _edge("e2", "settings", "targets", "按前缀分发"),
        _edge("e3", "cli_args", "cli", "解析", "right", "left"),
        _edge("e4", "cli", "targets", "target_date/is_final传入", "right", "left"),
    ]
    return {"nodes": nodes, "edges": edges}


def build_param_audit_data_flow():
    """§6b：审计数据流（企微 JSON → 落库 → 邮件）"""
    nodes = [
        _node("wecom_json", "📥 **企微打卡JSON**\nraw_payload\n⚠️外来数据不可信", -400, -40, 260, 70, color=6),
        _node("att_logs", "🗄️ **attendance_logs表**", -100, -40, 240, 55, color=5),
        _node("daily_att", "📊 **daily_attendance表**\n日合成", 200, -40, 240, 55, color=2),
        _node("is_anom", "❓ **is_anomaly?**\n日审核心判定点", 500, -40, 220, 55, color=1),
        _node("anom_mail", "📧 **个人异常邮件**", 780, -110, 220, 50, color=5),
        _node("daily_rpt", "📊 **公司日报邮件**", 780, -20, 220, 50, color=5),
        _node("appr_json", "📥 **企微审批JSON**", -100, 100, 240, 50, color=6),
        _node("appr_tbl", "🗄️ **approvals表**", 200, 100, 200, 50, color=5),
        _node("overtime", "⏱️ **加班审批**\n复核见4.4", 500, 100, 220, 55, color=6),
        _node("comp_dtl", "🗄️ **compensatory_leave_details**", 780, 100, 280, 55, color=5),
        _node("vac_bal", "🗄️ **vacation_balances**", 780, 190, 260, 50, color=5),
        _note("note_data",
              "📖 **图解**\n\n企微打卡JSON（外来、不可信）先入\nattendance_logs，逐人勾稽合成\ndaily_attendance；is_anomaly?是日审\n核心判定点——异常发个人邮件，正常\n汇入公司日报。企微审批JSON入\napprovals后可覆盖判定daily_\nattendance（如请假/出差覆盖缺卡\n告警）。加班审批经复核后入\ncompensatory_leave_details，累加进\nvacation_balances余额表。",
              -400, 80, 320, 220),
    ]
    edges = [
        _edge("p1", "wecom_json", "att_logs", "入库"),
        _edge("p2", "att_logs", "daily_att", "逐人勾稽"),
        _edge("p3", "daily_att", "is_anom", "判定"),
        _edge("p4", "is_anom", "anom_mail", "是", "right", "left"),
        _edge("p5", "daily_att", "daily_rpt", "汇总", "right", "left"),
        _edge("p6", "appr_json", "appr_tbl", "入库"),
        _edge("p7", "appr_tbl", "daily_att", "覆盖判定", "top", "bottom"),
        _edge("p8", "overtime", "comp_dtl", "复核", "right", "left"),
        _edge("p9", "comp_dtl", "vac_bal", "余额入账", "bottom", "top"),
    ]
    return {"nodes": nodes, "edges": edges}


def main():
    CANVAS_DIR.mkdir(parents=True, exist_ok=True)

    canvases = {
        "01_system_context.canvas": build_system_context(),
        # §3 模块结构：9 张小图（框架总纲 3.3 复杂度红线：单图 ≤12卡片/≤15连线/度≤6）
        "02_module_structure.canvas": build_module_overview(),
        "02a_module_facade_dispatch.canvas": build_module_facade_dispatch(),
        "02b_module_facade_reexport.canvas": build_module_facade_reexport(),
        "02c_module_daily_business_deps.canvas": build_module_daily_business_deps(),
        "02d_module_daily_infra_deps.canvas": build_module_daily_infra_deps(),
        "02e_module_monthly_business_deps.canvas": build_module_monthly_business_deps(),
        "02f_module_monthly_infra_deps.canvas": build_module_monthly_infra_deps(),
        "02g_module_weekly_expiry_deps.canvas": build_module_weekly_expiry_deps(),
        "02h_module_infra_internal.canvas": build_module_infra_internal(),
        # §4 审计规则：日审流程 + 月审/催用流程 + 2 张补充子图
        "03_audit_rules.canvas": build_daily_audit_flow(),
        "03d_monthly_close_and_recall.canvas": build_monthly_close_and_recall(),
        "03a_daily_anti_fraud.canvas": build_daily_anti_fraud(),
        "03b_gps_fence.canvas": build_gps_fence(),
        "03c_absence_appeal.canvas": build_absence_appeal(),
        # §5 函数调用：总图 + 3 子图
        "04_function_calls.canvas": build_function_calls_overview(),
        "04a_function_daily_chain.canvas": build_function_daily_chain(),
        "04b_function_monthly_chain.canvas": build_function_monthly_chain(),
        "04c_function_weekly_expiry.canvas": build_function_weekly_expiry_chain(),
        # §6 参数传递：拆为配置流/数据流
        "05a_param_config_flow.canvas": build_param_config_flow(),
        "05b_param_audit_data_flow.canvas": build_param_audit_data_flow(),
    }

    for name, data in canvases.items():
        path = CANVAS_DIR / name
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        # 复杂度红线自检(框架总纲 3.3)：📖图解便签卡不计入文本块上限。
        content_nodes = [n for n in data["nodes"] if n.get("type") == "text" and not n["id"].startswith("note")]
        ng = len([n for n in data["nodes"] if n.get("type") == "group"])
        ne = len(data["edges"])
        blocks = len(content_nodes) + ng
        flag = "⚠️ 超红线" if (blocks > 12 or ne > 15) else "✅"
        print(f"{flag} {name}: {len(content_nodes)} 卡片 + {ng} 分组 + {ne} 连线")

    print(f"\n共生成 {len(canvases)} 个 Canvas 到 {CANVAS_DIR}/")


if __name__ == "__main__":
    main()
