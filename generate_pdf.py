#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Merge Fanqie writer courses into a single PDF book."""

import json
import re
from pathlib import Path
from datetime import datetime
from fpdf import FPDF
import markdown
from bs4 import BeautifulSoup, NavigableString

BASE_DIR = Path('e:/2/NoveOs-master/fanqie_writer_courses')
INDEX_FILE = BASE_DIR / 'index.json'
OUTPUT_PDF = BASE_DIR / '番茄小说创作课_从新手到大神.pdf'

FONT_PATH = 'C:/Windows/Fonts/msyh.ttc'
FONT_BOLD_PATH = 'C:/Windows/Fonts/msyhbd.ttc'


class CoursePDF(FPDF):
    def header(self):
        if self.page_no() > 2:
            self.set_font('YaHei', '', 9)
            self.cell(0, 8, '番茄小说创作课：从新手到大神', align='C',
                      new_x='LMARGIN', new_y='NEXT')
            self.ln(2)

    def footer(self):
        if self.page_no() > 2:
            self.set_y(-15)
            self.set_font('YaHei', '', 9)
            self.cell(0, 10, f'- {self.page_no()} -', align='C')


def parse_md_file(md_path: Path):
    text = md_path.read_text(encoding='utf-8')
    # Extract title line
    title_match = re.search(r'^#\s+(.+)$', text, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else md_path.stem

    # Extract metadata block (before ---)
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

    # Body: after second ---
    parts = text.split('---', 2)
    body_md = parts[-1].strip() if len(parts) >= 3 else text
    return title, meta, body_md


def write_html_node(pdf: FPDF, node):
    """Recursively write BeautifulSoup nodes to PDF."""
    if isinstance(node, NavigableString):
        txt = str(node).strip()
        if txt:
            pdf.write(7, txt)
        return

    tag = node.name
    if tag in ('h1', 'h2', 'h3', 'h4'):
        sizes = {'h1': 16, 'h2': 14, 'h3': 12, 'h4': 11}
        pdf.ln(4)
        pdf.set_font('YaHei', 'B', sizes.get(tag, 11))
        for child in node.children:
            write_html_node(pdf, child)
        pdf.ln(6)
        pdf.set_font('YaHei', '', 10.5)
    elif tag == 'p':
        pdf.ln(2)
        for child in node.children:
            write_html_node(pdf, child)
        pdf.ln(5)
    elif tag == 'br':
        pdf.ln(4)
    elif tag == 'strong' or tag == 'b':
        pdf.set_font('YaHei', 'B', 10.5)
        for child in node.children:
            write_html_node(pdf, child)
        pdf.set_font('YaHei', '', 10.5)
    elif tag == 'em' or tag == 'i':
        # fpdf doesn't have real italic for this font; keep same
        for child in node.children:
            write_html_node(pdf, child)
    elif tag == 'a':
        txt = node.get_text(strip=True)
        href = node.get('href', '')
        if txt:
            pdf.set_text_color(0, 0, 255)
            pdf.write(7, txt, link=href)
            pdf.set_text_color(0, 0, 0)
    elif tag == 'img':
        # Skip remote images in PDF to avoid network/size issues
        alt = node.get('alt', '')
        if alt:
            pdf.set_font('YaHei', '', 9)
            pdf.set_text_color(128, 128, 128)
            pdf.write(7, f'[图片: {alt}]')
            pdf.set_text_color(0, 0, 0)
            pdf.set_font('YaHei', '', 10.5)
    elif tag in ('ul', 'ol'):
        pdf.ln(2)
        for li in node.find_all('li', recursive=False):
            pdf.cell(5)
            pdf.write(7, '• ')
            for child in li.children:
                write_html_node(pdf, child)
            pdf.ln(5)
        pdf.ln(2)
    elif tag == 'li':
        # handled by parent
        for child in node.children:
            write_html_node(pdf, child)
    elif tag == 'blockquote':
        pdf.set_font('YaHei', '', 10)
        pdf.set_text_color(80, 80, 80)
        pdf.cell(8)
        for child in node.children:
            write_html_node(pdf, child)
        pdf.set_text_color(0, 0, 0)
        pdf.set_font('YaHei', '', 10.5)
    elif tag in ('div', 'span'):
        for child in node.children:
            write_html_node(pdf, child)
    else:
        # fallback: just text
        txt = node.get_text(strip=True)
        if txt:
            pdf.write(7, txt)


def main():
    with open(INDEX_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    courses = data['courses']
    stats = data['stats']

    pdf = CoursePDF()
    # Register fonts
    pdf.add_font('YaHei', '', FONT_PATH)
    pdf.add_font('YaHei', 'B', FONT_BOLD_PATH)

    # Cover
    pdf.add_page()
    pdf.set_font('YaHei', 'B', 32)
    pdf.ln(80)
    pdf.cell(0, 25, '番茄小说创作课', align='C', new_x='LMARGIN', new_y='NEXT')
    pdf.set_font('YaHei', '', 18)
    pdf.cell(0, 14, '从新手到大神', align='C', new_x='LMARGIN', new_y='NEXT')
    pdf.ln(20)
    pdf.set_font('YaHei', '', 12)
    pdf.cell(0, 10, f'共收录 {len(courses)} 门课程', align='C', new_x='LMARGIN', new_y='NEXT')
    for cat, count in sorted(stats.items()):
        pdf.cell(0, 8, f'{cat}: {count} 门', align='C', new_x='LMARGIN', new_y='NEXT')
    pdf.ln(20)
    pdf.set_font('YaHei', '', 10)
    pdf.cell(0, 8, f'生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M")}', align='C')

    # Table of contents (outline generated by start_section)
    pdf.add_page()
    pdf.start_section('目录', level=0)
    pdf.set_font('YaHei', 'B', 20)
    pdf.cell(0, 15, '目  录', align='C', new_x='LMARGIN', new_y='NEXT')
    pdf.ln(8)
    pdf.set_font('YaHei', '', 11)

    current_cat = None
    for course in courses:
        cat = course['category']
        if cat != current_cat:
            current_cat = cat
            pdf.ln(5)
            pdf.set_font('YaHei', 'B', 13)
            pdf.cell(0, 10, f'▍{cat}', new_x='LMARGIN', new_y='NEXT')
            pdf.set_font('YaHei', '', 11)
        title = course['title']
        # Truncate if too long
        if len(title) > 40:
            title = title[:38] + '...'
        pdf.cell(0, 8, f'  {title}', new_x='LMARGIN', new_y='NEXT')

    # Content chapters
    md = markdown.Markdown()
    for i, course in enumerate(courses, 1):
        md_path = BASE_DIR / course['filename']
        if not md_path.exists():
            continue

        title, meta, body_md = parse_md_file(md_path)

        pdf.add_page()
        # Level 1 bookmark for category change, level 2 for course
        if i == 1 or course['category'] != courses[i - 2]['category']:
            pdf.start_section(course['category'], level=0)
        pdf.start_section(title, level=1)

        # Chapter title
        pdf.set_font('YaHei', 'B', 18)
        pdf.multi_cell(0, 11, title)
        pdf.ln(4)

        # Metadata
        pdf.set_font('YaHei', '', 9)
        pdf.set_text_color(100, 100, 100)
        meta_line = f"分类: {meta.get('category', course['category'])}  |  发布时间: {meta.get('publish_time', '')}  |  原文: {meta.get('link', course['link'])}"
        pdf.multi_cell(0, 6, meta_line)
        pdf.set_text_color(0, 0, 0)
        pdf.ln(6)

        # Convert markdown body to HTML
        html_body = md.convert(body_md)
        md.reset()
        soup = BeautifulSoup(html_body, 'html.parser')

        pdf.set_font('YaHei', '', 10.5)
        for node in soup.body.children if soup.body else soup.children:
            if isinstance(node, NavigableString):
                continue
            write_html_node(pdf, node)

        if i % 20 == 0:
            print(f'[{i}/{len(courses)}] processed: {title}')

    pdf.output(str(OUTPUT_PDF))
    print(f'\nPDF saved: {OUTPUT_PDF}')
    print(f'Total pages: {pdf.page_no()}')


if __name__ == '__main__':
    main()
