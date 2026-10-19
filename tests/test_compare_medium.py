"""Four cases use their own probabilities and identical fresh monthly sample sizes."""

from contextlib import redirect_stdout
from io import StringIO
import math
import unittest
from unittest.mock import patch

from analysis.compare_medium import CASES, run_comparison


class CompareMediumTest(unittest.TestCase):
    def test_each_confirmed_case_gets_the_same_month_count_and_actual_parameters(self):
        def validation(**kwargs):
            return {"timing_seconds": {"play": 1}, "summary": {
                "monthly_gross": {"mean": 10},
                "monthly_net_after_example_electricity": {"mean": 9},
                "negative_gross_months": 0, "negative_net_months": 0},
                "runtime_seconds": 1}

        with patch("analysis.compare_medium.run_validation", side_effect=validation) as validate, \
             redirect_stdout(StringIO()):
            report = run_comparison(months=2)
        self.assertEqual(validate.call_count, 4)
        self.assertEqual(report["days_per_case"], 60)
        for call, (picks, payout) in zip(validate.call_args_list, CASES):
            self.assertEqual(call.kwargs["months"], 2)
            self.assertEqual(call.kwargs["days_per_month"], 30)
            self.assertEqual(call.kwargs["picks"], picks)
            self.assertEqual(call.kwargs["payout_cents"], payout)
            expected = math.comb(19, picks) / math.comb(25, picks)
            self.assertEqual(report["cases"][str(picks)]["mathematics"]["win_probability"], expected)
        for count in (True, 0, 1.5):
            with self.subTest(count=count), self.assertRaises(ValueError):
                run_comparison(count)


if __name__ == "__main__":
    unittest.main()
