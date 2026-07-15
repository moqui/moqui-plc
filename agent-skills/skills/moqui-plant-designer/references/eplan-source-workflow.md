# EPLAN source workflow

Run `scripts/analyze_eplan_sources.py` against the EPLAN UTF-16 CSV export and,
optionally, the electrical drawing PDF. The extractor recognizes the two EPLAN
header rows and produces:

- source hashes and exact source row numbers;
- article, manufacturer, description, page and device-tag fields;
- a JSON review queue with empty proposed classification and PhysicalDevice ID;
- a Markdown provenance summary, including PDF revision warnings.

The developer reviews repeated article rows, device identity, cabling, signal
semantics, group roles and safety relevance. Only reviewed records are copied
into the surveys. The script does not perform physical binding or electrical
verification.
