"""Plain translator vs Larpslator on the team's test sets (read from data/, never written).

  ta: data/eval-ta.jsonl        English -> Tamil, 90 sentences (expected Tamil terms per sentence)
  ko: data/glossaries/CHECK.md  Korean -> English, Kenneth's example sentences (expected English term)

"Plain" is the same LLM with no glossary or field; "Larpslator" adds the field's glossary terms, like the
live pipeline with that field's checkbox on (or detected with --auto). A sentence counts as correct when
the expected term appears in the translation. That's term presence, not overall translation quality.

Usage:
  python evaluate.py                    # both sets, 10 sentences each
  python evaluate.py --set ta --limit 0 # all 90 Tamil sentences
  python evaluate.py --auto             # detect the field instead of using the sentence's own
"""
import argparse
import json
import re
import time
from pathlib import Path

import main
import ml

DATA = ml.DATA
LOG_DIR = Path(__file__).parent / "logs"


def tamil_cases() -> list[dict]:
    cases = []
    for line in (DATA / "eval-ta.jsonl").read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("domain") not in ml.FIELDS:
            continue
        # match_fragments_ta are stems that survive Tamil suffixes; fall back to the full expected terms.
        expected = r.get("match_fragments_ta") or r.get("expected_terms_ta") or []
        cases.append({"id": r["id"], "domain": r["domain"], "text": r["text"], "source": "english",
                      "target": "Tamil", "term": r.get("term_en", ""), "expected": expected})
    return cases


def korean_cases() -> list[dict]:
    """Rows of the tables in CHECK.md: | domain | Korean term | correct English | wrong | Korean sentence | English |"""
    cases, domain_alias = [], {"academia": "math"}
    for line in (DATA / "glossaries" / "CHECK.md").read_text().splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 6 or not re.search(r"[가-힣]", cells[4]):
            continue
        domain = domain_alias.get(cells[0], cells[0])
        if domain not in ml.FIELDS:
            continue  # med: not a context in the app
        correct = [c.strip() for c in re.split(r"[/,]| or ", re.sub(r"\(.*?\)", "", cells[2])) if c.strip()]
        cases.append({"id": f"ko-{domain}-{cells[1]}", "domain": domain, "text": cells[4], "source": "korean",
                      "target": "English", "term": cells[1], "expected": correct})
    return cases


def has_term(output: str, expected: list[str], target: str) -> bool:
    out = output.lower()
    if target == "English":  # allow plurals / -ed forms
        return any(re.search(rf"\b{re.escape(e.lower())}(s|es|ed|d)?\b", out) for e in expected)
    return any(e and e.lower() in out for e in expected)


def run(cases: list[dict], auto: bool) -> list[dict]:
    rows = []
    for i, c in enumerate(cases, 1):
        active = set(ml.FIELDS) if auto else {c["domain"]}
        main.ML.domain_ema = None
        a = main.ML.analyze(c["text"], c["target"], "", active, c["source"])
        t = time.perf_counter()
        plain, _ = main.translate(c["text"], c["target"], [], [])
        t_plain = time.perf_counter() - t
        t = time.perf_counter()
        ours, _ = main.translate(c["text"], c["target"], a["terms"], [])
        t_ours = time.perf_counter() - t
        row = {**c, "detected_domain": a["domain"], "terms_used": {x["match"]: x["choice"] for x in a["terms"]},
               "plain": plain, "larpslator": ours, "plain_ok": has_term(plain, c["expected"], c["target"]),
               "larpslator_ok": has_term(ours, c["expected"], c["target"]),
               "plain_s": round(t_plain, 2), "larpslator_s": round(t_ours, 2)}
        rows.append(row)
        mark = lambda ok: "✓" if ok else "✗"
        print(f"  {i:>3}/{len(cases)} {c['id']:<22} plain {mark(row['plain_ok'])}  larpslator {mark(row['larpslator_ok'])}"
              f"  [{c['term']}] {ours[:60]}")
    return rows


def summary(name: str, rows: list[dict]):
    if not rows:
        return
    n = len(rows)
    p, o = sum(r["plain_ok"] for r in rows), sum(r["larpslator_ok"] for r in rows)
    print(f"\n{name}: expected term in the translation")
    print(f"  plain translator  {p}/{n} ({p / n:.0%})")
    print(f"  Larpslator        {o}/{n} ({o / n:.0%})")
    fixed = [r for r in rows if r["larpslator_ok"] and not r["plain_ok"]]
    broke = [r for r in rows if r["plain_ok"] and not r["larpslator_ok"]]
    print(f"  fixed by Larpslator: {len(fixed)}   made worse: {len(broke)}")
    for r in fixed[:3]:
        print(f"    + [{r['term']}] {r['text']}\n        plain: {r['plain']}\n        ours:  {r['larpslator']}")
    for r in broke[:3]:
        print(f"    - [{r['term']}] {r['text']}\n        plain: {r['plain']}\n        ours:  {r['larpslator']}")


def main_cli():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", choices=["ta", "ko", "all"], default="all")
    ap.add_argument("--limit", type=int, default=10, help="sentences per set (0 = all)")
    ap.add_argument("--auto", action="store_true", help="detect the field instead of using the sentence's own")
    args = ap.parse_args()

    sets = {"ta": ("English -> Tamil (eval-ta.jsonl)", tamil_cases), "ko": ("Korean -> English (CHECK.md)", korean_cases)}
    report = {}
    for key in (["ta", "ko"] if args.set == "all" else [args.set]):
        name, load = sets[key]
        cases = load()
        if args.limit:
            # Spread the sample across fields instead of taking the first N of one field.
            by_field = {}
            for c in cases:
                by_field.setdefault(c["domain"], []).append(c)
            cases = [c for group in zip(*by_field.values()) for c in group][:args.limit]
        print(f"\n{name}: {len(cases)} sentences{' (field detected)' if args.auto else ''}")
        report[key] = run(cases, args.auto)
    for key, rows in report.items():
        summary(sets[key][0], rows)
    LOG_DIR.mkdir(exist_ok=True)
    out = LOG_DIR / f"eval-{time.strftime('%Y%m%d-%H%M%S')}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1))
    print(f"\nfull results: {out}")


if __name__ == "__main__":
    main_cli()
