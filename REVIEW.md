# Review guide

Every PR is reviewed before it is merged (rule in `agent.md`): by PR-Agent
(owner, 22.10.2026); a new Claude agent checks the **Wichtig** of earlier
rounds, and reviews when PR-Agent fails. The
reviewer knows nothing of the session that wrote the change: it gets the
PR's intent, its diff and the repository, and this file. The owner does not read code; this review is the second reader.

## What failure looks like here

kaiwa-data builds the SQLite file Kaiwa opens read-only for its
dictionary, names, kanji, accents and JLPT levels. A bug here reaches every
learner who downloads the package:

- **Wrong or lost data:** entries, spellings, readings, senses, names,
  kanji or accents dropped or attached to the wrong entry while parsing
  (`restr`, `stagk`/`stagr`, inherited `pos`), a German sense mixed into
  the English ones, encoding or NFKC normalisation that changes a word.
- **Breaks Kaiwa's reader:** a table or column renamed, removed or changed
  in meaning without a raised `SCHEMA_VERSION` in `build.py` and the
  schema table in `README.md`.
- **Breaks the licence:** data or fixtures without their attribution in
  `NOTICE`, the CC BY-SA data mixed into the MIT code, a new source
  without its licence.
- **Breaks the release:** a package or SHA-256 that does not match what
  `package.sh` built, release artefacts built or attached outside GitHub
  Actions.
- **Lies:** README, NOTICE or comments that say something the code does
  not do.

## What to check in particular

- Parser changes have a test on an excerpt in `tests/fixtures`; the tests
  run with `python3 -m unittest discover -s tests -t .`.
- A schema change raises `SCHEMA_VERSION` and updates the table in
  `README.md` (Kaiwa's reader follows it).
- Only the Python standard library.
- Bug fixes: does the fix remove the cause, with a test that failed
  before?

## What the owner confirms here

"What is published" (rule in `agent.md`) means here: a release (a tag
`v<version>`, which GitHub builds and attaches as the data package) and
any change to `package.sh` or the release workflow.

## Skip

- `tests/fixtures/` contents (check only that they are excerpts of the real
  sources with their attribution), `src/`, `dist/`.

## How to report

- Every finding names file and line and the concrete input or state that
  goes wrong. No guess without evidence; if unsure, say so.
- Each finding gets one label: **Wichtig** (a bug from the list above,
  must be fixed or answered before the merge), **Kleinigkeit** (optional,
  at most five) or **Bestand** (the bug was there before this PR; not
  blocking).
- The report starts with the count, e.g. "2 Wichtig, 1 Kleinigkeit" (the
  session puts the heading above it). The count of **Wichtig** holds every
  one still open, also from an earlier round, e.g. "1 Wichtig (offen aus
  Runde 1)". Only when none is open it says plainly: "Nichts zu beheben."
- In a later round: say for each open **Wichtig** of the last round whether
  it is fixed, or whether its answer is accepted, with the reason. PR-Agent
  sees no earlier round: it reports only its own findings with their labels,
  and a new Claude agent closes the open ones (`agent.md`).
- Findings in German, code names as they are.
