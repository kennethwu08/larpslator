# Larpslator research and runtime data

## Current application contract

The fields are `cs`, `tennis`, `pickleball`, and `math`, with `general` as fallback.
`larp` is a style, not a subject. `academia.json` is an alias loaded for math;
`med.json` is a legacy file and is not loaded by the current application.
The authoritative format is documented in `docs/messages.md` (read-only for this role).

The backend loads these files at startup, in preference order:

1. `glossaries/<field>.json` (then aliases).
2. `glossaries/selected/<field>-<lang>.json`.
3. Built-in seed terms and alternatives.

Mixed glossary shapes are intentional and supported. A plain Korean list attached
to an English term supplies Korean translations. A language map such as
`{"Korean": ["키친"], "Tamil": ["கிச்சன்"]}` explicitly names the target.
Selected files are flat `English term -> preferred translated string` maps.
The earliest option wins preference; selected exports do not override an earlier
main-file option. Backend restart is required to reload changed runtime data.

## Tamil readiness

45 draft English-to-Tamil terms are provided (15 per domain across cs, tennis,
pickleball). The main glossaries and selected Tamil exports are checked by
`research/audit_data.py`. The current backend exposes Tamil; older notes saying
that it still must be added to the language list were historical and are superseded.
This is not proof of end-to-end speech or translation quality. Tamil terminology
and reference sentences still require a Tamil-speaking reviewer.

The current Tamil contribution is English-to-Tamil. It does not contain Tamil
source-script terms for reverse glossary matching. Do not claim that this dataset
provides bidirectional Tamil jargon coverage.

## Research collections

- `research/terms.en-ko.jsonl`: 60 original English–Korean term records with
  definitions, source links and evidence/review status; `research/TERMS.md` is readable.
- `research/sources.json` and `collection_report.json`: original bounded collection
  and actual retrieval outcomes. Search indexing is not a successful direct scrape.
- `research/tamil/`: original academic metadata, labeled assistant-authored Tamil
  summaries, and four licensed English sports full texts. English sports papers
  are not Tamil-language publications.
- `glossaries/tamil-drafts.jsonl`: original 45 authored Tamil term drafts.
- `eval-ta.jsonl`: 90 held-out English utterances with draft Tamil references;
  not a gold-standard set and never a training set.
- `research/supplemental/`: additional source metadata, spelling checks and
  pending-review candidates. These are not silently promoted into live choices.
- `research/data-audit.json` and `DATA_AUDIT.md`: current structural audit and findings.

## Reproduce

```powershell
python data/research/audit_data.py
python data/research/supplemental/collect.py
```

These tools use the Python standard library and do not require API keys.
The supplemental collector checks robots.txt, limits response size, retains TLS
verification, and records blocked/failed sources. It does not archive full pages
or journal PDFs. Definitions are short authored paraphrases; spelling presence
does not establish translation correctness. Read review and license notes.

Original collection commands remain available:
`python data/research/collect_sources.py` and
`python data/research/tamil/collect_papers.py`.
Historical reports keep their original outcomes and are not evidence of a new run.

## Deployment boundary

`FASTAPI_ENTRYPOINT_NOT_FOUND` occurs before application data loading. Changing
JSON cannot fix the selected framework/root directory on Vercel. The frontend
project needs the `dashboard` root and static-site settings; the Python backend
needs its own deliberate deployment. No deployment setting or protected file was
changed by this data audit. The Vercel project inspected earlier pointed to
JustinC-08/larpslator, while earlier dashboard work was pushed to
kennethwu08/larpslator; the deployment owner must verify which repository contains
the intended code before redeploying.

API keys belong in backend environment settings, never these datasets.
