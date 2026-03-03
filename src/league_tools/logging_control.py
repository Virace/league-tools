"""日志输出控制。

默认关闭 `league_tools` 命名空间日志，避免作为依赖库时污染上游项目控制台。
上游项目可按需调用 ``enable_logging()`` 手动开启。
"""

from __future__ import annotations

from typing import Final

from loguru import logger

_LOGGER_NAMESPACE: Final[str] = "league_tools"
_logging_enabled: bool = False


def enable_logging() -> None:
    """开启 `league_tools` 命名空间日志输出。"""
    global _logging_enabled

    logger.enable(_LOGGER_NAMESPACE)
    _logging_enabled = True


def disable_logging() -> None:
    """关闭 `league_tools` 命名空间日志输出。"""
    global _logging_enabled

    logger.disable(_LOGGER_NAMESPACE)
    _logging_enabled = False


def is_logging_enabled() -> bool:
    """返回当前是否已开启 `league_tools` 命名空间日志输出。"""
    return _logging_enabled


disable_logging()
