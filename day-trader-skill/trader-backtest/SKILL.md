---
name: trader-backtest
description: >-
  Backtester. The evidence check that comes before every other skill: tests
  the opening-range breakout on 40 liquid stocks over 60 days of 5-minute
  bars, after slippage and commissions, with pessimistic fills (entry on the
  next bar's open, stops that gap fill at the open, targets that must trade
  through). Tries 432 variants (range length, stop rule, target, relative
  volume, VWAP and SPY filters), picks the best on the oldest 60 % of the
  days and grades it ONLY on the newest 40 %. Writes trader/backtest.json;
  trader-risk blocks ORB entries unless it says edge: true. Use when the user
  says "backtest", "does this strategy work", "is this profitable", "test the
  setup", "is there an edge", "should I trade ORB", "what settings work",
  weekly before trading, or whenever trader-risk says the backtest is missing
  or stale.
argument-hint: "[run | show] [--symbols A,B,C]"
---

# trader-backtest

The other ten skills find a trade, time it, size it and check it against
your limits. None of them asks whether the setup makes money. This one does,
and it is built to be hard to fool: costs on every fill, entries you could
really get, and a verdict that only counts days the settings were not picked
on. Most people who day trade lose money. Most setups that look good on the
days they were tuned on fail on the next ones. This skill exists to catch
that before it costs you. Not financial advice.

`${CLAUDE_SKILL_DIR}` below is this skill's folder (where this SKILL.md lives).

```bash
python3 "${CLAUDE_SKILL_DIR}/backtest.py" run                          # 40 liquid stocks + SPY -> trader/backtest.json
python3 "${CLAUDE_SKILL_DIR}/backtest.py" run --symbols TSLA,NVDA,AMD   # your own list (SPY is added)
python3 "${CLAUDE_SKILL_DIR}/backtest.py" run --watchlist trader/watchlist.json
python3 "${CLAUDE_SKILL_DIR}/backtest.py" run --save trader/charts     # keep the downloads
python3 "${CLAUDE_SKILL_DIR}/backtest.py" run --offline trader/charts  # re-run on them, no network
python3 "${CLAUDE_SKILL_DIR}/backtest.py" run --slip-bps 5 --commission 0.005
python3 "${CLAUDE_SKILL_DIR}/backtest.py" show
```

Exit code 0 when it found an edge, 1 when it did not, 2 when it could not run.
It takes about a minute: one Yahoo request per symbol.

## What it reads and writes

| file | what |
| --- | --- |
| `trader/config.json` | `no_entries_before`, `no_entries_after`, `flat_by`: the backtest trades the same window trader-risk allows |
| `trader/backtest.json` | written: the costs, the default rule's numbers, the best variant in- and out-of-sample, `edge`, `edge_reason`, the settings to use, every out-of-sample trade |

## The fills (pessimistic on purpose)

- Signal: the first 5-minute close above the opening-range high, inside the
  entry window.
- Entry: the NEXT bar's open plus slippage. You cannot buy the close you
  just saw.
- Stop: the stop price minus slippage. If a bar opens below the stop, the
  fill is that open minus slippage: a gap does not respect your stop.
- Target: a limit order, filled only when the high trades through it.
- A bar that touches both the stop and the target counts as the stop.
- Flat by: the close of the bar before `flat_by`, minus slippage.
- Costs: `--slip-bps` per side (default 3, at least 1 cent) and
  `--commission` per share per side (default 0, like Alpaca).

## The verdict

The days are split by date. The oldest 60 % pick the best variant
(in-sample); the newest 40 % grade it (out-of-sample). `edge` is true only
when, out-of-sample: 30 or more trades, an average of at least +0.05R after
costs, a t-stat of at least 1.5, a profit factor of at least 1.1, and the
variant also made money in-sample. Anything less and the honest reading is
"no edge": the best variant was the luckiest one on the days it was picked
on.

## How to present the result

1. Run `backtest.py run` (or `show` if it ran today).
2. Lead with the verdict line: EDGE yes or no, and why.
3. Show the pack's default rule (15-minute range, stop at the midpoint, 1R)
   after costs, then the best variant in- and out-of-sample. Say plainly
   when the out-of-sample number is negative.
4. If edge is false: say the setup lost money after costs on days it was not
   tuned on, that trader-risk will block ORB entries while `require_edge` is
   on, and that not trading is the result that keeps the money. Do not hunt
   for a different setting to make it look better: that is the overfitting
   this test exists to catch.
5. If edge is true: give the exact settings it prints for trader-scanner,
   trader-entry and trader-exit and the filters, and say to paper trade it
   first and compare real fills against the backtest.
6. Re-run it weekly. trader-risk treats a backtest older than
   `max_backtest_age_days` (default 7) as missing.

## Example

The run of November 16, 2026 on 39 stocks, 60 days, 3 bps a side:

```
The pack's default (15-min range, stop or_mid, 1R, no filters):
  in-sample      734 trades, win 44 %, avg -0.111R, total -81.8R, PF 0.77, t -3.37
  out-of-sample  535 trades, win 45 %, avg -0.086R, total -46.0R, PF 0.82, t -2.21
Best of 432 variants on the in-sample days: 30-min range, stop atr:1.5, target 2R, rvol >= 1.5
  in-sample      64 trades, win 55 %, avg +0.316R, PF 1.78
  out-of-sample  66 trades, win 29 %, avg -0.306R, PF 0.52
1 % of the variants were profitable out-of-sample.
EDGE: no
```

Even with zero costs the default rule lost (-0.055R in-sample, -0.040R
out-of-sample). That is the finding: in that market the breakout itself had
no edge, and costs made it worse.

## Rules

- Long only, like the rest of the pack. A falling market hurts every long
  breakout; the SPY filter is there for that.
- 60 days is one market regime. An edge in it can vanish in the next.
- Free Yahoo data, 5-minute bars, regular session only. No pre-market.
- Never present a backtest as a promise. Never skip the out-of-sample number.
- Nothing here places an order. Every order still goes through trader-risk
  and your yes in trader-broker.
