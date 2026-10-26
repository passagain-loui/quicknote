"""Tests ของหน้าต่างหลัก (Board + NoteCard) — Tk จริง, DB/settings ชั่วคราว, toast จำลอง

ครอบคลุม regression ของ BUG_REPORT: C2 C4 C5 C7 C8 H2 H4 H5 H9 H11 M1 M2 M22 + flow ของ alarm
"""

import sys
import tkinter as tk
import tkinter.font as tkfont
import types
import unicodedata
import unittest
from datetime import datetime, timedelta
from tkinter import messagebox
from unittest import mock

from src.core import database as db
from src.core.models import Note
from src.core.reminders import FMT
from src.ui import strings
from src.ui.board import clamp_geometry, parse_geometry
from src.ui.note_card import ellipsize
from src.ui.strings import t
from src.ui.widgets import px
from tests.v3.board_base import BoardTestCase, start_shared_root, stop_shared_root


def setUpModule() -> None:
    start_shared_root()


def tearDownModule() -> None:
    stop_shared_root()


def at(delta_min: float) -> str:
    return (datetime.now() + timedelta(minutes=delta_min)).strftime(FMT)


class GeometryTest(unittest.TestCase):
    def test_parse(self) -> None:
        self.assertEqual(parse_geometry("380x600+120+120"), (380, 600, 120, 120))
        self.assertEqual(parse_geometry("380x600+-8+-8"), (380, 600, -8, -8))  # Tk คืนติดลบเป็น +-8
        self.assertIsNone(parse_geometry("junk"))

    def test_c4_clamp_onto_virtual_screen(self) -> None:
        # จอรอง (ซ้าย) ถูกถอด → หน้าต่างที่เคยอยู่ x=-1500 ต้องกลับเข้าจอ
        self.assertEqual(clamp_geometry("380x600+-1500+50", 0, 0, 1920, 1080, 300, 360), "380x600+0+50")
        self.assertEqual(clamp_geometry("380x600+5000+5000", 0, 0, 1920, 1080, 300, 360), "380x600+1540+480")
        # ใหญ่เกินจอ → ย่อ ; เล็กกว่า minsize → ขยาย
        self.assertEqual(clamp_geometry("4000x4000+0+0", 0, 0, 1920, 1080, 300, 360), "1920x1080+0+0")
        self.assertEqual(clamp_geometry("100x100+10+10", 0, 0, 1920, 1080, 300, 360), "300x360+10+10")
        # virtual screen ที่เริ่มติดลบ (จอรองด้านซ้าย)
        self.assertEqual(clamp_geometry("380x600+-1900+10", -1920, 0, 3840, 1080, 300, 360), "380x600+-1900+10")
        self.assertEqual(clamp_geometry("garbage", 0, 0, 1920, 1080, 300, 360), "380x600+120+120")


class EllipsizeTest(BoardTestCase):
    def test_thai_never_cut_before_combining_mark(self) -> None:
        font = tkfont.Font(root=self.root, family="Leelawadee UI", size=10)
        text = "ผู้ใหญ่ที่ปรึกษาปั้นจั่นเกี่ยวกับเรื่องนี้เป็นอย่างไรก็ได้"
        for width in range(20, font.measure(text), 7):
            out = ellipsize(text, font, width)
            self.assertTrue(out.endswith("…"))
            kept = out[:-1]
            self.assertTrue(text.startswith(kept))
            if len(kept) < len(text):
                self.assertNotEqual(unicodedata.category(text[len(kept)]), "Mn", (width, out))
                self.assertNotIn(kept[-1:], tuple("เแโใไ"))
            self.assertLessEqual(font.measure(out), width)

    def test_short_text_untouched(self) -> None:
        font = tkfont.Font(root=self.root, size=10)
        self.assertEqual(ellipsize("abc", font, 500), "abc")
        self.assertEqual(ellipsize("abc", font, 0), "")


class WindowTest(BoardTestCase):
    def test_native_frame_and_title(self) -> None:
        self.assertEqual(self.root.title(), "QuickNote")
        self.assertFalse(self.root.overrideredirect())
        self.assertGreaterEqual(self.root.minsize()[0], px(self.root, 300))

    def test_geometry_roundtrip_is_dpi_independent(self) -> None:
        geo = self.board.get_persistable_geometry()
        w, h, _, _ = parse_geometry(geo)
        self.assertEqual((w, h), (380, 600))  # หน่วย 96 DPI แม้เครื่องนี้ scale อยู่
        self.assertEqual(self.root.winfo_width(), round(380 * self.board._scale()))

    def test_h2_topmost_follows_setting_only(self) -> None:
        self.settings.set("always_on_top", False)
        self.assertFalse(self.root.attributes("-topmost"))
        self.board._reapply_topmost()
        self.assertFalse(self.root.attributes("-topmost"), "ผู้ใช้ปิด always_on_top แล้วห้ามถูกดันกลับ")
        self.settings.set("always_on_top", True)
        self.assertTrue(self.root.attributes("-topmost"))
        self.assertTrue(self.board._tb_topmost.active)

    def test_h2_not_reapplied_over_open_dialog(self) -> None:
        self.root.attributes("-topmost", False)
        dlg = tk.Toplevel(self.root)
        self.pump()
        self.assertTrue(dlg.winfo_viewable())
        self.board._reapply_topmost()
        self.assertFalse(self.root.attributes("-topmost"))
        dlg.destroy()
        self.pump()
        self.board._reapply_topmost()
        self.assertTrue(self.root.attributes("-topmost"))

    def test_topmost_reapply_keeps_single_job(self) -> None:
        for _ in range(5):
            self.board._reapply_topmost()
        jobs = [j for j in self.root.tk.splitlist(self.root.tk.call("after", "info"))
                if "_reapply_topmost" in str(self.root.tk.call("after", "info", j)[0])]
        self.assertEqual(len(jobs), 1)

    def test_alpha_live(self) -> None:
        self.settings.set("alpha", 0.5)
        self.assertAlmostEqual(float(self.root.attributes("-alpha")), 0.5, places=1)

    def test_m22_toggle_visibility(self) -> None:
        self.board.hide()
        self.pump()
        self.assertFalse(self.root.winfo_viewable())
        self.board.toggle_visibility()  # ซ่อนอยู่ → แสดง
        self.pump()
        self.assertTrue(self.root.winfo_viewable())
        had_focus = self.root.focus_displayof() is not None
        self.board.toggle_visibility()
        self.pump()
        # มองเห็นแต่ไม่มี focus (ถูกบัง) ต้องดึงขึ้นมาไม่ใช่ซ่อน — ถ้ามี focus จริงถึงจะซ่อน
        self.assertEqual(self.root.winfo_viewable(), not had_focus)

    def test_hide_flushes_pending_title(self) -> None:
        nid = db.create_note("old", collapsed=False)
        self.board._load_notes()
        self.card(nid)._title_var.set("typed then hidden")
        self.board.hide()
        self.assertEqual(db.get_note(nid)["title"], "typed then hidden")

    def test_open_settings_singleton(self) -> None:
        created: list = []

        class FakeSettingsWindow:
            def __init__(self, root, settings, theme, actions, on_close):
                self.on_close, self.lifted = on_close, 0
                created.append(self)

            def lift(self):
                self.lifted += 1

        fake = types.ModuleType("src.ui.settings_window")
        fake.SettingsWindow = FakeSettingsWindow
        fake.make_default_actions = lambda root, on_restored: ("actions", on_restored)
        with mock.patch.dict(sys.modules, {"src.ui.settings_window": fake}):
            self.board.open_settings()
            self.board.open_settings()
            self.assertEqual(len(created), 1)
            self.assertEqual(created[0].lifted, 1)
            created[0].on_close()
            self.board.open_settings()
            self.assertEqual(len(created), 2)


class ListOrderTest(BoardTestCase):
    def test_c5_pin_bottom_card_goes_first_then_back(self) -> None:
        a = self.make("a", created="2026-01-03T10:00:00")
        b = self.make("b", created="2026-01-02T10:00:00")
        c = self.make("c", created="2026-01-01T10:00:00")
        self.board._load_notes()
        self.assertEqual(self.pack_order(), [a, b, c])
        self.card(c)._toggle_pin()
        self.pump()
        self.assertEqual(self.pack_order(), [c, a, b])
        self.assertIs(self.board._inner.pack_slaves()[0], self.card(c))
        self.card(c)._toggle_pin()
        self.pump()
        self.assertEqual(self.pack_order(), [a, b, c])

    def test_new_note_position_follows_sql_order_including_priority(self) -> None:
        hi = self.make("urgent", created="2026-01-01T10:00:00", priority="high")
        old = self.make("old", created="2026-01-02T10:00:00")
        self.board._load_notes()
        self.board._qa.set_value("new one")
        self.board._quick_add(False)
        self.pump()
        new = next(i for i in self.board.note_cards if i not in (hi, old))
        self.assertEqual(self.pack_order(), [hi, new, old])
        self.assertEqual(self.pack_order(), self.ids())

    def test_priority_change_reorders(self) -> None:
        a = self.make("a", created="2026-01-03T10:00:00")
        b = self.make("b", created="2026-01-01T10:00:00")
        self.board._load_notes()
        self.card(b).callbacks.on_priority(b, "high")
        self.assertEqual(db.get_note(b)["priority"], "high")  # C1: บันทึกจริง
        self.assertEqual(self.pack_order(), [b, a])

    def test_h9_search_survives_refresh_and_keeps_order(self) -> None:
        a = self.make("apple pie", created="2026-01-01T10:00:00")
        b = self.make("banana", created="2026-01-02T10:00:00")
        c = self.make("apricot", created="2026-01-03T10:00:00")
        self.board._load_notes()
        self.board._search.set_value("ap")
        self.pump(0.3)
        self.assertEqual(self.pack_order(), [c, a])
        self.board._load_notes()
        self.board.refresh()
        self.pump(0.3)
        self.assertEqual(self.board._search.get_value(), "ap")
        self.assertEqual(self.pack_order(), [c, a])
        db.update_fields(b, is_pinned=True)  # pin banana (ไม่ตรงคำค้น) ไม่ทำให้ลำดับของที่เหลือเพี้ยน
        self.board._load_notes()
        self.assertEqual(self.pack_order(), [c, a])
        self.board._search.clear()
        self.pump(0.3)
        self.assertEqual(self.pack_order(), [b, c, a])

    def test_search_matches_content_and_clear_via_escape(self) -> None:
        a = self.make("alpha")
        self.make("beta")
        db.update_fields(a, content="needle inside")
        self.board._load_notes()
        self.board._search.set_value("NEEDLE")
        self.pump(0.3)
        self.assertEqual(self.pack_order(), [a])
        self.board._on_escape()
        self.pump(0.3)
        self.assertEqual(self.board._search.get_value(), "")
        self.assertEqual(len(self.pack_order()), 2)

    def test_refresh_debounced_into_single_load(self) -> None:
        for _ in range(5):
            self.board.refresh()
        self.assertIsNotNone(self.board._refresh_job)
        db.create_note("late arrival")
        self.pump(0.4)
        self.assertIsNone(self.board._refresh_job)
        self.assertEqual(len(self.board.note_cards), 1)

    def test_tab_counts_and_switch(self) -> None:
        a = self.make("a")
        self.make("b")
        db.set_status(a, "completed")
        self.board._load_notes()
        self.assertEqual(self.board._tabs["active"][0].cget("text"), t("board.tab_active", n=1))
        self.assertEqual(self.board._tabs["completed"][0].cget("text"), t("board.tab_completed", n=1))
        self.board._select_tab("completed")
        self.pump()
        self.assertEqual(self.pack_order(), [a])
        self.assertFalse(self.board._qa_wrap.winfo_manager(), "quick-add มีเฉพาะแท็บ active")
        self.board._select_tab("active")
        self.assertTrue(self.board._qa_wrap.winfo_manager())


class EmptyStateTest(BoardTestCase):
    def labels_with(self, text: str) -> list[tk.Label]:
        found: list[tk.Label] = []

        def walk(w: tk.Misc) -> None:
            for ch in w.winfo_children():
                if isinstance(ch, tk.Label) and ch.cget("text") == text:
                    found.append(ch)
                walk(ch)
        walk(self.root)
        return found

    def test_m1_exactly_one_empty_state_on_startup(self) -> None:
        self.assertEqual(len(self.labels_with(t("board.empty_title"))), 1)
        self.assertTrue(self.board._empty.winfo_ismapped())
        self.board._load_notes()
        self.board._load_notes()
        self.assertEqual(len(self.labels_with(t("board.empty_title"))), 1)

    def test_m2_empty_state_after_deleting_last_note(self) -> None:
        nid = db.create_note("only")
        self.board._load_notes()
        self.pump()
        self.assertFalse(self.board._empty.winfo_ismapped())
        self.board._on_delete(nid)
        self.pump()
        self.assertTrue(self.board._empty.winfo_ismapped())
        self.assertEqual(len(self.labels_with(t("board.empty_title"))), 1)

    def test_empty_state_after_completing_last_note(self) -> None:
        nid = db.create_note("only")
        self.board._load_notes()
        self.board._on_toggle_complete(nid)
        self.pump(0.5)
        self.assertTrue(self.board._empty.winfo_ismapped())

    def test_variants(self) -> None:
        self.assertEqual(self.board._empty_mode, "active")
        self.board._select_tab("completed")
        self.assertEqual(self.board._empty_mode, "completed")
        self.assertEqual(self.board._empty_title.cget("text"), t("board.empty_completed"))
        self.board._select_tab("active")
        self.board._search.set_value("zzz")
        self.pump(0.3)
        self.assertEqual(self.board._empty_mode, "search")
        self.assertIn("zzz", self.board._empty_title.cget("text"))
        self.assertTrue(self.board._empty_link.winfo_ismapped())
        self.board._empty_link.invoke()  # "ล้างการค้นหา"
        self.pump(0.3)
        self.assertEqual(self.board._search.get_value(), "")
        self.assertEqual(self.board._empty_mode, "active")


class QuickAddTest(BoardTestCase):
    def test_enter_creates_collapsed_and_keeps_entry_ready(self) -> None:
        self.board._qa.focus_force()
        self.board._qa.set_value("buy milk")
        self.board._quick_add(False)
        self.pump()
        rows = db.get_notes_by_status("active")
        self.assertEqual([r["title"] for r in rows], ["buy milk"])
        self.assertEqual(rows[0]["collapsed"], 1)
        self.assertFalse(self.card(rows[0]["id"]).expanded)
        self.assertEqual(self.board._qa.get_value(), "")
        self.board._qa.set_value("second")
        self.board._quick_add(False)
        self.assertEqual(len(db.get_notes_by_status("active")), 2)

    def test_shift_enter_creates_expanded_and_collapses_previous(self) -> None:
        first = db.create_note("first", collapsed=False)
        self.board._load_notes()
        self.assertTrue(self.card(first).expanded)
        self.board._qa.set_value("with details")
        self.board._quick_add(True)
        self.pump()
        new = next(i for i in self.board.note_cards if i != first)
        self.assertTrue(self.card(new).expanded)
        self.assertFalse(self.card(first).expanded)
        self.assertEqual(db.get_note(new)["collapsed"], 0)
        self.assertEqual(db.get_note(first)["collapsed"], 1)

    def test_empty_enter_does_nothing(self) -> None:
        self.board._quick_add(False)
        self.board._qa.set_value("   ")
        self.board._quick_add(True)
        self.assertEqual(db.get_notes_by_status("active"), [])

    def test_not_on_completed_tab(self) -> None:
        self.board._select_tab("completed")
        self.board._qa.set_value("nope")
        self.board._quick_add(False)
        self.assertEqual(db.get_notes_by_status("active"), [])

    def test_real_key_binding(self) -> None:
        self.board._qa.focus_force()
        self.pump()
        self.board._qa.set_value("via key")
        self.board._qa.event_generate("<Return>")
        self.pump()
        self.assertEqual([r["title"] for r in db.get_notes_by_status("active")], ["via key"])

    def test_creating_while_searching_clears_search(self) -> None:
        self.make("zebra")
        self.board._load_notes()
        self.board._search.set_value("zebra")
        self.pump(0.3)
        self.board._qa.set_value("new")
        self.board._quick_add(False)
        self.pump(0.3)
        self.assertEqual(self.board._search.get_value(), "")
        self.assertEqual(len(self.pack_order()), 2)


class CardTest(BoardTestCase):
    def test_collapsed_card_height_and_seven_cards_fit(self) -> None:
        for i in range(9):
            self.make(f"note {i}", created=f"2026-01-{i + 1:02d}T10:00:00")
        self.board._load_notes()
        self.pump(0.2)
        cards = self.board._visible_cards()
        self.assertTrue(all(c.winfo_height() <= px(self.root, 56) for c in cards))
        view_h = self.board._canvas.winfo_height()
        fully_visible = [c for c in cards if c.winfo_y() + c.winfo_height() <= view_h]
        self.assertGreaterEqual(len(fully_visible), 7)

    def test_compact_card_is_short_and_title_only(self) -> None:
        nid = self.make("compact", priority="high")
        db.update_fields(nid, priority="high")
        self.board._load_notes()
        self.pump()
        normal = self.card(nid).winfo_height()
        self.settings.set("compact", True)
        self.pump()
        self.assertLess(self.card(nid).winfo_height(), normal)
        self.assertLessEqual(self.card(nid).winfo_height(), px(self.root, 40))
        self.assertFalse(self.card(nid)._meta.winfo_ismapped())

    def test_c7_type_then_collapse_immediately_saves(self) -> None:
        nid = db.create_note("t", collapsed=False)
        self.board._load_notes()
        card = self.card(nid)
        card._text.insert("1.0", "ตัวอักษรสุดท้ายห้ามหาย")
        self.pump()
        card.collapse()  # ไม่รอ debounce 500ms
        self.assertEqual(db.get_note(nid)["content"], "ตัวอักษรสุดท้ายห้ามหาย")
        self.assertEqual(db.get_note(nid)["collapsed"], 1)
        self.pump(0.7)  # timer ที่ค้างต้องไม่ทำให้เกิด exception (errors ถูกตรวจใน tearDown)

    def test_c8_flush_all_saves_pending_title_and_content(self) -> None:
        nid = db.create_note("old title", collapsed=False)
        self.board._load_notes()
        card = self.card(nid)
        card._title_var.set("fresh title")
        card._text.insert("1.0", "body")
        self.pump()
        self.board.flush_all_cards()
        row = db.get_note(nid)
        self.assertEqual((row["title"], row["content"]), ("fresh title", "body"))

    def test_debounce_saves_after_500ms_once(self) -> None:
        nid = db.create_note("t", collapsed=False)
        self.board._load_notes()
        saves: list[dict] = []
        original = self.board._callbacks.on_save
        self.board._callbacks.on_save = lambda i, ch: (saves.append(ch), original(i, ch))
        card = self.card(nid)
        for ch in "abc":
            card._text.insert("end", ch)
            self.pump(0.05)
        self.assertEqual(saves, [])
        self.pump(0.7)
        self.assertEqual(saves, [{"content": "abc"}])
        self.assertEqual(db.get_note(nid)["content"], "abc")

    def test_m19_empty_title_reverts(self) -> None:
        nid = db.create_note("keep me", collapsed=False)
        self.board._load_notes()
        card = self.card(nid)
        card._title_var.set("")
        card.flush_pending()
        self.assertEqual(card._title_var.get(), "keep me")
        self.assertEqual(db.get_note(nid)["title"], "keep me")

    def test_h5_refresh_from_updates_every_widget(self) -> None:
        nid = db.create_note("before", "first line\nsecond")
        self.board._load_notes()
        card = self.card(nid)
        self.pump()
        db.update_fields(nid, title="after", is_pinned=True, priority="high", color="green")
        db.set_reminder(nid, at(120))
        self.board._load_notes()
        self.pump()
        self.assertIs(self.card(nid), card)  # reuse ไม่ได้สร้างใหม่
        self.assertEqual(card._title.cget("text"), "after")
        self.assertTrue(card._pin.winfo_ismapped())
        self.assertIn(t("priority.high"), card._m_prio.cget("text"))
        self.assertIn(strings.t("card.when_today", hm="")[:0] or ":", card._m_time.cget("text"))
        self.assertEqual(card._bg_spec, self.theme.note_bg("green"))
        # ดัง → ขอบแดง 2px + chips
        db.mark_ringing(nid)
        self.board._load_notes()
        self.assertEqual((card._border_spec, card._bw), ("critical", 2))
        self.assertTrue(card._chip_row.winfo_children())
        db.dismiss_reminder(nid)
        self.board._load_notes()
        self.assertEqual((card._border_spec, card._bw), ("stroke", 1))
        self.assertFalse(card._chip_row.winfo_children())

    def test_h4_collapsed_state_persists_across_rebuild(self) -> None:
        a = db.create_note("a")
        b = db.create_note("b")
        self.board._load_notes()
        self.board._on_request_expand(a)
        self.assertEqual(db.get_note(a)["collapsed"], 0)
        self.board.rebuild()
        self.assertTrue(self.card(a).expanded)
        self.assertFalse(self.card(b).expanded)

    def test_h4_refresh_does_not_reset_user_expanded_card(self) -> None:
        a = db.create_note("a")
        self.board._load_notes()
        self.board._on_request_expand(a)
        for _ in range(3):  # alarm/dismiss/pin ของใบอื่นทำให้ refresh หลายรอบ
            self.board._load_notes()
        self.assertTrue(self.card(a).expanded)

    def test_refresh_does_not_clobber_text_being_typed(self) -> None:
        nid = db.create_note("t", "stored", collapsed=False)
        self.board._load_notes()
        card = self.card(nid)
        card._text.insert("end", " + typing")
        self.pump()
        self.board._load_notes()  # DB ยังเป็น "stored" แต่ผู้ใช้กำลังพิมพ์
        self.assertEqual(card._text.get("1.0", "end-1c"), "stored + typing")
        self.board.flush_all_cards()
        self.assertEqual(db.get_note(nid)["content"], "stored + typing")

    def test_only_one_card_expanded(self) -> None:
        a, b = db.create_note("a"), db.create_note("b")
        self.board._load_notes()
        self.board._on_request_expand(a)
        self.card(a)._text.insert("1.0", "unsaved in a")
        self.board._on_request_expand(b)
        self.assertFalse(self.card(a).expanded)
        self.assertTrue(self.card(b).expanded)
        self.assertEqual(db.get_note(a)["content"], "unsaved in a")  # flush ก่อนพับ
        self.assertEqual([i for i, c in self.board.note_cards.items() if c.expanded], [b])

    def test_db_with_multiple_expanded_rows_keeps_only_first(self) -> None:
        a = self.make("a", created="2026-01-02T10:00:00", collapsed=False)
        b = self.make("b", created="2026-01-01T10:00:00", collapsed=False)
        self.board._load_notes()
        self.assertEqual([i for i, c in self.board.note_cards.items() if c.expanded], [a])
        self.assertEqual(db.get_note(b)["collapsed"], 1)

    def test_content_order_header_content_chips(self) -> None:
        nid = db.create_note("t", collapsed=False)
        db.set_reminder(nid, at(60))
        self.board._load_notes()
        card = self.card(nid)
        order = [w for w in card.body.pack_slaves()]
        self.assertEqual(order, [card._top, card._content_wrap, card._chips])
        card.collapse()
        card.expand()
        self.assertEqual(card.body.pack_slaves(), [card._top, card._content_wrap, card._chips])

    def test_meta_line_content_and_overdue_color(self) -> None:
        nid = db.create_note("t", "สรุปประชุม\nบรรทัดสอง")
        db.set_reminder(nid, at(-30))  # เลยเวลา (scheduler หยุดอยู่ จึงยังไม่ดัง)
        db.update_fields(nid, priority="medium")
        self.board._load_notes()
        self.pump()
        card = self.card(nid)
        self.assertTrue(card._meta.winfo_ismapped())
        self.assertIn("เลยกำหนด", card._m_time.cget("text"))
        self.assertEqual(card._m_time.cget("fg"), self.theme.c("critical"))
        self.assertEqual(card._m_text.cget("text"), "สรุปประชุม")
        self.assertIn(t("priority.medium"), card._m_prio.cget("text"))

    def test_meta_hidden_when_no_data(self) -> None:
        nid = db.create_note("plain")
        self.board._load_notes()
        self.pump()
        self.assertFalse(self.card(nid)._meta.winfo_ismapped())

    def test_completed_card_style_and_restore(self) -> None:
        nid = db.create_note("done thing")
        db.set_status(nid, "completed")
        self.board._select_tab("completed")
        self.pump()
        card = self.card(nid)
        self.assertEqual(str(card._title.cget("fg")), self.theme.c("text_secondary"))
        self.assertTrue(card._title_font.cget("overstrike"))
        self.assertIn("เสร็จเมื่อ", card._m_text.cget("text"))
        self.assertTrue(card._check._done)
        card._toggle_complete()
        self.pump(0.5)
        self.assertEqual(db.get_note(nid)["status"], "active")
        self.assertIsNone(db.get_note(nid)["completed_at"])

    def test_hover_buttons_no_flicker_inside_card(self) -> None:
        nid = db.create_note("hover")
        self.board._load_notes()
        self.pump()
        card = self.card(nid)
        self.assertFalse(card._actions.winfo_manager())
        card._on_enter()
        self.assertTrue(card._actions.winfo_manager())
        # ตำแหน่งเมาส์จริงทดสอบไม่ได้ (ขึ้นกับหน้าต่างอื่นบนจอ) → ปลอมเฉพาะผลของ is_pointer_inside
        # <Leave> ที่ยิงตอนย้ายเข้าลูก: เมาส์ยังอยู่ใน card → ปุ่มต้องไม่หาย
        with mock.patch("src.ui.note_card.is_pointer_inside", return_value=True):
            card._on_leave()
        self.assertTrue(card._hover)
        with mock.patch("src.ui.note_card.is_pointer_inside", return_value=False):
            card._on_leave()
        self.assertFalse(card._hover)
        self.assertFalse(card._actions.winfo_manager())

    def test_context_menu_structure(self) -> None:
        nid = db.create_note("menu")
        self.board._load_notes()
        card = self.card(nid)
        card._build_menu()
        m = card._menu
        labels = [m.entrycget(i, "label") for i in range(m.index("end") + 1) if m.type(i) != "separator"]
        self.assertEqual(labels, [t("card.menu.complete"), t("card.menu.pin"), t("card.menu.reminder"),
                                  t("card.menu.priority"), t("card.menu.color"), t("card.menu.delete")])
        self.assertEqual(m.entrycget(0, "accelerator"), "Ctrl+Enter")
        prio_menu = self.root.nametowidget(m.entrycget(3, "menu"))
        self.assertEqual(prio_menu.type(0), "radiobutton")
        self.assertEqual(prio_menu.index("end") + 1, 4)
        color_menu = self.root.nametowidget(m.entrycget(4, "menu"))
        self.assertEqual(color_menu.index("end") + 1, 7)

    def test_menu_actions_reach_db(self) -> None:
        nid = db.create_note("menu")
        self.board._load_notes()
        card = self.card(nid)
        card._build_menu()
        card._menu.invoke(1)  # ปักหมุด
        self.assertEqual(db.get_note(nid)["is_pinned"], 1)
        prio_menu = self.root.nametowidget(card._menu.entrycget(3, "menu"))
        card._build_menu()
        prio_menu = self.root.nametowidget(card._menu.entrycget(3, "menu"))
        prio_menu.invoke(0)
        self.assertEqual(db.get_note(nid)["priority"], "high")
        card._build_menu()
        color_menu = self.root.nametowidget(card._menu.entrycget(4, "menu"))
        color_menu.invoke(3)
        self.assertEqual(db.get_note(nid)["color"], "pink")

    def test_chip_clear_reminder(self) -> None:
        nid = db.create_note("chip", collapsed=False)
        db.set_reminder(nid, at(90))
        self.board._load_notes()
        self.card(nid).callbacks.on_clear_reminder(nid)
        self.assertIsNone(db.get_note(nid)["reminder_datetime"])
        self.assertIn(nid, self.toasts.closed())

    def test_click_title_expands_and_circle_completes(self) -> None:
        a, b = db.create_note("a"), db.create_note("b")
        self.board._load_notes()
        self.pump()
        self.card(a)._title.event_generate("<Button-1>", x=5, y=5)
        self.pump()
        self.assertTrue(self.card(a).expanded)
        self.card(b)._check.event_generate("<ButtonRelease-1>", x=5, y=5)
        self.pump(0.5)
        self.assertEqual(db.get_note(b)["status"], "completed")

    def test_saved_caption_appears_then_fades_out(self) -> None:
        nid = db.create_note("t", collapsed=False)
        self.board._load_notes()
        card = self.card(nid)
        card._text.insert("1.0", "hello")
        self.pump(0.8)
        self.assertEqual(card._saved_lbl.cget("text"), t("card.saved"))
        self.pump(1.8)
        self.assertEqual(card._saved_lbl.cget("text"), "")

    def test_shortcut_forwarding_from_entry(self) -> None:
        nid = db.create_note("kb", collapsed=False)
        self.board._load_notes()
        self.pump()
        entry = self.card(nid)._title_entry
        before = self.settings.get("always_on_top")
        entry.event_generate("<<QN-Topmost>>")
        self.assertEqual(self.settings.get("always_on_top"), not before)


class UndoTest(BoardTestCase):
    def test_complete_then_undo(self) -> None:
        nid = db.create_note("task")
        self.board._load_notes()
        self.board._on_toggle_complete(nid)
        self.assertEqual(db.get_note(nid)["status"], "completed")
        self.assertTrue(self.board.undo_bar.is_active)
        self.pump(0.5)
        self.assertNotIn(nid, self.board.note_cards)
        self.assertEqual(self.board._tabs["completed"][0].cget("text"), t("board.tab_completed", n=1))
        self.board.undo_bar._on_undo_click()
        self.pump()
        self.assertEqual(db.get_note(nid)["status"], "active")
        self.assertIn(nid, self.board.note_cards)

    def test_h11_delete_is_soft_then_undo(self) -> None:
        nid = db.create_note("precious", "text")
        self.board._load_notes()
        self.board._on_delete(nid)
        self.assertNotIn(nid, self.board.note_cards)
        self.assertIsNotNone(db.get_note(nid)["deleted_at"])
        self.board.undo_bar._on_undo_click()
        self.assertIsNone(db.get_note(nid)["deleted_at"])
        self.assertIn(nid, self.board.note_cards)

    def test_h11_delete_purged_on_expire(self) -> None:
        nid = db.create_note("gone")
        self.board._load_notes()
        self.board._on_delete(nid)
        self.board.undo_bar.flush()  # = ครบ 5 วินาที
        self.assertIsNone(db.get_note(nid))

    def test_second_delete_purges_first(self) -> None:
        a, b = db.create_note("a"), db.create_note("b")
        self.board._load_notes()
        self.board._on_delete(a)
        self.board._on_delete(b)
        self.assertIsNone(db.get_note(a))
        self.assertIsNotNone(db.get_note(b))
        self.board.undo_bar._on_undo_click()
        self.assertIsNone(db.get_note(b)["deleted_at"])

    def test_delete_flushes_pending_text_for_undo(self) -> None:
        nid = db.create_note("t", collapsed=False)
        self.board._load_notes()
        self.card(nid)._text.insert("1.0", "typed just before delete")
        self.pump()
        self.board._on_delete(nid)
        self.board.undo_bar._on_undo_click()
        self.assertEqual(db.get_note(nid)["content"], "typed just before delete")

    def test_delete_all_completed_confirm(self) -> None:
        a = db.create_note("a")
        db.set_status(a, "completed")
        self.board._select_tab("completed")
        with mock.patch.object(messagebox, "askyesno", return_value=False):
            self.board._delete_all_completed()
        self.assertIsNotNone(db.get_note(a))
        with mock.patch.object(messagebox, "askyesno", return_value=True) as ask:
            self.board._delete_all_completed()
        self.assertTrue(ask.called)
        self.assertIsNone(db.get_note(a))
        self.pump()
        self.assertTrue(self.board._empty.winfo_ismapped())


class AlarmFlowTest(BoardTestCase):
    def ring(self, title="alarm", minutes_ago=2, repeat="none") -> str:
        nid = db.create_note(title)
        db.set_reminder(nid, at(-minutes_ago), repeat)
        self.board.scheduler.check_now()
        self.pump()
        return nid

    def test_due_marks_ringing_refreshes_and_shows_toast(self) -> None:
        nid = self.ring()
        self.assertEqual(db.get_note(nid)["reminder_triggered"], 1)
        self.assertIn(("show_reminder", nid), self.toasts.calls)
        card = self.card(nid)
        self.assertTrue(card.ringing)
        self.assertEqual(card._border_spec, "critical")
        self.board.scheduler.check_now()
        self.assertEqual(self.toasts.calls.count(("show_reminder", nid)), 1)  # ไม่ดังซ้ำ

    def test_done_completes_non_repeating(self) -> None:
        nid = self.ring()
        self.toasts.reminders[-1]["on_done"]()
        row = db.get_note(nid)
        self.assertEqual((row["status"], row["reminder_datetime"], row["reminder_triggered"]),
                         ("completed", None, 0))
        self.assertIn(nid, self.toasts.closed())
        self.assertNotIn(nid, self.board.note_cards)

    def test_done_on_repeating_advances_and_stays_active(self) -> None:
        nid = self.ring(repeat="daily")
        self.toasts.reminders[-1]["on_done"]()
        row = db.get_note(nid)
        self.assertEqual(row["status"], "active")
        self.assertGreater(row["reminder_datetime"], datetime.now().strftime(FMT))
        self.assertEqual(row["reminder_triggered"], 0)

    def test_snooze_callback_gets_when_string(self) -> None:
        nid = self.ring()
        when = at(15)
        self.toasts.reminders[-1]["on_snooze"](when)
        row = db.get_note(nid)
        self.assertEqual((row["reminder_datetime"], row["reminder_triggered"]), (when, 0))
        self.assertFalse(self.card(nid).ringing)
        self.assertIn(nid, self.toasts.closed())

    def test_dismiss_clears_alarm(self) -> None:
        nid = self.ring()
        self.toasts.reminders[-1]["on_dismiss"]()
        row = db.get_note(nid)
        self.assertEqual((row["reminder_datetime"], row["reminder_triggered"], row["status"]),
                         (None, 0, "active"))

    def test_open_reveals_expands_and_shows_window(self) -> None:
        nid = self.ring()
        self.board.hide()
        self.pump()
        self.toasts.reminders[-1]["on_open"]()
        self.pump()
        self.assertTrue(self.root.winfo_viewable())
        self.assertTrue(self.card(nid).expanded)
        self.assertTrue(db.get_note(nid)["reminder_triggered"])  # เปิดอย่างเดียวไม่ปิดเสียงเตือน

    def test_due_while_hidden_does_not_show_window(self) -> None:
        self.board.hide()
        self.pump()
        nid = self.ring()
        self.assertFalse(self.root.winfo_viewable())
        self.assertIn(("show_reminder", nid), self.toasts.calls)

    def test_card_chip_done_and_snooze_default_minutes(self) -> None:
        self.settings.set("snooze_default_minutes", 15)
        nid = self.ring()
        card = self.card(nid)
        texts = [lb.cget("text") for chip in card._chip_row.winfo_children() for lb in chip.winfo_children()]
        self.assertIn(t("card.alarm_done"), texts)
        self.assertIn(t("card.alarm_snooze", n=15), texts)
        card.callbacks.on_alarm_snooze(nid)
        row = db.get_note(nid)
        planned = datetime.strptime(row["reminder_datetime"], FMT)
        self.assertAlmostEqual((planned - datetime.now()).total_seconds() / 60, 15, delta=1.5)
        self.assertEqual(row["reminder_triggered"], 0)
        self.assertIn(nid, self.toasts.closed())

    def test_card_chip_done_completes(self) -> None:
        nid = self.ring()
        self.card(nid).callbacks.on_alarm_done(nid)
        self.assertEqual(db.get_note(nid)["status"], "completed")

    def test_completing_ringing_note_from_circle_dismisses_and_closes_toast(self) -> None:
        nid = self.ring()
        self.card(nid)._toggle_complete()
        row = db.get_note(nid)
        self.assertEqual((row["status"], row["reminder_datetime"], row["reminder_triggered"]),
                         ("completed", None, 0))
        self.assertIn(nid, self.toasts.closed())

    def test_missed_goes_to_missed_toast_not_reminder_toast(self) -> None:
        nid = self.ring(minutes_ago=60 * 4)
        self.assertIn(("show_missed", [nid]), self.toasts.calls)
        self.assertNotIn(("show_reminder", nid), self.toasts.calls)
        self.assertIsNone(db.get_note(nid)["reminder_datetime"])
        self.toasts.missed_view()  # "ดู" → แสดงหน้าต่าง
        self.pump()
        self.assertTrue(self.root.winfo_viewable())

    def test_status_bar_next_reminder(self) -> None:
        self.assertFalse(self.board._status.winfo_ismapped())
        nid = db.create_note("Dentist")
        db.set_reminder(nid, at(90))
        self.board._load_notes()
        self.pump()
        self.assertTrue(self.board._status.winfo_ismapped())
        self.assertIn("Dentist", self.board._status_text.cget("text"))
        db.set_reminder(nid, None)
        self.board._load_notes()
        self.pump()
        self.assertFalse(self.board._status.winfo_ismapped())


class ReminderDialogFlowTest(BoardTestCase):
    def install_fake_dialog(self):
        opened: list[dict] = []

        class FakeDialog:
            def __init__(self, root, note, theme, on_save):
                opened.append({"note": note, "on_save": on_save})

        fake = types.ModuleType("src.ui.reminder_dialog")
        fake.ReminderDialog = FakeDialog
        patcher = mock.patch.dict(sys.modules, {"src.ui.reminder_dialog": fake})
        patcher.start()
        self.addCleanup(patcher.stop)
        return opened

    def test_open_save_and_clear(self) -> None:
        opened = self.install_fake_dialog()
        nid = db.create_note("r")
        self.board._load_notes()
        self.card(nid).callbacks.on_reminder(nid)
        self.assertIsInstance(opened[0]["note"], Note)
        self.assertEqual(opened[0]["note"].id, nid)
        when = at(45)
        opened[0]["on_save"](when, "weekly")
        row = db.get_note(nid)
        self.assertEqual((row["reminder_datetime"], row["reminder_repeat"]), (when, "weekly"))
        opened[0]["on_save"](None, "none")
        self.assertIsNone(db.get_note(nid)["reminder_datetime"])
        self.assertIn(nid, self.toasts.closed())

    def test_saving_past_time_rings_immediately(self) -> None:
        opened = self.install_fake_dialog()
        nid = db.create_note("r")
        self.board._load_notes()
        self.card(nid).callbacks.on_reminder(nid)
        opened[0]["on_save"](at(-3), "none")
        self.assertIn(("show_reminder", nid), self.toasts.calls)


class LiveSettingsTest(BoardTestCase):
    def test_language_switch_relabels_and_rebuilds(self) -> None:
        nid = db.create_note("lang", "x", collapsed=False)
        db.set_reminder(nid, at(60))
        self.board._load_notes()
        self.card(nid)._title_var.set("typed before switch")
        self.settings.set("language", "en")
        self.pump()
        self.assertEqual(self.board._tabs["active"][0].cget("text"), "Active (1)")
        self.assertEqual(db.get_note(nid)["title"], "typed before switch")  # flush ก่อน rebuild
        card = self.card(nid)
        self.assertTrue(any("Today" in lb.cget("text") or "Tomorrow" in lb.cget("text")
                            for chip in card._chip_row.winfo_children() for lb in chip.winfo_children()))
        self.settings.set("language", "th")

    def test_theme_switch_recolors_cards_and_window(self) -> None:
        nid = db.create_note("t")
        db.update_fields(nid, color="yellow")
        self.board._load_notes()
        light_bg = self.card(nid)._bg_spec
        self.settings.set("theme", "dark")
        self.pump()
        self.assertEqual(self.card(nid)._bg_spec, self.theme.note_bg("yellow"))
        self.assertNotEqual(self.card(nid)._bg_spec, light_bg)
        self.assertEqual(self.board._inner.cget("bg"), self.theme.c("bg"))
        self.assertEqual(self.board._toolbar.cget("bg"), self.theme.c("surface"))
        self.settings.set("theme", "light")

    def test_font_size_change_refits_titles(self) -> None:
        nid = db.create_note("ชื่อโน้ตที่ยาวมากมากมากมากมากมากมากมากมากมากมากมากมากมากมากมาก " * 2)
        self.board._load_notes()
        self.pump()
        before = self.card(nid)._title.cget("text")
        self.settings.set("font_size", "large")
        self.pump(0.2)
        self.assertLessEqual(len(self.card(nid)._title.cget("text")), len(before))
        self.settings.set("font_size", "normal")


class KeyboardTest(BoardTestCase):
    def test_esc_cascade(self) -> None:
        nid = db.create_note("esc")
        self.board._load_notes()
        self.board._on_request_expand(nid)
        self.board._search.set_value("esc")
        self.pump(0.3)
        self.board._on_escape()  # 1) พับการ์ด
        self.assertFalse(self.card(nid).expanded)
        self.assertEqual(self.board._search.get_value(), "esc")
        self.board._on_escape()  # 2) ล้างคำค้น
        self.assertEqual(self.board._search.get_value(), "")
        self.assertTrue(self.root.winfo_viewable())
        self.board._on_escape()  # 3) ซ่อนหน้าต่าง
        self.pump()
        self.assertFalse(self.root.winfo_viewable())

    def test_virtual_shortcuts(self) -> None:
        db.set_status(db.create_note("c"), "completed")
        self.root.event_generate("<<QN-TabCompleted>>")
        self.assertEqual(self.board._tab, "completed")
        self.root.event_generate("<<QN-TabActive>>")
        self.assertEqual(self.board._tab, "active")
        self.root.event_generate("<<QN-Topmost>>")
        self.assertFalse(self.settings.get("always_on_top"))

    def test_ctrl_n_from_completed_goes_to_active_quick_add(self) -> None:
        self.board._select_tab("completed")
        self.root.event_generate("<<QN-NewNote>>")
        self.assertEqual(self.board._tab, "active")
        self.assertTrue(self.board._qa_wrap.winfo_manager())

    def test_arrow_keys_move_between_cards(self) -> None:
        a = self.make("a", created="2026-01-03T10:00:00")
        b = self.make("b", created="2026-01-02T10:00:00")
        self.board._load_notes()
        self.pump()
        self.card(a).focus_force()
        self.pump()
        self.board._on_arrow(1)
        self.pump()
        self.assertIs(self.root.focus_lastfor(), self.card(b))
        self.board._on_arrow(-1)
        self.assertIs(self.root.focus_lastfor(), self.card(a))

    def test_card_keys(self) -> None:
        nid = db.create_note("keys")
        self.board._load_notes()
        card = self.card(nid)
        card._toggle_pin()
        self.assertEqual(db.get_note(nid)["is_pinned"], 1)
        card.event_generate("<Delete>")  # canvas ไม่มี focus → ไม่ยิง ; เรียกผ่าน binding โดยตรง
        card.callbacks.on_delete(nid)
        self.assertIsNotNone(db.get_note(nid)["deleted_at"])

    def test_wheel_scrolls_list_from_any_widget(self) -> None:
        for i in range(30):
            self.make(f"n{i}", created=f"2026-01-{i % 28 + 1:02d}T10:{i:02d}:00")
        self.board._load_notes()
        self.pump(0.3)
        self.assertEqual(self.board._canvas.yview()[0], 0.0)
        card = self.board._visible_cards()[3]
        card._title.event_generate("<MouseWheel>", delta=-120)
        self.pump()
        self.assertGreater(self.board._canvas.yview()[0], 0.0)
        self.assertTrue(self.board._scroll_shown)

    def test_scrollbar_hidden_when_content_fits(self) -> None:
        self.make("only")
        self.board._load_notes()
        self.pump(0.3)
        self.assertFalse(self.board._scroll_shown)


class RebuildTest(BoardTestCase):
    def test_rebuild_drops_cards_without_flushing(self) -> None:
        nid = db.create_note("old", collapsed=False)
        self.board._load_notes()
        self.card(nid)._title_var.set("pending that must be discarded")
        old_card = self.card(nid)
        self.board.rebuild()
        self.assertIsNot(self.card(nid), old_card)
        self.assertEqual(db.get_note(nid)["title"], "old")

    def test_rebuild_after_database_swapped(self) -> None:
        a = db.create_note("a")
        self.board._load_notes()
        self.raw("DELETE FROM notes")
        b = db.create_note("b")
        self.board.rebuild()
        self.assertEqual(list(self.board.note_cards), [b])
        self.assertNotIn(a, self.board.note_cards)


if __name__ == "__main__":
    unittest.main()
