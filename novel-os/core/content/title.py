"""标题提取、验证与插入 —— 纯函数优先。"""
from __future__ import annotations

import logging
import re

logger = logging.getLogger("novel-os.content.title")


def extract_from_director(director_prompt: str, chapter_num: int) -> str:
    """从 Director 任务卡中提取章节标题，并验证章节号匹配。

    匹配格式：
        【标题】第X章：标题名
        第X章：标题名
    """
    lines = director_prompt.strip().splitlines()
    for line in lines[:8]:
        line = line.strip()
        # 带【标题】前缀
        if line.startswith("【标题】"):
            inner = line[4:].strip()
            m = re.match(r"第\s*(\d+)\s*章\s*[：:\s_]*(.+)", inner)
            if m:
                declared_num = int(m.group(1))
                title = m.group(2).strip()
                if declared_num == chapter_num:
                    return title[:20]
                else:
                    return ""
        # 无前缀
        m = re.match(r"第\s*(\d+)\s*章\s*[：:\s_]*(.+)", line)
        if m:
            declared_num = int(m.group(1))
            title = m.group(2).strip()
            if declared_num == chapter_num:
                return title[:20]
            else:
                return ""
    return ""


def extract_from_content(chapter_num: int, content: str) -> str:
    """从正文内容中提取章节标题，支持多种格式，严格校验章节号。"""
    if not content.strip():
        return "未命名"

    lines = content.strip().splitlines()

    # 策略1: 匹配 markdown 格式 # 第X章 标题
    md_pattern = re.compile(r"^#\s*第\s*(\d+)\s*章\s*[：:\s_]*(.+)$")
    for line in lines[:5]:
        m = md_pattern.match(line.strip())
        if m:
            declared_num = int(m.group(1))
            title = m.group(2).strip()
            if declared_num == chapter_num:
                return title

    # 策略2: 匹配 第X章 标题（无 markdown，支持中文数字）
    plain_pattern = re.compile(r"^第\s*(\d+|一|二|三|四|五|六|七|八|九|十)\s*章\s*[：:\s_]*(.+)$")
    for line in lines[:5]:
        m = plain_pattern.match(line.strip())
        if m:
            num_str = m.group(1)
            title = m.group(2).strip()
            cn_to_num = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
            declared_num = cn_to_num.get(num_str, int(num_str) if num_str.isdigit() else -1)
            if declared_num == chapter_num:
                return title

    # 策略3: 在全文搜索 "第N章" 附近是否有标题提示
    search_pattern = re.compile(r"第\s*" + str(chapter_num) + r"\s*章\s*[：:\s_]*([^\n]{1,30})")
    m = search_pattern.search(content)
    if m:
        return m.group(1).strip()

    return "未命名"


def is_title_present(chapter_num: int, content: str) -> bool:
    """检查正文首行是否已是正确标题。"""
    lines = content.strip().splitlines()
    if not lines:
        return False
    first = lines[0].strip()
    pattern = re.compile(r"^第\s*" + str(chapter_num) + r"\s*章\s*[：:\s_]*.+$")
    return bool(pattern.match(first))


def strip_title_prefix(chapter_num: int, content: str) -> tuple[str, str]:
    """从正文开头剥离章节标题，并返回（清洗后正文, 标题）。

    支持格式：
        第X章：标题
        # 第X章：标题
        第X章 标题
    只处理正文前 5 行内出现的第一个匹配标题。
    """
    if not content.strip():
        return content, ""

    lines = content.splitlines()
    title = ""
    start_idx = 0

    md_pattern = re.compile(r"^#\s*第\s*(\d+)\s*章\s*[：:\s_]*(.+)$")
    plain_pattern = re.compile(r"^第\s*(\d+)\s*章\s*[：:\s_]*(.+)$")

    for idx, raw_line in enumerate(lines[:5]):
        line = raw_line.strip()
        if not line:
            continue
        m = md_pattern.match(line) or plain_pattern.match(line)
        if m and int(m.group(1)) == chapter_num:
            title = m.group(2).strip()
            start_idx = idx + 1
            # 同时去掉标题后的空行
            while start_idx < len(lines) and not lines[start_idx].strip():
                start_idx += 1
            break

    cleaned = "\n".join(lines[start_idx:]).strip()
    if title:
        logger.info("第 %d 章 已从正文剥离标题 '%s'", chapter_num, title)
    return cleaned, title


def ensure_prefix(chapter_num: int, content: str, title: str = "") -> str:
    """标题兜底：检查正文首行是否为标题格式，如果没有则插入标题。

    Args:
        chapter_num: 章节号
        content: 正文内容
        title: 已知标题，为空时尝试从 content 提取

    Returns:
        带标题前缀的正文
    """
    if not content.strip():
        return content
    if is_title_present(chapter_num, content):
        return content

    if not title:
        title = extract_from_content(chapter_num, content)
        if title == "未命名":
            title = ""

    if title:
        new_content = f"第{chapter_num}章：{title}\n\n{content.strip()}"
        logger.info("第 %d 章 标题兜底：插入标题 '%s'", chapter_num, title)
        return new_content

    return content


def safe_filename(title: str) -> str:
    """清理标题中的非法文件名字符。"""
    return re.sub(r'[\\/:*?"<>|]', "", title)[:20]
