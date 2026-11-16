# 300点系统（含单纤25点实验阶段）全进口采购清单与原厂 PDF 资料库索引

本文件为您提供可直接用于询价立项的**分阶段采购 BOM 表（第一阶段：实验室单纤 25 点测试采购包；第二阶段：扩充至 300 点电厂工程采购包）**，以及已为您下载并整理在当前目录 [`Datasheets_PDF/`](./Datasheets_PDF/) 文件夹下的 **10 份全进口核心设备原厂英文 PDF 规格书（Datasheets）** 对照索引。

---

## 1. 分阶段采购与预算表（先花最少的钱做单纤 25 点实验 $\rightarrow$ 再扩到 300 点）

### 1.1 方案一（极简高可靠全进口组合：丹麦 Ibsen `I-MON 512` + 瑞士 `Sercalo` + 德国 `FBGS`）

| 序号 | 设备/模块名称 | 原厂品牌与产地 | 具体采购型号（Part Number） | **【阶段一：实验室单纤25点测试】采购数量与预算** | **【阶段二：补齐至300点满配】追加数量与预算** | 对应本地原厂 PDF 规格书链接 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **1** | **512像元 `InGaAs` 宽波段光谱解调 OEM 模块**<br/>*(含分光光栅+探测器+TIA+16位ADC+USB口)* | **Ibsen Photonics**<br/>（丹麦） | `I-MON 512 USB`<br/>*(1510–1595 nm 波段，内置评估软件与 C++/Python SDK)* | **1 台**<br/>**¥36,000** | 0 台 *(已具备 300 点能力，无需再买)* | [01_Ibsen_I-MON_256_512_USB_Interrogator_Datasheet.pdf](./Datasheets_PDF/01_Ibsen_I-MON_256_512_USB_Interrogator_Datasheet.pdf) |
| **2** | **C+L 波段高稳定 `ASE` 宽带光源成品模块**<br/>*(1525–1595 nm，内置恒流与TEC温控)* | **Amonics**<br/>（中国香港/美国芯片） | `ALS-CL-15-B-FA` *(台式实验版)* 或 `ALS-CL-15-M-FA` *(OEM 模块版)* + 三端口光学环形器 | **1 台**<br/>**¥12,500** | 0 台 *(无需再买)* | [04_Amonics_ALS_C-Band_ASE_Broadband_Light_Source_Datasheet.pdf](./Datasheets_PDF/04_Amonics_ALS_C-Band_ASE_Broadband_Light_Source_Datasheet.pdf) |
| **3** | **$1\times 16$ 通道军工级 `MEMS` 光开关成品盒**<br/>*(带 RS-232/USB 控制接口，支撑 $16\times 25 = 400$ 点)* | **Sercalo Microtechnology**<br/>（瑞士） | `SW1x16-9N-FA`<br/>*(SMF-28 单模，FC/APC 接头，切换 $<1\text{ ms}$)* | **1 台**<br/>**¥9,500**<br/>*(注：纯做单纤实验也可暂不买，上多路时再买)* | 0 台 *(16路已够 300 点用，还剩 4 路备用)* | [06_Sercalo_SW1x16_MEMS_Optical_Switch_Datasheet.pdf](./Datasheets_PDF/06_Sercalo_SW1x16_MEMS_Optical_Switch_Datasheet.pdf) |
| **4** | **工业计算机主板 + 明纬电源 + 19英寸 2U/3U 机箱** | **Kontron（德国控创）** / **研华** | `Kontron Core i5/i7` 嵌入式工控板 + `MeanWell` $12\text{V}/5\text{V}$ 工业电源 | **1 套**<br/>**¥4,000** | 0 套 *(无需再买)* | 工业通用标准件 |
| **5** | **预刻蚀单纤 25 点飞秒高温光纤光栅串**<br/>*(耐温 $500^\circ\text{C}$，免剥皮直写，高抗拉强度)* | **FBGS International**<br/>（德国/比利时）<br/>*(基底：美国 OFS `PyroCoat`)* | `FSG-A01-25Pts`<br/>*(1512.0~1588.8 nm，间距 3.2 nm，单纤 25 点，两端 FC/APC)* | **1 根（共 25 个点）**<br/>**¥6,500**<br/>*(实验单根定制价约 ¥260/点)* | **追加 11 根（共 275 个点）**<br/>**¥60,500**<br/>*(300点批量价约 ¥220/点)* | • [09_FBGS_FSG-A01_Femtosecond_Grating_Chain_Datasheet.pdf](./Datasheets_PDF/09_FBGS_FSG-A01_Femtosecond_Grating_Chain_Datasheet.pdf)<br/>• [10_OFS_PyroCoat_HighTemp_Polyimide_Fiber_Datasheet.pdf](./Datasheets_PDF/10_OFS_PyroCoat_HighTemp_Polyimide_Fiber_Datasheet.pdf) |
| **6** | **`316L` 无缝毛细管护套 + 水冷壁 `15CrMoG` 焊接导热铁块** | 瑞典 Sandvik 毛细管 + CNC 定制耐热钢块 | $\Phi 1.2\times 0.15\text{ mm}$ `316L` 毛细管 + 25 个 CNC 铣削 `15CrMoG` 导热铁块 | **1 套（25 个点）**<br/>**¥1,000** | **追加 11 套（275 个点）**<br/>**¥8,250** | 见工作区结构设计图纸说明 |
| **💰** | **合计预算（全进口方案一）** | — | — | **🧪 实验室单纤25点启动总价：`<br/>`**`¥69,500 元`** *(若暂不买光开关仅需 **`¥60,000 元`**)* | **🏭 扩充至 300 点追加款：`<br/>`**`¥68,750 元`**<br/>*(300点全系统总计：**`13.825 万元`**，合 **`461 元/点`**)* | — |

---

### 1.2 方案二（旗舰扫频激光全进口组合：日本 `Santec` / 美国 `Lumentum` + 德国 `FEMTO` + 德国 `Spectrum` + 瑞士 `Sercalo`）

如果您希望采用单点光电探测器 + 高速采集卡的**扫频激光路线**（自己从最底层的氣室吸收峰校准和 $16\text{-bit}$ ADC 波形开始写算法）：

| 序号 | 设备/模块名称 | 原厂品牌与产地 | 具体采购型号（Part Number） | **【阶段一：实验室单纤25点测试】采购数量与预算** | **【阶段二：补齐至300点满配】追加数量与预算** | 对应本地原厂 PDF 规格书链接 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **1** | **工业级可调谐扫频激光源模块** | **Santec（日本）** 或 **Lumentum（美国）** | `Santec WSL-110 / TSL-570` 或 `Lumentum S7500 MG-Y` | **1 台**：**¥42,000** | 0 台 | • [02_Santec_WSL-110_Tunable_Laser_Source_Datasheet.pdf](./Datasheets_PDF/02_Santec_WSL-110_Tunable_Laser_Source_Datasheet.pdf)<br/>• [03_Santec_TSL-570_Swept_Laser_Datasheet.pdf](./Datasheets_PDF/03_Santec_TSL-570_Swept_Laser_Datasheet.pdf) |
| **2** | **200MHz 超低噪声 `InGaAs PIN + TIA` 光电转换放大盒** | **FEMTO Messtechnik**（德国） | `HCA-S-200M-IN-FC`<br/>*(带 FC 光纤口与 SMA 电压输出口)* | **2 只** *(主探测+参考)*：**¥12,000** | 0 只 | [05_FEMTO_HCA-S-200M-IN_InGaAs_Photoreceiver_TIA_Datasheet.pdf](./Datasheets_PDF/05_FEMTO_HCA-S-200M-IN_InGaAs_Photoreceiver_TIA_Datasheet.pdf) |
| **3** | **NIST 认证氰化氢（$\text{HCN}$）气室 + 标准具 + 环形器** | **Wavelength References**（美国） | `HCN-13-C-100-FC/APC` + `50GHz Etalon` | **1 套**：**¥13,500** | 0 套 | [08_Wavelength_References_HCN-13_Gas_Cell_Datasheet.pdf](./Datasheets_PDF/08_Wavelength_References_HCN-13_Gas_Cell_Datasheet.pdf) |
| **4** | **16-bit 多通道同步 PCIe 高速数字化仪采集卡** | **Spectrum Instrumentation**（德国） | `M2p.5922-x4`<br/>*(16-bit, 20 MS/s, 4通道同步 PCIe 卡)* | **1 张**：**¥14,500** | 0 张 | [07_Spectrum_M2p59xx_16bit_PCIe_Digitizer_ADC_Datasheet.pdf](./Datasheets_PDF/07_Spectrum_M2p59xx_16bit_PCIe_Digitizer_ADC_Datasheet.pdf) |
| **5** | **$1\times 16$ 通道 `MEMS` 光开关 + 控创工控机箱** | **Sercalo**（瑞士）+ **Kontron**（德国） | `SW1x16-9N-FA` + 工控主机 | **1 套**：**¥13,500** | 0 套 | [06_Sercalo_SW1x16_MEMS_Optical_Switch_Datasheet.pdf](./Datasheets_PDF/06_Sercalo_SW1x16_MEMS_Optical_Switch_Datasheet.pdf) |
| **6** | **德国 FBGS 单纤 25 点飞秒高温光栅串 + 导热铁块** | **FBGS**（德国）+ **OFS**（美国） | `FSG-A01-25Pts` + `316L` 毛细管 + `15CrMoG` 铁块 | **1 根（25 点）**：**¥7,500** | **追加 11 根（275 点）**：**¥68,750** | [09_FBGS_FSG-A01_Femtosecond_Grating_Chain_Datasheet.pdf](./Datasheets_PDF/09_FBGS_FSG-A01_Femtosecond_Grating_Chain_Datasheet.pdf) |
| **💰** | **合计预算（全进口方案二）** | — | — | **🧪 实验室单纤25点启动总价：`<br/>`**`¥103,000 元`** *(若暂不买光开关为 **`¥93,500 元`**)* | **🏭 扩充至 300 点追加款：`<br/>`**`¥68,750 元`**<br/>*(300点全系统总计：**`17.175 万元`**，合 **`572 元/点`**)* | — |

---

## 2. 原厂 PDF 资料包（`Datasheets_PDF/`）文件清单与核心参数提取表

当前工作区文件夹 [`Datasheets_PDF/`](./Datasheets_PDF/) 中已为您下载并整理好以下 **10 份原厂官方 PDF 规格书**，方便您直接查阅机械尺寸、电气引脚定义、光学接口与寄存器/SDK 参数：

| 文件编号与点击链接 | 对应核心设备 | 原厂品牌（国家） | PDF 内核查的关键工程参数摘要 |
| :--- | :--- | :--- | :--- |
| **[01_Ibsen_I-MON_256_512_USB_Interrogator_Datasheet.pdf](./Datasheets_PDF/01_Ibsen_I-MON_256_512_USB_Interrogator_Datasheet.pdf)** | 512像元 `InGaAs` 线阵光谱解调模块 | **Ibsen Photonics**（丹麦） | 波长范围 $1510\sim 1595\text{ nm}$；512 像素；内置 $16\text{-bit}$ ADC；USB 2.0 / SPI / UART 接口；供电 $5\text{ V DC}$；寻峰分辨率 $<0.5\text{ pm}$。 |
| **[02_Santec_WSL-110_Tunable_Laser_Source_Datasheet.pdf](./Datasheets_PDF/02_Santec_WSL-110_Tunable_Laser_Source_Datasheet.pdf)** | 小型可调谐激光源模块 | **Santec**（日本） | 调谐范围覆盖 C/L 波段；输出功率 $+13\text{ dBm}$（$20\text{ mW}$）；线宽 $<100\text{ kHz}$；USB / GP-IB / Ethernet 控制。 |
| **[03_Santec_TSL-570_Swept_Laser_Datasheet.pdf](./Datasheets_PDF/03_Santec_TSL-570_Swept_Laser_Datasheet.pdf)** | 旗舰级高速线性扫频激光器 | **Santec**（日本） | 波长 $1500\sim 1630\text{ nm}$（超宽 $130\text{ nm}$）；扫频速度高达 $200\text{ nm/s}$；波长精度 $\pm 1\text{ pm}$；带压电/周期 Trigger 同步输出。 |
| **[04_Amonics_ALS_C-Band_ASE_Broadband_Light_Source_Datasheet.pdf](./Datasheets_PDF/04_Amonics_ALS_C-Band_ASE_Broadband_Light_Source_Datasheet.pdf)** | 高平坦度 `ASE` 掺铒宽带光源 | **Amonics**（香港） | 输出功率 $+10\sim +20\text{ dBm}$；光谱平坦度 $<1.5\text{ dB}$；短期功率稳定度 $\pm 0.02\text{ dB}$；带联锁安全钥匙与 RS-232 接口。 |
| **[05_FEMTO_HCA-S-200M-IN_InGaAs_Photoreceiver_TIA_Datasheet.pdf](./Datasheets_PDF/05_FEMTO_HCA-S-200M-IN_InGaAs_Photoreceiver_TIA_Datasheet.pdf)** | 高速 `InGaAs PIN + TIA` 光电转换放大器 | **FEMTO Messtechnik**（德国） | 光谱响应 $900\sim 1700\text{ nm}$；带宽 $\text{DC}\sim 200\text{ MHz}$（上升时间 $1.8\text{ ns}$）；跨阻增益 $2\times 10^4\text{ V/A}$；等效噪声功率 $\text{NEP} = 6\text{ pW}/\sqrt{\text{Hz}}$；FC 光纤口输入，SMA $50\text{ }\Omega$ 电压输出。 |
| **[06_Sercalo_SW1x16_MEMS_Optical_Switch_Datasheet.pdf](./Datasheets_PDF/06_Sercalo_SW1x16_MEMS_Optical_Switch_Datasheet.pdf)** | $1\times 16$ 通道军工级 `MEMS` 光开关 | **Sercalo**（瑞士） | 波长 $1260\sim 1670\text{ nm}$ 全透明；插入损耗典型值 $1.0\text{ dB}$；回波损耗 $>50\text{ dB}$；切换时间 $<1\text{ ms}$；寿命 $>10^{10}$ 次；尺寸 $90\times 60\times 19\text{ mm}$；I2C / RS232 控制。 |
| **[07_Spectrum_M2p59xx_16bit_PCIe_Digitizer_ADC_Datasheet.pdf](./Datasheets_PDF/07_Spectrum_M2p59xx_16bit_PCIe_Digitizer_ADC_Datasheet.pdf)** | 16位多通道同步 PCIe 高速采集卡 | **Spectrum Instrumentation**（德国） | 真 $16\text{-bit}$ 分辨率；$5\sim 125\text{ MS/s}$ 采样率；4/8 通道完全同步采样（无相位差）；板载 $512\text{ MSamples}$ 内存；支持 Windows/Linux C++, Python, MATLAB, LabVIEW 驱动。 |
| **[08_Wavelength_References_HCN-13_Gas_Cell_Datasheet.pdf](./Datasheets_PDF/08_Wavelength_References_HCN-13_Gas_Cell_Datasheet.pdf)** | NIST 溯源 $\text{H}^{13}\text{C}^{14}\text{N}$ 氰化氢波长校准气室 | **Wavelength References**（美国） | 覆盖 $1525\sim 1565\text{ nm}$ P支与R支共 50+ 条标准分子吸收线；绝对波长不确定度 $\pm 0.12\sim 0.3\text{ pm}$；温度系数 $<0.01\text{ pm/}^\circ\text{C}$；设计寿命 $>10\text{ 年}$。 |
| **[09_FBGS_FSG-A01_Femtosecond_Grating_Chain_Datasheet.pdf](./Datasheets_PDF/09_FBGS_FSG-A01_Femtosecond_Grating_Chain_Datasheet.pdf)** | 飞秒穿透涂覆层直写高温光栅串 | **FBGS International**（德国/比利时） | `FSG-A01` 聚酰亚胺涂覆低损耗光纤；免剥皮飞秒激光直写；栅长 $1\sim 10\text{ mm}$；反射率 $>15\%$；半高宽 $0.1\sim 0.7\text{ nm}$；整纤无熔接高机械强度。 |
| **[10_OFS_PyroCoat_HighTemp_Polyimide_Fiber_Datasheet.pdf](./Datasheets_PDF/10_OFS_PyroCoat_HighTemp_Polyimide_Fiber_Datasheet.pdf)** | 耐高温聚酰亚胺（`PyroCoat®`）特种光纤 | **OFS Fitel**（美国） | 石英包层 $125\pm 1\text{ }\mu\text{m}$；`PyroCoat` 聚酰亚胺涂层外径 $155\pm 5\text{ }\mu\text{m}$；长期工作温度 $-65^\circ\text{C}\sim +300^\circ\text{C}$、短期耐温 $+400^\circ\text{C}$（配合微氧毛细管封装更高）；筛选强度 $\ge 100/200\text{ kpsi}$。 |
| **[11_Hamamatsu_G11620_512Pixel_InGaAs_Linear_Sensor_Datasheet.pdf](./Datasheets_PDF/11_Hamamatsu_G11620_512Pixel_InGaAs_Linear_Sensor_Datasheet.pdf)** | 512像元 `InGaAs` 线阵图像传感器芯片（I-MON 512 内部核心芯片） | **Hamamatsu（日本滨松）** | 型号 `G11620-512DA`；光谱响应 $950\sim 1700\text{ nm}$；512 像素（像元尺寸 $25\text{ }\mu\text{m} \times 500\text{ }\mu\text{m}$）；内置 CMOS 电荷积分读出放大器。 |
