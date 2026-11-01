# Data consistency audit — 2026-11-01

## Result

Structural checks passed: 29 JSON/JSONL artifacts, 269 JSONL rows, 90 Tamil
evaluation sentences, and no duplicate JSON keys or preferred-choice conflicts.
Counts describe this run; rerun `python data/research/audit_data.py` after edits.
This does not validate translation quality or the deployed backend.

## Corrected inconsistencies

- The old README listed academia/cs/med as application fields. Current fields are
  cs/tennis/pickleball/math; academia is the math-file alias and med is not loaded.
- Readiness notes said Tamil must be added to the backend. The inspected backend
  already includes Tamil. Updated the notes without changing application code.
- The handoff implied selected files require a new loader. They are already merged
  automatically; main-file options take precedence. No preference conflicts found.
- domains-ta.json implied there was no application classifier and omitted math from
  its explanation. It is now explicitly scoped as research-pack metadata, not
  application configuration. Its existing labels and file paths were preserved.

## Valid behavior that was preserved

Language maps, flat selected strings and script-inferred option lists are all
supported. The 20 CS Korean selected terms need not be duplicated in cs.json:
the current backend merges them. Everyday wrong-meaning options in existing
Korean-to-English entries are deliberate feedback alternatives per the protocol,
not malformed translations. No existing glossary choice was removed or reordered.

## Remaining research gaps

There are 15 English-to-Tamil terms per researched field (45 total), but no
Tamil-script source terms for reverse matching. Math has no English-to-Tamil
coverage in these data files. Do not silently claim full bilingual coverage.
Tamil terms and evaluation references remain pending human review. Additional
Korean candidates are quarantined in research/supplemental until reviewed.

## Vercel issue (outside data edit scope)

The reported FASTAPI_ENTRYPOINT_NOT_FOUND error occurs while Vercel selects a
framework/entrypoint, before glossary loading. Data changes cannot fix it.
The inspected Vercel project selected FastAPI with backend as its root. Static
frontend deployment needs dashboard as the root and the Other framework preset.
Also verify repository identity: Vercel showed JustinC-08/larpslator at ed94556,
while the earlier redesigned dashboard was pushed to kennethwu08/larpslator at
2345bf7. This is an observed mismatch, not proof of which repository is intended.
No Vercel settings, backend files or frontend files were changed in this audit.

## Supplemental source collection

Two of four direct source attempts succeeded and supplied 12 Korean candidates:
six computing terms from Python documentation and six pickleball terms from PGC.
The tennis and Tamil direct attempts were skipped when robots availability could
not be established; they are not counted as successful scrapes. A new Tamil-titled
AI/ML journal record was verified through publisher web metadata. Its abstract
is English, full body language is unverified, and its DOI is incomplete. The
Tamil summary is assistant-authored and pending review. No full paper was copied.
