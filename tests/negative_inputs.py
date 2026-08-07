# -*- coding: utf-8 -*-
"""ONE FAILING INPUT PER CHECK.

Nothing in the 198 shipped files can currently demonstrate that any of the thirteen
executable checks fires at all. A fixture set of only-passing cases produces tests that pass
because nothing is being tested -- so each case here is built to violate ONE check's stated
pass condition, and the suite asserts the check NOTICES.

Every input is synthetic. The prose is invented and deliberately bland.

A case declares:
    check    the script under test
    args     how to invoke it, with {in} standing for the generated input
    want     the exit code that means "the check fired"
    build    writes the violating input and returns its path
    passes   writes a CONFORMING input, so a check that fires on everything is caught too.
             A check that cannot tell good from bad is not a check, and only the pair shows
             it. This is the half a one-sided suite leaves out.
"""
import json
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"


def _para(idx, src, en=None, **kw):
    d = {"idx": idx, "text": src, "style": "Normal"}
    if en is not None:
        d["en"] = en
    d.update(kw)
    return d


def _write(tmp, name, obj):
    p = Path(tmp) / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    return p


CASES = []


def case(check, why, args="{in}", want=None):
    def deco(fn):
        CASES.append({"check": check, "why": why, "args": args,
                      "want": want, "build": fn})
        return fn
    return deco


# ---------------------------------------------------------------------------
# 1. validate_translations.py — completeness, and the 35-paragraph batch cap.
#    The cap is an ATTENTION cap, measured correctly calibrated. Two ways to break it.
# ---------------------------------------------------------------------------
@case("validate_translations.py", "a paragraph with no English at all")
def _vt_incomplete(tmp):
    bad = [_para(i, f"Bron paragraaf {i}.", f"Source paragraph {i}.") for i in range(3)]
    bad.append(_para(3, "Deze is niet vertaald."))          # no `en` key
    good = [_para(i, f"Bron paragraaf {i}.", f"Source paragraph {i}.") for i in range(4)]
    return _write(tmp, "vt_bad.json", bad), _write(tmp, "vt_good.json", good)


@case("validate_translations.py", "a batch of 36, one over the cap of 35")
def _vt_batch(tmp):
    bad = [_para(i, f"Bron {i}.", f"Source {i}.", batch=1) for i in range(36)]
    good = [_para(i, f"Bron {i}.", f"Source {i}.", batch=1) for i in range(35)]
    return _write(tmp, "vt_batch_bad.json", bad), _write(tmp, "vt_batch_good.json", good)


# ---------------------------------------------------------------------------
# 2. validate_en_runs.py — a definitions section whose paragraphs carry no en_runs.
# ---------------------------------------------------------------------------
@case("validate_en_runs.py", "a definitions paragraph with no en_runs")
def _ver(tmp):
    # The detector needs BOTH anchors: a recognised heading of <=80 chars, and at least
    # THREE of the next eight paragraphs in the predicate shape `Term means ...`. Two
    # definitions is not a definitions section, and the heading is read from `en`, not from
    # the source text. Get either wrong and the gate stays silent -- which is exactly what
    # the first version of this case did, and it read as "the gate does not fire".
    DEFS = [('"Aanvangsdatum" betekent de begindatum.',
             '"Commencement Date" means the start date.'),
            ('"Overeenkomst" betekent deze overeenkomst.',
             '"Agreement" means this agreement.'),
            ('"Partij" betekent een partij bij deze overeenkomst.',
             '"Party" means a party to this agreement.'),
            ('"Zekerheid" betekent enige zekerheid.',
             '"Security" means any security given under this agreement.')]

    def block(with_runs):
        rows = [_para(0, "1. Definities", "1. Definitions")]
        for i, (src, en) in enumerate(DEFS, start=1):
            p = _para(i, src, en)
            if with_runs:
                # en_runs are OFFSETS into `en`, not copies of its text.
                p["en_runs"] = [{"start": 0, "end": len(en), "bold": False}]
            rows.append(p)
        return rows
    return (_write(tmp, "ver_bad.json", block(False)),
            _write(tmp, "ver_good.json", block(True)))


# ---------------------------------------------------------------------------
# 3. validate_segment_shapes.py — XML-boundary risk shapes in en_segments.
# ---------------------------------------------------------------------------
@case("validate_segment_shapes.py", "a segment boundary falling on a bare article",
      args="{in} --strict")
def _vss(tmp):
    # The real key is `type`, not `kind`, and a paragraph is only examined when it declares
    # tracked changes. Both were wrong first time round and the check reported
    # "all 0 tracked-change paragraphs" -- a PASS over an empty set, which is the classic
    # shape of a check passing for the wrong reason.
    def para(en_seg):
        return [{"idx": 0, "text": "De partij stemt in.", "style": "Normal",
                 "en": "The party agrees.", "has_track_changes": True,
                 "tc_segments": [{"type": "regular", "text": "De partij "},
                                 {"type": "ins", "text": "stemt in."}],
                 "en_segments": en_seg}]
    # The linter's actual subject is a segment BOUNDARY that falls on a binding word --
    # an inserted segment consisting of a bare article strands it against the run boundary
    # and predicts the downstream defect. Raw XML in the text, which the first version of
    # this case used, is not what it looks for and it passed cleanly.
    bad = para([{"type": "regular", "en": "The party shall deliver "},
                {"type": "ins", "en": "the"},
                {"type": "regular", "en": " goods."}])
    good = para([{"type": "regular", "en": "The party shall deliver "},
                 {"type": "ins", "en": "all outstanding"},
                 {"type": "regular", "en": " goods."}])
    return _write(tmp, "vss_bad.json", bad), _write(tmp, "vss_good.json", good)


# ---------------------------------------------------------------------------
# 4. validate_reject_all.py — the reject-all reading must be coherent English too.
#    This is the construct the skill has no concept of: what the document says if every
#    tracked change is rejected.
# ---------------------------------------------------------------------------
@case("validate_reject_all.py", "accept-all reads clean, reject-all doubles an article",
      args="{in} --strict")
def _vra(tmp):
    def para(en_seg):
        return [{"idx": 0, "text": "De termijn is drie jaar.", "style": "Normal",
                 "en": "The term is five years.", "has_track_changes": True,
                 "tc_segments": [{"type": "regular", "text": "De termijn is "},
                                 {"type": "del", "text": "drie"},
                                 {"type": "ins", "text": "vijf"},
                                 {"type": "regular", "text": " jaar."}],
                 "en_segments": en_seg}]
    # ACCEPTING every change reads perfectly; REJECTING every change leaves a doubled
    # article. That asymmetry is the whole point of the check and the reason the
    # reject-all view has to be reconstructed rather than reasoned about:
    #   accept -> "Payment is due under clause 4 of the Schedule."   clean
    #   reject -> "Payment is due under the the Schedule."           doubled article
    bad = para([{"type": "regular", "en": "Payment is due under "},
                {"type": "del", "en": "the"},
                {"type": "ins", "en": "clause 4 of"},
                {"type": "regular", "en": " the Schedule."}])
    good = para([{"type": "regular", "en": "Payment is due under "},
                 {"type": "del", "en": "clause 3"},
                 {"type": "ins", "en": "clause 4"},
                 {"type": "regular", "en": " of the Schedule."}])
    return _write(tmp, "vra_bad.json", bad), _write(tmp, "vra_good.json", good)


# ---------------------------------------------------------------------------
# 5. validate_apply.py — did the declared English actually land in the XML?
#    THE KNOWN LIMIT, and the suite states it rather than hiding it: --strict compares
#    TOKEN SETS. No order, no punctuation, not even a multiset, and it polices only MISSING
#    tokens, never extra ones. A negative input therefore has to REMOVE a word; reordering
#    or repunctuating passes. That limit is branch 11's whole reason for existing.
# ---------------------------------------------------------------------------
@case("validate_apply.py", "declared English that never reached the XML",
      args="{in} {xml} --strict")
def _va(tmp):
    xml = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
           '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
           '<w:body><w:p><w:r><w:t>The Supplier shall deliver</w:t></w:r></w:p></w:body>'
           '</w:document>')
    (Path(tmp) / "document.xml").write_text(xml, encoding="utf-8")
    bad = [_para(0, "De leverancier levert de goederen op tijd.",
                 "The Supplier shall deliver the goods punctually.")]
    good = [_para(0, "De leverancier levert.", "The Supplier shall deliver")]
    return _write(tmp, "va_bad.json", bad), _write(tmp, "va_good.json", good)


# ---------------------------------------------------------------------------
# 6. lexicon_compliance.py — a forbidden calque in the English.
# ---------------------------------------------------------------------------
@case("lexicon_compliance.py", "a forbidden calque in the translated text",
      args="{in} --stage pre-apply --warnings-are-errors")
def _lc(tmp):
    # Taken from the shipped rule table's own BLOCK list rather than invented. An invented
    # "forbidden" phrase proves nothing about the check -- which is what the first version
    # of this case did, and it reported PASSED.
    bad = [_para(0, "Partijen komen overeen.",
                 "The present agreement is governed by English law.")]
    good = [_para(0, "Partijen komen overeen.",
                  "This agreement is governed by English law.")]
    return _write(tmp, "lc_bad.json", bad), _write(tmp, "lc_good.json", good)


# ---------------------------------------------------------------------------
# 7. clean_conversion_artifacts.py — upstream conversion damage in a .docx.
# ---------------------------------------------------------------------------
@case("clean_conversion_artifacts.py", "a .docx that is not a ZIP container")
def _cca(tmp):
    bad = Path(tmp) / "cca_bad.docx"
    shutil.copyfile(FIXTURES / "not-a-zip.docx", bad)
    good = Path(tmp) / "cca_good.docx"
    shutil.copyfile(FIXTURES / "anchors-and-tabs.docx", good)
    return bad, good


# ---------------------------------------------------------------------------
# 8. extract_paragraphs.py — a corrupt container.
# ---------------------------------------------------------------------------
@case("extract_paragraphs.py", "a truncated .docx", args="{in} {out}")
def _ep(tmp):
    bad = Path(tmp) / "ep_bad.docx"
    shutil.copyfile(FIXTURES / "truncated.docx", bad)
    good = Path(tmp) / "ep_good.docx"
    shutil.copyfile(FIXTURES / "anchors-and-tabs.docx", good)
    return bad, good


# ---------------------------------------------------------------------------
# 9. strip_noop_tracked_changes.py — operates on a document.xml.
# ---------------------------------------------------------------------------
@case("strip_noop_tracked_changes.py", "a document.xml that is not well-formed XML")
def _snt(tmp):
    bad = Path(tmp) / "snt_bad.xml"
    bad.write_text('<w:document><w:body><w:p><w:r><w:t>unclosed', encoding="utf-8")
    good = Path(tmp) / "snt_good.xml"
    good.write_text(
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:body><w:p><w:r><w:t>Settled text.</w:t></w:r></w:p></w:body></w:document>',
        encoding="utf-8")
    return bad, good


# ---------------------------------------------------------------------------
# 10. coalesce_fragmented_tcs.py — malformed input.
# ---------------------------------------------------------------------------
@case("coalesce_fragmented_tcs.py", "paragraphs.json that is not a list of paragraphs")
def _cft(tmp):
    bad = Path(tmp) / "cft_bad.json"
    bad.write_text('{"not": "a paragraph list"}', encoding="utf-8")
    good = _write(tmp, "cft_good.json",
                  [_para(0, "De partij stemt in.", "The party agrees.")])
    return bad, good


# ---------------------------------------------------------------------------
# 11. verify_diligence.py — the end-of-pipeline audit, over a workdir.
#     Its WARN is `1 if strict else 0`, so it must be driven WITH --strict or a warning is
#     indistinguishable from a pass. That is the finding, and here it is also the method.
# ---------------------------------------------------------------------------
@case("verify_diligence.py", "a workdir where the pipeline plainly did not run",
      args="{in} --strict")
def _vd(tmp):
    bad = Path(tmp) / "wd_bad"
    (bad / "word").mkdir(parents=True, exist_ok=True)
    good = Path(tmp) / "wd_good"
    (good / "word").mkdir(parents=True, exist_ok=True)
    _write(good, "paragraphs.json",
           [_para(i, f"Bron {i}.", f"Source {i}.", batch=1) for i in range(4)])
    # The state file's real shape, taken from an actual run rather than invented:
    # `validated_indices` plus a `history` audit trail. A guessed shape made the audit
    # report all four paragraphs as never validated, which looked like the check being
    # unable to tell good from bad when it was reading a file it did not recognise.
    (good / ".validate-state.json").write_text(
        json.dumps({"validated_indices": [0, 1, 2, 3],
                    "history": [{"timestamp": "2020-01-01T00:00:00Z",
                                 "count": 4, "indices": [0, 1, 2, 3]}]}),
        encoding="utf-8")
    shutil.copyfile(FIXTURES / "anchors-and-tabs.docx", good / "final.docx")
    with zipfile.ZipFile(FIXTURES / "anchors-and-tabs.docx") as z:
        z.extractall(good / "final")
    return bad, good


# ---------------------------------------------------------------------------
# 12 & 13. translate_comments.py and translate_headers_footers.py both take a workdir and
#     translate auxiliary parts. A missing part is their failing input.
# ---------------------------------------------------------------------------
# Both take `original.docx [output_dir]` and a mode flag -- NOT a workdir. Driving them
# with a directory made them fail on both arms, which reads as "cannot tell good from bad"
# when the truth was that the harness could not drive them at all.
@case("translate_comments.py", "a source .docx that is not a ZIP container",
      args="{in} --list")
def _tc(tmp):
    bad = Path(tmp) / "tc_bad.docx"
    shutil.copyfile(FIXTURES / "not-a-zip.docx", bad)
    good = Path(tmp) / "tc_good.docx"
    shutil.copyfile(FIXTURES / "anchors-and-tabs.docx", good)
    return bad, good


@case("translate_headers_footers.py", "a source .docx that is not a ZIP container",
      args="{in} --extract {out}")
def _thf(tmp):
    bad = Path(tmp) / "thf_bad.docx"
    shutil.copyfile(FIXTURES / "not-a-zip.docx", bad)
    # The clean arm needs a document that HAS a header and a footer. Handed one without,
    # the script exits non-zero and the pair reads as "cannot tell good from bad" when in
    # fact the harness had given it nothing to do.
    good = Path(tmp) / "thf_good.docx"
    shutil.copyfile(FIXTURES / "headers-footers.docx", good)
    return bad, good
