# -*- coding: utf-8 -*-
"""THE PARITY CHECK — the two trees differ only in the permitted variant layer.

Nothing anywhere claims to keep the two packages in step, and that absence is what permits
the drift: the default tree runs 37 spelling rules where the other runs 60 and 34 where the
other runs 91; a tidy-up function takes a variant argument in one tree and hardcodes the UK
answer in the other; a blocking rule cannot see the other variant's spelling of the phrase it
blocks; a sentence in the always-loaded file has its two verbs swapped, corrected in one tree
and never in the other.

TWO ARMS, and the second is the one that matters most.

  CROSS-TREE   the two trees differ only in the permitted variant layer, reached at all four
               places the drift has actually been measured: dictionary rows, script string
               literals, function signatures, rule-table lengths.
  WITHIN-TREE  run inside EACH tree separately. Two assertions: that a row rendering a
               variant-controlled term carries BOTH forms with markers, and that the two
               dictionary layers do not give different answers for the same term.

WHY THE WITHIN-TREE ARM EXISTS. The one instance that reached a client was not one tree being
behind. A sub-dictionary row hardcoded the UK form with no marker while the cross-language
reference in that same package gave both forms correctly -- IDENTICALLY WRONG IN BOTH TREES,
so a cross-tree comparison passes it as clean. A cross-tree check alone would not have caught
the defect that actually shipped.

TWO SPECIFICATION FACTS, both measured, either of which would make a naive check useless:

  * IT MUST COMPARE PROGRAMS, NOT TEXT. The variant conversion reached local variable names,
    so no textual comparison of the two trees can ever come back clean. Comparing them as
    PARSED PROGRAMS is the only reason it can be said that 7 of the 15 differing scripts
    differ in nothing but comments.
  * THE TERM LIST IS HARVESTED FROM THE PACKAGE'S OWN TABLES, never supplied by us, or the
    check measures our expectations instead of the artefact.

A THIRD ARM IS NAMED IN THE ANALYSIS AND DELIBERATELY NOT BUILT HERE: that a US delivery
contains no "Clause" and a UK delivery no "Section". It inspects a DELIVERED DOCUMENT, so it
is not a parity check at all and belongs with the delivered-document checks being built at
branch 11.

WHAT THIS DOES NOT DO: it repairs nothing. The reconciliation is deferred item D1. This
measures, and from here on it makes every NEW divergence visible as it is introduced.

Exit codes:  0 = no divergence outside the recorded baseline · 1 = new divergence · 2 = the
check could not run.

    uv run python tools/parity_check.py
    uv run python tools/parity_check.py --write-baseline
    uv run python tools/parity_check.py --full        # list baselined items too
"""
import ast
import io
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent
UK, US = ROOT / "uk", ROOT / "us"
BASELINE = ROOT / "tests" / "baselines" / "known-divergences.json"
WRITE = "--write-baseline" in sys.argv
FULL = "--full" in sys.argv

# The permitted variant layer for the scripts, measured: one default flag value in three
# files, nothing more. Anything else in a script is drift until proved otherwise.
VARIANT_TOKENS = re.compile(r"(?i)\b(?:uk|us|british|american|en-?gb|en-?us)\b")

divergences = []          # (arm, kind, key, detail)


def note(arm, kind, key, detail):
    divergences.append({"arm": arm, "kind": kind, "key": key, "detail": detail})


# ---------------------------------------------------------------------------
# ARM 1 — CROSS-TREE
# ---------------------------------------------------------------------------
def norm(node):
    """An AST dump with positions dropped, so formatting and comments cannot register as a
    difference. Docstrings are dropped too: they are prose, and prose differences belong to
    the dictionary-row comparison rather than the program comparison."""
    class Strip(ast.NodeTransformer):
        def visit_Expr(self, n):
            if isinstance(n.value, ast.Constant) and isinstance(n.value.value, str):
                return None
            return self.generic_visit(n)
    node = Strip().visit(node)
    return ast.dump(node, annotate_fields=True, include_attributes=False)


def functions(tree):
    return {f.name: f for f in ast.walk(tree) if isinstance(f, (ast.FunctionDef,
                                                                ast.AsyncFunctionDef))}


def signature(f):
    a = f.args
    parts = [x.arg for x in a.posonlyargs + a.args]
    if a.vararg:
        parts.append("*" + a.vararg.arg)
    parts += [x.arg for x in a.kwonlyargs]
    if a.kwarg:
        parts.append("**" + a.kwarg.arg)
    # Default VALUES are the variant layer's own mechanism, so the count is compared, not
    # the values -- a differing default flag is the permitted difference, a differing NUMBER
    # of parameters is not.
    return f"{f.name}({', '.join(parts)})[defaults={len(a.defaults)}+{len(a.kw_defaults)}]"


def rule_tables(tree):
    """Module-level collection literals, by name and LENGTH. This is what catches the
    37-versus-60 and 34-versus-91 spelling-rule drift: the tables have the same name in both
    trees and a different number of entries."""
    out = {}
    for n in tree.body:
        if not isinstance(n, (ast.Assign, ast.AnnAssign)):
            continue
        targets = n.targets if isinstance(n, ast.Assign) else [n.target]
        for t in targets:
            if not isinstance(t, ast.Name):
                continue
            v = n.value
            if isinstance(v, (ast.List, ast.Tuple, ast.Set)):
                out[t.id] = len(v.elts)
            elif isinstance(v, ast.Dict):
                out[t.id] = len(v.keys)
    return out


def string_literals(tree):
    return sorted({n.value for n in ast.walk(tree)
                   if isinstance(n, ast.Constant) and isinstance(n.value, str)
                   and len(n.value) > 3})


def cross_tree_scripts():
    uk_s = {p.name for p in (UK / "scripts").glob("*.py")}
    us_s = {p.name for p in (US / "scripts").glob("*.py")}
    for only, side in ((uk_s - us_s, "uk"), (us_s - uk_s, "us")):
        for n in sorted(only):
            note("cross-tree", "script-only-in-one-tree", f"scripts/{n}", f"present only in {side}")

    for name in sorted(uk_s & us_s):
        try:
            a = ast.parse((UK / "scripts" / name).read_text(encoding="utf-8"))
            b = ast.parse((US / "scripts" / name).read_text(encoding="utf-8"))
        except SyntaxError as e:
            note("cross-tree", "unparseable", f"scripts/{name}", str(e))
            continue

        fa, fb = functions(a), functions(b)
        for n in sorted(set(fa) - set(fb)):
            note("cross-tree", "function-missing", f"scripts/{name}::{n}", "absent from us")
        for n in sorted(set(fb) - set(fa)):
            note("cross-tree", "function-missing", f"scripts/{name}::{n}", "absent from uk")

        for n in sorted(set(fa) & set(fb)):
            if signature(fa[n]) != signature(fb[n]):
                note("cross-tree", "signature", f"scripts/{name}::{n}",
                     f"uk {signature(fa[n])} vs us {signature(fb[n])}")

        ta, tb = rule_tables(a), rule_tables(b)
        for n in sorted(set(ta) & set(tb)):
            if ta[n] != tb[n]:
                note("cross-tree", "rule-table-length", f"scripts/{name}::{n}",
                     f"uk {ta[n]} entries vs us {tb[n]}")
        for n in sorted(set(ta) ^ set(tb)):
            note("cross-tree", "rule-table-missing", f"scripts/{name}::{n}",
                 "table present in only one tree")

        # Programs, not text. A body difference that is NOT explained by a variant token is
        # drift; one that is, is the variant layer doing its job.
        for n in sorted(set(fa) & set(fb)):
            if norm(fa[n]) == norm(fb[n]):
                continue
            sa, sb = set(string_literals(fa[n])), set(string_literals(fb[n]))
            only = (sa ^ sb)
            if only and all(VARIANT_TOKENS.search(s) for s in only):
                continue                       # permitted variant layer
            # Say WHAT differs. The first version reported "0 differing literal(s)" whenever
            # the divergence was structural rather than textual, which reads as "nothing is
            # different" next to a finding that says the bodies differ.
            if only:
                why = f"{len(only)} differing string literal(s), none carrying a variant token"
            else:
                why = ("identical string literals — the bodies differ in STRUCTURE or in "
                       "names, which is what comparing programs rather than text is for")
            note("cross-tree", "body-differs", f"scripts/{name}::{n}", why)


def md_tables(path):
    """Every table row in a markdown file, as (first cell, whole row)."""
    rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.strip()
        if not s.startswith("|") or set(s) <= set("|-: "):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if cells:
            rows.append((cells[0], tuple(cells)))
    return rows


def cross_tree_dictionaries():
    for folder in ("references", "sub-lexicons"):
        uk_f = {p.name for p in (UK / folder).glob("*.md")}
        us_f = {p.name for p in (US / folder).glob("*.md")}
        for only, side in ((uk_f - us_f, "uk"), (us_f - uk_f, "us")):
            for n in sorted(only):
                note("cross-tree", "dictionary-only-in-one-tree", f"{folder}/{n}",
                     f"present only in {side}")
        for name in sorted(uk_f & us_f):
            a = {k: r for k, r in md_tables(UK / folder / name)}
            b = {k: r for k, r in md_tables(US / folder / name)}
            missing = sorted(set(a) - set(b))
            extra = sorted(set(b) - set(a))
            if len(a) != len(b):
                note("cross-tree", "dictionary-row-count", f"{folder}/{name}",
                     f"uk {len(a)} rows vs us {len(b)}")
            for k in (missing + extra):
                note("cross-tree", "dictionary-row-missing", f"{folder}/{name}::{k[:48]}",
                     "row present in only one tree")


# ---------------------------------------------------------------------------
# ARM 2 — WITHIN-TREE
# ---------------------------------------------------------------------------
def harvest_variant_terms(tree_root):
    """The variant-controlled term list, taken from the PACKAGE'S OWN table. Supplying our
    own would measure our expectations instead of the artefact."""
    ref = tree_root / "references" / "general-legal.md"
    if not ref.exists():
        return {}
    text = ref.read_text(encoding="utf-8", errors="replace")
    # THE HEADING AND THE COLUMN ORDER BOTH FLIP BETWEEN THE TREES. The UK package says
    # "## UK vs US English" with UK in the first column; the US package says
    # "## US vs UK English" with US first. The first version of this harvester matched only
    # the UK form and assumed UK-first, so it silently returned NOTHING for the US tree and
    # the whole within-tree arm did not run on half the package -- while reporting no
    # failure. Read the header row and normalise, rather than assuming either.
    m = re.search(r"^##\s+(?:UK vs US|US vs UK) English\s*$(.*?)(?=^##\s|\Z)",
                  text, re.S | re.M)
    if not m:
        return {}
    rows, uk_first = [], None
    for line in m.group(1).splitlines():
        s = line.strip()
        if not s.startswith("|") or set(s) <= set("|-: "):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if len(cells) != 2:
            continue
        head = cells[0].lower()
        if head.startswith(("uk english", "us english")):
            uk_first = head.startswith("uk english")
            continue
        rows.append(cells)
    if uk_first is None:
        return {}
    pairs = {}
    for cells in rows:
        left, right = (cells if uk_first else cells[::-1])
        for ukw, usw in zip(re.split(r"\s*,\s*", left), re.split(r"\s*,\s*", right)):
            ukw = re.sub(r"\s*\(.*?\)\s*", "", ukw).strip().lower()
            usw = re.sub(r"\s*\(.*?\)\s*", "", usw).strip().lower()
            if ukw and usw and ukw != usw and " " not in ukw:
                pairs[ukw] = usw
    return pairs


def within_tree(tree_root, label):
    terms = harvest_variant_terms(tree_root)
    if not terms:
        note("within-tree", "no-term-list", f"{label}/references/general-legal.md",
             "the UK vs US table could not be harvested — this arm has NOT run")
        return 0

    # (a) a row rendering a variant-controlled term must carry BOTH forms.
    single = 0
    for folder in ("references", "sub-lexicons"):
        for p in sorted((tree_root / folder).glob("*.md")):
            if p.name == "general-legal.md" and folder == "references":
                continue
            for first, row in md_tables(p):
                # THE RENDERING COLUMN ONLY, not the whole row. Searching the whole row
                # fired 1,521 times, overwhelmingly on commentary that merely mentions a
                # term -- and a control with that false-positive rate is one a reviewer
                # starts skimming, which is the failure mode this project has already
                # diagnosed in the skill's own validators. The defect that shipped was in
                # what a row RENDERS, so that is what is asserted.
                if len(row) < 2:
                    continue
                # EXACT ALTERNATIVES ONLY. Substring matching on the rendering column still
                # fired 1,344 times and was ~99% wrong, because the variant mapping governs
                # the STRUCTURAL use of a word, not every compound term of art containing
                # it: "non-compete clause", "warranty and indemnity insurance" and
                # "completion accounts" are the same in both variants. So the rendering is
                # split into its alternatives and each is compared WHOLE.
                alts = [re.sub(r"\s*\(.*?\)\s*", " ", a).strip().lower()
                        for a in re.split(r"\s*/\s*|\s*;\s*", row[1])]
                alts = [a for a in alts if a]
                for ukw, usw in terms.items():
                    if ukw in alts and usw not in alts:
                        note("within-tree", "single-variant-row",
                             f"{label}/{folder}/{p.name}::{first[:40]}",
                             f"renders {ukw!r} as a whole alternative without {usw!r}")
                        single += 1
                        break

    # (b) the two dictionary layers must not give DIFFERENT ANSWERS for the same term.
    ref_rows = {}
    for p in (tree_root / "references").glob("*.md"):
        for first, row in md_tables(p):
            ref_rows.setdefault(first.strip().lower(), set()).add(" | ".join(row[1:]).lower())
    for p in sorted((tree_root / "sub-lexicons").glob("*.md")):
        for first, row in md_tables(p):
            k = first.strip().lower()
            if k not in ref_rows:
                continue
            sub = " | ".join(row[1:]).lower()
            for ukw, usw in terms.items():
                sub_uk = re.search(rf"\b{re.escape(ukw)}\b", sub)
                sub_us = re.search(rf"\b{re.escape(usw)}\b", sub)
                ref_has_both = any(re.search(rf"\b{re.escape(ukw)}\b", r)
                                   and re.search(rf"\b{re.escape(usw)}\b", r)
                                   for r in ref_rows[k])
                if ref_has_both and (bool(sub_uk) != bool(sub_us)):
                    note("within-tree", "layers-disagree",
                         f"{label}/sub-lexicons/{p.name}::{first[:40]}",
                         "the sub-dictionary gives one form where the reference gives both")
                    break
    return len(terms)


# ---------------------------------------------------------------------------
def main():
    if not UK.exists() or not US.exists():
        print("CANNOT RUN — one of the variant trees is missing.")
        return 2

    print("=" * 100)
    print("PARITY CHECK — the two trees differ only in the permitted variant layer")
    print("=" * 100)

    cross_tree_scripts()
    cross_tree_dictionaries()
    n_uk = within_tree(UK, "uk")
    n_us = within_tree(US, "us")
    print(f"  variant-controlled terms harvested from the package's own table: "
          f"uk {n_uk} · us {n_us}")

    # THE BASELINE KEY INCLUDES THE DETAIL, and that is not fussiness. Keying on
    # key+kind alone meant a divergence that got WORSE still matched its baseline entry
    # and was silently suppressed: a rule table drifting from 34-vs-91 to 34-vs-92 is the
    # same key and the same kind. A baseline that hides a known divergence deepening is
    # worse than no baseline, because it reads as "no new drift".
    def ident(d):
        return d["key"] + "|" + d["kind"] + "|" + d["detail"]

    known = set()
    if BASELINE.exists():
        known = {ident(d)
                 for d in json.loads(BASELINE.read_text(encoding="utf-8"))["divergences"]}

    fresh = [d for d in divergences if ident(d) not in known]
    baselined = [d for d in divergences if ident(d) in known]

    by_kind = {}
    for d in divergences:
        by_kind.setdefault((d["arm"], d["kind"]), []).append(d)
    print()
    for (arm, kind), items in sorted(by_kind.items()):
        new = sum(1 for d in items if ident(d) not in known)
        print(f"  {arm:<12} {kind:<28} {len(items):>4} total · {new:>4} NEW")

    if WRITE:
        BASELINE.parent.mkdir(parents=True, exist_ok=True)
        BASELINE.write_text(json.dumps({
            "_what": "Divergences between the two trees that were already present when the "
                     "parity check was built. The check fails only on divergences NOT in "
                     "this list, which is what makes 'the drift cannot grow while the "
                     "repair waits' true rather than aspirational.",
            "_repair": "Deferred item D1 reconciles these. As it lands, entries come OUT of "
                       "this file. When the file is empty the check has teeth with no "
                       "baseline at all.",
            "_not_an_excuse": "A divergence is baselined only because it EXISTS today, never "
                              "because it is acceptable. Anything the check cannot "
                              "positively classify is reported, never folded on a guess.",
            "count": len(divergences),
            "divergences": sorted(divergences, key=lambda d: (d["arm"], d["kind"], d["key"])),
        }, indent=1), encoding="utf-8")
        print(f"\n  baseline written: {BASELINE.relative_to(ROOT)} ({len(divergences)} entries)")
        return 0

    print()
    print("=" * 100)
    if fresh:
        print(f"  FAIL — {len(fresh)} divergence(s) NOT in the recorded baseline:")
        for d in fresh[:30]:
            print(f"      [{d['arm']}/{d['kind']}] {d['key']}")
            print(f"          {d['detail']}")
        if len(fresh) > 30:
            print(f"      ... and {len(fresh) - 30} more")
        print()
        print("  A new divergence means the two trees have moved apart since the baseline.")
        print("  Fix it in the branch that introduced it — do not add it to the baseline.")
        return 1
    print(f"  PASS — no divergence outside the recorded baseline "
          f"({len(baselined)} known, awaiting D1).")
    if FULL:
        for d in baselined:
            print(f"      [{d['arm']}/{d['kind']}] {d['key']}")
    print("=" * 100)
    return 0


if __name__ == "__main__":
    sys.exit(main())
