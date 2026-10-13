"""Tests for build.py on small excerpts of the real sources (tests/fixtures)."""

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import build

FIX = Path(__file__).parent / "fixtures"


class BuildTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        out = Path(cls.tmp.name) / "kaiwa-dict.sqlite"
        build.build(FIX / "JMdict.xml", FIX / "kanjidic2.xml", FIX / "accents.txt", out, "9.9.9")
        cls.db = sqlite3.connect(out)

    @classmethod
    def tearDownClass(cls):
        cls.db.close()
        cls.tmp.cleanup()

    def q(self, sql, *args):
        return self.db.execute(sql, args).fetchall()

    def test_meta_names_schema_version_and_licence(self):
        meta = dict(self.q("SELECT key, value FROM meta"))
        self.assertEqual(meta["schema"], str(build.SCHEMA_VERSION))
        self.assertEqual(meta["version"], "9.9.9")
        self.assertEqual(meta["licence"], "CC BY-SA 4.0")
        self.assertEqual(meta["languages"], "en,de")

    def test_every_source_has_licence_and_attribution(self):
        rows = self.q("SELECT id, licence, attribution FROM source ORDER BY id")
        self.assertEqual([r[0] for r in rows], ["jmdict", "kanjidic2", "kanjium"])
        for _, licence, attribution in rows:
            self.assertEqual(licence, "CC BY-SA 4.0")
            self.assertTrue(attribution)
        created = dict(self.q("SELECT id, created FROM source"))
        self.assertRegex(created["jmdict"], r"^\d{4}-\d{2}-\d{2}$")

    def test_pos_keeps_entity_codes(self):
        [(pos,)] = self.q(
            "SELECT s.pos FROM sense s JOIN form f ON f.entry = s.entry "
            "WHERE f.text = '食べる' AND s.lang = 'en' AND s.ord = 0")
        self.assertEqual(json.loads(pos), ["v1", "vt"])
        [(desc,)] = self.q("SELECT description FROM entity WHERE code = 'v1'")
        self.assertIn("Ichidan", desc)

    def test_german_glosses_kept_other_languages_dropped(self):
        langs = {r[0] for r in self.q("SELECT DISTINCT lang FROM sense")}
        self.assertEqual(langs, {"en", "de"})
        de = self.q("SELECT s.glosses FROM sense s JOIN form f ON f.entry = s.entry "
                    "WHERE f.text = '食べる' AND s.lang = 'de' ORDER BY s.ord")
        self.assertIn("essen", json.loads(de[0][0]))

    def test_pos_is_inherited_by_later_senses(self):
        for (pos,) in self.q("SELECT pos FROM sense WHERE lang = 'en'"):
            self.assertNotEqual(json.loads(pos), [])

    def test_common_flag_and_reading_restriction(self):
        [(common,)] = self.q("SELECT e.common FROM entry e JOIN form f ON f.entry = e.id "
                             "WHERE f.text = 'そよ風'")
        self.assertEqual(common, 1)
        [(restr,)] = self.q("SELECT restr FROM form WHERE text = 'びふう'")
        self.assertEqual(json.loads(restr), ["微風"])
        [(restr,)] = self.q("SELECT restr FROM form WHERE text = 'そよかぜ'")
        self.assertIsNone(restr)

    def test_reading_without_kanji_has_empty_restriction(self):
        rows = self.q("SELECT f.text, f.restr FROM form f WHERE f.entry = 1003430 AND kind = 'r'")
        restrs = {t: r for t, r in rows}
        self.assertIn("[]", restrs.values())

    def test_accents_skip_bad_lines_and_normalise_digits(self):
        self.assertEqual(self.q("SELECT pattern FROM accent WHERE word = '食べる'"), [("2",)])
        self.assertEqual(self.q("SELECT pattern FROM accent WHERE word = '10月'"), [("4,0",)])
        self.assertEqual(self.q("SELECT count(*) FROM accent WHERE word = 'bad'"), [(0,)])
        self.assertEqual(sorted(self.q("SELECT reading, pattern FROM accent WHERE word = '明白'")),
                         [("あからさま", "0,3"), ("めいはく", "0")])

    def test_kanji_readings_and_english_meanings(self):
        [(grade, strokes, on, kun, meanings)] = self.q(
            "SELECT grade, strokes, onyomi, kunyomi, meanings FROM kanji WHERE literal = '食'")
        self.assertEqual((grade, strokes), (2, 9))
        self.assertIn("ショク", json.loads(on))
        self.assertIn("た.べる", json.loads(kun))
        self.assertEqual(json.loads(meanings), ["eat", "food"])


if __name__ == "__main__":
    unittest.main()
