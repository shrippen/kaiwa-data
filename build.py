#!/usr/bin/env python3
"""Build Kaiwa's language data package (kaiwa-data, ADR-007 in Kaiwa).

Reads JMdict (all languages), JMnedict (names), KANJIDIC2, the Kanjium accent list and the JLPT
word lists of tanos.co.uk (archived pages) and writes one SQLite file that the app opens
read-only. Only the standard library is used, so the build runs anywhere.

    python3 build.py --jmdict JMdict.gz --jmnedict JMnedict.xml.gz --kanjidic kanjidic2.xml.gz \
        --accents accents.txt --tanos src/tanos --out kaiwa-dict.sqlite --version 0.2.0

The schema is described in README.md; `SCHEMA_VERSION` changes whenever a reader has to change.
"""

from __future__ import annotations

import argparse
import gzip
import json
import re
import sqlite3
import sys
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path

SCHEMA_VERSION = 2

# Gloss languages kept: the UI languages of Kaiwa (JMdict codes, ISO 639-2).
LANGS = {"eng": "en", "ger": "de"}

# JMdict priority codes that mark a word as common (as in the EDRDG documentation: news1,
# ichi1, spec1/2, gai1; nf01–nf24 are the halves of news1).
COMMON = {"news1", "ichi1", "spec1", "spec2", "gai1"}

SOURCES = [
    {
        "id": "jmdict",
        "name": "JMdict",
        "url": "https://www.edrdg.org/wiki/index.php/JMdict-EDICT_Dictionary_Project",
        "licence": "CC BY-SA 4.0",
        "attribution": "Electronic Dictionary Research and Development Group (EDRDG)",
    },
    {
        "id": "kanjidic2",
        "name": "KANJIDIC2",
        "url": "https://www.edrdg.org/wiki/index.php/KANJIDIC_Project",
        "licence": "CC BY-SA 4.0",
        "attribution": "Electronic Dictionary Research and Development Group (EDRDG)",
    },
    {
        "id": "jmnedict",
        "name": "JMnedict",
        "url": "https://www.edrdg.org/enamdict/enamdict_doc.html",
        "licence": "CC BY-SA 4.0",
        "attribution": "Electronic Dictionary Research and Development Group (EDRDG)",
    },
    {
        "id": "tanos",
        "name": "JLPT word lists (tanos.co.uk)",
        "url": "https://www.tanos.co.uk/jlpt/sharing/",
        "licence": "CC BY",
        "attribution": "Jonathan Waller, tanos.co.uk",
    },
    {
        "id": "kanjium",
        "name": "Kanjium pitch accents",
        "url": "https://github.com/mifunetoshiro/kanjium",
        "licence": "CC BY-SA 4.0",
        "attribution": "Uros Ozvatic (Kanjium); partly derived from EDRDG data",
    },
]

SCHEMA = """
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE source (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, url TEXT NOT NULL,
    licence TEXT NOT NULL, attribution TEXT NOT NULL, created TEXT
);
-- One JMdict entry; id is its ent_seq.
CREATE TABLE entry (id INTEGER PRIMARY KEY, common INTEGER NOT NULL, nf INTEGER);
-- Kanji and kana spellings of an entry, in JMdict order (ord). kind: 'k' kanji, 'r' reading.
-- restr: for readings, the kanji spellings it belongs to (JSON array) or NULL for all.
CREATE TABLE form (
    entry INTEGER NOT NULL REFERENCES entry(id), kind TEXT NOT NULL, ord INTEGER NOT NULL,
    text TEXT NOT NULL, common INTEGER NOT NULL, info TEXT, restr TEXT
);
CREATE INDEX form_text ON form(text);
CREATE INDEX form_entry ON form(entry);
-- A sense in one language; pos/misc/field are JMdict entity codes (JSON arrays), pos inherited
-- from the previous sense of the same language as JMdict documents it.
CREATE TABLE sense (
    entry INTEGER NOT NULL REFERENCES entry(id), lang TEXT NOT NULL, ord INTEGER NOT NULL,
    pos TEXT NOT NULL, misc TEXT NOT NULL, field TEXT NOT NULL,
    stagk TEXT, stagr TEXT, info TEXT, glosses TEXT NOT NULL
);
CREATE INDEX sense_entry ON sense(entry);
-- JMdict entity codes and their English description.
CREATE TABLE entity (code TEXT PRIMARY KEY, description TEXT NOT NULL);
-- Accent kernels per word and reading (Kanjium): pattern is the comma-separated list of
-- downstep positions in morae (0 = heiban).
CREATE TABLE accent (word TEXT NOT NULL, reading TEXT NOT NULL, pattern TEXT NOT NULL);
CREATE INDEX accent_word ON accent(word);
CREATE INDEX accent_reading ON accent(reading);
-- Names (JMnedict): one row per spelling and reading. kanji is NULL for names written in kana
-- only; types are JMnedict codes (JSON: surname, given, place, station …); trans the first
-- romanisation or translation.
CREATE TABLE name (
    id INTEGER NOT NULL, kanji TEXT, reading TEXT NOT NULL, types TEXT NOT NULL, trans TEXT
);
CREATE INDEX name_kanji ON name(kanji);
CREATE INDEX name_reading ON name(reading);
-- The JLPT level a word has in the tanos lists (5 = N5 … 1 = N1); an estimate by one person,
-- one source among others for Kaiwa's own level (INHALT-ENTWURF 4.2 in Kaiwa).
CREATE TABLE jlpt (word TEXT NOT NULL, reading TEXT NOT NULL, level INTEGER NOT NULL);
CREATE INDEX jlpt_word ON jlpt(word);
CREATE INDEX jlpt_reading ON jlpt(reading);
CREATE TABLE kanji (
    literal TEXT PRIMARY KEY, grade INTEGER, strokes INTEGER, freq INTEGER, jlpt_old INTEGER,
    onyomi TEXT NOT NULL, kunyomi TEXT NOT NULL, meanings TEXT NOT NULL
);
"""

ENTITY_DECL = re.compile(r'<!ENTITY\s+(\S+)\s+"([^"]*)">')
CREATED = re.compile(r"<!--\s*(?:JMdict|JMnedict|Kanjidic2?|kanjidic2?)\s+created:\s*([0-9-]+)\s*-->", re.I)
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"


def open_text(path: Path):
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8")
    return open(path, encoding="utf-8")


def keep_entity_codes(lines, entities: dict, created: list):
    """Rewrite the DTD so that each entity expands to its own code (&n; → "n") and remember
    the descriptions; JMdict's entities otherwise expand to English prose."""
    for line in lines:
        m = ENTITY_DECL.search(line)
        if m and line.lstrip().startswith("<!ENTITY"):
            entities[m.group(1)] = m.group(2)
            line = f'<!ENTITY {m.group(1)} "{m.group(1)}">\n'
        c = CREATED.search(line)
        if c:
            created.append(c.group(1))
        yield line


def iter_elements(path: Path, tag: str, entities: dict, created: list):
    parser = ET.XMLPullParser(events=("end",))
    with open_text(path) as f:
        for line in keep_entity_codes(f, entities, created):
            parser.feed(line)
            for _, el in parser.read_events():
                if el.tag == tag:
                    yield el
                    el.clear()
    parser.close()


def texts(el, tag):
    return [c.text or "" for c in el.findall(tag)]


def nf_rank(pri: list[str]):
    for p in pri:
        if p.startswith("nf"):
            return int(p[2:])
    return None


def load_jmdict(db: sqlite3.Connection, path: Path) -> str | None:
    entities: dict = {}
    created: list = []
    entries = forms = senses = 0
    for e in iter_elements(path, "entry", entities, created):
        seq = int(e.findtext("ent_seq"))
        pri_all: list[str] = []
        rows = []
        for ord_, k in enumerate(e.findall("k_ele")):
            pri = texts(k, "ke_pri")
            pri_all += pri
            info = texts(k, "ke_inf")
            rows.append(("k", ord_, k.findtext("keb"), bool(COMMON & set(pri)),
                         json.dumps(info, ensure_ascii=False) if info else None, None))
        for ord_, r in enumerate(e.findall("r_ele")):
            pri = texts(r, "re_pri")
            pri_all += pri
            info = texts(r, "re_inf")
            restr = texts(r, "re_restr")
            if r.find("re_nokanji") is not None:
                restr = []
            rows.append(("r", ord_, r.findtext("reb"), bool(COMMON & set(pri)),
                         json.dumps(info, ensure_ascii=False) if info else None,
                         json.dumps(restr, ensure_ascii=False) if r.find("re_restr") is not None
                         or r.find("re_nokanji") is not None else None))
        sense_rows = []
        last_pos: dict[str, list[str]] = {}
        ords: dict[str, int] = {}
        for s in e.findall("sense"):
            glosses = s.findall("gloss")
            if not glosses:
                continue
            lang = LANGS.get(glosses[0].get(XML_LANG, "eng"))
            if lang is None:
                continue
            pos = texts(s, "pos") or last_pos.get(lang, [])
            last_pos[lang] = pos
            ord_ = ords.get(lang, 0)
            ords[lang] = ord_ + 1
            stagk = texts(s, "stagk")
            stagr = texts(s, "stagr")
            info = texts(s, "s_inf")
            sense_rows.append((
                lang, ord_, json.dumps(pos), json.dumps(texts(s, "misc")),
                json.dumps(texts(s, "field")),
                json.dumps(stagk, ensure_ascii=False) if stagk else None,
                json.dumps(stagr, ensure_ascii=False) if stagr else None,
                "; ".join(info) if info else None,
                json.dumps([g.text or "" for g in glosses
                            if LANGS.get(g.get(XML_LANG, "eng")) == lang], ensure_ascii=False),
            ))
        if not sense_rows:
            continue
        db.execute("INSERT INTO entry VALUES (?,?,?)",
                   (seq, int(bool(COMMON & set(pri_all))), nf_rank(pri_all)))
        db.executemany("INSERT INTO form VALUES (?,?,?,?,?,?,?)",
                       [(seq, k, o, t, int(c), i, rs) for k, o, t, c, i, rs in rows])
        db.executemany("INSERT INTO sense VALUES (?,?,?,?,?,?,?,?,?,?)",
                       [(seq, *r) for r in sense_rows])
        entries += 1
        forms += len(rows)
        senses += len(sense_rows)
    db.executemany("INSERT OR REPLACE INTO entity VALUES (?,?)", entities.items())
    print(f"JMdict: {entries} entries, {forms} forms, {senses} senses", file=sys.stderr)
    return created[0] if created else None


def load_jmnedict(db: sqlite3.Connection, path: Path) -> str | None:
    entities: dict = {}
    created: list = []
    rows = []
    for e in iter_elements(path, "entry", entities, created):
        seq = int(e.findtext("ent_seq"))
        kanji = [k.findtext("keb") for k in e.findall("k_ele")]
        types: list[str] = []
        trans = None
        for t in e.findall("trans"):
            types += [x for x in texts(t, "name_type") if x not in types]
            if trans is None:
                trans = t.findtext("trans_det")
        for r in e.findall("r_ele"):
            reading = r.findtext("reb")
            restr = texts(r, "re_restr")
            for k in (restr or kanji or [None]):
                rows.append((seq, k, reading, json.dumps(types), trans))
    db.executemany("INSERT INTO name VALUES (?,?,?,?,?)", rows)
    db.executemany("INSERT OR IGNORE INTO entity VALUES (?,?)", entities.items())
    print(f"JMnedict: {len(rows)} names", file=sys.stderr)
    return created[0] if created else None


TANOS_ROW = re.compile(r"<tr>(.*?)</tr>", re.S)
TANOS_CELL = re.compile(r"<td[^>]*>(.*?)</td>", re.S)
KANA = re.compile(r"^[\u3040-\u30ffー]+$")


def tanos_rows(page: str):
    """(word, reading) from a tanos vocabulary page: the cells kanji/kana, reading, English.
    Both cells may hold variants (、 ・ / or spaces: なん/なに, 見る  観る); 〜 is dropped."""
    import html
    for tr in TANOS_ROW.findall(page):
        cells = [html.unescape(re.sub(r"<[^>]+>", "", c)).strip() for c in TANOS_CELL.findall(tr)]
        if len(cells) != 3:
            continue
        word, readings = cells[0].strip("〜～ "), cells[1]
        for reading in re.split(r"[、・,/／\s]+", readings):
            reading = reading.strip("〜～ ")
            if not KANA.match(reading):
                continue
            for w in (re.split(r"[、・,/／\s]+", word) if word else [reading]):
                w = w.strip("〜～ ")
                if w:
                    yield w, reading


def load_tanos(db: sqlite3.Connection, folder: Path):
    """The pages n5.html … n1.html in `folder` (fetch.sh takes them from the web archive)."""
    n = 0
    for level in (5, 4, 3, 2, 1):
        page = (folder / f"n{level}.html").read_text(encoding="utf-8", errors="replace")
        rows = sorted(set(tanos_rows(page)))
        db.executemany("INSERT INTO jlpt VALUES (?,?,?)", [(w, r, level) for w, r in rows])
        n += len(rows)
    print(f"tanos: {n} words", file=sys.stderr)


def kana_key(s: str) -> str:
    """Fullwidth digits and letters in Kanjium's words to their usual form (NFKC)."""
    return unicodedata.normalize("NFKC", s)


def load_accents(db: sqlite3.Connection, path: Path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) != 3 or not parts[2]:
                continue
            word, reading, pattern = parts
            if not re.fullmatch(r"[0-9]+(,[0-9]+)*", pattern):
                continue
            rows.append((kana_key(word), reading or kana_key(word), pattern))
    db.executemany("INSERT INTO accent VALUES (?,?,?)", rows)
    print(f"Kanjium: {len(rows)} accents", file=sys.stderr)


def load_kanjidic(db: sqlite3.Connection, path: Path) -> str | None:
    created: list = []
    n = 0
    for c in iter_elements(path, "character", {}, created):
        misc = c.find("misc")

        def num(tag):
            v = misc.findtext(tag) if misc is not None else None
            return int(v) if v else None

        on, kun, meanings = [], [], []
        for g in c.iterfind("reading_meaning/rmgroup"):
            for r in g.findall("reading"):
                if r.get("r_type") == "ja_on":
                    on.append(r.text)
                elif r.get("r_type") == "ja_kun":
                    kun.append(r.text)
            meanings += [m.text for m in g.findall("meaning") if m.get("m_lang") is None]
        db.execute("INSERT INTO kanji VALUES (?,?,?,?,?,?,?,?)", (
            c.findtext("literal"), num("grade"), num("stroke_count"), num("freq"), num("jlpt"),
            json.dumps(on, ensure_ascii=False), json.dumps(kun, ensure_ascii=False),
            json.dumps(meanings, ensure_ascii=False)))
        n += 1
    print(f"KANJIDIC2: {n} kanji", file=sys.stderr)
    if created:
        return created[0]
    return None


def kanjidic_date(path: Path) -> str | None:
    with open_text(path) as f:
        for _ in range(2000):
            line = f.readline()
            m = re.search(r"<date_of_creation>([0-9-]+)</date_of_creation>", line)
            if m:
                return m.group(1)
    return None


def build(jmdict: Path, kanjidic: Path, accents: Path, out: Path, version: str,
          jmnedict: Path, tanos: Path):
    if out.exists():
        out.unlink()
    db = sqlite3.connect(out)
    db.executescript(SCHEMA)
    created = {
        "jmdict": load_jmdict(db, jmdict),
        "kanjidic2": (load_kanjidic(db, kanjidic) or kanjidic_date(kanjidic)),
        "kanjium": None,
        "jmnedict": load_jmnedict(db, jmnedict),
        "tanos": "2020",
    }
    load_accents(db, accents)
    load_tanos(db, tanos)
    db.executemany("INSERT INTO source VALUES (?,?,?,?,?,?)", [
        (s["id"], s["name"], s["url"], s["licence"], s["attribution"], created[s["id"]])
        for s in SOURCES])
    db.executemany("INSERT INTO meta VALUES (?,?)", [
        ("schema", str(SCHEMA_VERSION)),
        ("version", version),
        ("licence", "CC BY-SA 4.0"),
        ("languages", ",".join(LANGS.values())),
    ])
    db.commit()
    db.execute("VACUUM")
    db.close()


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--jmdict", type=Path, required=True)
    p.add_argument("--jmnedict", type=Path, required=True)
    p.add_argument("--kanjidic", type=Path, required=True)
    p.add_argument("--accents", type=Path, required=True)
    p.add_argument("--tanos", type=Path, required=True, help="folder with n5.html … n1.html")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--version", required=True)
    a = p.parse_args(argv)
    build(a.jmdict, a.kanjidic, a.accents, a.out, a.version, a.jmnedict, a.tanos)


if __name__ == "__main__":
    main()
