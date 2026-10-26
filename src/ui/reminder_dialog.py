"""ReminderDialog — หน้าต่างตั้งการแจ้งเตือน (ContentDialog, DESIGN_SPEC 5)

dialog นี้ "ไม่เขียน DB เอง": ผู้ใช้กดบันทึก → เรียก on_save(when_or_None, repeat) แล้วปิด
กติกาที่ห้ามพลาด:
- modal ต้องปลด grab ทุกทางออก (M8) ไม่งั้นหน้าต่างหลักค้าง — ปิดก่อนเรียก callback เสมอ
- transient(root) เฉพาะตอน root มองเห็น (C6): transient จะ "ตาม state ของ root" แล้วซ่อนตามไปด้วย
- prefill ค่าเดิม (M6) และ validate ระหว่างพิมพ์พร้อมบอกเหตุผล (M7) — Save ถูก disable ตอนค่าไม่ถูกต้อง
- เวลาในอดีตบันทึกได้ (= ดังทันที) แต่ต้องเตือนให้เห็น
"""

from __future__ import annotations

import logging
import tkinter as tk
from datetime import datetime, timedelta
from tkinter import ttk
from typing import Callable

from tkcalendar import DateEntry

from ..core import reminders
from ..core.models import REPEATS, Note
from . import win11
from .icons import glyph
from .strings import get_language, t
from .toast import ICON_FILE, wrap_clamp
from .widgets import px

log = logging.getLogger(__name__)

_DATE_FMT = "%d/%m/%Y"
_DATE_PATTERN = "dd/mm/yyyy"
_SIZE = (380, 400)  # px ที่ 96 DPI (spec 5) — สูงขึ้นได้ถ้าเนื้อหาไม่พอ
_QUICK = (("in15m", "reminder.quick_15m"), ("in1h", "reminder.quick_1h"),
          ("this_evening", "reminder.quick_evening"), ("tomorrow_9", "reminder.quick_tomorrow"))


def _now() -> datetime:
    """แยกเป็นฟังก์ชันเพื่อให้ test ตรึงเวลาได้"""
    return datetime.now()


class ReminderDialog:
    def __init__(self, root: tk.Misc, note: Note, theme, on_save: Callable[[str | None, str], None]) -> None:
        self.root = root
        self.note = note
        self.theme = theme
        self._on_save = on_save
        self._closed = False
        self._when: datetime | None = None  # ค่าที่ parse จากช่องกรอกล่าสุด (None = ไม่ถูกต้อง)
        self.has_existing = bool(note.reminder_datetime)

        self.top = tk.Toplevel(root)
        self.top.withdraw()
        self.top.title(t("reminder.title"))
        self.top.resizable(False, False)
        theme.apply_window(self.top)
        self._set_icon()

        now = _now()
        start = self._initial_datetime(now)
        self.date_var = tk.StringVar(master=self.top)
        self.hour_var = tk.StringVar(master=self.top, value=f"{start.hour:02d}")
        self.minute_var = tk.StringVar(master=self.top, value=f"{start.minute:02d}")
        self.repeat_var = tk.StringVar(master=self.top)
        self._repeat_labels = {r: t(f"reminder.repeat.{r}") for r in REPEATS}

        self._build(start)
        self.set_repeat(note.reminder_repeat if note.reminder_repeat in REPEATS else "none")
        for var in (self.date_var, self.hour_var, self.minute_var):
            var.trace_add("write", lambda *_a: self._validate())
        self._validate()

        self.top.protocol("WM_DELETE_WINDOW", self.cancel)
        self.top.bind("<Escape>", lambda _e: self.cancel())
        self.top.bind("<Return>", self._on_return)
        self._unsub = theme.subscribe(self._apply_theme)
        self.top.bind("<Destroy>", self._on_destroy, add="+")
        self._show()

    # ------------------------------------------------------------ public
    @property
    def repeat(self) -> str:
        """ค่า repeat เป็น key ('none'|'daily'|'weekdays'|'weekly') ไม่ใช่ข้อความที่แสดง"""
        shown = self.repeat_var.get()
        for key, label in self._repeat_labels.items():
            if label == shown:
                return key
        return "none"

    def set_repeat(self, repeat: str) -> None:
        self.repeat_var.set(self._repeat_labels.get(repeat, self._repeat_labels["none"]))

    def set_when(self, when: datetime) -> None:
        """ใส่วัน/เวลาลงช่องกรอก (ปุ่มลัดใช้ตัวนี้)"""
        self.date_entry.set_date(when.date())
        self.hour_var.set(f"{when.hour:02d}")
        self.minute_var.set(f"{when.minute:02d}")

    @property
    def message(self) -> str:
        """ข้อความ error/เตือนใต้ช่องกรอก ('' = ไม่มี)"""
        return self._msg_text.cget("text")

    @property
    def is_valid(self) -> bool:
        return self._when is not None

    @property
    def is_past(self) -> bool:
        return self._when is not None and self._when <= _now()

    def save(self) -> None:
        """บันทึก = ปิด dialog แล้วส่ง (when, repeat) — ค่าไม่ถูกต้องไม่ทำอะไร (ปุ่มถูก disable อยู่แล้ว)"""
        if self._when is None or self._closed:
            return
        when, repeat = reminders.format_dt(self._when), self.repeat
        self._finish(lambda: self._on_save(when, repeat))

    def delete_reminder(self) -> None:
        self._finish(lambda: self._on_save(None, "none"))

    def cancel(self) -> None:
        self._close()

    def close(self) -> None:
        self._close()

    def lift(self) -> None:
        try:
            self.top.lift()
            self.top.focus_force()
        except tk.TclError:
            pass

    # ------------------------------------------------------------ build
    def _set_icon(self) -> None:
        try:
            self.top.iconbitmap(str(ICON_FILE))
        except tk.TclError:
            pass  # ไม่มีไอคอนไม่ใช่เรื่องใหญ่

    def _initial_datetime(self, now: datetime) -> datetime:
        """ค่าเดิมของโน้ต (M6) ไม่งั้นชั่วโมงเต็มถัดไป"""
        if self.note.reminder_datetime:
            try:
                return reminders.parse_dt(self.note.reminder_datetime)
            except (TypeError, ValueError):
                pass
        return now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)

    def _build(self, start: datetime) -> None:
        th, top = self.theme, self.top
        pad = px(top, 20)
        gap = px(top, 8)
        bg = th.c("bg")
        self._plain: list[tk.Widget] = []         # tk widget ที่ต้องย้อมพื้นใหม่ตอนเปลี่ยนธีม
        self._text_labels: list[tk.Label] = []    # label สี text ปกติ

        main = tk.Frame(top, bg=bg)
        main.pack(fill="both", expand=True, padx=pad, pady=(px(top, 16), px(top, 16)))
        self._plain.append(main)

        # แถวปุ่มล่างสุด pack ก่อนเพื่อไม่ถูกเนื้อหาดันออกนอกหน้าต่าง
        bottom = tk.Frame(main, bg=bg)
        bottom.pack(side="bottom", fill="x", pady=(px(top, 12), 0))
        self._plain.append(bottom)
        self.save_btn = ttk.Button(bottom, text=t("common.save"), style="Accent.TButton", width=10,
                                   command=self.save)
        self.save_btn.pack(side="right")
        self.cancel_btn = ttk.Button(bottom, text=t("common.cancel"), width=10, command=self.cancel)
        self.cancel_btn.pack(side="right", padx=(0, gap))
        self.delete_btn: ttk.Button | None = None
        if self.has_existing:
            # ลิงก์ซ้ายสุด ห่างจากปุ่มบันทึก (V25: ลบอยู่ติด Set เดิมกดพลาดง่าย)
            self.delete_btn = ttk.Button(bottom, text=t("reminder.delete"), style="Link.TButton",
                                         command=self.delete_reminder)
            self.delete_btn.pack(side="left")

        # ข้อความ error/เตือน: จองที่ 2 บรรทัดไว้เสมอ ไม่ให้ปุ่มด้านล่างขยับตอนข้อความโผล่
        msg = tk.Frame(main, bg=bg)
        msg.pack(side="bottom", fill="x", pady=(px(top, 8), 0))
        self._plain.append(msg)
        self._msg_icon = tk.Label(msg, text="", font=th.font("icon10"), bg=bg, fg=th.c("critical"))
        self._msg_icon.pack(side="left", anchor="n", padx=(0, px(top, 6)), pady=(px(top, 2), 0))
        inner_w = px(top, _SIZE[0]) - 2 * pad
        self._msg_text = tk.Label(msg, text="", font=th.font("caption"), bg=bg, fg=th.c("critical"),
                                  anchor="nw", justify="left", height=2, wraplength=inner_w - px(top, 24))
        self._msg_text.pack(side="left", fill="x", expand=True)
        self._plain += [self._msg_icon, self._msg_text]

        # --- หัวข้อโน้ต
        name = (self.note.title or "").strip() or t("common.untitled")
        self._note_lbl = tk.Label(main, text=wrap_clamp(name, th.font("caption"), inner_w, 1),
                                  font=th.font("caption"), bg=bg, fg=th.c("text_secondary"), anchor="w")
        self._note_lbl.pack(fill="x")
        self._plain.append(self._note_lbl)

        # --- ปุ่มเวลาเร็ว 2x2
        quick = tk.Frame(main, bg=bg)
        quick.pack(fill="x", pady=(px(top, 12), 0))
        self._plain.append(quick)
        self.quick_buttons: dict[str, ttk.Button] = {}
        available = reminders.quick_times(_now())
        for i, (key, label_key) in enumerate(_QUICK):
            quick.grid_columnconfigure(i % 2, weight=1, uniform="quick")
            btn = ttk.Button(quick, text=t(label_key), command=lambda k=key: self._apply_quick(k))
            btn.grid(row=i // 2, column=i % 2, sticky="ew", padx=(0, gap) if i % 2 == 0 else 0,
                     pady=(0, gap) if i < 2 else 0)
            if available[key] is None:  # 17:00 ผ่านไปแล้ว → กดไม่ได้ (คงตำแหน่งตารางไว้)
                btn.state(["disabled"])
            self.quick_buttons[key] = btn

        # --- วันที่
        self._field_label(main, "reminder.date", px(top, 12))
        self.date_entry = self._make_date_entry(main, start)
        self.date_entry.pack(fill="x", pady=(px(top, 4), 0))

        # --- เวลา: ชั่วโมง : นาที
        self._field_label(main, "reminder.time", px(top, 10))
        trow = tk.Frame(main, bg=bg)
        trow.pack(fill="x", pady=(px(top, 4), 0))
        self._plain.append(trow)
        self.hour_spin = ttk.Spinbox(trow, from_=0, to=23, increment=1, wrap=True, width=4, justify="center",
                                     format="%02.0f", textvariable=self.hour_var)
        self.hour_spin.pack(side="left")
        colon = tk.Label(trow, text=":", font=th.font("body_strong"), bg=bg, fg=th.c("text"))
        colon.pack(side="left", padx=gap)
        self._plain.append(colon)
        self._text_labels.append(colon)
        # step 5 ตามสเปก (to=55 ให้ลูกศร wrap 00↔55 ลงตัว) แต่พิมพ์เลขอะไรก็ได้ 0–59 — _validate ตรวจเอง
        self.minute_spin = ttk.Spinbox(trow, from_=0, to=55, increment=5, wrap=True, width=4, justify="center",
                                       format="%02.0f", textvariable=self.minute_var)
        self.minute_spin.pack(side="left")

        # --- ทำซ้ำ
        self._field_label(main, "reminder.repeat", px(top, 10))
        self.repeat_combo = ttk.Combobox(main, state="readonly", textvariable=self.repeat_var,
                                         values=[self._repeat_labels[r] for r in REPEATS])
        self.repeat_combo.pack(fill="x", pady=(px(top, 4), 0))

    def _field_label(self, parent: tk.Widget, key: str, top_pad: int) -> None:
        lbl = tk.Label(parent, text=t(key), font=self.theme.font("body"), bg=self.theme.c("bg"),
                       fg=self.theme.c("text"), anchor="w")
        lbl.pack(fill="x", pady=(top_pad, 0))
        self._plain.append(lbl)
        self._text_labels.append(lbl)

    def _calendar_colors(self) -> dict[str, str]:
        """ปฏิทิน dropdown ใช้สี token ทั้งหมด (V23: เดิม hard-code darkblue)"""
        c = self.theme.c
        return {
            "background": c("surface"), "foreground": c("text"),
            "headersbackground": c("surface"), "headersforeground": c("text_secondary"),
            "normalbackground": c("card"), "normalforeground": c("text"),
            "weekendbackground": c("card"), "weekendforeground": c("text_secondary"),
            "othermonthbackground": c("card"), "othermonthforeground": c("text_disabled"),
            "othermonthweforeground": c("text_disabled"), "othermonthwebackground": c("card"),
            "selectbackground": c("accent"), "selectforeground": c("on_accent"),
            "bordercolor": c("stroke_strong"),
            "tooltipbackground": c("surface"), "tooltipforeground": c("text"),
        }

    def _make_date_entry(self, parent: tk.Widget, start: datetime) -> DateEntry:
        locale = "th_TH" if get_language() == "th" else "en_US"
        common = dict(textvariable=self.date_var, date_pattern=_DATE_PATTERN, year=start.year,
                      month=start.month, day=start.day, showweeknumbers=False, **self._calendar_colors())
        try:
            return DateEntry(parent, locale=locale, **common)
        except Exception:  # babel ไม่มี locale นี้ → ใช้ค่าเริ่มต้นของ tkcalendar ดีกว่า dialog เปิดไม่ขึ้น
            log.warning("DateEntry locale %s unavailable", locale, exc_info=True)
            return DateEntry(parent, **common)

    # ------------------------------------------------------------ show / modal
    def _show(self) -> None:
        top, root = self.top, self.root
        top.update_idletasks()
        w = px(top, _SIZE[0])
        h = max(px(top, _SIZE[1]), top.winfo_reqheight())
        try:
            viewable = bool(root.winfo_viewable())
        except tk.TclError:
            viewable = False
        if viewable:
            top.transient(root)  # เฉพาะตอน root เห็นอยู่ — ไม่งั้น dialog จะหายตาม root (C6)
            cx = root.winfo_rootx() + root.winfo_width() // 2
            cy = root.winfo_rooty() + root.winfo_height() // 2
        else:
            top.attributes("-topmost", True)  # root ซ่อนอยู่ ไม่มีอะไรให้ซ้อนทับ แต่กันโดนแอปอื่นบัง
            left, tp, right, bottom = win11.get_work_area(root)
            cx, cy = (left + right) // 2, (tp + bottom) // 2
        left, tp, right, bottom = win11.get_work_area(root)
        x = max(left, min(cx - w // 2, right - w))
        y = max(tp, min(cy - h // 2, bottom - h))
        top.geometry(f"{w}x{h}+{x}+{y}")
        top.deiconify()
        try:
            top.wait_visibility()
            top.grab_set()
        except tk.TclError:
            log.debug("grab_set failed (dialog not viewable)", exc_info=True)  # ไม่ modal ก็ยังใช้ได้
        top.lift()
        top.focus_force()

    def _finish(self, action: Callable[[], None]) -> None:
        """ปิด (ปลด grab) ก่อนแล้วค่อยเรียก callback — callback พังต้องไม่ทำให้หน้าต่างหลักค้าง (M8)"""
        self._close()
        try:
            action()
        except Exception:
            log.exception("reminder on_save callback failed")
            # ต้องบอกผู้ใช้ ไม่งั้นเข้าใจว่าตั้งเตือนแล้วแต่จริง ๆ ไม่ได้บันทึก
            try:
                from tkinter import messagebox
                messagebox.showerror("QuickNote", t("msg.reminder_save_fail"), parent=self.root)
            except tk.TclError:
                pass

    def _close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._unsub()
        try:
            self.top.grab_release()
        except tk.TclError:
            pass
        try:
            self.top.destroy()
        except tk.TclError:
            pass
        try:
            if self.root.winfo_viewable():
                self.root.focus_force()  # คืน focus ให้หน้าต่างหลักหลัง dialog ปิด
        except tk.TclError:
            pass

    def _on_destroy(self, e) -> None:
        # ถูกทำลายจากทางอื่น (เช่น root ปิด) → ปลด grab/ถอดตัวฟังธีมให้ครบ
        if e.widget is self.top and not self._closed:
            self._closed = True
            self._unsub()

    # ------------------------------------------------------------ interaction
    def _apply_quick(self, key: str) -> None:
        when = reminders.quick_times(_now())[key]
        if when is not None:
            self.set_when(reminders.parse_dt(when))

    def _on_return(self, _e) -> str | None:
        # Enter บนปุ่มอื่น (ยกเลิก/ลบ/ปุ่มลัด) ต้องทำตามปุ่มนั้น ไม่ใช่บันทึก
        try:
            w = self.top.focus_get()
        except (tk.TclError, KeyError):
            w = None
        if isinstance(w, ttk.Button) and w is not self.save_btn:
            w.invoke()
        else:
            self.save()
        return "break"

    # ------------------------------------------------------------ validation (M7)
    def _parse_fields(self) -> tuple[datetime | None, str | None]:
        """อ่านช่องกรอก → (datetime, None) หรือ (None, key ของข้อความ error)"""
        try:
            d = datetime.strptime(self.date_var.get().strip(), _DATE_FMT)
        except ValueError:
            return None, "reminder.err_date"
        if not 2000 <= d.year <= 2999:  # %Y ปีน้อยกว่า 1000 ไม่ pad → parse_dt ของ core อ่านกลับไม่ได้
            return None, "reminder.err_date"
        hour, minute = self.hour_var.get().strip(), self.minute_var.get().strip()
        if not (hour.isascii() and hour.isdigit() and int(hour) <= 23):
            return None, "reminder.err_hour"
        if not (minute.isascii() and minute.isdigit() and int(minute) <= 59):
            return None, "reminder.err_minute"
        return d.replace(hour=int(hour), minute=int(minute)), None

    def _validate(self) -> None:
        if self._closed:
            return
        when, err = self._parse_fields()
        self._when = when
        if err is not None:
            self._set_message(t(err))
        elif when <= _now():
            self._set_message(t("reminder.past_warning"))
        else:
            self._set_message("")
        self.save_btn.state(["!disabled"] if when is not None else ["disabled"])

    def _set_message(self, text: str) -> None:
        try:
            self._msg_text.configure(text=text)
            self._msg_icon.configure(text=glyph("warning") if text else "")
        except tk.TclError:
            pass

    # ------------------------------------------------------------ theme
    def _apply_theme(self) -> None:
        th = self.theme
        try:
            th.apply_window(self.top)
            for w in self._plain:
                w.configure(bg=th.c("bg"))
            self._note_lbl.configure(fg=th.c("text_secondary"))
            self._msg_icon.configure(fg=th.c("critical"))
            self._msg_text.configure(fg=th.c("critical"))
            for w in self._text_labels:
                w.configure(fg=th.c("text"))
            self.date_entry.configure(**self._calendar_colors())
        except tk.TclError:
            pass
