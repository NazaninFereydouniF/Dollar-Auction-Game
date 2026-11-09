from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from decimal import Decimal
from pathlib import Path
import time
import uuid

import dollar_auction as engine

DISPLAY_TO_OPPORTUNITY_DELAY_MS = 1000

def timestamp_pair() -> tuple[str, float]:
    #Wall-clock timestamp for export plus monotonic clock for RT calculation.
    return engine.now_utc(), time.perf_counter()

def reaction_times(display_clock: float, opportunity_clock: float, submitted_clock: float) -> tuple[float, float]:
    #Return non-negative RTs from opportunity start (A) and opponent display (B).
    return (max(0.0, submitted_clock - opportunity_clock),
            max(0.0, submitted_clock - display_clock))

class AuctionApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Dollar Auction — Game 1 (local GUI prototype)")
        self.root.geometry("760x620")
        self.root.minsize(650, 560)
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
        self._build_setup()

    def _build_setup(self):
        outer = ttk.Frame(self.root, padding=18)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="Thesis Game 1 — All-Pay Dollar Auction", font=("TkDefaultFont", 16, "bold")).pack(anchor="w")
        ttk.Label(outer, text="Version 1 payment rule: each participant pays only their own final bid.", wraplength=700).pack(anchor="w", pady=(4, 14))
        form = ttk.Frame(outer)
        form.pack(fill="x")
        self.prize_var = tk.StringVar(value="1")
        self.rate_var = tk.StringVar(value="100000")
        self.source_var = tk.StringVar(value="")
        self.mode_var = tk.StringVar(value="A")
        self.p1_var = tk.StringVar(value="Player A")
        self.p2_var = tk.StringVar(value="Player B")
        fields = [("Prize value (USD)", self.prize_var),
                  ("USD-to-toman rate (toman per USD; manually entered)", self.rate_var),
                  ("Rate source/description", self.source_var),
                  ("Participant A label (pseudonym only)", self.p1_var),("Participant B label (pseudonym only)", self.p2_var)]
        for row, (label, var) in enumerate(fields):
            ttk.Label(form, text=label).grid(row=row, column=0, sticky="w", pady=5)
            ttk.Entry(form, textvariable=var, width=42).grid(row=row, column=1, sticky="ew", padx=(12, 0), pady=5)
        form.columnconfigure(1, weight=1)
        ttk.Label(form, text="Reaction-time reference").grid(row=5, column=0, sticky="w", pady=5)
        modebox = ttk.Frame(form)
        modebox.grid(row=5, column=1, sticky="w", padx=(12, 0), pady=5)
        ttk.Radiobutton(modebox, text="A — response opportunity start", variable=self.mode_var, value="A").pack(anchor="w")
        ttk.Radiobutton(modebox, text="B — opponent information displayed", variable=self.mode_var, value="B").pack(anchor="w")
        ttk.Label(outer, text=f"Timing procedure: opponent/game information appears first; response controls activate after {DISPLAY_TO_OPPORTUNITY_DELAY_MS} ms. Invalid entries do not reset the clock.", wraplength=700).pack(anchor="w", pady=(10, 6))
        ttk.Label(outer, text="This is a local, turn-taking prototype. It is not online, not a multi-condition arousal experiment, and not approved as a final research instrument.", wraplength=700).pack(anchor="w", pady=(0, 12))
        ttk.Button(outer, text="Validate settings and start game", command=self.start_game).pack(anchor="w")

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
        rate_time = engine.now_utc()
        p1 = engine.Player("P-" + uuid.uuid4().hex[:8].upper(), p1_label)
        p2 = engine.Player("P-" + uuid.uuid4().hex[:8].upper(), p2_label)
        self.session = engine.Session("S-" + uuid.uuid4().hex, prize_usd, rate, prize_usd * rate, source, rate_time, engine.MODE_A if self.mode_var.get() == "A" else engine.MODE_B, [p1, p2])
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
        self.main = ttk.Frame(self.root, padding=22)
        self.main.pack(fill="both", expand=True)
        ttk.Label(self.main, text="Dollar Auction", font=("TkDefaultFont", 17, "bold")).pack(anchor="w")
        self.summary = ttk.Label(self.main, text="", justify="left", wraplength=700)
        self.summary.pack(anchor="w", fill="x", pady=(8, 16))
        self.turn_title = ttk.Label(self.main, text="", font=("TkDefaultFont", 13, "bold"))
        self.turn_title.pack(anchor="w", pady=(0, 8))
        self.status = ttk.Label(self.main, text="", wraplength=700)
        self.status.pack(anchor="w", fill="x", pady=(0, 14))
        self.input_frame = ttk.Frame(self.main)
        self.input_frame.pack(anchor="w", fill="x")
        ttk.Label(self.input_frame, text="Your bid (toman; must exceed current highest bid):").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
        self.bid_var = tk.StringVar()
        self.bid_entry = ttk.Entry(self.input_frame, textvariable=self.bid_var, width=28)
        self.bid_entry.grid(row=1, column=0, sticky="w")
        self.submit_button = ttk.Button(self.input_frame, text="Submit bid", command=self.submit_bid)
        self.submit_button.grid(row=1, column=1, padx=(8, 0))
        self.pass_button = ttk.Button(self.input_frame, text="Pass", command=self.submit_pass)
        self.pass_button.grid(row=1, column=2, padx=(8, 0))
        self.bid_entry.bind("<Return>", lambda _event: self.submit_bid())
        self.continue_button = ttk.Button(self.main, text="Continue to next turn", command=self._advance, state="disabled")
        self.continue_button.pack(anchor="w", pady=(18, 0))
        self.result_box = ttk.Label(self.main, text="", justify="left", wraplength=700)
        self.result_box.pack(anchor="w", fill="x", pady=(12, 0))
        self._set_controls(False)

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
            #Start round duration at the first turn-screen preparation, not setup entry.
            self.session.started_at = engine.now_utc()
            self.session.started_clock = time.perf_counter()
            self._session_clock_started = True
        self.continue_button.configure(state="disabled")
        self.result_box.configure(text="")
        self.bid_var.set("")
        self._set_controls(False)
        s = self.session
        self.summary.configure(text=(
            f"Prize: {engine.money(s.prize_toman)} toman  |  Fixed rate: {engine.money(s.rate)} toman/USD\n"
            f"Highest bid: {engine.money(s.highest_bid)} toman  |  Stages so far: {s.stages}\n"
            f"Session: {s.sid}  |  Rate timestamp (UTC): {s.rate_timestamp}"))
        self.turn_title.configure(text=f"Current participant: {self.current.label}")
        self.status.configure(text=(
            f"Opponent's last bid: {engine.money(self.opponent.last_bid)} toman. "
            f"Your last bid: {engine.money(self.current.last_bid)} toman. "
            f"Choose a bid greater than the current highest bid, or pass."))
        self.display_at, self.display_clock = "", 0.0
        self.opportunity_at, self.opportunity_clock = "", 0.0
        #after_idle timestamps the point after Tk has processed the visible state.
        self.root.after_idle(self._mark_opponent_displayed)

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
            self.status.configure(text=f"{exc}. Please correct the entry; the response clock continues.")
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
        if action == "bid": self.status.configure(text=f"Recorded bid: {engine.money(bid)} toman.")
        else:
            self.status.configure(text="Recorded pass.")
        if action == "pass":
            if self.session.leader_id is None and self.current is self.first:
                self.result_box.configure(text="No opening bid yet; the other participant receives an opening opportunity.")
                self.continue_button.configure(state="normal")
                return
            self.session.termination_reason = "opponent_passed_after_valid_bid" if self.session.leader_id else "both_passed_without_bid"
            self._finish_game()
            return
        self.continue_button.configure(state="normal")

    def _advance(self):
        if self.game_over:
            return
        self.current, self.opponent = self.opponent, self.current
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
        self.continue_button.configure(text="Save CSV…", state="normal", command=lambda: self._save_result(result))

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
            engine.save_csv(self.session, result, safe, "GUI prototype; local turn-taking; not yet validated as a research instrument")
        except OSError as exc:
            messagebox.showerror("Save failed", str(exc))
            return
        self.events_saved = True
        self.result_box.configure(text=self.result_box.cget("text") + f"\n\nCSV saved to:\n{safe.resolve()}")
        messagebox.showinfo("Saved", f"CSV saved to:\n{safe.resolve()}")

def main():
    root = tk.Tk()
    app = AuctionApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
