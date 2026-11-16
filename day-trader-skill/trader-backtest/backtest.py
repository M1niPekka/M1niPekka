#!/usr/bin/env python3
"""Backtester for trader-backtest. Standard library only.

Answers the one question the other ten skills cannot: does the setup make
money AFTER costs, on many stocks, on days it was NOT tuned on?

    python3 backtest.py run                                  # default liquid list + SPY, 60 days of 5-min bars
    python3 backtest.py run --symbols TSLA,NVDA,AMD,META      # your own list (SPY is added for the market filter)
    python3 backtest.py run --watchlist trader/watchlist.json
    python3 backtest.py run --offline DIR                    # saved <SYM>-60d5m.json(.gz) files, no network
    python3 backtest.py run --slip-bps 3 --commission 0.0    # costs per side
    python3 backtest.py show                                 # print the saved trader/backtest.json

How it works
  1. 60 days of 5-minute bars per symbol (Yahoo, the same reader as trader-timemachine).
     Full sessions only (78 bars, 9:30 to 16:00 New York).
  2. Every variant of the opening-range breakout (long only, like the rest of
     the pack) is traded on every symbol and every day:
        opening range   5, 15 or 30 minutes
        stop            or_mid, or_low, atr:1.5 (1.5 x ATR(14) of the 5-min bars to the entry)
        target          1R, 2R, 3R, or 10R (in practice: hold to flat_by)
        filters         relative volume of the opening range >= 0 / 1.5 / 2.5 times its
                        20-day average; close above the session VWAP or not; SPY above
                        its own VWAP at the signal or not
  3. Fills are deliberately pessimistic:
        signal  = the first 5-min CLOSE above the opening-range high, inside the
                  no_entries_before / no_entries_after window
        entry   = the NEXT bar's open + slippage (you cannot buy the close you just saw)
        stop    = the stop price - slippage; if a bar OPENS below the stop (a gap),
                  the open - slippage. A bar that touches stop and target counts the stop.
        target  = a limit: only when the high trades THROUGH it (high > target)
        flat_by = the close of the 15:50 bar (out by 15:55) - slippage
        costs   = slip_bps on each side (min 1 cent) + commission per share each side
  4. Walk-forward: the oldest 60 % of the days pick the best variant (in-sample),
     the newest 40 % grade it (out-of-sample). Only the out-of-sample number
     counts: picking the best of 288 variants on the same days you report
     would flatter any rule.
  5. "edge" is true only when out-of-sample: >= 30 trades, average >= +0.05R net,
     t-stat >= 1.5, profit factor >= 1.1, and the in-sample average was positive.

trader-risk refuses ORB entries when "require_edge" is true (the default in
the config this pack recommends) and trader/backtest.json is missing, older
than 7 days, or says edge: false.

Not a promise. 60 days is one market regime; a rule that worked in it can stop
working in the next one. It is the minimum honest test, not a guarantee.
"""

import argparse
import datetime
import json
import math
import os
import statistics
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "trader-timemachine"))
import timemachine as tm  # noqa: E402  (the pack's own Yahoo reader and session splitter)

SESSION_BARS = tm.SESSION_BARS
OPEN_MIN = tm.OPEN_MIN
DEFAULT_SYMBOLS = ("AAPL,MSFT,NVDA,AMZN,META,GOOGL,TSLA,AMD,NFLX,AVGO,CRM,ORCL,ADBE,INTC,MU,QCOM,"
                   "UBER,SHOP,PLTR,COIN,SNOW,PANW,CRWD,BA,JPM,BAC,XOM,CVX,WMT,COST,DIS,NKE,PYPL,"
                   "XYZ,ROKU,MRNA,LLY,UNH,CAT,GE")
MARKET = "SPY"
OR_MINUTES = (5, 15, 30)
STOPS = ("or_mid", "or_low", "atr:1.5")
TARGETS = (1.0, 2.0, 3.0, 10.0)
RVOLS = (0.0, 1.5, 2.5)
RVOL_DAYS = 20
RVOL_MIN_DAYS = 5
ATR_BARS = 14
MIN_RISK_PCT = 0.05          # same floor as trader-exit: a stop closer than 0.05 % is inside the spread
IS_SHARE = 0.6
EDGE = {"min_trades": 30, "min_avg_r": 0.05, "min_t": 1.5, "min_pf": 1.1}
MIN_IS_TRADES = 30


class BTError(Exception):
    pass


def hhmm_to_min(text):
    h, m = str(text).split(":")
    return int(h) * 60 + int(m)


# ---------------------------------------------------------------- data

def load_sessions(text, sym, now_utc):
    res = tm.chart_result(text, sym)
    _, bars, _ = tm.parse_bars(res, now_utc)
    days = tm.split_sessions(bars)
    full, _ = tm.full_sessions(days, "9999-12-31")
    return full


def day_features(sessions):
    """Per session: cumulative VWAP per bar, and the opening-range volume of each
    length divided by its average over the prior RVOL_DAYS sessions (None until
    RVOL_MIN_DAYS sessions are behind it)."""
    out = []
    for j, (d, D) in enumerate(sessions):
        pv = vol = 0.0
        vwap = []
        for b in D:
            tp = (b["h"] + b["l"] + b["c"]) / 3.0
            pv += tp * (b["v"] or 0)
            vol += b["v"] or 0
            vwap.append(pv / vol if vol else b["c"])
        rv = {}
        for orm in OR_MINUTES:
            n = orm // 5
            now = sum(b["v"] or 0 for b in D[:n])
            prior = [sum(b["v"] or 0 for b in P[:n]) for _, P in sessions[max(0, j - RVOL_DAYS):j]]
            prior = [x for x in prior if x > 0]
            rv[orm] = (now / statistics.mean(prior)) if len(prior) >= RVOL_MIN_DAYS and now > 0 else None
        out.append({"date": d, "vwap": vwap, "rvol": rv})
    return out


def atr_to(D, k, n=ATR_BARS):
    trs, prev = [], None
    for b in D[:k + 1]:
        tr = b["h"] - b["l"]
        if prev is not None:
            tr = max(tr, abs(b["h"] - prev), abs(b["l"] - prev))
        trs.append(tr)
        prev = b["c"]
    use = trs[-n:]
    return sum(use) / len(use)


# ---------------------------------------------------------------- one trade

def slip(price, bps):
    return max(0.01, price * bps / 10000.0) if bps > 0 else 0.0


def trade_day(D, feat, mkt, orm, stop_rule, target_r, rvol_min, vwap_on, mkt_on, cost, window):
    """One symbol, one day, one variant -> a trade dict or None (no signal / filtered)."""
    n = orm // 5
    first_k, last_k, flat_k = window
    oh = max(b["h"] for b in D[:n])
    ol = min(b["l"] for b in D[:n])
    if rvol_min > 0:
        rv = feat["rvol"].get(orm)
        if rv is None or rv < rvol_min:
            return None
    k = None
    for i in range(max(n, first_k), last_k + 1):
        if D[i]["c"] > oh:
            k = i
            break
    if k is None or k + 1 > flat_k:
        return None
    if vwap_on and not D[k]["c"] > feat["vwap"][k]:
        return None
    if mkt_on:
        if mkt is None or not mkt["D"][k]["c"] > mkt["vwap"][k]:
            return None
    bps, comm = cost
    e_raw = D[k + 1]["o"]
    entry = e_raw + slip(e_raw, bps)
    if stop_rule == "or_mid":
        stop = math.floor((oh + ol) / 2 * 100) / 100.0
    elif stop_rule == "or_low":
        stop = math.floor(ol * 100) / 100.0
    else:
        mult = float(stop_rule.split(":")[1])
        stop = math.floor((D[k]["c"] - mult * atr_to(D, k)) * 100) / 100.0
    risk = entry - stop
    if risk <= entry * MIN_RISK_PCT / 100.0:
        return None          # the next open is already at or under the stop: no trade
    target = round(entry + target_r * risk, 2)
    exit_px, how = None, "flat"
    for i in range(k + 1, flat_k + 1):
        b = D[i]
        if i > k + 1 and b["o"] <= stop:
            exit_px, how = b["o"] - slip(b["o"], bps), "gap"
            break
        if b["l"] <= stop:
            exit_px, how = stop - slip(stop, bps), "stop"
            break
        if b["h"] > target:
            exit_px, how = target, "target"
            break
    if exit_px is None:
        c = D[flat_k]["c"]
        exit_px = c - slip(c, bps)
    pnl = exit_px - entry - 2 * comm
    return {"entry": round(entry, 4), "stop": stop, "exit": round(exit_px, 4), "how": how,
            "R": pnl / risk, "k": k}


# ---------------------------------------------------------------- stats

def stats(rs):
    n = len(rs)
    if not n:
        return {"trades": 0}
    wins = [r for r in rs if r > 0]
    losses = [-r for r in rs if r < 0]
    avg = statistics.mean(rs)
    sd = statistics.stdev(rs) if n > 1 else 0.0
    eq = peak = dd = 0.0
    for r in rs:
        eq += r
        peak = max(peak, eq)
        dd = max(dd, peak - eq)
    return {"trades": n, "win_rate": round(len(wins) / n, 3), "avg_R": round(avg, 3),
            "total_R": round(sum(rs), 2), "t_stat": round(avg / (sd / math.sqrt(n)), 2) if sd > 0 else None,
            "profit_factor": round(sum(wins) / sum(losses), 2) if losses else None,
            "max_drawdown_R": round(dd, 2)}


def has_edge(is_s, oos_s):
    if not oos_s.get("trades") or oos_s["trades"] < EDGE["min_trades"]:
        return False, "only %d out-of-sample trades (need %d)" % (oos_s.get("trades", 0), EDGE["min_trades"])
    if (is_s.get("avg_R") or 0) <= 0:
        return False, "it lost money in-sample"
    if oos_s["avg_R"] < EDGE["min_avg_r"]:
        return False, "out-of-sample average %+.3fR is under +%.2fR" % (oos_s["avg_R"], EDGE["min_avg_r"])
    if (oos_s.get("t_stat") or 0) < EDGE["min_t"]:
        return False, "out-of-sample t-stat %s is under %.1f (could be luck)" % (oos_s.get("t_stat"), EDGE["min_t"])
    if (oos_s.get("profit_factor") or 0) < EDGE["min_pf"]:
        return False, "out-of-sample profit factor %s is under %.1f" % (oos_s.get("profit_factor"), EDGE["min_pf"])
    return True, "passed every out-of-sample test"


# ---------------------------------------------------------------- the run

def variants(with_market):
    out = []
    for orm in OR_MINUTES:
        for st in STOPS:
            for tr in TARGETS:
                for rv in RVOLS:
                    for vw in (False, True):
                        for mk in ((False, True) if with_market else (False,)):
                            out.append({"or_minutes": orm, "stop": st, "target_r": tr, "rvol_min": rv,
                                        "above_vwap": vw, "spy_above_vwap": mk})
    return out


def backtest(data, cfg=None, slip_bps=3.0, commission=0.0, is_share=IS_SHARE, min_is_trades=MIN_IS_TRADES):
    """data = {SYM: [(date, 78 bars)...]} (MARKET optional) -> the backtest document."""
    c = {"no_entries_before": "09:45", "no_entries_after": "15:30", "flat_by": "15:55"}
    c.update(cfg or {})
    first_k = (hhmm_to_min(c["no_entries_before"]) - OPEN_MIN) // 5 - 1
    last_k = (hhmm_to_min(c["no_entries_after"]) - OPEN_MIN) // 5 - 1
    flat_k = min(SESSION_BARS - 1, (hhmm_to_min(c["flat_by"]) - OPEN_MIN) // 5 - 1)
    window = (max(0, first_k), last_k, flat_k)
    mkt = None
    if MARKET in data and data[MARKET]:
        mkt = {d: {"D": D, "vwap": f["vwap"]} for (d, D), f in zip(data[MARKET], day_features(data[MARKET]))}
    syms = sorted(s for s in data if s != MARKET and data[s])
    if not syms:
        raise BTError("no symbol has full sessions to test")
    feats = {s: day_features(data[s]) for s in syms}
    dates = sorted({d for s in syms for d, _ in data[s]})
    if len(dates) < 20:
        raise BTError("only %d trading days in the data; need at least 20" % len(dates))
    cut = dates[int(len(dates) * is_share)]
    vs = variants(mkt is not None)
    results = []
    for v in vs:
        is_r, oos_r, trades = [], [], []
        for s in syms:
            for (d, D), f in zip(data[s], feats[s]):
                t = trade_day(D, f, mkt.get(d) if mkt else None, v["or_minutes"], v["stop"], v["target_r"],
                              v["rvol_min"], v["above_vwap"], v["spy_above_vwap"], (slip_bps, commission), window)
                if t is None:
                    continue
                (is_r if d < cut else oos_r).append(t["R"])
                trades.append((d, s, t))
        results.append({"variant": v, "is": stats(is_r), "oos": stats(oos_r), "_trades": trades})
    ranked = sorted((r for r in results if r["is"].get("trades", 0) >= min_is_trades),
                    key=lambda r: r["is"]["avg_R"], reverse=True)
    if not ranked:
        raise BTError("no variant traded %d times in-sample; add more symbols" % min_is_trades)
    best = ranked[0]
    edge, why = has_edge(best["is"], best["oos"])
    oos_pos = sum(1 for r in results if r["oos"].get("trades", 0) >= 10 and r["oos"]["avg_R"] > 0)
    oos_cnt = sum(1 for r in results if r["oos"].get("trades", 0) >= 10)
    baseline = next(r for r in results if r["variant"] == {
        "or_minutes": 15, "stop": "or_mid", "target_r": 1.0, "rvol_min": 0.0, "above_vwap": False,
        "spy_above_vwap": False})
    v = best["variant"]
    settings = {
        "trader-scanner": "orb --or-minutes %d" % v["or_minutes"],
        "trader-entry": "--or-minutes %d" % v["or_minutes"],
        "trader-exit": "--stop %s --target %gR" % (v["stop"].replace("_", "-"), v["target_r"]),
        "filters": [x for x, on in (("opening-range relative volume >= %g" % v["rvol_min"], v["rvol_min"] > 0),
                                    ("signal close above the session VWAP", v["above_vwap"]),
                                    ("SPY above its VWAP at the signal", v["spy_above_vwap"])) if on],
    }
    sample = [{"date": d, "symbol": s, "entry": t["entry"], "stop": t["stop"], "exit": t["exit"],
               "how": t["how"], "R": round(t["R"], 3)} for d, s, t in best["_trades"] if d >= cut]
    return {
        "created_by": "trader-backtest",
        "created_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "setup": "orb", "side": "buy",
        "symbols": syms, "market_filter": mkt is not None,
        "days": len(dates), "from": dates[0], "to": dates[-1], "oos_from": cut,
        "costs": {"slip_bps_per_side": slip_bps, "commission_per_share_per_side": commission},
        "window": c,
        "variants_tested": len(vs),
        "oos_positive_share": round(oos_pos / oos_cnt, 3) if oos_cnt else None,
        "baseline": {"variant": baseline["variant"], "is": baseline["is"], "oos": baseline["oos"]},
        "best": {"variant": v, "is": best["is"], "oos": best["oos"], "settings": settings},
        "top": [{"variant": r["variant"], "is": r["is"], "oos": r["oos"]} for r in ranked[:10]],
        "edge": edge, "edge_reason": why,
        "oos_trades": sample,
    }


def describe_variant(v):
    bits = ["%d-min range" % v["or_minutes"], "stop %s" % v["stop"],
            "target %gR" % v["target_r"] if v["target_r"] < 10 else "hold to flat_by"]
    if v["rvol_min"]:
        bits.append("rvol >= %g" % v["rvol_min"])
    if v["above_vwap"]:
        bits.append("above VWAP")
    if v["spy_above_vwap"]:
        bits.append("SPY above VWAP")
    return ", ".join(bits)


def fmt_stats(s):
    if not s.get("trades"):
        return "no trades"
    return ("%d trades, win %.0f %%, avg %+.3fR, total %+.1fR, PF %s, t %s, max DD %.1fR"
            % (s["trades"], 100 * s["win_rate"], s["avg_R"], s["total_R"], s.get("profit_factor"),
               s.get("t_stat"), s["max_drawdown_R"]))


def report(doc):
    b, base = doc["best"], doc["baseline"]
    lines = [
        "Backtest: ORB long, %d symbols, %d days (%s to %s), out-of-sample from %s."
        % (len(doc["symbols"]), doc["days"], doc["from"], doc["to"], doc["oos_from"]),
        "Costs: %.1f bps slippage a side (min 1 cent), $%.3f/share commission a side. Entry on the NEXT bar's open."
        % (doc["costs"]["slip_bps_per_side"], doc["costs"]["commission_per_share_per_side"]),
        "",
        "The pack's default (15-min range, stop or_mid, 1R, no filters):",
        "  in-sample      " + fmt_stats(base["is"]),
        "  out-of-sample  " + fmt_stats(base["oos"]),
        "",
        "Best of %d variants on the in-sample days: %s" % (doc["variants_tested"], describe_variant(b["variant"])),
        "  in-sample      " + fmt_stats(b["is"]),
        "  out-of-sample  " + fmt_stats(b["oos"]),
        "",
        "%s of the variants were profitable out-of-sample." % (
            "%.0f %%" % (100 * doc["oos_positive_share"]) if doc["oos_positive_share"] is not None else "None"),
        "",
    ]
    if doc["edge"]:
        s = b["settings"]
        lines += ["EDGE: yes (%s). Trade only this version:" % doc["edge_reason"],
                  "  /trader-scanner %s" % s["trader-scanner"], "  /trader-entry %s" % s["trader-entry"],
                  "  /trader-exit %s" % s["trader-exit"]]
        lines += ["  filter: " + f for f in s["filters"]]
        lines.append("Paper trade it first and compare your fills to these numbers.")
    else:
        lines += ["EDGE: no (%s)." % doc["edge_reason"],
                  "No version of this setup beat its costs on days it was not tuned on. The profitable move is "
                  "not to trade it. trader-risk will block ORB entries while require_edge is on."]
    lines.append("A backtest is one past regime, not a promise.")
    return lines


def write(path, doc):
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1)
        fh.write("\n")


def read_config(path):
    if path and os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as fh:
                c = json.load(fh)
            return c if isinstance(c, dict) else {}
        except ValueError:
            raise BTError("%s is not valid JSON" % path)
    return {}


def symbols_from(a):
    if a.symbols:
        syms = [s.strip().upper() for s in a.symbols.split(",") if s.strip()]
    elif a.watchlist:
        try:
            with open(a.watchlist, encoding="utf-8") as fh:
                syms = [h["symbol"].upper() for h in json.load(fh).get("hits", [])]
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            raise BTError("could not read symbols from %s" % a.watchlist)
    else:
        syms = DEFAULT_SYMBOLS.split(",")
    if MARKET not in syms and not a.no_market:
        syms.append(MARKET)
    return syms


def cmd_run(a):
    now = tm.parse_now(a.now)
    syms = symbols_from(a)
    data, failed = {}, []
    for i, s in enumerate(syms):
        try:
            text = tm.read_offline(a.offline, s) if a.offline else tm.fetch_chart(s)
            if a.save and not a.offline:
                os.makedirs(a.save, exist_ok=True)
                with open(os.path.join(a.save, "%s-60d5m.json" % s), "w", encoding="utf-8") as fh:
                    fh.write(text)
            data[s] = load_sessions(text, s, now)
        except tm.TMError as e:
            failed.append("%s (%s)" % (s, e))
        if not a.offline and i < len(syms) - 1:
            time.sleep(tm.PAUSE)
    doc = backtest(data, read_config(a.config), a.slip_bps, a.commission, min_is_trades=a.min_is_trades)
    doc["failed"] = failed
    if not a.no_write:
        write(a.write, doc)
    if a.json:
        print(json.dumps({k: v for k, v in doc.items() if k != "oos_trades"}, indent=2))
    else:
        print("\n".join(report(doc)))
        if failed:
            print("Skipped %d symbol(s): %s" % (len(failed), "; ".join(failed[:5])))
        if not a.no_write:
            print("Wrote %s." % a.write)
    return 0 if doc["edge"] else 1


def cmd_show(a):
    if not os.path.exists(a.write):
        raise BTError("no %s: run backtest.py run first" % a.write)
    with open(a.write, encoding="utf-8") as fh:
        print("\n".join(report(json.load(fh))))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Backtest the opening-range breakout after costs (trader-backtest).")
    sub = ap.add_subparsers(dest="cmd")
    p = sub.add_parser("run")
    p.add_argument("--symbols", help="comma-separated tickers (default: 40 liquid US stocks)")
    p.add_argument("--watchlist", help="trader/watchlist.json from trader-scanner")
    p.add_argument("--offline", metavar="DIR", help="folder of <SYM>-60d5m.json(.gz) files, no network")
    p.add_argument("--save", metavar="DIR", help="also save each downloaded chart to DIR (re-run with --offline DIR)")
    p.add_argument("--no-market", action="store_true", help="do not add SPY (drops the market filter)")
    p.add_argument("--slip-bps", type=float, default=3.0, help="slippage per side in basis points (default 3)")
    p.add_argument("--commission", type=float, default=0.0, help="commission per share per side (default 0)")
    p.add_argument("--min-is-trades", type=int, default=MIN_IS_TRADES,
                   help="in-sample trades a variant needs to be ranked (default %d)" % MIN_IS_TRADES)
    p.add_argument("--config", default="trader/config.json")
    p.add_argument("--now", help='pin the clock ("2026-10-19 16:05" New York)')
    p.add_argument("--json", action="store_true")
    p.add_argument("--write", default="trader/backtest.json")
    p.add_argument("--no-write", action="store_true")
    p = sub.add_parser("show")
    p.add_argument("--write", default="trader/backtest.json")
    a = ap.parse_args(argv)
    if not a.cmd:
        ap.print_help()
        return 1
    try:
        return {"run": cmd_run, "show": cmd_show}[a.cmd](a)
    except (BTError, tm.TMError) as e:
        print("backtest.py: %s" % e, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
