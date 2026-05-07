"""
安全配置模块
导出自公共 iuap_common.secure_config 模块
"""
from __future__ import annotations

# 从共享库重新导出所有公共API，保持向后兼容
from iuap_common.secure_config import (
    SecureConfigError,
    SecureConfigLoader,
    _interpolate_env_vars,
    _load_dotenv,
    _walk_and_interpolate,
    get_env,
    load_secure_config,
)

__all__ = [
    "SecureConfigError",
    "SecureConfigLoader",
    "_interpolate_env_vars",
    "_load_dotenv",
    "_walk_and_interpolate",
    "get_env",
    "load_secure_config",
]
