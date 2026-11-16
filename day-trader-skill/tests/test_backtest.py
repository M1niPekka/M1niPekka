import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr

from _load import load, FIX

bt = load("trader-backtest", "backtest")

TM_DIR = os.path.join(FIX, "trader-timemachine")
WINDOW = (2, 71, 76)          # 09:45 first entry close, 15:30 last, out by 15:55
COST0 = (0.0, 0.0)


def bar(o, h, l, c, v=1000):
    return {"o": o, "h": h, "l": l, "c": c, "v": v}


def flat_day(px=100.0):
    return [bar(px, px + 0.05, px - 0.05, px) for _ in range(78)]


def feat(D):
    return bt.day_features([("2026-10-01", D)])[0]


class Fills(unittest.TestCase):
    """The fills are pessimistic: next-bar entry, gap stops, targets must trade through."""

    def breakout(self):
        D = flat_day()
        D[0] = bar(100, 101, 99, 100)      # 15-min range 99..101 (bars 0-2)
        D[3] = bar(100.5, 101.6, 100.4, 101.5)  # first close above 101 -> signal at bar 3
        D[4] = bar(101.7, 101.8, 101.6, 101.7)  # entry at this open, 101.70
        for i in range(5, 78):
            D[i] = bar(101.7, 101.75, 101.65, 101.7)
        return D

    def test_entry_is_the_next_open_and_flat_by_closes_it(self):
        D = self.breakout()
        t = bt.trade_day(D, feat(D), None, 15, "or_mid", 10.0, 0, False, False, COST0, WINDOW)
        self.assertEqual((t["k"], t["entry"], t["stop"], t["how"]), (3, 101.7, 100.0, "flat"))
        self.assertAlmostEqual(t["R"], 0.0)

    def test_a_gap_through_the_stop_fills_at_the_open(self):
        D = self.breakout()
        D[10] = bar(98.0, 98.2, 97.5, 98.0)       # opens 2 points under the 100.00 stop
        t = bt.trade_day(D, feat(D), None, 15, "or_mid", 10.0, 0, False, False, COST0, WINDOW)
        self.assertEqual(t["how"], "gap")
        self.assertAlmostEqual(t["R"], (98.0 - 101.7) / 1.7)     # worse than -1R

    def test_the_target_must_trade_through(self):
        D = self.breakout()
        D[10] = bar(101.7, 103.40, 101.6, 103.3)  # 1R target is 103.40: touched, not through
        t = bt.trade_day(D, feat(D), None, 15, "or_mid", 1.0, 0, False, False, COST0, WINDOW)
        self.assertEqual(t["how"], "flat")
        D[10] = bar(101.7, 103.41, 101.6, 103.3)
        t = bt.trade_day(D, feat(D), None, 15, "or_mid", 1.0, 0, False, False, COST0, WINDOW)
        self.assertEqual(t["how"], "target")
        self.assertAlmostEqual(t["R"], 1.0)

    def test_both_in_one_bar_counts_the_stop(self):
        D = self.breakout()
        D[10] = bar(101.7, 104.0, 99.0, 101.7)
        t = bt.trade_day(D, feat(D), None, 15, "or_mid", 1.0, 0, False, False, COST0, WINDOW)
        self.assertEqual(t["how"], "stop")

    def test_costs_make_a_flat_trade_a_loss(self):
        D = self.breakout()
        t = bt.trade_day(D, feat(D), None, 15, "or_mid", 10.0, 0, False, False, (3.0, 0.005), WINDOW)
        self.assertLess(t["R"], 0)

    def test_no_signal_inside_the_window(self):
        D = flat_day()
        self.assertIsNone(bt.trade_day(D, feat(D), None, 15, "or_mid", 1.0, 0, False, False, COST0, WINDOW))

    def test_the_market_filter(self):
        D = self.breakout()
        down = {"D": [bar(50, 50, 49, 49) for _ in range(78)], "vwap": [50.0] * 78}
        self.assertIsNone(bt.trade_day(D, feat(D), down, 15, "or_mid", 1.0, 0, False, True, COST0, WINDOW))
        self.assertIsNotNone(bt.trade_day(D, feat(D), None, 15, "or_mid", 1.0, 0, False, False, COST0, WINDOW))


class Verdict(unittest.TestCase):
    def test_edge_needs_every_test(self):
        good_is = {"trades": 60, "avg_R": 0.2}
        good = {"trades": 40, "avg_R": 0.2, "t_stat": 2.0, "profit_factor": 1.4}
        self.assertTrue(bt.has_edge(good_is, good)[0])
        self.assertFalse(bt.has_edge(good_is, dict(good, trades=20))[0])
        self.assertFalse(bt.has_edge(good_is, dict(good, avg_R=0.01))[0])
        self.assertFalse(bt.has_edge(good_is, dict(good, t_stat=1.0))[0])
        self.assertFalse(bt.has_edge(good_is, dict(good, profit_factor=1.05))[0])
        self.assertFalse(bt.has_edge({"trades": 60, "avg_R": -0.1}, good)[0])

    def test_stats(self):
        s = bt.stats([1.0, -1.0, 1.0, -1.0, 2.0])
        self.assertEqual((s["trades"], s["win_rate"], s["avg_R"], s["profit_factor"], s["max_drawdown_R"]),
                         (5, 0.6, 0.4, 2.0, 1.0))


class TheReelData(unittest.TestCase):
    """TSLA's real 60 days: the reel's rule loses after costs, in- and out-of-sample."""

    @classmethod
    def setUpClass(cls):
        text = bt.tm.read_offline(TM_DIR, "TSLA")
        cls.data = {"TSLA": bt.load_sessions(text, "TSLA", bt.tm.parse_now("2026-10-20 16:05"))}
        cls.doc = bt.backtest(cls.data, min_is_trades=10)

    def test_the_default_rule_after_costs(self):
        b = self.doc["baseline"]
        self.assertEqual((b["is"]["trades"], b["oos"]["trades"]), (20, 13))
        self.assertLess(b["is"]["avg_R"], 0)
        self.assertLess(b["oos"]["avg_R"], 0)

    def test_no_edge_and_the_reason(self):
        self.assertFalse(self.doc["edge"])
        self.assertIn("out-of-sample trades", self.doc["edge_reason"])
        self.assertEqual(self.doc["variants_tested"], 216)          # no SPY: no market filter

    def test_the_report_leads_with_the_verdict(self):
        text = "\n".join(bt.report(self.doc))
        self.assertIn("EDGE: no", text)
        self.assertIn("out-of-sample", text)
        self.assertIn("not a promise", text)

    def test_cli_offline_writes_the_file(self):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "trader", "backtest.json")
            buf = io.StringIO()
            with redirect_stdout(buf), redirect_stderr(io.StringIO()):
                code = bt.main(["run", "--offline", TM_DIR, "--symbols", "TSLA", "--no-market",
                                "--now", "2026-10-20 16:05", "--min-is-trades", "10", "--write", out,
                                "--config", os.path.join(d, "none.json")])
            self.assertEqual(code, 1)                   # 1 = ran, no edge
            self.assertTrue(os.path.exists(out))
            self.assertIn("EDGE: no", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
