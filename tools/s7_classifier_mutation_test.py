"""Mutation test of S7's classifier -- tools/s7_classifier_mutation_test.py

Created 2026-11-06, the same session as S7, because the standing item
"MUTATION-TEST THE RUNNERS' SCORING LOGIC, NOT ONLY THEIR ARMS" has been
carried since 10-26 and S7's classifier IS scoring logic: it assigns one of
four verdicts and nothing else checks that the assignment is load-bearing.

IT EARNED ITS KEEP ON THE FIRST RUN.  M5 -- loosening the rewording threshold
from 0.75 to 0.0, which makes any arrival absorb any departure -- SURVIVED all
six original controls, because C1's plant has no arrivals at all and so never
executes the rewording loop.  The threshold was an unguarded constant in a
classifier.  C7 was added to read it, and M5 is now detected.

Run:  python3 tools/s7_classifier_mutation_test.py  Each injected defect must be caught by a
named control.  The mutant tree is SYMLINKS to the real repo with one real
file -- the mutated module -- so nothing is copied and the mutant sees exactly
the repo the baseline saw."""
import os, re, shutil, subprocess, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOD = 'open_item_staleness_audit.py'
SRC = os.path.join(REPO, 'tools', MOD)
ROOT = '/tmp/s7mut%d' % os.getuid()

# (id, description, old, new, controls that MUST go red)
MUTANTS = [
    ('M1', 'LOST made unreachable: an unaccounted departure reads REWORDED',
     "    return 'LOST', 'no adjudication, no removal note, no reworded arrival'",
     "    return 'REWORDED', 'no adjudication, no removal note, no reworded arrival'",
     ['C1']),
    ('M2', 'the STALE-adjudication route deleted',
     "    if head in stale_heads:\n        return 'ADJUDICATED', 'a STALE adjudication entry quotes this head'",
     "    if False:\n        return 'ADJUDICATED', 'a STALE adjudication entry quotes this head'",
     ['C2', 'C6']),
    ('M3', 'the removal-note route deleted',
     "    if head in notes:\n        return 'NOTED', 'the entry that dropped it carries a removal note'",
     "    if False:\n        return 'NOTED', 'the entry that dropped it carries a removal note'",
     ['C3']),
    ('M4', 'precedence inverted: the REWORDED scan runs before ADJUDICATED, every route still present',
     "    if head in stale_heads:\n        return 'ADJUDICATED', 'a STALE adjudication entry quotes this head'",
     "    th0 = tokens(head)\n    for a0 in arrivals:\n        if th0 and len(th0 & tokens(a0)) / float(len(th0)) >= 0.75:\n            return 'REWORDED', 'arrived reworded as \"%s\"' % a0[:58]\n    if head in stale_heads:\n        return 'ADJUDICATED', 'a STALE adjudication entry quotes this head'",
     ['C6']),
    ('M5', 'the token threshold loosened to 0.0, so any arrival looks like a rewording',
     "        if th and len(th & tokens(a)) / float(len(th)) >= 0.75:",
     "        if th and len(th & tokens(a)) / float(len(th)) >= 0.0:",
     ['C7']),
    ('M6', 'the departure membership test inverted, so departures are never found',
     "        if h in cs:\n            continue",
     "        if h not in cs:\n            continue",
     ['C2', 'C3', 'C4', 'C5', 'C6']),
]

def link_tree(dest):
    os.makedirs(os.path.join(dest, 'tools'), exist_ok=True)
    for name in os.listdir(REPO):
        if name in ('.git', 'tools'):
            continue
        os.symlink(os.path.join(REPO, name), os.path.join(dest, name))
    for name in os.listdir(os.path.join(REPO, 'tools')):
        if name == MOD or name == '__pycache__':
            continue
        os.symlink(os.path.join(REPO, 'tools', name),
                   os.path.join(dest, 'tools', name))

def run(path, cwd):
    p = subprocess.run([sys.executable, path], cwd=cwd,
                       capture_output=True, text=True, timeout=120)
    return p.stdout

def red(out):
    return sorted(set(re.findall(r'\[FAIL\] (C\d)', out)))

print('=' * 74)
print('S7 CLASSIFIER MUTATION TEST -- 2026-11-06')
print('Does any control actually fail when the classifier is broken?')
print('=' * 74)
base = run(SRC, REPO)
m = re.search(r'RESULT: .*', base)
print('\nBASELINE (unmutated, real repo): %s' % (m.group(0) if m else '??'))
assert not red(base), 'baseline already red: %r' % red(base)
print('baseline: C1-C6 all green, so a red control below is caused by the mutant\n')

shutil.rmtree(ROOT, ignore_errors=True)
detected = survived = notapplied = 0
for mid, desc, old, new, expect in MUTANTS:
    d = os.path.join(ROOT, mid)
    link_tree(d)
    src = open(SRC, encoding='utf-8').read()
    n = src.count(old)
    tgt = os.path.join(d, 'tools', MOD)
    if n != 1:
        print('%s  NOT APPLIED  anchor matched %d times -- %s' % (mid, n, desc))
        notapplied += 1
        continue
    open(tgt, 'w', encoding='utf-8').write(src.replace(old, new, 1))
    out = run(tgt, d)
    r = red(out)
    caught = [c for c in expect if c in r]
    res = re.search(r'RESULT: .*', out)
    print('%s  %-8s  %s' % (mid, 'DETECTED' if caught else 'SURVIVED', desc))
    print('        expected red : %s' % ','.join(expect))
    print('        actually red  : %s' % (','.join(r) or 'NONE'))
    print('        %s' % (res.group(0) if res else 'no RESULT line -- the mutant crashed'))
    if caught:
        detected += 1
    else:
        survived += 1
shutil.rmtree(ROOT, ignore_errors=True)
print('\n' + '=' * 74)
print('TOTAL: %d detected, %d survived, %d not applied (of %d)'
      % (detected, survived, notapplied, len(MUTANTS)))
print('=' * 74)
sys.exit(0 if detected == len(MUTANTS) else 1)
