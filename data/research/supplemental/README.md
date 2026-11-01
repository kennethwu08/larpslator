# Supplemental Korean and Tamil research

Run `python data/research/supplemental/collect.py` to refresh the four fixed sources.
Read `collection_report.json` for actual outcomes. `terms.jsonl` contains only
candidate spellings found in successfully retrieved HTML, with short original
English definitions and direct source URLs. These are pending-review research
records, not automatic changes to runtime glossaries. Existing choices are preserved.

The Python source is official technical documentation. PGC is an independent
community glossary, not a governing-body rulebook. Sports definitions are word-sense
notes, not complete rules. No full page or PDF is redistributed.

`papers.jsonl` adds a University of Malaya journal record discovered through web
research. The publisher abstract is English despite the Tamil title. PDF body
language and full-text access are unverified. Its incomplete DOI is deliberately
stored as null. The Tamil summary is an authored draft, not extracted Tamil prose.
The direct collector could not establish robots availability for the journal or
the tennis handout, and skipped them. No successful full-paper scrape is claimed.

Do not use these records as gold-standard training or evaluation data until a
language reviewer approves them. Spelling presence alone does not validate meaning.
