from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path
import time
import uuid
from datetime import datetime, timezone

import dollar_auction as engine

DISPLAY_TO_OPPORTUNITY_DELAY_MS = 1000
BG = "#101827"
PANEL = "#1b2940"
PANEL_ALT = "#233650"
TEXT = "#f4f7fb"
MUTED = "#b8c5d8"
ACCENT = "#67e8f9"
HIGHLIGHT = "#fbbf24"
GREEN = "#34d399"
RED = "#fb7185"

def timestamp_pair() -> tuple[str, float]:
    return engine.now_utc(), time.perf_counter()

def reaction_times(display_clock: float, opportunity_clock: float, submitted_clock: float) -> tuple[float, float]:
    return (max(0.0, submitted_clock - opportunity_clock),
            max(0.0, submitted_clock - display_clock))

def group_digits_live(raw: str) -> str:
    #Format an amount with thousands separators while preserving a decimal tail.
    raw = raw.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
    raw = raw.replace(",", "").replace(" ", "")
    allowed = []
    dot_seen = False
    for ch in raw:
        if ch.isdigit():
            allowed.append(ch)
        elif ch == "." and not dot_seen:
            allowed.append(ch)
            dot_seen = True
    cleaned = "".join(allowed)
    if not cleaned or cleaned == ".":
        return cleaned
    if "." in cleaned:
        whole, decimal = cleaned.split(".", 1)
        whole = f"{int(whole):,}" if whole else "0"
        return whole + "." + decimal
    return f"{int(cleaned):,}"

class AuctionApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Dollar Auction | Game 1 · v4.2")
        self.root.geometry("940x850")
        self.root.minsize(800, 760)
        self.root.configure(bg=BG)
        self.session = None
        self.current = None
        self.opponent = None
        self.first = None
        self.display_at = ""
        self.display_clock = 0.0
        self.opportunity_at = ""
        self.opportunity_clock = 0.0
        self.turn_active = False
        self.game_over = False
        self.events_saved = False
        self._session_clock_started = False
        self._formatting = False
        self._build_setup()

    def _tk_label(self, parent, text="", **kwargs):
        return tk.Label(parent, text=text, bg=kwargs.pop("bg", PANEL), fg=kwargs.pop("fg", TEXT), font=kwargs.pop("font", ("Segoe UI", 10)), **kwargs)

    def _build_setup(self):
        outer = tk.Frame(self.root, bg=BG, padx=28, pady=26)
        outer.pack(fill="both", expand=True)
        self._tk_label(outer, "DOLLAR AUCTION", bg=BG, fg=ACCENT, font=("Segoe UI", 11, "bold")).pack(anchor="w")
        self._tk_label(outer, "Game 1 · Local two-player pilot", bg=BG, font=("Segoe UI", 23, "bold")).pack(anchor="w", pady=(2, 4))
        self._tk_label(outer, "Version 1 payment rule: each participant pays only their own final bid.", bg=BG, fg=MUTED, wraplength=800, justify="left").pack(anchor="w", pady=(0, 20))

        card = tk.Frame(outer, bg=PANEL, padx=20, pady=18)
        card.pack(fill="x")
        self.prize_var = tk.StringVar(value="1")
        self.rate_var = tk.StringVar(value="100000")
        self.source_var = tk.StringVar(value="")
        self.mode_var = tk.StringVar(value="A")
        self.arousal_var = tk.StringVar(value="Low")
        self.condition_order_var = tk.StringVar(value="1")
        self.protocol_var = tk.StringVar(value="")
        self.p1_var = tk.StringVar(value="Player A")
        self.p2_var = tk.StringVar(value="Player B")
        fields = [("Prize value (USD)", self.prize_var),
                  ("USD-to-toman rate (toman per USD)", self.rate_var),
                  ("Rate source / description", self.source_var),
                  ("Participant 1 label (pseudonym only)", self.p1_var),
                  ("Participant 2 label (pseudonym only)", self.p2_var)]
        for row, (label, var) in enumerate(fields):
            self._tk_label(card, label, bg=PANEL, fg=MUTED).grid(row=row, column=0, sticky="w", pady=6)
            entry = tk.Entry(card, textvariable=var, bg="#f8fafc",  fg="#111827", insertbackground="#111827", relief="flat", font=("Segoe UI", 11), width=38)
            entry.grid(row=row, column=1, sticky="ew", padx=(20, 0), pady=6, ipady=6)
        self._tk_label(card, "Assigned arousal condition", bg=PANEL, fg=MUTED).grid(row=5, column=0, sticky="w", pady=6)
        condition_box = ttk.Combobox(card, textvariable=self.arousal_var, values=("Low", "Medium", "High"), state="readonly", width=35)
        condition_box.grid(row=5, column=1, sticky="ew", padx=(20, 0), pady=6, ipady=4)
        self._tk_label(card, "Condition order (counterbalancing index)", bg=PANEL, fg=MUTED).grid(row=6, column=0, sticky="w", pady=6)
        tk.Entry(card, textvariable=self.condition_order_var, bg="#f8fafc", fg="#111827", relief="flat", font=("Segoe UI", 11), width=38).grid(row=6, column=1, sticky="ew", padx=(20, 0), pady=6, ipady=6)
        self._tk_label(card, "Approved protocol/script ID", bg=PANEL, fg=MUTED).grid(row=7, column=0, sticky="w", pady=6)
        tk.Entry(card, textvariable=self.protocol_var, bg="#f8fafc", fg="#111827", relief="flat", font=("Segoe UI", 11), width=38).grid(row=7, column=1, sticky="ew", padx=(20, 0), pady=6, ipady=6)
        self._tk_label(card, "Reaction-time reference", bg=PANEL, fg=MUTED).grid(row=8, column=0, sticky="w", pady=8)
        modebox = tk.Frame(card, bg=PANEL)
        modebox.grid(row=8, column=1, sticky="w", padx=(20, 0), pady=8)
        for label, value in [("A · opportunity start → response", "A"), ("B · opponent display → response", "B")]:
            tk.Radiobutton(modebox, text=label, variable=self.mode_var, value=value, bg=PANEL, fg=TEXT, selectcolor=PANEL_ALT, activebackground=PANEL, activeforeground=TEXT, font=("Segoe UI", 10)).pack(anchor="w", pady=2)
        self._tk_label(outer, "Bids are entered in toman and grouped by thousands as you type. No fixed bid increment or maximum is imposed.", bg=BG, fg=MUTED, wraplength=800, justify="left").pack(anchor="w", pady=(16, 6))
        self._tk_label(outer, f"Timing prototype: response controls activate {DISPLAY_TO_OPPORTUNITY_DELAY_MS} ms after the turn information is processed by the GUI.", bg=BG, fg=MUTED, wraplength=800, justify="left").pack(anchor="w", pady=(0, 16))
        tk.Button(outer, text="VALIDATE SETTINGS  →  START", command=self.start_game, bg=ACCENT, fg="#082f49", activebackground="#a5f3fc", activeforeground="#082f49", relief="flat", font=("Segoe UI", 11, "bold"), padx=18, pady=10, cursor="hand2").pack(anchor="w")
        self._tk_label(outer, "Research prototype only · Not yet validated for formal data collection", bg=BG, fg="#fda4af", font=("Segoe UI", 9, "italic")).pack(anchor="w", pady=(18, 0))

    def start_game(self):
        try:
            prize_usd = engine.dec(self.prize_var.get(), "Prize value", positive=True)
            rate = engine.dec(self.rate_var.get(), "Exchange rate", positive=True)
        except ValueError as exc:
            messagebox.showerror("Invalid settings", str(exc))
            return
        p1_label, p2_label = self.p1_var.get().strip(), self.p2_var.get().strip()
        if not p1_label or not p2_label:
            messagebox.showerror("Invalid labels", "Both participants need a non-empty pseudonym/label.")
            return
        if p1_label == p2_label:
            messagebox.showerror("Invalid labels", "Use distinct participant labels.")
            return
        source = self.source_var.get().strip() or "Not provided by researcher"
        try:
            condition_order = int(self.condition_order_var.get().strip())
            if condition_order < 1:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid condition order", "Condition order must be a positive integer.")
            return
        protocol_id = self.protocol_var.get().strip()
        if not protocol_id:
            messagebox.showerror("Protocol required", "Enter the approved arousal-manipulation script/protocol ID. The condition label alone does not induce or validate arousal.")
            return
        instructions = ("STANDARD GAME INSTRUCTIONS\n\n" "You are playing a two-person dollar auction. The prize value is shown in toman. " "Each valid new bid must be strictly higher than the current highest bid. There is no fixed increment or maximum bid. " "You may submit a valid bid or pass. Passing ends the game after a valid bid has been made; if nobody has bid yet, " "the other participant receives an opening opportunity. In Game 1, each participant pays only their own final bid. " "The winner receives the prize and pays their own final bid; the other participant pays their own final bid and receives no prize.\n\n" f"Assigned condition: {self.arousal_var.get()}. Protocol: {protocol_id}.\n" "Read the approved condition-specific manipulation script separately and consistently before continuing.")
        if not messagebox.askokcancel("Read standardized instructions", instructions):
            return
        rate_time = engine.now_utc()
        p1 = engine.Player("P-" + uuid.uuid4().hex[:6].upper(), p1_label)
        p2 = engine.Player("P-" + uuid.uuid4().hex[:6].upper(), p2_label)
        session_code = "SES-" + datetime.now(timezone.utc).strftime("%Y%m%d") + "-" + uuid.uuid4().hex[:4].upper()
        self.session = engine.Session(session_code, prize_usd, rate, prize_usd * rate, source, rate_time, engine.MODE_A if self.mode_var.get() == "A" else engine.MODE_B, [p1, p2], arousal_condition=self.arousal_var.get(), condition_order=condition_order, condition_protocol_id=protocol_id)

        import random
        order = self.session.players[:]
        random.shuffle(order)
        self.first = order[0]
        self.current, self.opponent = order[0], order[1]
        self._build_game_screen()
        self._show_turn()

    def _build_game_screen(self):
        for child in self.root.winfo_children():
            child.destroy()
        self.main = tk.Frame(self.root, bg=BG, padx=26, pady=22)
        self.main.pack(fill="both", expand=True)
        header = tk.Frame(self.main, bg=BG)
        header.pack(fill="x")
        self._tk_label(header, "DOLLAR AUCTION", bg=BG, fg=ACCENT, font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self._tk_label(header, "Make your next move", bg=BG, font=("Segoe UI", 22, "bold")).pack(anchor="w")
        self.summary = self._tk_label(self.main, "", fg=MUTED, bg=BG, justify="left", wraplength=820)
        self.summary.pack(anchor="w", fill="x", pady=(8, 14))

        self.turn_title = self._tk_label(self.main, "", bg=BG, fg=HIGHLIGHT, font=("Segoe UI", 14, "bold"))
        self.turn_title.pack(anchor="w", pady=(0, 6))

        #Keep the turn-transition control near the top of the window. In v4 it was below the history/results and could be clipped on common screens, leaving the game apparently stuck after the first decision.
        self.continue_button = tk.Button(self.main, text="CONTINUE TO NEXT TURN  →", command=self._advance, state="disabled", bg="#334155", fg=TEXT, activebackground="#475569", relief="flat", font=("Segoe UI", 10, "bold"), padx=16, pady=8, cursor="hand2")
        self.continue_button.pack(anchor="w", pady=(0, 12))

        #Large, stylized bid ticket: intentionally not an imitation of a real banknote.
        self.bid_card = tk.Frame(self.main, bg="#0f766e", padx=22, pady=16, highlightthickness=2, highlightbackground="#5eead4")
        self.bid_card.pack(fill="x", pady=(0, 14))
        self._tk_label(self.bid_card, "OPPONENT'S LAST BID", bg="#0f766e", fg="#ccfbf1", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.opponent_bid_display = self._tk_label(self.bid_card, "0 toman", bg="#0f766e", fg="#ffffff", font=("Segoe UI", 28, "bold"))
        self.opponent_bid_display.pack(anchor="w", pady=(2, 0))
        self._tk_label(self.bid_card, "LIVE BID DISPLAY · Toman", bg="#0f766e", fg="#99f6e4", font=("Segoe UI", 9)).pack(anchor="e")

        stats = tk.Frame(self.main, bg=BG)
        stats.pack(fill="x", pady=(0, 14))
        self.highest_card = tk.Frame(stats, bg=PANEL, padx=15, pady=12)
        self.highest_card.pack(side="left", fill="both", expand=True, padx=(0, 7))
        self._tk_label(self.highest_card, "CURRENT HIGHEST BID", bg=PANEL, fg=MUTED, font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self.highest_display = self._tk_label(self.highest_card, "0 toman", bg=PANEL, fg=HIGHLIGHT, font=("Segoe UI", 17, "bold"))
        self.highest_display.pack(anchor="w", pady=(3, 0))
        self.prize_card = tk.Frame(stats, bg=PANEL, padx=15, pady=12)
        self.prize_card.pack(side="left", fill="both", expand=True, padx=(7, 0))
        self._tk_label(self.prize_card, "PRIZE VALUE", bg=PANEL, fg=MUTED, font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self.prize_display = self._tk_label(self.prize_card, "0 toman", bg=PANEL, fg=GREEN, font=("Segoe UI", 17, "bold"))
        self.prize_display.pack(anchor="w", pady=(3, 0))

        self.status = self._tk_label(self.main, "", bg=BG, fg=TEXT, wraplength=820, justify="left")
        self.status.pack(anchor="w", fill="x", pady=(0, 12))
        self.input_frame = tk.Frame(self.main, bg=PANEL, padx=18, pady=16)
        self.input_frame.pack(fill="x")
        self._tk_label(self.input_frame, "YOUR BID (TOMAN)", bg=PANEL, fg=MUTED,font=("Segoe UI", 9, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        self.bid_var = tk.StringVar()
        self.bid_entry = tk.Entry(self.input_frame, textvariable=self.bid_var, bg="#f8fafc", fg="#111827", insertbackground="#111827", relief="flat", font=("Segoe UI", 19, "bold"), width=24)
        self.bid_entry.grid(row=1, column=0, sticky="ew", ipady=7)
        self.bid_entry.bind("<KeyRelease>", self._format_bid_entry)
        self.submit_button = tk.Button(self.input_frame, text="SUBMIT BID", command=self.submit_bid, bg=ACCENT, fg="#082f49", activebackground="#a5f3fc", relief="flat", font=("Segoe UI", 10, "bold"), padx=16, pady=10, cursor="hand2")
        self.submit_button.grid(row=1, column=1, padx=(10, 0))
        self.pass_button = tk.Button(self.input_frame, text="PASS", command=self.submit_pass, bg="#334155", fg=TEXT, activebackground="#475569", relief="flat", font=("Segoe UI", 10, "bold"), padx=18, pady=10, cursor="hand2")
        self.pass_button.grid(row=1, column=2, padx=(8, 0))
        self.bid_entry.bind("<Return>", lambda _event: self.submit_bid())
        self._tk_label(self.input_frame, "Example: 1250000 appears as 1,250,000 while typing.", bg=PANEL, fg=MUTED, font=("Segoe UI", 9)).grid(row=2, column=0, columnspan=3, sticky="w", pady=(8, 0))
        self.input_frame.columnconfigure(0, weight=1)

        self._tk_label(self.main, "BID HISTORY · chronological order", bg=BG, fg=ACCENT, font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(15, 5))
        self.history_display = self._tk_label(self.main, "No bids yet", bg=PANEL_ALT, fg=TEXT, justify="left", wraplength=820, padx=12, pady=10)
        self.history_display.pack(fill="x")
        self.result_box = self._tk_label(self.main, "", bg=BG, fg=TEXT, justify="left", wraplength=820)
        self.result_box.pack(anchor="w", fill="x", pady=(10, 0))
        self._set_controls(False)

    def _format_bid_entry(self, _event=None):
        if self._formatting or not hasattr(self, "bid_entry"):
            return
        original = self.bid_var.get()
        try:
            cursor = self.bid_entry.index(tk.INSERT)
        except tk.TclError:
            cursor = len(original)
        before = original[:cursor].replace(",", "").replace(" ", "")
        before = before.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
        meaningful_before = sum(1 for c in before if c.isdigit() or c == ".")
        formatted = group_digits_live(original)
        if formatted != original:
            self._formatting = True
            self.bid_var.set(formatted)
            new_cursor = 0
            seen = 0
            while new_cursor < len(formatted) and seen < meaningful_before:
                if formatted[new_cursor].isdigit() or formatted[new_cursor] == ".":
                    seen += 1
                new_cursor += 1
            self.bid_entry.icursor(new_cursor)
            self._formatting = False

    def _set_controls(self, enabled: bool):
        state = "normal" if enabled else "disabled"
        self.bid_entry.configure(state=state)
        self.submit_button.configure(state=state)
        self.pass_button.configure(state=state)
        self.turn_active = enabled
        if enabled:
            self.bid_entry.focus_set()

    def _show_turn(self):
        if self.game_over:
            return
        if not self._session_clock_started:
            self.session.started_at = engine.now_utc()
            self.session.started_clock = time.perf_counter()
            self._session_clock_started = True
        self.continue_button.configure(state="disabled")
        self.result_box.configure(text="")
        self.bid_var.set("")
        self._set_controls(False)
        s = self.session
        self.summary.configure(text=(f"Prize: {engine.money(s.prize_toman)} toman  |  Fixed rate: {engine.money(s.rate)} toman/USD\n"
                                     f"Session code: {s.sid}  |  Rate timestamp (UTC): {s.rate_timestamp}\n"
                                     f"Arousal condition: {s.arousal_condition}  |  Condition order: {s.condition_order}  |  Protocol: {s.condition_protocol_id}"))
        self.turn_title.configure(text=f"YOUR TURN  ·  {self.current.label}")
        self.opponent_bid_display.configure(text=f"{engine.money(self.opponent.last_bid)} toman")
        self.highest_display.configure(text=f"{engine.money(s.highest_bid)} toman")
        self.prize_display.configure(text=f"{engine.money(s.prize_toman)} toman")
        self.status.configure(text=(f"Opponent's last bid: {engine.money(self.opponent.last_bid)} toman. "
                                    f"Your last bid: {engine.money(self.current.last_bid)} toman. "
                                    "Enter an amount above the current highest bid, or pass."))
        self._refresh_history()
        self.display_at, self.display_clock = "", 0.0
        self.opportunity_at, self.opportunity_clock = "", 0.0
        self.root.after_idle(self._mark_opponent_displayed)

    def _refresh_history(self):
        bid_events = [e for e in self.session.events if e.action == "bid" and e.bid is not None]
        if not bid_events:
            self.history_display.configure(text="No bids yet — the opening bid can be any positive amount.")
            return
        label_by_id = {p.pid: p.label for p in self.session.players}
        chunks = [f"{i}. {label_by_id[e.pid]}  ·  {engine.money(e.bid)} toman" for i, e in enumerate(bid_events, 1)]
        self.history_display.configure(text="     →     ".join(chunks))

    def _mark_opponent_displayed(self):
        if self.game_over:
            return
        self.display_at, self.display_clock = timestamp_pair()
        self.root.after(DISPLAY_TO_OPPORTUNITY_DELAY_MS, self._activate_opportunity)

    def _activate_opportunity(self):
        if self.game_over:
            return
        self.opportunity_at, self.opportunity_clock = timestamp_pair()
        self.status.configure(text=self.status.cget("text") + "\nYou may now respond.")
        self._set_controls(True)

    def submit_bid(self):
        if not self.turn_active or self.game_over:
            return
        submitted_at, submitted_clock = timestamp_pair()
        try:
            bid = engine.dec(self.bid_var.get(), "Bid", positive=True)
        except ValueError as exc:
            self.status.configure(text=f"{exc}. Correct the entry; the response clock continues.")
            self.bid_entry.focus_set()
            return
        if bid <= self.session.highest_bid:
            self.status.configure(text=f"Bid must exceed {engine.money(self.session.highest_bid)} toman. The response clock continues.")
            self.bid_entry.focus_set()
            return
        self._accept_decision("bid", bid, submitted_at, submitted_clock)

    def submit_pass(self):
        if not self.turn_active or self.game_over:
            return
        submitted_at, submitted_clock = timestamp_pair()
        self._accept_decision("pass", None, submitted_at, submitted_clock)

    def _accept_decision(self, action, bid, submitted_at, submitted_clock):
        self._set_controls(False)
        rt_a, rt_b = reaction_times(self.display_clock, self.opportunity_clock, submitted_clock)
        timing = (self.display_at, self.opportunity_at, submitted_at, rt_a, rt_b)
        engine.record_decision(self.session, self.current, self.opponent, action, bid, timing)
        if action == "bid":
            self.status.configure(text=f"Recorded bid: {engine.money(bid)} toman.")
            self.bid_card.configure(bg="#7c3aed", highlightbackground="#c4b5fd")
            self.opponent_bid_display.configure(text=f"{engine.money(bid)} toman", bg="#7c3aed")
        else:
            self.status.configure(text="Recorded pass.")
        self._refresh_history()
        if action == "pass":
            if self.session.leader_id is None and self.current is self.first:
                self.result_box.configure(text="No opening bid yet; the other participant receives an opening opportunity.")
                self.continue_button.configure(state="normal")
                return
            self.session.termination_reason = "opponent_passed_after_valid_bid" if self.session.leader_id else "both_passed_without_bid"
            self._finish_game()
            return
        self.continue_button.configure(state="normal", text="CONTINUE TO NEXT TURN  →")
        self.status.configure(text=self.status.cget("text") + "  Click CONTINUE above to hand over to the next participant.")

    def _advance(self):
        if self.game_over:
            return
        self.current, self.opponent = self.opponent, self.current
        self.bid_card.configure(bg="#0f766e", highlightbackground="#5eead4")
        self.opponent_bid_display.configure(bg="#0f766e")
        self._show_turn()

    def _finish_game(self):
        self.game_over = True
        self._set_controls(False)
        result = engine.outcome(self.session)
        try:
            checks = engine.validate_game(self.session, result)
        except ValueError as exc:
            self.result_box.configure(text=f"VALIDATION FAILED — no CSV saved.\n{exc}")
            messagebox.showerror("Validation failed", str(exc))
            return
        winner = result["winner"]
        lines = ["VALIDATION PASSED", *[f"✓ {x}" for x in checks], ""]
        if winner:
            winner_p = next(p for p in self.session.players if p.pid == winner)
            lines.append(f"Winner: {winner_p.label}; winning bid: {engine.money(result['winning_bid'])} toman")
        else:
            lines.append("No valid bids; no winner.")
        for p in self.session.players:
            lines.append(f"{p.label}: final bid {engine.money(p.last_bid)}; payment {engine.money(result['payments'][p.pid])}; net payoff {engine.money(result['payoffs'][p.pid])} toman")
        lines.append(f"Stages: {self.session.stages}; bids: {sum(e.action == 'bid' for e in self.session.events)}; escalations: {self.session.escalation_count}; leader changes: {self.session.leader_change_count}")
        lines.append(f"Round duration: {result['duration']:.3f} seconds")
        self.result_box.configure(text="\n".join(lines))
        self.status.configure(text="Game finished. Validate pilot data and research protocol before any formal data collection.")
        messagebox.showinfo("Debrief", "Thank you for participating. The task studied decisions in a competitive bidding situation. No individual response should be interpreted in isolation. The researcher should now provide the approved study-specific debrief, explain the purpose of the arousal manipulation, and answer questions. This generic notice does not replace an ethics-approved debrief.")
        self.continue_button.configure(text="SAVE CSV…", state="normal", command=lambda: self._save_result(result), bg=GREEN, fg="#052e16")

    def _save_result(self, result):
        if self.events_saved:
            messagebox.showinfo("Already saved", "This session has already been saved.")
            return
        default_name = f"dollar_auction_game1_{self.session.sid}.csv"
        selected = filedialog.asksaveasfilename(title="Save decision-level CSV", initialfile=default_name, defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
        if not selected:
            return
        requested = Path(selected).expanduser()
        safe = engine.non_overwriting_path(requested)
        try:
            engine.save_csv(self.session, result, safe, "GUI v4.2; local two-player Game 1; assigned arousal-condition metadata; live thousands grouping; chronological bid sequence; not validated as a research instrument")
        except OSError as exc:
            messagebox.showerror("Save failed", str(exc))
            return
        self.events_saved = True
        self.result_box.configure(text=self.result_box.cget("text") + f"\n\nCSV saved to:\n{safe.resolve()}")
        messagebox.showinfo("Saved", f"CSV saved to:\n{safe.resolve()}")

def main():
    root = tk.Tk()
    AuctionApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
