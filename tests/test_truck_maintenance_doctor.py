"""Tests for truck_maintenance_doctor."""

import json
import os
import sys
import tempfile
import unittest
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))

import truck_maintenance_doctor as tmd

AS_OF = date(2026, 11, 15)


def options(**overrides):
    """Audit options, with clean defaults."""
    base = {
        "due_days": 14,
        "due_miles": 500,
        "as_of": AS_OF,
    }
    base.update(overrides)
    return base


def row(**overrides):
    """One service row, with clean defaults."""
    base = {"unit_id": "UNIT-2001",
            "unit_number": "Truck 201",
            "service_type": "oil change",
            "due_date": "2026-12-20",
            "due_miles": "160000",
            "last_service_date": "2026-09-01",
            "last_service_miles": "140000",
            "odometer": "145000",
            "status": "scheduled"}
    base.update(overrides)
    return base


def codes(findings, rule=None):
    """Finding rules, optionally filtered to one rule."""
    return [f.rule for f in findings
            if rule is None or f.rule == rule]


def severities(findings, rule):
    """Severities of findings for one rule."""
    return [f.severity for f in findings if f.rule == rule]


def run(rows, **overrides):
    """Audit rows and return (findings, report, summary)."""
    findings, report = tmd.audit(rows, options(**overrides))
    return findings, report, tmd.summarize(findings, report)


class TestParseHelpers(unittest.TestCase):
    def test_parse_int(self):
        self.assertEqual(tmd.parse_int("145000", "miles"), 145000)
        self.assertEqual(tmd.parse_int("145,000", "miles"), 145000)
        self.assertIsNone(tmd.parse_int("", "miles"))
        self.assertIsNone(tmd.parse_int(None, "miles"))
        with self.assertRaises(ValueError):
            tmd.parse_int("many", "miles")
        with self.assertRaises(ValueError):
            tmd.parse_int("12.5", "miles")

    def test_parse_date(self):
        self.assertEqual(tmd.parse_date("2026-09-15", "x"),
                         date(2026, 9, 15))
        self.assertIsNone(tmd.parse_date("", "x"))
        self.assertIsNone(tmd.parse_date(None, "x"))
        with self.assertRaises(ValueError):
            tmd.parse_date("15/09/2026", "x")

    def test_normalise_header(self):
        self.assertEqual(tmd.normalise_header("Due Date"),
                         "duedate")
        self.assertEqual(tmd.normalise_header("Odometer"),
                         "odometer")


class TestCleanRow(unittest.TestCase):
    def test_clean_row_has_no_findings(self):
        findings, report, summary = run([row()])
        self.assertEqual(findings, [])
        self.assertEqual(summary["services"], 1)
        self.assertEqual(summary["errors"], 0)
        self.assertEqual(summary["warnings"], 0)

    def test_due_date_only_is_clean(self):
        findings, _, _ = run([row(due_miles="",
                                  last_service_miles="")])
        self.assertEqual(findings, [])

    def test_due_miles_only_is_clean(self):
        findings, _, _ = run([row(due_date="",
                                  last_service_date="")])
        self.assertEqual(findings, [])

    def test_completed_overdue_service_is_clean(self):
        findings, _, _ = run([row(due_date="2026-11-01",
                                  due_miles="140000",
                                  last_service_date="2026-11-01",
                                  last_service_miles="140000",
                                  odometer="146000",
                                  status="completed")])
        self.assertEqual(findings, [])

    def test_due_today_is_not_overdue(self):
        findings, _, _ = run([row(due_date="2026-11-15")])
        self.assertEqual(codes(findings), ["service-due-soon"])

    def test_due_exactly_at_window_edge_is_warning(self):
        findings, _, _ = run([row(due_date="2026-11-29")])
        self.assertEqual(codes(findings), ["service-due-soon"])

    def test_due_just_outside_window_is_clean(self):
        findings, _, _ = run([row(due_date="2026-11-30",
                                  due_miles="")])
        self.assertEqual(findings, [])

    def test_miles_exactly_at_window_edge_is_warning(self):
        findings, _, _ = run([row(due_date="",
                                  due_miles="145500")])
        self.assertEqual(codes(findings),
                         ["due-by-miles-soon"])

    def test_miles_just_outside_window_is_clean(self):
        findings, _, _ = run([row(due_date="",
                                  due_miles="145501")])
        self.assertEqual(findings, [])


class TestOverdueRules(unittest.TestCase):
    def test_overdue_service_is_error(self):
        findings, _, summary = run([row(due_date="2026-11-10")])
        self.assertEqual(codes(findings), ["overdue-service"])
        self.assertEqual(severities(findings, "overdue-service"),
                         ["error"])
        self.assertEqual(summary["overdue"], 1)

    def test_service_due_soon_is_warning(self):
        findings, _, _ = run([row(due_date="2026-11-20",
                                  due_miles="")])
        self.assertEqual(codes(findings), ["service-due-soon"])
        self.assertEqual(severities(findings,
                                    "service-due-soon"),
                         ["warning"])

    def test_overdue_by_miles_is_error(self):
        findings, _, summary = run([row(due_date="",
                                        due_miles="140000")])
        self.assertEqual(codes(findings), ["overdue-by-miles"])
        self.assertEqual(severities(findings,
                                    "overdue-by-miles"),
                         ["error"])
        self.assertEqual(summary["overdue_by_miles"], 1)

    def test_due_by_miles_soon_is_warning(self):
        findings, _, _ = run([row(due_date="",
                                  due_miles="145200")])
        self.assertEqual(codes(findings),
                         ["due-by-miles-soon"])
        self.assertEqual(severities(findings,
                                    "due-by-miles-soon"),
                         ["warning"])

    def test_due_days_override(self):
        findings, _, _ = run([row(due_date="2026-11-20",
                                  due_miles="")], due_days=3)
        self.assertEqual(findings, [])

    def test_due_miles_override(self):
        findings, _, _ = run([row(due_date="",
                                  due_miles="145200")],
                             due_miles=100)
        self.assertEqual(findings, [])


class TestRecordRules(unittest.TestCase):
    def test_missing_last_service_is_error(self):
        findings, _, _ = run([row(last_service_date="",
                                  last_service_miles="")])
        self.assertEqual(codes(findings),
                         ["missing-last-service"])
        self.assertEqual(severities(findings,
                                    "missing-last-service"),
                         ["error"])

    def test_missing_due_is_error(self):
        findings, _, _ = run([row(due_date="", due_miles="")])
        self.assertEqual(codes(findings), ["missing-due"])

    def test_duplicate_service_is_error(self):
        findings, _, _ = run([row(),
                              row(due_date="2027-01-10")])
        self.assertEqual(codes(findings, "duplicate-service"),
                         ["duplicate-service"])

    def test_same_service_different_unit_is_clean(self):
        findings, _, _ = run([row(),
                              row(unit_id="UNIT-2002",
                                  unit_number="Truck 202")])
        self.assertEqual(findings, [])

    def test_different_service_same_unit_is_clean(self):
        findings, _, _ = run([row(),
                              row(service_type="brake inspection",
                                  due_date="2026-12-10")])
        self.assertEqual(findings, [])

    def test_odometer_regression_is_error(self):
        findings, _, _ = run([row(odometer="139000")])
        self.assertEqual(codes(findings),
                         ["odometer-regression"])
        self.assertEqual(severities(findings,
                                    "odometer-regression"),
                         ["error"])

    def test_odometer_equal_to_last_miles_is_clean(self):
        findings, _, _ = run([row(odometer="140000")])
        self.assertEqual(findings, [])


class TestValueRules(unittest.TestCase):
    def test_missing_unit_id_is_error(self):
        findings, _, _ = run([row(unit_id="")])
        self.assertIn("missing-unit-id", codes(findings))

    def test_missing_service_type_is_error(self):
        findings, _, _ = run([row(service_type="")])
        self.assertIn("missing-service-type", codes(findings))

    def test_unknown_service_type_is_warning(self):
        findings, _, _ = run([row(service_type="mystery job")])
        self.assertEqual(codes(findings),
                         ["unknown-service-type"])
        self.assertEqual(severities(findings,
                                    "unknown-service-type"),
                         ["warning"])

    def test_known_service_types_are_clean(self):
        for service in tmd.KNOWN_SERVICES:
            findings, _, _ = run([row(service_type=service)])
            self.assertEqual(findings, [], service)

    def test_invalid_date_is_error(self):
        findings, _, _ = run([row(due_date="soon")])
        self.assertEqual(codes(findings), ["invalid-date"])

    def test_invalid_last_date_is_error(self):
        findings, _, _ = run([row(last_service_date="yesterday")])
        self.assertEqual(codes(findings), ["invalid-date"])

    def test_future_date_is_error(self):
        findings, _, _ = run(
            [row(last_service_date="2026-12-01")])
        self.assertIn("future-date", codes(findings))

    def test_last_service_after_due_is_warning(self):
        findings, _, _ = run(
            [row(due_date="2026-11-10",
                 last_service_date="2026-11-12")])
        self.assertIn("overdue-service", codes(findings))
        self.assertIn("last-service-after-due", codes(findings))
        self.assertEqual(severities(findings,
                                    "last-service-after-due"),
                         ["warning"])

    def test_invalid_miles_is_error(self):
        findings, _, _ = run([row(due_miles="many")])
        self.assertEqual(codes(findings), ["invalid-miles"])

    def test_negative_miles_is_error(self):
        findings, _, _ = run([row(odometer="-5",
                                  last_service_miles="")])
        self.assertEqual(codes(findings), ["invalid-miles"])

    def test_invalid_status_is_error(self):
        findings, _, _ = run([row(status="waiting")])
        self.assertEqual(codes(findings), ["invalid-status"])


class TestReport(unittest.TestCase):
    def test_totals(self):
        _, report, summary = run([
            row(),
            row(unit_id="UNIT-2002", unit_number="Truck 202",
                due_date="2026-11-10"),
            row(unit_id="UNIT-2002", unit_number="Truck 202",
                service_type="brake inspection",
                due_date="2026-11-20", due_miles=""),
        ])
        self.assertEqual(summary["services"], 3)
        self.assertEqual(summary["units"], 2)
        self.assertEqual(summary["overdue"], 1)
        self.assertEqual(summary["due_soon"], 1)
        self.assertEqual(len(report["per_unit"]), 2)

    def test_per_unit_counts(self):
        _, report, _ = run([
            row(due_date="2026-11-10"),
            row(service_type="brake inspection",
                due_date="2026-11-20", due_miles=""),
        ])
        first = report["per_unit"][0]
        self.assertEqual(first["unit_id"], "UNIT-2001")
        self.assertEqual(first["services"], 2)
        self.assertEqual(first["overdue"], 1)
        self.assertEqual(first["due_soon"], 1)
        self.assertEqual(first["errors"], 1)
        self.assertEqual(first["warnings"], 1)

    def test_missing_unit_rows_share_entry(self):
        _, report, _ = run([row(unit_id=""), row(unit_id="")])
        self.assertEqual(len(report["per_unit"]), 1)
        self.assertEqual(report["per_unit"][0]["services"], 2)


class TestOutput(unittest.TestCase):
    def test_format_text_sample_counts(self):
        base = os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)))
        path = os.path.join(base, "examples", "maintenance.csv")
        rows = tmd.read_csv(path)
        findings, report = tmd.audit(rows, options())
        summary = tmd.summarize(findings, report)
        self.assertEqual(summary["services"], 16)
        self.assertEqual(summary["units"], 9)
        self.assertEqual(summary["findings"], 18)
        self.assertEqual(summary["errors"], 13)
        self.assertEqual(summary["warnings"], 5)
        self.assertEqual(summary["overdue"], 3)
        self.assertEqual(summary["due_soon"], 2)
        self.assertEqual(summary["overdue_by_miles"], 2)
        text = tmd.format_text(findings, report, summary)
        self.assertIn("Services: 16, units: 9, findings: 18, "
                      "errors: 13, warnings: 5", text)
        self.assertIn("Services overdue: 3", text)

    def test_format_json_shape(self):
        findings, report, summary = run(
            [row(due_date="2026-11-10")])
        payload = json.loads(tmd.format_json(findings, report,
                                             summary))
        self.assertEqual(payload["summary"]["errors"], 1)
        self.assertEqual(len(payload["findings"]), 1)
        self.assertEqual(payload["findings"][0]["rule"],
                         "overdue-service")
        self.assertEqual(payload["per_unit"][0]["unit_id"],
                         "UNIT-2001")

    def test_clean_sample_is_clean(self):
        base = os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)))
        path = os.path.join(base, "examples", "clean.csv")
        rows = tmd.read_csv(path)
        findings, report = tmd.audit(rows, options())
        summary = tmd.summarize(findings, report)
        self.assertEqual(summary["services"], 5)
        self.assertEqual(summary["findings"], 0)
        self.assertIn("All services clean.",
                      tmd.format_text(findings, report, summary))

    def test_warnings_sample_counts(self):
        base = os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)))
        path = os.path.join(base, "examples", "warnings.csv")
        rows = tmd.read_csv(path)
        findings, report = tmd.audit(rows, options())
        summary = tmd.summarize(findings, report)
        self.assertEqual(summary["services"], 3)
        self.assertEqual(summary["findings"], 5)
        self.assertEqual(summary["errors"], 0)
        self.assertEqual(summary["warnings"], 5)


class TestReadCsv(unittest.TestCase):
    def test_header_aliases_and_bom(self):
        with tempfile.NamedTemporaryFile(
                "w", suffix=".csv", delete=False,
                encoding="utf-8") as handle:
            handle.write("\ufeffUnit,Unit Number,Service,Due Date,"
                         "Due Miles,"
                         "Last Service Date,Last Service Miles,"
                         "Odometer,Status\n")
            handle.write("UNIT-9,Truck 9,oil change,2026-12-20,"
                         "160000,2026-09-01,140000,145000,"
                         "scheduled\n")
            path = handle.name
        try:
            rows = tmd.read_csv(path)
        finally:
            os.unlink(path)
        self.assertEqual(rows[0]["unit_id"], "UNIT-9")
        self.assertEqual(rows[0]["odometer"], "145000")
        findings, _, _ = run(rows)
        self.assertEqual(findings, [])

    def test_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            tmd.read_csv("/nonexistent/maintenance.csv")


class TestMain(unittest.TestCase):
    def test_main_check_exit_codes(self):
        base = os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)))
        sample = os.path.join(base, "examples", "maintenance.csv")
        clean = os.path.join(base, "examples", "clean.csv")
        warnings_file = os.path.join(base, "examples",
                                     "warnings.csv")
        self.assertEqual(tmd.main([sample, "--as-of",
                                   "2026-11-15", "--check"]), 1)
        self.assertEqual(tmd.main([clean, "--as-of",
                                   "2026-11-15", "--check"]), 0)
        self.assertEqual(tmd.main([warnings_file, "--as-of",
                                   "2026-11-15", "--check"]), 0)
        self.assertEqual(tmd.main([warnings_file, "--as-of",
                                   "2026-11-15", "--check",
                                   "--strict"]), 1)

    def test_main_missing_file_exits_2(self):
        self.assertEqual(tmd.main(["/nonexistent/x.csv"]), 2)

    def test_main_bad_as_of_exits_2(self):
        base = os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)))
        clean = os.path.join(base, "examples", "clean.csv")
        self.assertEqual(tmd.main([clean, "--as-of",
                                   "15-11-2026"]), 2)

    def test_main_missing_unit_id_column_exits_2(self):
        with tempfile.NamedTemporaryFile(
                "w", suffix=".csv", delete=False) as handle:
            handle.write("service,due_date\n"
                         "oil change,2026-12-01\n")
            path = handle.name
        try:
            self.assertEqual(tmd.main([path]), 2)
        finally:
            os.unlink(path)

    def test_main_json_and_out(self):
        base = os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)))
        clean = os.path.join(base, "examples", "clean.csv")
        with tempfile.NamedTemporaryFile(
                "w", suffix=".txt", delete=False) as handle:
            out_path = handle.name
        try:
            code = tmd.main([clean, "--as-of", "2026-11-15",
                             "--json", "--out", out_path])
            self.assertEqual(code, 0)
            with open(out_path, encoding="utf-8") as handle:
                payload = json.load(handle)
            self.assertEqual(payload["summary"]["findings"], 0)
        finally:
            os.unlink(out_path)


if __name__ == "__main__":
    unittest.main()
