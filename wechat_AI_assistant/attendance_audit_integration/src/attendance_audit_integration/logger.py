"""统一日志配置（框架标准件，一般无需修改）。

用法:
    from attendance_audit_integration.logger import get_logger
    logger = get_logger(__name__)
    logger.info("同步开始 batch_id=%s", batch_id)

规范见框架文档 05_LOGGING_STANDARD.md：
- 控制台: INFO+ 简洁格式；文件 logs/app.log: DEBUG+ 完整格式
- 文件轮转: 5MB x 5份
- 禁止 print() 调试、禁止裸 except、敏感信息脱敏
"""
from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

_LOG_DIR = Path(__file__).resolve().parents[2] / "logs"
_INITIALIZED = False

_FILE_FMT = "%(asctime)s | %(levelname)-8s | %(module)s:%(funcName)s:%(lineno)d | %(message)s"
_CONSOLE_FMT = "%(asctime)s | %(levelname)-8s | %(message)s"


def _init_root(log_file: str = "app.log") -> None:
    global _INITIALIZED
    if _INITIALIZED:
        return
    _LOG_DIR.mkdir(exist_ok=True)
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())
    console.setFormatter(logging.Formatter(_CONSOLE_FMT, datefmt="%H:%M:%S"))
    root.addHandler(console)

    file_handler = RotatingFileHandler(
        _LOG_DIR / log_file, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(_FILE_FMT))
    root.addHandler(file_handler)

    _INITIALIZED = True


def get_logger(name: str, log_file: str = "app.log") -> logging.Logger:
    """获取模块级 logger。首次调用时初始化全局配置。"""
    _init_root(log_file)
    return logging.getLogger(name)


def mask(secret: str, keep: int = 4) -> str:
    """敏感信息脱敏: mask('eyJhbGciOi...') -> 'eyJh****'"""
    if not secret:
        return ""
    return secret[:keep] + "****"
