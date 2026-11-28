# tools/check_traceability.py 伪代码(信任链关键件)

## 本文件职责(一句话)
图-代码溯源对账:比对 ARCHITECTURE.md 里 Mermaid 声明的模块依赖 与 代码真实 import 关系,不一致即失败。

## 对应PRD功能
00 总纲 2.1(逆向自动对账)/2.4 闸门1

## 依赖
- 调用:标准库(ast, re, pathlib)
- 被调用:pre-commit hook、tests/unit/test_traceability.py、人工命令行

## 伪代码

函数 parse_declared_edges(架构文档):
    提取全部 ```mermaid 代码块
    对每条 "A --> B" 边: 若两端节点标签都含 .py 文件名 → 记为声明边(模块名, 模块名)
    (两端不全是 .py 的边如 API/DB 节点,自动忽略)

函数 parse_actual_edges(src目录):
    对 src 下每个 .py(除 __init__): ast 解析
    收集 import / from X import Y 中指向项目内模块的引用 → 真实边(调用方, 被调方)
    同时收集: 跨模块私有导入违规(from 模块 import _下划线开头的名字)

函数 find_cycle(边集合):                       # 00 总纲 4.9 硬指标2
    对依赖图做深度优先遍历
    发现回到途中节点 → 返回环路径(如 a → b → a);无环返回空

函数 run_check(项目根):
    架构文档不存在 → FAIL
    # 第一部分: 代码卫生检查(不依赖图,模板示例期也执行)
    真实边成环 → 打印环路径, FAIL(循环依赖)
    存在跨模块私有导入 → 逐条打印, FAIL(接口最小暴露被破坏)
    # 第二部分: 图-代码对账(模板示例期跳过)
    含 TEMPLATE-EXAMPLE-CONTENT 标记 → SKIP 对账部分
    声明边为空 → FAIL(图没画对或节点标签缺 .py 文件名)
    声明边成环 → FAIL(设计本身画出了循环依赖,先改图)
    缺失 = 声明有代码无(设计未实现/图过时)
    多余 = 代码有图没画(实现漂移)
    有任一 → 逐条打印并 exit 1;否则 exit 0

## 异常与边界
- 单个 .py 语法错误:WARN 跳过该文件,不让对账本身崩(但该文件的边会缺失,间接暴露)
- `from package import module` 形式:names 也按模块名匹配(已修的漏检 bug,见 VERIFICATION)
- 粒度限制:模块级 import 对账;函数级调用/参数路径/Canvas 一致性为文件尾 TODO 扩展点
- 私有导入检查只覆盖 import 语句形式;`模块._函数()` 属性访问形式不查(已知弱约束,提示词层约束)
- 环检测与私有检查不依赖架构图,模板示例期(TEMPLATE-EXAMPLE-CONTENT)也照常执行

## 注意事项 / 坑
- 图上模块节点标签必须含真实 .py 文件名,否则该节点所有边被忽略,对账会漏
- 本脚本是"人不读代码"信任链的地基:改它属 L2 级变更,改后必须重跑三场景验证(一致/漂移/未实现)
