"""Generate HTML and PDF from the Novel-OS partnership proposal Markdown."""
from __future__ import annotations

import markdown
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE_DIR = Path(__file__).parent.parent
MD_PATH = BASE_DIR / "docs" / "Novel-OS 合作方案.md"
HTML_PATH = BASE_DIR / "docs" / "Novel-OS 合作方案.html"
PDF_PATH = BASE_DIR / "docs" / "Novel-OS 合作方案.pdf"

CSS = """
<style>
  @page { size: A4; margin: 2cm; }
  body {
    font-family: "PingFang SC", "Microsoft YaHei", "Noto Sans SC", sans-serif;
    line-height: 1.7;
    color: #1f2937;
    max-width: 900px;
    margin: 0 auto;
    padding: 2rem;
  }
  h1 { font-size: 2.2rem; color: #111827; border-bottom: 3px solid #2563eb; padding-bottom: 0.5rem; margin-top: 2rem; }
  h2 { font-size: 1.6rem; color: #1f2937; margin-top: 2rem; border-left: 5px solid #2563eb; padding-left: 0.8rem; }
  h3 { font-size: 1.25rem; color: #374151; margin-top: 1.5rem; }
  blockquote {
    border-left: 4px solid #2563eb;
    background: #eff6ff;
    margin: 1rem 0;
    padding: 0.8rem 1.2rem;
    color: #1e40af;
  }
  table {
    width: 100%;
    border-collapse: collapse;
    margin: 1.2rem 0;
    font-size: 0.95rem;
  }
  th, td {
    border: 1px solid #d1d5db;
    padding: 0.7rem 0.9rem;
    text-align: left;
  }
  th { background: #f3f4f6; font-weight: 600; }
  tr:nth-child(even) { background: #f9fafb; }
  code {
    background: #f3f4f6;
    padding: 0.15rem 0.35rem;
    border-radius: 0.25rem;
    font-family: "SFMono-Regular", Consolas, monospace;
  }
  pre {
    background: #1f2937;
    color: #f9fafb;
    padding: 1rem;
    border-radius: 0.5rem;
    overflow-x: auto;
  }
  ul, ol { margin: 0.8rem 0; padding-left: 1.5rem; }
  li { margin: 0.3rem 0; }
  hr { border: none; border-top: 1px solid #e5e7eb; margin: 2rem 0; }
  .subtitle { font-size: 1.3rem; color: #4b5563; margin-top: -0.5rem; }
</style>
"""


def build_html() -> str:
    md_text = MD_PATH.read_text(encoding="utf-8")
    html_body = markdown.markdown(
        md_text,
        extensions=["tables", "fenced_code", "toc"],
    )
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Novel-OS 合作方案</title>
  {CSS}
</head>
<body>
{html_body}
</body>
</html>
"""


def save_html(html: str) -> None:
    HTML_PATH.write_text(html, encoding="utf-8")
    print(f"HTML saved: {HTML_PATH}")


def save_pdf(html_path: Path, pdf_path: Path) -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(f"file:///{html_path.resolve().as_posix()}")
        page.pdf(
            path=str(pdf_path),
            format="A4",
            margin={"top": "2cm", "bottom": "2cm", "left": "2cm", "right": "2cm"},
            print_background=True,
        )
        browser.close()
    print(f"PDF saved: {pdf_path}")


def main() -> None:
    if not MD_PATH.exists():
        raise FileNotFoundError(f"Markdown not found: {MD_PATH}")

    html = build_html()
    save_html(html)
    save_pdf(HTML_PATH, PDF_PATH)


if __name__ == "__main__":
    main()
