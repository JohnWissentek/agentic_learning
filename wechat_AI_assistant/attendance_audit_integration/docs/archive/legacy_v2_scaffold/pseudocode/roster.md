# roster.py 伪代码

## 本文件职责（一句话）
从本地 JSON 花名册加载员工姓名/邮箱等；提供外勤 GPS 200m 有效性判定。

## 对应PRD功能
F8、F13；异常场景 E14、E21

## 依赖
- 调用：config（ROOT_DIR / get）、logger、json/pathlib
- 被调用：audit_engine、scripts、cli（间接）

## 伪代码

常量 DEFAULT_ROSTER_PATH = 项目根/data/employee_roster.json
常量 OUTDOOR_GPS_MAX_RADIUS_METERS = 200

函数 get_roster_path():
    若 env EMPLOYEE_ROSTER_PATH 有值 → 用该路径
    否则 DEFAULT_ROSTER_PATH

函数 load_employee_roster(path=None):
    读 JSON；取 employees 列表
    过滤空姓名；规范化 email/userid/role/company
    缺文件 → FileNotFoundError；格式错 → ValueError

函数 evaluate_outdoor_gps_distance(distance_meters):
    若 distance ≤ 200 → "valid"
    否则 → "invalid"

## 异常与边界
- 缺文件/坏 JSON：上抛，由 CLI/任务记 ERROR 并非 0 退出
- 单行缺邮箱：允许（空串），匹配企微后可能无法发信（E21）
- GPS：无 100–500 人工审中间带；仅 valid / invalid

## 注意事项 / 坑
- 运行时禁止再读 xlsx；历史 Excel 仅作一次性迁移源
- 部分邮箱需人工补全 `data/employee_roster.json`
