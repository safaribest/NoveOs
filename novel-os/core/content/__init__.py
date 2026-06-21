"""内容域 —— 纯文本处理函数集合。"""
from core.content.formatter import split_long_paragraphs
from core.content.metrics import count_chinese_chars
from core.content.sanitizer import SanitizeRule, Sanitizer
from core.content.title import (
    ensure_prefix,
    extract_from_content,
    extract_from_director,
    strip_title_prefix,
)

__all__ = [
    "count_chinese_chars",
    "Sanitizer",
    "SanitizeRule",
    "extract_from_director",
    "extract_from_content",
    "ensure_prefix",
    "strip_title_prefix",
    "split_long_paragraphs",
]
