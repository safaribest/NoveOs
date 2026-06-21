#!/usr/bin/env python3
"""
RAG深度发掘引擎 v2.0
跨品类模式挖掘：章节微结构、品类DNA、平台适配度、模板可迁移性
"""
import re, json, statistics, math
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime

RAG = Path(r"D:\noveos\RAG")
OUT = Path(r"D:\noveos\rag_deep_analysis")
OUT.mkdir(exist_ok=True)

# ══════════════════════════════════════════════════════
#  UTILITIES
# ══════════════════════════════════════════════════════

def read_novel(filepath):
    try:
        return filepath.read_text(encoding="utf-8", errors="ignore")
    except:
        try:
            return filepath.read_text(encoding="gbk", errors="ignore")
        except:
            return ""

def split_chapters(text):
    chapters = []
    pat = r'第[一二三四五六七八九十百千\d]+[章节][^\n]*'
    splits = re.split(f'({pat})', text)
    header = None
    for part in splits:
        if re.match(pat, part):
            header = part.strip()
        elif header and len(re.findall(r'[一-鿿]', part)) > 100:
            chapters.append({"title": header, "text": part.strip()})
            header = None
    if not chapters and len(re.findall(r'[一-鿿]', text)) > 5000:
        paras = text.split('\n')
        chunk, ch_num = "", 1
        for p in paras:
            chunk += p + '\n'
            if len(re.findall(r'[一-鿿]', chunk)) > 2000:
                chapters.append({"title": f"Ch{ch_num}", "text": chunk.strip()})
                chunk, ch_num = "", ch_num + 1
        if chunk.strip():
            chapters.append({"title": f"Ch{ch_num}", "text": chunk.strip()})
    return chapters

# ══════════════════════════════════════════════════════
#  DEEP ANALYSIS 1: Chapter Micro-Structure
# ══════════════════════════════════════════════════════

def analyze_chapter_microstructure(chapters, max_ch=30):
    """Analyze the internal rhythm of chapters: paragraph length patterns,
    dialogue clustering, scene break frequency"""
    sample = chapters[:min(max_ch, len(chapters))]

    results = {
        "para_len_sequence": [],      # Paragraph length pattern within chapters
        "dialogue_clusters": [],      # Where dialogue bunches up
        "scene_breaks_per_ch": [],    # How many scene changes per chapter
        "opening_type": Counter(),    # How chapters start
        "closing_type": Counter(),    # How chapters end
        "para_len_variance": [],      # How much paragraph length varies within a chapter
    }

    for ch in sample:
        text = ch['text']
        paras_raw = text.split('\n')

        # Measure each paragraph's Chinese char count
        para_lens = []
        for p in paras_raw:
            cn = len(re.findall(r'[一-鿿]', p))
            if cn > 3:
                para_lens.append(cn)

        if not para_lens:
            continue

        results["para_len_sequence"].append(para_lens)
        results["para_len_variance"].append(round(statistics.stdev(para_lens), 1) if len(para_lens) > 1 else 0)

        # Dialogue detection per paragraph
        dial_markers = []
        for p in paras_raw:
            cn = len(re.findall(r'[一-鿿]', p))
            if cn < 3:
                continue
            is_dial = bool(re.search(r'[""' "''「」『』]", p) or re.search(r'[说问道喊叫骂嚷答]', p[:30]))
            dial_markers.append(1 if is_dial else 0)

        # Find dialogue clusters (consecutive dialogue paragraphs)
        cluster_sizes = []
        cluster = 0
        for m in dial_markers:
            if m == 1:
                cluster += 1
            else:
                if cluster >= 2:
                    cluster_sizes.append(cluster)
                cluster = 0
        if cluster >= 2:
            cluster_sizes.append(cluster)

        results["dialogue_clusters"].append({
            "count": len(cluster_sizes),
            "avg_size": round(statistics.mean(cluster_sizes), 1) if cluster_sizes else 0,
            "max_size": max(cluster_sizes) if cluster_sizes else 0
        })

        # Scene breaks (consecutive empty lines or separator patterns)
        scene_breaks = len(re.findall(r'\n\s*\n\s*\n+', text))
        results["scene_breaks_per_ch"].append(scene_breaks)

        # Opening analysis - first 100 chars
        first_100 = text.strip()[:100]
        if re.search(r'["""' "''「]", first_100):
            results["opening_type"]["对话开场"] += 1
        elif re.search(r'(?:忽然|突然|正在|正要|就在|这时|那天|这日)', first_100):
            results["opening_type"]["事件切入"] += 1
        elif re.search(r'(?:阿|老|林|楚|叶|苏|沈|顾|陆)', first_100):
            results["opening_type"]["人物引入"] += 1
        elif re.search(r'(?:【|系统|叮|恭喜|提示)', first_100):
            results["opening_type"]["系统/信息面板"] += 1
        else:
            results["opening_type"]["情境描写"] += 1

        # Closing analysis - last 200 chars
        last_200 = text.strip()[-200:]
        if re.search(r'[？?]', last_200[-50:]):
            results["closing_type"]["疑问悬念"] += 1
        elif re.search(r'(?:正要|就要|刚要|即将|马上|准备|打算)', last_200[-50:]):
            results["closing_type"]["动作悬念"] += 1
        elif re.search(r'(?:心中|心想|暗|念及|不知|或许|也许|怕是)', last_200[-50:]):
            results["closing_type"]["内心余韵"] += 1
        elif re.search(r'(?:笑|哭|叹|点头|摇头|嗯|好)', last_200[-50:]):
            results["closing_type"]["情绪定格"] += 1
        else:
            results["closing_type"]["叙述收束"] += 1

    return results


# ══════════════════════════════════════════════════════
#  DEEP ANALYSIS 2: Genre DNA Fingerprinting
# ══════════════════════════════════════════════════════

def extract_genre_dna(novels_in_genre):
    """Extract the unique structural DNA of a genre"""
    if len(novels_in_genre) < 3:
        return None

    dna = {
        "sentence_rhythm": defaultdict(list),  # Per-novel sentence length stats
        "dialogue_signature": {},              # Dialogue verb preferences
        "chapter_pacing": {},                  # Chapter length consistency
        "emotion_profile": {},                 # Emotion density pattern
        "scene_density": {},                   # Scenes per chapter
        "unique_markers": Counter(),           # Genre-specific vocabulary
    }

    for novel in novels_in_genre:
        path = novel.get('path')
        if not path or not Path(path).exists():
            continue
        content = read_novel(Path(path))
        chapters = split_chapters(content)
        if not chapters:
            continue

        sample = chapters[:min(20, len(chapters))]

        # Sentence rhythm
        all_sent_lens = []
        scene_counts = []

        for ch in sample:
            text = ch['text']
            sents = re.split(r'[。！？…]+', text)
            for s in sents:
                cn_s = len(re.findall(r'[一-鿿]', s))
                if 1 < cn_s < 100:
                    all_sent_lens.append(cn_s)

            # Scene breaks
            scene_counts.append(len(re.findall(r'\n\s*\n\s*\n+', text)))

        if all_sent_lens:
            dna["sentence_rhythm"]["mean"].append(round(statistics.mean(all_sent_lens), 1))
            dna["sentence_rhythm"]["median"].append(round(statistics.median(all_sent_lens), 1))
            # Proportion of very short sentences (<8 chars) - creates urgency
            short_pct = sum(1 for s in all_sent_lens if s <= 8) / len(all_sent_lens) * 100
            dna["sentence_rhythm"]["short_pct"].append(round(short_pct, 1))
            # Proportion of long sentences (>40 chars) - creates description density
            long_pct = sum(1 for s in all_sent_lens if s >= 40) / len(all_sent_lens) * 100
            dna["sentence_rhythm"]["long_pct"].append(round(long_pct, 1))

        if scene_counts:
            dna["scene_density"]["avg_scenes_per_ch"] = round(statistics.mean(scene_counts), 1)

        # Dialogue signature
        sample_text = '\n'.join(ch['text'] for ch in sample)
        dial_verbs = re.findall(r'(?:说|道|问|喊|叫|骂|嚷|答|告诉|讲|谈|聊|吼|喝|冷声|低声|轻声|淡淡)', sample_text)
        if dial_verbs:
            vc = Counter(dial_verbs)
            for v, c in vc.most_common(8):
                dna["dialogue_signature"][v] = dna["dialogue_signature"].get(v, 0) + c

    # Normalize
    if dna["dialogue_signature"]:
        total = sum(dna["dialogue_signature"].values())
        dna["dialogue_signature"] = {k: round(v/total*100, 1) for k, v in
                                      sorted(dna["dialogue_signature"].items(), key=lambda x: -x[1])[:8]}

    # Aggregate metrics
    for key in ["mean", "median", "short_pct", "long_pct"]:
        if dna["sentence_rhythm"].get(key):
            vals = dna["sentence_rhythm"][key]
            dna["sentence_rhythm"][key] = round(statistics.mean(vals), 1)

    return dna


# ══════════════════════════════════════════════════════
#  DEEP ANALYSIS 3: Platform Fitness Scoring
# ══════════════════════════════════════════════════════

def score_platform_fitness(novel_data):
    """Score how well a novel's structure matches 番茄/七猫 platform preferences.

    番茄 platform preferences (inferred from recommendation patterns):
    - Consistent chapter length (CV < 20%): favors algorithmic scheduling
    - Moderate dialogue density (25-40%): keeps readers engaged without fatigue
    - Short paragraphs (avg < 100 chars): mobile reading optimized
    - Regular cliffhangers (every 2-3 chapters): retention hooks
    - "他" density < 2%: readability
    - Chapter length 1500-3500: mobile-optimized reading sessions
    """
    m = novel_data.get('metrics', {})
    score = 0
    details = []

    # Chapter consistency (max 25 pts)
    cv = m.get('ch_cv_pct', 100)
    if cv < 10:
        score += 25
        details.append("章字数极稳定(CV<10%): +25")
    elif cv < 20:
        score += 20
        details.append("章字数稳定(CV<20%): +20")
    elif cv < 35:
        score += 12
        details.append("章字数较稳(CV<35%): +12")
    else:
        score += 5
        details.append("章字数波动大: +5")

    # Chapter length range (max 20 pts)
    ch_cn = m.get('avg_ch_cn', 0)
    if 1500 <= ch_cn <= 2500:
        score += 20
        details.append(f"黄金章长({ch_cn}字): +20")
    elif 2500 <= ch_cn <= 3500:
        score += 15
        details.append(f"良好章长({ch_cn}字): +15")
    elif ch_cn >= 1000:
        score += 8
        details.append(f"可接受章长({ch_cn}字): +8")

    # Dialogue density (max 15 pts)
    dial = m.get('avg_dial_pct', 0)
    if 25 <= dial <= 45:
        score += 15
        details.append(f"黄金对话密度({dial:.0f}%): +15")
    elif 15 <= dial <= 55:
        score += 10
        details.append(f"可接受对话密度({dial:.0f}%): +10")
    else:
        score += 5
        details.append(f"极端对话密度({dial:.0f}%): +5")

    # Sentence length - mobile readability (max 15 pts)
    sent_len = m.get('avg_sent_len', 30)
    if 18 <= sent_len <= 28:
        score += 15
        details.append(f"黄金句长({sent_len:.0f}字): +15")
    elif 15 <= sent_len <= 35:
        score += 10
        details.append(f"可接受句长({sent_len:.0f}字): +10")
    else:
        score += 5
        details.append(f"极端句长({sent_len:.0f}字): +5")

    # Ta density (max 15 pts)
    ta = m.get('avg_ta_density', 0)
    if ta < 1.0:
        score += 15
        details.append(f"他密度极低({ta:.1f}%): +15")
    elif ta < 2.0:
        score += 12
        details.append(f"他密度健康({ta:.1f}%): +12")
    elif ta < 3.0:
        score += 7
        details.append(f"他密度偏高({ta:.1f}%): +7")
    else:
        score += 3
        details.append(f"他密度超标({ta:.1f}%): +3")

    # Suspense ending ratio (max 10 pts)
    susp = m.get('suspense_ending_pct', 0)
    if 40 <= susp <= 65:
        score += 10
        details.append(f"悬念节奏黄金({susp:.0f}%): +10")
    elif 30 <= susp <= 75:
        score += 7
        details.append(f"悬念节奏良好({susp:.0f}%): +7")
    else:
        score += 3
        details.append(f"悬念节奏极端({susp:.0f}%): +3")

    tier = "S" if score >= 85 else ("A" if score >= 70 else ("B" if score >= 55 else "C"))

    return {"score": score, "tier": tier, "details": details}


# ══════════════════════════════════════════════════════
#  DEEP ANALYSIS 4: Template Transferability Matrix
# ══════════════════════════════════════════════════════

def build_transfer_matrix(all_novels_by_genre):
    """Build a matrix showing which genre templates can transfer to which other genres"""
    genres = sorted(all_novels_by_genre.keys())

    # Calculate genre centroids
    centroids = {}
    for genre, novels in all_novels_by_genre.items():
        if len(novels) < 3:
            continue
        centroids[genre] = {
            "avg_ch_cn": statistics.mean([n['metrics']['avg_ch_cn'] for n in novels]),
            "avg_sent_len": statistics.mean([n['metrics']['avg_sent_len'] for n in novels]),
            "avg_dial_pct": statistics.mean([n['metrics']['avg_dial_pct'] for n in novels]),
            "avg_ta": statistics.mean([n['metrics']['avg_ta_density'] for n in novels]),
            "avg_suspense": statistics.mean([n['metrics']['suspense_ending_pct'] for n in novels]),
        }

    # Calculate "transferability scores" between genres
    matrix = {}
    for g1 in centroids:
        matrix[g1] = {}
        c1 = centroids[g1]
        for g2 in centroids:
            if g1 == g2:
                matrix[g1][g2] = 100
                continue
            c2 = centroids[g2]
            # Euclidean distance normalized
            dims = ['avg_ch_cn', 'avg_sent_len', 'avg_dial_pct', 'avg_ta', 'avg_suspense']
            max_vals = {d: max(centroids[g][d] for g in centroids) for d in dims}
            min_vals = {d: min(centroids[g][d] for g in centroids) for d in dims}

            dist = 0
            for d in dims:
                if max_vals[d] == min_vals[d]:
                    continue
                norm1 = (c1[d] - min_vals[d]) / (max_vals[d] - min_vals[d])
                norm2 = (c2[d] - min_vals[d]) / (max_vals[d] - min_vals[d])
                dist += (norm1 - norm2) ** 2
            dist = math.sqrt(dist)
            # Convert to similarity score (100 = identical, 0 = completely different)
            matrix[g1][g2] = round(max(0, 100 - dist * 40), 1)

    return matrix, centroids


# ══════════════════════════════════════════════════════
#  MAIN EXECUTION
# ══════════════════════════════════════════════════════

print(f"DEEP ANALYSIS START: {datetime.now().strftime('%H:%M:%S')}")
print(f"Source: {RAG}")
print()

# Collect all novels with file paths
all_novels = []
for genre_dir in sorted(RAG.iterdir()):
    if not genre_dir.is_dir():
        continue
    for txt_file in sorted(genre_dir.glob("*.txt")):
        all_novels.append({
            "path": str(txt_file),
            "genre": genre_dir.name,
            "name": txt_file.stem
        })

print(f"Total novels found: {len(all_novels)}")
print()

# ── PHASE 1: Chapter Micro-Structure Analysis ──
print("=" * 60)
print("PHASE 1: Chapter Micro-Structure Analysis")
print("=" * 60)

micro_results = {}
for novel in all_novels[:50]:  # Sample top 50 by size for micro analysis
    try:
        content = read_novel(Path(novel['path']))
        cn = len(re.findall(r'[一-鿿]', content))
        if cn < 5000:
            continue
    except:
        continue

    chapters = split_chapters(content)
    if len(chapters) < 5:
        continue

    micro = analyze_chapter_microstructure(chapters)
    micro_results[f"{novel['genre']}/{novel['name']}"] = micro

# Aggregate opening/closing patterns across all books
all_openings = Counter()
all_closings = Counter()
para_len_variances = []
dialogue_cluster_sizes = []
scene_breaks_avg = []

for key, micro in micro_results.items():
    all_openings.update(micro['opening_type'])
    all_closings.update(micro['closing_type'])
    para_len_variances.extend(micro['para_len_variance'])
    for dc in micro['dialogue_clusters']:
        if dc['avg_size'] > 0:
            dialogue_cluster_sizes.append(dc['avg_size'])
    scene_breaks_avg.extend(micro['scene_breaks_per_ch'])

total_openings = sum(all_openings.values())
total_closings = sum(all_closings.values())

opening_report = {k: round(v/total_openings*100, 1) for k, v in all_openings.most_common()}
closing_report = {k: round(v/total_closings*100, 1) for k, v in all_closings.most_common()}

avg_scene_breaks = round(statistics.mean(scene_breaks_avg), 1) if scene_breaks_avg else 0

micro_summary = {
    "opening_patterns": opening_report,
    "closing_patterns": closing_report,
    "avg_para_len_variance": round(statistics.mean(para_len_variances), 1) if para_len_variances else 0,
    "avg_dialogue_cluster_size": round(statistics.mean(dialogue_cluster_sizes), 1) if dialogue_cluster_sizes else 0,
    "avg_scene_breaks_per_chapter": avg_scene_breaks,
}

print(f"  Analyzed {len(micro_results)} novels for micro-structure")
print(f"  Opening patterns (top): {dict(list(opening_report.items())[:3])}")
print(f"  Closing patterns (top): {dict(list(closing_report.items())[:3])}")
print(f"  Avg para length variance: {micro_summary['avg_para_len_variance']}")
print(f"  Avg dialogue cluster size: {micro_summary['avg_dialogue_cluster_size']}")
print(f"  Avg scene breaks/chapter: {avg_scene_breaks}")
print()

# ── PHASE 2: Genre DNA Extraction ──
print("=" * 60)
print("PHASE 2: Genre DNA Fingerprinting")
print("=" * 60)

genre_dna = {}
by_genre_novels = defaultdict(list)
for novel in all_novels:
    by_genre_novels[novel['genre']].append(novel)

for genre, novels in sorted(by_genre_novels.items()):
    dna = extract_genre_dna(novels)
    if dna:
        genre_dna[genre] = dna
        sent_r = dna.get('sentence_rhythm', {})
        print(f"  {genre}: 句长均值={sent_r.get('mean','?')}字, "
              f"短句(<8字)占比={sent_r.get('short_pct','?')}%, "
              f"长句(>40字)占比={sent_r.get('long_pct','?')}%, "
              f"对话动词={dna.get('dialogue_signature',{})}")
print()

# ── PHASE 3: Platform Fitness Scoring ──
print("=" * 60)
print("PHASE 3: Platform Fitness Scoring (番茄/七猫)")
print("=" * 60)

# Load existing analysis data
master_path = Path(r"D:\noveos\rag_analysis\master_index.json")
if master_path.exists():
    master = json.loads(master_path.read_text(encoding='utf-8'))

# Build fitness scores
fitness_scores = []
for genre_name, novels in by_genre_novels.items():
    for novel in novels:
        # Load individual novel JSON
        novel_json_path = Path(r"D:\noveos\rag_analysis\novels") / genre_name / f"{novel['name'].replace('/','_').replace(':','_')[:60]}.json"
        if novel_json_path.exists():
            try:
                nd = json.loads(novel_json_path.read_text(encoding='utf-8'))
                fitness = score_platform_fitness(nd)
                fitness['name'] = novel['name']
                fitness['genre'] = genre_name
                fitness['chapters'] = nd.get('chapters', 0)
                fitness['total_cn'] = nd.get('total_cn', 0)
                fitness_scores.append(fitness)
            except:
                pass

fitness_scores.sort(key=lambda x: -x['score'])

# Top and bottom
print(f"  Scored {len(fitness_scores)} novels")
print(f"\n  TOP 15 Platform-Ready Novels:")
for i, f in enumerate(fitness_scores[:15]):
    print(f"  {i+1:>2}. [{f['tier']}] {f['name'][:30]:<30} {f['genre']:<10} score={f['score']} {f['chapters']}ch {f['total_cn']}字")

print(f"\n  BOTTOM 10 (least platform-fit):")
for i, f in enumerate(fitness_scores[-10:]):
    print(f"  {len(fitness_scores)-9+i:>2}. [{f['tier']}] {f['name'][:30]:<30} {f['genre']:<10} score={f['score']}")

# Genre average fitness
genre_fitness = defaultdict(list)
for f in fitness_scores:
    genre_fitness[f['genre']].append(f['score'])

print(f"\n  Genre Platform Fitness Ranking:")
for genre, scores in sorted(genre_fitness.items(), key=lambda x: -statistics.mean(x[1])):
    print(f"    {genre:<12} avg={statistics.mean(scores):.0f}  best={max(scores)}  worst={min(scores)}  count={len(scores)}")
print()

# ── PHASE 4: Template Transferability Matrix ──
print("=" * 60)
print("PHASE 4: Template Transferability Matrix")
print("=" * 60)

# Build novel data dictionaries by genre
genre_novels_data = defaultdict(list)
for genre_name, novels in by_genre_novels.items():
    for novel in novels:
        novel_json_path = Path(r"D:\noveos\rag_analysis\novels") / genre_name / f"{novel['name'].replace('/','_').replace(':','_')[:60]}.json"
        if novel_json_path.exists():
            try:
                nd = json.loads(novel_json_path.read_text(encoding='utf-8'))
                genre_novels_data[genre_name].append(nd)
            except:
                pass

matrix, centroids = build_transfer_matrix(genre_novels_data)

print(f"  Template Transferability (100 = identical structure, genes closest together):")
print()
# Header
genres_list = sorted(centroids.keys())
print(f"  {'FROM \\ TO':<12}", end="")
for g in genres_list:
    print(f"{g[:6]:>8}", end="")
print()
print(f"  {'':-<12}", end="")
print(f"{'':->{len(genres_list)*8}}")

for g1 in genres_list:
    print(f"  {g1:<12}", end="")
    for g2 in genres_list:
        val = matrix.get(g1, {}).get(g2, 0)
        marker = "##" if val >= 80 else ("~~" if val >= 65 else (".." if val >= 50 else "  "))
        print(f"{marker}{val:>4.0f} ", end="")
    print()

print(f"\n  Most transferable genre pairs:")
pairs = []
for g1 in matrix:
    for g2 in matrix[g1]:
        if g1 < g2:
            pairs.append((g1, g2, matrix[g1][g2]))
pairs.sort(key=lambda x: -x[2])
for g1, g2, score in pairs[:10]:
    print(f"    {g1} <-> {g2}: {score:.0f}% 结构相似度")

# ── PHASE 5: Cross-Genre Archetypes ──
print(f"\n{'='*60}")
print("PHASE 5: Cross-Genre Narrative Archetypes")
print(f"{'='*60}")

# Cluster novels by structural similarity
# Using simple feature vector: [ch_cn, sent_len, dial_pct, ta_density, suspense_pct]
features = []
for f in fitness_scores:
    # Get full data
    novel_json_path = Path(r"D:\noveos\rag_analysis\novels") / f['genre'] / f"{f['name'].replace('/','_').replace(':','_')[:60]}.json"
    if novel_json_path.exists():
        try:
            nd = json.loads(novel_json_path.read_text(encoding='utf-8'))
            m = nd.get('metrics', {})
            features.append({
                "name": f['name'],
                "genre": f['genre'],
                "ch_cn": m.get('avg_ch_cn', 0),
                "sent_len": m.get('avg_sent_len', 0),
                "dial_pct": m.get('avg_dial_pct', 0),
                "ta": m.get('avg_ta_density', 0),
                "suspense": m.get('suspense_ending_pct', 0),
            })
        except:
            pass

# Define archetypes based on dominant features
archetypes = {
    "短章对白体": [],    # ch_cn < 2500, dial > 50%
    "中章均衡体": [],     # 2500 <= ch_cn < 4000, 25 <= dial <= 50
    "长章叙事体": [],     # ch_cn >= 4000, dial < 35%
    "动作驱动体": [],     # sent_len < 25, ta < 1.5%
    "文艺描写体": [],     # sent_len > 35, ta > 2.5%
}

for f in features:
    if f['ch_cn'] < 2500 and f['dial_pct'] > 50:
        archetypes["短章对白体"].append(f)
    if 2500 <= f['ch_cn'] < 4000 and 25 <= f['dial_pct'] <= 50:
        archetypes["中章均衡体"].append(f)
    if f['ch_cn'] >= 4000 and f['dial_pct'] < 35:
        archetypes["长章叙事体"].append(f)
    if f['sent_len'] < 25 and f['ta'] < 1.5:
        archetypes["动作驱动体"].append(f)
    if f['sent_len'] > 35 and f['ta'] > 2.5:
        archetypes["文艺描写体"].append(f)

for archetype, members in archetypes.items():
    if members:
        genres_in = Counter(m['genre'] for m in members)
        print(f"\n  [{archetype}] {len(members)}本: {dict(genres_in.most_common(5))}")
        # Show 3 examples
        for m in members[:3]:
            print(f"    {m['name'][:30]:<30} {m['genre']:<10} {m['ch_cn']:.0f}字/章 句长{m['sent_len']:.0f} 对话{m['dial_pct']:.0f}%")

# ── SAVE ALL RESULTS ──
deep_results = {
    "analysis_time": datetime.now().isoformat(),
    "micro_structure": micro_summary,
    "genre_dna": {g: {
        "sentence_rhythm": d.get('sentence_rhythm', {}),
        "dialogue_signature": d.get('dialogue_signature', {}),
        "scene_density": d.get('scene_density', {}),
    } for g, d in genre_dna.items()},
    "platform_fitness": {
        "top_20": [
            {"name": f['name'], "genre": f['genre'], "score": f['score'], "tier": f['tier'],
             "details": f['details']}
            for f in fitness_scores[:20]
        ],
        "genre_ranking": {g: round(statistics.mean(scores), 1) for g, scores in
                         sorted(genre_fitness.items(), key=lambda x: -statistics.mean(x[1]))},
        "tier_distribution": {
            "S": sum(1 for f in fitness_scores if f['tier'] == 'S'),
            "A": sum(1 for f in fitness_scores if f['tier'] == 'A'),
            "B": sum(1 for f in fitness_scores if f['tier'] == 'B'),
            "C": sum(1 for f in fitness_scores if f['tier'] == 'C'),
        }
    },
    "transferability": {
        "matrix": matrix,
        "centroids": centroids,
        "top_pairs": [{"from": g1, "to": g2, "similarity": s} for g1, g2, s in pairs[:15]]
    },
    "archetypes": {k: {
        "count": len(v),
        "genre_distribution": dict(Counter(m['genre'] for m in v).most_common(5)),
        "examples": [{"name": m['name'], "genre": m['genre']} for m in v[:5]]
    } for k, v in archetypes.items() if v}
}

(OUT / "deep_analysis.json").write_text(
    json.dumps(deep_results, ensure_ascii=False, indent=2), encoding='utf-8'
)

print(f"\n{'='*60}")
print(f"DEEP ANALYSIS COMPLETE: {datetime.now().strftime('%H:%M:%S')}")
print(f"Output: {OUT / 'deep_analysis.json'}")
