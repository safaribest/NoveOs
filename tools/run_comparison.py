import sys
from pathlib import Path
sys.path.insert(0, str(Path('D:/noveos/novel-os')))
from core.anti_detect_reviser import AntiDetectReviser
import glob

reviser = AntiDetectReviser()

pre_files = sorted(glob.glob('D:/noveos/pre_reform_chapters/pre_ch*.txt'))
post_files = sorted(glob.glob('D:/noveos/post_reform_chapters/post_ch*.txt'))

print('='*70)
print('辞林式改造前后 AI味 对比检测报告')
print('='*70)
print()

results = []
for i, (pre, post) in enumerate(zip(pre_files, post_files), 1):
    with open(pre, 'r', encoding='utf-8') as f:
        pre_text = f.read()
    with open(post, 'r', encoding='utf-8') as f:
        post_text = f.read()
    
    pre_score = reviser.compute_ai_marker_score(pre_text)
    post_score = reviser.compute_ai_marker_score(post_text)
    
    pre_wc = sum(1 for c in pre_text if '\u4e00' <= c <= '\u9fff')
    post_wc = sum(1 for c in post_text if '\u4e00' <= c <= '\u9fff')
    
    change = pre_score['total'] - post_score['total']
    pct = (change / pre_score['total'] * 100) if pre_score['total'] > 0 else 0
    
    results.append({
        'chapter': i,
        'pre_wc': pre_wc,
        'post_wc': post_wc,
        'pre_total': pre_score['total'],
        'post_total': post_score['total'],
        'change': change,
        'pct': pct,
        'pre_para': pre_score['paragraph_uniformity'],
        'post_para': post_score['paragraph_uniformity'],
        'pre_trans': pre_score['transition_density'],
        'post_trans': post_score['transition_density'],
        'pre_le': pre_score['le_density'],
        'post_le': post_score['le_density'],
        'pre_forbid': pre_score['forbidden_density'],
        'post_forbid': post_score['forbidden_density'],
        'pre_form': pre_score['formulaic'],
        'post_form': post_score['formulaic'],
    })
    
    print(f'第{i}章')
    print(f'  字数: {pre_wc} -> {post_wc} ({post_wc-pre_wc:+d})')
    print(f'  综合AI味: {pre_score["total"]:.3f} -> {post_score["total"]:.3f} ({change:+.3f}, -{pct:.1f}%)')
    print(f'  |-- 段落均匀度: {pre_score["paragraph_uniformity"]:.3f} -> {post_score["paragraph_uniformity"]:.3f}')
    print(f'  |-- 过渡词密度: {pre_score["transition_density"]:.3f} -> {post_score["transition_density"]:.3f}')
    print(f'  |-- 了字密度: {pre_score["le_density"]:.3f} -> {post_score["le_density"]:.3f}')
    print(f'  |-- 禁用词密度: {pre_score["forbidden_density"]:.3f} -> {post_score["forbidden_density"]:.3f}')
    print(f'  `-- 公式化转折: {pre_score["formulaic"]:.3f} -> {post_score["formulaic"]:.3f}')
    print()

print('='*70)
print('汇总')
print('='*70)

avg_pre = sum(r['pre_total'] for r in results) / len(results)
avg_post = sum(r['post_total'] for r in results) / len(results)
avg_change = avg_pre - avg_post
avg_pct = (avg_change / avg_pre * 100) if avg_pre > 0 else 0

print(f'综合AI味平均: {avg_pre:.3f} -> {avg_post:.3f} ({avg_change:+.3f}, -{avg_pct:.1f}%)')
print(f'AI味降幅: {avg_pct:.1f}%')
if avg_pct >= 40:
    print('结论: 改造效果显著 (>=40%降幅)')
elif avg_pct >= 20:
    print('结论: 改造效果中等 (20-40%降幅)')
else:
    print('结论: 改造效果有限 (<20%降幅)')

# Save report
report_path = Path('D:/noveos/reports/cilin_ai_score_comparison.txt')
report_path.parent.mkdir(parents=True, exist_ok=True)
with open(report_path, 'w', encoding='utf-8') as f:
    f.write('辞林式改造前后 AI味 对比检测报告\n')
    f.write('='*70 + '\n\n')
    for r in results:
        f.write(f"第{r['chapter']}章\n")
        f.write(f"  字数: {r['pre_wc']} -> {r['post_wc']}\n")
        f.write(f"  综合AI味: {r['pre_total']:.3f} -> {r['post_total']:.3f} (-{r['pct']:.1f}%)\n")
        f.write(f"  段落均匀度: {r['pre_para']:.3f} -> {r['post_para']:.3f}\n")
        f.write(f"  过渡词密度: {r['pre_trans']:.3f} -> {r['post_trans']:.3f}\n")
        f.write(f"  了字密度: {r['pre_le']:.3f} -> {r['post_le']:.3f}\n")
        f.write(f"  禁用词密度: {r['pre_forbid']:.3f} -> {r['post_forbid']:.3f}\n")
        f.write(f"  公式化转折: {r['pre_form']:.3f} -> {r['post_form']:.3f}\n\n")
    f.write(f"\n平均综合AI味: {avg_pre:.3f} -> {avg_post:.3f} (-{avg_pct:.1f}%)\n")
    f.write(f"结论: {'显著' if avg_pct >= 40 else '中等' if avg_pct >= 20 else '有限'}改造效果\n")

print(f'\n报告已保存: {report_path}')
