#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Regenerate Fanqie writer courses PDF with better taxonomy and reading experience."""

import json
import re
from pathlib import Path
from datetime import datetime
from fpdf import FPDF
import markdown
from bs4 import BeautifulSoup, NavigableString

BASE_DIR = Path('e:/2/NoveOs-master/fanqie_writer_courses')
INDEX_FILE = BASE_DIR / 'index.json'
OUTPUT_PDF = BASE_DIR / '番茄小说创作课_从新手到大神_重排版.pdf'

FONT_PATH = 'C:/Windows/Fonts/msyh.ttc'
FONT_BOLD_PATH = 'C:/Windows/Fonts/msyhbd.ttc'

# Part intros
PART_INTROS = {
    '入门必读与平台规则': '先搞懂规则再动笔。本部分收录账号注册、实名认证、平台规则、稿费福利、作品完结等基础内容，帮助新手快速了解番茄平台的运作方式。',
    '开书准备': '动笔之前，先做对选择。本部分围绕选题、题材、构思、大纲、开篇等关键环节，帮你建立一本书的骨架。',
    '写作技法': '把故事写好看的核心方法。本部分涵盖人物塑造、冲突设计、爽点设计、对白、节奏、钩子、改文等实战技巧。',
    '作品包装与运营': '好内容也要被发现。本部分包括书名、封面、简介、标签、拉新、粉丝运营、稳定更新等让作品突围的运营方法。',
    '品类指南': '不同题材有不同的写法。本部分按玄幻、都市、古言、现言、悬疑、科幻、历史等品类整理，帮你找到细分赛道的切入点。',
    'IP与改编运营': '从网文到IP。本部分涉及IP价值、IP改编、短剧/漫剧改编风向，以及如何判断作品改编潜力。',
    '版权与平台规则': '保护自己的作品。本部分聚焦版权说系列、抄袭判定、申诉维权、签约审核等平台规则。',
    '大神创作谈': '站在过来人肩上。本部分收录番茄平台大神作家、编辑、文学大师的访谈与创作经验，提供真实可感的成长路径。',
    '训练营与专题': '系统化精进。本部分整理训练营精品课、专项练习、大师课等专题内容。',
}

PART_ORDER = [
    '入门必读与平台规则',
    '开书准备',
    '写作技法',
    '作品包装与运营',
    '品类指南',
    'IP与改编运营',
    '版权与平台规则',
    '大神创作谈',
    '训练营与专题',
]


class CoursePDF(FPDF):
    def header(self):
        if self.page_no() > 2:
            self.set_font('YaHei', '', 8)
            self.set_text_color(120, 120, 120)
            self.cell(0, 7, '番茄小说创作课：从新手到大神', align='C',
                      new_x='LMARGIN', new_y='NEXT')
            self.set_text_color(0, 0, 0)

    def footer(self):
        if self.page_no() > 2:
            self.set_y(-12)
            self.set_font('YaHei', '', 8)
            self.set_text_color(120, 120, 120)
            self.cell(0, 8, f'- {self.page_no()} -', align='C')
            self.set_text_color(0, 0, 0)

    def chapter_title(self, title):
        self.set_font('YaHei', 'B', 17)
        self.set_text_color(30, 30, 30)
        self.multi_cell(0, 11, title)
        self.ln(3)

    def part_title_page(self, part_name, chapter_count):
        self.add_page()
        self.set_font('YaHei', 'B', 26)
        self.set_text_color(180, 40, 40)
        self.ln(60)
        self.cell(0, 18, part_name, align='C', new_x='LMARGIN', new_y='NEXT')
        self.set_text_color(80, 80, 80)
        self.set_font('YaHei', '', 13)
        self.ln(10)
        self.cell(0, 10, f'共 {chapter_count} 章', align='C', new_x='LMARGIN', new_y='NEXT')
        intro = PART_INTROS.get(part_name, '')
        if intro:
            self.ln(20)
            self.set_font('YaHei', '', 11)
            self.set_text_color(60, 60, 60)
            self.multi_cell(0, 8, intro)
            self.set_text_color(0, 0, 0)


CN_NUM = {'一':1,'二':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9,'十':10,
          '十一':11,'十二':12,'十三':13,'二十':20,'二十五':25,
          '1':1,'2':2,'3':3,'4':4,'5':5,'6':6,'7':7,'8':8,'9':9,'10':10,'11':11,'12':12,'13':13}


def classify(course):
    t = course['title']
    
    # 训练营与专题
    if any(k in t for k in ['训练营', '专项练习', '大师课', '教学局']):
        return '训练营与专题'
    
    # 大神创作谈（访谈、经验、作家自述、大师课）
    if any(k in t for k in ['作家', '作者', '自述', '创作经验', '大神答疑', '十二日谈', '番茄大师课', '专访']):
        return '大神创作谈'
    if re.search(r'《[^》]+》[:：]', t):
        return '大神创作谈'
    if re.search(r'从\d+个阅读|从拒稿到|从流水线|从钢筋工|年入百万|月入|在读|追更|日收|完读率|这本.*从.*到', t):
        return '大神创作谈'
    if 'TOP' in t.upper():
        return '大神创作谈'
    if any(k in t for k in ['他为什么能写出', '鸟松米', '采薇采薇']):
        return '大神创作谈'
    
    # 版权与平台规则
    if any(k in t for k in ['版权', '抄袭', '审核', '请假', '签约', '维权', '被下架']):
        return '版权与平台规则'
    
    # 入门必读（账号、规则、福利、稿费）
    if any(k in t for k in ['账号注册', '实名认证', '平台规则', '稿费', '福利', '稿酬', '定时发布']):
        return '入门必读与平台规则'
    
    # IP与改编
    if any(k in t for k in ['IP价值', 'IP改编', '改编风向标', '改编']):
        return 'IP与改编运营'
    
    # 作品包装与运营
    if any(k in t for k in ['书名', '封面', '简介', '标签', '包装', '推广', '完结', '社区推广', '粉丝群', '多书名', '拉新', '投放', '推荐字数', '不断更', '榜单新风向']):
        return '作品包装与运营'
    
    # 开书准备
    if any(k in t for k in ['开书准备', '如何构思', '选题', '大纲', '开篇', '如何写好新书', '灵感', '题材选择', '网络文学发展史']):
        return '开书准备'
    
    # 写作技法
    if any(k in t for k in ['人物塑造', '对白', '冲突', '爽点', '代入感', '剧情', '副本', '节奏', '改文', '稳定更新', '悬念', '反转', '时间线', '场景', '动作', '细节', '情绪', '句式', '视角', '崩文', '差评', '钩子', '避雷', '素材', '写作地图', '编辑说', '金番讲写作']):
        return '写作技法'
    
    # 品类指南
    if any(k in t for k in ['品类', '玄幻', '都市', '古言', '现言', '悬疑', '科幻', '历史', '种田', '宫斗', '宅斗', '甜宠', '虐恋', '脑洞', '修仙', '重生', '穿越', '年代', '刑侦', '武侠', '仙侠', '奇幻', '短剧', '短故事', '职业文', '新媒体', '番茄历史课']):
        return '品类指南'
    
    return '其他精选课程'


def extract_series_num(title):
    """Extract episode/lecture number for sorting series courses."""
    # 第X集 / 第X讲 / 第X期
    m = re.search(r'第\s*([一二三四五六七八九十0-9]+)\s*[集讲期]', title)
    if m:
        s = m.group(1)
        if s.isdigit():
            return int(s)
        return CN_NUM.get(s, 0)
    return 9999


def course_sort_key(course):
    return (extract_series_num(course['title']), course['title'])


def parse_md_file(md_path: Path):
    text = md_path.read_text(encoding='utf-8')
    title_match = re.search(r'^#\s+(.+)$', text, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else md_path.stem

    meta = {}
    meta_block = re.search(r'\*\*分类\*\*:\s*(.+?)\n', text)
    if meta_block:
        meta['category'] = meta_block.group(1).strip()
    time_block = re.search(r'\*\*发布时间\*\*:\s*(.+?)\n', text)
    if time_block:
        ts = time_block.group(1).strip()
        try:
            meta['publish_time'] = datetime.fromtimestamp(int(ts)).strftime('%Y-%m-%d')
        except Exception:
            meta['publish_time'] = ts
    link_block = re.search(r'\*\*原文链接\*\*:\s*(.+?)\n', text)
    if link_block:
        meta['link'] = link_block.group(1).strip()

    parts = text.split('---', 2)
    if len(parts) >= 3:
        body_md = parts[-1].strip()
    elif len(parts) == 2:
        body_md = parts[1].strip()
    else:
        body_md = text
    return title, meta, body_md


def first_paragraph_text(body_md):
    """Extract first meaningful paragraph as summary."""
    lines = [l.strip() for l in body_md.split('\n') if l.strip() and not l.strip().startswith('!') and not l.strip().startswith('[')]
    if lines:
        txt = lines[0]
        if len(txt) > 200:
            txt = txt[:198] + '...'
        return txt
    return ''


def write_html_node(pdf: FPDF, node):
    if isinstance(node, NavigableString):
        txt = str(node).strip()
        if txt:
            pdf.write(6.5, txt)
        return

    tag = node.name
    if tag in ('h1', 'h2', 'h3', 'h4'):
        sizes = {'h1': 15, 'h2': 13, 'h3': 11.5, 'h4': 10.5}
        pdf.ln(4)
        pdf.set_font('YaHei', 'B', sizes.get(tag, 11))
        for child in node.children:
            write_html_node(pdf, child)
        pdf.ln(5)
        pdf.set_font('YaHei', '', 10)
    elif tag == 'p':
        pdf.ln(2)
        for child in node.children:
            write_html_node(pdf, child)
        pdf.ln(5)
    elif tag == 'br':
        pdf.ln(3)
    elif tag in ('strong', 'b'):
        pdf.set_font('YaHei', 'B', 10)
        for child in node.children:
            write_html_node(pdf, child)
        pdf.set_font('YaHei', '', 10)
    elif tag in ('em', 'i'):
        for child in node.children:
            write_html_node(pdf, child)
    elif tag == 'a':
        txt = node.get_text(strip=True)
        href = node.get('href', '')
        if txt:
            pdf.set_text_color(0, 80, 160)
            pdf.write(6.5, txt, link=href)
            pdf.set_text_color(0, 0, 0)
    elif tag == 'img':
        alt = node.get('alt', '')
        if alt:
            pdf.set_font('YaHei', '', 8)
            pdf.set_text_color(128, 128, 128)
            pdf.write(6.5, f'[图片: {alt}]')
            pdf.set_text_color(0, 0, 0)
            pdf.set_font('YaHei', '', 10)
    elif tag in ('ul', 'ol'):
        pdf.ln(2)
        for li in node.find_all('li', recursive=False):
            pdf.cell(6)
            pdf.write(6.5, '• ')
            for child in li.children:
                write_html_node(pdf, child)
            pdf.ln(5)
        pdf.ln(2)
    elif tag == 'li':
        for child in node.children:
            write_html_node(pdf, child)
    elif tag == 'blockquote':
        pdf.set_font('YaHei', '', 9)
        pdf.set_text_color(80, 80, 80)
        pdf.cell(8)
        for child in node.children:
            write_html_node(pdf, child)
        pdf.set_text_color(0, 0, 0)
        pdf.set_font('YaHei', '', 10)
    elif tag in ('div', 'span'):
        for child in node.children:
            write_html_node(pdf, child)
    else:
        txt = node.get_text(strip=True)
        if txt:
            pdf.write(6.5, txt)


def main():
    with open(INDEX_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    courses = data['courses']
    
    # Classify and sort
    classified = {}
    for part in PART_ORDER:
        classified[part] = []
    classified['其他精选课程'] = []
    
    for c in courses:
        cat = classify(c)
        if cat in classified:
            classified[cat].append(c)
        else:
            classified['其他精选课程'].append(c)
    
    # Sort each category to keep series courses in correct order
    for cat in classified:
        classified[cat].sort(key=course_sort_key)
    
    pdf = CoursePDF()
    pdf.add_font('YaHei', '', FONT_PATH)
    pdf.add_font('YaHei', 'B', FONT_BOLD_PATH)
    pdf.set_auto_page_break(auto=True, margin=20)

    # Cover
    pdf.add_page()
    pdf.set_font('YaHei', 'B', 34)
    pdf.set_text_color(180, 40, 40)
    pdf.ln(70)
    pdf.cell(0, 28, '番茄小说创作课', align='C', new_x='LMARGIN', new_y='NEXT')
    pdf.set_text_color(50, 50, 50)
    pdf.set_font('YaHei', '', 18)
    pdf.cell(0, 14, '从新手到大神', align='C', new_x='LMARGIN', new_y='NEXT')
    pdf.ln(25)
    pdf.set_font('YaHei', '', 11)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 9, f'精选 {len(courses)} 门番茄作家课堂课程，按学习路径重新编排', align='C', new_x='LMARGIN', new_y='NEXT')
    total_parts = sum(1 for p in PART_ORDER if classified[p])
    pdf.cell(0, 9, f'全书共 {total_parts} 大模块', align='C', new_x='LMARGIN', new_y='NEXT')
    pdf.ln(30)
    pdf.set_font('YaHei', '', 9)
    pdf.cell(0, 7, f'生成时间: {datetime.now().strftime("%Y-%m-%d")}', align='C')

    # Table of contents
    pdf.add_page()
    pdf.start_section('目录', level=0)
    pdf.set_font('YaHei', 'B', 20)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(0, 16, '目  录', align='C', new_x='LMARGIN', new_y='NEXT')
    pdf.ln(6)
    
    for part in PART_ORDER + ['其他精选课程']:
        items = classified[part]
        if not items:
            continue
        pdf.set_font('YaHei', 'B', 12)
        pdf.set_text_color(180, 40, 40)
        pdf.ln(4)
        pdf.cell(0, 9, f'{part}（{len(items)} 章）', new_x='LMARGIN', new_y='NEXT')
        pdf.set_font('YaHei', '', 9.5)
        pdf.set_text_color(60, 60, 60)
        for c in items:
            title = c['title']
            if len(title) > 38:
                title = title[:36] + '...'
            pdf.cell(0, 7, f'  {title}', new_x='LMARGIN', new_y='NEXT')
        pdf.set_text_color(0, 0, 0)

    # Content
    md = markdown.Markdown()
    chapter_counter = 0
    
    for part in PART_ORDER + ['其他精选课程']:
        items = classified[part]
        if not items:
            continue
        
        pdf.part_title_page(part, len(items))
        pdf.start_section(part, level=0)
        
        for c in items:
            chapter_counter += 1
            md_path = BASE_DIR / c['filename']
            if not md_path.exists():
                continue
            
            title, meta, body_md = parse_md_file(md_path)
            
            pdf.add_page()
            pdf.start_section(title, level=1)
            
            # Chapter header with number
            pdf.set_font('YaHei', '', 9)
            pdf.set_text_color(150, 150, 150)
            pdf.cell(0, 7, f'第 {chapter_counter} 章  ·  {part}', new_x='LMARGIN', new_y='NEXT')
            pdf.set_text_color(0, 0, 0)
            pdf.ln(1)
            
            pdf.chapter_title(title)
            
            # Summary box
            summary = first_paragraph_text(body_md)
            if summary:
                pdf.set_fill_color(245, 245, 245)
                pdf.set_font('YaHei', '', 9)
                pdf.set_text_color(70, 70, 70)
                pdf.multi_cell(0, 6, f'【本章导读】{summary}', fill=True)
                pdf.set_text_color(0, 0, 0)
                pdf.ln(5)
            
            # Body
            html_body = md.convert(body_md)
            md.reset()
            soup = BeautifulSoup(html_body, 'html.parser')
            
            pdf.set_font('YaHei', '', 10)
            for node in (soup.body.children if soup.body else soup.children):
                if isinstance(node, NavigableString):
                    continue
                write_html_node(pdf, node)
            
            if chapter_counter % 20 == 0:
                print(f'[{chapter_counter}/{len(courses)}] processed: {title}')

    pdf.output(str(OUTPUT_PDF))
    print(f'\nPDF saved: {OUTPUT_PDF}')
    print(f'Total pages: {pdf.page_no()}')


if __name__ == '__main__':
    main()
