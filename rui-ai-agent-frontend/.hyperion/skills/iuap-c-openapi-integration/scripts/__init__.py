"""
业务接口查询技能 (Business Interface Query Skill)

提供业务接口查询、入参解析、代码生成提示等功能。
"""

from .business_interface_query import (
    query_single,
    query_multiple_parallel,
    build_ai_friendly_structure,
    split_interface_input_hints,
)
from .bip_auth import get_access_token, invalidate_token_cache
from .skill_context import resolve_mcp_context, format_context_markdown

__all__ = [
    "query_single",
    "query_multiple_parallel",
    "build_ai_friendly_structure",
    "split_interface_input_hints",
    "get_access_token",
    "invalidate_token_cache",
    "resolve_mcp_context",
    "format_context_markdown",
]

__version__ = "2.0.0"
