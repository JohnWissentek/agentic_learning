"""一键诊断包（框架标准件，对应 05_LOGGING_STANDARD 第5节 / 00 总纲 4.5）。

客户执行一条命令，导出可发给交付方的诊断压缩包:

    python -m attendance_audit_integration.diagnostics

包内容: 全部日志 / 脱敏配置快照 / 版本与环境信息 / 健康自检结果。
安全: .env 的所有值一律脱敏(只保留前4字符)，密钥不会离开客户服务器。
"""
from __future__ import annotations

import json
import platform
import shutil
import sys
import zipfile
from datetime import datetime
from pathlib import Path

from attendance_audit_integration.logger import get_logger, mask

logger = get_logger(__name__)

ROOT_DIR = Path(__file__).resolve().parents[2]
LOG_DIR = ROOT_DIR / "logs"


def _version() -> str:
    """从已安装元数据取版本号，取不到则回退 pyproject.toml。"""
    try:
        from importlib.metadata import version
        return version("attendance_audit_integration")
    except Exception:
        try:
            import tomllib
            data = tomllib.loads((ROOT_DIR / "pyproject.toml").read_text(encoding="utf-8"))
            return data["project"]["version"]
        except Exception:
            return "unknown"


def _masked_env() -> list[str]:
    """读取 .env，所有值统一脱敏——密钥绝不进入诊断包。"""
    env_file = ROOT_DIR / ".env"
    if not env_file.exists():
        return ["(.env 不存在)"]
    lines = []
    for raw in env_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            lines.append(raw)
            continue
        key, _, value = line.partition("=")
        lines.append(f"{key}={mask(value.strip())}")
    return lines


def _health_check() -> dict:
    """健康自检：磁盘余量、日志状态、上次运行痕迹。按项目需要扩展(如外部依赖连通性)。"""
    du = shutil.disk_usage(ROOT_DIR)
    app_log = LOG_DIR / "app.log"
    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "version": _version(),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "disk_free_gb": round(du.free / 1024**3, 2),
        "disk_used_percent": round(du.used / du.total * 100, 1),
        "log_dir_size_mb": round(
            sum(f.stat().st_size for f in LOG_DIR.rglob("*") if f.is_file()) / 1024**2, 2
        ) if LOG_DIR.exists() else 0,
        "last_log_write": datetime.fromtimestamp(app_log.stat().st_mtime).isoformat(
            timespec="seconds") if app_log.exists() else None,
        # TODO: 按 PRD 第5节外部依赖表，逐项加连通性自检(带超时,失败不抛异常只记录)
    }


def export(out_dir: Path | None = None) -> Path:
    """生成诊断包，返回 zip 路径。"""
    out_dir = out_dir or ROOT_DIR
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_path = out_dir / f"diagnostics_{stamp}.zip"

    logger.info("开始导出诊断包 -> %s", zip_path)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # 1. 全部日志
        if LOG_DIR.exists():
            for f in LOG_DIR.rglob("*"):
                if f.is_file():
                    zf.write(f, Path("logs") / f.relative_to(LOG_DIR))
        # 2. 脱敏配置快照
        zf.writestr("env_masked.txt", "\n".join(_masked_env()))
        # 3. 健康自检(含版本与环境)
        zf.writestr("health.json", json.dumps(_health_check(), ensure_ascii=False, indent=2))

    logger.info("诊断包导出完成: %s (%.1f KB)", zip_path, zip_path.stat().st_size / 1024)
    print(f"\n诊断包已生成: {zip_path}\n请将此文件发送给技术支持。")
    return zip_path


if __name__ == "__main__":
    export()
