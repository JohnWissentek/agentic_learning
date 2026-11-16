#!/usr/bin/env python3
"""Generate Hardware Integration & Electrical/Optical/DCS/AI System Interface Architecture Diagram.

Exports:
- `docs/02_BOILER_FBG_SYSTEM_INTERFACE_ARCH.{drawio,svg,pdf}`
- `<output_dir>/10_BOILER_FBG_SYSTEM_INTERFACE_ARCH.{drawio,svg,pdf}`
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

from generate_ipd_workflow_drawio import CleanDiagramBuilder, mid_bot, mid_left, mid_right, mid_top

BASE_DIR = Path(__file__).resolve().parents[1]
DOCS_DRAWIO = BASE_DIR / "docs/02_BOILER_FBG_SYSTEM_INTERFACE_ARCH.drawio"
DRAWIO_BIN = Path("/Applications/draw.io.app/Contents/MacOS/draw.io")


def generate_all(output_dir: Path) -> None:
    d = CleanDiagramBuilder(2800, 1980)

    d.add_box(
        "sys_banner",
        "BANNER",
        40,
        30,
        2720,
        "BoilerSense-AI™ 双档模块化集成系统物理与信号接口全图 (全外购国际现货硬件 + 自研软件/旁路AI)",
        "左侧: 锅炉水冷壁耐高温传感阵列 (Track A 全进口 / Track B 混合高性价比)  →  中部: 标准版 BS-STD-600 / 旗舰版 BS-PRO-2000 机柜光学与电信号链  →  右侧: 工业上位机、单向网闸 DCS 与两阶段 AI 平台",
        hdr_h=40,
        body_font_size=13,
    )

    d.add_band(40, 145, 760, 1780, "Zone 1 · 锅炉炉膛水冷壁现场端 (350°C–600°C 强振防爆区)", "#B45309")
    d.add_band(830, 145, 1140, 1780, "Zone 2 · 解调机柜硬件集成层 (外购成品模块，免自研模拟PCB)", "#1E3A8A")
    d.add_band(2000, 145, 760, 1780, "Zone 3 · 自研软件、物理隔离DCS与两阶段锅炉AI层", "#065F46")

    # Zone 1
    d.add_box("z1_wall", "CONTEXT_BOX", 75, 210, 690, "1.1 水冷壁焊接导热块 (15CrMoG / 12Cr1MoVG)", "• TIG 满焊于膜式水冷壁向火侧/背火侧鳍片或管冠\n• 内置 Φ1.5mm 松套通孔，热传递路径 10mm (ΔT≈-3.2°C @350kW/m²)\n• 配合防磨耐火护瓦与炉墙膨胀补偿密封套管", min_h=170)
    d.add_box("z1_fbg_a", "STORAGE", 75, 430, 690, "1.2 Track A 全进口高温光栅串 (标杆配置)", "• 德国 FBGS FSG-A01 飞秒穿透涂覆层直写 (免剥皮 >200 kpsi)\n• 美国 OFS PyroCoat® / 英国 Fibercore SM1500SC 纯石英芯光纤\n• 瑞士/瑞典 Sandvik Φ1.2mm 316L / Inconel 600 松套毛细管铠装", min_h=175)
    d.add_box("z1_fbg_b", "STORAGE", 75, 655, 690, "1.3 Track B 高性价比量产光栅串 (招标主打)", "• 长飞/OFS 200 kpsi 抗氢损碳-聚酰亚胺特种单模纤\n• 严选认证飞秒直写(25-40点/纤) 或 拉丝塔 DTG/UWFBG(80-125点)\n• 激光连续焊接不锈钢微细铠装光缆 + 现场防拉脱接续盒", min_h=175)
    d.add_box("z1_cable", "HARDCODED", 75, 880, 690, "1.4 铠装尾缆与炉前汇接箱 (OTDR 验收红线)", "• 单通道 1510-1595nm 间隔 3.2nm (25点) 或 2.8nm (32点)\n• 耐高温阻燃金属软管穿桥架引至电子间 (总长 80–200m)\n• 统一 FC/APC (8°斜面低回反 RL>55dB) 防尘接头接入机柜后板", min_h=175)
    d.add_box("z1_qc", "GATE", 75, 1110, 690, "1.5 现场安装三大绝对工程红线", "• 严禁胶水粘死光栅区：光栅必须悬空松套于毛细管内完全去应力\n• 弯曲半径 ≥30mm (盘纤盒 ≥40mm)，熔接单点损耗 ≤0.08 dB\n• 冷态焊后 + 热态升温全通道 OTDR & 光谱 SNR ≥18 dB 签字验收", min_h=180)

    # Zone 2 - STD & PRO routes + Power
    d.add_box("z2_sw", "HARDCODED", 865, 210, 1070, "2.1 公共多路光学切换与环形隔离前端 (Shared Optical Front-End)", "• 瑞士 Sercalo SW1x16 / SW1x32 / SW1x48 军工级 MEMS 光开关 (IL≈1.0dB, <1ms切换, >10^10次寿命)\n• 控制接口: RS-232 (115200bps) / USB / 5V TTL I/O 帧同步触发，FC/APC 单模端口直出\n• 三端口高功率光学环形器 (Port1光源进 → Port2接MEMS公共端 → Port3回波至探测器)", min_h=185)

    d.add_box("z2_std", "LLM_AGENT", 865, 445, 515, "2.2A 标准版 BS-STD-600 核心光引擎", "• 光源: 香港/美 Amonics ALS-CL-15-M-FA\n  (1510-1595nm C+L ASE, +15dBm, +5V/12V供电)\n• 解调盒: 丹麦 Ibsen I-MON 512 USB\n  (体光栅 + 滨松 G11620 512像元 + 16位ADC)\n• 数据接口: USB 2.0 / SPI 3000帧/秒直接吐出\n  512点原始光谱数组 (免采集卡、35天出样)", min_h=330)

    d.add_box("z2_pro", "LLM_AGENT", 1415, 445, 520, "2.2B 旗舰版 BS-PRO-2000 扫频引擎", "• 光源: 日本 Santec WSL-110/TSL-570 或 Lumentum\n  (+13dBm, 50-100Hz扫频, 输出 TTL Trigger 脉冲)\n• 参考校准: 美国 Wavelength Ref HCN-13 气室\n  + 50GHz 无热 F-P 标准具 (10%分光监测)\n• 光电盒: 德国 FEMTO HCA-S-200M-IN (×2 主+参)\n  (±15V供电, FC输入 → SMA 50Ω 0~2V 电压输出)\n• 采集卡: 德国 Spectrum M2p.5922-x4 PCIe 16位卡", min_h=330)

    d.add_box("z2_host", "HARDCODED", 865, 835, 1070, "2.3 工业边缘主控计算单元 & 工业电源配电树", "• 工业主控: 研华 Advantech ARK-2250L / 德国控创 Kontron 4U 工业服务器 (双千兆电口 + PCIe x4 扩展槽 + 看门狗)\n• 配电树: 台湾明纬 MeanWell NDR-240-24 (主24VDC) + 隔离 DC-DC (±15V供FEMTO, +12V/+5V供ASE与MEMS光开关)\n• EMC与防浪涌: 机箱单点保护接地 (<1Ω)，IEC 61000-4-4/5 电厂级 4kV 浪涌与群脉冲防护", min_h=205)

    d.add_box("z2_net", "HARDCODED", 865, 1095, 1070, "2.4 电厂工业通讯与物理隔离安全接口", "• 协议转换网关: 台湾摩莎 Moxa MGate MB3180 / 工业 OPC UA Server，支持 Modbus TCP / OPC UA / 硬接线 4-20mA 报警继电器\n• 一期安全边界: 通过正/反向工业物理单向隔离网闸 (只读采集 DCS 负荷/煤量/风门/吹灰信号，物理阻断反向写操作)", min_h=170)

    d.add_box("z2_qa", "STORAGE", 865, 1320, 1070, "2.5 工厂标定与量产 NPI 测试工装接口", "• 标定接口: AMETEK Jofra CTC-660 / 三温区 650°C 精密管式标定炉 + 一等铂电阻参考表 (RS-485 闭环控温)\n• 老化验收: 高低温湿热箱 (-10°C~+60°C 72h 拷机) + OTDR 光衰减校准台 → 自动生成每根光栅串三阶系数 JSON 表", min_h=175)

    # Zone 3
    d.add_box("z3_alg", "LLM_AGENT", 2035, 210, 690, "3.1 自研高速解调与标定软件栈 (C++ / Python)", "• 驱动层: Ibsen USB DLL / Spectrum DMA 零拷贝环形队列\n• 算法链: 暗电流扣除 → SG滤波 → HCN/F-P 样条非线性校正\n  → 加权对数高斯 / LM 亚像素寻峰 (<0.5 pm) → 导热块逆向补偿\n• 自诊断: 光强突变断纤定位、通道插损告警、自动重映射", min_h=250)

    d.add_box("z3_twin", "STORAGE", 2035, 510, 690, "3.2 水冷壁三维温度场数字孪生上位机", "• 水冷壁四面展开热力云图 (克里金空间插值 + 1Hz实时刷新)\n• 时序历史曲线、超温阈值三级告警与单点寿命台账\n• 断网本地 SQLite/TimescaleDB 连续缓存 ≥1 年", min_h=190)

    d.add_box("z3_ai1", "LLM_AGENT", 2035, 755, 690, "3.3 锅炉 AI 一期：旁路只读智慧运行 (零涉网阻力)", "• 结焦洁净因子反演: 热阻增长识别积灰，输出按需吹灰最佳区域与时序\n• 爆管寿命预警: 结合 15%–30% 深调峰热交变 + Larson-Miller 蠕变模型\n• 燃烧偏斜诊断: 识别切圆火焰刷墙与高温还原性气氛腐蚀高危区", min_h=240)

    d.add_box("z3_ai2", "GATE", 2035, 1050, 690, "3.4 锅炉 AI 二期：闭环优化与等保三级升级", "• 通过发电集团等保三级与电力监控安防合规评估后开放双向接口\n• 基于 PINN 物理约束软测量与强化学习，向 DCS 输出吹灰程控触发\n  与二次风门偏置建议，目标稳定降低供电煤耗 0.8–1.5 g/kWh", min_h=225)

    d.add_box("z3_dcs", "CONTEXT_BOX", 2035, 1330, 690, "3.5 外部电厂 DCS / SIS 交互接口", "• OPC UA / Modbus TCP 只读点表 (机组负荷MW、主汽压/温、给煤量、风量)\n• 一期硬接线干接点 (24V/2A 无源常开)：全系统严重超温/断纤硬件告警\n• 二期 SIS/MIS Web 大屏与集团集中诊断中心远传 API", min_h=195)

    # Wiring
    b = d.boxes
    d.add_edge("z1_wall", "z1_fbg_a", [mid_bot(b["z1_wall"]), mid_top(b["z1_fbg_a"])], "#B45309")
    d.add_edge("z1_fbg_a", "z1_fbg_b", [mid_bot(b["z1_fbg_a"]), mid_top(b["z1_fbg_b"])], "#059669", dashed=True)
    d.add_edge("z1_fbg_b", "z1_cable", [mid_bot(b["z1_fbg_b"]), mid_top(b["z1_cable"])], "#1E3A8A")
    d.add_edge("z1_cable", "z1_qc", [mid_bot(b["z1_cable"]), mid_top(b["z1_qc"])], "#9F1239")

    # Zone 1 -> Zone 2 optical cables
    d.add_edge("z1_cable", "z2_sw", [(mid_right(b["z1_cable"])[0], mid_right(b["z1_cable"])[1]), (810, mid_right(b["z1_cable"])[1]), (810, mid_left(b["z2_sw"])[1]), mid_left(b["z2_sw"])], "#2563EB", stroke_w=3.2)

    # Switch -> STD / PRO
    d.add_edge("z2_sw", "z2_std", [(mid_bot(b["z2_sw"])[0] - 260, mid_bot(b["z2_sw"])[1]), (mid_top(b["z2_std"])[0], mid_top(b["z2_std"])[1])], "#5B21B6")
    d.add_edge("z2_sw", "z2_pro", [(mid_bot(b["z2_sw"])[0] + 260, mid_bot(b["z2_sw"])[1]), (mid_top(b["z2_pro"])[0], mid_top(b["z2_pro"])[1])], "#5B21B6")

    # STD / PRO -> Host
    d.add_edge("z2_std", "z2_host", [mid_bot(b["z2_std"]), (mid_bot(b["z2_std"])[0], 810), (mid_top(b["z2_host"])[0] - 250, 810), (mid_top(b["z2_host"])[0] - 250, mid_top(b["z2_host"])[1])], "#1E3A8A")
    d.add_edge("z2_pro", "z2_host", [mid_bot(b["z2_pro"]), (mid_bot(b["z2_pro"])[0], 810), (mid_top(b["z2_host"])[0] + 250, 810), (mid_top(b["z2_host"])[0] + 250, mid_top(b["z2_host"])[1])], "#1E3A8A")

    d.add_edge("z2_host", "z2_net", [mid_bot(b["z2_host"]), mid_top(b["z2_net"])], "#1E3A8A")
    d.add_edge("z2_net", "z2_qa", [mid_bot(b["z2_net"]), mid_top(b["z2_qa"])], "#059669", dashed=True)

    # Zone 2 -> Zone 3
    d.add_edge("z2_host", "z3_alg", [(mid_right(b["z2_host"])[0], mid_right(b["z2_host"])[1]), (1985, mid_right(b["z2_host"])[1]), (1985, mid_left(b["z3_alg"])[1]), mid_left(b["z3_alg"])], "#5B21B6", stroke_w=3.0)
    d.add_edge("z2_net", "z3_dcs", [(mid_right(b["z2_net"])[0], mid_right(b["z2_net"])[1]), (1985, mid_right(b["z2_net"])[1]), (1985, mid_left(b["z3_dcs"])[1]), mid_left(b["z3_dcs"])], "#D97706", stroke_w=3.0)

    d.add_edge("z3_alg", "z3_twin", [mid_bot(b["z3_alg"]), mid_top(b["z3_twin"])], "#059669")
    d.add_edge("z3_twin", "z3_ai1", [mid_bot(b["z3_twin"]), mid_top(b["z3_ai1"])], "#5B21B6")
    d.add_edge("z3_ai1", "z3_ai2", [mid_bot(b["z3_ai1"]), mid_top(b["z3_ai2"])], "#9F1239", dashed=True)
    d.add_edge("z3_dcs", "z3_ai1", [(mid_left(b["z3_dcs"])[0], mid_left(b["z3_dcs"])[1]), (2015, mid_left(b["z3_dcs"])[1]), (2015, mid_left(b["z3_ai1"])[1]), mid_left(b["z3_ai1"])], "#D97706", dashed=True)

    tree = d.build_xml()
    DOCS_DRAWIO.parent.mkdir(parents=True, exist_ok=True)
    out_drawio = output_dir / "10_BOILER_FBG_SYSTEM_INTERFACE_ARCH.drawio"
    out_drawio.parent.mkdir(parents=True, exist_ok=True)
    tree.write(str(DOCS_DRAWIO), encoding="utf-8", xml_declaration=True)
    shutil.copy2(DOCS_DRAWIO, out_drawio)

    if DRAWIO_BIN.exists():
        for target in (DOCS_DRAWIO, out_drawio):
            for fmt in ("svg", "pdf"):
                out_f = target.with_suffix(f".{fmt}")
                subprocess.run([str(DRAWIO_BIN), "-x", "-f", fmt, "-o", str(out_f), str(target)], check=True, capture_output=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=str((BASE_DIR / "../output").resolve()))
    args = parser.parse_args()
    generate_all(Path(args.output_dir).resolve())


if __name__ == "__main__":
    main()
