"""
请求重试工具模块
导出自公共 iuap_common.retry_utils 模块
"""
from __future__ import annotations

# 从共享库重新导出所有公共API，保持向后兼容
from iuap_common.retry_utils import (
    DEFAULT_RETRYABLE_EXCEPTIONS,
    CircuitBreaker,
    CircuitBreakerOpenError,
    RateLimiter,
    get_global_rate_limiter,
    retry_on_failure,
    retry_on_failure_with_result,
    set_global_rate_limiter,
)

__all__ = [
    "DEFAULT_RETRYABLE_EXCEPTIONS",
    "CircuitBreaker",
    "CircuitBreakerOpenError",
    "RateLimiter",
    "get_global_rate_limiter",
    "retry_on_failure",
    "retry_on_failure_with_result",
    "set_global_rate_limiter",
]
