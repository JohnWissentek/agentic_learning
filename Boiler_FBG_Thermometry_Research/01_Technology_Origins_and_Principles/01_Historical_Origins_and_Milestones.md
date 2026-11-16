# 光纤光栅（FBG）及高温准分布式测温技术溯源与演进脉络

## 1. 最早的技术出处（从物理发现到工业实用化）

光纤光栅（Fiber Bragg Grating, FBG）测温技术并非单一发明的产物，而是经历了**“光纤光敏性发现 $\rightarrow$ 紫外侧写突破 $\rightarrow$ 相位掩模量产化 $\rightarrow$ 高温再生与飞秒激光耐高温突破 $\rightarrow$ 拉丝塔超弱光栅阵列大容量复用”**五个关键代际。

### 1.1 第一阶段：光纤光栅的鼻祖——加拿大通信研究中心（CRC）Kenneth O. Hill（1978 年）
* **最早出处**：**1978 年**，加拿大通信研究中心（Communications Research Centre, CRC, Ottawa）的物理学家 **Kenneth O. Hill（肯尼斯·希尔）** 与川崎（B. S. Kawasaki）、约翰逊（D. C. Johnson）等人在实验中首次偶然发现了掺锗石英光纤的光敏性（Photosensitivity），并制造出人类历史上第一根光纤布拉格光栅。
* **原始论文**：*K. O. Hill, Y. Fujii, D. C. Johnson, and B. S. Kawasaki, "Photosensitivity in optical fiber waveguides: Application to reflection filter fabrication," Applied Physics Letters, vol. 32, no. 10, pp. 647–649, May 1978.*
* **早期工艺原理（内部驻波法 / Hill Grating）**：将波长为 $488\text{ nm}$ 的连续氩离子激光从掺锗石英光纤的一端注入纤芯，入射光与光纤末端 $4\%$ 菲涅尔反射回来的光发生干涉，在纤芯内形成周期性的驻波光强分布。高光强区域的锗氧缺陷中心发生双光子吸收，引起折射率永久性周期变化。
* **历史局限**：驻波法刻出的光栅周期被死死锁定在激发光波长（$488\text{ nm}$）附近，无法反射通信常用的 $1310\text{ nm}$ 或 $1550\text{ nm}$ 红外光，也无法在同一根光纤不同位置自由设定不同波长。

### 1.2 第二阶段：实用化决定性突破——美国联合技术研究中心（UTRC）Gerald Meltz（1989 年）
* **核心突破出处**：**1989 年**，美国联合技术研究中心（United Technologies Research Center, UTRC）的 **Gerald Meltz（杰拉尔德·梅尔茨）**、W. W. Morey 和 W. H. Glenn 发明了**紫外双光束横向全息干涉写入法（Transverse Holographic Inscription）**，同时首次系统论证了 FBG 作为**温度与应变传感器**的物理模型。
* **原始论文**：*G. Meltz, W. W. Morey, and W. H. Glenn, "Formation of Bragg gratings in optical fibers by a transverse holographic method," Optics Letters, vol. 14, no. 15, pp. 823–825, Aug. 1989.*
* **技术意义**：不再从光纤端面打光，而是用 $244\text{ nm}$ 的紫外激光分成两束，从光纤**侧面**相交干涉直接照射纤芯。通过调节两束紫外光的夹角 $\theta$，即可在同一根光纤的不同位置刻蚀出**任意不同周期（不同中心波长）**的光栅。这正是您提到的“同一根光纤不同位置刻蚀得不一样，靠波长区分位置”的直接源头。

### 1.3 第三阶段：工业化量产基石——相位掩模法（Phase Mask Technique, 1993 年）
* **核心突破出处**：**1993 年**，加拿大 CRC 的 **Kenneth O. Hill、B. Malo** 团队与美国 AT&T 贝尔实验室的 **D. Z. Anderson** 团队几乎同时独立发明了**相位掩模刻蚀法（Phase Mask Method）**。
* **原始论文**：*K. O. Hill, B. Malo, F. Bilodeau, D. C. Johnson, and J. Albert, "Bragg gratings fabricated in monomode photosensitive optical fiber by UV exposure through a phase mask," Applied Physics Letters, vol. 62, no. 10, pp. 1035–1037, Mar. 1993.*
* **技术意义**：用一块精密蚀刻的石英衍射光栅（相位掩模板）紧贴光纤，紫外激光透过掩模板产生 $\pm 1$ 级衍射干涉条纹写入光纤。大幅降低了对激光空间相干性和防振平台的要求，使 FBG 从实验室走向流水线量产。

---

## 2. 针对电厂锅炉高温（$400^\circ\text{C}\sim 1000^\circ\text{C}$）与百点/千点大容量复用的专门技术出处

普通紫外光刻写的 I 类光纤光栅（Type I FBG）在高于 $250^\circ\text{C}\sim 300^\circ\text{C}$ 的环境下，其锗氧缺陷中心发生热激发复合，光栅会在几小时至几天内被**热擦除（Thermal Erasure）**，反射峰彻底消失。为了将光纤光栅搬上**电厂锅炉水冷壁（管壁/鳍片工作温度 $350^\circ\text{C}\sim 600^\circ\text{C}$，局部烟气超温可达 $700^\circ\text{C}$ 以上）**并实现**单纤数百至上千点测量**，学术界与工业界发展出了以下三项核心专门技术：

### 2.1 高温耐受路线一：飞秒激光直写/相位掩模光栅（Femtosecond Laser FBG, 2003 年）
* **最早技术出处**：**2003 年**，加拿大通信研究中心（CRC）的 **Stephen J. Mihailov（斯蒂芬·米哈伊洛夫）** 团队首次利用 $800\text{ nm}$ 钛宝石飞秒脉冲激光（脉冲宽度 $\sim 120\text{ fs}$）结合特制相位掩模板，在无需载氢敏化的标准通信单模光纤中刻写出耐受 **$1000^\circ\text{C}$** 高温的 II 类（Type II）光纤光栅；随后 **2004 年** 英国阿斯顿大学 **A. Martinez** 与德国耶拿大学团队发展了**飞秒激光逐点直写法（Point-by-Point, PbP）**与**逐线法（Line-by-Line）**。
* **原始论文**：*S. J. Mihailov et al., "Fiber Bragg gratings made with a phase mask and 800-nm femtosecond radiation," Optics Letters, vol. 28, no. 12, pp. 995–997, Jun. 2003.*
* **耐高温原理**：飞秒激光峰值功率密度高达 $10^{13}\text{ W/cm}^2$，在纤芯内引发非线性多光子电离和微区微爆（Micro-void / 致密化结构改性），形成物理结构级别的折射率改变，而非普通紫外光的不稳定色心缺陷，因此**在 $600^\circ\text{C}\sim 1000^\circ\text{C}$ 下长期工作不退化、不擦除**。

### 2.2 高温耐受路线二：再生光纤光栅（Regenerated FBG, RFBG, 2002–2008 年）
* **最早技术出处**：**2002 年** 瑞典皇家工学院（KTH）的 **M. Fokine** 首次报道了掺氟/掺锗光纤中的高温化学组成光栅（Chemical Composition Grating, CCG）；**2008 年** 澳大利亚悉尼大学光子学实验室的 **John Canning（约翰·坎宁）** 与 **Simon Bandyopadhyay** 正式提出并标准化了普通载氢光敏光纤的**热再生光栅（Regenerated FBG, RFBG）**工艺。
* **原始论文**：*S. Bandyopadhyay, J. Canning, M. Stevenson, and K. Cook, "Ultrahigh-temperature regenerated gratings in boron-codoped germanosilicate optical fiber using 193 nm," Optics Letters, vol. 33, no. 16, pp. 1917–1919, Aug. 2008.*
* **耐高温原理**：先用紫外光在高压载氢光纤上刻写出强反射率的“种子光栅（Seed Grating）”，再放入高温退火炉中升温至 $850^\circ\text{C}\sim 950^\circ\text{C}$ 保温。原有的紫外光栅在高温下先完全擦除归零，随后纤芯内部的羟基与掺杂剂在周期性应力场诱导下发生石英玻璃网络结构松弛与结晶相变，重新“长”出一个新的光栅（再生光栅）。再生光栅可在 **$600^\circ\text{C}\sim 900^\circ\text{C}$** 下长期稳定测温，且制造成本远低于飞秒激光器，是目前国内电站锅炉高温点位极常采用的量产方案。

### 2.3 单纤百点/千点复用路线：拉丝塔在线刻写光栅（DTG）与超弱光栅阵列（UWFBG）
* **拉丝塔光栅（Draw Tower Grating, DTG）最早出处**：**1993–1995 年** 由美国弗吉尼亚理工大学与德国 **IPHT Jena（耶拿光子技术研究所，后孵化出 FBGS 公司）** 的 **L. Dong、C. G. Askins、M. Rothhardt** 等人发明。在光纤预制棒高温拉丝成形的瞬间、涂覆层尚未涂上去之前，用单脉冲准分子激光在线写入光栅，然后再涂覆聚酰亚胺（PI），消除了传统“剥涂覆层 $\rightarrow$ 刻蚀 $\rightarrow$ 二次涂覆”造成的机械强度下降。
* **超弱光纤光栅阵列（UWFBG）大容量工程化出处**：
  * **国际源头（OFDR 解调结合弱光栅）**：**1998 年** 美国 **NASA 兰利研究中心（Langley Research Center）的 Mark Froggatt 与 Jason Moore** 发明了基于光频域反射（OFDR）的高密度弱反射光栅传感解调技术（后商业化为美国 **Luna Innovations** 公司），在一根光纤上刻写数百至数千个相同或相近波长的弱光栅，利用频域反射区分位置。
  * **国内工程化源头（拉丝塔千点级弱光栅阵列）**：**2010 年前后**，**武汉理工大学姜德生院士团队**（及孵化企业武汉理工光科等）突破了拉丝塔在线高速制备单纤数千点超弱光纤光栅阵列（反射率 $R < 0.01\%$，即 $-40\text{ dB}$ 以下）及波分/时分/空分复合解调技术，并将其大规模推向石化储罐、电力电缆廊道及电厂锅炉受热面监测。

---

## 3. 电厂锅炉水冷壁“金属导热块 + 光纤光栅”应用脉络汇总表

| 关键技术要素 | 最早发明/提出机构与学者 | 发表年份 | 解决的核心工程痛点 |
| :--- | :--- | :--- | :--- |
| **光纤光敏性与驻波光栅** | 加拿大通信研究中心（CRC）Kenneth O. Hill 等 | 1978 年 | 证明石英光纤纤芯可写入永久性周期折射率光栅 |
| **双光束紫外侧写与传感模型** | 美国联合技术研究中心（UTRC）Gerald Meltz 等 | 1989 年 | 实现任意位置刻写不同波长光栅，确立温度/应变传感公式 |
| **相位掩模法批量刻写** | 加拿大 CRC (K. O. Hill) & 美国贝尔实验室 (D. Z. Anderson) | 1993 年 | 实现光栅工业化高精度一致刻写 |
| **拉丝塔在线刻写（DTG）** | 美国 NRL (C. G. Askins) & 德国 IPHT Jena | 1993–1997 年 | 在拉丝涂覆前单脉冲刻写，实现长距离无熔接、高机械强度光栅串 |
| **OFDR 高密度弱光栅解调** | 美国 NASA 兰利研究中心 Mark Froggatt（Luna 公司前身） | 1998 年 | 突破单纤波分复用 30 点上限，实现单纤数百至上千点毫米/厘米级定位测温 |
| **飞秒激光耐高温 II 类光栅** | 加拿大 CRC Stephen J. Mihailov 等 | 2003 年 | 解决普通光栅 $>300^\circ\text{C}$ 热擦除问题，将耐温极限推升至 $1000^\circ\text{C}$ |
| **热再生高温光纤光栅（RFBG）** | 瑞典 KTH (M. Fokine) & 澳大利亚悉尼大学 (John Canning) | 2002–2008 年 | 以低成本紫外写入+高温退火重结晶工艺，实现 $600^\circ\text{C}\sim 900^\circ\text{C}$ 电站锅炉长期测温 |
| **水冷壁去应力毛细管+焊接导热块封装** | 欧美电力研究院（EPRI）及国内华北电力大学、武汉理工、国电南自等团队 | 2012–2018 年 | 通过耐热钢导热块焊接+内部毛细钢管松套悬空结构，解决水冷壁热膨胀应变干扰与炉膛耐磨防护 |
