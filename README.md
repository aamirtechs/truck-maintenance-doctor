# truck-maintenance-doctor

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/aamirtechs/truck-maintenance-doctor/blob/main/LICENSE) [![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](https://github.com/aamirtechs/truck-maintenance-doctor/issues)

A zero-dependency Python CLI that audits a fleet maintenance
schedule CSV for the mistakes that put a truck out of service
or on the wrong side of a roadside inspection: preventive
maintenance past its due date, services due soon, services
overdue by miles, missing last-service records, duplicate
service entries, invalid or future dates, odometer regression,
and malformed rows.

49 CFR 396.3 requires every motor carrier to have a
systematic inspection, repair, and maintenance program, and
for a small fleet that program is usually a spreadsheet. A
spreadsheet falls behind quietly: a due date slips a week,
then a month, and the first person to notice is the inspector
at the scale house. The usual fixes are one row at a time in
the spreadsheet. This tool is the offline audit: it reads the
exported CSV, flags every problem with a rule name and a
severity, prints a per-unit summary and totals, and never
touches your records.

## Install

Requires Python 3.10 or newer. No dependencies beyond the standard
library.

```bash
pip install truck-maintenance-doctor
```

Or run it straight from the source checkout:

```bash
python3 truck_maintenance_doctor.py examples/maintenance.csv
```

## Input format

A CSV export with a header row. Columns used:
`unit_id`, `unit_number`, `service_type`, `due_date`,
`due_miles`, `last_service_date`, `last_service_miles`,
`odometer`, `status`. Spreadsheet aliases work too
(`Unit`, `Service`, `Due Date`, `Odometer`, `Last Service
Date`), and snake_case headers. Extra columns are ignored,
so a full export works as-is. A UTF-8 BOM header is handled.
Mileages are whole numbers and accept thousands separators.

```csv
unit_id,unit_number,service_type,due_date,due_miles,last_service_date,last_service_miles,odometer,status
UNIT-001,Truck 101,oil change,2026-12-01,150000,2026-08-01,140000,145000,scheduled
UNIT-001,Truck 101,brake inspection,2026-11-10,148000,2026-05-10,130000,145000,scheduled
UNIT-002,Truck 102,dot annual inspection,2026-10-01,,2025-10-01,120000,145500,scheduled
```

## What it checks

Errors, the ones that mean a service is missed or the data
is wrong:

* `overdue-service`: a service whose due date is past, with
  the number of days overdue in the message.
* `overdue-by-miles`: the odometer has passed the due miles,
  with the number of miles overdue in the message.
* `missing-last-service`: no last service date and no last
  service miles, so there is no record the service was ever
  done.
* `missing-due`: no due date and no due miles, so nothing
  will ever trigger the service.
* `duplicate-service`: the same unit has two entries for the
  same service type, so the schedule conflicts with itself.
* `odometer-regression`: the odometer reads below the last
  service miles, so one of the two readings is wrong.
* `missing-unit-id`, `missing-service-type`: rows that cannot
  be identified or acted on.
* `invalid-date`, `future-date`: an unparseable due or last
  service date, or a last service date in the future.
* `invalid-miles`: an unparseable or negative mileage.
* `invalid-status`: a status that is not scheduled, completed,
  overdue, or cancelled.

Warnings, patterns worth investigating:

* `service-due-soon`: a service due within `--due-days` days
  (default 14).
* `due-by-miles-soon`: a service due within `--due-miles`
  miles (default 500).
* `unknown-service-type`: a service type that is not one of
  the recognised services, so check the spelling.
* `last-service-after-due`: the last service date is after
  the next due date, so the schedule looks stale.

The report also prints a per-unit summary (unit, services,
overdue count, due-soon count, and error and warning counts)
and totals: services overdue, services due soon, and services
overdue by miles.

## Usage

```bash
python3 truck_maintenance_doctor.py examples/maintenance.csv --as-of 2026-11-15
```

Captured output:

```
ERROR [overdue-service] UNIT-001 brake inspection: service was due 2026-11-10, 5 days ago
WARNING [service-due-soon] UNIT-002 oil change: service is due 2026-11-20, in 5 days
WARNING [due-by-miles-soon] UNIT-002 oil change: service is due at 146000 miles, 500 miles away
ERROR [overdue-service] UNIT-002 dot annual inspection: service was due 2026-10-01, 45 days ago
ERROR [missing-last-service] UNIT-003 tire rotation: service has no last service date and no last service miles, so there is no record it was ever done
ERROR [overdue-by-miles] UNIT-003 tire rotation: service was due at 140000 miles and the odometer reads 142000, 2000 miles overdue
ERROR [odometer-regression] UNIT-004 oil change: odometer 148000 is below the last service miles 152000, so one of the two readings is wrong
WARNING [service-due-soon] UNIT-004 oil change: service is due 2026-11-25, in 10 days
ERROR [invalid-date] UNIT-005 air filter: due date is not a YYYY-MM-DD date: 'soon'
ERROR [invalid-miles] UNIT-005 def system service: due miles is not a whole number: 'many'
ERROR [duplicate-service] UNIT-001 brake inspection: unit UNIT-001 already has a brake inspection entry, so the schedule conflicts with itself
WARNING [unknown-service-type] UNIT-007 mystery service: service type 'mystery service' is not a recognised service, so check the spelling
ERROR [missing-due] UNIT-007 oil change: service has no due date and no due miles, so nothing will ever trigger it
ERROR [future-date] UNIT-008 lights inspection: last service date 2026-12-01 is in the future
WARNING [last-service-after-due] UNIT-008 lights inspection: last service 2026-12-01 is after the next due date 2026-11-30, so the schedule looks stale
ERROR [missing-unit-id] (no unit) oil change: row has no unit id, so the truck cannot be identified
ERROR [overdue-service] UNIT-009 oil change: service was due 2026-11-01, 14 days ago
ERROR [overdue-by-miles] UNIT-009 oil change: service was due at 140000 miles and the odometer reads 141000, 1000 miles overdue

Units:
  UNIT-001     Truck 101    3 services, 1 overdue, 0 due soon: 2 errors
  UNIT-002     Truck 102    2 services, 1 overdue, 2 due soon: 1 error, 2 warnings
  UNIT-003     Truck 103    2 services, 1 overdue, 0 due soon: 2 errors
  UNIT-004     Truck 104    2 services, 0 overdue, 1 due soon: 1 error, 1 warning
  UNIT-005     Truck 105    2 services, 0 overdue, 0 due soon: 2 errors
  UNIT-007     Truck 107    2 services, 0 overdue, 0 due soon: 1 error, 1 warning
  UNIT-008     Truck 108    1 services, 0 overdue, 0 due soon: 1 error, 1 warning
  (no unit)    Truck 109    1 services, 0 overdue, 0 due soon: 1 error
  UNIT-009     Truck 110    1 services, 2 overdue, 0 due soon: 2 errors

Services overdue: 3
Services due soon: 2
Services overdue by miles: 2

Services: 16, units: 9, findings: 18, errors: 13, warnings: 5
```

The sample has 16 services across 9 units and 18 findings.
The story it tells: a DOT annual inspection is 45 days
overdue, a tire rotation has no last-service record and is
2,000 miles overdue, one odometer reads below its last
service miles, and one unit has two conflicting brake
inspection entries.

Use it as a CI gate: `--check` exits 1 when any error is found,
and 0 otherwise. On the sample above it exits 1:

```bash
python3 truck_maintenance_doctor.py examples/maintenance.csv --as-of 2026-11-15 --check
```

On `examples/clean.csv`, five clean services, it exits 0:

```

Units:
  UNIT-201     Truck 201    1 services, 0 overdue, 0 due soon: clean
  UNIT-202     Truck 202    1 services, 0 overdue, 0 due soon: clean
  UNIT-203     Truck 203    1 services, 0 overdue, 0 due soon: clean
  UNIT-204     Truck 204    1 services, 0 overdue, 0 due soon: clean
  UNIT-205     Truck 205    1 services, 0 overdue, 0 due soon: clean

Services overdue: 0
Services due soon: 0
Services overdue by miles: 0

Services: 5, units: 5, findings: 0, errors: 0, warnings: 0
All services clean.
```

With `--strict`, `--check` also fails on warnings: a file with
warnings only (a service due in 5 days and 500 miles away, an
unknown service type, and a service 200 miles from its due
mileage) exits 0 under `--check` and 1 under `--check
--strict`. `--json` emits the summary, the per-unit list, and
findings as JSON, and `--out` writes the report to a file.

Tune the windows to your PM program: `--due-days 30` on the
sample raises the findings from 18 to 25, because seven more
services fall inside the wider window, and `--due-miles 2000`
raises them from 18 to 19.

## Options

| Flag | Meaning |
| --- | --- |
| `--due-days` | Flag services due within this many days (default: 14) |
| `--due-miles` | Flag services due within this many miles (default: 500) |
| `--as-of` | Reference date YYYY-MM-DD for due and future checks (default: today) |
| `--json` | Emit JSON instead of text |
| `--check` | Exit 1 if any error is found |
| `--strict` | With --check, also exit 1 on warnings |
| `--out` | Write the report to a file |

## Edge cases

* A service due exactly `--due-days` days out is flagged,
  and one due exactly `--due-miles` miles out is flagged.
  A service due today is due soon, not overdue.
* A service with only a due date, or only due miles, is
  audited on the trigger it has. A service with neither is
  an error, because nothing will ever trigger it.
* A service with only a last service date, or only last
  service miles, has a record. A service with neither is an
  error.
* A completed service is not flagged as overdue or due soon,
  even when its due date has passed, because the work is
  done. Its dates and mileages are still validated.
* A last service date after the next due date always comes
  with either a future-date error or an overdue-service
  error, because the last date is either in the future or
  the due date is already past.
* The per-unit overdue count counts findings, so a service
  overdue by both date and miles adds 2 to its unit's count,
  as UNIT-009 shows in the sample. The totals count rows:
  services overdue counts rows with an overdue-service
  finding, and services overdue by miles counts rows with an
  overdue-by-miles finding.
* A row with no unit id is reported as `(no unit)` and still
  gets its other findings.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

50 tests, all passing: every rule, error and warning severities,
header aliases and BOM handling, due window boundaries and
overrides, per-unit summary and totals, summary counts, JSON
output shape, `--check` and `--strict` exit codes, and the
three sample files with their exact finding counts.

## License

MIT. See [LICENSE](LICENSE).
