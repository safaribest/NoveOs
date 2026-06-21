#!/usr/bin/env python3
"""
RAG全库批量小说结构分析引擎
逐本提取：结构节拍表 + 语言指纹 + 情绪曲线 + 品类模板
输出：每本独立JSON + 品类汇总JSON + 全库索引
"""
import re, json, statistics, os, sys
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime

RAG = Path(r"D:\noveos\RAG")
OUT = Path(r"D:\noveos\rag_analysis")
OUT.mkdir(exist_ok=True)

# ── Analysis functions ──

def split_chapters(text):
    """Split text into chapters, handling various formats."""
    # Try standard chapter markers
    patterns = [
        r'第[一二三四五六七八九十百千\d]+章[^\n]*',
        r'第[一二三四五六七八九十百千\d]+节[^\n]*',
        r'Chapter\s+\d+',
        r'[Cc][Hh]\d+',
    ]

    chapters = []
    for pat in patterns:
        splits = re.split(f'({pat})', text)
        if len(splits) > 3:
            chapters = []
            header = None
            for part in splits:
                if re.match(pat, part):
                    header = part.strip()
                elif header and len(re.findall(r'[一-鿿]', part)) > 50:
                    chapters.append({"title": header, "text": part.strip()})
                    header = None
            if chapters:
                break

    # If no chapters found, treat as single chapter if short, or split by size
    if not chapters:
        cn = len(re.findall(r'[一-鿿]', text))
        if cn > 5000:
            # Split into ~2000 char chunks
            chunk_size = 2000
            paras = text.split('\n')
            chunk_text = ""
            ch_num = 1
            for p in paras:
                chunk_text += p + '\n'
                if len(re.findall(r'[一-鿿]', chunk_text)) > chunk_size:
                    chapters.append({"title": f"第{ch_num}章(自动分段)", "text": chunk_text.strip()})
                    chunk_text = ""
                    ch_num += 1
            if chunk_text.strip():
                chapters.append({"title": f"第{ch_num}章(自动分段)", "text": chunk_text.strip()})

    return chapters


def analyze_chapter(text):
    """Extract metrics from a single chapter."""
    cn = len(re.findall(r'[一-鿿]', text))
    if cn < 50:
        return None

    # Paragraphs
    paras = [p.strip() for p in text.split('\n') if p.strip() and len(re.findall(r'[一-鿿]', p)) > 3]

    # Sentences
    sents = re.split(r'[。！？…!?]+', text)
    sents = [s.strip() for s in sents if s.strip()]
    sent_lens = [len(re.findall(r'[一-鿿]', s)) for s in sents if re.findall(r'[一-鿿]', s)]
    mean_sent_len = round(statistics.mean(sent_lens), 1) if sent_lens else 0

    # Dialogue ratio
    dialogue_paras = sum(1 for p in paras if re.search(r'[""' "''「」『』“”]", p) or re.search(r'[说问道喊叫骂嚷答告诉讲谈聊]', p[:30]))
    dial_ratio = round(dialogue_paras / len(paras) * 100, 1) if paras else 0

    # Ta density
    ta_count = len(re.findall(r'[他她它]', text))
    ta_density = round(ta_count / cn * 100, 2) if cn else 0

    # Exclamation marks
    excl = len(re.findall(r'[！!]', text))

    # Action verbs
    action_pattern = r'(?:走|跑|跳|抓|拿|放|推|拉|打|拍|提|抱|抬|踢|踩|甩|扔|掏|捡|捞|爬|翻|冲|赶|追|逃|躲|坐|站|躺|蹲|跪|杀|砍|刺|射|飞|闪|跃|扑|摔|砸|劈|扫|挡|接|握|拽|扯|撕|咬|吞|咽|喝|吸|呼|吹|唱|喊|叫|吼|哭|笑|骂|说|道|问|答|讲)'
    actions = len(re.findall(action_pattern, text))

    # Question marks (for suspense detection)
    questions = len(re.findall(r'[？?]', text))

    # Dialogue verb variety
    dial_verbs = re.findall(r'(?:说|道|问|喊|叫|骂|嚷|答|告诉|讲|谈|聊|吼|喝|叱|呵|斥|责备|质问|反问|追问|笑道|哭道|怒道|冷声道|淡淡道|轻声道|低声说|高声说)', text)
    dial_verb_counter = Counter(dial_verbs)

    # Scene change detection (consecutive short lines / separators)
    scene_changes = len(re.findall(r'(?:^[*=~—\-]{3,}|^\s*$)', text, re.MULTILINE))

    return {
        "cn": cn, "paras": len(paras), "sent_len_mean": mean_sent_len,
        "dial_pct": dial_ratio, "ta_density": ta_density, "excl": excl,
        "actions": actions, "questions": questions, "scene_changes": scene_changes,
        "top_dial_verbs": dict(dial_verb_counter.most_common(5))
    }


def analyze_novel(filepath):
    """Full structural analysis of a single novel."""
    try:
        content = filepath.read_text(encoding="utf-8", errors="ignore")
    except:
        try:
            content = filepath.read_text(encoding="gbk", errors="ignore")
        except:
            return None

    total_cn = len(re.findall(r'[一-鿿]', content))
    if total_cn < 1000:
        return None

    chapters = split_chapters(content)
    chapter_metrics = []
    for ch in chapters:
        m = analyze_chapter(ch['text'])
        if m:
            m['title'] = ch['title'][:40]
            chapter_metrics.append(m)

    if not chapter_metrics:
        return None

    # Aggregate metrics
    ch_cns = [m['cn'] for m in chapter_metrics]
    avg_cn = round(statistics.mean(ch_cns))
    ch_cv = round(statistics.stdev(ch_cns) / avg_cn * 100, 1) if len(ch_cns) > 1 and avg_cn > 0 else 0

    avg_sent = round(statistics.mean([m['sent_len_mean'] for m in chapter_metrics]), 1)
    avg_dial = round(statistics.mean([m['dial_pct'] for m in chapter_metrics]), 1)
    avg_ta = round(statistics.mean([m['ta_density'] for m in chapter_metrics]), 2)
    avg_excl = round(statistics.mean([m['excl'] for m in chapter_metrics]), 1)
    avg_actions = round(statistics.mean([m['actions'] for m in chapter_metrics]), 1)

    # Emotion curve
    emotion_density = [(m['excl'] + m['actions']) / m['cn'] * 1000 for m in chapter_metrics]

    # Detect structure beats: look for recurring patterns in chapter composition
    # Analyze where dialogue clusters, action clusters, etc. appear
    # Use first 20 chapters as sample for beat detection
    sample_chs = chapter_metrics[:min(20, len(chapter_metrics))]

    # Beat analysis: for each chapter, find where dialogue peaks and action peaks
    beat_pattern = None
    if len(sample_chs) >= 5:
        # Simplified beat detection: categorize chapters by their dominant mode
        dial_heavy = sum(1 for m in sample_chs if m['dial_pct'] > 30)
        action_heavy = sum(1 for m in sample_chs if m['actions'] / max(m['cn'], 1) * 1000 > 15)

        if dial_heavy > len(sample_chs) * 0.6:
            pattern_type = "对话驱动型"
        elif action_heavy > len(sample_chs) * 0.6:
            pattern_type = "动作驱动型"
        else:
            pattern_type = "混合型"

        beat_pattern = {
            "type": pattern_type,
            "dial_heavy_chapters": dial_heavy,
            "action_heavy_chapters": action_heavy,
            "total_sampled": len(sample_chs),
            "avg_word_count": avg_cn,
            "structure_consistency": "极高" if ch_cv < 10 else ("高" if ch_cv < 20 else ("中" if ch_cv < 35 else "低"))
        }

    # Language fingerprint
    sample_text = '\n'.join(ch['text'] for ch in chapters[:min(20, len(chapters))])

    # Top verbs
    verb_pattern = r'(?:说|道|问|喊|叫|走|看|去|来|拿|吃|想|做|出|回|到|下|上|起|开|进|过|让|给|打|放|拉|推|跑|跳|抱|提|踢|追|赶|逃|笑|哭|骂|写|买|卖|坐|站|躺|洗|煮|烧|杀|死|爱|恨|怕|惊|怒|喜|悲|叹|望|听|闻|觉|记|忘|知|等|送|收|还|借|欠|花|赚|赔|分|变|成|当|为)'
    verbs = re.findall(verb_pattern, sample_text)
    vc = Counter(verbs)

    # Sentence length distribution
    all_sents = []
    for ch_text in [ch['text'] for ch in chapters[:min(20, len(chapters))]]:
        sents = re.split(r'[。！？…!?]+', ch_text)
        for s in sents:
            cn_s = len(re.findall(r'[一-鿿]', s))
            if cn_s > 0:
                all_sents.append(cn_s)

    sent_dist = {"0-10": 0, "11-20": 0, "21-30": 0, "31-50": 0, "50+": 0}
    for sl in all_sents:
        if sl <= 10: sent_dist["0-10"] += 1
        elif sl <= 20: sent_dist["11-20"] += 1
        elif sl <= 30: sent_dist["21-30"] += 1
        elif sl <= 50: sent_dist["31-50"] += 1
        else: sent_dist["50+"] += 1
    total_sents = sum(sent_dist.values())
    if total_sents > 0:
        sent_dist = {k: round(v/total_sents*100, 1) for k, v in sent_dist.items()}

    # Ending pattern analysis
    suspense_endings = 0
    calm_endings = 0
    for m in chapter_metrics:
        if m['questions'] > 2:
            suspense_endings += 1
        else:
            calm_endings += 1

    # AI-like word detection
    ai_words = ['基于', '梳理', '面向', '赋能', '抓手', '打造', '闭环', '维度', '底层',
                '复盘', '对齐', '拉通', '颗粒度', '组合拳', '解法', '体感', '水位',
                '首先', '其次', '最后', '综上所述', '值得注意的是', '换句话说', '说白了']
    ai_word_hits = {w: len(re.findall(w, sample_text)) for w in ai_words if re.findall(w, sample_text)}

    result = {
        "name": filepath.stem,
        "total_cn": total_cn,
        "chapters": len(chapter_metrics),
        "metrics": {
            "avg_ch_cn": avg_cn, "ch_cv_pct": ch_cv,
            "avg_sent_len": avg_sent, "avg_dial_pct": avg_dial,
            "avg_ta_density": avg_ta, "avg_excl_per_ch": avg_excl,
            "avg_actions_per_ch": avg_actions,
            "suspense_ending_pct": round(suspense_endings / len(chapter_metrics) * 100, 1) if chapter_metrics else 0,
            "calm_ending_pct": round(calm_endings / len(chapter_metrics) * 100, 1) if chapter_metrics else 0,
        },
        "beat_pattern": beat_pattern,
        "language_fingerprint": {
            "top_verbs": dict(vc.most_common(20)),
            "sent_len_distribution": sent_dist,
            "ai_word_hits": ai_word_hits if ai_word_hits else {},
        },
        "emotion_curve": [round(e, 1) for e in emotion_density[:30]],
        "chapter_details": chapter_metrics[:15],
    }

    return result


# ── Main ──
print(f"开始时间: {datetime.now().strftime('%H:%M:%S')}")
print(f"扫描目录: {RAG}")
print()

all_results = {}
by_genre = defaultdict(list)
total_files = 0
analyzed = 0
skipped = 0

for genre_dir in sorted(RAG.iterdir()):
    if not genre_dir.is_dir():
        continue

    genre_name = genre_dir.name
    genre_results = []

    for txt_file in sorted(genre_dir.glob("*.txt")):
        total_files += 1
        result = analyze_novel(txt_file)

        if result:
            result["genre"] = genre_name
            genre_results.append(result)
            by_genre[genre_name].append(result)
            analyzed += 1

            # Print progress
            cv_str = f"CV={result['metrics']['ch_cv_pct']:.1f}%"
            print(f"  [{analyzed:>3}] {genre_name}/{result['name'][:25]:<25} {result['chapters']:>4}ch {result['total_cn']:>8}字 {cv_str:>10}")
        else:
            skipped += 1

    if genre_results:
        all_results[genre_name] = genre_results

print(f"\n完成: {analyzed}本分析, {skipped}本跳过, {total_files}总文件")

# ── Save individual novel JSONs ──
novel_out = OUT / "novels"
novel_out.mkdir(exist_ok=True)

for genre, novels in all_results.items():
    genre_dir = novel_out / genre
    genre_dir.mkdir(exist_ok=True)
    for novel in novels:
        # Remove problematic chars from filename
        safe_name = novel['name'].replace('/', '_').replace('\\', '_').replace(':', '_')[:60]
        out_path = genre_dir / f"{safe_name}.json"
        out_path.write_text(json.dumps(novel, ensure_ascii=False, indent=2), encoding='utf-8')

# ── Save genre summaries ──
genre_summaries = {}
for genre, novels in all_results.items():
    if len(novels) < 2:
        continue

    all_cn = [n['total_cn'] for n in novels]
    all_chs = [n['chapters'] for n in novels]
    all_cv = [n['metrics']['ch_cv_pct'] for n in novels if n['metrics']['ch_cv_pct'] > 0]
    all_sent = [n['metrics']['avg_sent_len'] for n in novels]
    all_dial = [n['metrics']['avg_dial_pct'] for n in novels]
    all_ta = [n['metrics']['avg_ta_density'] for n in novels]

    # Most structured novels
    structured = sorted(
        [n for n in novels if n['metrics']['ch_cv_pct'] > 0 and n['chapters'] >= 10],
        key=lambda x: x['metrics']['ch_cv_pct']
    )[:10]

    # Most dialogue-heavy
    dial_heavy = sorted(novels, key=lambda x: -x['metrics']['avg_dial_pct'])[:5]

    # Most action-heavy
    action_heavy = sorted(novels, key=lambda x: -x['metrics']['avg_actions_per_ch'])[:5]

    genre_summaries[genre] = {
        "novel_count": len(novels),
        "total_cn_chars": sum(all_cn),
        "avg_novel_cn": round(statistics.mean(all_cn)),
        "avg_chapters": round(statistics.mean(all_chs)),
        "avg_ch_cv_pct": round(statistics.mean(all_cv), 1) if all_cv else 0,
        "avg_sent_len": round(statistics.mean(all_sent), 1),
        "avg_dial_pct": round(statistics.mean(all_dial), 1),
        "avg_ta_density": round(statistics.mean(all_ta), 2),
        "most_structured": [
            {"name": n['name'], "cv": n['metrics']['ch_cv_pct'], "ch_cn": n['metrics']['avg_ch_cn'],
             "chapters": n['chapters'], "dial_pct": n['metrics']['avg_dial_pct'], "genre": n.get('genre','')}
            for n in structured[:5]
        ],
        "most_dialogue_heavy": [
            {"name": n['name'], "dial_pct": n['metrics']['avg_dial_pct'], "sent_len": n['metrics']['avg_sent_len']}
            for n in dial_heavy
        ],
        "most_action_heavy": [
            {"name": n['name'], "actions": n['metrics']['avg_actions_per_ch'], "sent_len": n['metrics']['avg_sent_len']}
            for n in action_heavy
        ],
        "beat_pattern_distribution": {},
        "novels": [n['name'] for n in novels]
    }

    # Beat pattern distribution
    for n in novels:
        if n.get('beat_pattern'):
            pt = n['beat_pattern']['type']
            genre_summaries[genre]['beat_pattern_distribution'][pt] = \
                genre_summaries[genre]['beat_pattern_distribution'].get(pt, 0) + 1

# Save genre summaries
(OUT / "genre_summaries.json").write_text(
    json.dumps(genre_summaries, ensure_ascii=False, indent=2), encoding='utf-8'
)

# ── Save master index ──
master_index = {
    "analysis_time": datetime.now().isoformat(),
    "total_files": total_files,
    "analyzed": analyzed,
    "skipped": skipped,
    "total_cn_chars": sum(sum(n['total_cn'] for n in novels) for novels in all_results.values()),
    "genres": {},
    "top_structured_overall": [],
    "top_dialogue_overall": [],
    "top_action_overall": [],
}

# Collect all novels for cross-genre ranking
all_novels_flat = []
for novels in all_results.values():
    all_novels_flat.extend(novels)

# Top structured (low CV, many chapters)
structured_all = sorted(
    [n for n in all_novels_flat if n['metrics']['ch_cv_pct'] > 0 and n['chapters'] >= 10],
    key=lambda x: x['metrics']['ch_cv_pct']
)[:20]
master_index['top_structured_overall'] = [
    {"name": n['name'], "genre": n.get('genre',''), "cv": n['metrics']['ch_cv_pct'],
     "ch_cn": n['metrics']['avg_ch_cn'], "chapters": n['chapters'],
     "dial_pct": n['metrics']['avg_dial_pct'], "pattern": n.get('beat_pattern',{}).get('type','')}
    for n in structured_all
]

# Top dialogue
dial_all = sorted(all_novels_flat, key=lambda x: -x['metrics']['avg_dial_pct'])[:20]
master_index['top_dialogue_overall'] = [
    {"name": n['name'], "genre": n.get('genre',''), "dial_pct": n['metrics']['avg_dial_pct'],
     "sent_len": n['metrics']['avg_sent_len']}
    for n in dial_all
]

# Top action
action_all = sorted(all_novels_flat, key=lambda x: -x['metrics']['avg_actions_per_ch'])[:20]
master_index['top_action_overall'] = [
    {"name": n['name'], "genre": n.get('genre',''), "actions": n['metrics']['avg_actions_per_ch'],
     "sent_len": n['metrics']['avg_sent_len']}
    for n in action_all
]

# Genre summaries
for genre in sorted(all_results.keys()):
    novels = all_results[genre]
    all_cv = [n['metrics']['ch_cv_pct'] for n in novels if n['metrics']['ch_cv_pct'] > 0]
    master_index['genres'][genre] = {
        "count": len(novels),
        "total_cn": sum(n['total_cn'] for n in novels),
        "avg_ch_cv": round(statistics.mean(all_cv), 1) if all_cv else 0,
        "avg_sent_len": round(statistics.mean([n['metrics']['avg_sent_len'] for n in novels]), 1),
        "avg_dial_pct": round(statistics.mean([n['metrics']['avg_dial_pct'] for n in novels]), 1),
        "avg_ta_density": round(statistics.mean([n['metrics']['avg_ta_density'] for n in novels]), 2),
        "novel_names": [n['name'] for n in novels]
    }

(OUT / "master_index.json").write_text(
    json.dumps(master_index, ensure_ascii=False, indent=2), encoding='utf-8'
)

# ── Print final summary ──
print(f"\n{'='*70}")
print(f"  全库分析完成")
print(f"{'='*70}")
print(f"  输出目录: {OUT}")
print(f"  单本JSON: {novel_out}/ (按品类分目录)")
print(f"  品类汇总: genre_summaries.json")
print(f"  全库索引: master_index.json")
print(f"  总分析本数: {analyzed}")
print(f"  总中文字: {sum(n['total_cn'] for n in all_novels_flat):,}")
print(f"  品类数: {len(all_results)}")
print(f"  完成时间: {datetime.now().strftime('%H:%M:%S')}")
