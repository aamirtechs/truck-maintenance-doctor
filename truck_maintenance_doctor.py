"""Fleet maintenance schedule audit CLI.

Reads a fleet maintenance schedule CSV (unit, service type,
due date or miles, last service date or miles, odometer) and
audits every scheduled service for the mistakes that put a
truck out of service or on the wrong side of a roadside
inspection: preventive maintenance past its due date, services
due soon, services overdue by miles, missing last-service
records, duplicate service entries, invalid or future dates,
odometer regression, and malformed rows.

49 CFR 396.3 requires every motor carrier to have a
systematic inspection, repair, and maintenance program, and
for a small fleet that program is usually a spreadsheet.
A spreadsheet falls behind quietly: a due date slips a week,
then a month, and the first person to notice is the inspector
at the scale house. This tool is the offline audit: it reads
the exported CSV, flags every problem with a rule name and a
severity, prints a per-unit summary and totals, and never
touches your records.

Each problem is a finding with a code, a rule name, a severity
(error or warning), and a message. Errors are the ones that
mean a service is missed or the data is wrong; warnings are
patterns worth investigating. --check exits 1 when any error
is found, and --strict also fails on warnings.

Zero dependencies, Python 3.10 or newer, standard library only.

Usage:
    python3 truck_maintenance_doctor.py examples/maintenance.csv
    python3 truck_maintenance_doctor.py maintenance.csv --json --check
"""

import argparse
import csv
import json
import sys
from datetime import date, datetime

__version__ = "1.0.0"

DEFAULT_DUE_DAYS = 14
DEFAULT_DUE_MILES = 500

VALID_STATUSES = ("scheduled", "completed", "overdue",
                  "cancelled")
KNOWN_SERVICES = (
    "oil change",
    "brake inspection",
    "tire rotation",
    "dot annual inspection",
    "coolant flush",
    "transmission service",
    "air filter",
    "def system service",
    "lights inspection",
    "battery check",
    "alignment",
)

# Header names, normalised by lowercasing and stripping every
# character that is not a letter or digit, mapped to the field
# this tool uses. A fleet spreadsheet may call the columns
# "Unit", "Service", "Due Date" and "Odometer"; a hand-built
# CSV may use the snake_case names instead. Both work.
HEADER_ALIASES = {
    "unitid": "unit_id",
    "unit": "unit_id",
    "id": "unit_id",
    "unitnumber": "unit_number",
    "truck": "unit_number",
    "vehicle": "unit_number",
    "servicetype": "service_type",
    "service": "service_type",
    "pmtype": "service_type",
    "duedate": "due_date",
    "nextdue": "due_date",
    "dued": "due_date",
    "duemiles": "due_miles",
    "dueodometer": "due_miles",
    "nextserviceat": "due_miles",
    "lastservicedate": "last_service_date",
    "lastservice": "last_service_date",
    "lastdone": "last_service_date",
    "lastservicemiles": "last_service_miles",
    "lastmiles": "last_service_miles",
    "milesatlastservice": "last_service_miles",
    "odometer": "odometer",
    "miles": "odometer",
    "currentmiles": "odometer",
    "status": "status",
    "servicestatus": "status",
}


class Finding:
    """One audit finding for one service entry or pattern."""

    def __init__(self, code, rule, severity, message):
        self.code = code
        self.rule = rule
        self.severity = severity
        self.message = message

    def as_dict(self):
        """Return the finding as a plain dict."""
        return {"code": self.code, "rule": self.rule,
                "severity": self.severity, "message": self.message}

    def __str__(self):
        return "%s [%s] %s: %s" % (self.severity.upper(), self.rule,
                                   self.code, self.message)


def normalise_header(name):
    """Lowercase a header and strip every non-alphanumeric char."""
    return "".join(ch for ch in str(name).strip().lower()
                   if ch.isalnum())


def parse_int(value, field):
    """Parse an integer, or return None when blank.

    Raises ValueError on anything else.
    """
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        raise ValueError("%s is not a whole number: %r"
                         % (field, value))


def parse_date(value, field):
    """Parse a YYYY-MM-DD date, or return None when blank.

    Raises ValueError on anything else.
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError("%s is not a YYYY-MM-DD date: %r"
                         % (field, value))


def audit_row(row, seen_services, options):
    """Audit one service row and return its findings."""
    findings = []
    unit = row.get("unit_id", "").strip()
    service = row.get("service_type", "").strip()
    label = unit or "(no unit)"
    if service:
        label = "%s %s" % (label, service)

    def add(rule, severity, message):
        findings.append(Finding(label, rule, severity, message))

    if not unit:
        add("missing-unit-id", "error",
            "row has no unit id, so the truck cannot be "
            "identified")
    if not service:
        add("missing-service-type", "error",
            "row has no service type, so nobody can tell what "
            "is due")
    elif service.lower() not in KNOWN_SERVICES:
        add("unknown-service-type", "warning",
            "service type %r is not a recognised service, so "
            "check the spelling" % service)

    if unit and service:
        key = (unit.lower(), service.lower())
        if key in seen_services:
            add("duplicate-service", "error",
                "unit %s already has a %s entry, so the "
                "schedule conflicts with itself"
                % (unit, service))
        else:
            seen_services.add(key)

    status = row.get("status", "").strip().lower()
    if status and status not in VALID_STATUSES:
        add("invalid-status", "error",
            "status %r is not one of %s"
            % (row.get("status", "").strip(),
               ", ".join(VALID_STATUSES)))
    done = status == "completed"

    as_of = options["as_of"]

    due_date = None
    try:
        due_date = parse_date(row.get("due_date"), "due date")
    except ValueError as exc:
        add("invalid-date", "error", str(exc))
    last_date = None
    try:
        last_date = parse_date(row.get("last_service_date"),
                               "last service date")
    except ValueError as exc:
        add("invalid-date", "error", str(exc))
    if last_date is not None and last_date > as_of:
        add("future-date", "error",
            "last service date %s is in the future"
            % last_date.isoformat())
    if last_date is not None and due_date is not None \
            and last_date > due_date:
        add("last-service-after-due", "warning",
            "last service %s is after the next due date %s, so "
            "the schedule looks stale"
            % (last_date.isoformat(), due_date.isoformat()))

    due_miles = None
    try:
        due_miles = parse_int(row.get("due_miles"), "due miles")
    except ValueError as exc:
        add("invalid-miles", "error", str(exc))
    last_miles = None
    try:
        last_miles = parse_int(row.get("last_service_miles"),
                               "last service miles")
    except ValueError as exc:
        add("invalid-miles", "error", str(exc))
    odometer = None
    try:
        odometer = parse_int(row.get("odometer"), "odometer")
    except ValueError as exc:
        add("invalid-miles", "error", str(exc))
    for value, field in ((due_miles, "due miles"),
                         (last_miles, "last service miles"),
                         (odometer, "odometer")):
        if value is not None and value < 0:
            add("invalid-miles", "error",
                "%s %d is below zero" % (field, value))

    if due_date is None and due_miles is None:
        add("missing-due", "error",
            "service has no due date and no due miles, so "
            "nothing will ever trigger it")
    if last_date is None and last_miles is None:
        add("missing-last-service", "error",
            "service has no last service date and no last "
            "service miles, so there is no record it was ever "
            "done")
    if odometer is not None and last_miles is not None \
            and odometer < last_miles:
        add("odometer-regression", "error",
            "odometer %d is below the last service miles %d, "
            "so one of the two readings is wrong"
            % (odometer, last_miles))

    if not done:
        if due_date is not None:
            days_overdue = (as_of - due_date).days
            if days_overdue > 0:
                add("overdue-service", "error",
                    "service was due %s, %d days ago"
                    % (due_date.isoformat(), days_overdue))
            elif -days_overdue <= options["due_days"]:
                add("service-due-soon", "warning",
                    "service is due %s, in %d days"
                    % (due_date.isoformat(), -days_overdue))
        if due_miles is not None and odometer is not None:
            miles_overdue = odometer - due_miles
            if miles_overdue > 0:
                add("overdue-by-miles", "error",
                    "service was due at %d miles and the "
                    "odometer reads %d, %d miles overdue"
                    % (due_miles, odometer, miles_overdue))
            elif -miles_overdue <= options["due_miles"]:
                add("due-by-miles-soon", "warning",
                    "service is due at %d miles, %d miles away"
                    % (due_miles, -miles_overdue))

    return findings, due_date, due_miles, odometer


def audit(rows, options):
    """Audit all service rows and return (findings, report)."""
    findings = []
    seen_services = set()
    units = {}
    overdue = 0
    due_soon = 0
    overdue_by_miles = 0
    for row in rows:
        row_findings, _, _, _ = audit_row(
            row, seen_services, options)
        findings.extend(row_findings)
        code = row.get("unit_id", "").strip() or "(no unit)"
        entry = units.get(code)
        if entry is None:
            entry = {
                "unit_id": code,
                "unit_number": row.get("unit_number", "").strip(),
                "services": 0,
                "overdue": 0,
                "due_soon": 0,
                "errors": 0,
                "warnings": 0,
            }
            units[code] = entry
        entry["services"] += 1
        for finding in row_findings:
            if finding.severity == "error":
                entry["errors"] += 1
            else:
                entry["warnings"] += 1
            if finding.rule in ("overdue-service",
                                "overdue-by-miles"):
                entry["overdue"] += 1
            if finding.rule in ("service-due-soon",
                                "due-by-miles-soon"):
                entry["due_soon"] += 1
        if any(f.rule == "overdue-service"
               for f in row_findings):
            overdue += 1
        if any(f.rule in ("service-due-soon",
                          "due-by-miles-soon")
               for f in row_findings):
            due_soon += 1
        if any(f.rule == "overdue-by-miles"
               for f in row_findings):
            overdue_by_miles += 1
    report = {
        "services": len(rows),
        "units": len(units),
        "per_unit": [units[key] for key in units],
        "overdue": overdue,
        "due_soon": due_soon,
        "overdue_by_miles": overdue_by_miles,
    }
    return findings, report


def summarize(findings, report):
    """Build the summary dict from findings and the report."""
    errors = sum(1 for f in findings if f.severity == "error")
    warnings = sum(1 for f in findings if f.severity == "warning")
    summary = {
        "services": report["services"],
        "units": report["units"],
        "findings": len(findings),
        "errors": errors,
        "warnings": warnings,
        "overdue": report["overdue"],
        "due_soon": report["due_soon"],
        "overdue_by_miles": report["overdue_by_miles"],
    }
    return summary


def format_text(findings, report, summary):
    """Render the audit as human-readable text."""
    lines = []
    for finding in findings:
        lines.append(str(finding))
    lines.append("")
    lines.append("Units:")
    for entry in report["per_unit"]:
        if entry["errors"] == 0 and entry["warnings"] == 0:
            state = "clean"
        else:
            parts = []
            if entry["errors"]:
                parts.append("%d error%s"
                             % (entry["errors"],
                                "s" if entry["errors"] != 1 else ""))
            if entry["warnings"]:
                parts.append("%d warning%s"
                             % (entry["warnings"],
                                "s" if entry["warnings"] != 1
                                else ""))
            state = ", ".join(parts)
        lines.append("  %-12s %-12s %d services, %d overdue, "
                     "%d due soon: %s"
                     % (entry["unit_id"], entry["unit_number"],
                        entry["services"], entry["overdue"],
                        entry["due_soon"], state))
    lines.append("")
    lines.append("Services overdue: %d" % summary["overdue"])
    lines.append("Services due soon: %d" % summary["due_soon"])
    lines.append("Services overdue by miles: %d"
                 % summary["overdue_by_miles"])
    lines.append("")
    lines.append("Services: %d, units: %d, findings: %d, "
                 "errors: %d, warnings: %d"
                 % (summary["services"], summary["units"],
                    summary["findings"], summary["errors"],
                    summary["warnings"]))
    if summary["errors"] == 0 and summary["warnings"] == 0:
        lines.append("All services clean.")
    return "\n".join(lines) + "\n"


def format_json(findings, report, summary):
    """Render the audit as JSON."""
    payload = {
        "summary": summary,
        "per_unit": report["per_unit"],
        "findings": [f.as_dict() for f in findings],
    }
    return json.dumps(payload, indent=2) + "\n"


def read_csv(path, aliases=None):
    """Read a CSV file, normalising headers via the alias map."""
    aliases = aliases or HEADER_ALIASES
    with open(path, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            return []
        mapped = {}
        for name in reader.fieldnames:
            if name is None:
                continue
            mapped[name] = aliases.get(normalise_header(name),
                                       normalise_header(name))
        rows = []
        for raw in reader:
            row = {}
            for name, value in raw.items():
                if name is None:
                    continue
                row[mapped[name]] = "" if value is None else value
            rows.append(row)
        return rows


def parse_args(argv):
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Audit a fleet maintenance schedule CSV "
                    "for overdue and missing services.")
    parser.add_argument("file",
                        help="CSV file of services to audit")
    parser.add_argument("--due-days", type=int,
                        default=DEFAULT_DUE_DAYS,
                        help="flag services due within this many "
                             "days (default: 14)")
    parser.add_argument("--due-miles", type=int,
                        default=DEFAULT_DUE_MILES,
                        help="flag services due within this many "
                             "miles (default: 500)")
    parser.add_argument("--as-of", default=None,
                        help="reference date YYYY-MM-DD for due "
                             "and future checks (default: today)")
    parser.add_argument("--json", action="store_true",
                        help="emit JSON instead of text")
    parser.add_argument("--check", action="store_true",
                        help="exit 1 if any error is found")
    parser.add_argument("--strict", action="store_true",
                        help="with --check, also exit 1 on "
                             "warnings")
    parser.add_argument("--out", default=None,
                        help="write the report to a file")
    return parser.parse_args(argv)


def main(argv=None):
    """Run the audit and return the process exit code."""
    args = parse_args(argv)
    try:
        as_of = date.today()
        if args.as_of:
            as_of = datetime.strptime(args.as_of,
                                      "%Y-%m-%d").date()
    except ValueError:
        print("error: --as-of must be a YYYY-MM-DD date",
              file=sys.stderr)
        return 2
    try:
        rows = read_csv(args.file)
    except FileNotFoundError:
        print("error: file not found: %s" % args.file,
              file=sys.stderr)
        return 2
    except OSError as exc:
        print("error: cannot read %s: %s" % (args.file, exc),
              file=sys.stderr)
        return 2
    if not rows:
        print("error: no data rows in %s" % args.file,
              file=sys.stderr)
        return 2
    if "unit_id" not in rows[0]:
        print("error: no unit id column found in %s"
              % args.file, file=sys.stderr)
        return 2
    options = {
        "due_days": args.due_days,
        "due_miles": args.due_miles,
        "as_of": as_of,
    }
    findings, report = audit(rows, options)
    summary = summarize(findings, report)
    if args.json:
        output = format_json(findings, report, summary)
    else:
        output = format_text(findings, report, summary)
    if args.out:
        try:
            with open(args.out, "w", encoding="utf-8") as handle:
                handle.write(output)
        except OSError as exc:
            print("error: cannot write %s: %s" % (args.out, exc),
                  file=sys.stderr)
            return 2
    else:
        sys.stdout.write(output)
    if args.check:
        if summary["errors"] > 0:
            return 1
        if args.strict and summary["warnings"] > 0:
            return 1
    return 0


def main_entry():
    """Console script entry point."""
    sys.exit(main())


if __name__ == "__main__":
    main_entry()
