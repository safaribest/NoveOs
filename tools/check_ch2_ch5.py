import sys
from pathlib import Path
sys.path.insert(0, str(Path('D:/noveos/novel-os')))
from core.anti_detect_reviser import AntiDetectReviser

reviser = AntiDetectReviser()

for ch in [2, 5]:
    with open(f'D:/noveos/post_reform_chapters/post_ch{ch:03d}.txt', 'r', encoding='utf-8') as f:
        text = f.read()
    score = reviser.compute_ai_marker_score(text)
    wc = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    print(f'Chapter {ch} (fixed)')
    print(f'  Words: {wc}')
    print(f'  Total AI: {score["total"]:.3f}')
    print(f'  Para uniformity: {score["paragraph_uniformity"]:.3f}')
    print(f'  Transition density: {score["transition_density"]:.3f}')
    print(f'  Le density: {score["le_density"]:.3f}')
    print(f'  Forbidden density: {score["forbidden_density"]:.3f}')
    print(f'  Formulaic: {score["formulaic"]:.3f}')
    print()
