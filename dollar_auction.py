from __future__ import annotations
import csv, random, time, uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

GAME_VERSION = "thesis_game_1_last_bid_payment"
MODE_A = "A_opportunity_start_to_response"
MODE_B = "B_opponent_bid_display_to_response"


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")

def dec(raw: str, label: str, positive: bool = False) -> Decimal:
    try:
        v = Decimal(raw.strip().replace(",", "").replace(" ", ""))
    except InvalidOperation as e:
        raise ValueError(f"{label} must be numeric") from e
    if not v.is_finite() or v < 0 or (positive and v == 0):
        raise ValueError(f"{label} must be {'greater than zero' if positive else 'zero or greater'}")
    return v

def ask_decimal(prompt: str, label: str, positive: bool = False) -> Decimal:
    while True:
        try:
            return dec(input(prompt), label, positive)
        except ValueError as e:
            print(f"Input error: {e}")

def money(v: Decimal) -> str:
    return f"{v:,.2f}".rstrip("0").rstrip(".")

def blank(v):
    return "" if v is None else format(v, "f")

@dataclass
class Player:
    pid: str
    label: str
    last_bid: Decimal = Decimal("0")

@dataclass
class Event:
    event_id: str
    stage: int
    pid: str
    opponent_id: str
    action: str
    bid: Decimal | None
    opponent_previous_bid: Decimal
    event_timestamp: str
    opponent_bid_displayed_at: str
    response_opportunity_started_at: str
    response_submitted_at: str
    rt_a: float
    rt_b: float
    selected_rt: float
    selected_mode: str
    previous_leader_id: str | None
    leader_after_id: str | None
    bid_increment: Decimal | None
    escalation: int
    leader_change: int

@dataclass
class Session:
    sid: str
    prize_usd: Decimal
    rate: Decimal
    prize_toman: Decimal
    rate_source: str
    rate_timestamp: str
    reaction_mode: str
    players: list[Player]
    started_at: str = field(default_factory=now_utc)
    started_clock: float = field(default_factory=time.perf_counter)
    events: list[Event] = field(default_factory=list)
    leader_id: str | None = None
    highest_bid: Decimal = Decimal("0")
    stages: int = 0
    escalation_count: int = 0
    leader_change_count: int = 0
    termination_reason: str = ""

def ask_decision(player: Player, opponent: Player, s: Session):
    print("\n" + "-" * 62)
    print(f"Turn: {player.label} ({player.pid})")
    print(f"Prize: {money(s.prize_toman)} toman")
    print(f"Current highest bid: {money(s.highest_bid)} toman")
    print(f"Your last bid: {money(player.last_bid)} toman")
    print(f"Opponent's last bid: {money(opponent.last_bid)} toman")
    display_at, display_clock = now_utc(), time.perf_counter()
    opportunity_at, opportunity_clock = now_utc(), time.perf_counter()
    while True:
        raw = input("Enter a bid in TOMAN, or P to pass: ").strip()
        submitted_at, submitted_clock = now_utc(), time.perf_counter()
        rt_a = max(0.0, submitted_clock - opportunity_clock)
        rt_b = max(0.0, submitted_clock - display_clock)
        if raw.lower() in {"p", "pass", "surrender", "q"}:
            return "pass", None, (display_at, opportunity_at, submitted_at, rt_a, rt_b)
        try:
            bid = dec(raw, "Bid", positive=True)
        except ValueError as e:
            print(f"Input error: {e}")
        else:
            if bid <= s.highest_bid:
                print(f"Bid must exceed {money(s.highest_bid)} toman.")
            else:
                return "bid", bid, (display_at, opportunity_at, submitted_at, rt_a, rt_b)
        # Invalid entries do not count as a decision; restart both clocks.
        display_at, display_clock = now_utc(), time.perf_counter()
        opportunity_at, opportunity_clock = now_utc(), time.perf_counter()

def record_decision(s: Session, p: Player, opp: Player, action: str, bid: Decimal | None, timing):
    display_at, opportunity_at, submitted_at, rt_a, rt_b = timing
    old_leader, old_high = s.leader_id, s.highest_bid
    increment, escalation, leader_change = None, 0, 0
    if action == "bid":
        assert bid is not None
        increment = bid - old_high
        if old_leader is not None:
            escalation = 1
            s.escalation_count += 1
            if p.pid != old_leader:
                leader_change = 1
                s.leader_change_count += 1
        p.last_bid = bid
        s.highest_bid = bid
        s.leader_id = p.pid
    s.stages += 1
    selected_rt = rt_a if s.reaction_mode == MODE_A else rt_b
    s.events.append(Event(
        str(uuid.uuid4()), s.stages, p.pid, opp.pid, action, bid, opp.last_bid,
        submitted_at, display_at, opportunity_at, submitted_at, rt_a, rt_b,
        selected_rt, s.reaction_mode, old_leader, s.leader_id, increment,
        escalation, leader_change))

def play(s: Session):
    order = s.players[:]
    random.shuffle(order)
    first, second = order
    print(f"Opening participant (randomized): {first.label} ({first.pid})")
    current, opponent = first, second
    while True:
        action, bid, timing = ask_decision(current, opponent, s)
        record_decision(s, current, opponent, action, bid, timing)
        if action == "pass":
            if s.leader_id is None and current is first:
                print("No opening bid yet; the second participant gets an opening opportunity.")
                current, opponent = opponent, current
                continue
            s.termination_reason = "opponent_passed_after_valid_bid" if s.leader_id else "both_passed_without_bid"
            break
        current, opponent = opponent, current

def outcome(s: Session):
    ended = now_utc()
    duration = max(0.0, time.perf_counter() - s.started_clock)
    winner = s.leader_id
    loser = next((p.pid for p in s.players if winner and p.pid != winner), None)
    payments = {p.pid: p.last_bid for p in s.players}
    payoffs = {}
    for p in s.players:
        if winner is None:
            payoffs[p.pid] = Decimal("0")
        elif p.pid == winner:
            payoffs[p.pid] = s.prize_toman - p.last_bid
        else:
            payoffs[p.pid] = -p.last_bid
    winning_bid = next((p.last_bid for p in s.players if p.pid == winner), None)
    return {"ended": ended, "duration": duration, "winner": winner, "loser": loser, "payments": payments, "payoffs": payoffs, "winning_bid": winning_bid, 
            "winning_bid_minus_prize": winning_bid - s.prize_toman if winning_bid is not None else None, "winning_bid_ratio": float(winning_bid / s.prize_toman) if winning_bid is not None and s.prize_toman > 0 else None}

FIELDS = ["game_version", "session_id", "round_number", "event_id", "stage_number","participant_id", "opponent_id", "action", "new_bid_toman", "opponent_previous_bid_toman","event_timestamp", "opponent_bid_displayed_at", "response_opportunity_started_at","response_submitted_at", "reaction_time_seconds_mode_a", "reaction_time_seconds_mode_b","selected_reaction_mode", "selected_reaction_time_seconds", "previous_leader_id","leader_after_decision_id", "bid_increment_toman", "is_escalation", "is_leader_change", "prize_usd", "usd_to_toman_rate", "prize_toman", "rate_source", "rate_method", "rate_timestamp", "round_started_at", "round_ended_at", "round_duration_seconds", "total_bids", "total_stages", "escalation_count", "leader_change_count", "winner_id", "loser_id", "winning_bid_toman", "winning_bid_minus_prize_toman", "winning_bid_to_prize_ratio", "participant_final_bid_toman", "participant_payment_toman", "participant_net_payoff_toman", "termination_reason","arousal_condition", "condition_order", "notes"]

def save_csv(s: Session, result: dict, path: Path, notes: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    bids = sum(e.action == "bid" for e in s.events)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for e in s.events:
            p = next(x for x in s.players if x.pid == e.pid)
            row = {"game_version": GAME_VERSION, "session_id": s.sid, 
                   "round_number": 1, 
                   "event_id": e.event_id, 
                   "stage_number": e.stage, 
                   "participant_id": e.pid, 
                   "opponent_id": e.opponent_id, 
                   "action": e.action, 
                   "new_bid_toman": blank(e.bid),
                   "opponent_previous_bid_toman": format(e.opponent_previous_bid, "f"),
                   "event_timestamp": e.event_timestamp, "opponent_bid_displayed_at": e.opponent_bid_displayed_at,"response_opportunity_started_at": e.response_opportunity_started_at,
                   "response_submitted_at": e.response_submitted_at,"reaction_time_seconds_mode_a": f"{e.rt_a:.6f}", "reaction_time_seconds_mode_b": f"{e.rt_b:.6f}","selected_reaction_mode": e.selected_mode, "selected_reaction_time_seconds": f"{e.selected_rt:.6f}","previous_leader_id": e.previous_leader_id or "", "leader_after_decision_id": e.leader_after_id or "","bid_increment_toman": blank(e.bid_increment), "is_escalation": e.escalation,
                   "is_leader_change": e.leader_change, "prize_usd": format(s.prize_usd, "f"),
                   "usd_to_toman_rate": format(s.rate, "f"), "prize_toman": format(s.prize_toman, "f"),
                   "rate_source": s.rate_source, "rate_method": "manual", "rate_timestamp": s.rate_timestamp,
                   "round_started_at": s.started_at, "round_ended_at": result["ended"],
                   "round_duration_seconds": f"{result['duration']:.6f}", "total_bids": bids,
                   "total_stages": s.stages, "escalation_count": s.escalation_count,
                   "leader_change_count": s.leader_change_count, "winner_id": result["winner"] or "",
                   "loser_id": result["loser"] or "", "winning_bid_toman": blank(result["winning_bid"]),
                   "winning_bid_minus_prize_toman": blank(result["winning_bid_minus_prize"]),
                   "winning_bid_to_prize_ratio": "" if result["winning_bid_ratio"] is None else f"{result['winning_bid_ratio']:.6f}",
                   "participant_final_bid_toman": format(p.last_bid, "f"),
                   "participant_payment_toman": format(result["payments"][p.pid], "f"),
                   "participant_net_payoff_toman": format(result["payoffs"][p.pid], "f"),
                   "termination_reason": s.termination_reason, "arousal_condition": "", "condition_order": "", "notes": notes}
            writer.writerow(row)

def main():
    print("Dollar Auction — Thesis Game 1 / local two-player prototype")
    print("Amounts are in TOMAN. Each player pays only their own final bid.")
    print("No fixed increment or maximum bid. Type P to pass.\n")
    prize_usd = ask_decimal("Prize value in USD: ", "Prize value", True)
    rate = ask_decimal("Manual free-market rate (TOMAN per USD): ", "Rate", True)
    rate_source = input("Rate source/description (record what you actually used): ").strip()
    rate_timestamp = now_utc()
    mode = input("Reaction mode [A = opportunity start / B = bid display]: ").strip().lower()
    while mode not in {"a", "b"}:
        mode = input("Enter A or B: ").strip().lower()
    p1_label = input("Participant 1 label (use a pseudonym, not a real name) [Player A]: ").strip() or "Player A"
    p2_label = input("Participant 2 label (use a pseudonym, not a real name) [Player B]: ").strip() or "Player B"
    p1, p2 = Player("P-" + uuid.uuid4().hex[:8].upper(), p1_label), Player("P-" + uuid.uuid4().hex[:8].upper(), p2_label)
    s = Session("S-" + uuid.uuid4().hex, prize_usd, rate, prize_usd * rate, rate_source, rate_timestamp,
                MODE_A if mode == "a" else MODE_B, [p1, p2])
    print(f"\nFixed prize: {money(s.prize_toman)} toman (${money(prize_usd)} × {money(rate)} toman/USD)")
    print(f"Session ID: {s.sid}; rate timestamp (UTC): {rate_timestamp}; method: manual")
    input("Read the same neutral instructions to both participants, then press Enter to start...")
    play(s)
    r = outcome(s)
    print("\nRESULT")
    if r["winner"]:
        winner = next(p for p in s.players if p.pid == r["winner"])
        print(f"Winner: {winner.label} ({winner.pid}); winning bid: {money(r['winning_bid'])} toman")
    else:
        print("No valid bids; no winner.")
    for p in s.players:
        print(f"{p.label}: final bid {money(p.last_bid)} toman; payment {money(r['payments'][p.pid])} toman; net payoff {money(r['payoffs'][p.pid])} toman")
    print(f"Stages: {s.stages}; bids: {sum(e.action == 'bid' for e in s.events)}; escalations: {s.escalation_count}; leader changes: {s.leader_change_count}")
    print(f"Round duration: {r['duration']:.3f} seconds")
    default = f"dollar_auction_game1_{s.sid}.csv"
    out = input(f"CSV path [{default}]: ").strip() or default
    notes = input("Optional non-identifying notes: ").strip()
    save_csv(s, r, Path(out).expanduser(), notes)
    print(f"CSV saved to {Path(out).expanduser().resolve()}")
    print("Research caution: pilot and validate this prototype before collecting study data.")

if __name__ == "__main__":
    main()
