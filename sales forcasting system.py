# ============================================================
#  ◈ SalesOracle — Sales Forecasting & Analytics System
#  Converted from React/JSX  →  Pure Python 3 + tkinter
#  Run : Open in IDLE 3.13  →  F5  (or  python sales_forecasting.py)
#
#  Standard-library only for GUI (tkinter).
#  matplotlib required for charts:  pip install matplotlib
#  For AI Insights tab you also need:
#      pip install anthropic          (optional – tab still works without it)
# ============================================================

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import random
import math
import threading
from datetime import date, timedelta

# ── optional imports ──────────────────────────────────────────────────────────
try:
    import matplotlib
    matplotlib.use("TkAgg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    HAS_MPL = True
except ImportError:
    HAS_MPL = False

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

# ── colour palette (mirrors JSX) ──────────────────────────────────────────────
C = {
    "bg":        "#0a0e1a",
    "surface":   "#111827",
    "surfaceHi": "#1a2335",
    "border":    "#1f2d45",
    "accent":    "#00d4ff",
    "accentDim": "#0099bb",
    "green":     "#00e5a0",
    "amber":     "#ffb800",
    "red":       "#ff4d6a",
    "text":      "#e2eaf6",
    "muted":     "#5a7099",
}

PRODUCTS = ["P001", "P002", "P003", "P004", "P005"]
STORES   = ["S01",  "S02",  "S03",  "S04"]
HOLIDAYS = ["None", "Diwali", "Christmas", "New Year", "Holi"]

# ── data generation ───────────────────────────────────────────────────────────
def generate_dataset(rows: int = 60, seed: int = 42) -> list[dict]:
    random.seed(seed)
    dataset = []
    start = date(2024, 1, 1)
    for i in range(rows):
        d        = start + timedelta(days=i * 6)
        promo    = random.random() > 0.65
        holiday  = (HOLIDAYS[random.randint(1, 4)]
                    if random.random() > 0.8 else "None")
        base     = random.randint(40, 200)
        units    = (base
                    + (random.randint(20, 60) if promo else 0)
                    + (random.randint(30, 80) if holiday != "None" else 0))
        revenue  = units * random.randint(150, 500)
        dataset.append({
            "date":       d.isoformat(),
            "product_id": PRODUCTS[i % len(PRODUCTS)],
            "store_id":   STORES[i % len(STORES)],
            "units_sold": units,
            "revenue":    revenue,
            "promotion":  promo,
            "holiday":    holiday,
        })
    return dataset

# ── linear regression forecast ────────────────────────────────────────────────
def linear_forecast(data: list[dict], periods: int = 10) -> list[dict]:
    n  = len(data)
    if n < 2:
        return []
    xs = list(range(n))
    ys = [r["units_sold"] for r in data]
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((xs[i] - mx) * (ys[i] - my) for i in range(n))
    den = sum((x - mx) ** 2 for x in xs) or 1
    m   = num / den
    b   = my - m * mx

    last = date.fromisoformat(data[-1]["date"])
    result = []
    for i in range(periods):
        fd = last + timedelta(days=(i + 1) * 6)
        y  = max(0, round(m * (n + i) + b))
        result.append({"date": fd.isoformat(), "units_sold": y, "forecast": True})
    return result

# ── summary stats ─────────────────────────────────────────────────────────────
def compute_stats(filtered: list[dict], forecast: list[dict]) -> dict:
    total_units   = sum(r["units_sold"] for r in filtered)
    total_revenue = sum(r["revenue"]    for r in filtered)
    promo_rows    = [r for r in filtered if r["promotion"]]
    holiday_rows  = [r for r in filtered if r["holiday"] != "None"]
    promo_lift    = (round(sum(r["units_sold"] for r in promo_rows)   / len(promo_rows))
                     if promo_rows else 0)
    holiday_lift  = (round(sum(r["units_sold"] for r in holiday_rows) / len(holiday_rows))
                     if holiday_rows else 0)
    fc_t1         = forecast[0]["units_sold"] if forecast else 0
    return {
        "total_units":   total_units,
        "total_revenue": total_revenue,
        "promo_lift":    promo_lift,
        "holiday_lift":  holiday_lift,
        "fc_t1":         fc_t1,
        "records":       len(filtered),
    }

# ── AI helpers ────────────────────────────────────────────────────────────────
def call_claude_sync(prompt: str) -> str:
    if not HAS_ANTHROPIC:
        return ("anthropic package not installed.\n"
                "Run:  pip install anthropic\n"
                "Then restart and try again.")
    try:
        client = anthropic.Anthropic()          # reads ANTHROPIC_API_KEY env var
        msg = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text
    except Exception as e:
        return f"Error calling Claude API: {e}"

# ══════════════════════════════════════════════════════════════════════════════
#  GUI
# ══════════════════════════════════════════════════════════════════════════════
class SalesOracleApp(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("◈ SalesOracle — Sales Forecasting & Analytics")
        self.geometry("1100x760")
        self.minsize(900, 620)
        self.configure(bg=C["bg"])

        # state
        self.all_data      = generate_dataset(60)
        self.filter_product = tk.StringVar(value="All")
        self.filter_store   = tk.StringVar(value="All")
        self.active_tab     = tk.StringVar(value="dashboard")
        self.chat_history: list[dict] = []

        self._build_header()
        self._build_tabs()
        self._refresh()

    # ── header ────────────────────────────────────────────────────────────────
    def _build_header(self):
        hdr = tk.Frame(self, bg=C["surface"], pady=10)
        hdr.pack(fill="x")

        title_frame = tk.Frame(hdr, bg=C["surface"])
        title_frame.pack(side="left", padx=20)

        tk.Label(title_frame, text="◈ SalesOracle", font=("Georgia", 18, "bold"),
                 fg=C["accent"], bg=C["surface"]).pack(anchor="w")
        tk.Label(title_frame, text="Sales Forecasting & Analytics System",
                 font=("Courier", 9), fg=C["muted"], bg=C["surface"]).pack(anchor="w")

        # filters
        flt = tk.Frame(hdr, bg=C["surface"])
        flt.pack(side="right", padx=20)
        self._make_filter(flt, "Product", self.filter_product,
                          ["All"] + PRODUCTS)
        self._make_filter(flt, "Store",   self.filter_store,
                          ["All"] + STORES)

        # tabs
        tab_bar = tk.Frame(self, bg=C["bg"], pady=6)
        tab_bar.pack(fill="x", padx=4)
        self._tab_buttons = {}
        for name in ("dashboard", "data", "forecast", "chat"):
            b = tk.Button(tab_bar, text=name.upper(),
                          font=("Courier", 10, "bold"),
                          relief="flat", bd=0, pady=6, padx=16,
                          cursor="hand2",
                          command=lambda n=name: self._switch_tab(n))
            b.pack(side="left")
            self._tab_buttons[name] = b
        self._update_tab_styles()

    def _make_filter(self, parent, label, var, options):
        f = tk.Frame(parent, bg=C["surface"])
        f.pack(side="left", padx=6)
        tk.Label(f, text=label, font=("Courier", 9), fg=C["muted"],
                 bg=C["surface"]).pack(anchor="w")
        cb = ttk.Combobox(f, textvariable=var, values=options,
                          state="readonly", width=9,
                          font=("Courier", 9))
        cb.pack()
        cb.bind("<<ComboboxSelected>>", lambda _: self._refresh())

        # style
        style = ttk.Style()
        style.theme_use("default")
        style.configure("TCombobox",
                         fieldbackground=C["surfaceHi"],
                         background=C["surfaceHi"],
                         foreground=C["text"],
                         selectbackground=C["accent"],
                         selectforeground=C["bg"])

    def _switch_tab(self, name):
        self.active_tab.set(name)
        self._update_tab_styles()
        self._show_tab(name)

    def _update_tab_styles(self):
        act = self.active_tab.get()
        for name, btn in self._tab_buttons.items():
            if name == act:
                btn.configure(fg=C["accent"], bg=C["surfaceHi"],
                              activeforeground=C["accent"],
                              activebackground=C["surfaceHi"])
            else:
                btn.configure(fg=C["muted"], bg=C["bg"],
                              activeforeground=C["text"],
                              activebackground=C["bg"])

    # ── tab container ─────────────────────────────────────────────────────────
    def _build_tabs(self):
        self.tab_frame = tk.Frame(self, bg=C["bg"])
        self.tab_frame.pack(fill="both", expand=True, padx=16, pady=10)

        self.tabs: dict[str, tk.Frame] = {}
        for name in ("dashboard", "data", "forecast", "chat"):
            f = tk.Frame(self.tab_frame, bg=C["bg"])
            self.tabs[name] = f

        self._build_dashboard()
        self._build_data_tab()
        self._build_forecast_tab()
        self._build_chat_tab()
        self._show_tab("dashboard")

    def _show_tab(self, name):
        for n, f in self.tabs.items():
            f.pack_forget()
        self.tabs[name].pack(fill="both", expand=True)
        self._update_tab_styles()

    # ── refresh on filter change ───────────────────────────────────────────────
    def _refresh(self):
        fp = self.filter_product.get()
        fs = self.filter_store.get()
        self._filtered = [
            r for r in self.all_data
            if (fp == "All" or r["product_id"] == fp)
            and (fs == "All" or r["store_id"] == fs)
        ]
        self._forecast = linear_forecast(self._filtered[-20:], 10)
        self._stats    = compute_stats(self._filtered, self._forecast)
        self._refresh_dashboard()
        self._refresh_data_tab()
        self._refresh_forecast_tab()

    # ─────────────────────────────────────────────────────────────────────────
    #  DASHBOARD TAB
    # ─────────────────────────────────────────────────────────────────────────
    def _build_dashboard(self):
        tab = self.tabs["dashboard"]

        # stat cards row
        self.stat_frame = tk.Frame(tab, bg=C["bg"])
        self.stat_frame.pack(fill="x", pady=(0, 12))

        # charts row
        self.chart_frame = tk.Frame(tab, bg=C["bg"])
        self.chart_frame.pack(fill="x", pady=(0, 12))

        # AI insights
        ai_box = tk.Frame(tab, bg=C["surfaceHi"],
                          highlightbackground=C["border"],
                          highlightthickness=1)
        ai_box.pack(fill="x", pady=(0, 6))

        ai_head = tk.Frame(ai_box, bg=C["surfaceHi"])
        ai_head.pack(fill="x", padx=16, pady=(10, 6))
        tk.Label(ai_head, text="✦  AI Sales Insights",
                 font=("Courier", 9, "bold"), fg=C["muted"],
                 bg=C["surfaceHi"]).pack(side="left")
        tk.Button(ai_head, text="Generate Insights",
                  font=("Courier", 10, "bold"),
                  fg=C["bg"], bg=C["accent"], relief="flat",
                  padx=10, pady=4, cursor="hand2",
                  command=self._fetch_ai_insight).pack(side="right")

        self.ai_label = tk.Label(ai_box,
                                 text='Click "Generate Insights" for AI-powered recommendations.',
                                 font=("Segoe UI", 10), fg=C["muted"],
                                 bg=C["surfaceHi"], wraplength=900,
                                 justify="left", padx=16, pady=10)
        self.ai_label.pack(fill="x")

        self._dash_chart_canvas = None

    def _refresh_dashboard(self):
        s = self._stats
        # clear stat cards
        for w in self.stat_frame.winfo_children():
            w.destroy()

        cards = [
            ("Total Units Sold",  f"{s['total_units']:,}",      "↑ trend",            C["accent"]),
            ("Total Revenue",     f"₹{s['total_revenue']//1000}K", "across stores",   C["green"]),
            ("Promo Avg Units",   str(s["promo_lift"]),          "per promo period",   C["amber"]),
            ("Holiday Avg Units", str(s["holiday_lift"]),        "during holidays",    C["red"]),
            ("Forecast T+1",      str(s["fc_t1"]),               "next period",        C["accentDim"]),
            ("Records",           str(s["records"]),
             f"{len(PRODUCTS)} products · {len(STORES)} stores", C["muted"]),
        ]
        for label, val, sub, col in cards:
            self._stat_card(self.stat_frame, label, val, sub, col)

        # chart strip
        if not HAS_MPL:
            return
        for w in self.chart_frame.winfo_children():
            w.destroy()

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 2.4),
                                        facecolor=C["bg"])
        fig.subplots_adjust(left=0.06, right=0.98, top=0.82, bottom=0.18,
                            wspace=0.35)

        # product bar
        prod_vals  = [sum(r["units_sold"] for r in self.all_data
                         if r["product_id"] == p) for p in PRODUCTS]
        self._plot_bars(ax1, PRODUCTS, prod_vals, C["accent"],
                        "Units by Product")

        # store bar
        store_vals = [sum(r["revenue"] for r in self.all_data
                         if r["store_id"] == s) // 1000 for s in STORES]
        self._plot_bars(ax2, STORES, store_vals, C["green"],
                        "Revenue by Store (₹K)")

        canvas = FigureCanvasTkAgg(fig, master=self.chart_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="x")
        plt.close(fig)

    def _stat_card(self, parent, label, val, sub, col):
        card = tk.Frame(parent, bg=C["surfaceHi"],
                        highlightbackground=col, highlightthickness=1,
                        padx=14, pady=10)
        card.pack(side="left", expand=True, fill="both", padx=4, pady=2)
        tk.Label(card, text=label, font=("Courier", 8),
                 fg=C["muted"], bg=C["surfaceHi"]).pack(anchor="w")
        tk.Label(card, text=val, font=("Georgia", 20, "bold"),
                 fg=C["text"], bg=C["surfaceHi"]).pack(anchor="w")
        tk.Label(card, text=sub, font=("Courier", 8),
                 fg=col, bg=C["surfaceHi"]).pack(anchor="w")

    def _plot_bars(self, ax, labels, vals, color, title):
        ax.set_facecolor(C["surfaceHi"])
        ax.set_title(title, color=C["muted"], fontsize=8,
                     fontfamily="monospace", pad=4)
        bars = ax.bar(labels, vals, color=color, alpha=0.8,
                      edgecolor=C["bg"], linewidth=0.5)
        ax.tick_params(colors=C["muted"], labelsize=7)
        for spine in ax.spines.values():
            spine.set_color(C["border"])
        ax.yaxis.label.set_color(C["muted"])
        for b in bars:
            ax.text(b.get_x() + b.get_width() / 2,
                    b.get_height() * 1.02,
                    str(int(b.get_height())),
                    ha="center", va="bottom",
                    color=C["text"], fontsize=7)

    def _fetch_ai_insight(self):
        s = self._stats
        prompt = (
            f"Dataset summary ({s['records']} records):\n"
            f"- Total units sold: {s['total_units']}\n"
            f"- Total revenue: ₹{s['total_revenue']:,}\n"
            f"- Promo avg units: {s['promo_lift']}\n"
            f"- Holiday avg units: {s['holiday_lift']}\n"
            f"- Forecast next period: {s['fc_t1']} units\n"
            f"Provide 3 concise actionable insights for a sales manager. Be direct."
        )
        self.ai_label.configure(text="Analysing…  ⏳", fg=C["amber"])

        def worker():
            result = call_claude_sync(prompt)
            self.after(0, lambda: self.ai_label.configure(
                text=result, fg=C["text"]))

        threading.Thread(target=worker, daemon=True).start()

    # ─────────────────────────────────────────────────────────────────────────
    #  DATA TAB
    # ─────────────────────────────────────────────────────────────────────────
    def _build_data_tab(self):
        tab = self.tabs["data"]
        self.data_count_lbl = tk.Label(
            tab, text="", font=("Courier", 10),
            fg=C["muted"], bg=C["bg"])
        self.data_count_lbl.pack(anchor="w", pady=(0, 6))

        cols = ("Date", "Product", "Store",
                "Units Sold", "Revenue (₹)", "Promo", "Holiday")
        self.tree = ttk.Treeview(tab, columns=cols, show="headings",
                                  height=22)
        col_widths = (100, 70, 60, 90, 100, 60, 90)
        for col, w in zip(cols, col_widths):
            self.tree.heading(col, text=col)
            self.tree.column(col, width=w, anchor="center")

        style = ttk.Style()
        style.configure("Treeview",
                         background=C["surface"],
                         foreground=C["text"],
                         fieldbackground=C["surface"],
                         rowheight=24,
                         font=("Courier", 9))
        style.configure("Treeview.Heading",
                         background=C["surfaceHi"],
                         foreground=C["muted"],
                         font=("Courier", 9, "bold"))
        style.map("Treeview",
                  background=[("selected", C["accentDim"])],
                  foreground=[("selected", C["bg"])])

        vsb = ttk.Scrollbar(tab, orient="vertical",
                             command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="left", fill="y")
        self.tree.tag_configure("promo", foreground=C["amber"])
        self.tree.tag_configure("holiday", foreground=C["red"])
        self.tree.tag_configure("normal", foreground=C["text"])

    def _refresh_data_tab(self):
        self.data_count_lbl.configure(
            text=f"Showing {len(self._filtered)} records")
        for row in self.tree.get_children():
            self.tree.delete(row)
        for r in self._filtered[:50]:
            tag = ("promo"   if r["promotion"] else
                   "holiday" if r["holiday"] != "None" else "normal")
            self.tree.insert("", "end", values=(
                r["date"],
                r["product_id"],
                r["store_id"],
                r["units_sold"],
                f"{r['revenue']:,}",
                "YES" if r["promotion"] else "no",
                r["holiday"],
            ), tags=(tag,))

    # ─────────────────────────────────────────────────────────────────────────
    #  FORECAST TAB
    # ─────────────────────────────────────────────────────────────────────────
    def _build_forecast_tab(self):
        tab = self.tabs["forecast"]

        # top stat cards
        self.fc_card_frame = tk.Frame(tab, bg=C["bg"])
        self.fc_card_frame.pack(fill="x", pady=(0, 10))

        # chart area
        self.fc_chart_frame = tk.Frame(tab, bg=C["bg"])
        self.fc_chart_frame.pack(fill="x", pady=(0, 10))

        # forecast table
        tk.Label(tab, text="FORECAST TABLE",
                 font=("Courier", 9, "bold"), fg=C["muted"],
                 bg=C["bg"]).pack(anchor="w", pady=(4, 4))

        cols = ("Period", "Date", "Forecast Units", "Confidence %")
        self.fc_tree = ttk.Treeview(tab, columns=cols,
                                     show="headings", height=10)
        widths = (70, 110, 130, 120)
        for col, w in zip(cols, widths):
            self.fc_tree.heading(col, text=col)
            self.fc_tree.column(col, width=w, anchor="center")
        self.fc_tree.pack(fill="x")

    def _refresh_forecast_tab(self):
        # top cards
        for w in self.fc_card_frame.winfo_children():
            w.destroy()
        for i, fc in enumerate(self._forecast[:3]):
            self._stat_card(self.fc_card_frame,
                            f"T+{i+1} Forecast",
                            str(fc["units_sold"]),
                            fc["date"], C["amber"])

        # chart
        if HAS_MPL:
            for w in self.fc_chart_frame.winfo_children():
                w.destroy()
            hist = self._filtered[-20:]
            fc   = self._forecast
            all_pts = hist + fc
            vals    = [r["units_sold"] for r in all_pts]
            n_hist  = len(hist)

            fig, ax = plt.subplots(figsize=(10, 2.8),
                                   facecolor=C["bg"])
            ax.set_facecolor(C["surfaceHi"])
            fig.subplots_adjust(left=0.06, right=0.98,
                                top=0.82, bottom=0.22)

            xs_h = list(range(n_hist))
            ys_h = [r["units_sold"] for r in hist]
            xs_f = list(range(n_hist - 1, n_hist + len(fc)))
            ys_f = [hist[-1]["units_sold"]] + [r["units_sold"] for r in fc]

            ax.fill_between(xs_h, ys_h, alpha=0.10,
                            color=C["accent"])
            ax.plot(xs_h, ys_h, color=C["accent"],
                    linewidth=2.2, label="Historical")
            ax.fill_between(xs_f, ys_f, alpha=0.10,
                            color=C["amber"])
            ax.plot(xs_f, ys_f, color=C["amber"], linewidth=2,
                    linestyle="--", label="Forecast")
            ax.axvline(n_hist - 1, color=C["amber"],
                       linestyle=":", linewidth=1, alpha=0.7)
            ax.scatter([n_hist - 1], [ys_h[-1]],
                       color=C["accent"], zorder=5, s=40)
            ax.scatter([n_hist], [ys_f[1]],
                       color=C["amber"], zorder=5, s=40)

            ax.tick_params(colors=C["muted"], labelsize=7)
            for spine in ax.spines.values():
                spine.set_color(C["border"])
            ax.set_ylabel("Units", color=C["muted"], fontsize=8)

            # x tick labels (dates)
            tick_idx = list(range(0, len(all_pts), max(1, len(all_pts)//6)))
            ax.set_xticks(tick_idx)
            ax.set_xticklabels(
                [all_pts[i]["date"][5:] for i in tick_idx],
                fontsize=6, rotation=20)

            ax.legend(facecolor=C["surfaceHi"],
                      edgecolor=C["border"],
                      labelcolor=C["text"], fontsize=8)
            ax.set_title("Units Sold — Historical vs Forecast",
                         color=C["muted"], fontsize=9,
                         fontfamily="monospace", pad=6)

            canvas = FigureCanvasTkAgg(fig,
                                        master=self.fc_chart_frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill="x")
            plt.close(fig)

        # forecast table
        for row in self.fc_tree.get_children():
            self.fc_tree.delete(row)
        for i, fc in enumerate(self._forecast):
            conf = max(60.0, 95 - i * 3.5)
            tag  = ("hi" if conf > 80 else
                    "mid" if conf > 70 else "lo")
            self.fc_tree.insert("", "end",
                                tags=(tag,),
                                values=(
                f"T+{i+1}",
                fc["date"],
                fc["units_sold"],
                f"{conf:.0f}%",
            ))
        self.fc_tree.tag_configure("hi",  foreground=C["green"])
        self.fc_tree.tag_configure("mid", foreground=C["amber"])
        self.fc_tree.tag_configure("lo",  foreground=C["red"])

    # ─────────────────────────────────────────────────────────────────────────
    #  CHAT TAB
    # ─────────────────────────────────────────────────────────────────────────
    def _build_chat_tab(self):
        tab = self.tabs["chat"]

        tk.Label(tab,
                 text="Ask questions about your sales data in natural language.",
                 font=("Courier", 9), fg=C["muted"],
                 bg=C["bg"]).pack(anchor="w", pady=(0, 8))

        # suggested questions
        sq_frame = tk.Frame(tab, bg=C["bg"])
        sq_frame.pack(fill="x", pady=(0, 10))
        suggestions = [
            "Which product has the highest units?",
            "How does promotion affect sales?",
            "What is the holiday sales impact?",
            "Give me a revenue forecast summary.",
        ]
        for q in suggestions:
            tk.Button(sq_frame, text=q,
                      font=("Courier", 9),
                      fg=C["muted"], bg=C["surfaceHi"],
                      relief="flat", padx=8, pady=4,
                      cursor="hand2",
                      command=lambda x=q: self._set_question(x)
                      ).pack(side="left", padx=4)

        # chat display
        self.chat_display = scrolledtext.ScrolledText(
            tab, height=20, state="disabled",
            font=("Segoe UI", 10),
            bg=C["surface"], fg=C["text"],
            insertbackground=C["accent"],
            relief="flat", bd=0,
            wrap="word")
        self.chat_display.pack(fill="both", expand=True, pady=(0, 8))

        # colour tags
        self.chat_display.tag_configure("user",
            foreground=C["accent"], font=("Segoe UI", 10, "bold"))
        self.chat_display.tag_configure("bot",
            foreground=C["text"])
        self.chat_display.tag_configure("label_user",
            foreground=C["accentDim"],
            font=("Courier", 8, "bold"))
        self.chat_display.tag_configure("label_bot",
            foreground=C["muted"],
            font=("Courier", 8, "bold"))

        # input row
        inp_frame = tk.Frame(tab, bg=C["bg"])
        inp_frame.pack(fill="x")
        self.question_var = tk.StringVar()
        entry = tk.Entry(inp_frame,
                         textvariable=self.question_var,
                         font=("Segoe UI", 11),
                         bg=C["surfaceHi"], fg=C["text"],
                         insertbackground=C["accent"],
                         relief="flat", bd=8)
        entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        entry.bind("<Return>", lambda _: self._send_chat())

        self.send_btn = tk.Button(inp_frame, text="Send ▶",
                                   font=("Courier", 10, "bold"),
                                   fg=C["bg"], bg=C["accent"],
                                   relief="flat", padx=14, pady=6,
                                   cursor="hand2",
                                   command=self._send_chat)
        self.send_btn.pack(side="right")

    def _set_question(self, text):
        self.question_var.set(text)

    def _append_chat(self, role: str, text: str):
        self.chat_display.configure(state="normal")
        label = "You:" if role == "user" else "SalesOracle:"
        tag_l = "label_user" if role == "user" else "label_bot"
        tag_t = "user"       if role == "user" else "bot"
        self.chat_display.insert("end", f"\n{label}\n", tag_l)
        self.chat_display.insert("end", text + "\n", tag_t)
        self.chat_display.see("end")
        self.chat_display.configure(state="disabled")

    def _send_chat(self):
        q = self.question_var.get().strip()
        if not q:
            return
        self.question_var.set("")
        self.chat_history.append({"role": "user", "content": q})
        self._append_chat("user", q)
        self.send_btn.configure(state="disabled",
                                bg=C["border"], text="…")

        s = self._stats
        ctx = (
            f"You are a sales analyst. "
            f"Dataset: {s['records']} records, "
            f"₹{s['total_revenue']:,} revenue, "
            f"{s['total_units']} units. "
            f"Promo lift: {s['promo_lift']} avg units. "
            f"Holiday lift: {s['holiday_lift']} avg units. "
            f"Answer concisely."
        )
        history_str = "\n".join(
            f"{m['role']}: {m['content']}"
            for m in self.chat_history)
        prompt = f"{ctx}\n\n{history_str}\n\nassistant:"

        def worker():
            reply = call_claude_sync(prompt)
            self.chat_history.append(
                {"role": "assistant", "content": reply})
            self.after(0, lambda: (
                self._append_chat("assistant", reply),
                self.send_btn.configure(
                    state="normal",
                    bg=C["accent"],
                    text="Send ▶"),
            ))

        threading.Thread(target=worker, daemon=True).start()

# ── entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = SalesOracleApp()
    app.mainloop()