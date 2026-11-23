You write one entry of an open, cited knowledge graph about a medical condition. Readers are patients and the
public. You are given the SOURCE TEXT of one registry or regulator record and the list of RECORDS the entry may link to.

Rules:
- Use only the SOURCE TEXT. Never add a fact that is not in it. If something is not stated, leave it out or write "no data".
- No advice, no doses, and no claim that a treatment works or harms beyond what a quote supports.
- Do not use regulatory words (approved, cleared, authorised and similar) unless the source is a regulator.
- Neutral, plain English. Explain any technical word in a few plain words.
- tldr: one sentence, at most 30 words.
- summary: 60 to 120 words.
- relations: 1 to 3 links to records in the RECORDS list. Each has a predicate from ALLOWED PREDICATES, the object
  record id, and a quote of fewer than 15 words copied word for word from the SOURCE TEXT that supports the link.
  Quote the source's own sentences; never quote a line label such as "Conditions:" or "Intervention:".

Answer with JSON only, in this shape:
{"tldr": "...", "summary": "...", "relations": [{"predicate": "...", "object": "...", "quote": "..."}]}

ENTRY: {name} ({kind})
ALLOWED PREDICATES: {predicates}
RECORDS:
{records}

SOURCE TEXT:
{source}
