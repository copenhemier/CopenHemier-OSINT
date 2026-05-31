import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import json
import re
import html
import webbrowser
from datetime import datetime
from urllib.parse import quote_plus
import requests


BG = "#0a0e0c"
BG_ELEV = "#0f1614"
BG_CARD = "#0d1311"
BORDER = "#1f3a32"
BORDER_BRIGHT = "#2c5d4d"
TEXT = "#d4e8df"
TEXT_DIM = "#6b8a7d"
TEXT_FAINT = "#3d544a"
ACCENT = "#00ff9c"
ACCENT_HOVER = "#4dffbc"
ACCENT_DIM = "#00b86e"
DANGER = "#ff5572"
WARNING = "#ffb84d"
INFO = "#66d9ff"

FONT_MONO = ("Consolas", 10)
FONT_MONO_SM = ("Consolas", 9)
FONT_MONO_XS = ("Consolas", 8)
FONT_DISPLAY = ("Segoe UI", 18, "bold")
FONT_HEADING = ("Consolas", 9, "bold")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}


def fetch_tiktok_profile(username):
    username = username.lstrip("@").strip()
    url = f"https://www.tiktok.com/@{quote_plus(username)}"

    try:
        resp = requests.get(url, headers=HEADERS, timeout=12)
    except Exception as e:
        return {"found": False, "error": f"Network error: {e}"}

    if resp.status_code == 404:
        return {"found": False, "error": "Profile not found"}
    if resp.status_code != 200:
        return {"found": False, "error": f"HTTP {resp.status_code}"}

    match = re.search(
        r'<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__"[^>]*>(.+?)</script>',
        resp.text, re.DOTALL,
    )
    if not match:
        return {"found": False, "error": "Could not parse page"}

    try:
        data = json.loads(html.unescape(match.group(1)))
    except json.JSONDecodeError:
        return {"found": False, "error": "JSON decode failed"}

    try:
        user_detail = data["__DEFAULT_SCOPE__"]["webapp.user-detail"]
    except KeyError:
        return {"found": False, "error": "Profile data missing"}

    if user_detail.get("statusCode") and user_detail.get("statusCode") != 0:
        return {"found": False, "error": user_detail.get("statusMsg", "Unavailable")}

    user_info = user_detail.get("userInfo", {})
    user = user_info.get("user", {})
    stats = user_info.get("stats", {}) or user_info.get("statsV2", {})

    if not user:
        return {"found": False, "error": "No profile data"}

    bio = user.get("signature", "") or ""
    bio_link = user.get("bioLink", {}).get("link") if user.get("bioLink") else None
    url_pattern = re.compile(r"https?://[^\s]+")
    external_links = list(set(url_pattern.findall(bio)))
    if bio_link and bio_link not in external_links:
        external_links.append(bio_link)

    tags = []
    if user.get("verified"): tags.append("Verified account")
    if user.get("privateAccount"): tags.append("Private account")
    if user.get("commerceUserInfo", {}).get("commerceUser"): tags.append("Business account")
    if user.get("region"): tags.append(f"Region: {user['region']}")
    if user.get("language"): tags.append(f"Language: {user['language']}")
    if user.get("ttSeller"): tags.append("TikTok seller")
    if external_links: tags.append(f"{len(external_links)} external link(s)")
    if re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", bio):
        tags.append("Email visible in bio")
    if re.search(r"\b\d{3}[-.\s]?\d{3,4}[-.\s]?\d{4}\b", bio):
        tags.append("Phone-like number in bio")

    platforms = {
        "Instagram":   f"https://www.instagram.com/{username}",
        "X / Twitter": f"https://x.com/{username}",
        "YouTube":     f"https://www.youtube.com/@{username}",
        "Twitch":      f"https://www.twitch.tv/{username}",
        "Reddit":      f"https://www.reddit.com/user/{username}",
        "GitHub":      f"https://github.com/{username}",
        "Snapchat":    f"https://www.snapchat.com/add/{username}",
        "Facebook":    f"https://www.facebook.com/{username}",
        "Threads":     f"https://www.threads.net/@{username}",
        "Pinterest":   f"https://www.pinterest.com/{username}/",
    }

    return {
        "found": True,
        "username": user.get("uniqueId", username),
        "display_name": user.get("nickname"),
        "user_id": user.get("id"),
        "sec_uid": user.get("secUid"),
        "bio": bio,
        "verified": bool(user.get("verified")),
        "private": bool(user.get("privateAccount")),
        "region": user.get("region"),
        "language": user.get("language"),
        "create_time": user.get("createTime"),
        "stats": {
            "followers": int(stats.get("followerCount", 0) or 0),
            "following": int(stats.get("followingCount", 0) or 0),
            "likes": int(stats.get("heartCount", 0) or stats.get("heart", 0) or 0),
            "videos": int(stats.get("videoCount", 0) or 0),
        },
        "external_links": external_links,
        "osint_tags": tags,
        "cross_platform": platforms,
        "profile_url": url,
        "google_dork": f'https://www.google.com/search?q=%22{quote_plus(username)}%22+site%3Atiktok.com',
    }


def fmt_num(n):
    if n is None: return "—"
    n = int(n)
    if n >= 1_000_000_000: return f"{n/1_000_000_000:.2f}B"
    if n >= 1_000_000:     return f"{n/1_000_000:.2f}M"
    if n >= 10_000:        return f"{n/1_000:.1f}K"
    return f"{n:,}"


def fmt_ts(ts):
    if not ts: return "—"
    try: return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
    except Exception: return "—"


class HoverButton(tk.Button):
    def __init__(self, master, hover_bg=None, hover_fg=None, **kw):
        super().__init__(master, **kw)
        self._bg = kw.get("bg", BG)
        self._fg = kw.get("fg", TEXT)
        self._hbg = hover_bg or BG_ELEV
        self._hfg = hover_fg or ACCENT
        self.bind("<Enter>", lambda e: self.config(bg=self._hbg, fg=self._hfg))
        self.bind("<Leave>", lambda e: self.config(bg=self._bg, fg=self._fg))


class LeechApp:
    def __init__(self, root):
        self.root = root
        self.last_report = None
        self.result_widgets = []
        self._setup_root()
        self._build_ui()
        self._tick_clock()

    def _setup_root(self):
        self.root.title("CopenHemier OSINT")
        self.root.geometry("960x820")
        self.root.configure(bg=BG)
        self.root.minsize(720, 600)

    def _build_ui(self):
        topbar = tk.Frame(self.root, bg=BG_ELEV, height=40)
        topbar.pack(fill="x", side="top")
        topbar.pack_propagate(False)
        sep = tk.Frame(self.root, bg=BORDER, height=1)
        sep.pack(fill="x")

        brand = tk.Frame(topbar, bg=BG_ELEV)
        brand.pack(side="left", padx=18, pady=10)
        tk.Label(brand, text="●", bg=BG_ELEV, fg=ACCENT, font=("Consolas", 11)).pack(side="left", padx=(0,8))
        tk.Label(brand, text="CopenHemier OSINT", bg=BG_ELEV, fg=ACCENT,
                 font=("Consolas", 10, "bold")).pack(side="left")

        status = tk.Frame(topbar, bg=BG_ELEV)
        status.pack(side="right", padx=18, pady=10)
        self.clock_lbl = tk.Label(status, text="--:--:--", bg=BG_ELEV, fg=TEXT_DIM, font=FONT_MONO_SM)
        self.clock_lbl.pack(side="right", padx=(8,0))
        tk.Label(status, text="│", bg=BG_ELEV, fg=TEXT_FAINT, font=FONT_MONO_SM).pack(side="right", padx=6)
        tk.Label(status, text="● ONLINE", bg=BG_ELEV, fg=TEXT_DIM, font=FONT_MONO_SM).pack(side="right")

        self.canvas = tk.Canvas(self.root, bg=BG, highlightthickness=0)
        scrollbar = tk.Scrollbar(self.root, orient="vertical", command=self.canvas.yview,
                                  bg=BG_ELEV, troughcolor=BG, activebackground=ACCENT_DIM,
                                  bd=0, highlightthickness=0)
        self.main = tk.Frame(self.canvas, bg=BG)
        self.main_id = self.canvas.create_window((0,0), window=self.main, anchor="nw")

        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def _on_main_configure(e):
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        def _on_canvas_configure(e):
            self.canvas.itemconfig(self.main_id, width=e.width)
        self.main.bind("<Configure>", _on_main_configure)
        self.canvas.bind("<Configure>", _on_canvas_configure)

        def _on_mousewheel(e):
            self.canvas.yview_scroll(int(-1*(e.delta/120)), "units")
        self.root.bind_all("<MouseWheel>", _on_mousewheel)

        banner = (
            " ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\n"
            " ┃   CopenHemier  OSINT V.1                        ┃\n"
            " ┃   public-source lookup terminal                 ┃\n"
            " ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛"
        )
        tk.Label(self.main, text=banner, bg=BG, fg=ACCENT, font=("Consolas", 9),
                 justify="left").pack(anchor="w", padx=24, pady=(20, 6))
        tk.Label(self.main, text="$ Only publicly available data is queried. Use responsibly.",
                 bg=BG, fg=TEXT_DIM, font=FONT_MONO_SM).pack(anchor="w", padx=24, pady=(0,18))

        tk.Label(self.main, text="▸ TARGET HANDLE", bg=BG, fg=ACCENT_DIM,
                 font=FONT_HEADING).pack(anchor="w", padx=24, pady=(6, 6))

        search_outer = tk.Frame(self.main, bg=BORDER_BRIGHT)
        search_outer.pack(fill="x", padx=24, pady=(0, 10))
        search_frame = tk.Frame(search_outer, bg=BG_ELEV)
        search_frame.pack(fill="x", padx=1, pady=1)

        tk.Label(search_frame, text="@", bg=BG_ELEV, fg=ACCENT,
                 font=("Consolas", 14, "bold"), padx=14).pack(side="left")
        tk.Frame(search_frame, bg=BORDER, width=1).pack(side="left", fill="y")

        self.entry = tk.Entry(search_frame, bg=BG_ELEV, fg=TEXT, insertbackground=ACCENT,
                              font=("Consolas", 12), relief="flat", bd=0,
                              highlightthickness=0)
        self.entry.pack(side="left", fill="x", expand=True, padx=10, pady=12)
        self.entry.bind("<Return>", lambda e: self.lookup())

        self.run_btn = tk.Button(search_frame, text="EXECUTE ▶", bg=ACCENT, fg=BG,
                                  font=("Consolas", 10, "bold"), relief="flat", bd=0,
                                  padx=22, pady=12, cursor="hand2",
                                  activebackground=ACCENT_HOVER, activeforeground=BG,
                                  command=self.lookup)
        self.run_btn.pack(side="right")

        quick = tk.Frame(self.main, bg=BG)
        quick.pack(anchor="w", padx=24, pady=(0, 18))
        tk.Label(quick, text="Try:", bg=BG, fg=TEXT_FAINT, font=FONT_MONO_SM).pack(side="left")
        for name in ["charlidamelio", "khaby.lame", "mrbeast"]:
            b = HoverButton(quick, text=name, bg=BG, fg=TEXT_DIM, font=FONT_MONO_SM,
                            relief="flat", bd=0, cursor="hand2", padx=8,
                            hover_bg=BG, hover_fg=ACCENT,
                            command=lambda n=name: self._set_quick(n))
            b.pack(side="left", padx=2)

        tk.Label(self.main, text="▸ QUERY LOG", bg=BG, fg=ACCENT_DIM,
                 font=FONT_HEADING).pack(anchor="w", padx=24, pady=(4, 6))

        log_outer = tk.Frame(self.main, bg=BORDER)
        log_outer.pack(fill="x", padx=24, pady=(0,20))
        log_inner = tk.Frame(log_outer, bg="#060908")
        log_inner.pack(fill="both", padx=1, pady=1)

        log_header = tk.Frame(log_inner, bg=BG_ELEV)
        log_header.pack(fill="x")
        for c in [DANGER, WARNING, ACCENT]:
            tk.Label(log_header, text="●", bg=BG_ELEV, fg=c, font=("Consolas", 9)).pack(side="left", padx=(8 if c==DANGER else 2, 0), pady=4)
        tk.Label(log_header, text="// query.log", bg=BG_ELEV, fg=TEXT_DIM,
                 font=FONT_MONO_XS).pack(side="right", padx=10, pady=4)
        tk.Frame(log_inner, bg=BORDER, height=1).pack(fill="x")

        self.log_text = tk.Text(log_inner, bg="#060908", fg=TEXT_DIM, font=FONT_MONO_SM,
                                height=9, relief="flat", bd=0, wrap="word", padx=14, pady=10,
                                insertbackground=ACCENT, selectbackground=BORDER_BRIGHT,
                                highlightthickness=0)
        self.log_text.pack(fill="both", expand=True)
        self.log_text.tag_configure("muted", foreground=TEXT_FAINT)
        self.log_text.tag_configure("ok", foreground=ACCENT)
        self.log_text.tag_configure("warn", foreground=WARNING)
        self.log_text.tag_configure("err", foreground=DANGER)
        self.log_text.tag_configure("info", foreground=INFO)
        self._log("Awaiting target input...", "muted")
        self.log_text.config(state="disabled")

        self.results_frame = tk.Frame(self.main, bg=BG)
        self.results_frame.pack(fill="x", padx=24, pady=(0, 30))

    def _set_quick(self, name):
        self.entry.delete(0, "end")
        self.entry.insert(0, name)
        self.lookup()

    def _log(self, text, tag=""):
        self.log_text.config(state="normal")
        t = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert("end", f"[{t}] {text}\n", tag if tag else "")
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def _tick_clock(self):
        self.clock_lbl.config(text=datetime.now().strftime("%H:%M:%S"))
        self.root.after(1000, self._tick_clock)

    def lookup(self):
        raw = self.entry.get().strip().lstrip("@")
        if not raw:
            self._log("No username provided.", "warn")
            return
        if not re.match(r"^[\w.\-]{2,30}$", raw):
            self._log("Invalid username format.", "err")
            return

        self.run_btn.config(state="disabled", text="WORKING...")
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.config(state="disabled")
        self._log("Initiating lookup...", "info")
        self._log(f"Target: @{raw}", "info")
        self._log(f"GET tiktok.com/@{raw} ...", "muted")

        for w in self.results_frame.winfo_children():
            w.destroy()

        threading.Thread(target=self._do_lookup, args=(raw,), daemon=True).start()

    def _do_lookup(self, username):
        data = fetch_tiktok_profile(username)
        self.root.after(0, self._on_result, data)

    def _on_result(self, data):
        self.run_btn.config(state="normal", text="EXECUTE ▶")

        if not data.get("found"):
            self._log(f"Lookup failed: {data.get('error')}", "err")
            err_outer = tk.Frame(self.results_frame, bg=DANGER)
            err_outer.pack(fill="x", pady=8)
            err_inner = tk.Frame(err_outer, bg="#2b1418")
            err_inner.pack(fill="x", padx=1, pady=1)
            tk.Label(err_inner, text=f"⚠   {data.get('error', 'Unknown error')}",
                     bg="#2b1418", fg=DANGER, font=FONT_MONO,
                     padx=16, pady=14).pack(anchor="w")
            return

        self._log("Page fetched. Parsing JSON state...", "muted")
        self._log("JSON extracted.", "ok")
        self._log(f"Display name: {data['display_name']}", "ok")
        self._log(
            f"Followers: {fmt_num(data['stats']['followers'])} │ "
            f"Likes: {fmt_num(data['stats']['likes'])} │ "
            f"Videos: {fmt_num(data['stats']['videos'])}", "ok")
        if data['verified']: self._log("VERIFIED account.", "info")
        if data['private']: self._log("PRIVATE account.", "warn")
        if data['external_links']:
            self._log(f"{len(data['external_links'])} external link(s) found.", "info")
        self._log(f"Indicators: {len(data['osint_tags'])}", "info")
        self._log("Lookup complete. ▒", "ok")

        self.last_report = data
        self._render_results(data)

    def _card(self, parent, title, meta=""):
        outer = tk.Frame(parent, bg=BORDER)
        inner = tk.Frame(outer, bg=BG_CARD)
        inner.pack(fill="both", padx=1, pady=1)

        header = tk.Frame(inner, bg=BG_CARD)
        header.pack(fill="x", padx=16, pady=(12, 8))
        tk.Label(header, text=title, bg=BG_CARD, fg=ACCENT,
                 font=FONT_HEADING).pack(side="left")
        if meta:
            tk.Label(header, text=meta, bg=BG_CARD, fg=TEXT_FAINT,
                     font=FONT_MONO_XS).pack(side="right")
        sep = tk.Frame(inner, bg=BORDER, height=1)
        sep.pack(fill="x", padx=16)

        body = tk.Frame(inner, bg=BG_CARD)
        body.pack(fill="x", padx=16, pady=(10, 14))
        return outer, body

    def _render_results(self, d):
        prof, body = self._card(self.results_frame, "▸ TARGET PROFILE",
                                 f"region: {d['region']}" if d['region'] else "—")
        prof.pack(fill="x", pady=(0, 10))

        name_row = tk.Frame(body, bg=BG_CARD)
        name_row.pack(anchor="w", fill="x")
        tk.Label(name_row, text=d['display_name'] or d['username'],
                 bg=BG_CARD, fg=TEXT, font=FONT_DISPLAY).pack(side="left")
        if d['verified']:
            tk.Label(name_row, text=" ✓", bg=BG_CARD, fg=ACCENT,
                     font=("Segoe UI", 14, "bold")).pack(side="left")
        tk.Label(body, text=f"@{d['username']}", bg=BG_CARD, fg=ACCENT_DIM,
                 font=FONT_MONO_SM).pack(anchor="w", pady=(2,8))

        bio_frame = tk.Frame(body, bg=BG_ELEV)
        bio_frame.pack(fill="x", pady=(6,0))
        tk.Frame(bio_frame, bg=ACCENT_DIM, width=2).pack(side="left", fill="y")
        bio = d['bio'] or "(no bio)"
        tk.Label(bio_frame, text=bio, bg=BG_ELEV, fg=TEXT_DIM,
                 font=FONT_MONO, justify="left", wraplength=820,
                 padx=12, pady=10).pack(side="left", fill="x", expand=True, anchor="w")

        metrics_outer, mbody = self._card(self.results_frame, "▸ METRICS")
        metrics_outer.pack(fill="x", pady=(0, 10))
        grid = tk.Frame(mbody, bg=BG_CARD)
        grid.pack(fill="x")
        for col, (label, val) in enumerate([
            ("FOLLOWERS", fmt_num(d['stats']['followers'])),
            ("FOLLOWING", fmt_num(d['stats']['following'])),
            ("TOTAL LIKES", fmt_num(d['stats']['likes'])),
            ("VIDEOS", fmt_num(d['stats']['videos'])),
        ]):
            stat = tk.Frame(grid, bg=BG_ELEV)
            stat.grid(row=0, column=col, sticky="nsew", padx=(0 if col==0 else 6, 0))
            grid.columnconfigure(col, weight=1, uniform="stat")
            tk.Frame(stat, bg=ACCENT_DIM, width=2).pack(side="left", fill="y")
            inner_stat = tk.Frame(stat, bg=BG_ELEV)
            inner_stat.pack(side="left", fill="both", expand=True, padx=12, pady=10)
            tk.Label(inner_stat, text=val, bg=BG_ELEV, fg=ACCENT,
                     font=("Segoe UI", 16, "bold")).pack(anchor="w")
            tk.Label(inner_stat, text=label, bg=BG_ELEV, fg=TEXT_DIM,
                     font=FONT_MONO_XS).pack(anchor="w")

        ident_outer, ibody = self._card(self.results_frame, "▸ TECHNICAL IDENTIFIERS")
        ident_outer.pack(fill="x", pady=(0, 10))
        rows = [
            ("user_id", d['user_id'] or "—"),
            ("sec_uid", d['sec_uid'] or "—"),
            ("region", d['region'] or "—"),
            ("language", d['language'] or "—"),
            ("private", "YES" if d['private'] else "no"),
            ("created", fmt_ts(d['create_time'])),
        ]
        for r, (k, v) in enumerate(rows):
            tk.Label(ibody, text=k, bg=BG_CARD, fg=TEXT_FAINT,
                     font=FONT_MONO_SM, anchor="w", width=10).grid(row=r, column=0, sticky="w", pady=3)
            tk.Label(ibody, text=str(v), bg=BG_CARD, fg=TEXT,
                     font=FONT_MONO_SM, anchor="w", wraplength=720,
                     justify="left").grid(row=r, column=1, sticky="w", pady=3, padx=(10,0))

        tags_outer, tbody = self._card(self.results_frame, "▸ LOOKUP INDICATORS")
        tags_outer.pack(fill="x", pady=(0, 10))
        if d['osint_tags']:
            tag_wrap = tk.Frame(tbody, bg=BG_CARD)
            tag_wrap.pack(anchor="w", fill="x")
            for i, tag in enumerate(d['osint_tags']):
                is_warn = bool(re.search(r"private|email|phone", tag, re.I))
                fg = WARNING if is_warn else ACCENT
                bg_sub = "#1a1208" if is_warn else "#082017"
                bord = WARNING if is_warn else ACCENT_DIM
                lbl_outer = tk.Frame(tag_wrap, bg=bord)
                lbl_outer.pack(side="left", padx=(0 if i==0 else 6, 0), pady=3)
                tk.Label(lbl_outer, text=tag, bg=bg_sub, fg=fg,
                         font=FONT_MONO_XS, padx=10, pady=4).pack(padx=1, pady=1)
        else:
            tk.Label(tbody, text="No notable indicators detected.",
                     bg=BG_CARD, fg=TEXT_FAINT, font=("Consolas", 9, "italic")).pack(anchor="w")

        links_outer, lbody = self._card(self.results_frame, "▸ EXTERNAL LINKS DETECTED")
        links_outer.pack(fill="x", pady=(0, 10))
        if d['external_links']:
            for url in d['external_links']:
                lf = tk.Frame(lbody, bg=BG_ELEV)
                lf.pack(fill="x", pady=2)
                tk.Frame(lf, bg=INFO, width=2).pack(side="left", fill="y")
                b = HoverButton(lf, text=f"↗  {url}", bg=BG_ELEV, fg=INFO,
                                font=FONT_MONO_SM, relief="flat", bd=0, cursor="hand2",
                                anchor="w", padx=12, pady=8,
                                hover_bg="#1a2724", hover_fg="#99e6ff",
                                command=lambda u=url: webbrowser.open(u))
                b.pack(side="left", fill="x", expand=True)
        else:
            tk.Label(lbody, text="No external links found.",
                     bg=BG_CARD, fg=TEXT_FAINT, font=("Consolas", 9, "italic")).pack(anchor="w")

        cross_outer, cbody = self._card(self.results_frame, "▸ CROSS-PLATFORM RECON",
                                          "manual verification recommended")
        cross_outer.pack(fill="x", pady=(0, 10))
        cgrid = tk.Frame(cbody, bg=BG_CARD)
        cgrid.pack(fill="x")
        cols = 3
        for i, (name, url) in enumerate(d['cross_platform'].items()):
            r, c = divmod(i, cols)
            cgrid.columnconfigure(c, weight=1, uniform="plat")
            pframe = tk.Frame(cgrid, bg=BORDER)
            pframe.grid(row=r, column=c, sticky="nsew", padx=(0 if c==0 else 6, 0), pady=3)
            btn = HoverButton(pframe, bg=BG_ELEV, fg=TEXT_DIM, font=FONT_MONO_SM,
                              relief="flat", bd=0, cursor="hand2",
                              hover_bg="#0d2820", hover_fg=ACCENT,
                              command=lambda u=url: webbrowser.open(u))
            btn.pack(fill="both", padx=1, pady=1)
            row = tk.Frame(btn, bg=BG_ELEV)
            row.pack(fill="x", padx=12, pady=8)
            tk.Label(row, text=name, bg=BG_ELEV, fg=TEXT_DIM, font=FONT_MONO_SM).pack(side="left")
            tk.Label(row, text=f"@{d['username']}  ↗", bg=BG_ELEV, fg=TEXT_FAINT,
                     font=FONT_MONO_XS).pack(side="right")
            btn.bind("<Enter>", lambda e, b=btn, r=row: self._hover_plat(b, r, True))
            btn.bind("<Leave>", lambda e, b=btn, r=row: self._hover_plat(b, r, False))

        act_outer, abody = self._card(self.results_frame, "▸ ADDITIONAL TOOLS")
        act_outer.pack(fill="x", pady=(0, 10))
        actions = tk.Frame(abody, bg=BG_CARD)
        actions.pack(fill="x")
        actions_list = [
            ("▸ Open TikTok profile", lambda: webbrowser.open(d['profile_url'])),
            ("▸ Google dork search", lambda: webbrowser.open(d['google_dork'])),
            ("▸ Export JSON report", self._export_json),
            ("▸ Copy summary", self._copy_summary),
        ]
        for i, (label, cmd) in enumerate(actions_list):
            af = tk.Frame(actions, bg=BORDER_BRIGHT)
            af.pack(side="left", padx=(0 if i==0 else 8, 0))
            b = HoverButton(af, text=label, bg=BG_CARD, fg=TEXT, font=FONT_MONO_SM,
                            relief="flat", bd=0, cursor="hand2", padx=14, pady=8,
                            hover_bg="#0d2820", hover_fg=ACCENT, command=cmd)
            b.pack(padx=1, pady=1)

        self.canvas.update_idletasks()
        self.canvas.yview_moveto(0)

    def _hover_plat(self, btn, row, hovering):
        bg = "#0d2820" if hovering else BG_ELEV
        fg = ACCENT if hovering else TEXT_DIM
        btn.config(bg=bg)
        row.config(bg=bg)
        for child in row.winfo_children():
            child.config(bg=bg)
            current_fg = child.cget("fg")
            if current_fg in (TEXT_DIM, ACCENT):
                child.config(fg=fg)

    def _export_json(self):
        if not self.last_report:
            return
        fn = filedialog.asksaveasfilename(
            defaultextension=".json",
            initialfile=f"leech_{self.last_report['username']}_{int(datetime.now().timestamp())}.json",
            filetypes=[("JSON", "*.json"), ("All files", "*.*")],
        )
        if not fn: return
        try:
            with open(fn, "w", encoding="utf-8") as f:
                json.dump(self.last_report, f, indent=2, ensure_ascii=False)
            self._log(f"Report exported: {fn}", "ok")
        except Exception as e:
            self._log(f"Export failed: {e}", "err")

    def _copy_summary(self):
        if not self.last_report: return
        d = self.last_report
        summary = (
            f"=== LEECH LOOKUP REPORT ===\n"
            f"Target:     @{d['username']}\n"
            f"Name:       {d['display_name'] or '—'}\n"
            f"Verified:   {'YES' if d['verified'] else 'no'}\n"
            f"Private:    {'YES' if d['private'] else 'no'}\n"
            f"Region:     {d['region'] or '—'}\n"
            f"Language:   {d['language'] or '—'}\n"
            f"Followers:  {fmt_num(d['stats']['followers'])}\n"
            f"Following:  {fmt_num(d['stats']['following'])}\n"
            f"Likes:      {fmt_num(d['stats']['likes'])}\n"
            f"Videos:     {fmt_num(d['stats']['videos'])}\n"
            f"User ID:    {d['user_id'] or '—'}\n"
            f"Bio:        {(d['bio'] or '').replace(chr(10), ' / ')}\n"
            f"Links:      {', '.join(d['external_links']) or 'none'}\n"
            f"Indicators: {' │ '.join(d['osint_tags']) or 'none'}\n"
        )
        self.root.clipboard_clear()
        self.root.clipboard_append(summary)
        self._log("Summary copied to clipboard.", "ok")


if __name__ == "__main__":
    root = tk.Tk()
    app = LeechApp(root)
    root.mainloop()