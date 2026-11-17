# 06｜世纪互联 SharePoint 私有库与 OneDrive 实操手册（实测图文版）

| 项 | 内容 |
| :--- | :--- |
| 文档版本 | v3.2（Wissentek 世纪互联真实界面实测版） |
| 更新日期 | 2026-11-17 |
| 适用范围 | https://wissentek.sharepoint.cn（由世纪互联运营的 Microsoft 365 企业版） |
| 关联文档 | [总览 README](../README.md) · [02-技术栈与存储架构设计](02-技术栈与存储架构设计.md) · [04-阿里云部署与实施路线](04-阿里云部署与分阶段实施路线.md) · [05-全流程实操SOP与验收Checklist](05-全流程实操SOP与验收Checklist.md) |

---

## 一、 为什么实际页面与常规教程不一样？（实测差异对照）

很多早期或面向国际版旧界面写的教程会在 SharePoint 首页直接写「点击页面顶部 + 创建网站」以及「文档库点 添加到 OneDrive 快捷方式」。经过实际登录 https://wissentek.sharepoint.cn/_layouts/15/sharepoint.aspx/discover/sites/recent 勘察操作，新版世纪互联界面已发生 5 处关键改版：

| 环节 | 常见旧教程写法（容易找不到的原因） | Wissentek 世纪互联当前真实界面（实测） |
| :--- | :--- | :--- |
| 1. 首页路径 | 打开 SharePoint 主页直接看顶部按钮 | 访问 /_layouts/15/sharepoint.aspx 会自动跳转至 /_layouts/15/sharepoint.aspx/discover；/discover/sites/recent（页面标题 SharePoint \| 发现）仅用于浏览与筛选现有站点（主区有 最新动态 / 收藏夹 / 推荐 三个胶囊选项卡），页面顶部已无任何新建站点按钮。 |
| 2. 建站入口位置 | 页面顶部工具栏 + 创建网站 | 入口已收纳至最左侧纵向应用栏第 3 个图标 生成（/_layouts/15/sharepoint.aspx/build）。该栏共 4 个固定图标：发现 → 发布 → 生成 → OneDrive。点开 生成 后，主区 开始构建 下方会显示 4 张卡片（网站、列表、文档库、智能体），点击第 1 张卡片 网站 才是建站入口。 |
| 3. 建站模板流程 | 直接选“团队网站/通信网站”后进入填表 | 升级为两段式向导：先弹出 选择站点模板（顶部含 团队站点 / 通信站点 两个选项卡），在 来自 Microsoft 下选择模板（如 标准团队）→ 进入 预览站点模板 确认后点击右下角 使用模板 → 才会打开 设置站点 表单。 |
| 4. 地址与时区字段 | 需点击地址旁铅笔按钮编辑英文 URL；填表时可选时区 | 在 设置站点 弹窗中：站点地址 * 固定前缀 https://wissentek.sharepoint.cn/sites/ 后方即为可直接输入编辑的文本框（同时会校验 群组电子邮件地址 *）；隐私设置 选项全称为 专用 - 仅成员可访问此站点；建站向导内没有时区选项（新建后默认显示 UTC-08:00，可按需在站点区域设置改回东八区）。 |
| 5. 文档库与快捷方式图标 | 顶部工具栏点“添加到 OneDrive 快捷方式”，网盘中显示链条小图标 | 新建后的站点与 Documents 文档库界面目前默认以英文工具栏呈现：旧版 + 新建 / 上传 合并为右侧紫色主按钮 + Create or upload；命令栏中按钮为 Add shortcut to OneDrive，点击后会展开目标菜单 Shortcuts / My files 供选定目录；添加后在网页版 OneDrive 我的文件 中表现为黄色共享文件夹右下角带白色方框内蓝色斜向上箭头 ↗（名称格式为 <站点名称> - Documents）。 |

---

## 二、 本次已完成的配置结果核对清单

> 以下配置已通过受控浏览器在你的 wissentek.sharepoint.cn 账号下实操完成，且核验仅你本人 1 名成员，可直接在后续 Sites.Selected 赋权阶段使用：

| 配置项 | 实测结果与核验状态 |
| :--- | :--- |
| 站点名称 | 董事长幕僚归档库 |
| 站点根地址（MS_SITE_ID 对应路径） | https://wissentek.sharepoint.cn/sites/chairman-vault |
| 站点首页地址 | https://wissentek.sharepoint.cn/sites/chairman-vault/SitePages/CollabHome.aspx?market=zh-CN |
| 默认文档库地址 | https://wissentek.sharepoint.cn/sites/chairman-vault/Shared%20Documents/Forms/AllItems.aspx |
| 群组邮箱前缀 / 英文别名 | chairman-vault |
| 隐私级别与成员隔离核验 | 页面右上角显示 Private group 与 1 member；点开 Group membership 面板核实仅当前登录账号本人 1 名 Owner，无其他任何同事。 |
| OneDrive 快捷方式位置 | 网页版 OneDrive 我的文件（https://wissentek-my.sharepoint.cn/my） |
| OneDrive 快捷方式显示名称 | 董事长幕僚归档库 - Documents（所有者: 董事长幕僚归档库，辅助图标：黄色文件夹右下角 ↗ 快捷方式角标） |
| 时区补充说明（选调） | 因向导无时区选项，文档库 Modified 列悬停目前默认为 (UTC-08:00) Pacific Time (US and Canada)；不影响后续后端接口（Graph API 统一使用 ISO-8601 UTC），若希望网页列时间显示北京时间，按第 4.3 节改一次区域设置即可。 |

---

## 三、 100% 还原真实界面的分步操作手册（Step-by-Step）

如果日后需要在同类世纪互联租户下新建第二个隔离私有库，或需复盘本次配置路径，请严格按以下实测步骤操作：

### 步骤 1：在「发现」页确认无同名冲突站点
1. 登录 https://wissentek.sharepoint.cn/_layouts/15/sharepoint.aspx/discover/sites/recent（页面标题为 SharePoint | 发现）。
2. 在次级左侧导航中，默认高亮 发现 → 站点；右侧主区标题为 网站，下方有 最新动态、收藏夹、推荐 三个选项卡。
3. 切换检查确认不存在同名站点（若页面显示 你的网站将显示在此处 即说明尚无最近或推荐站点）。

### 步骤 2：从最左侧纵向应用栏进入「生成 → 网站」
1. 将目光移到窗口最左侧纵向应用栏（从上到下共 4 个图标：发现、发布、生成、OneDrive）。
2. 点击第 3 个图标 生成（地址会跳转至 /_layouts/15/sharepoint.aspx/build）。
3. 在主内容区 开始构建 标题下方可以看到 4 张卡片（网站、列表、文档库、智能体），点击第 1 张卡片 网站（说明：创建共享空间以跨组织进行协作或通信。）。

### 步骤 3：在「选择站点模板」向导中选定标准团队站点
1. 第一屏弹窗（标题：选择站点模板）：
   - 确认顶部选项卡选中的是 团队站点（另一选项卡为 通信站点；团队站点支持与 Microsoft 365 组联动并提供精细隐私与 Sites.Selected 控制）。
   - 在下方 来自 Microsoft 模板列表中，点击第 1 张模板卡片 标准团队。
2. 第二屏弹窗（标题：预览站点模板）：
   - 检查摘要确认类型显示为 来自 Microsoft / 团队站点（包含的内容: 1 个主页）。
   - 点击窗口右下角 使用模板 按钮。

### 步骤 4：填写「设置站点」并锁死「专用」隐私与英文路径
在打开的 设置站点 表单弹窗中逐项填写（打 * 为必填）：
1. 站点名称 *：输入 董事长幕僚归档库（输入框下方应出现绿色校验提示 该网站名称可用。）。
2. 站点描述：按需填写或留空。
3. 群组电子邮件地址 *：输入简洁纯英文别名 chairman-vault（提示 该组别名可用。）。
4. 站点地址 *：在固定前缀 https://wissentek.sharepoint.cn/sites/ 右侧的直接编辑框内确认或修改为 chairman-vault，失焦后确认出现 此站点地址可用。。
   - 说明：请务必使用纯英文短路径作为 站点地址，这样后续系统调用 Graph API 检索路径与网页浏览 URL 都最简洁稳定。
5. 隐私设置（关键安全红线）：点击下拉框，务必确认选择 专用 - 仅成员可访问此站点，切勿改为“公用”。
6. 选择语言：选择 中文(简体)。
7. 点击弹窗右下角 创建站点 按钮。

### 步骤 5：跳过「添加所有者和成员」并进入站点
1. 界面进入创建与模板应用进度（正在创建站点... → 正在应用模板... → 最终显示 你的站点已准备就绪!）。
2. 下方的 在等待期间，添加所有者和成员。 → 键入姓名或电子邮件 输入框完全留空，绝不输入或添加任何其他员工，确认待添加列表为空。
3. 点击右下角 转到站点，自动进入站点首页（https://wissentek.sharepoint.cn/sites/chairman-vault/SitePages/CollabHome.aspx?market=zh-CN）。
4. 若右侧弹出 Next steps 引导面板可点右上角关闭，然后核对站点头部右上角必须明确显示 Private group 与 1 member；可点击 1 member 打开 Group membership 面板再次核实仅有你本人 1 名 Owner。

### 步骤 6：进入「Documents」文档库并添加 OneDrive 快捷方式
1. 在站点左侧导航栏点击 Documents，进入默认文档库（首次进入若弹出 Collect Files with Forms 引导提示，点击 Got it 关闭）。
2. 观察文档库顶部命令栏（自左向右可见：Add shortcut to OneDrive、Forms、Edit in grid view、Pin to Quick access、Automate、Integrate、Sync、... 更多菜单，以及最右侧紫色 + Create or upload 按钮）。
3. 点击 Add shortcut to OneDrive（只点这一项，切勿再去点 Sync）。
4. 按钮下方会展开目标目录选择菜单（Shortcuts / My files），点击 My files。
5. 稍等 1–2 秒，页面底部会弹出带绿色对勾的深色确认条：Added 1 shortcut to in OneDrive，即表示绑定成功。

### 步骤 7：在网页版 OneDrive 核验快捷方式（纯云端零本地占用策略）
1. 网页端核验：点击页面左上角九宫格应用启动器按钮（App launcher / :::）→ 点击 OneDrive → 在新打开的标签页点击左侧 我的文件（https://wissentek-my.sharepoint.cn/my），确认列表中已出现 董事长幕僚归档库 - Documents（图标为黄色文件夹右下角带蓝色斜向上箭头 ↗ 快捷方式角标，所有者列显示 董事长幕僚归档库）。
2. 纯云端使用约定（不在本地 Mac 同步盘落盘）：因本机 Mac 存储空间有限，已定案不在 Mac 安装或同步 OneDrive 本地文件夹；日常直接在手机/电脑浏览器打开 chairman-vault、OneDrive 网页端 我的文件 → 董事长幕僚归档库 - Documents（支持 Office Online 在线浏览 PDF/Excel/Word/Markdown），或通过驾驶舱网页上的云端直链随时查阅，不占本地 1 MB 磁盘。

---

## 四、 常见避坑与后续阶段衔接说明

### 4.1 为什么只点「Add shortcut to OneDrive」，不要再点「Sync」？
- 微软官方 SharePoint 与 OneDrive 机制规定：对同一个文档库添加 OneDrive 快捷方式后，不应同时对该库点击 Sync（尤其当前明确采用纯云端浏览方案、不向本机 Mac 同步大文件）。
- 使用 Add shortcut to OneDrive -> My files 后，无论您用办公室电脑、家里浏览器还是手机登录同一个 Wissentek 世纪互联账户，OneDrive 我的文件 里都会固定保留 董事长幕僚归档库 - Documents 云端直达入口。

### 4.2 如何解决站点/文档库界面混用英文或默认值问题？
- 虽然建站时语言选择了 中文(简体)，新建团队站点默认导航和命令栏标签仍可能显示为英文（如 Documents、Add shortcut to OneDrive），这在世纪互联 SharePoint 模板中属于正常现象，不影响 Graph API 读写，也不影响云端目录里的中文文件名显示（后续我们在第 S2.2 步初始化的 00_我的四大清单、01_项目归档 等子文件夹全部是清晰中文）。

### 4.3 如需把文档库默认显示时区调为北京时间（可选）
1. 打开 https://wissentek.sharepoint.cn/sites/chairman-vault，点击顶部导航栏右上角齿轮图标 Settings → Site information → View all site settings。
2. 在 Site Administration 分组下点击 Regional settings。
3. 将 Time Zone 从 (UTC-08:00) Pacific Time (US and Canada) 改为 (UTC+08:00) Beijing, Chongqing, Hong Kong, Urumqi，下拉到页面底部点击 OK 保存即可。

### 4.4 与下一步 S0.3 Entra 授权（Sites.Selected）的直接衔接
完成本手册后，在执行 [05-全流程实操SOP与验收Checklist.md](05-全流程实操SOP与验收Checklist.md) 中 S0.3 第 2–3 步（Entra 应用注册与一次性站点赋权）时，你的站点查询接口路径已经完全确定：
- 查询目标站点 MS_SITE_ID 的 Graph 请求路径为：
  ```text
  GET https://microsoftgraph.chinacloudapi.cn/v1.0/sites/wissentek.sharepoint.cn:/sites/chairman-vault
  ```
- 拿到 id 字段写入 MS_SITE_ID 并按 S0.3 第 3 步提交一次 roles: ["write"] 授权后，后端 Python 智能体即可在境内高速直连写入 董事长幕僚归档库 - Documents 对应的云端文档库，同时对 Wissentek 租户内所有其它团队站点保持 403 物理隔离。
