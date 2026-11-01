# Data (Roles D + C)
glossaries/<domain>.json   term -> list of candidate translations (15-20 terms per domain)
train.jsonl                training sentences for the domain classifier
eval.jsonl                 evaluation set (20 terms x 2 sentences, with correct translations)
Domains: academia, cs, med, general

## Korean terminology research (2026-11-01)

Research domains for this collection: cs, pickleball, tennis. These are additional
research labels; the original classifier plan above still lists academia/cs/med.
No classifier, dashboard domain selector, or backend logic was changed.

- research/TERMS.md: readable table of 60 English–Korean term entries (20/domain).
- research/terms.en-ko.jsonl: definitions, preferred terms, alternative spellings,
  evidence status, review status, and direct source URLs.
- research/sources.json: seven source records, including authority notes.
- research/collection_report.json: actual fetch outcomes, timestamps, hashes,
  and extraction failures. Failed sources are never counted as scraped.
- research/spelling_checks.jsonl: automated spelling-presence checks, not
  verification of meaning or translation quality.
- glossaries/<domain>.json: term -> candidate Korean translations (list), as
  proposed in the original data format.
- glossaries/selected/<domain>-ko.json: term -> preferred Korean string, compatible
  with backend/translate.py's --glossary input. Alternatives are synonyms or
  spelling variants, not deliberately incorrect distractors.

### Proposed glossary handoff (backend implementation required)

These are proposed commands for the backend teammate after implementing a translator; no backend translator is included in this research contribution:

~~~powershell
python backend/translate.py --text "Wait for the ball to bounce before hitting it from the kitchen." --target Korean --domain pickleball --glossary data/glossaries/selected/pickleball-ko.json
python backend/translate.py --text "Love means zero in tennis." --target Korean --domain tennis --glossary data/glossaries/selected/tennis-ko.json
~~~

Use a Korean-speaking teammate to assess whether each translation is natural and
preserves the intended sporting meaning.

### Reproduce source collection

~~~powershell
python data/research/collect_sources.py
~~~

The collector needs only Python's standard library for HTML. Optionally install
pypdf to check extractable PDF text. It fetches only the listed sources, checks
robots.txt, limits file size, retains certificate verification, and pauses between
requests. It saves metadata and term-presence checks; it does not save full pages,
bulk-download a website, or rewrite curated definitions.

### Evidence and limitations

This is a bounded starter terminology dataset, not all Korean documents on these
subjects. Definitions are original short paraphrases written during research.
Source links document their terminology basis; they are not licenses to reproduce
the full source publications. No full article or PDF text is redistributed.

All human_review_status values are pending. Before the demo, a Korean-speaking
teammate should approve terminology and add natural utterance-level translations.
None of these entries has been tested against your plain-translation baseline;
do not describe them as proven baseline failures. There is no generated training
or evaluation corpus in this collection.

Five tennis entries use indexed KOCW text only: direct retrieval failed TLS
hostname verification. The collector does not bypass that failure. The 2020
KTA/ITF PDF is a historical reference and yielded no Korean text with basic PDF
extraction; do not use it as a current rulebook or claim it was successfully
text-scraped. See the report for live outcomes, including robots skips.

The pickleball source is an independent specialist guide, not an official
governing-body glossary. Korean spellings may vary. Erne was intentionally omitted:
the retrieved source used an inconsistent spelling. Do not equate the two-bounce
rule with a double-bounce fault. Rule details and scoring formats must be checked
against the rules of the actual event; glossary entries are short word-sense aids.

Recommended demo candidates: dictionary/key (cs), kitchen/drive/stacking/paddle
(pickleball), love/break point/let/set (tennis). Test these as hypotheses rather
than assuming a plain translator will get them wrong.

## Tamil academic research (2026-11-01)

See research/tamil/README.md for the new Tamil research collection.
It contains two Tamil computing article records and four English academic sports
papers with clearly labeled, assistant-authored Tamil summaries (approved fallback).
Only the four English articles have licensed full text saved. All Tamil summaries
await human review. See the collection report and candidate list for access gaps.
The earlier Korean data remains separate and must not be used as Tamil terminology.

## Tamil draft research dataset

See data/TAMIL_REVIEW.md and data/TEAM_HANDOFF_TAMIL.md. There are 45 draft terms
(15 per topic) and 90 held-out English utterances with draft Tamil references in
data/eval-ta.jsonl. Human review has not occurred. Academic sources provide context;
they do not validate the authored translations. data/domains-ta.json proposes labels
for the ML teammate; no classifier was trained. Application code changes were undone
so this contribution remains research-only.
