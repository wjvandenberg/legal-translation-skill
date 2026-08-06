#!/usr/bin/env python3
"""Structural + consistency validator for FINDINGS-REGISTER.md.

Checks things eyeballing misses:
  1  every finding row parses into 5 columns with a valid severity
  2  the Clusters table's claimed id ranges match the rows that actually exist
  3  no duplicate ids, no dangling cross-references
  4  narrative claims about the D03/D03B comparison match the two grade reports
  5  leakage gate over the committable files
  6  header counts reconcile to a row-by-row count
Exit 0 only if everything passes.
"""
import re, sys, os

REG = 'FINDINGS-REGISTER.md'
SEV = {'CRITICAL', 'HIGH', 'MED', 'LOW', 'POS', '—', '-'}
fails, warns = [], []


def fail(m): fails.append(m)
def warn(m): warns.append(m)


reg = open(REG, encoding='utf-8').read()
lines = reg.split('\n')

# ---------- 1. row structure ----------
sec = None
rows = {}          # section -> [(id, cols)]
for ln, l in enumerate(lines, 1):
    m = re.match(r'^### (.+)', l)
    if m:
        sec = m.group(1).strip()
    m = re.match(r'^\| ([A-Z]{1,2}-?\d{1,2}[a-z]?) \|', l)
    if not m:
        continue
    fid = m.group(1)
    # In GFM a backslash-escaped pipe is a literal character and does NOT end a cell.
    # Split on unescaped pipes only, then unescape.
    body = l.strip().strip('|')
    cols = [c.replace('\\|', '|').strip() for c in re.split(r'(?<!\\)\|', body)]
    rows.setdefault(sec, []).append((fid, cols, ln))
    is_inst = fid.startswith('I-')          # instrument table has its own H2, so check id first
    is_pos = (not is_inst) and sec and sec.startswith('Positives')
    expect = 4 if is_inst else (3 if is_pos else 5)
    if len(cols) != expect:
        fail('%s line %d: expected %d columns, got %d -> last=%r'
             % (fid, ln, expect, len(cols), cols[-1][:40]))
    elif not is_pos and not is_inst:
        # severity may carry a trailing italic annotation, e.g. "MED *(was CRITICAL)*"
        base = re.sub(r'\s*\*\(.*?\)\*\s*$', '', cols[4]).strip()
        if base not in SEV:
            fail('%s line %d: severity %r not in %s' % (fid, ln, cols[4], sorted(SEV)))
        if not cols[2]:
            fail('%s line %d: empty docs column' % (fid, ln))
    # NOTE: an unescaped pipe in prose shows up as a column-count mismatch above,
    # so no separate check is needed - and checking the UNescaped column text for
    # pipes gives false positives on correctly-escaped regexes and quoted tables.

allids = [f for v in rows.values() for f, _, _ in v]
ids = set(allids)
dupes = sorted({i for i in allids if allids.count(i) > 1})
if dupes:
    fail('duplicate ids: %s' % dupes)

# ---------- 2. Clusters table vs reality ----------
def expand(spec):
    out = []
    for tok in re.split(r'[,·]', spec):
        tok = tok.strip()
        m = re.match(r'^([A-Z]+)(\d+)[–-]([A-Z]*)(\d+)$', tok)
        if m:
            pre, a, _, b = m.groups()
            out += ['%s%d' % (pre, i) for i in range(int(a), int(b) + 1)]
        elif re.match(r'^[A-Z]+\d+$', tok):
            out.append(tok)
    return out

cluster_rows = {}
for s, v in rows.items():
    if s and s.startswith('Cluster'):
        letter = re.match(r'Cluster ([A-Z])', s).group(1)
        cluster_rows.setdefault(letter, []).extend(f for f, _, _ in v)

for m in re.finditer(r'^\| \*\*([A-Z])\*\* \| (.+?) \| ([A-Z0-9–,\- ]+) \|', reg, re.M):
    letter, _desc, spec = m.groups()
    claimed = set(expand(spec))
    # a cluster's findings are those whose id starts with its letter, wherever the row sits
    actual = {i for i in ids if re.match(r'^%s\d+$' % letter, i)}
    if claimed != actual:
        fail('Clusters table row %s claims %s but ids present are %s  (missing from table: %s)'
             % (letter, spec.strip(), ''.join(sorted(actual, key=lambda x: int(x[1:]))),
                sorted(actual - claimed, key=lambda x: int(x[1:])) or 'none'))

# rows filed under the wrong cluster heading
for letter, fs in cluster_rows.items():
    stray = [f for f in fs if not f.startswith(letter)]
    if stray:
        warn('rows under "Cluster %s" heading belonging to another cluster: %s' % (letter, stray))

# ---------- 3. dangling cross-references ----------
# ids the register explicitly declares reserved/unallocated are not dangling
reserved = set()
for m in re.finditer(r'([A-Z]+)(\d+)[–-]([A-Z]*)(\d+)\*{0,2} are deliberately unallocated', reg):
    pre, lo, hi = m.group(1), int(m.group(2)), int(m.group(4))
    reserved |= {'%s%d' % (pre, i) for i in range(lo, hi + 1)}
if reserved:
    print('  reserved (declared unallocated): %s' % ' '.join(sorted(reserved)))
refs = {r for r in re.findall(r'\b((?:[A-Z]|I-)\d{1,2})\b', reg)
        if re.match(r'^([ABCEFGHJKLNOPQRST]|I-)\d', r)}
dangling = sorted(r for r in refs if r not in ids and r not in reserved)
if dangling:
    fail('dangling cross-references: %s' % dangling)

# ---------- 3b. edit-damage sweeps ----------
# (a) a truncating edit would leave an implausibly short finding cell.
#     Applies to the 5-column skill-finding tables only - the instrument table
#     is legitimately terse (e.g. I-3 "Script-less steps could not be closed").
for s, v in rows.items():
    for fid, cols, ln in v:
        if fid.startswith('I-') or (s and s.startswith('Positives')) or len(cols) != 5:
            continue
        if len(cols[1]) < 60:
            fail('%s line %d: finding text only %d chars - truncated? %r'
                 % (fid, ln, len(cols[1]), cols[1][:50]))
# (b) the docs column must contain only recognised document ids / origins
DOCTOK = re.compile(r'^(D\d{2}B?|WvdB|June|PM|all|—|-|and|\+|vs|probe|code|repro|log|grade)$')
for s, v in rows.items():
    for fid, cols, ln in v:
        if fid.startswith('I-') or (s and s.startswith('Positives')):
            docs = cols[2] if len(cols) > 2 else ''
        elif len(cols) == 5:
            docs = cols[2]
        else:
            continue
        for tok in re.sub(r'\*\*|\*', '', docs).replace(',', ' ').split():
            if not DOCTOK.match(tok):
                warn('%s line %d: unrecognised token %r in docs column %r'
                     % (fid, ln, tok, docs[:50]))

# ---------- 4. header counts ----------
clustered = sum(len(v) for s, v in rows.items() if s and s.startswith('Cluster'))
uncl = len(rows.get('Unclustered / single-instance', []))
pos = [i for i in allids if i.startswith('P')]
inst = [i for i in allids if i.startswith('I-')]
nfixed = len(re.findall(r'^\| I-\d+ \|.*?\| fixed[^|]*\|', reg, re.M))
nopen = len(re.findall(r'^\| I-\d+ \|.*?\| open\s*\|', reg, re.M))
h = re.search(r'\*\*Coverage at [^:]+:\*\* (\d+) clusters · \*\*(\d+) skill findings\*\* '
              r'\((\d+) clustered \+ (\d+) single-instance\) ·\s*\*\*(\d+) positives-to-preserve\*\* · '
              r'\*\*(\d+) instrument defects \((\d+) fixed, (\d+) open\)', reg, re.S)
if not h:
    fail('could not parse the Coverage header line')
else:
    got = [int(x) for x in h.groups()]
    want = [len(cluster_rows), clustered + uncl, clustered, uncl, len(pos), len(inst), nfixed, nopen]
    for lab, a, b in zip(['clusters', 'skill', 'clustered', 'single', 'positives',
                          'instrument', 'fixed', 'open'], got, want):
        if a != b:
            fail('header %s: says %d, actual %d' % (lab, a, b))

# ---------- 5. D03 vs D03B consistency ----------
LOG = '../legal-translation-logs/A1'
def scores(path):
    t = open(path, encoding='utf-8').read()
    out = {}
    for m in re.finditer(r'^\| (\d{1,2}|\*\*17\*\*) \| ([^|]+?) \| \*{0,2}([\d.]+)', t, re.M):
        k = m.group(1).replace('*', '')
        out[int(k)] = float(m.group(3))
    return out

p03 = os.path.join(LOG, 'D03', 'GRADE-D03.md')
p03b = os.path.join(LOG, 'BATCH-D01-D10-D03B', 'GRADE-D03B.md')
if os.path.exists(p03) and os.path.exists(p03b):
    a, b = scores(p03), scores(p03b)
    common = sorted(set(a) & set(b) - {17})
    same = [c for c in common if a[c] == b[c]]
    diff = [c for c in common if a[c] != b[c]]
    print('  D03 vs D03B: %d criteria compared, %d identical, %d differ %s'
          % (len(common), len(same), len(diff), diff))
    print('  overall: D03 %.1f  D03B %.1f' % (a.get(17, -1), b.get(17, -1)))
    # what does the register claim?
    for m in re.finditer(r'\*\*(\w+) of sixteen criteria are identical', reg):
        word = m.group(1).lower()
        nmap = {'ten': 10, 'eleven': 11, 'twelve': 12, 'thirteen': 13}
        if nmap.get(word) != len(same):
            fail('register says "%s of sixteen criteria are identical"; actual is %d of %d'
                 % (word, len(same), len(common)))
    # T1's per-criterion deltas
    t1 = re.search(r'^\| T1 \|(.*?)\n', reg, re.M | re.S)
    if t1:
        for lab, crit in (('readability', 4), ('completeness', 5), ('page layout', 12),
                          ('run properties', 14)):
            mm = re.search(re.escape(lab) + r' (\d+) → (\d+)', t1.group(1))
            if not mm:
                warn('T1 does not state a %s delta' % lab)
            elif (float(mm.group(1)), float(mm.group(2))) != (a[crit], b[crit]):
                fail('T1 %s says %s→%s; grades say %g→%g'
                     % (lab, mm.group(1), mm.group(2), a[crit], b[crit]))
        mm = re.search(r'overall \*\*(\d+\.\d+) → (\d+\.\d+)\*\*', t1.group(1))
        if mm and (float(mm.group(1)), float(mm.group(2))) != (a[17], b[17]):
            fail('T1 overall says %s→%s; grades say %g→%g'
                 % (mm.group(1), mm.group(2), a[17], b[17]))
else:
    warn('grade reports not found; skipped the D03/D03B cross-check')

# ---------- 6. leakage ----------
pats = [l.strip() for l in open('../legal-translation-private/leakage-names.txt', encoding='utf-8')
        if l.strip() and not l.startswith('#')]
for t in (REG, 'CLAUDE.md'):
    txt = open(t, encoding='utf-8').read()
    for p in pats:
        if re.search(p, txt, re.I):
            fail('LEAKAGE %r in %s' % (p, t))

# ---------- report ----------
print('\n  rows=%d  clusters=%d  clustered=%d  single=%d  positives=%d  instrument=%d(%df/%do)'
      % (len(allids), len(cluster_rows), clustered, uncl, len(pos), len(inst), nfixed, nopen))
print('  leakage patterns checked: %d' % len(pats))
print()
for w in warns:
    print('  WARN  ' + w)
for f in fails:
    print('  FAIL  ' + f)
print('\n%s  (%d failures, %d warnings)' % ('PASS' if not fails else 'FAILED', len(fails), len(warns)))
sys.exit(1 if fails else 0)
