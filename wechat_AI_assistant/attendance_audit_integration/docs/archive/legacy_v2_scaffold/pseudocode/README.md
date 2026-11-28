# 伪代码目录

每个 `src/attendance_audit_integration/` 下的 `.py` 文件对应一份 `.md`（子路径 `/` 换成 `__`）：

- `src/attendance_audit_integration/main.py` → `main.md`
- `src/attendance_audit_integration/audit_engine.py` → `audit_engine.md`
- `tools/check_stage.py` → `tools__check_stage.md`

模板与规范见框架文档 `code_dev_audit_framework_v2/docs/03_PSEUDOCODE_GUIDE.md`。每份含六部分：职责、对应PRD、依赖、伪代码、**异常与边界（必填）**、注意事项。

规则：**先改伪代码，再改代码**（变更分级 L3，见框架 00 总纲 2.3）。
