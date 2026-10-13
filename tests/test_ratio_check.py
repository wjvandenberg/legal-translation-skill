# -*- coding: utf-8 -*-
"""THE CHARACTER-RATIO CHECK CAN FIRE - branch 12 slice 12c, registers H2 and H4.

validate_translations.py measured every translated paragraph's English against its source only above 150
characters (H4: 758 of 1,291 translated paragraphs in the 13 recorded runs never examined), with one pair of
thresholds for every language (a Japanese paragraph had to lose 80% of its English to warn), and printed PASS
on a source already in English, where the ratio measures nothing (H2). On SYNTHETIC notes, each case in its
own temporary workdir, the language declared through Step 1c's own route (`--declare`):

  1  THE FLOOR. A 29-character source whose English lost most of itself BLOCKS - the check must fail it, and
     is asserted to exit 2; a 40-character one with half its English warns; a 19-character one is not
     examined. (Red at the old floor of 150.)
  2  THE LANGUAGE. Declared Japanese, English as long as the source (ratio 1.0) WARNS - its median is near 3;
     at ratio 2.6 it passes. (Red unscaled.) Declared Italian and declared Norwegian - no lexicon, still
     checked - at 0.5 warn, at 0.9 pass, unscaled.
  3  SOURCE DECLARED ENGLISH. The ratio says NOT APPLICABLE, never PASS, and does not block even at 0.2; the
     batch cap still refuses 36. (Red: it used to say PASS.)
  4  UNDECLARED. Checked against the unscaled thresholds and says so: PASS carries "unscaled", and the reason
     names Step 1c.

    uv run python tests/test_ratio_check.py [--variant us]
"""
import io
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent
VARIANT = sys.argv[sys.argv.index("--variant") + 1] if "--variant" in sys.argv else "uk"
SCRIPTS = ROOT / VARIANT / "scripts"
FAIL, CHECKED = [], 0


def ok(label, cond, detail=""):
    global CHECKED
    CHECKED += 1
    print(f"  {'ok  ' if cond else 'FAIL'}  {label}" + (f"  [{detail}]" if detail and not cond else ""))
    if not cond:
        FAIL.append(label)


def run(paras, language=None):
    """Write the notes into a fresh workdir, declare `language` if given, run the check: (rc, output)."""
    with tempfile.TemporaryDirectory(prefix="ratio-") as td:
        notes = Path(td) / "paragraphs.json"
        notes.write_bytes(json.dumps(paras, ensure_ascii=False).encode("utf-8"))
        if language:
            d = subprocess.run([sys.executable, str(SCRIPTS / "source_language_markers.py"), "--declare", language,
                                td], capture_output=True, text=True, encoding="utf-8", errors="replace")
            if d.returncode != 0:
                return -1, d.stdout + d.stderr
        r = subprocess.run([sys.executable, str(SCRIPTS / "validate_translations.py"), str(notes)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        return r.returncode, (r.stdout or "") + (r.stderr or "")


def para(i, text, en):
    return {"idx": i, "text": text, "en": en}


def sized(n, ch="a"):
    """A source or English text of exactly n characters, spaced like prose."""
    return ((ch * 4 + " ") * (n // 5 + 1))[:n].strip().ljust(n, ch)


print(f"variant {VARIANT}")
# ------------------------------------------------------------------------------------------ 1
print("\n1   THE FLOOR")
rc, out = run([para(0, sized(29), sized(5, "e"))], "italian")
ok("29 characters, English at 0.17: BLOCKS (exit 2)", rc == 2 and "BLOCK" in out, f"rc={rc}")
rc, out = run([para(0, sized(40), sized(20, "e"))], "italian")
ok("40 characters, English at 0.50: WARNS (exit 1)", rc == 1 and "WARN" in out, f"rc={rc}")
rc, out = run([para(0, sized(19), sized(2, "e"))], "italian")
ok("19 characters, English at 0.11: not examined (exit 0)", rc == 0, f"rc={rc}")

# ------------------------------------------------------------------------------------------ 2
print("\n2   THE LANGUAGE")
JA = "本契約は当事者間の合意を定めるものであり、全ての条項は有効である。"
rc, out = run([para(0, JA, sized(len(JA), "e"))], "japanese")
ok(f"Japanese ({len(JA)} characters), English at 1.0: WARNS - scaled x2.0", rc == 1 and "WARN" in out, f"rc={rc}")
ok("...and the thresholds printed are the scaled ones", "WARN below 1.20" in out, out[-300:])
rc, out = run([para(0, JA, sized(int(len(JA) * 2.6), "e"))], "japanese")
ok("Japanese, English at 2.6: passes", rc == 0 and "PASS" in out, f"rc={rc}")
for lang in ("italian", "norwegian"):
    rc, out = run([para(0, sized(200), sized(100, "e"))], lang)
    ok(f"declared {lang}, English at 0.50: WARNS, unscaled", rc == 1 and "WARN below 0.60" in out, f"rc={rc}")
    rc, out = run([para(0, sized(200), sized(180, "e"))], lang)
    ok(f"declared {lang}, English at 0.90: PASS, not marked unscaled", rc == 0 and "PASS:" in out
       and "unscaled" not in out, f"rc={rc}")

# ------------------------------------------------------------------------------------------ 3
print("\n3   SOURCE DECLARED ENGLISH")
rc, out = run([para(0, sized(200), sized(40, "e"))], "english")
ok("ratio 0.2: NOT APPLICABLE, exit 0, never PASS and never BLOCK", rc == 0 and "NOT APPLICABLE" in out
   and "PASS" not in out and "BLOCK" not in out, f"rc={rc}")
ok("...the reason names English as the target", "TARGET" in out, out[-300:])
rc, out = run([para(i, f"Source {i}.", f"Source {i}!") for i in range(36)], "english")
ok("the batch cap still refuses 36 on a source declared English", rc == 2 and "per-batch cap" in out, f"rc={rc}")

# ------------------------------------------------------------------------------------------ 4
print("\n4   UNDECLARED")
rc, out = run([para(0, sized(200), sized(180, "e"))])
ok("no declaration: PASS marked unscaled", rc == 0 and "PASS (unscaled" in out, f"rc={rc}")
ok("...and the reason names Step 1c", "Step 1c" in out, out[-300:])
rc, out = run([para(0, JA, sized(len(JA), "e"))])
ok("undeclared Japanese at 1.0: unscaled, so it passes - the declaration is what scales it", rc == 0, f"rc={rc}")

print("\n" + "=" * 88)
print(f"  {CHECKED} check(s), {len(FAIL)} failure(s)")
sys.exit(1 if FAIL else 0)
