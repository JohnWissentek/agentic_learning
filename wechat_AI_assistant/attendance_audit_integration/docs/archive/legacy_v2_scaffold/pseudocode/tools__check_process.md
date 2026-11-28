# tools/check_process.py 伪代码(信任链关键件)

## 本文件职责(一句话)
过程闸门:凡提交触碰实质内容(src/docs/tests)却未同时更新 docs/STATUS.md,拒绝提交。

## 对应PRD功能
00 总纲 2.2(状态总账硬性规则)/2.4 闸门2

## 依赖
- 调用:git diff --cached --name-only(subprocess)
- 被调用:pre-commit hook

## 伪代码

函数 check(staged文件列表):
    实质改动 = 列表中属于 src/**, docs/**, tests/** 且不是 docs/STATUS.md 的文件
    若 实质改动为空: 通过(工具/README类提交不强制)
    若 docs/STATUS.md 在列表中: 通过
    否则: 打印受影响文件+补账指引, 返回 1(拒绝提交)

## 异常与边界
- git 命令失败(如不在仓库中):WARN 并放行——闸门自身故障不应锁死开发,宁可漏拦不可误锁
- 空提交(无 staged 文件):通过
- 绕过途径:--no-verify,属已知残余风险(00 总纲 2.4),事后必须补账

## 注意事项 / 坑
- 只看"是否动了 STATUS.md",不校验内容质量——内容质量靠人审开发日志
- 若项目调整目录结构(如 src 改名),需同步改本文件的路径前缀清单
