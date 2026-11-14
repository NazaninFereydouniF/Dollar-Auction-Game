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
    s.events.append(Event(f"EVT-{s.stages:03d}", s.stages, p.pid, opp.pid, action, bid, opp.last_bid, submitted_at, display_at, opportunity_at, submitted_at, rt_a, rt_b, selected_rt, s.reaction_mode, old_leader, s.leader_id, increment, escalation, leader_change))

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
    return {"ended": ended, 
            "duration": duration, 
            "winner": winner, 
            "loser": loser,
            "payments": payments, 
            "payoffs": payoffs, 
            "winning_bid": winning_bid,
            "winning_bid_minus_prize": winning_bid - s.prize_toman if winning_bid is not None else None,
            "winning_bid_ratio": float(winning_bid / s.prize_toman) if winning_bid is not None and s.prize_toman > 0 else None}

def validate_game(s: Session, result: dict) -> list[str]:
    #Validate event order, bid progression, leader state, and first-game payoffs. Raises ValueError on inconsistency; returns a short list of passed checks otherwise.
    
    if not s.events:
        raise ValueError("A game must contain at least one decision event.")
    player_ids = {p.pid for p in s.players}
    if len(player_ids) != 2:
        raise ValueError("This prototype must contain exactly two players.")
    if len({e.event_id for e in s.events}) != len(s.events):
        raise ValueError("Duplicate event_id detected.")

    last_bids = {pid: Decimal("0") for pid in player_ids}
    highest = Decimal("0")
    leader = None
    checks = ["two-player roster and unique event IDs"]

    for expected_stage, e in enumerate(s.events, start=1):
        if e.stage != expected_stage:
            raise ValueError(f"Non-sequential stage number at event {expected_stage}.")
        if e.pid not in player_ids or e.opponent_id not in player_ids or e.pid == e.opponent_id:
            raise ValueError(f"Unknown or invalid participant IDs at stage {e.stage}.")
        if e.action not in {"bid", "pass"}:
            raise ValueError(f"Invalid action at stage {e.stage}: {e.action!r}.")
        if e.previous_leader_id != leader:
            raise ValueError(f"Previous leader mismatch at stage {e.stage}.")
        if e.opponent_previous_bid != last_bids[e.opponent_id]:
            raise ValueError(f"Opponent's previous bid mismatch at stage {e.stage}.")

        if e.action == "bid":
            if e.bid is None or e.bid <= highest:
                raise ValueError(f"Bid is missing or not strictly increasing at stage {e.stage}.")
            if e.bid_increment != e.bid - highest:
                raise ValueError(f"Bid increment mismatch at stage {e.stage}.")
            last_bids[e.pid] = e.bid
            highest = e.bid
            leader = e.pid
        elif e.bid is not None:
            raise ValueError(f"Pass action must not contain a bid at stage {e.stage}.")

        if e.leader_after_id != leader:
            raise ValueError(f"Leader-after-decision mismatch at stage {e.stage}.")

    if s.highest_bid != highest or s.leader_id != leader:
        raise ValueError("Final game state does not match the recorded event stream.")
    for p in s.players:
        if p.last_bid != last_bids[p.pid]:
            raise ValueError(f"Final bid mismatch for participant {p.pid}.")

    expected_winner = leader
    if result["winner"] != expected_winner:
        raise ValueError("Winner does not match the final valid bid.")
    for p in s.players:
        expected_payment = last_bids[p.pid]
        if result["payments"][p.pid] != expected_payment:
            raise ValueError(f"Payment mismatch for participant {p.pid}.")
        if expected_winner is None:
            expected_payoff = Decimal("0")
        elif p.pid == expected_winner:
            expected_payoff = s.prize_toman - last_bids[p.pid]
        else:
            expected_payoff = -last_bids[p.pid]
        if result["payoffs"][p.pid] != expected_payoff:
            raise ValueError(f"Net payoff mismatch for participant {p.pid}.")

    checks.extend(["sequential stages and valid action types", "strictly increasing bids and bid increments", "leader and opponent-bid history reconstructed from events", "final bids, winner, payments, and net payoffs consistent with Game 1"])
    return checks

def non_overwriting_path(path: Path) -> Path:
    #Return path if unused, otherwise choose a numbered filename without overwriting.
    if not path.exists():
        return path
    stem, suffix = path.stem, path.suffix
    index = 2
    while True:
        candidate = path.with_name(f"{stem}_{index}{suffix}")
        if not candidate.exists():
            return candidate
        index += 1

def classify_competitive_arousal(bid: Decimal | None, prize: Decimal) -> str | None:
    #Post-hoc operational category from the participant's current bid vs prize.
    """
    A: current bid < 50% of prize; B: 50% of prize through prize inclusive;
    C: current bid > prize. A zero/no-bid state is unclassified.
    This is a behavioral proxy derived after the task, not a direct psychometric
    measurement of subjective arousal.
    """
    if bid is None or bid <= 0 or prize <= 0:
        return None
    if bid < prize / Decimal("2"):
        return "A"
    if bid <= prize:
        return "B"
    return "C"

def build_stage_analysis(s: Session) -> list[dict]:
    #One post-hoc analysis row per decision event, based on that player's current bid at that point in the sequence, not a condition selected at start.
    
    current = {p.pid: Decimal("0") for p in s.players}
    rows = []
    for e in sorted(s.events, key=lambda x: x.stage):
        if e.action == "bid" and e.bid is not None:
            current[e.pid] = e.bid
        bid = current[e.pid]
        level = classify_competitive_arousal(bid, s.prize_toman)
        rows.append({"session_code": s.sid, 
                     "stage_number": e.stage, 
                     "event_code": e.event_id,
                     "participant_id": e.pid, 
                     "opponent_id": e.opponent_id,
                     "action": e.action, 
                     "new_bid_toman": blank(e.bid),
                     "participant_current_bid_toman": format(bid, "f") if bid > 0 else "",
                     "prize_toman": format(s.prize_toman, "f"),
                     "current_bid_to_prize_ratio": f"{float(bid / s.prize_toman):.6f}" if bid > 0 and s.prize_toman > 0 else "",
                     "competitive_arousal_level": level or "",
                     "classification_rule": "A: bid < 50% prize; B: 50% prize <= bid <= 100% prize; C: bid > 100% prize",
                     "classification_is_posthoc_behavioral_proxy": "True",
                     "event_timestamp": e.event_timestamp})
    return rows

def summarize_competitive_arousal(s: Session) -> list[dict]:
    #Per-player stage counts by category and first stage reaching B/C.
    rows = build_stage_analysis(s)
    out = []
    for p in s.players:
        own = [r for r in rows if r["participant_id"] == p.pid]
        levels = [r["competitive_arousal_level"] for r in own if r["competitive_arousal_level"]]
        out.append({"session_code": s.sid,
                    "participant_id": p.pid, 
                    "participant_label": p.label,
                    "final_bid_toman": format(p.last_bid, "f"), 
                    "prize_toman": format(s.prize_toman, "f"),
                    "stages_classified_A": sum(x == "A" for x in levels),
                    "stages_classified_B": sum(x == "B" for x in levels),
                    "stages_classified_C": sum(x == "C" for x in levels),
                    "first_stage_B_or_higher": next((r["stage_number"] for r in own if r["competitive_arousal_level"] in ("B", "C")), ""),
                    "first_stage_C": next((r["stage_number"] for r in own if r["competitive_arousal_level"] == "C"), ""),
                    "highest_level_reached": next((x for x in ("C", "B", "A") if x in levels), "None"),
                    "rule": "A < 50% prize; B >= 50% and <= prize; C > prize",
                    "interpretation_note": "Behavioral classification based on bid trajectory; not a direct self-report/physiological arousal measure."})
    return out

def save_analysis_csv(s: Session, path: Path):
    #Write stage-level classifications and a separate participant summary.
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = build_stage_analysis(s)
    if rows:
        with path.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader(); writer.writerows(rows)
    summary_path = path.with_name(path.stem.replace("_stage_analysis", "_participant_summary") + path.suffix)
    summary = summarize_competitive_arousal(s)
    with summary_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary[0].keys()) if summary else ["session_code"])
        writer.writeheader(); writer.writerows(summary)
    return path, summary_path

FIELDS = ["game_version", "session_code", "round_number", "event_code", "stage_number","participant_id", "opponent_id", "action", "new_bid_toman", "opponent_previous_bid_toman","event_timestamp", "opponent_bid_displayed_at", "response_opportunity_started_at","response_submitted_at", "reaction_time_seconds_mode_a", "reaction_time_seconds_mode_b", "selected_reaction_mode", "selected_reaction_time_seconds", "previous_leader_id","leader_after_decision_id", "bid_increment_toman", "is_escalation", "is_leader_change","prize_usd", "usd_to_toman_rate", "prize_toman", "rate_source", "rate_method", "rate_timestamp","round_started_at", "round_ended_at", "round_duration_seconds", "total_bids", "total_stages","escalation_count", "leader_change_count", "winner_id", "loser_id", "winning_bid_toman","winning_bid_minus_prize_toman", "winning_bid_to_prize_ratio", "participant_final_bid_toman","participant_payment_toman", "participant_net_payoff_toman", "termination_reason","participant_current_bid_toman", "competitive_arousal_level", "competitive_arousal_rule","competitive_arousal_ratio_to_prize", "chronological_bid_sequence_toman","chronological_bid_sequence", "notes"]

def save_csv(s: Session, result: dict, path: Path, notes: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    bids = sum(e.action == "bid" for e in s.events)
    player_labels = {p.pid: p.label for p in s.players}
    bid_events = [e for e in s.events if e.action == "bid" and e.bid is not None]
    chronological_amounts = " → ".join(money(e.bid) for e in bid_events)
    chronological_labeled = " → ".join(f"{player_labels[e.pid]}: {money(e.bid)}" for e in bid_events)
    current_bids = {p.pid: Decimal("0") for p in s.players}
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for e in s.events:
            p = next(x for x in s.players if x.pid == e.pid)
            if e.action == "bid" and e.bid is not None:
                current_bids[e.pid] = e.bid
            current_bid = current_bids[e.pid]
            row = {"game_version": GAME_VERSION,
                   "session_code": s.sid, 
                   "round_number": 1,
                   "event_code": e.event_id, 
                   "stage_number": e.stage, 
                   "participant_id": e.pid,
                   "opponent_id": e.opponent_id, 
                   "action": e.action, 
                   "new_bid_toman": blank(e.bid),
                   "opponent_previous_bid_toman": format(e.opponent_previous_bid, "f"),
                   "event_timestamp": e.event_timestamp, 
                   "opponent_bid_displayed_at": e.opponent_bid_displayed_at,
                   "response_opportunity_started_at": e.response_opportunity_started_at,
                   "response_submitted_at": e.response_submitted_at,
                   "reaction_time_seconds_mode_a": f"{e.rt_a:.6f}", 
                   "reaction_time_seconds_mode_b": f"{e.rt_b:.6f}",
                   "selected_reaction_mode": e.selected_mode,
                   "selected_reaction_time_seconds": f"{e.selected_rt:.6f}",
                   "previous_leader_id": e.previous_leader_id or "", 
                   "leader_after_decision_id": e.leader_after_id or "",
                   "bid_increment_toman": blank(e.bid_increment), 
                   "is_escalation": e.escalation,
                   "is_leader_change": e.leader_change, 
                   "prize_usd": format(s.prize_usd, "f"),
                   "usd_to_toman_rate": format(s.rate, "f"), 
                   "prize_toman": format(s.prize_toman, "f"),
                   "rate_source": s.rate_source, 
                   "rate_method": "manual", 
                   "rate_timestamp": s.rate_timestamp,
                   "round_started_at": s.started_at, 
                   "round_ended_at": result["ended"],
                   "round_duration_seconds": f"{result['duration']:.6f}", 
                   "total_bids": bids,
                   "total_stages": s.stages, 
                   "escalation_count": s.escalation_count,
                   "leader_change_count": s.leader_change_count, 
                   "winner_id": result["winner"] or "",
                   "loser_id": result["loser"] or "", 
                   "winning_bid_toman": blank(result["winning_bid"]),
                   "winning_bid_minus_prize_toman": blank(result["winning_bid_minus_prize"]),
                   "winning_bid_to_prize_ratio": "" if result["winning_bid_ratio"] is None else f"{result['winning_bid_ratio']:.6f}",
                   "participant_final_bid_toman": format(p.last_bid, "f"),
                   "participant_payment_toman": format(result["payments"][p.pid], "f"),
                   "participant_net_payoff_toman": format(result["payoffs"][p.pid], "f"),
                   "termination_reason": s.termination_reason,
                   "participant_current_bid_toman": format(current_bid, "f") if current_bid > 0 else "",
                   "competitive_arousal_level": classify_competitive_arousal(current_bid, s.prize_toman) or "",
                   "competitive_arousal_rule": "A: bid < 0.5*prize; B: 0.5*prize <= bid <= prize; C: bid > prize",
                   "competitive_arousal_ratio_to_prize": f"{float(current_bid / s.prize_toman):.6f}" if s.prize_toman > 0 and current_bid > 0 else "",
                   "chronological_bid_sequence_toman": chronological_amounts,
                   "chronological_bid_sequence": chronological_labeled, "notes": notes}
            writer.writerow(row)

def main():
    print("Dollar Auction — Thesis Game 1 / local two-player prototype")
    print("Amounts are in TOMAN. Each player pays only their own final bid.")
    print("No fixed increment or maximum bid. Type P to pass.\n")
    prize_usd = ask_decimal("Prize value in USD: ", "Prize value", True)
    rate = ask_decimal("Manual free-market rate (TOMAN per USD): ", "Rate", True)
    rate_timestamp = now_utc() #capture when the rate is entered, not after later prompts
    rate_source = input("Rate source/description (record what you actually used): ").strip()
    if not rate_source:
        rate_source = "Not provided by researcher"
    mode = input("Reaction mode [A = opportunity start / B = bid display]: ").strip().lower()
    while mode not in {"a", "b"}:
        mode = input("Enter A or B: ").strip().lower()
    p1_label = input("Participant 1 label (use a pseudonym, not a real name) [Player A]: ").strip() or "Player A"
    p2_label = input("Participant 2 label (use a pseudonym, not a real name) [Player B]: ").strip() or "Player B"
    p1, p2 = Player("P-" + uuid.uuid4().hex[:8].upper(), p1_label), Player("P-" + uuid.uuid4().hex[:8].upper(), p2_label)
    s = Session("SES-" + datetime.now(timezone.utc).strftime("%Y%m%d") + "-" + uuid.uuid4().hex[:4].upper(), prize_usd, rate, prize_usd * rate, rate_source, rate_timestamp, MODE_A if mode == "a" else MODE_B, [p1, p2])
    print(f"\nFixed prize: {money(s.prize_toman)} toman (${money(prize_usd)} × {money(rate)} toman/USD)")
    print(f"Session ID: {s.sid}; rate timestamp (UTC): {rate_timestamp}; method: manual")
    input("Read the same neutral instructions to both participants, then press Enter to start...")
    play(s)
    r = outcome(s)
    try:
        checks = validate_game(s, r)
    except ValueError as exc:
        print(f"VALIDATION FAILED: {exc}")
        print("The result will not be written as a validated CSV. Preserve the session details for debugging.")
        return
    print("\nVALIDATION PASSED")
    for check in checks:
        print(f"  - {check}")
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
    requested_path = Path(out).expanduser()
    safe_path = non_overwriting_path(requested_path)
    if safe_path != requested_path:
        print(f"File already exists; preserving it. New output path: {safe_path}")
    save_csv(s, r, safe_path, notes)
    print(f"CSV saved to {safe_path.resolve()}")
    print("Research caution: pilot and validate this prototype before collecting study data.")

if __name__ == "__main__":
    main()
