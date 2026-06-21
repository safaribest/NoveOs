import markdown
from markdown.extensions import fenced_code, tables, toc

with open('docs/Novel-OS_架构梳理.md', 'r', encoding='utf-8') as f:
    md_content = f.read()

md = markdown.Markdown(extensions=['fenced_code', 'tables', 'toc'])
html_body = md.convert(md_content)
toc_html = md.toc

html_template = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Novel-OS 架构梳理</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github.min.css">
<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/languages/python.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/languages/bash.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/languages/typescript.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/languages/json.min.js"></script>
<style>
  :root {{
    --bg: #F5F5F7;
    --card: #FFFFFF;
    --text: #1D1D1F;
    --text-secondary: #86868B;
    --accent: #007AFF;
    --accent-light: #E6F2FF;
    --border: rgba(0,0,0,0.08);
    --code-bg: #F6F8FA;
    --sidebar-width: 280px;
    --radius: 18px;
    --shadow: 0 4px 24px rgba(0,0,0,0.06);
    --shadow-lg: 0 12px 40px rgba(0,0,0,0.1);
  }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  html {{ scroll-behavior: smooth; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", Roboto, "Helvetica Neue", Arial, "Noto Sans SC", sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.75;
    font-size: 15px;
    -webkit-font-smoothing: antialiased;
  }}
  .top-nav {{
    position: fixed; top: 0; left: 0; right: 0; height: 52px;
    background: rgba(255,255,255,0.72);
    backdrop-filter: blur(20px) saturate(180%);
    -webkit-backdrop-filter: blur(20px) saturate(180%);
    border-bottom: 1px solid var(--border);
    z-index: 100;
    display: flex; align-items: center; justify-content: space-between;
    padding: 0 24px;
  }}
  .top-nav .brand {{
    font-weight: 600; font-size: 16px; letter-spacing: -0.3px;
    display: flex; align-items: center; gap: 10px;
  }}
  .top-nav .brand svg {{ width: 22px; height: 22px; }}
  .top-nav .actions {{ display: flex; gap: 12px; align-items: center; }}
  .btn {{
    padding: 6px 14px; border-radius: 8px; border: none;
    font-size: 13px; font-weight: 500; cursor: pointer;
    background: var(--accent); color: #fff;
    transition: transform .15s, box-shadow .15s;
  }}
  .btn:hover {{ transform: translateY(-1px); box-shadow: 0 4px 12px rgba(0,122,255,0.3); }}
  .btn-ghost {{
    background: transparent; color: var(--text-secondary);
  }}
  .btn-ghost:hover {{ background: rgba(0,0,0,0.04); transform: none; box-shadow: none; }}
  .layout {{
    display: flex; padding-top: 52px; min-height: 100vh;
  }}
  .sidebar {{
    position: fixed; top: 52px; left: 0; bottom: 0; width: var(--sidebar-width);
    overflow-y: auto; overflow-x: hidden;
    background: rgba(255,255,255,0.6);
    backdrop-filter: blur(16px);
    border-right: 1px solid var(--border);
    padding: 24px 16px 40px;
    z-index: 90;
  }}
  .sidebar::-webkit-scrollbar {{ width: 5px; }}
  .sidebar::-webkit-scrollbar-thumb {{ background: rgba(0,0,0,0.12); border-radius: 10px; }}
  .toc-title {{
    font-size: 11px; font-weight: 600; text-transform: uppercase;
    letter-spacing: 0.8px; color: var(--text-secondary);
    margin-bottom: 12px; padding-left: 8px;
  }}
  .toc ul {{ list-style: none; }}
  .toc li {{ margin: 2px 0; }}
  .toc a {{
    display: block; padding: 5px 10px; border-radius: 8px;
    text-decoration: none; color: var(--text-secondary); font-size: 13px;
    transition: all .15s; line-height: 1.5;
    border-left: 3px solid transparent;
  }}
  .toc a:hover {{ background: rgba(0,0,0,0.03); color: var(--text); }}
  .toc a.active {{ background: var(--accent-light); color: var(--accent); border-left-color: var(--accent); font-weight: 500; }}
  .toc ul ul a {{ padding-left: 22px; font-size: 12.5px; }}
  .toc ul ul ul a {{ padding-left: 36px; }}
  .main {{
    margin-left: var(--sidebar-width);
    flex: 1; padding: 40px 32px 80px;
    max-width: 900px; width: 100%;
  }}
  .content-card {{
    background: var(--card); border-radius: var(--radius);
    box-shadow: var(--shadow); padding: 48px 56px;
    animation: fadeUp .6s ease both;
  }}
  @keyframes fadeUp {{
    from {{ opacity: 0; transform: translateY(20px); }}
    to {{ opacity: 1; transform: translateY(0); }}
  }}
  h1, h2, h3, h4, h5, h6 {{
    font-weight: 700; letter-spacing: -0.4px; line-height: 1.3;
    margin-top: 1.8em; margin-bottom: 0.6em;
  }}
  h1 {{ font-size: 32px; margin-top: 0; letter-spacing: -0.8px; }}
  h2 {{ font-size: 24px; padding-bottom: 10px; border-bottom: 1px solid var(--border); margin-top: 2em; }}
  h3 {{ font-size: 19px; color: #1d1d1f; margin-top: 1.6em; }}
  h4 {{ font-size: 16px; margin-top: 1.4em; }}
  p {{ margin: 0.8em 0; }}
  a {{ color: var(--accent); text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  blockquote {{
    border-left: 4px solid var(--accent); background: var(--accent-light);
    padding: 12px 18px; border-radius: 0 10px 10px 0;
    margin: 1em 0; color: #1a1a1a;
  }}
  blockquote p {{ margin: 0; }}
  hr {{
    border: none; height: 1px; background: var(--border); margin: 2.5em 0;
  }}
  ul, ol {{ margin: 0.8em 0; padding-left: 1.6em; }}
  li {{ margin: 4px 0; }}
  pre {{
    background: var(--code-bg); border-radius: 12px;
    padding: 18px 20px; overflow-x: auto;
    font-size: 13.5px; line-height: 1.6;
    border: 1px solid var(--border); margin: 1em 0;
  }}
  pre code {{ background: none; padding: 0; font-size: inherit; border: none; }}
  code {{
    background: rgba(0,122,255,0.08); color: #0066cc;
    padding: 2px 6px; border-radius: 5px; font-size: 13.5px;
    font-family: "SF Mono", Monaco, "Cascadia Code", Consolas, monospace;
  }}
  table {{
    width: 100%; border-collapse: collapse; margin: 1.2em 0;
    font-size: 14px; border-radius: 10px; overflow: hidden;
    box-shadow: 0 0 0 1px var(--border);
  }}
  th, td {{ padding: 10px 14px; text-align: left; border-bottom: 1px solid var(--border); }}
  th {{ background: #FAFAFA; font-weight: 600; font-size: 13px; color: var(--text-secondary); }}
  tr:last-child td {{ border-bottom: none; }}
  tr:hover td {{ background: #FAFBFC; }}
  pre.ascii-art, pre.ascii-art code {{
    background: #1D1D1F !important;
    color: #F5F5F7 !important;
    font-family: "SF Mono", Monaco, Consolas, monospace !important;
  }}
  .back-to-top {{
    position: fixed; bottom: 28px; right: 28px;
    width: 42px; height: 42px; border-radius: 50%;
    background: var(--card); border: 1px solid var(--border);
    box-shadow: var(--shadow-lg); cursor: pointer;
    display: flex; align-items: center; justify-content: center;
    opacity: 0; pointer-events: none; transition: opacity .3s, transform .3s;
    z-index: 80;
  }}
  .back-to-top.visible {{ opacity: 1; pointer-events: auto; }}
  .back-to-top:hover {{ transform: translateY(-2px); }}
  .back-to-top svg {{ width: 18px; height: 18px; stroke: var(--text-secondary); }}
  @media (max-width: 1024px) {{
    .sidebar {{ transform: translateX(-100%); transition: transform .3s; }}
    .sidebar.open {{ transform: translateX(0); }}
    .main {{ margin-left: 0; padding: 24px 20px; max-width: 100%; }}
    .content-card {{ padding: 32px 24px; }}
    .overlay {{
      position: fixed; inset: 0; background: rgba(0,0,0,0.25);
      z-index: 85; opacity: 0; pointer-events: none; transition: opacity .3s;
    }}
    .overlay.open {{ opacity: 1; pointer-events: auto; }}
  }}
  @media (min-width: 1025px) {{ .hamburger, .overlay {{ display: none; }} }}
  .hamburger {{
    background: none; border: none; cursor: pointer; padding: 4px;
    display: flex; flex-direction: column; gap: 4px;
  }}
  .hamburger span {{
    display: block; width: 20px; height: 2px; background: var(--text);
    border-radius: 2px;
  }}
</style>
</head>
<body>
<nav class="top-nav">
  <div class="brand">
    <button class="hamburger" onclick="toggleSidebar()" aria-label="menu">
      <span></span><span></span><span></span>
    </button>
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"></path><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"></path></svg>
    Novel-OS 架构梳理
  </div>
  <div class="actions">
    <a href="https://github.com/ColinZFF-1/NoveOs" target="_blank" class="btn btn-ghost">GitHub</a>
  </div>
</nav>
<div class="overlay" id="overlay" onclick="toggleSidebar()"></div>
<div class="layout">
  <aside class="sidebar" id="sidebar">
    <div class="toc-title">目录</div>
    <div class="toc">
      {toc_html}
    </div>
  </aside>
  <main class="main">
    <article class="content-card">
      {html_body}
    </article>
    <div style="text-align:center; margin-top:40px; color:var(--text-secondary); font-size:13px;">
      © Novel-OS Project · 生成于 2026-05-29
    </div>
  </main>
</div>
<button class="back-to-top" id="backToTop" onclick="window.scrollTo({{top:0, behavior:'smooth'}})">
  <svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 15l-6-6-6 6"/></svg>
</button>
<script>
  // Detect ASCII art blocks and style them
  document.querySelectorAll('pre code').forEach(function(block) {{
    const text = block.textContent || '';
    if (/[┌┐└┘├┤┬┴┼│─┄┅┆┇┈┉┊┋╌╍╎╏]/.test(text) || (/^\s*[│├└┌]/.test(text))) {{
      block.parentElement.classList.add('ascii-art');
    }}
  }});
  hljs.highlightAll();
  const headings = document.querySelectorAll('h1[id], h2[id], h3[id], h4[id]');
  const tocLinks = document.querySelectorAll('.toc a');
  function updateActive(){{
    let current = '';
    for (const h of headings){{
      if (h.getBoundingClientRect().top <= 100) current = h.id;
    }}
    tocLinks.forEach(a => {{
      a.classList.toggle('active', a.getAttribute('href') === '#' + current);
    }});
  }}
  window.addEventListener('scroll', updateActive, {{passive:true}});
  updateActive();
  const btt = document.getElementById('backToTop');
  window.addEventListener('scroll', () => {{
    btt.classList.toggle('visible', window.scrollY > 600);
  }}, {{passive:true}});
  function toggleSidebar(){{
    document.getElementById('sidebar').classList.toggle('open');
    document.getElementById('overlay').classList.toggle('open');
  }}
</script>
</body>
</html>'''

with open('docs/index.html', 'w', encoding='utf-8') as f:
    f.write(html_template)

print('Generated docs/index.html successfully')
