# 🎲 Dollar Auction Game

A flexible, self-contained implementation of Martin Shubik's **Dollar Auction** (1971) using **only the Python standard library**. Runs in the VS Code terminal and in Jupyter Notebook (via `%run dollar_auction.py`).

## 📖 About the Game

The dollar auction is a classic experiment in game theory and behavioral economics that shows how rational bidders can fall into a "sunk-cost trap".

**Core rules:**

- The highest bidder wins the prize.
- **Both the winner and the runner-up pay their final bids.**
- Any other players pay nothing.
- Each new bid must exceed the current high bid by at least the configured increment.
- The auction ends when no player is willing to raise their bid.

The interesting result: because the runner-up also pays, the urge to "recover losses" can push bids well beyond the prize's value.

## ✨ Features

- **Game modes:** human vs. human (shared keyboard) or human vs. computer.
- **Configurable parameters:** prize value, bid increment, number of rounds, and a safety bid cap.
- **Computer strategies:**
  - `cautious` — typically stops before reaching the prize value.
  - `value_limited` — never voluntarily bids above the prize value.
  - `escalating` — once invested, tends to continue and even exceed the value.
  - `random` — random decisions within the configured cap.
- **Input validation:** all monetary values, integers, yes/no answers, and menu choices are checked.
- **Randomized starting order** each round to reduce systematic first-player advantage.
- **CSV logging:** one row per round, suitable for analysis in Excel, pandas, or other tools.
- **End-of-session summary:** win counts, total profit/loss per player, and the output file path.

## 🚀 Installation & Usage

No dependencies are required—only Python 3.8 or newer.

## 🕹️ Sample Flow

1. Choose the game mode (human/human or human/computer)
2. Set the prize value (default: $1.00) and bid increment (default: $0.05)
3. Set the number of rounds and the safety bid cap
4. Choose the CSV output filename (default: dollar_auction_results.csv)
5. Enter player names and, in computer mode, select the opponent's strategy
6. Play each round, review the result, and have it saved to CSV automatically

## 📊 CSV Output
One CSV row is appended for each completed round. Fields include session and round identifiers, configuration, each player's final bid and payoff, winner, runner-up, number of bids, duration, and termination reason.

Payoff convention:

* Winner: prize value - winner's final bid
* Runner-up: - runner-up's final bid
* A player who never bids has a final bid of zero and pays nothing.

## ⚠️ Research Notes
This is a functional implementation of the core mechanism, not a validated reproduction of a specific 1971 laboratory protocol. Before collecting publishable human-subject data, define a preregistered protocol, counterbalancing/randomization, participant instructions, consent/debriefing, exclusion criteria, and ethics approval as applicable. The current CSV records round-level outcomes, not every decision timestamp or participant-level psychological measure.
The computer agents are simple, illustrative heuristics and are not a substitute for real human participants.

## 📁 Code Structure
| Component | Description |  
|-----------|-------------|  
| `Player` | dataclass holding each player's state |  
| `RoundResult` | dataclass describing a round's result (for CSV output) |  
| `make_computer_bid` | bidding logic for the computer strategies |  
| `get_human_decision` | input and validation of human bids |  
| `play_round` | runs a full auction and computes payoffs |  
| `save_result` | appends a result to the CSV file |  
| `main` | session setup and final summary |  

## ⚖️ License
This project is provided for educational and research purposes.
Suggested license: MIT.

## 🤝 Contributing

Ideas and improvements are welcome! Fork the project, make your changes, and open a Pull Request. You can also open an Issue to report a bug or suggest a feature.

<p align="center"><i>Made with ❤️</i></p>
