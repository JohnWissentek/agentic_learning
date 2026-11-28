# diagnostics.py 伪代码

## 本文件职责（一句话）
一键导出诊断包(日志+脱敏配置+健康自检)，支撑"无法登录客户服务器"模式下的远程定位。

## 对应PRD功能
非功能需求 7.5(可观测性与远程支持)；00 总纲 4.5

## 依赖
- 调用：logger(get_logger, mask)
- 被调用：无（独立入口 `python -m attendance_audit_integration.diagnostics`）

## 伪代码

函数 export(输出目录):
    zip路径 = 输出目录/diagnostics_时间戳.zip
    打包:
        logs/ 下全部文件
        .env 快照 —— 每个值经 mask() 脱敏,密钥不离开服务器
        health.json —— 版本号/Python/OS/磁盘余量/日志大小/上次写日志时间
    打印人话提示"请将此文件发送给技术支持"
    返回 zip路径

函数 _health_check():
    收集环境与磁盘指标
    # TODO 按 PRD 外部依赖表逐项加连通性自检(带超时,失败只记录不抛)

## 异常与边界
- .env 不存在: 写入占位说明,不报错(诊断包本身不能因环境残缺而失败)
- logs/ 为空或不存在: 跳过,包仍生成
- 版本号取不到: 回退 pyproject.toml,再不行记 "unknown"
- 原则: 诊断功能自身绝不能崩——它是最后的救命通道

## 注意事项 / 坑
- 所有 .env 值统一脱敏,不做"哪些是敏感的"判断——宁可多脱,不可漏脱
- 新增外部依赖时,记得到 _health_check 的 TODO 处补连通性自检
