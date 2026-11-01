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

The current backend already loads selected Tamil files and lists Tamil as a target.
Role B can compare the same
English sentences with general/no glossary versus correct domain/glossary settings. Record
latency, API errors, and human judgments separately. Word presence alone is not accuracy.

This research pack covers cs, tennis, pickleball and general; the application also
supports math. Role C should preserve that application domain contract and use independent
English utterances. Do not train on eval-ta.jsonl or its paraphrases. Feedback choices need
validated Tamil alternatives and local persistence.

The Korean files are separate and must not be used as Tamil terminology. Research scripts
under research/ collect sources; they do not implement the application.
