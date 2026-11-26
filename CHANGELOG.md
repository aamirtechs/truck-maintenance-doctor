# Changelog

## 1.0.0 - 2026-11-16

Initial release.

* Maintenance audit over a fleet maintenance schedule CSV:
  overdue PM services by date and by miles, services due
  soon, missing last-service records, duplicate service
  entries, invalid and future dates, odometer regression,
  and malformed rows.
* Per-unit summary (unit, services, overdue count, due-soon
  count, and error and warning counts) and totals: services
  overdue, services due soon, and services overdue by miles.
* Findings carry a code, rule name, severity (error or warning),
  and message; errors and warnings are counted in the summary.
* Text and --json output, --out file output, overridable
  windows (--due-days, --due-miles, --as-of), and a --check
  CI gate that exits 1 on errors (and on warnings with
  --strict).
* Zero dependencies, Python 3.10 or newer.
