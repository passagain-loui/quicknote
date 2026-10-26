"""Test settings.py — deepcopy, atomic save, .bak fallback, coercion, subscribe"""

import json
import unittest

from src.core import settings as settings_mod
from src.core.constants import MIN_ALPHA
from src.core.settings import DEFAULTS, Settings
from tests.v3.core_base import CoreTestCase


class SettingsTests(CoreTestCase):
    def path(self):
        return settings_mod.SETTINGS_FILE

    def test_defaults_when_no_file(self):
        s = Settings()
        s.load()
        self.assertEqual(s.data, DEFAULTS)
        self.assertEqual(s.get("language"), "th")
        self.assertEqual(s.get("missing", 42), 42)

    def test_hotkeys_deepcopy_isolated_l7(self):
        a, b = Settings(), Settings()
        a.data["hotkeys"]["new_note"] = "<ctrl>+x"
        self.assertEqual(b.data["hotkeys"]["new_note"], DEFAULTS["hotkeys"]["new_note"])
        self.assertEqual(DEFAULTS["hotkeys"]["new_note"], "<ctrl>+<alt>+n")
        a.load()
        a.data["hotkeys"]["toggle_show"] = "zzz"
        self.assertEqual(DEFAULTS["hotkeys"]["toggle_show"], "<ctrl>+<alt>+s")

    def test_save_and_reload_roundtrip_and_bak(self):
        s = Settings()
        s.set("theme", "dark")
        s.set("language", "en")
        self.assertTrue(self.path().exists())
        self.assertFalse(self.path().with_name("settings.json.tmp").exists())
        s2 = Settings()
        s2.load()
        self.assertEqual((s2.get("theme"), s2.get("language")), ("dark", "en"))
        # การ save ครั้งที่สองสร้าง .bak จากไฟล์ก่อนหน้า
        bak = json.loads(self.path().with_name("settings.json.bak").read_text(encoding="utf-8"))
        self.assertEqual(bak["theme"], "dark")

    def test_corrupt_json_falls_back_to_bak(self):
        s = Settings()
        s.set("theme", "dark")
        s.set("alpha", 0.6)  # save ครั้งนี้ทำให้ .bak = {theme: dark, alpha: 1.0}
        self.path().write_text("{ not json", encoding="utf-8")
        s2 = Settings()
        s2.load()
        self.assertEqual(s2.get("theme"), "dark")
        self.assertEqual(s2.get("alpha"), 1.0)

    def test_corrupt_without_bak_uses_defaults(self):
        self.path().write_text("[1, 2", encoding="utf-8")
        s = Settings()
        s.load()
        self.assertEqual(s.data, DEFAULTS)

    def test_save_does_not_overwrite_good_bak_with_corrupt_file(self):
        s = Settings()
        s.set("theme", "dark")
        s.set("language", "en")
        good_bak = self.path().with_name("settings.json.bak").read_text(encoding="utf-8")
        self.path().write_text("garbage", encoding="utf-8")
        s.save()
        self.assertEqual(self.path().with_name("settings.json.bak").read_text(encoding="utf-8"), good_bak)
        s3 = Settings()
        s3.load()
        self.assertEqual(s3.get("language"), "en")

    def test_non_dict_json_treated_as_corrupt(self):
        self.path().write_text("[1, 2, 3]", encoding="utf-8")
        s = Settings()
        s.load()
        self.assertEqual(s.data, DEFAULTS)

    def test_coercion_on_load(self):
        self.path().write_text(json.dumps({
            "alpha": 0.01, "theme": "neon", "language": "fr", "font_size": "huge",
            "snooze_default_minutes": 7, "compact": "maybe", "hotkeys": {"new_note": "<ctrl>+q", "junk": 5},
            "geometry": "", "sound": 0,
        }), encoding="utf-8")
        s = Settings()
        s.load()
        self.assertEqual(s.get("alpha"), MIN_ALPHA)
        self.assertEqual(s.get("theme"), "system")
        self.assertEqual(s.get("language"), "th")
        self.assertEqual(s.get("font_size"), "normal")
        self.assertEqual(s.get("snooze_default_minutes"), 5)
        self.assertEqual(s.get("compact"), False)
        self.assertEqual(s.get("sound"), False)
        self.assertEqual(s.get("geometry"), DEFAULTS["geometry"])
        self.assertEqual(s.get("hotkeys"), {"new_note": "<ctrl>+q", "toggle_show": "<ctrl>+<alt>+s"})

    def test_alpha_clamp_and_garbage(self):
        s = Settings()
        s.set("alpha", 7, save=False)
        self.assertEqual(s.get("alpha"), 1.0)
        s.set("alpha", "0.5", save=False)
        self.assertEqual(s.get("alpha"), 0.5)
        s.set("alpha", "abc", save=False)
        self.assertEqual(s.get("alpha"), 1.0)
        s.set("alpha", -3, save=False)
        self.assertEqual(s.get("alpha"), MIN_ALPHA)

    def test_set_coerces_enum_and_snooze(self):
        s = Settings()
        s.set("theme", "light", save=False)
        s.set("theme", "bogus", save=False)
        self.assertEqual(s.get("theme"), "system")
        s.set("snooze_default_minutes", "15", save=False)
        self.assertEqual(s.get("snooze_default_minutes"), 15)

    def test_set_save_false_does_not_write(self):
        s = Settings()
        s.set("theme", "dark", save=False)
        self.assertFalse(self.path().exists())

    def test_subscribe_fires_once_per_real_change(self):
        s = Settings()
        calls = []
        s.subscribe(lambda k, v: calls.append((k, v)))
        s.set("theme", "dark")
        s.set("theme", "dark")           # ไม่เปลี่ยน → เงียบ
        s.set("alpha", 1.0)              # เท่ากับค่าเดิม → เงียบ
        s.set("theme", "bogus")          # coerce เป็น system → เปลี่ยนจริง
        self.assertEqual(calls, [("theme", "dark"), ("theme", "system")])

    def test_unchanged_set_does_not_save(self):
        s = Settings()
        s.set("theme", "system")
        self.assertFalse(self.path().exists())

    def test_hotkeys_set_notifies_and_isolated(self):
        s = Settings()
        calls = []
        s.subscribe(lambda k, v: calls.append(k))
        hk = {"new_note": "<ctrl>+1", "toggle_show": "<ctrl>+2"}
        s.set("hotkeys", hk)
        hk["new_note"] = "mutated"
        self.assertEqual(s.get("hotkeys")["new_note"], "<ctrl>+1")
        self.assertEqual(calls, ["hotkeys"])

    def test_listener_exception_does_not_break_others(self):
        s = Settings()
        seen = []

        def boom(k, v):
            raise RuntimeError("x")
        s.subscribe(boom)
        s.subscribe(lambda k, v: seen.append(k))
        s.set("sound", False, save=False)
        self.assertEqual(seen, ["sound"])


if __name__ == "__main__":
    unittest.main()
