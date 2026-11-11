# -*- coding: utf-8 -*-
"""BUGList —— 项目内的 BUG / TODO 清单（.buglist）。

数据：UTF-8 JSON，跟着项目文件夹走，可读、可手改、可进版本库。
条目：kind = bug / todo，status = open 未处理 / wontfix 已读不修 / fixed 已修。

命令行：
    pythonw buglist.py 清单.buglist                          打开窗口
    python  buglist.py 清单.buglist --add 简述 --detail 详情   追加一条（不开窗口）
    python  buglist.py 清单.buglist --list [--verbose]         在终端按状态列出
    python  buglist.py 清单.buglist --mark ID 已修             改状态
    python  buglist.py 清单.buglist --set-detail ID 详情       补/改详细描述
    python  buglist.py 清单.buglist --remove ID                删除一条

详情支持轻量 Markdown：`代码`、**加粗**、- 列表、## 小标题。
"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import re
import secrets
import sys
import tkinter as tk
from datetime import datetime
from tkinter import font as tkfont
from tkinter import ttk

APP_TITLE = "待修复 BUG"
FONT_FAMILY = "Microsoft YaHei UI"
FONT_CODE = "Consolas"
FROZEN = bool(getattr(sys, "frozen", False))
if FROZEN:
    TOOL_DIR = os.path.dirname(os.path.abspath(sys.executable))
    BUNDLE_DIR = getattr(sys, "_MEIPASS", TOOL_DIR)
else:
    TOOL_DIR = os.path.dirname(os.path.abspath(__file__))
    BUNDLE_DIR = TOOL_DIR
ICON_PATH = next(
    (
        path
        for path in (
            os.path.join(BUNDLE_DIR, "buglist.ico"),
            os.path.join(BUNDLE_DIR, "assets", "buglist.ico"),
            os.path.join(BUNDLE_DIR, "buglist_ai.ico"),
        )
        if os.path.exists(path)
    ),
    "",
)

COLOR = {
    "bg": "#0f1116",
    "panel": "#171a21",
    "panel_alt": "#12151b",
    "detail": "#12151b",
    "line": "#262b36",
    "fg": "#e7e9ef",
    "muted": "#8a92a6",
    "dim": "#5d6478",
    "accent": "#f0a63c",
    "wontfix": "#7b8bb2",
    "fixed": "#5a6172",
    "todo": "#8fa6ff",
    "select": "#2a3142",
    "entry": "#1b1f28",
    "code": "#9ce8d6",
    "code_bg": "#1a2330",
}

STATUS_ORDER = {"open": 0, "wontfix": 1, "fixed": 2}
STATUS_LABEL = {"open": "未处理", "wontfix": "已读不修", "fixed": "已修"}
STATUS_COLOR = {
    "open": COLOR["accent"],
    "wontfix": COLOR["wontfix"],
    "fixed": COLOR["fixed"],
}
LABEL_STATUS = {label: key for key, label in STATUS_LABEL.items()}
KINDS = ("todo", "bug")
KIND_LABEL = {"bug": "BUG", "todo": "TODO"}
KIND_COLOR = {"bug": COLOR["accent"], "todo": COLOR["todo"]}
KIND_EMPTY_TEXT = {"bug": "还没有 BUG", "todo": "还没有 TODO"}

INLINE_PATTERN = re.compile(r"(\*\*.+?\*\*|`[^`\n]+`)")


# ---------------------------------------------------------------- 数据读写

def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def make_id(existing: set[str]) -> str:
    while True:
        candidate = secrets.token_hex(4)
        if candidate not in existing:
            return candidate


def empty_data(path: str) -> dict:
    return {
        "format": "buglist",
        "version": 2,
        "project": os.path.basename(os.path.dirname(os.path.abspath(path))),
        "created": now_iso(),
        "items": [],
    }


def normalize_item(raw: dict, used_ids: set[str]) -> dict | None:
    text = str(raw.get("text", "")).strip()
    if not text:
        return None
    item_id = raw.get("id")
    if not isinstance(item_id, str) or not item_id or item_id in used_ids:
        item_id = make_id(used_ids)
    used_ids.add(item_id)
    kind = raw.get("kind")
    if kind not in KIND_LABEL:
        kind = "bug"
    status = raw.get("status")
    if status not in STATUS_ORDER:
        status = "open"
    created = str(raw.get("created") or now_iso())
    return {
        "id": item_id,
        "kind": kind,
        "text": text,
        "detail": str(raw.get("detail", "") or ""),
        "status": status,
        "created": created,
        "updated": str(raw.get("updated") or created),
    }


def load_data(path: str) -> dict:
    """读清单；旧版（bugs 数组）自动升级成 items，坏文件先备份成 .bak。"""
    if not os.path.exists(path):
        return empty_data(path)
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            raise ValueError("文件结构不是 buglist")
        raw_items = data.get("items")
        if raw_items is None:
            raw_items = data.get("bugs")
            if not isinstance(raw_items, list):
                raise ValueError("文件结构不是 buglist")
    except (OSError, ValueError) as error:
        print(f"[buglist] 读取失败，原文件备份为 .bak：{error}", file=sys.stderr)
        try:
            os.replace(path, path + ".bak")
        except OSError:
            pass
        return empty_data(path)

    data["items"] = raw_items
    data["format"] = "buglist"
    data["version"] = 2
    data.setdefault("project", os.path.basename(os.path.dirname(os.path.abspath(path))))
    data.setdefault("created", now_iso())

    items = []
    used: set[str] = set()
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        item = normalize_item(raw, used)
        if item:
            items.append(item)
    data["items"] = items
    data.pop("bugs", None)
    return data


def save_data(path: str, data: dict) -> float:
    folder = os.path.dirname(os.path.abspath(path))
    if folder:
        os.makedirs(folder, exist_ok=True)
    temp_path = path + ".tmp"
    with open(temp_path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    os.replace(temp_path, path)
    return os.path.getmtime(path)


def add_item(data: dict, text: str, kind: str = "bug", detail: str = "", status: str = "open") -> dict:
    used = {item["id"] for item in data["items"]}
    stamp = now_iso()
    item = {
        "id": make_id(used),
        "kind": kind if kind in KIND_LABEL else "bug",
        "text": text.strip(),
        "detail": detail.strip(),
        "status": status if status in STATUS_ORDER else "open",
        "created": stamp,
        "updated": stamp,
    }
    data["items"].insert(0, item)
    return item


def parse_timestamp(item: dict) -> float:
    for key in ("created", "updated"):
        value = item.get(key)
        if not value:
            continue
        try:
            return datetime.fromisoformat(str(value)).timestamp()
        except ValueError:
            continue
    return 0.0


def sorted_items(data: dict, kind: str) -> list[dict]:
    """同一栏里：未处理 → 已读不修 → 已修，组内新的在上。"""
    return sorted(
        (item for item in data["items"] if item.get("kind") == kind),
        key=lambda item: (STATUS_ORDER.get(item.get("status"), 0), -parse_timestamp(item)),
    )


def count_status(data: dict, kind: str) -> dict[str, int]:
    counts = {status: 0 for status in STATUS_ORDER}
    for item in data["items"]:
        if item.get("kind") == kind:
            counts[item.get("status", "open")] = counts.get(item.get("status", "open"), 0) + 1
    return counts


def format_time(item: dict, pattern: str = "%m-%d %H:%M") -> str:
    try:
        return datetime.fromisoformat(str(item.get("created"))).strftime(pattern)
    except ValueError:
        return ""


# ---------------------------------------------------------------- 深色标题栏

def enable_dpi_awareness() -> None:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass


def apply_dark_title_bar(window: tk.Misc) -> None:
    """Win11 深色标题栏；失败就保持系统默认，不影响使用。"""
    try:
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        value = ctypes.c_int(1)
        for attribute in (20, 19):
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, attribute, ctypes.byref(value), ctypes.sizeof(value)
            ) == 0:
                break
        for attribute, color in (
            (35, 0x00171A17),  # DWMWA_CAPTION_COLOR   COLORREF 0x00BBGGRR
            (36, 0x00EFE9E7),  # DWMWA_TEXT_COLOR
            (34, 0x00362B26),  # DWMWA_BORDER_COLOR
        ):
            color_value = ctypes.c_int(color)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, attribute, ctypes.byref(color_value), ctypes.sizeof(color_value)
            )
    except (AttributeError, OSError):
        pass


# ---------------------------------------------------------------- 窗口

class BugListWindow:
    def __init__(self, path: str) -> None:
        self.path = os.path.abspath(path)
        self.data = load_data(self.path)
        self.selected_id: str | None = None
        self.selected_kind: str | None = None
        self.add_kind = "bug"
        self.detail_open = False
        self._suppress = False
        self.last_mtime = 0.0
        self.dirty_note = ""
        self.jobs: list[str] = []
        self.trees: dict[str, ttk.Treeview] = {}
        self.count_labels: dict[str, dict[str, tk.Label]] = {}
        self.empty_hints: dict[str, tk.Label] = {}

        self.root = tk.Tk()
        self.root.withdraw()  # 先藏起来，配色全设好再显示，避免白屏一闪
        self.root.title(f"{APP_TITLE} — {os.path.basename(self.path)}")
        self.root.configure(bg=COLOR["bg"])
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)
        self.scale = max(1.0, self.root.winfo_fpixels("1i") / 96.0)
        self.show_fixed = tk.BooleanVar(value=False)

        self._build_style()
        self._build_header()
        self._build_body()
        self._build_detail()
        self._build_footer()
        self._bind_keys()

        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.geometry(self._centered_geometry(1120, 820))
        self.root.minsize(self.px(900), self.px(560))
        if os.path.exists(ICON_PATH):
            try:
                self.root.iconbitmap(ICON_PATH)
            except tk.TclError:
                pass

        self.root.update_idletasks()
        apply_dark_title_bar(self.root)
        self.root.deiconify()
        self.root.lift()
        self.root.attributes("-topmost", True)
        self.later(400, lambda: self.root.attributes("-topmost", False))
        self.root.focus_force()

        if not os.path.exists(self.path):
            self.save()
        else:
            self.last_mtime = os.path.getmtime(self.path)
        self.refresh()
        self._render_status_line()
        self.root.after_idle(self._focus_first_tree)
        self.later(1200, self.poll_file)

    # -------------------------------------------------- 小工具

    def px(self, value: float) -> int:
        """逻辑像素 → 当前 DPI 下的实际像素。"""
        return int(round(value * self.scale))

    def font(self, size: int, weight: str = "normal") -> tuple:
        return (FONT_FAMILY, size, weight)

    def later(self, milliseconds: int, callback) -> None:
        """延时任务统一登记，关窗时一并取消，避免 Tk 报 invalid command name。"""
        pending = self.root.tk.call("after", "info")
        self.jobs = [job for job in self.jobs if job in pending]

        def wrapped() -> None:
            if self.root.winfo_exists():
                callback()

        self.jobs.append(self.root.after(milliseconds, wrapped))

    def button(
        self,
        parent: tk.Misc,
        text: str,
        command,
        fg: str | None = None,
        bg: str | None = None,
        hover: str | None = None,
    ) -> tk.Button:
        fg = fg or COLOR["fg"]
        bg = bg or COLOR["panel"]
        hover = hover or COLOR["select"]
        widget = tk.Button(
            parent,
            text=text,
            command=command,
            bg=bg,
            fg=fg,
            activebackground=hover,
            activeforeground=fg,
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            padx=self.px(14),
            pady=self.px(7),
            cursor="hand2",
            font=self.font(10),
            takefocus=0,
        )
        widget.bind("<Enter>", lambda event: widget.configure(bg=hover))
        widget.bind("<Leave>", lambda event: widget.configure(bg=bg))
        return widget

    def _centered_geometry(self, width: int, height: int) -> str:
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        win_w, win_h = self.px(width), self.px(height)
        left = max(0, (screen_w - win_w) // 2)
        top = max(0, int((screen_h - win_h) * 0.3))
        return f"{win_w}x{win_h}+{left}+{top}"

    def _focus_first_tree(self) -> None:
        if not self.selected_kind:
            self.trees["bug"].focus_set()

    # -------------------------------------------------- 样式

    def _build_style(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(
            "Bug.Treeview",
            background=COLOR["panel"],
            fieldbackground=COLOR["panel"],
            foreground=COLOR["fg"],
            borderwidth=0,
            rowheight=self.px(36),
            font=self.font(10),
        )
        style.layout("Bug.Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
        style.map(
            "Bug.Treeview",
            background=[("selected", COLOR["select"])],
            foreground=[("selected", "#ffffff")],
        )
        style.configure(
            "Bug.Treeview.Heading",
            background=COLOR["bg"],
            foreground=COLOR["dim"],
            borderwidth=0,
            relief="flat",
            padding=(self.px(8), self.px(7)),
            font=self.font(9, "bold"),
        )
        style.map("Bug.Treeview.Heading", background=[("active", COLOR["bg"])])
        style.configure(
            "Bug.Vertical.TScrollbar",
            background="#252b38",
            troughcolor=COLOR["panel"],
            bordercolor=COLOR["panel"],
            arrowcolor=COLOR["panel"],
            darkcolor="#252b38",
            lightcolor="#252b38",
            gripcount=0,
            arrowsize=1,
            relief="flat",
            width=self.px(8),
        )
        style.map("Bug.Vertical.TScrollbar", background=[("active", "#394154")])
        style.configure(
            "Detail.Vertical.TScrollbar",
            background="#2d3547",
            troughcolor=COLOR["detail"],
            bordercolor=COLOR["detail"],
            arrowcolor=COLOR["detail"],
            darkcolor="#2d3547",
            lightcolor="#2d3547",
            gripcount=0,
            arrowsize=1,
            relief="flat",
            width=self.px(8),
        )
        style.map("Detail.Vertical.TScrollbar", background=[("active", "#3a4560")])

    # -------------------------------------------------- 顶部

    def _build_header(self) -> None:
        header = tk.Frame(self.root, bg=COLOR["bg"], padx=self.px(22), pady=self.px(14))
        header.grid(row=0, column=0, sticky="ew")

        left = tk.Frame(header, bg=COLOR["bg"])
        left.pack(side="left", anchor="w")
        tk.Label(
            left,
            text=APP_TITLE,
            bg=COLOR["bg"],
            fg=COLOR["fg"],
            font=self.font(16, "bold"),
            anchor="w",
        ).pack(anchor="w")
        self.subtitle = tk.Label(
            left,
            text=self._subtitle_text(),
            bg=COLOR["bg"],
            fg=COLOR["dim"],
            font=self.font(9),
            anchor="w",
        )
        self.subtitle.pack(anchor="w", pady=(self.px(2), 0))

        self.toggle_hint = tk.Label(
            header,
            text="点一行看详情",
            bg=COLOR["bg"],
            fg=COLOR["dim"],
            font=self.font(9),
        )
        self.toggle_hint.pack(side="right", anchor="e")

    def _subtitle_text(self) -> str:
        project = self.data.get("project") or "未命名项目"
        return f"{project}  ·  {os.path.basename(self.path)}"

    # -------------------------------------------------- 两栏列表

    def _build_body(self) -> None:
        body = tk.Frame(self.root, bg=COLOR["bg"], padx=self.px(22))
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1, uniform="pane")
        body.columnconfigure(1, weight=1, uniform="pane")
        body.rowconfigure(0, weight=1)
        for column, kind in enumerate(KINDS):
            frame = tk.Frame(body, bg=COLOR["bg"])
            frame.grid(
                row=0,
                column=column,
                sticky="nsew",
                padx=(0, self.px(10)) if kind == "todo" else (self.px(2), 0),
            )
            self._build_pane(frame, kind)

    def _build_pane(self, frame: tk.Frame, kind: str) -> None:
        head = tk.Frame(frame, bg=COLOR["bg"])
        head.pack(fill="x", pady=(0, self.px(6)))

        tk.Label(
            head,
            text=KIND_LABEL[kind],
            bg=COLOR["bg"],
            fg=KIND_COLOR[kind],
            font=self.font(11, "bold"),
        ).pack(side="left")

        counts = tk.Frame(head, bg=COLOR["bg"])
        counts.pack(side="right")
        self.count_labels[kind] = {}
        for status in ("open", "wontfix", "fixed"):
            label = tk.Label(
                counts,
                text="",
                bg=COLOR["bg"],
                fg=STATUS_COLOR[status],
                font=self.font(9),
            )
            label.pack(side="left", padx=(self.px(6), 0))
            self.count_labels[kind][status] = label

        shell = tk.Frame(
            frame,
            bg=COLOR["panel"],
            highlightthickness=1,
            highlightbackground=COLOR["line"],
        )
        shell.pack(fill="both", expand=True)

        tree = ttk.Treeview(
            shell,
            columns=("status", "text", "time"),
            show="headings",
            style="Bug.Treeview",
            selectmode="browse",
            height=7,
        )
        tree.heading("status", text="状态", anchor="w")
        tree.heading("text", text="简述", anchor="w")
        tree.heading("time", text="时间", anchor="e")
        tree.column("status", width=self.px(80), minwidth=self.px(70), stretch=False, anchor="w")
        tree.column("text", width=self.px(300), minwidth=self.px(120), stretch=True, anchor="w")
        tree.column("time", width=self.px(92), minwidth=self.px(80), stretch=False, anchor="e")

        for tag in ("plain", "stripe"):
            tree.tag_configure(
                tag, background=COLOR["panel"] if tag == "plain" else COLOR["panel_alt"]
            )
        for status in ("open", "wontfix", "fixed"):
            tree.tag_configure(status, foreground=STATUS_COLOR[status])

        scrollbar = ttk.Scrollbar(
            shell, orient="vertical", command=tree.yview, style="Bug.Vertical.TScrollbar"
        )
        tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        tree.pack(side="left", fill="both", expand=True)
        tree.bind("<<TreeviewSelect>>", lambda event, name=kind: self._on_select(name))
        self.trees[kind] = tree

        hint = tk.Label(
            shell,
            text=KIND_EMPTY_TEXT[kind],
            bg=COLOR["panel"],
            fg=COLOR["dim"],
            font=self.font(9),
        )
        self.empty_hints[kind] = hint

    # -------------------------------------------------- 详情

    def _build_detail(self) -> None:
        frame = tk.Frame(self.root, bg=COLOR["bg"], padx=self.px(22), pady=self.px(6))
        frame.grid(row=2, column=0, sticky="ew")
        frame.grid_remove()
        self.detail_frame = frame

        head = tk.Frame(frame, bg=COLOR["bg"])
        head.pack(fill="x")

        close = tk.Label(
            head,
            text="收起 ✕",
            bg=COLOR["bg"],
            fg=COLOR["muted"],
            font=self.font(9),
            cursor="hand2",
        )
        close.pack(side="right")
        close.bind("<Button-1>", lambda event: self.hide_detail())
        close.bind("<Enter>", lambda event: close.configure(fg=COLOR["fg"]))
        close.bind("<Leave>", lambda event: close.configure(fg=COLOR["muted"]))

        self.detail_meta = tk.Label(
            head,
            text="",
            bg=COLOR["bg"],
            fg=COLOR["dim"],
            font=self.font(9),
        )
        self.detail_meta.pack(side="right", padx=(0, self.px(12)))

        tk.Label(
            head, text="详情", bg=COLOR["bg"], fg=COLOR["dim"], font=self.font(9)
        ).pack(side="left")
        self.detail_title = tk.Label(
            head,
            text="",
            bg=COLOR["bg"],
            fg=COLOR["fg"],
            font=self.font(10, "bold"),
            anchor="w",
        )
        self.detail_title.pack(side="left", padx=(self.px(8), 0), fill="x", expand=True)

        shell = tk.Frame(
            frame,
            bg=COLOR["detail"],
            highlightthickness=1,
            highlightbackground=COLOR["line"],
        )
        shell.pack(fill="x", pady=(self.px(6), 0))

        self.detail_text = tk.Text(
            shell,
            height=10,
            bg=COLOR["detail"],
            fg=COLOR["fg"],
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            wrap="word",
            padx=self.px(14),
            pady=self.px(10),
            insertwidth=0,
            spacing1=self.px(2),
            spacing3=self.px(3),
            font=self.font(10),
            cursor="arrow",
            takefocus=0,
        )
        self.detail_text.configure(state="disabled")
        scrollbar = ttk.Scrollbar(
            shell,
            orient="vertical",
            command=self.detail_text.yview,
            style="Detail.Vertical.TScrollbar",
        )
        self.detail_text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.detail_text.pack(side="left", fill="both", expand=True)

        self.detail_text.tag_configure(
            "body",
            foreground=COLOR["fg"],
            lmargin1=self.px(4),
            lmargin2=self.px(4),
            spacing1=self.px(2),
            spacing3=self.px(3),
        )
        self.detail_text.tag_configure(
            "bold", foreground="#ffffff", font=self.font(10, "bold")
        )
        self.detail_text.tag_configure(
            "code",
            foreground=COLOR["code"],
            background=COLOR["code_bg"],
            font=(FONT_CODE, 10),
        )
        self.detail_text.tag_configure(
            "codeblock",
            foreground=COLOR["code"],
            background=COLOR["code_bg"],
            font=(FONT_CODE, 10),
            lmargin1=self.px(12),
            lmargin2=self.px(12),
            spacing1=0,
            spacing3=0,
        )
        self.detail_text.tag_configure(
            "bullet",
            lmargin1=self.px(12),
            lmargin2=self.px(34),
            spacing1=self.px(2),
            spacing3=self.px(2),
        )
        self.detail_text.tag_configure(
            "heading",
            foreground=COLOR["accent"],
            font=self.font(11, "bold"),
            spacing1=self.px(10),
            spacing3=self.px(4),
        )
        self.detail_text.tag_configure(
            "empty", foreground=COLOR["dim"], font=self.font(9)
        )

    # -------------------------------------------------- 底部

    def _build_footer(self) -> None:
        footer = tk.Frame(self.root, bg=COLOR["bg"], padx=self.px(22), pady=self.px(12))
        footer.grid(row=3, column=0, sticky="ew")

        actions = tk.Frame(footer, bg=COLOR["bg"])
        actions.pack(fill="x")

        for status, hint in (("open", "退格"), ("wontfix", "Shift"), ("fixed", "Enter")):
            self.button(
                actions,
                f"{STATUS_LABEL[status]}  {hint}",
                lambda value=status: self.set_status(value),
                fg=STATUS_COLOR[status],
            ).pack(side="left", padx=(0, self.px(8)))
        self.button(actions, "删除  Del", self.delete_selected, fg=COLOR["muted"]).pack(side="left")

        tk.Checkbutton(
            actions,
            text="显示已修",
            variable=self.show_fixed,
            command=self.refresh,
            bg=COLOR["bg"],
            fg=COLOR["muted"],
            activebackground=COLOR["bg"],
            activeforeground=COLOR["fg"],
            selectcolor=COLOR["entry"],
            highlightthickness=0,
            borderwidth=0,
            font=self.font(9),
            cursor="hand2",
            takefocus=0,
        ).pack(side="right")

        entry_row = tk.Frame(footer, bg=COLOR["bg"], pady=self.px(9))
        entry_row.pack(fill="x")

        self.entry = tk.Entry(
            entry_row,
            bg=COLOR["entry"],
            fg=COLOR["fg"],
            insertbackground=COLOR["accent"],
            relief="flat",
            highlightthickness=1,
            highlightbackground=COLOR["line"],
            highlightcolor=COLOR["accent"],
            font=self.font(10),
        )
        self.entry.pack(side="left", fill="x", expand=True, ipady=self.px(7), padx=(0, self.px(8)))
        self.entry.bind("<Return>", self._on_entry_return)

        add_bug = self.button(
            entry_row, "加 BUG", lambda: self.add_from_entry("bug"),
            fg=COLOR["bg"], bg=COLOR["accent"], hover="#ffc061",
        )
        add_bug.configure(padx=self.px(16))
        add_bug.pack(side="left", padx=(0, self.px(6)))

        add_todo = self.button(
            entry_row, "加 TODO", lambda: self.add_from_entry("todo"),
            fg=COLOR["bg"], bg=COLOR["todo"], hover="#a9baff",
        )
        add_todo.configure(padx=self.px(16))
        add_todo.pack(side="left")

        status_row = tk.Frame(footer, bg=COLOR["bg"])
        status_row.pack(fill="x", pady=(self.px(4), 0))
        self.status_line = tk.Label(
            status_row,
            text="",
            bg=COLOR["bg"],
            fg=COLOR["dim"],
            font=self.font(9),
            anchor="w",
        )
        self.status_line.pack(side="left")
        tk.Label(
            status_row,
            text="Enter 已修   ·   Shift 已读不修   ·   Backspace 未处理   ·   Del 删除",
            bg=COLOR["bg"],
            fg=COLOR["dim"],
            font=self.font(9),
            anchor="e",
        ).pack(side="right")

    # -------------------------------------------------- 快捷键

    def _bind_keys(self) -> None:
        self.root.bind("<Return>", lambda event: self.hotkey_status("fixed"))
        self.root.bind("<KP_Enter>", lambda event: self.hotkey_status("fixed"))
        self.root.bind("<KeyPress-Shift_L>", lambda event: self.hotkey_status("wontfix"))
        self.root.bind("<KeyPress-Shift_R>", lambda event: self.hotkey_status("wontfix"))
        self.root.bind("<BackSpace>", lambda event: self.hotkey_status("open"))
        self.root.bind("<Delete>", self.hotkey_delete)
        self.root.bind("<Escape>", lambda event: self.hide_detail())
        self.root.bind("<Control-n>", lambda event: self.entry.focus_set())
        self.root.bind("<F5>", lambda event: self.reload())

    def _typing_in_entry(self) -> bool:
        return self.root.focus_get() is self.entry

    def hotkey_status(self, status: str) -> None:
        if self._typing_in_entry():
            return
        self.set_status(status)

    def hotkey_delete(self, event=None) -> None:
        if self._typing_in_entry():
            return
        self.delete_selected()

    def _on_entry_return(self, event) -> str:
        self.add_from_entry(self.add_kind)
        return "break"

    # -------------------------------------------------- 渲染

    def refresh(self) -> None:
        for kind in KINDS:
            self._refresh_pane(kind)
        self._update_counts()
        self.subtitle.configure(text=self._subtitle_text())
        item = self.current_item()
        if item and self.detail_open:
            self.populate_detail(item)

    def _refresh_pane(self, kind: str) -> None:
        tree = self.trees[kind]
        self._suppress = True
        for item_id in tree.get_children():
            tree.delete(item_id)

        shown = 0
        for item in sorted_items(self.data, kind):
            if item.get("status") == "fixed" and not self.show_fixed.get():
                continue
            tree.insert(
                "",
                "end",
                iid=item["id"],
                values=(
                    STATUS_LABEL[item["status"]],
                    item["text"],
                    format_time(item),
                ),
                tags=(item["status"], "plain" if shown % 2 == 0 else "stripe"),
            )
            shown += 1

        if self.selected_id and self.selected_kind == kind and tree.exists(self.selected_id):
            tree.selection_set(self.selected_id)
            tree.focus(self.selected_id)
            tree.see(self.selected_id)

        self._suppress = False

        hint = self.empty_hints[kind]
        if shown == 0:
            hint.place(relx=0.5, rely=0.5, anchor="center")
            hint.lift()
        else:
            hint.place_forget()

    def _update_counts(self) -> None:
        for kind in KINDS:
            counts = count_status(self.data, kind)
            for status, label in self.count_labels[kind].items():
                label.configure(text=f"{STATUS_LABEL[status]} {counts[status]}")

    def _on_select(self, kind: str) -> None:
        if self._suppress:
            return
        tree = self.trees[kind]
        selection = tree.selection()
        if not selection:
            return
        self.selected_kind = kind
        self.selected_id = selection[0]
        self.add_kind = kind
        other = "bug" if kind == "todo" else "todo"
        if self.trees[other].selection():
            self._suppress = True
            self.trees[other].selection_remove(self.trees[other].selection())
            self._suppress = False
        item = self.current_item()
        if item:
            self.populate_detail(item)

    # -------------------------------------------------- 详情渲染

    def populate_detail(self, item: dict) -> None:
        self.detail_frame.grid()
        self.detail_open = True
        self.detail_title.configure(text=item["text"])
        self.detail_meta.configure(
            text=f"{KIND_LABEL[item['kind']]} · {STATUS_LABEL[item['status']]} · {format_time(item, '%Y-%m-%d %H:%M')}"
        )
        self._render_markup(item.get("detail", ""))
        self._fit_detail_height()
        self.detail_text.yview_moveto(0)

    def _fit_detail_height(self) -> None:
        """详情面板按内容实际像素高度伸缩，短的就小、长的最高 18 行再滚动。"""
        try:
            self.detail_text.update_idletasks()
            pixels = int(self.detail_text.count("1.0", "end-1c", "ypixels")[0])
        except (tk.TclError, TypeError, IndexError):
            pixels = 0
        if pixels <= 0:
            return
        line_space = tkfont.Font(root=self.root, font=self.font(10)).metrics("linespace")
        needed = -(-pixels // max(1, line_space))
        self.detail_text.configure(height=max(4, min(18, needed)))

    def hide_detail(self) -> None:
        self.detail_frame.grid_remove()
        self.detail_open = False

    def _render_markup(self, markup: str) -> None:
        widget = self.detail_text
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        text = (markup or "").replace("\r\n", "\n").strip("\n")
        if not text.strip():
            widget.insert("end", "（这条没有详细描述）", "empty")
        else:
            in_code = False
            for index, line in enumerate(text.split("\n")):
                if index:
                    widget.insert("end", "\n", "body")
                stripped = line.rstrip()
                if stripped.strip().startswith("```"):
                    in_code = not in_code
                    continue
                if in_code:
                    widget.insert("end", stripped, "codeblock")
                    continue
                if not stripped.strip():
                    continue
                if stripped.startswith("- "):
                    widget.insert("end", "•  ", "bullet")
                    self._insert_inline(widget, stripped[2:], "bullet")
                elif stripped.startswith("## "):
                    widget.insert("end", stripped[3:], "heading")
                else:
                    self._insert_inline(widget, stripped, "body")
        widget.configure(state="disabled")

    def _insert_inline(self, widget: tk.Text, text: str, base: str) -> None:
        position = 0
        for match in INLINE_PATTERN.finditer(text):
            if match.start() > position:
                widget.insert("end", text[position:match.start()], base)
            token = match.group(0)
            if token.startswith("**"):
                widget.insert("end", token[2:-2], ("bold", base))
            else:
                widget.insert("end", token[1:-1], ("code", base))
            position = match.end()
        if position < len(text):
            widget.insert("end", text[position:], base)

    # -------------------------------------------------- 动作

    def current_item(self) -> dict | None:
        if not self.selected_id:
            return None
        for item in self.data["items"]:
            if item["id"] == self.selected_id:
                return item
        return None

    def set_status(self, status: str) -> None:
        item = self.current_item()
        if not item or item.get("status") == status:
            return
        item["status"] = status
        item["updated"] = now_iso()
        self.save()
        self.refresh()
        if item["status"] == "fixed" and not self.show_fixed.get():
            self.selected_id = None
            self.selected_kind = None
            self.hide_detail()
        self.flash(f"已标记为「{STATUS_LABEL[status]}」")

    def add_from_entry(self, kind: str) -> None:
        text = self.entry.get().strip()
        if not text:
            self.entry.focus_set()
            return
        item = add_item(self.data, text, kind)
        self.entry.delete(0, "end")
        self.save()
        self.selected_kind = kind
        self.selected_id = item["id"]
        self.add_kind = kind
        self.refresh()
        self.trees[kind].selection_set(item["id"])
        self.trees[kind].focus(item["id"])
        self.trees[kind].see(item["id"])
        self.entry.focus_set()
        self.flash(f"已添加一条 {KIND_LABEL[kind]}")

    def delete_selected(self) -> None:
        item = self.current_item()
        if not item:
            return
        kind = item["kind"]
        if not self.confirm("删除这条记录？", item["text"]):
            return
        self.data["items"] = [row for row in self.data["items"] if row["id"] != item["id"]]
        self.selected_id = None
        self.selected_kind = None
        self.save()
        self.refresh()
        self.hide_detail()
        self.flash(f"已删除一条 {KIND_LABEL[kind]}")

    def confirm(self, title: str, message: str) -> bool:
        result = {"ok": False}
        dialog = tk.Toplevel(self.root)
        dialog.withdraw()
        dialog.title(title)
        dialog.configure(bg=COLOR["panel"])
        dialog.resizable(False, False)
        dialog.transient(self.root)

        tk.Label(
            dialog,
            text=title,
            bg=COLOR["panel"],
            fg=COLOR["fg"],
            font=self.font(11, "bold"),
            anchor="w",
            wraplength=self.px(380),
            justify="left",
        ).pack(anchor="w", padx=self.px(18), pady=(self.px(16), self.px(6)))
        tk.Label(
            dialog,
            text=message,
            bg=COLOR["panel"],
            fg=COLOR["muted"],
            font=self.font(9),
            anchor="w",
            wraplength=self.px(380),
            justify="left",
        ).pack(anchor="w", padx=self.px(18))

        row = tk.Frame(dialog, bg=COLOR["panel"])
        row.pack(fill="x", padx=self.px(18), pady=self.px(16))

        def close(value: bool) -> None:
            result["ok"] = value
            dialog.destroy()

        self.button(row, "取消", lambda: close(False), fg=COLOR["muted"]).pack(side="right")
        self.button(
            row, "删除", lambda: close(True), fg="#e8836f", bg="#2a1d1b", hover="#3a2723"
        ).pack(side="right", padx=(0, self.px(8)))

        dialog.update_idletasks()
        width, height = dialog.winfo_reqwidth(), dialog.winfo_reqheight()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - width) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - height) // 3
        dialog.geometry(f"+{max(0, x)}+{max(0, y)}")
        apply_dark_title_bar(dialog)
        dialog.deiconify()
        dialog.grab_set()
        dialog.focus_force()
        self.root.wait_window(dialog)
        return result["ok"]

    # -------------------------------------------------- 存取

    def save(self) -> None:
        try:
            self.last_mtime = save_data(self.path, self.data)
        except OSError as error:
            self.flash(f"保存失败：{error}")
            return
        self._render_status_line()

    def reload(self) -> None:
        self.data = load_data(self.path)
        self.refresh()
        self.flash("已重新读取文件")

    def poll_file(self) -> None:
        """外部（比如命令行 --add）改了文件，窗口自动跟上。"""
        try:
            mtime = os.path.getmtime(self.path)
        except OSError:
            mtime = None
        if mtime and mtime != self.last_mtime:
            self.last_mtime = mtime
            self.data = load_data(self.path)
            self.refresh()
            self.flash("已同步外部改动")
        self.later(1200, self.poll_file)

    def flash(self, message: str) -> None:
        self.dirty_note = message
        self._render_status_line()
        self.later(4000, lambda: self._clear_note(message))

    def _clear_note(self, message: str) -> None:
        if self.dirty_note == message:
            self.dirty_note = ""
            self._render_status_line()

    def _render_status_line(self) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        self.status_line.configure(text=self.dirty_note or f"已保存 {stamp}")

    def close(self) -> None:
        for job in self.jobs:
            try:
                self.root.after_cancel(job)
            except tk.TclError:
                pass
        self.jobs.clear()
        self.save()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


# ---------------------------------------------------------------- 命令行

def describe_item(item: dict, verbose: bool) -> list[str]:
    head = f"[{STATUS_LABEL[item['status']]}] {item['id']}  {item['text']}  ({format_time(item, '%Y-%m-%d %H:%M')})"
    if item.get("detail"):
        head += "  +详情" if not verbose else ""
    lines = [head]
    if verbose and item.get("detail"):
        for line in item["detail"].splitlines():
            lines.append(f"    {line}")
    return lines


def run_cli(args) -> int:
    path = os.path.abspath(args.path)
    data = load_data(path)

    if args.add is not None:
        text = args.add.strip()
        if not text:
            print("拒绝：简述是空的", file=sys.stderr)
            return 2
        item = add_item(data, text, args.kind or "bug", args.detail or "", args.status or "open")
        save_data(path, data)
        print(f"已记录 {KIND_LABEL[item['kind']]} [{STATUS_LABEL[item['status']]}] {item['id']}  {item['text']}")
        return 0

    if args.list:
        kinds = [args.kind] if args.kind else list(KINDS)
        summary = "  ·  ".join(
            f"{KIND_LABEL[name]} " + " / ".join(
                f"{STATUS_LABEL[status]} {count_status(data, name)[status]}"
                for status in ("open", "wontfix", "fixed")
            )
            for name in KINDS
        )
        print(f"{os.path.basename(path)}  ·  {summary}")
        for kind in kinds:
            rows = sorted_items(data, kind)
            print(f"\n{KIND_LABEL[kind]}")
            if not rows:
                print("  (空)")
                continue
            for item in rows:
                for line in describe_item(item, args.verbose):
                    print(line)
        return 0

    if args.mark:
        item_id, status_text = args.mark
        status = LABEL_STATUS.get(status_text, status_text)
        if status not in STATUS_ORDER:
            print("状态只能是 未处理/已读不修/已修（或 open/wontfix/fixed）", file=sys.stderr)
            return 2
        for item in data["items"]:
            if item["id"] == item_id:
                item["status"] = status
                item["updated"] = now_iso()
                save_data(path, data)
                print(f"{item_id} → {STATUS_LABEL[status]}")
                return 0
        print(f"没有 id 为 {item_id} 的记录", file=sys.stderr)
        return 1

    if args.set_detail:
        item_id, detail = args.set_detail
        for item in data["items"]:
            if item["id"] == item_id:
                item["detail"] = detail
                item["updated"] = now_iso()
                save_data(path, data)
                print(f"{item_id} 详情已更新（{len(detail)} 字）")
                return 0
        print(f"没有 id 为 {item_id} 的记录", file=sys.stderr)
        return 1

    if args.remove:
        for item in data["items"]:
            if item["id"] == args.remove:
                data["items"] = [row for row in data["items"] if row["id"] != args.remove]
                save_data(path, data)
                print(f"已删除 {args.remove}")
                return 0
        print(f"没有 id 为 {args.remove} 的记录", file=sys.stderr)
        return 1

    return -1


def main() -> int:
    parser = argparse.ArgumentParser(description="BUGList：项目内的 BUG / TODO 清单")
    parser.add_argument("path", help=".buglist 文件路径（不存在会新建）")
    parser.add_argument("--add", metavar="简述", help="追加一条后退出，不开窗口")
    parser.add_argument("--detail", metavar="详情", help="配合 --add：详细描述（支持 `代码`、**加粗**、- 列表）")
    parser.add_argument("--kind", choices=list(KINDS), help="bug 或 todo，默认 bug")
    parser.add_argument("--status", choices=list(STATUS_ORDER), help="配合 --add 指定初始状态")
    parser.add_argument("--list", action="store_true", help="在终端按状态列出，不开窗口")
    parser.add_argument("--verbose", action="store_true", help="配合 --list 输出详细描述")
    parser.add_argument("--mark", nargs=2, metavar=("ID", "状态"), help="改某条的状态")
    parser.add_argument("--set-detail", nargs=2, metavar=("ID", "详情"), help="补/改某条的详细描述")
    parser.add_argument("--remove", metavar="ID", help="删除某条")
    args = parser.parse_args()

    if args.add is not None or args.list or args.mark or args.set_detail or args.remove:
        return run_cli(args)

    enable_dpi_awareness()
    window = BugListWindow(args.path)
    window.run()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # 窗口化运行时没有控制台，把错误写到日志里
        import traceback

        try:
            log_path = os.path.join(TOOL_DIR, "buglist_ai_error.log")
            with open(log_path, "a", encoding="utf-8") as handle:
                handle.write(f"\n===== {now_iso()} =====\n")
                traceback.print_exc(file=handle)
        except OSError:
            pass
        raise




