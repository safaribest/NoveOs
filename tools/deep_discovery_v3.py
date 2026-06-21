#!/usr/bin/env python3
"""
RAG 深层模式挖掘引擎 v3.0
四次元分析：
  1. 幽灵作者检测 — 结构指纹聚类
  2. 追读基因 — 信息释放节奏与成瘾性标记
  3. 公式成熟曲线 — 长篇连载结构演化
  4. 微张力振荡 — 段落级紧张-释放交替
"""
import re, json, statistics, math, sys
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime

RAG = Path(r"D:\noveos\RAG")
OUT = Path(r"D:\noveos\rag_deep_analysis")
OUT.mkdir(exist_ok=True)

# ═══════════════ UTILS ═══════════════
def read_file(fp):
    try: return fp.read_text(encoding="utf-8", errors="ignore")
    except:
        try: return fp.read_text(encoding="gbk", errors="ignore")
        except: return ""

def split_chapters(text):
    chs = []
    pat = r'第[一二三四五六七八九十百千\d]+[章节][^\n]*'
    splits = re.split(f'({pat})', text)
    hdr = None
    for part in splits:
        if re.match(pat, part): hdr = part.strip()
        elif hdr and len(re.findall(r'[一-鿿]', part)) > 100:
            chs.append({"title": hdr, "text": part.strip()}); hdr = None
    if not chs and len(re.findall(r'[一-鿿]', text)) > 5000:
        paras = text.split('\n'); chunk, cn = "", 1
        for p in paras:
            chunk += p + '\n'
            if len(re.findall(r'[一-鿿]', chunk)) > 2000:
                chs.append({"title": f"Ch{cn}", "text": chunk.strip()}); chunk, cn = "", cn+1
        if chunk.strip(): chs.append({"title": f"Ch{cn}", "text": chunk.strip()})
    return chs

def cn_count(s): return len(re.findall(r'[一-鿿]', s))

# ═══════════════ DISCOVERY 1: GHOST AUTHOR DETECTION ═══════════════
def extract_structural_fingerprint(chapters):
    """Extract a 20-dimensional structural fingerprint from a novel."""
    if len(chapters) < 10: return None

    fp = {}
    sample = chapters[:min(50, len(chapters))]

    # Dimension 1-3: Chapter length statistics
    ch_lens = [cn_count(ch['text']) for ch in sample]
    fp['ch_len_mean'] = round(statistics.mean(ch_lens), 1)
    fp['ch_len_cv'] = round(statistics.stdev(ch_lens)/fp['ch_len_mean']*100, 1) if fp['ch_len_mean']>0 else 0
    fp['ch_len_skew'] = round((statistics.mean(ch_lens)-statistics.median(ch_lens))/max(statistics.stdev(ch_lens),1), 2)

    # Dimension 4-7: Sentence rhythm
    all_sents = []
    for ch in sample:
        sents = re.split(r'[。！？…!?]+', ch['text'])
        for s in sents:
            cn = cn_count(s)
            if 1 < cn < 100: all_sents.append(cn)
    if all_sents:
        fp['sent_mean'] = round(statistics.mean(all_sents), 1)
        fp['sent_std'] = round(statistics.stdev(all_sents), 1)
        fp['sent_short_pct'] = round(sum(1 for s in all_sents if s<=8)/len(all_sents)*100, 1)
        fp['sent_long_pct'] = round(sum(1 for s in all_sents if s>=35)/len(all_sents)*100, 1)

    # Dimension 8-10: Paragraph rhythm
    all_paras = []
    for ch in sample:
        paras = [p.strip() for p in ch['text'].split('\n') if cn_count(p) > 3]
        all_paras.extend([cn_count(p) for p in paras])
    if all_paras:
        fp['para_mean'] = round(statistics.mean(all_paras), 1)
        fp['para_std'] = round(statistics.stdev(all_paras), 1)
        fp['para_cv'] = round(fp['para_std']/fp['para_mean']*100, 1)

    # Dimension 11-13: Dialogue patterns
    dial_ratios = []
    dial_cluster_sizes = []
    for ch in sample:
        paras = [p.strip() for p in ch['text'].split('\n') if cn_count(p) > 3]
        markers = [1 if re.search(r'[""' "''「」『』]", p) or re.search(r'[说问道喊叫骂嚷答]', p[:30]) else 0 for p in paras]
        dial_ratios.append(sum(markers)/len(markers)*100 if markers else 0)
        # Cluster sizes
        cluster, cur = [], 0
        for m in markers:
            if m==1: cur+=1
            else:
                if cur>=2: cluster.append(cur)
                cur=0
        if cur>=2: cluster.append(cur)
        if cluster: dial_cluster_sizes.append(statistics.mean(cluster))

    fp['dial_ratio_mean'] = round(statistics.mean(dial_ratios), 1) if dial_ratios else 0
    fp['dial_ratio_std'] = round(statistics.stdev(dial_ratios), 1) if len(dial_ratios)>1 else 0
    fp['dial_cluster_mean'] = round(statistics.mean(dial_cluster_sizes), 1) if dial_cluster_sizes else 0

    # Dimension 14-15: Ta density
    ta_densities = []
    for ch in sample:
        cn = cn_count(ch['text'])
        ta = len(re.findall(r'[他她它]', ch['text']))
        ta_densities.append(ta/cn*100 if cn else 0)
    fp['ta_mean'] = round(statistics.mean(ta_densities), 2)
    fp['ta_std'] = round(statistics.stdev(ta_densities), 2) if len(ta_densities)>1 else 0

    # Dimension 16-17: Ending patterns
    suspense = 0
    for ch in sample:
        last200 = ch['text'].strip()[-200:] if len(ch['text'])>200 else ch['text']
        if re.search(r'[？?]', last200[-60:]): suspense += 1
    fp['suspense_ending_pct'] = round(suspense/len(sample)*100, 1)

    # Dimension 18-20: Opening patterns
    dial_open = 0; scene_open = 0; action_open = 0
    for ch in sample:
        first100 = ch['text'].strip()[:100]
        if re.search(r'[""' "''「]", first100): dial_open += 1
        elif re.search(r'(?:忽然|突然|正在|正要|就在|这时|那天)', first100): action_open += 1
        else: scene_open += 1
    fp['dialogue_open_pct'] = round(dial_open/len(sample)*100, 1)
    fp['scene_open_pct'] = round(scene_open/len(sample)*100, 1)

    return fp


def cluster_novels_by_fingerprint(fingerprints):
    """Simple hierarchical clustering based on fingerprint similarity."""
    names = list(fingerprints.keys())
    if len(names) < 2: return []

    # Compute distance matrix
    dist_matrix = {}
    for i, n1 in enumerate(names):
        for j, n2 in enumerate(names):
            if i >= j: continue
            fp1, fp2 = fingerprints[n1], fingerprints[n2]
            # Euclidean distance on normalized dimensions
            dims = [k for k in fp1.keys() if k in fp2]
            if len(dims) < 10: continue
            # Normalize each dimension to [0,1] across all novels
            dist = 0
            for d in dims:
                all_vals = [fingerprints[n].get(d, 0) for n in names if d in fingerprints.get(n, {})]
                if not all_vals or max(all_vals)==min(all_vals): continue
                v1 = (fp1[d]-min(all_vals))/(max(all_vals)-min(all_vals))
                v2 = (fp2[d]-min(all_vals))/(max(all_vals)-min(all_vals))
                dist += (v1-v2)**2
            dist = math.sqrt(dist/len(dims))
            dist_matrix[(n1,n2)] = round(dist, 4)

    # Find closest pairs (potential ghost authors)
    pairs = sorted(dist_matrix.items(), key=lambda x: x[1])
    return pairs[:30]  # Top 30 closest pairs


# ═══════════════ DISCOVERY 2: BINGE-READING GENE ═══════════════
def analyze_binge_gene(chapters):
    """Analyze information withholding patterns that drive binge-reading."""
    if len(chapters) < 10: return None

    sample = chapters[:min(30, len(chapters))]

    # Measure: Question density per chapter (unresolved questions)
    questions_per_ch = []
    reveals_per_ch = []
    info_gaps = []  # Distance between question raised and answered

    for ch in sample:
        text = ch['text']
        # Explicit questions (？结尾的句子)
        q_marks = len(re.findall(r'[？?]', text))
        # Implicit questions (悬念标记词)
        suspense_words = len(re.findall(r'(?:难道|莫非|究竟|到底|为何|怎么|什么|谁|哪里|何时|会不会|是否|莫非)', text))
        questions_per_ch.append(q_marks)

        # Reveals (information given)
        reveals = len(re.findall(r'(?:原来|终于|发现|明白|知道|看来|果然|竟然|居然|突然|忽然|一下子|顿时)', text))
        reveals_per_ch.append(reveals)

    # Calculate: Information Withholding Ratio (IWR)
    # High IWR = questions raised but not immediately answered = binge-driving
    total_q = sum(questions_per_ch)
    total_r = sum(reveals_per_ch)
    iwr = total_q / max(total_r, 1)

    # Calculate: Reveal Spacing (how many chapters between question peaks and reveal peaks)
    q_peaks = [i for i, q in enumerate(questions_per_ch) if q > statistics.mean(questions_per_ch)]
    r_peaks = [i for i, r in enumerate(reveals_per_ch) if r > statistics.mean(reveals_per_ch)]

    # Average distance from question peak to nearest reveal peak
    reveal_distances = []
    for qp in q_peaks:
        if r_peaks:
            nearest = min(abs(qp-rp) for rp in r_peaks)
            reveal_distances.append(nearest)
    avg_reveal_gap = round(statistics.mean(reveal_distances), 1) if reveal_distances else 0

    # Chapter-to-chapter hook strength
    # Measure: how many chapters end with explicit continuation hooks
    hook_count = 0
    for ch in sample:
        last100 = ch['text'].strip()[-150:] if len(ch['text'])>150 else ch['text']
        hook_signals = len(re.findall(r'(?:正要|就要|刚要|即将|马上|突然|忽然|不想|谁知|不料|哪知|只见|这时|此刻)', last100))
        if hook_signals >= 1: hook_count += 1

    hook_pct = round(hook_count/len(sample)*100, 1)

    return {
        "information_withholding_ratio": round(iwr, 2),
        "avg_questions_per_ch": round(statistics.mean(questions_per_ch), 1),
        "avg_reveals_per_ch": round(statistics.mean(reveals_per_ch), 1),
        "avg_reveal_gap_chapters": avg_reveal_gap,
        "hook_ending_pct": hook_pct,
        "binge_score": round(min(100, (iwr*15 + hook_pct*0.5 + (4-avg_reveal_gap)*8)), 1) if avg_reveal_gap < 10 else 50,
        "question_peaks": q_peaks[:10],
        "reveal_peaks": r_peaks[:10],
    }


# ═══════════════ DISCOVERY 3: FORMULA MATURATION CURVE ═══════════════
def analyze_formula_maturation(chapters):
    """For long series: how does structure evolve from early to late chapters?"""
    if len(chapters) < 60: return None  # Need at least 60 chapters

    # Split into three phases
    third = len(chapters) // 3
    early = chapters[:third]
    mid = chapters[third:2*third]
    late = chapters[2*third:]

    def phase_stats(chs):
        lens = [cn_count(ch['text']) for ch in chs]
        dials = []
        for ch in chs:
            paras = [p for p in ch['text'].split('\n') if cn_count(p)>3]
            markers = [1 if re.search(r'[""' "''「」『』]", p) or re.search(r'[说问道喊叫骂嚷答]', p[:30]) else 0 for p in paras]
            dials.append(sum(markers)/len(markers)*100 if markers else 0)

        sents = []
        for ch in chs:
            for s in re.split(r'[。！？…]+', ch['text']):
                cn = cn_count(s)
                if 1<cn<100: sents.append(cn)

        return {
            "avg_ch_len": round(statistics.mean(lens)),
            "ch_len_cv": round(statistics.stdev(lens)/statistics.mean(lens)*100,1) if lens else 0,
            "avg_dial_pct": round(statistics.mean(dials),1) if dials else 0,
            "avg_sent_len": round(statistics.mean(sents),1) if sents else 0,
        }

    e_stats = phase_stats(early)
    m_stats = phase_stats(mid)
    l_stats = phase_stats(late)

    # Calculate evolution vectors
    return {
        "total_chapters": len(chapters),
        "early": e_stats,
        "mid": m_stats,
        "late": l_stats,
        "evolution": {
            "ch_len_trend": round(l_stats['avg_ch_len'] - e_stats['avg_ch_len']),
            "dial_trend": round(l_stats['avg_dial_pct'] - e_stats['avg_dial_pct'], 1),
            "sent_trend": round(l_stats['avg_sent_len'] - e_stats['avg_sent_len'], 1),
            "consistency_trend": round(l_stats['ch_len_cv'] - e_stats['ch_len_cv'], 1),
        },
        "fatigue_signal": "膨胀" if l_stats['avg_ch_len'] > e_stats['avg_ch_len']*1.2 else (
            "收缩" if l_stats['avg_ch_len'] < e_stats['avg_ch_len']*0.8 else "稳定"),
        "dialogue_evolution": "对话增多" if l_stats['avg_dial_pct'] > e_stats['avg_dial_pct']+3 else (
            "对话减少" if l_stats['avg_dial_pct'] < e_stats['avg_dial_pct']-3 else "对话稳定"),
    }


# ═══════════════ DISCOVERY 4: MICRO-TENSION OSCILLATION ═══════════════
def analyze_micro_tension(chapters):
    """Paragraph-level tension oscillation analysis."""
    if len(chapters) < 5: return None

    # Analyze 3 sample chapters in detail
    sample = chapters[:min(3, len(chapters))]

    tension_sequences = []
    for ch in sample:
        paras = [p.strip() for p in ch['text'].split('\n') if cn_count(p) > 5]
        if len(paras) < 10: continue

        # Per-paragraph tension proxy: (exclamation*3 + action_verbs*2 + short_sent_pct*1) / para_len
        tensions = []
        for p in paras:
            cn = cn_count(p)
            excl = len(re.findall(r'[！!]', p))
            actions = len(re.findall(r'(?:走|跑|跳|打|杀|冲|追|逃|躲|飞|闪|摔|砸|劈|砍|刺|射|扑|跃|抓|握|扯|撕|咬|踢|踩|喊|叫|吼)', p))
            short_sents = len(re.findall(r'[。！？…][^。！？…]{1,10}[。！？…]', p))
            tension = (excl*3 + actions*2 + short_sents*1) / max(cn, 1) * 100
            tensions.append(round(tension, 2))

        if tensions:
            tension_sequences.append(tensions)

    if not tension_sequences: return None

    # Find oscillation patterns: how often does tension rise and fall?
    oscillation_counts = []
    for seq in tension_sequences:
        oscillations = 0
        direction = None
        for i in range(1, len(seq)):
            if seq[i] > seq[i-1]*1.05:
                if direction == 'down': oscillations += 1
                direction = 'up'
            elif seq[i] < seq[i-1]*0.95:
                if direction == 'up': oscillations += 1
                direction = 'down'
        oscillation_counts.append(oscillations)

    # Average tension per paragraph position (normalized)
    max_len = max(len(s) for s in tension_sequences)
    position_tensions = defaultdict(list)
    for seq in tension_sequences:
        for i, t in enumerate(seq):
            pos = round(i/len(seq)*100)  # Normalize to 0-100
            position_tensions[pos].append(t)

    # Build normalized tension curve
    tension_curve = {}
    for pos in sorted(position_tensions.keys()):
        if len(position_tensions[pos]) >= 1:
            tension_curve[pos] = round(statistics.mean(position_tensions[pos]), 2)

    return {
        "avg_oscillations_per_chapter": round(statistics.mean(oscillation_counts), 1) if oscillation_counts else 0,
        "normalized_tension_curve": tension_curve,
        "peak_tension_position": max(tension_curve, key=tension_curve.get) if tension_curve else None,
        "valley_tension_position": min(tension_curve, key=tension_curve.get) if tension_curve else None,
        "tension_range": round(max(tension_curve.values())-min(tension_curve.values()), 2) if tension_curve else 0,
    }


# ═══════════════ MAIN EXECUTION ═══════════════
print(f"DEEP DISCOVERY v3.0 START: {datetime.now().strftime('%H:%M:%S')}")
print(f"Source: {RAG}")
print()

# Collect all novels
all_novels = []
for genre_dir in sorted(RAG.iterdir()):
    if not genre_dir.is_dir(): continue
    for txt_file in sorted(genre_dir.glob("*.txt")):
        all_novels.append({"path": str(txt_file), "genre": genre_dir.name, "name": txt_file.stem})

print(f"Total novels: {len(all_novels)}")

# ── DISCOVERY 1: Ghost Author Detection ──
print(f"\n{'='*60}")
print("DISCOVERY 1: Ghost Author Detection (Structural Fingerprint Clustering)")
print(f"{'='*60}")

fingerprints = {}
for novel in all_novels:
    content = read_file(Path(novel['path']))
    chapters = split_chapters(content)
    if len(chapters) < 10: continue
    fp = extract_structural_fingerprint(chapters)
    if fp:
        key = f"{novel['genre']}/{novel['name']}"
        fingerprints[key] = fp

print(f"  Extracted fingerprints for {len(fingerprints)} novels")

# Find ghost author candidates (structurally extremely similar books)
pairs = cluster_novels_by_fingerprint(fingerprints)

print(f"\n  TOP 20 STRUCTURAL CLONES (potential ghost authors/same studio):")
ghost_findings = []
for (n1, n2), dist in pairs[:20]:
    # Only flag if from different "genres" or clearly different names
    g1, t1 = n1.split('/', 1)
    g2, t2 = n2.split('/', 1)
    confidence = "极高" if dist < 0.08 else ("高" if dist < 0.12 else ("中" if dist < 0.15 else "低"))
    if dist < 0.15:  # Only report high-confidence matches
        ghost_findings.append({
            "book1": n1, "book2": n2,
            "distance": round(dist, 4),
            "confidence": confidence,
            "same_genre": g1 == g2,
        })
        print(f"  [{confidence}] dist={dist:.4f} | {t1[:25]} <-> {t2[:25]} {'[同品类]' if g1==g2 else '[跨品类!]'}")

if not ghost_findings:
    print("  (No high-confidence ghost author pairs found)")

# ── DISCOVERY 2: Binge-Reading Gene ──
print(f"\n{'='*60}")
print("DISCOVERY 2: Binge-Reading Gene")
print(f"{'='*60}")

binge_scores = []
for novel in all_novels:
    content = read_file(Path(novel['path']))
    chapters = split_chapters(content)
    if len(chapters) < 10: continue
    bg = analyze_binge_gene(chapters)
    if bg:
        bg['name'] = novel['name']
        bg['genre'] = novel['genre']
        bg['chapters'] = len(chapters)
        binge_scores.append(bg)

binge_scores.sort(key=lambda x: -x['binge_score'])

print(f"\n  TOP 15 BINGE-DRIVING NOVELS (highest addiction potential):")
for i, bg in enumerate(binge_scores[:15]):
    print(f"  {i+1:>2}. [{bg['binge_score']:.0f}分] {bg['name'][:30]:<30} {bg['genre']:<10} "
          f"IWR={bg['information_withholding_ratio']:.1f} 钩子率={bg['hook_ending_pct']:.0f}% 揭示间隔={bg['avg_reveal_gap_chapters']}ch")

# Genre binge ranking
genre_binge = defaultdict(list)
for bg in binge_scores:
    genre_binge[bg['genre']].append(bg['binge_score'])
print(f"\n  Genre Binge-Ranking:")
for g, scores in sorted(genre_binge.items(), key=lambda x: -statistics.mean(x[1])):
    print(f"    {g:<12} avg={statistics.mean(scores):.0f}  max={max(scores):.0f}  count={len(scores)}")

# ── DISCOVERY 3: Formula Maturation ──
print(f"\n{'='*60}")
print("DISCOVERY 3: Formula Maturation Curve (100+ chapter series)")
print(f"{'='*60}")

maturation_data = []
for novel in all_novels:
    content = read_file(Path(novel['path']))
    chapters = split_chapters(content)
    if len(chapters) < 100: continue  # Only long series
    fm = analyze_formula_maturation(chapters)
    if fm:
        fm['name'] = novel['name']
        fm['genre'] = novel['genre']
        maturation_data.append(fm)

print(f"  Analyzed {len(maturation_data)} long series (100+ chapters)")

# Categorize evolution patterns
expanders = [m for m in maturation_data if m['fatigue_signal'] == '膨胀']
shrinkers = [m for m in maturation_data if m['fatigue_signal'] == '收缩']
stable = [m for m in maturation_data if m['fatigue_signal'] == '稳定']
dial_growers = [m for m in maturation_data if m['dialogue_evolution'] == '对话增多']
dial_shrinkers = [m for m in maturation_data if m['dialogue_evolution'] == '对话减少']

print(f"\n  Formula Evolution Patterns:")
print(f"    膨胀型 (后期章变长): {len(expanders)}本 — {(len(expanders)/len(maturation_data)*100):.0f}%")
print(f"    收缩型 (后期章变短): {len(shrinkers)}本 — {(len(shrinkers)/len(maturation_data)*100):.0f}%")
print(f"    稳定型: {len(stable)}本 — {(len(stable)/len(maturation_data)*100):.0f}%")
print(f"    对话增多型: {len(dial_growers)}本 — {(len(dial_growers)/len(maturation_data)*100):.0f}%")
print(f"    对话减少型: {len(dial_shrinkers)}本 — {(len(dial_shrinkers)/len(maturation_data)*100):.0f}%")

# Show most dramatic evolutions
print(f"\n  Most Dramatic Changes:")
maturation_data.sort(key=lambda x: abs(x['evolution']['ch_len_trend']), reverse=True)
for m in maturation_data[:10]:
    ev = m['evolution']
    print(f"    {m['name'][:30]:<30} {m['genre']:<10} {m['total_chapters']}ch "
          f"章长{ev['ch_len_trend']:+d}字 对话{ev['dial_trend']:+.1f}% 句长{ev['sent_trend']:+.1f}字 [{m['fatigue_signal']}]")

# ── DISCOVERY 4: Micro-Tension Oscillation ──
print(f"\n{'='*60}")
print("DISCOVERY 4: Micro-Tension Oscillation (Paragraph-Level)")
print(f"{'='*60}")

tension_data = []
for novel in all_novels:
    content = read_file(Path(novel['path']))
    chapters = split_chapters(content)
    if len(chapters) < 5: continue
    mt = analyze_micro_tension(chapters)
    if mt and mt['avg_oscillations_per_chapter'] > 0:
        mt['name'] = novel['name']
        mt['genre'] = novel['genre']
        tension_data.append(mt)

print(f"  Analyzed {len(tension_data)} novels for micro-tension")

# Find the "golden oscillation frequency"
osc_vals = [t['avg_oscillations_per_chapter'] for t in tension_data]
print(f"  Avg oscillations per chapter: {statistics.mean(osc_vals):.1f}")
print(f"  Oscillation range: {min(osc_vals):.1f} - {max(osc_vals):.1f}")

# Peak tension positions distribution
peak_positions = Counter()
for t in tension_data:
    if t['peak_tension_position'] is not None:
        # Bucket into 10% intervals
        bucket = round(t['peak_tension_position']/10)*10
        peak_positions[bucket] += 1

print(f"\n  Peak Tension Position Distribution (as % of chapter):")
for pos in sorted(peak_positions.keys()):
    bar = '#' * peak_positions[pos]
    print(f"    {pos:>3}% | {bar} ({peak_positions[pos]})")

# Genre micro-tension ranking
genre_tension = defaultdict(list)
for t in tension_data:
    genre_tension[t['genre']].append(t['avg_oscillations_per_chapter'])
print(f"\n  Genre Micro-Tension Ranking (avg oscillations/chapter):")
for g, scores in sorted(genre_tension.items(), key=lambda x: -statistics.mean(x[1])):
    print(f"    {g:<12} avg={statistics.mean(scores):.1f}  count={len(scores)}")

# ── SAVE ──
deep_discoveries = {
    "analysis_time": datetime.now().isoformat(),
    "total_novels_analyzed": len(all_novels),
    "discovery_1_ghost_authors": {
        "total_fingerprinted": len(fingerprints),
        "top_structural_clones": ghost_findings[:20],
        "closest_pair_distance": pairs[0][1] if pairs else None,
    },
    "discovery_2_binge_gene": {
        "top_binge_novels": [
            {"name": b['name'], "genre": b['genre'], "binge_score": b['binge_score'],
             "iwr": b['information_withholding_ratio'], "hook_pct": b['hook_ending_pct'],
             "reveal_gap": b['avg_reveal_gap_chapters']}
            for b in binge_scores[:20]
        ],
        "genre_binge_ranking": {g: round(statistics.mean(scores),1) for g,scores in sorted(genre_binge.items(), key=lambda x:-statistics.mean(x[1]))},
        "avg_iwr": round(statistics.mean([b['information_withholding_ratio'] for b in binge_scores]), 2),
        "avg_hook_pct": round(statistics.mean([b['hook_ending_pct'] for b in binge_scores]), 1),
    },
    "discovery_3_formula_maturation": {
        "total_long_series": len(maturation_data),
        "evolution_patterns": {
            "expanders_pct": round(len(expanders)/len(maturation_data)*100) if maturation_data else 0,
            "shrinkers_pct": round(len(shrinkers)/len(maturation_data)*100) if maturation_data else 0,
            "stable_pct": round(len(stable)/len(maturation_data)*100) if maturation_data else 0,
            "dialogue_growers_pct": round(len(dial_growers)/len(maturation_data)*100) if maturation_data else 0,
        },
        "top_dramatic_changes": [
            {"name": m['name'], "genre": m['genre'], "chapters": m['total_chapters'],
             "evolution": m['evolution'], "fatigue": m['fatigue_signal']}
            for m in maturation_data[:15]
        ],
    },
    "discovery_4_micro_tension": {
        "total_analyzed": len(tension_data),
        "avg_oscillations_per_chapter": round(statistics.mean(osc_vals), 1) if osc_vals else 0,
        "peak_tension_position_distribution": {str(k): v for k,v in sorted(peak_positions.items())},
        "genre_tension_ranking": {g: round(statistics.mean(scores),1) for g,scores in sorted(genre_tension.items(), key=lambda x:-statistics.mean(x[1]))},
    },
}

(OUT / "deep_discoveries_v3.json").write_text(
    json.dumps(deep_discoveries, ensure_ascii=False, indent=2), encoding='utf-8'
)

print(f"\n{'='*60}")
print(f"DEEP DISCOVERY v3.0 COMPLETE: {datetime.now().strftime('%H:%M:%S')}")
print(f"Output: {OUT / 'deep_discoveries_v3.json'}")
print(f"{'='*60}")
