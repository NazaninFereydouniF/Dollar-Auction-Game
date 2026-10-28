from __future__ import annotations

import csv
import random
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

@dataclass
class Player:
    name: str
    kind: str = "human"          # "human" or "computer"
    strategy: str = "escalating" # used only for computer players
    max_bid: float = 5.0
    bid: float = 0.0
    active: bool = True
    last_action: str = "pass"

@dataclass
class RoundResult:
    session_id: str
    round_number: int
    timestamp: str
    prize_value: float
    increment: float
    player1_name: str
    player1_kind: str
    player1_strategy: str
    player1_final_bid: float
    player1_payoff: float
    player1_won: bool
    player2_name: str
    player2_kind: str
    player2_strategy: str
    player2_final_bid: float
    player2_payoff: float
    player2_won: bool
    winner: str
    runner_up: str
    total_bids: int
    auction_duration_seconds: float
    termination_reason: str

def money(value: float) -> str:
    return f"${value:.2f}"

def ask_float(prompt: str, default: float, minimum: float = 0.01) -> float:
    while True:
        raw = input(f"{prompt} [{default:g}]: ").strip()
        if not raw:
            return default
        try:
            value = float(raw)
            if value < minimum:
                print(f"Please enter a number >= {minimum:g}.")
                continue
            return round(value, 2)
        except ValueError:
            print("Please enter a valid number, e.g. 0.50.")

def ask_int(prompt: str, default: int, minimum: int = 1) -> int:
    while True:
        raw = input(f"{prompt} [{default}]: ").strip()
        if not raw:
            return default
        try:
            value = int(raw)
            if value < minimum:
                print(f"Please enter an integer >= {minimum}.")
                continue
            return value
        except ValueError:
            print("Please enter a whole number.")

def ask_yes_no(prompt: str, default: bool = True) -> bool:
    suffix = "Y/n" if default else "y/N"
    while True:
        raw = input(f"{prompt} ({suffix}): ").strip().lower()
        if not raw:
            return default
        if raw in ("y", "yes", "bale", "بله"):
            return True
        if raw in ("n", "no", "na", "خیر"):
            return False
        print("Please answer y or n.")

def choose(prompt: str, options: Dict[str, str], default: str) -> str:
    print(prompt)
    for key, label in options.items():
        print(f"  {key}) {label}")
    while True:
        raw = input(f"Choice [{default}]: ").strip() or default
        if raw in options:
            return raw
        print("Choose one of:", ", ".join(options))

def make_computer_bid(player: Player, opponent_bid: float, prize: float,
                      increment: float, round_number: int, bid_count: int) -> Optional[float]:
    #Return a legal next bid, or None to pass. Strategies are illustrative heuristics.
    next_bid = round(opponent_bid + increment, 2)
    if next_bid > player.max_bid:
        return None

    strategy = player.strategy
    if strategy == "cautious":
        #Usually stops once the next bid reaches the prize or a small reserve.
        limit = min(player.max_bid, prize * 0.9)
        if next_bid > limit:
            return None
        probability = 0.78 if next_bid <= prize * 0.5 else 0.35
        return next_bid if random.random() < probability else None

    if strategy == "value_limited":
        #Does not voluntarily bid beyond the prize value.
        if next_bid > prize:
            return None
        return next_bid if random.random() < 0.9 else None

    if strategy == "escalating":
        #More likely to continue after investing money, and can exceed the prize.
        #This is a teaching heuristic, not a psychologically validated agent.
        probability = 0.85
        if next_bid > prize:
            probability = 0.62
        if bid_count >= 4:
            probability = min(0.95, probability + 0.08)
        if next_bid > player.max_bid * 0.8:
            probability *= 0.45
        return next_bid if random.random() < probability else None

    if strategy == "random":
        if next_bid > prize * 1.5:
            return None
        return next_bid if random.random() < 0.5 else None

    #Safe fallback
    return next_bid if next_bid <= prize else None


def get_human_decision(player: Player, current_bid: float, increment: float,
                       prize: float, opponent_name: str) -> Optional[float]:
    min_next = round(current_bid + increment, 2)
    print(f"\n{player.name}'s turn")
    print(f"Prize: {money(prize)} | Current high bid: {money(current_bid)}")
    print(f"Minimum raise: {money(min_next)} | Your maximum configured bid: {money(player.max_bid)}")
    print(f"Opponent: {opponent_name}")
    while True:
        raw = input("Enter your next bid, or P to pass: ").strip().lower()
        if raw in ("p", "pass", "پ", "رد"):
            return None
        try:
            bid = round(float(raw), 2)
        except ValueError:
            print("Enter a number (e.g. 1.50) or P to pass.")
            continue
        if bid < min_next:
            print(f"Bid must be at least {money(min_next)}.")
            continue
        if bid > player.max_bid:
            print(f"Bid cannot exceed your configured maximum of {money(player.max_bid)}.")
            continue
        return bid

def save_result(result: RoundResult, csv_path: Path) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    file_exists = csv_path.exists()
    with csv_path.open("a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(asdict(result).keys()))
        if not file_exists:
            writer.writeheader()
        writer.writerow(asdict(result))

def play_round(player1: Player, player2: Player, prize: float, increment: float,
               round_number: int, session_id: str, csv_path: Path,
               show_payoffs: bool = True) -> RoundResult:
    #Play one auction. Both winner and runner-up pay their final bids.
    players = [player1, player2]
    for p in players:
        p.bid = 0.0
        p.active = True
        p.last_action = "pass"

    current_bid = 0.0
    current_bidder: Optional[Player] = None
    previous_bidder: Optional[Player] = None
    bid_count = 0
    start = time.time()
    termination_reason = "both_players_passed_or_declined"

    print("\n" + "=" * 62)
    print(f"ROUND {round_number} — DOLLAR AUCTION")
    print(f"Prize value: {money(prize)} | Minimum increment: {money(increment)}")
    print("Reminder: the winner and the second-highest bidder both pay.")
    print("=" * 62)

    #Initial order is randomized to reduce systematic first-mover advantage.
    order = players[:]
    random.shuffle(order)
    turn_order = order[:]
    consecutive_passes = 0

    while True:
        #A player who is no longer willing to bid can pass. The current leader
        #may still be challenged by the other player; once the non-leader passes,
        #the auction ends because only two players are participating.
        if current_bidder is None:
            player = turn_order[0]
            opponent = turn_order[1]
        else:
            opponent = current_bidder
            player = player1 if opponent is player2 else player2

        if player.kind == "computer":
            time.sleep(0.15)
            proposed = make_computer_bid(player, current_bid, prize, increment,
                                         round_number, bid_count)
            if proposed is not None:
                print(f"{player.name} bids {money(proposed)}.")
            else:
                print(f"{player.name} passes.")
        else:
            proposed = get_human_decision(player, current_bid, increment, prize, opponent.name)

        if proposed is None:
            player.active = False
            player.last_action = "pass"
            consecutive_passes += 1
            if current_bidder is None:
                #No bid has been made yet; offer the other player a chance.
                if consecutive_passes >= 2:
                    termination_reason = "no_bids"
                    break
                turn_order = [turn_order[1], turn_order[0]]
                continue
            #With two players, a pass by the non-leading player ends the auction.
            termination_reason = "challenger_passed"
            break

        previous_bidder = current_bidder
        current_bid = float(proposed)
        current_bidder = player
        player.bid = current_bid
        player.active = True
        player.last_action = "bid"
        bid_count += 1
        consecutive_passes = 0
        print(f"Current leader: {current_bidder.name} at {money(current_bid)}.")

    duration = round(time.time() - start, 3)

    #Resolve final bids. Highest bidder wins; runner-up still pays their own last bid.
    if current_bidder is None:
        winner = "No winner"
        runner_up = "No runner-up"
        p1_payoff = 0.0
        p2_payoff = 0.0
        p1_won = p2_won = False
    else:
        winner_player = current_bidder
        loser_player = player1 if winner_player is player2 else player2
        winner = winner_player.name
        runner_up = loser_player.name
        p1_won = winner_player is player1
        p2_won = winner_player is player2
        p1_payoff = (prize - player1.bid) if p1_won else -player1.bid
        p2_payoff = (prize - player2.bid) if p2_won else -player2.bid

    result = RoundResult(
        session_id=session_id,
        round_number=round_number,
        timestamp=datetime.now().isoformat(timespec="seconds"),
        prize_value=prize,
        increment=increment,
        player1_name=player1.name,
        player1_kind=player1.kind,
        player1_strategy=player1.strategy if player1.kind == "computer" else "",
        player1_final_bid=player1.bid,
        player1_payoff=round(p1_payoff, 2),
        player1_won=p1_won,
        player2_name=player2.name,
        player2_kind=player2.kind,
        player2_strategy=player2.strategy if player2.kind == "computer" else "",
        player2_final_bid=player2.bid,
        player2_payoff=round(p2_payoff, 2),
        player2_won=p2_won,
        winner=winner,
        runner_up=runner_up,
        total_bids=bid_count,
        auction_duration_seconds=duration,
        termination_reason=termination_reason)
    print("\n--- ROUND RESULT ---")
    print(f"Winner: {winner}")
    print(f"Runner-up: {runner_up}")
    print(f"{player1.name}: final bid {money(player1.bid)} | payoff {money(p1_payoff)}")
    print(f"{player2.name}: final bid {money(player2.bid)} | payoff {money(p2_payoff)}")
    if current_bidder is not None and current_bid > prize:
        print("Note: the winning bid exceeded the prize value.")
    if show_payoffs:
        print(f"Combined participant payoff: {money(p1_payoff + p2_payoff)}")
    save_result(result, csv_path)
    print(f"Round data appended to: {csv_path.resolve()}")
    return result


def create_player(name: str, kind: str, strategy: str, max_bid: float) -> Player:
    return Player(name=name, kind=kind, strategy=strategy, max_bid=max_bid)


def main() -> None:
    print("=" * 62)
    print("DOLLAR AUCTION GAME")
    print("A standalone implementation of Shubik's 1971 auction mechanism")
    print("=" * 62)
    print("Rule: highest bidder wins the prize; winner AND runner-up pay.")
    print("This program uses only the Python standard library.\n")

    mode = choose(
        "Select game mode:",
        {"1": "Human vs Human (shared keyboard)",
         "2": "Human vs Computer"},
        "2")
    prize = ask_float("Prize value", 1.00, 0.01)
    increment = ask_float("Minimum bid increment", 0.05, 0.01)
    rounds = ask_int("Number of rounds", 5, 1)
    max_bid_default = max(10.0, prize * 10)
    max_bid = ask_float("Maximum allowed bid per player (safety limit)",
                        max_bid_default, increment)
    csv_name = input("CSV output filename [dollar_auction_results.csv]: ").strip()
    if not csv_name:
        csv_name = "dollar_auction_results.csv"
    csv_path = Path(csv_name).expanduser()
    session_id = datetime.now().strftime("session_%Y%m%d_%H%M%S")

    p1_name = input("Player 1 name [Player 1]: ").strip() or "Player 1"
    player1 = create_player(p1_name, "human", "", max_bid)

    if mode == "1":
        p2_name = input("Player 2 name [Player 2]: ").strip() or "Player 2"
        player2 = create_player(p2_name, "human", "", max_bid)
    else:
        p2_name = input("Computer opponent name [Computer]: ").strip() or "Computer"
        strategy_key = choose(
            "Select computer strategy:",
            {"1": "Cautious", "2": "Value-limited", "3": "Escalating", "4": "Random"},
            "3")
        strategy_map = {"1": "cautious", "2": "value_limited",
                        "3": "escalating", "4": "random"}
        player2 = create_player(p2_name, "computer", strategy_map[strategy_key], max_bid)

    print("\nConfiguration")
    print(f"Prize: {money(prize)} | Increment: {money(increment)} | Rounds: {rounds}")
    print(f"Maximum bid: {money(max_bid)} | Output: {csv_path}")
    if not ask_yes_no("Start the session?", True):
        print("Session cancelled.")
        return

    results = []
    for round_number in range(1, rounds + 1):
        if round_number > 1 and not ask_yes_no(f"Start round {round_number}?", True):
            break
        result = play_round(player1, player2, prize, increment, round_number,
                            session_id, csv_path)
        results.append(result)

    if results:
        print("\n" + "=" * 62)
        print("SESSION SUMMARY")
        print("=" * 62)
        total1 = sum(r.player1_payoff for r in results)
        total2 = sum(r.player2_payoff for r in results)
        wins1 = sum(r.player1_won for r in results)
        wins2 = sum(r.player2_won for r in results)
        print(f"{player1.name}: wins={wins1}, total payoff={money(total1)}")
        print(f"{player2.name}: wins={wins2}, total payoff={money(total2)}")
        print(f"Rounds completed: {len(results)}")
        print(f"Data saved to: {csv_path.resolve()}")
        print("You can open the CSV in Excel, pandas, or another analysis tool.")


if __name__ == "__main__":
    main()
