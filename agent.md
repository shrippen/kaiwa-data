# Working rules for this repository

kaiwa-data builds the language data package of Kaiwa (`shrippen/Kaiwa`, ADR-007, /LD050/):
JMdict, KANJIDIC2 and Kanjium accents as one SQLite file.

- Code (build.py, scripts, tests) is MIT, the package and the fixtures are CC BY-SA 4.0 (NOTICE).
- Run `python3 -m unittest discover -s tests -t .` before every commit.
- A change Kaiwa's reader must follow raises `SCHEMA_VERSION` in build.py and the table in README.md.
- This repository lives on Gitea (`git.arianw.de`); GitHub is its push mirror. Work on a branch,
  open a PR on Gitea, merge there after green CI.
- Releases: push a tag `v<version>` on Gitea. The mirror carries it to GitHub, where
  `.github/workflows/release.yml` builds the package and attaches it with its SHA-256. The Gitea
  release gets the tag and notes only. After a release, pin size and SHA-256 in Kaiwa
  (`kaiwa_speech::download`).
