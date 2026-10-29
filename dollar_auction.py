import csv
import random
import time
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

CENT = Decimal("0.01")

CSV_FIELDS = ["session_id", "round_number", "stage_number", "bidder_id", "opponent_id",
    "opponent_previous_bid_toman", "new_bid_toman", "action_status", "event_timestamp",
    "winner_id", "loser_id", "participant_1_id", "participant_1_final_bid_toman",
    "participant_1_final_payment_toman", "participant_1_net_payoff_toman",
    "participant_2_id", "participant_2_final_bid_toman",
    "participant_2_final_payment_toman", "participant_2_net_payoff_toman",
    "prize_value_toman", "round_duration_seconds","termination_reason"]

def amount(value):
    return value.quantize(CENT, rounding=ROUND_HALF_UP)

def fmt(value):
    return f"{amount(value):f}"

def display(value):
    return f"{amount(value):,.2f}".rstrip("0").rstrip(".")

def parse_amount(raw):
    try:
        value = Decimal(raw.strip().replace(",", ""))
        if not value.is_finite() or value <= 0:
            return None
        return amount(value)
    except (InvalidOperation, ValueError, AttributeError):
        return None

def ask_amount(prompt, default):
    while True:
        raw = input(f"{prompt} [{default}]: ").strip() or str(default)
        value = parse_amount(raw)
        if value is not None:
            return value
        print("Enter a positive amount, e.g. 64700 or 64700.50.")

def ask_integer(prompt, default):
    while True:
        raw = input(f"{prompt} [{default}]: ").strip()
        if not raw:
            return default
        try:
            value = int(raw)
            if value >= 1:
                return value
        except ValueError:
            pass
        print("Enter an integer greater than zero.")

def ask_yes_no(prompt, default=True):
    suffix = "Y/n" if default else "y/N"
    while True:
        raw = input(f"{prompt} ({suffix}): ").strip().lower()
        if not raw:
            return default
        if raw in {"y", "yes", "b", "بله"}:
            return True
        if raw in {"n", "no", "خ", "خیر"}:
            return False
        print("Please answer yes or no.")

def ask_id(prompt, default):
    while True:
        value = input(f"{prompt} — anonymous ID only [{default}]: ").strip() or default
        if "," not in value and "\n" not in value and "\r" not in value:
            return value
        print("The ID cannot contain commas or line breaks.")

def timestamp():
    return datetime.now().astimezone().isoformat(timespec="milliseconds")

def get_decision(player_id, opponent_id, previous_bid=None):
    print(f"\nParticipant: {player_id}")
    print(f"Opponent: {opponent_id}")

    if previous_bid is None:
        print("No bid has been made yet. Enter a positive opening bid.")
    else:
        print(f"Opponent's previous bid: {display(previous_bid)} toman")
        print("Your new bid must be strictly greater than this amount.")

    print("Enter P to surrender/pass.")

    while True:
        raw = input("Bid amount in toman / P: ").strip()

        if raw.lower() in {"p", "pass", "surrender", "تسلیم", "پ"}:
            return None

        bid = parse_amount(raw)
        if bid is None:
            print("Enter a positive amount, e.g. 65000.")
            continue

        if previous_bid is not None and bid <= previous_bid:
            print("The new bid must be greater than ", f"{display(previous_bid)} toman.")
            continue
        return bid

def save_events(csv_path, events):
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    needs_header = not csv_path.exists() or csv_path.stat().st_size == 0

    with csv_path.open("a", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=CSV_FIELDS)
        if needs_header:
            writer.writeheader()
        writer.writerows(events)

def play_round(session_id, round_number, p1, p2, prize, csv_path):
    participants = [p1, p2]
    bids = {p1: Decimal("0"), p2: Decimal("0")}
    has_bid = {p1: False, p2: False}
    events = []
    stage = 0
    start = time.perf_counter()

    print("\n" + "=" * 60)
    print(f"ROUND {round_number}")
    print(f"Anonymous participants: {p1}, {p2}")
    print(f"Prize value: {display(prize)} toman")
    print("Both players pay only their own final bid.")
    print("=" * 60)

    # Randomize the first opportunity in each round.
    random.shuffle(participants)
    first, second = participants
    leader = None

    # Opening opportunity for the first participant.
    stage += 1
    decision_time = timestamp()
    bid = get_decision(first, second)

    events.append({"stage_number": stage,
                  "bidder_id": first,
                  "opponent_id": second,
                  "opponent_previous_bid_toman": "",
                  "new_bid_toman": fmt(bid) if bid is not None else "",
                  "action_status": "continued" if bid is not None else "surrendered",
                  "event_timestamp": decision_time})

    if bid is not None:
        bids[first] = bid
        has_bid[first] = True
        leader = first
    else:
        # If the first participant does not open, the second can open.
        stage += 1
        decision_time = timestamp()
        bid = get_decision(second, first)

        events.append({"stage_number": stage,
                      "bidder_id": second,
                      "opponent_id": first,
                      "opponent_previous_bid_toman": "",
                      "new_bid_toman": fmt(bid) if bid is not None else "",
                      "action_status": "continued" if bid is not None else "surrendered",
                      "event_timestamp": decision_time})

        if bid is not None:
            bids[second] = bid
            has_bid[second] = True
            leader = second

    termination_reason = ("no_bids_both_declined_to_open" if leader is None else "")

    # The non-leading participant responds to each new high bid.
    while leader is not None:
        challenger = p2 if leader == p1 else p1
        previous_bid = bids[leader]

        stage += 1
        decision_time = timestamp()
        new_bid = get_decision(challenger, leader, previous_bid)

        events.append({"stage_number": stage,
                      "bidder_id": challenger,
                      "opponent_id": leader,
                      "opponent_previous_bid_toman": fmt(previous_bid),
                      "new_bid_toman": fmt(new_bid) if new_bid is not None else "",
                      "action_status": ("continued" if new_bid is not None else "surrendered"),
                      "event_timestamp": decision_time})

        if new_bid is None:
            termination_reason = "challenger_surrendered"
            break

        bids[challenger] = new_bid
        has_bid[challenger] = True
        leader = challenger

    duration = round(time.perf_counter() - start, 3)

    # Determine final outcome under Version 1 payment rules.
    if leader is None:
        winner = ""
        loser = ""
        payment_1 = Decimal("0")
        payment_2 = Decimal("0")
        payoff_1 = Decimal("0")
        payoff_2 = Decimal("0")
    else:
        winner = leader
        loser = p2 if winner == p1 else p1

        payment_1 = bids[p1] if has_bid[p1] else Decimal("0")
        payment_2 = bids[p2] if has_bid[p2] else Decimal("0")

        payoff_1 = prize - payment_1 if winner == p1 else -payment_1
        payoff_2 = prize - payment_2 if winner == p2 else -payment_2

    # Add final outcome fields to every decision row.
    for event in events:
        event.update({"session_id": session_id,
                      "round_number": round_number,
                      "winner_id": winner,
                      "loser_id": loser,
                      "participant_1_id": p1,
                      "participant_1_final_bid_toman": fmt(bids[p1]),
                      "participant_1_final_payment_toman": fmt(payment_1),
                      "participant_1_net_payoff_toman": fmt(payoff_1),
                      "participant_2_id": p2,
                      "participant_2_final_bid_toman": fmt(bids[p2]),
                      "participant_2_final_payment_toman": fmt(payment_2),
                      "participant_2_net_payoff_toman": fmt(payoff_2),
                      "prize_value_toman": fmt(prize),
                      "round_duration_seconds": duration,
                      "termination_reason": termination_reason})

    save_events(csv_path, events)

    print("\n--- ROUND RESULT ---")
    print(f"Winner: {winner or 'No winner'}")
    print(f"Loser: {loser or 'No loser'}")
    print(f"{p1}: final bid={display(bids[p1])}, ", f"payment={display(payment_1)}, net payoff={display(payoff_1)} toman")
    print(f"{p2}: final bid={display(bids[p2])}, ", f"payment={display(payment_2)}, net payoff={display(payoff_2)} toman")
    print(f"Duration: {duration} seconds")
    print(f"Saved to: {csv_path.resolve()}")

    return {"winner": winner, "p1_payoff": payoff_1, "p2_payoff": payoff_2}

def main():
    print("=" * 72)
    print("DOLLAR AUCTION — VERSION 1")
    print("=" * 72)
    print("Payment rule: both participants pay only their final bid.")
    print("A new bid must be strictly greater than the opponent's previous bid.")
    print("No fixed increment or predefined maximum bid is imposed.")
    print("\nData recorded for each decision:")
    print("1. Stage number and anonymous bidder ID")
    print("2. Exact bid amount")
    print("3. Opponent's previous bid and new bid")
    print("4. Decision timestamp")
    print("5. Continued or surrendered status")
    print("6. Winner/loser IDs, final payments and net payoffs")
    print("Do not enter real names or identifying information.")

    p1 = ask_id("Participant 1 ID", "P001")
    p2 = ask_id("Participant 2 ID", "P002")
    while p2 == p1:
        print("The two participant IDs must be different.")
        p2 = ask_id("Participant 2 ID", "P002")

    prize = ask_amount("Prize value in toman", "64700")
    rounds = ask_integer("Number of rounds", 1)

    filename = input("CSV output filename [dollar_auction_events.csv]: ").strip() or "dollar_auction_events.csv"
    csv_path = Path(filename).expanduser()
    session_id = datetime.now().astimezone().strftime("session_%Y%m%d_%H%M%S_%z")

    print("\nSession configuration")
    print(f"Session ID: {session_id}")
    print(f"Participants: {p1}, {p2}")
    print(f"Prize: {display(prize)} toman")
    print(f"Rounds: {rounds}")
    print(f"CSV file: {csv_path}")

    if not ask_yes_no("Start the session?", True):
        print("Session cancelled.")
        return

    results = []
    for round_number in range(1, rounds + 1):
        if round_number > 1 and not ask_yes_no(f"Start round {round_number}?", True):
            break

        results.append(play_round(session_id, round_number, p1, p2, prize, csv_path))

    total_p1 = sum((result["p1_payoff"] for result in results), Decimal("0"))
    total_p2 = sum((result["p2_payoff"] for result in results), Decimal("0"))

    print("\n--- SESSION SUMMARY ---")
    print(f"Completed rounds: {len(results)}")
    print(f"{p1} total net payoff: {display(total_p1)} toman")
    print(f"{p2} total net payoff: {display(total_p2)} toman")
    print(f"CSV file: {csv_path.resolve()}")


if __name__ == "__main__":
    main()
