# kaiwa-data

Language data for [Kaiwa](https://git.arianw.de/shrippen/Kaiwa), the Japanese conversation
trainer: dictionary (JMdict), names (JMnedict), kanji (KANJIDIC2), pitch accents (Kanjium) and the
JLPT word lists of tanos.co.uk in one SQLite file,
`kaiwa-dict.sqlite`. Kaiwa offers it for download only after the learner asks for it and
checks it against the SHA-256 of the release.

The data is CC BY-SA 4.0 (the tanos lists in it are CC BY) (see [NOTICE](NOTICE) and [LICENSE-DATA](LICENSE-DATA)); the build
scripts are MIT ([LICENSE](LICENSE)). Code and data are kept apart this way so the share-alike
terms apply to the data package only (Kaiwa ADR-007).

## Build

```sh
./fetch.sh            # current sources into src/
./package.sh 0.2.0    # dist/kaiwa-data-0.2.0.tar.bz2 and its .sha256
python3 -m unittest discover -s tests -t .
```

Only the Python standard library is needed. A full build takes about half a minute.

## Releases

A tag `v<version>` on Gitea reaches GitHub through the push mirror; GitHub Actions builds the
package from the sources of that day and attaches it to the release, with size, SHA-256 and
the date of each source in the notes.

## Schema (version 2)

| Table | Content |
|---|---|
| `meta` | `schema`, `version`, `licence`, `languages` (`en,de`) |
| `source` | each source with URL, licence, attribution and the date of its file |
| `entry` | one JMdict entry (`id` = `ent_seq`), `common` (news1, ichi1, spec1/2, gai1), `nf` frequency band |
| `form` | spellings: `kind` `k` (kanji) or `r` (reading), JMdict order, `common`, `info` (JSON), `restr` (JSON list of kanji spellings a reading belongs to; `[]` for readings without kanji; NULL for all) |
| `sense` | one sense in one language (`en` or `de`): `pos`, `misc`, `field` as JMdict codes (JSON), `stagk`, `stagr`, `info`, `glosses` (JSON). `pos` is inherited from the previous sense of the same language. German senses are separate from the English ones, as in JMdict, and often have no `pos`. |
| `entity` | JMdict codes (`v1`, `n`, `uk` …) with their English description |
| `accent` | `word`, `reading`, `pattern`: downstep positions in morae, comma-separated (`0` = heiban) |
| `name` | JMnedict: `id`, `kanji` (NULL for kana-only names), `reading`, `types` (JSON codes: `surname`, `given`, `place`, `station` …, described in `entity`), `trans` (first romanisation or translation) |
| `jlpt` | tanos: `word`, `reading`, `level` (5 = N5 … 1 = N1); an estimate by one person, a source for Kaiwa's own level, not an official list |
| `kanji` | `literal`, `grade`, `strokes`, `freq`, `jlpt_old` (the pre-2010 four levels), `onyomi`, `kunyomi`, `meanings` (English) |

Version 2 (0.2.0) added `name` and `jlpt`; the version 1 tables are unchanged.

Lookup: find the entry through `form.text` (index), then its senses in the UI language and,
if there are none, in English (marked as such in the app).
