"""Path C: outer loop + LLM deep analysis"""
import json, sys, os
from datetime import datetime
from pathlib import Path
sys.path.insert(0, '.')

from core.llm_client import LLMConfig, LLMClient
from core.outer_loop.rule_reader import RuleReader
from core.outer_loop.test_runner import TestRunner
from core.outer_loop.analyzer import Analyzer
from core.outer_loop.proposer import Proposer
from core.outer_loop.comparer import Comparer
from core.outer_loop.convergence import ConvergenceDetector
from core.outer_loop.rule_writer import RuleWriter
from core.outer_loop.models import IterationRound

CHAPTERS_DIR = 'e:/1/NoveOs-master/NoveOs-master/books/修仙模拟器：我的未来被诡异污染了_54a4cced/chapters'
OUTPUT = Path('reports/outer_loop')

# LLM
config = LLMConfig.from_env('deepseek-chat')
config.api_key = 'YOUR_DEEPSEEK_API_KEY_HERE'
config.api_base = 'https://api.deepseek.com/v1'
config.temperature = 0.1
config.max_tokens = 2000
llm = LLMClient(config)

print('=' * 70)
print('  Path C: Outer Loop + LLM Deep Analysis')
print('  LLM: {} @ {}'.format(config.model, config.api_base))
print('=' * 70)

# Step 1
print('\n[Step 1] Audit 1-10 chapters...')
runner = TestRunner(CHAPTERS_DIR)
batch = runner.run(chapter_range=(1, 10))
print('  avg_score={:.3f}, pass_rate={:.0%}'.format(batch.avg_rule_score, batch.pass_rate))

# Step 2: code + LLM
print('\n[Step 2] Analyze (code + LLM)...')
analyzer = Analyzer(llm=llm)
findings = analyzer.analyze(batch)
print('  {} findings:'.format(len(findings)))
for f in findings:
    sev = {'high':'[H]','medium':'[M]','low':'[L]'}.get(f.severity,'')
    cat = {'threshold_miscalibration':'threshold','blind_spot':'blind_spot','false_positive':'false_pos','correlation':'conflict'}.get(f.category, f.category)
    src = '[LLM]' if 'LLM' in f.evidence else '[code]'
    print('  {} {} {} {}'.format(sev, src, cat, f.description[:140]))
    if f.confidence > 0.7:
        print('       high conf({:.0%}): {}'.format(f.confidence, f.recommendation[:150]))

# Step 3
print('\n[Step 3] Propose (code + LLM)...')
proposer = Proposer(llm=llm)
proposals = proposer.propose(findings)
print('  {} proposals:'.format(len(proposals)))
for i, p in enumerate(proposals, 1):
    risk = {'low':'G','medium':'Y','high':'R'}.get(p.risk,'?')
    print('  {}. {} {}'.format(i, risk, p.summary()[:120]))

# Step 4
approved = [p for p in proposals if p.risk != 'high']
for p in approved:
    p.approved = True
    p.approved_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
print('\n[Step 4] Approval: {}/{} approved'.format(len(approved), len(proposals)))

if not approved:
    print('  No approved proposals, exit')
    sys.exit(0)

# Step 5
print('\n[Step 5] Apply changes...')
writer = RuleWriter()
sid = writer.apply_all(approved, snapshot_label='path_c_round2')
print('  snapshot: {}'.format(sid))

# Step 6
print('\n[Step 6] Verify...')
reader = RuleReader()
reader.invalidate_cache()
batch2 = runner.run(chapter_range=(1, 10))
print('  avg_score={:.3f}, pass_rate={:.0%}'.format(batch2.avg_rule_score, batch2.pass_rate))

# Step 7
print('\n[Step 7] Compare...')
comparer = Comparer()
comparison = comparer.compare(batch, batch2, approved)

# Print key metrics
key_metrics = ['rule_score_total','banned_total','not_x_but_y_count',
               'xiang_count','cn_number_density','validator_issues_count']
print('\n  {:25s} {:>8s} {:>8s} {:>8s}'.format('metric','before','after','delta'))
for mc in comparison.metrics:
    if mc.metric_name in key_metrics:
        e = {'improved':'OK','worsened':'!!','unchanged':'--'}[mc.direction]
        names = {
            'rule_score_total':'AI_score','banned_total':'banned_hits',
            'not_x_but_y_count':'not_X_but_Y','xiang_count':'xiang',
            'cn_number_density':'cn_density','validator_issues_count':'WARNs'
        }
        print('  {:25s} {:8.3f} {:8.3f} {:+7.1f}% {}'.format(
            names[mc.metric_name], mc.before_avg, mc.after_avg,
            mc.delta_pct*100, e))

print('\n  Summary: {}'.format(comparison.summary))
if comparison.goodhart_alerts:
    print('  WARNING Goodhart: {}'.format(comparison.goodhart_alerts))

# Convergence
conv = ConvergenceDetector(max_stable_rounds=3)
rnd = IterationRound(round_num=2)
rnd.proposals = proposals
rnd.approved_count = len(approved)
rnd.audit_before = batch.records
rnd.audit_after = batch2.records
c = conv.check(rnd, comparison)
print('\n  Convergence: {} - {}'.format(c['status'], c['reason']))

# Per-chapter WARN comparison
print('\n  Per-chapter WARN comparison:')
print('  {:5s} {:>8s} {:>8s} {:>8s}'.format('Ch','before','after','change'))
for i in range(10):
    b_rec = [r for r in batch.records if r.chapter_num == i+1]
    a_rec = [r for r in batch2.records if r.chapter_num == i+1]
    b_warns = len([iss for r in b_rec for iss in r.validator_issues if iss.get('level')=='WARN']) if b_rec else 0
    a_warns = len([iss for r in a_rec for iss in r.validator_issues if iss.get('level')=='WARN']) if a_rec else 0
    chg = a_warns - b_warns
    chg_str = '{:+d}'.format(chg) if chg != 0 else '0'
    b_verdict = b_rec[0].validator_verdict if b_rec else '?'
    a_verdict = a_rec[0].validator_verdict if a_rec else '?'
    print('  {:5d} {:>8s} {:>8s} {:>8s}'.format(i+1,
        '{}W'.format(b_warns) if b_warns else b_verdict,
        '{}W'.format(a_warns) if a_warns else a_verdict,
        chg_str))

# Save
report = {
    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    'llm': config.model,
    'findings': [{'id':f.finding_id,'cat':f.category,'desc':f.description,'conf':f.confidence,'sev':f.severity} for f in findings],
    'proposals': [{'path':p.asset_path,'from':str(p.current_value),'to':str(p.proposed_value),'risk':p.risk} for p in proposals],
    'approved': len(approved),
    'comparison': comparison.summary,
    'convergence': c,
}
fp = OUTPUT / 'path_c_round2_{}.json'.format(datetime.now().strftime('%Y%m%d_%H%M%S'))
fp.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print('\n  Report: {}'.format(fp))
print('\n  Token cost: ~5K (analyzer LLM + proposer LLM) = approx $0.01')
print('\n' + '=' * 70)
print('  Path C Complete! Code + LLM dual-stage analysis')
print('=' * 70)
