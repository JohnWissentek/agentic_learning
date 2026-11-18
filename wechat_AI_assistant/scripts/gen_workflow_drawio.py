"""Generate the 6-stage workflow diagram (draw.io) for wechat_AI_assistant.

Layout rules:
- Stages 1-5 run left to right; stage 6 (scheduled jobs) is a separate lane at the bottom.
- Standard flowchart symbols: rectangle = code step, process-box = LLM call, diamond = decision,
  cylinder = storage, parallelogram = WeChat / email input or output.
- Every edge uses explicit waypoints through empty corridors so no line crosses a card.

Run:  python3 scripts/gen_workflow_drawio.py
Then: draw.io -x -f png|pdf docs/04-AI分拣工作流全景图_A0.drawio
"""

from __future__ import annotations

import html
from pathlib import Path

OUT_PATH = Path(__file__).resolve().parents[1] / "docs" / "04-AI分拣工作流全景图_A0.drawio"
PAGE_W, PAGE_H = 5100, 2820

_TEXT = "whiteSpace=wrap;html=1;fontSize=14;align=left;verticalAlign=top;spacingTop=10;spacingLeft=14;spacingRight=12;"
S_CODE = "rounded=0;fillColor=#dae8fc;strokeColor=#2b6cb0;strokeWidth=2;" + _TEXT
S_LLM = "shape=process;size=0.035;fillColor=#e1d5e7;strokeColor=#6b46c1;strokeWidth=2.5;" + _TEXT.replace("spacingLeft=14", "spacingLeft=30").replace("spacingRight=12", "spacingRight=28")
S_DECISION = "rhombus;whiteSpace=wrap;html=1;fillColor=#fff2cc;strokeColor=#b7950b;strokeWidth=2.5;fontSize=14;fontStyle=1;align=center;verticalAlign=middle;"
S_DB = "shape=cylinder3;boundedLbl=1;backgroundOutline=1;size=14;whiteSpace=wrap;html=1;fillColor=#d5e8d4;strokeColor=#2f855a;strokeWidth=2;fontSize=13;align=center;verticalAlign=middle;"
S_IO = "shape=parallelogram;perimeter=parallelogramPerimeter;size=0.07;fixedSize=0;whiteSpace=wrap;html=1;fillColor=#f5f5f5;strokeColor=#555555;strokeWidth=2;fontSize=13;align=center;verticalAlign=middle;"
S_CARD = S_IO.replace("#f5f5f5", "#ffe6cc").replace("#555555", "#dd6b20")
S_NOTE = "rounded=0;dashed=1;fillColor=#fffbe6;strokeColor=#b7950b;strokeWidth=1.5;" + _TEXT.replace("fontSize=14", "fontSize=13")
S_ZONE = "rounded=0;whiteSpace=wrap;html=1;fillColor=#f8f9fa;strokeColor=#adb5bd;strokeWidth=2;dashed=1;fontSize=18;fontStyle=1;align=left;verticalAlign=top;spacingTop=12;spacingLeft=16;"
S_TERM = "rounded=1;arcSize=50;whiteSpace=wrap;html=1;fillColor=#2d3748;strokeColor=#1a202c;strokeWidth=2;fontSize=15;fontStyle=1;fontColor=#ffffff;align=center;verticalAlign=middle;"
S_CONN = "ellipse;whiteSpace=wrap;html=1;aspect=fixed;fillColor=#ffffff;strokeColor=#dd6b20;strokeWidth=3;fontSize=18;fontStyle=1;fontColor=#dd6b20;align=center;verticalAlign=middle;"
S_TITLE = "text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;fontSize=26;fontStyle=1;"

C_MAIN, C_ROUTE, C_EXEC, C_LOOP, C_READ, C_REPLY = "#2b6cb0", "#6b46c1", "#dd6b20", "#c53030", "#2f855a", "#777777"

cells: list[str] = []


def _label(title: str, body: str = "") -> str:
    inner = f"<b>{html.escape(title)}</b>"
    if body:
        inner += "<br/>" + "<br/>".join(html.escape(x) for x in body.splitlines())
    return html.escape(inner, quote=True)


def node(cid: str, x: int, y: int, w: int, h: int, style: str, title: str, body: str = "") -> None:
    cells.append(
        f'<mxCell id="{cid}" value="{_label(title, body)}" style="{style}" vertex="1" parent="1">'
        f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>'
    )


def text(cid: str, x: int, y: int, w: int, h: int, value: str, style: str) -> None:
    cells.append(
        f'<mxCell id="{cid}" value="{html.escape(value, quote=True)}" style="{style}" vertex="1" parent="1">'
        f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>'
    )


def edge(
    eid: str,
    src: str,
    dst: str,
    label: str,
    color: str,
    *,
    exit_xy: tuple[float, float],
    entry_xy: tuple[float, float],
    points: list[tuple[int, int]] | None = None,
    dashed: bool = False,
    width: float = 2.5,
) -> None:
    style = (
        "edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;endArrow=block;endFill=1;"
        f"exitX={exit_xy[0]};exitY={exit_xy[1]};exitDx=0;exitDy=0;entryX={entry_xy[0]};entryY={entry_xy[1]};entryDx=0;entryDy=0;"
        f"strokeColor={color};strokeWidth={width};{'dashed=1;' if dashed else ''}"
        f"fontSize=13;fontStyle=1;fontColor={color};labelBackgroundColor=#ffffff;"
    )
    pts = ""
    if points:
        pts = '<Array as="points">' + "".join(f'<mxPoint x="{px}" y="{py}"/>' for px, py in points) + "</Array>"
    cells.append(
        f'<mxCell id="{eid}" value="{html.escape(label, quote=True)}" style="{style}" edge="1" parent="1" source="{src}" target="{dst}">'
        f'<mxGeometry relative="1" as="geometry">{pts}</mxGeometry></mxCell>'
    )


# ------------------------------------------------------------------ title & legend
text("title", 40, 22, 2300, 50, "董事长 AI 工作助理 — 六阶段工作流全景图", S_TITLE)
text("subtitle", 40, 70, 2300, 30,
     "每次处理从「开始」单向走到「本次结束」，每条路径都会记录对话；只有阶段五能改待办和看板（必须经你确认）；底部灰色虚线是外层循环",
     "text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;fontSize=15;fontColor=#555555;")
lg_y = 18
node("lg_term", 2360, lg_y + 8, 140, 56, S_TERM, "开始")
node("lg_code", 2520, lg_y, 280, 70, S_CODE, "代码步骤", "确定性执行，不调用大模型")
node("lg_llm", 2820, lg_y, 280, 70, S_LLM, "调用大模型", "标明模型与作用")
node("lg_dec", 3120, lg_y - 4, 190, 78, S_DECISION, "判断")
node("lg_db", 3330, lg_y, 190, 72, S_DB, "数据存储")
node("lg_io", 3540, lg_y, 230, 70, S_IO, "微信 / 邮件 收发")
text("lg_lines", 3790, lg_y, 1270, 72,
     "连线：蓝=主流程　紫=按意图分流　橙=执行落盘　红虚线=审核不通过重写　绿虚线=读取数据　灰虚线=回到微信 / 外层循环　橙色圆圈Ⓐ=同一条线的两端（跨区连接）",
     "rounded=0;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#999999;fontSize=13;align=left;verticalAlign=middle;spacingLeft=12;")

ZONE_TOP, ZONE_BOTTOM = 130, 2190

# ------------------------------------------------------------------ stage 1: receive & pre-process
text("z1", 40, ZONE_TOP, 690, ZONE_BOTTOM - ZONE_TOP, "阶段一｜接收与预处理", S_ZONE)
node("start", 205, 195, 360, 70, S_TERM, "开始：收到消息 / 到点触发")
node("in_wx", 80, 320, 290, 100, S_IO, "微信消息", "主入口 / 备用客服通道（含你对确认卡的回复）")
node("in_mail", 400, 320, 290, 100, S_IO, "邮件", "国际版 O365，每 2 分钟拉取")
node("intake", 80, 480, 610, 330, S_CODE, "接入与预处理（代码）",
     "• 验签解密，0.5 秒内回「已收到」\n"
     "• 连续转发停手 2 秒自动合并成一件事\n"
     "• 语音转文字（qwen3-asr-flash）\n"
     "• 邮件只放行 V&F / Tera / B&D，同一封只处理一次，正文加不可信标记\n"
     "• 附件按页提取文字；原件先备份到 OneDrive；无法解析的格式只记文件名，不丢原件\n"
     "输出：一段统一的文本 + 附件")
node("is_shortcut", 235, 880, 300, 190, S_DECISION, "是快捷指令吗？")
node("shortcut", 80, 1160, 610, 270, S_CODE, "快捷指令直接处理（代码，0 次模型）",
     "不需要上下文，立即处理：\n"
     "• 看板 / 负荷 → 直接回复（本次结束）\n"
     "• 1 / 2、开始 #N、完成 #N、撤销 → 交阶段五执行\n"
     "• 改：<意见> → 带着修改意见进入路径④重新起草")
edge("e_start_wx", "start", "in_wx", "", C_MAIN, exit_xy=(0.25, 1), entry_xy=(0.5, 0))
edge("e_start_mail", "start", "in_mail", "", C_MAIN, exit_xy=(0.75, 1), entry_xy=(0.5, 0))
edge("e_wx", "in_wx", "intake", "", C_MAIN, exit_xy=(0.5, 1), entry_xy=(0.24, 0))
edge("e_mail", "in_mail", "intake", "", C_MAIN, exit_xy=(0.5, 1), entry_xy=(0.76, 0))
edge("e_intake", "intake", "is_shortcut", "", C_MAIN, exit_xy=(0.5, 1), entry_xy=(0.5, 0))
edge("e_sc_yes", "is_shortcut", "shortcut", "是", C_MAIN, exit_xy=(0.5, 1), entry_xy=(0.5, 0))

# ------------------------------------------------------------------ stage 2: assemble context
text("z2", 790, ZONE_TOP, 540, ZONE_BOTTOM - ZONE_TOP, "阶段二｜装配上下文", S_ZONE)
node("ctx_db", 900, 330, 320, 150, S_DB, "SQLite 数据库", "对话记录 · 待确认卡 · 项目待办 · 文档索引")
node("ctx", 820, 600, 480, 620, S_CODE, "装配 4 层上下文（代码）",
     "按固定顺序读取真实数据，拼成提示词：\n\n"
     "1. 跨天滚动摘要 + 最近 30 轮对话\n"
     "　（间隔超 30 分钟会标注，防止串话题）\n\n"
     "2. 待确认卡片\n"
     "　（你还没回复确认的方案）\n\n"
     "3. 在途项目、待办快照\n"
     "　（提到项目名时自动附上项目卡）\n\n"
     "4. 历史文档与旧对话检索\n"
     "　（查资料和工作交办时才检索）\n\n"
     "输出：一份完整的上下文提示词")
edge("e_ctx_read", "ctx_db", "ctx", "读取", C_READ, exit_xy=(0.5, 1), entry_xy=(0.5, 0), dashed=True)
edge("e_sc_no", "is_shortcut", "ctx", "否", C_MAIN, exit_xy=(1, 0.5), entry_xy=(0, 0.605))

# ------------------------------------------------------------------ stage 3: decide & dispatch
text("z3", 1390, ZONE_TOP, 600, ZONE_BOTTOM - ZONE_TOP, "阶段三｜判断意图并分流", S_ZONE)
node("router", 1410, 830, 270, 160, S_LLM, "路由模型判断意图", "qwen3.8-flash\n读上下文，判断你想做什么，补全「这个/刚才那事」")
node("which", 1720, 810, 240, 200, S_DECISION, "走哪条路？")
edge("e_ctx_router", "ctx", "router", "", C_MAIN, exit_xy=(1, 0.5), entry_xy=(0, 0.5))
edge("e_router_which", "router", "which", "", C_MAIN, exit_xy=(1, 0.5), entry_xy=(0, 0.5))
node("router_note", 1410, 1110, 390, 250, S_NOTE, "代码兜底规则",
     "• 没有待确认卡却说「确认」\n　→ 当闲聊处理\n"
     "• 交办内容太模糊（置信度 < 0.55）\n　→ 路径⑤\n"
     "• 没明确说「查一下/上网查」\n　→ 不联网搜索")

# ------------------------------------------------------------------ stage 4: five paths
Z4_X = 2050
text("z4", Z4_X, ZONE_TOP, 2480, ZONE_BOTTOM - ZONE_TOP, "阶段四｜五条处理路径", S_ZONE)
BX, BW, BH = 2120, 600, 170
OX, OW, OH = 2800, 250, 100

node("p1", BX, 245, BW, BH, S_CODE, "① 直接执行（代码）", "确认或作废卡片、开始/完成打卡（可一句话多条）、撤销\n→ 交阶段五执行")
node("p2", BX, 535, BW, BH, S_LLM, "② 参谋回复（qwen3.8-flash）", "每条消息回复一次，不建待办\n聊几轮由你决定")
node("p3", BX, 825, BW, BH, S_LLM, "③ 查档问答（代码检索 + qwen3.8-flash）", "先查文档和旧对话，再只依据查到的内容回答\n必须带出处页码；查不到就说查不到")
node("p5", BX, 1115, BW, BH, S_CODE, "⑤ 请你澄清（代码）", "说明能力边界，或追问一个关键细节\n不建待办")
for pid, y in (("p2", 535), ("p3", 825), ("p5", 1115)):
    node(f"{pid}_out", OX, y + (BH - OH) // 2, OW, OH, S_IO, "回复发到微信")
    edge(f"e_{pid}_out", pid, f"{pid}_out", "", C_REPLY, exit_xy=(1, 0.5), entry_xy=(0, 0.5))

edge("e_r1", "which", "p1", "确认/作废卡片 · 打卡 · 撤销", C_ROUTE, exit_xy=(0.5, 0), entry_xy=(0, 0.5), points=[(1840, 330)])
edge("e_r2", "which", "p2", "闲聊 · 讨论 · 问建议", C_ROUTE, exit_xy=(0.75, 0.25), entry_xy=(0, 0.5), points=[(2010, 860), (2010, 620)])
edge("e_r3", "which", "p3", "查文档 · 查进度", C_ROUTE, exit_xy=(1, 0.5), entry_xy=(0, 0.5))
edge("e_r5", "which", "p5", "太模糊 · 做不了", C_ROUTE, exit_xy=(0.75, 0.75), entry_xy=(0, 0.5), points=[(2020, 960), (2020, 1200)])
edge("e_r4", "which", "t1", "交办工作 · 转发 · 附件 · 改卡片", C_ROUTE, exit_xy=(0.5, 1), entry_xy=(0, 0.5), points=[(1840, 1590)], width=3)

node("hb_note", 3600, 560, 860, 140, S_NOTE, "进度心跳",
     "任何一条路径处理超过 12 秒，就向微信推送当前在做哪一步，此后每 25 秒一次，直到出结果")

node("record", 3150, 535, 330, 750, S_CODE, "记录本次对话（代码）",
     "把你这句话和回复写入对话记录\n\n"
     "下次处理时，阶段二从这里读取，所以对话能接上\n\n"
     "每满 8 轮，后台刷新一次滚动摘要\n\n"
     "路径①和④同样会记录\n（分别在执行完、出卡后）\n\n"
     "只记对话，不改待办和看板")
for pid, frac in (("p2", 0.113), ("p3", 0.5), ("p5", 0.887)):
    edge(f"e_{pid}_rec", f"{pid}_out", "record", "", C_REPLY, exit_xy=(1, 0.5), entry_xy=(0, frac))
node("end_main", 3560, 875, 220, 70, S_TERM, "本次结束")
edge("e_rec_end", "record", "end_main", "", C_REPLY, exit_xy=(1, 0.5), entry_xy=(0, 0.5))

# path ④ pipeline
TY, TH = 1490, 200
text("p4_label", BX, 1420, 1500, 40, "④ 工作交办（最长的一条路径，按顺序执行）",
     "text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;fontSize=16;fontStyle=1;fontColor=#6b46c1;")
node("t1", BX, TY, 400, TH, S_CODE, "1 查证（代码）", "查历史文档和旧对话\n查未来 14 天每日排期密度\n两版 Excel 报价自动逐行比对")
node("t2", 2590, TY, 330, TH, S_CODE, "2 压缩（代码）", "把查到的长材料截成精简证据卡，避免模型被长文本淹没")
node("t3", 2990, TY, 420, TH, S_LLM, "3 起草方案（qwen3.8-max）", "拆出做什么、谁负责、起止日期、所属项目\n可自己调用排期和工作日推算工具\n不估工时，不代做外部调研")
node("t4", 3480, TY, 400, TH, S_LLM, "4 审核（代码 + deepseek-v4-pro）", "代码核对数字是否都有出处\n另一个模型挑漏项和逻辑错误")
node("t4_ok", 3940, 1500, 200, 180, S_DECISION, "通过？")
node("card", 4180, 1520, 340, 140, S_CARD, "5 出卡", "待确认卡存入数据库（原件已备份）\n记录本次对话，发卡到微信")
node("card_next", 4200, 1800, 300, 150, S_IO, "本次结束：等你回复",
     "回「1 / 好的」→ 路径① 执行\n回「改：…」→ 回到本路径重新起草")
edge("e_t12", "t1", "t2", "", C_MAIN, exit_xy=(1, 0.5), entry_xy=(0, 0.5))
edge("e_t23", "t2", "t3", "", C_MAIN, exit_xy=(1, 0.5), entry_xy=(0, 0.5))
edge("e_t34", "t3", "t4", "", C_MAIN, exit_xy=(1, 0.5), entry_xy=(0, 0.5))
edge("e_t4ok", "t4", "t4_ok", "", C_MAIN, exit_xy=(1, 0.5), entry_xy=(0, 0.5))
edge("e_fail", "t4_ok", "t3", "否：带修改意见重写（最多 2 次）", C_LOOP, exit_xy=(0.5, 1), entry_xy=(0.5, 1),
     points=[(4040, 1780), (3200, 1780)], dashed=True)
edge("e_pass", "t4_ok", "card", "是", C_MAIN, exit_xy=(1, 0.5), entry_xy=(0, 0.5))
edge("e_card_exec", "card", "exec", "你确认后（回复「1」，经路径①）", C_EXEC, exit_xy=(1, 0.5), entry_xy=(0, 0.7),
     points=[(4565, 1590), (4565, 481)], dashed=True)
edge("e_card_next", "card", "card_next", "", C_REPLY, exit_xy=(0.5, 1), entry_xy=(0.5, 0), dashed=True)

# ------------------------------------------------------------------ stage 5: execute after confirmation
Z5_X = 4590
text("z5", Z5_X, ZONE_TOP, 470, ZONE_BOTTOM - ZONE_TOP, "阶段五｜你确认后修改待办与看板", S_ZONE)
node("exec", 4630, 250, 400, 330, S_CODE, "修改待办与看板（代码）",
     "唯一能改正式数据的地方：\n• 先校验确认令牌，没有令牌拒绝写入\n"
     "• 一次性写入待办与项目，留 24 小时撤销快照\n"
     "• 附件归档到 OneDrive 对应项目目录\n"
     "• 重绘 5 份 .md 看板\n"
     "• 回复结果到微信，记录对话（本次结束）")
node("db", 4630, 680, 180, 170, S_DB, "SQLite", "待办 · 项目 · 对话")
node("od", 4850, 680, 180, 170, S_DB, "OneDrive", "原件 · 归档 · 5 份看板")
node("web", 4630, 950, 400, 230, S_CODE, "Web 驾驶舱",
     "直接读同一个数据库\n表格 · 甘特图 · 排期密度 · 统计\n网页上的修改同样写库并重绘看板")
edge("e_p1_exec", "p1", "exec", "执行", C_EXEC, exit_xy=(1, 0.5), entry_xy=(0, 0.242))
edge("e_exec_db", "exec", "db", "", C_EXEC, exit_xy=(0.225, 1), entry_xy=(0.5, 0))
edge("e_exec_od", "exec", "od", "", C_EXEC, exit_xy=(0.775, 1), entry_xy=(0.5, 0))
edge("e_db_web", "db", "web", "读取", C_READ, exit_xy=(0.5, 1), entry_xy=(0.225, 0), dashed=True)
node("conn_a1", 360, 1500, 50, 50, S_CONN, "A")
text("conn_a1_lbl", 420, 1500, 270, 50, "接阶段五（Ⓐ）", "text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;fontSize=14;fontStyle=1;fontColor=#dd6b20;")
edge("e_sc_conn", "shortcut", "conn_a1", "1/2、开始、完成、撤销", C_EXEC, exit_xy=(0.5, 1), entry_xy=(0.5, 0))
node("conn_a2", 4980, 182, 50, 50, S_CONN, "A")
text("conn_a2_lbl", 4640, 182, 330, 50, "Ⓐ 来自阶段一快捷指令", "text;html=1;strokeColor=none;fillColor=none;align=right;verticalAlign=middle;fontSize=14;fontStyle=1;fontColor=#dd6b20;")
edge("e_conn_exec", "conn_a2", "exec", "", C_EXEC, exit_xy=(0.5, 1), entry_xy=(0.875, 0))

edge("e_outer_loop", "card_next", "start",
     "外层循环：你的下一条消息 / 下一次触发 → 回到开始（阶段二会读取上次存下的状态）",
     C_REPLY, exit_xy=(0.5, 1), entry_xy=(0, 0.5), points=[(4350, 2280), (18, 2280), (18, 230)], dashed=True, width=3)

# ------------------------------------------------------------------ stage 6: scheduled jobs (independent lane)
text("z6", 40, 2330, 5020, 450, "阶段六｜每日定时任务（独立运行，到点或拉到邮件后从「开始」进入）", S_ZONE)
node("timer", 120, 2420, 380, 140, S_CODE, "定时器", "工作日 08:30 早报\n工作日 18:00 晚间复盘")
node("digest", 600, 2400, 900, 180, S_CODE, "生成简报（代码）",
     "早报：今日在途事项、平均完成跨度、优先待办、外部卡点、驾驶舱链接\n"
     "18:00：额外列出「进行中 / 今日到期 / 已超期」事项，请你确认进度\n"
     "简报同时写入对话记录，方便你直接回复")
node("digest_out", 1600, 2430, 560, 120, S_IO, "推送到微信",
     "你回复「#3 做完了，#5 开始了」→ 作为下一条消息走路径①")
node("mail_job", 2400, 2420, 900, 140, S_CODE, "邮件拉取（每 2 分钟）",
     "只拉白名单公司邮件，同一封只处理一次\n拉到后从「开始」进入，走一遍阶段一到五")
node("sum_job", 3420, 2420, 1550, 140, S_LLM, "滚动摘要（每 8 轮对话，后台运行，qwen3.8-flash）",
     "把上一版摘要与新对话合并成语义摘要：进行中项目、已定事项、待跟进人和日期\n失败时保留关键词摘要，不影响回复速度")
edge("e_timer", "timer", "digest", "", C_MAIN, exit_xy=(1, 0.5), entry_xy=(0, 0.5))
edge("e_digest", "digest", "digest_out", "", C_REPLY, exit_xy=(1, 0.5), entry_xy=(0, 0.5))

xml = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<mxfile host="app.diagrams.net" agent="Antigravity" version="24.7.17">\n'
    '  <diagram id="six-stage-workflow" name="六阶段工作流全景图">\n'
    f'    <mxGraphModel dx="2400" dy="1600" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" '
    f'fold="1" page="1" pageScale="1" pageWidth="{PAGE_W}" pageHeight="{PAGE_H}" math="0" shadow="0">\n'
    "      <root>\n"
    '        <mxCell id="0"/>\n'
    '        <mxCell id="1" parent="0"/>\n'
    "        " + "\n        ".join(cells) + "\n"
    "      </root>\n"
    "    </mxGraphModel>\n"
    "  </diagram>\n"
    "</mxfile>\n"
)
OUT_PATH.write_text(xml, encoding="utf-8")
print("Wrote", OUT_PATH, "bytes=", len(xml.encode("utf-8")))
