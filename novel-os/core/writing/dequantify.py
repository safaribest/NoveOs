"""Dequantify —— 降低中文数词密度。

Loop Engineering 知识管理体系的一部分：
大纲作者习惯用量词（三层、七日、百年、九道）做设定，
但正文中高密度使用会触发 AI 味检测。本模块把非剧情必需的
精确中文数词降级为模糊体感表达。
"""
from __future__ import annotations

import re


# 剧情必需数词后缀：这些必须保留，不能降级
# 注意：'层' 不在此列，因为'三层境界'应降级，而'第三层'已被 (?<!第) 保护
_STORY_ESSENTIAL_SUFFIXES = re.compile(
    r"(?:分钟|秒钟|小时|天|章|回|卷|楼|号|室|集|期|岁|载|纪|代)"
)

# 可降级后缀：层级、时间跨度、数量等
_DEGRADABLE_SUFFIXES = re.compile(
    r"(?:层|级|阶|段|境|域|重|关|日|年|月|时辰|刻|道|条|块|片|枚|颗|粒|"
    r"根|只|把|张|支|双|副|座|扇|步|件|份|种|类|项|面|侧|头|匹|具|艘|架|辆|台|部|套|滴|缕|丝)"
)

# 中文数词
_CN_NUM = r"[一二两三四五六七八九十百千万亿零半几]+"


def dequantify_text(text: str) -> str:
    """把文本中的精确中文数词降级为模糊表达。

    规则：
    - 保留剧情必需数词（第X章、X楼、X号、X分钟等）
    - 其他层级/时间/数量词降级为'几/数/多/一'前缀
    - 阿拉伯数字不处理（已有其他规则控制）
    """
    if not text:
        return text

    def _replace(match: re.Match) -> str:
        full = match.group(0)
        suffix = match.group(2)
        # 如果后面紧跟剧情必需后缀，保留
        if _STORY_ESSENTIAL_SUFFIXES.match(suffix):
            return full
        # 否则降级：根据后缀选择合适模糊词
        if suffix in ("日", "年", "月", "时辰", "刻"):
            return "数" + suffix
        if suffix in ("层", "级", "阶", "段", "境", "域", "重", "关", "道", "条"):
            return "几" + suffix
        return "多" + suffix

    # 匹配"第?中文数词+可降级后缀"，但跳过"第"前缀（如第几层保留）
    pattern = re.compile(r"(?<!第)(" + _CN_NUM + r")(" + _DEGRADABLE_SUFFIXES.pattern + r")")
    return pattern.sub(_replace, text)


def dequantify_dict(data: dict[str, str]) -> dict[str, str]:
    """对字典中所有字符串值做降级处理。"""
    return {k: dequantify_text(v) if isinstance(v, str) else v for k, v in data.items()}
