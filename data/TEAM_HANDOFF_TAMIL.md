# Tamil research handoff

Scope: research and data only. Backend implementation, tests, and environment changes were undone at the user's request.

## Prepared assets

- 45 draft English–Tamil terms, 15 per topic, in glossaries/tamil-drafts.jsonl.
- Three flat Tamil glossaries in glossaries/selected/*-ta.json.
- 90 held-out evaluation sentences and draft references in eval-ta.jsonl.
- Human review instructions in TAMIL_REVIEW.md.
- Proposed classifier labels in domains-ta.json; no classifier was trained.
- Academic sources and labeled Tamil summaries in research/tamil/.

## Research tasks remaining

A Tamil-speaking teammate must review terms and references. All approvals remain pending.
No baseline failure, translation improvement, or demo sentence has been verified by a live API run.

## Handoff to teammates

Role B can load the selected Tamil glossary as an English-to-Tamil map and compare the same
English sentences with general/no glossary versus correct domain/glossary settings. Record
latency, API errors, and human judgments separately. Word presence alone is not accuracy.

Role C should use cs, tennis, pickleball, general as proposed labels and train on independent
English utterances. Do not train on eval-ta.jsonl or its paraphrases. Feedback choices need
validated Tamil alternatives and local persistence.

The Korean files are separate and must not be used as Tamil terminology. Research scripts
under research/ collect sources; they do not implement the application.
