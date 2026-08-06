"""A3 final check: every Markdown table row in the committable files is contiguous
with a header + delimiter row, and every row has the header's column count.

This is the check that would have caught the eleven non-rendering register rows.
"""
import re
import sys

PIPE = re.compile(r"(?<!\\)\|")
DELIM = re.compile(r"^\|[\s:|-]+\|$")


def check(path: str) -> int:
    lines = open(path, encoding="utf-8").read().split("\n")
    hdr_width = None
    prev_row = None
    bad = orphan = tables = 0
    for i, raw in enumerate(lines, 1):
        st = raw.strip()
        if st.startswith("|") and st.endswith("|"):
            if DELIM.match(st):
                if prev_row is None:
                    print(f"  {path}:{i} delimiter with no header above")
                    bad += 1
                    continue
                hdr_width = len(PIPE.findall(prev_row))
                if len(PIPE.findall(st)) != hdr_width:
                    print(f"  {path}:{i} delimiter width mismatch")
                    bad += 1
                tables += 1
                prev_row = st
                continue
            if hdr_width is None:
                # could be the header line itself; only a problem if no delimiter follows
                nxt = lines[i].strip() if i < len(lines) else ""
                if not DELIM.match(nxt):
                    orphan += 1
                    if orphan <= 5:
                        print(f"  {path}:{i} ORPHAN row (no header/delimiter): {st[:70]}")
            elif len(PIPE.findall(st)) != hdr_width:
                bad += 1
                if bad <= 8:
                    print(f"  {path}:{i} width {len(PIPE.findall(st))} vs header "
                          f"{hdr_width}: {st[:70]}")
            prev_row = st
        else:
            if not st:
                hdr_width = None
                prev_row = None
            else:
                prev_row = None
    print(f"{path}: {tables} tables, {bad} width mismatches, {orphan} orphan rows")
    return bad + orphan


if __name__ == "__main__":
    total = sum(check(p) for p in sys.argv[1:])
    print(f"\n{'CLEAN' if total == 0 else 'PROBLEMS: %d' % total}")
    sys.exit(1 if total else 0)
