# 🎲 Dollar Auction — Thesis Game 1 (Local Prototype)

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/Interface-CLI_%7C_Tkinter_GUI-blueviolet" alt="CLI / GUI">
  <img src="https://img.shields.io/badge/Output-CSV_decision--level-brightgreen" alt="CSV Output">
  <img src="https://img.shields.io/badge/Dependencies-Standard_Library-success" alt="Standard Library only">
  <img src="https://img.shields.io/badge/License-MIT-lightgrey" alt="MIT License">
</p>

Local two-player prototype for thesis **Game 1 (last-bid payment rule)** using **only the Python standard library**. No network, no computer agents.

## 📖 About the Game

Variant of Shubik's Dollar Auction (1971) adapted for this thesis:

- The highest bidder wins the prize.
- **Each participant pays only their own final bid** (winner and runner-up both pay).
- A player who never bids pays zero.
- Each new bid must be **strictly greater** than the current highest bid.
- **No fixed increment, no predefined maximum.**
- The game ends on `opponent_passed_after_valid_bid` or `both_passed_without_bid`.

Payoffs (toman):

- Winner: `prize_toman - winner_final_bid`
- Loser: `-loser_final_bid`
- No winner: `0, 0`

> Amounts are in **toman**. Prize is entered in **USD** plus a manually entered free-market rate: `prize_toman = prize_usd × rate`. Rate source and UTC timestamp are recorded per session.

## 📁 Files

| File | Role |
|------|------|
| `dollar_auction.py` | CLI engine + validator. Must stay. |
| `dollar_auction_game1_gui_v3.py` | Tkinter GUI. Thin layer on `dollar_auction` (`import dollar_auction as engine`). Both files must be in the same folder. |

Do not rename `dollar_auction` unless you also update the `import` in `gui_v3`.

## ✨ Features

- **Turn-taking local play** with randomized opening order.
- **Reaction-time (RT) measurement, two references:** `A = opportunity start`, `B = opponent display`. Selectable per session.
- **Escalation metrics:** `bid_increment, is_escalation, is_leader_change` + counts.
- **Internal validator `validate_game()`:** checks sequential stages, unique event IDs, strictly increasing bids, leader history, winner/payments/payoffs. Blocks CSV write on failure.
- **Non-overwriting save `non_overwriting_path()`:** auto `file_2.csv` instead of overwrite.
- **GUI timing procedure:** info displayed first, controls activate after 1000 ms (`DISPLAY_TO_OPPORTUNITY_DELAY_MS`). Invalid entries keep the clock running.
- **Anonymous IDs:** `S-hex` sessions, `P-XXXXXXXX` participants, pseudonym labels only.

## 🚀 Usage

Requires Python 3.10+ . No install.

## 🕹️ Sample Flow

1. Enter prize USD + manual rate + source + RT mode A/B + labels
2. Read the same neutral instructions to both participants
3. Alternate bids (must exceed highest) or Pass
4. Review validation + result, save decision-level CSV

## 📊 CSV Output
One row per decision (50 columns, utf-8-sig). Key fields: game_version, session_id, event_id, stage_number, participant_id, opponent_id, action(bid/pass), new_bid_toman, opponent_previous_bid_toman, event_timestamp, opponent_bid_displayed_at, response_opportunity_started_at, response_submitted_at, reaction_time_seconds_mode_a/b, selected_reaction_time_seconds, previous_leader_id, leader_after_decision_id, bid_increment_toman, is_escalation, is_leader_change, prize_usd, usd_to_toman_rate, prize_toman, winner_id, loser_id, participant_final_bid/payment/net_payoff, plus arousal_condition, condition_order, notes (reserved).

Payoff convention:

* Winner: prize value - winner's final bid
* Runner-up: - runner-up's final bid
* A player who never bids has a final bid of zero and pays nothing.

## ⚠️ Research Notes
Intermediate prototype with internal consistency checks — not a validated laboratory instrument. Before formal data collection define a preregistered protocol, instructions, consent/debriefing, exclusion criteria, counterbalancing, and ethics approval. No online play, no arousal manipulation, no computer agents. Pilot and validate first.

## ⚖️ License
This project is provided for educational and research purposes.
<p>Released under the MIT License · See the <a href="LICENSE">LICENSE</a> file for details.</p>
<p>⚠️ Educational use only — not a validated experimental protocol for human-subject research.</p>


## 🤝 Contributing

Ideas and improvements are welcome! Fork the project, make your changes, and open a Pull Request. You can also open an Issue to report a bug or suggest a feature.

<p align="center"><i>Made with ❤️</i></p>
