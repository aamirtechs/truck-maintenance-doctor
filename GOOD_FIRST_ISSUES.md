# Good first issues

Seeded issues for new contributors. File each one on GitHub with the
`good first issue` and `help wanted` labels.

## 1. Flag units with no DOT annual inspection scheduled

Title: Warn when a unit has no DOT annual inspection row

Description: The tool audits the rows it is given, but it
never notices a unit that has no DOT annual inspection row
at all, and 49 CFR 396.17 requires one every 12 months. Add
a warning for every unit in the file that has no dot annual
inspection entry, listing the unit id, so a fleet can spot
the truck that fell out of the annual inspection cycle
entirely.

Difficulty: Easy

Acceptance criteria: the sample file warns on the 7
identified units with no DOT annual inspection row (the row
with no unit id is skipped, not warned on); the clean file
warns on the 4 units without one; a file where every unit
has one stays clean; a test covers all three cases; README documents
the rule.

## 2. Add a PM compliance rate to the summary

Title: Show a PM compliance percentage in the report

Description: The report prints counts of overdue and due
soon services, but a fleet manager wants one number for how
healthy the program is. Add a compliance line to the text
report: the share of services that are neither overdue nor
due soon, as a percentage, so the fleet can see at a glance
whether the PM program is on track.

Difficulty: Easy

Acceptance criteria: the sample file shows 62.5% compliant
(10 of 16 services with no overdue or due-soon finding); the
clean file shows 100%; a test checks both values; README
documents the line.

## 3. Support a service history reference file

Title: Cross-check last service dates against a history file

Description: A last service date typed into the schedule can
be wrong without any other row to contradict it. Add an
optional --history-file flag that takes a CSV of completed
service records (unit_id, service_type, service_date,
service_miles). Flag any audited row whose last service date
or miles disagree with the newest matching history record,
with both values in the message, so a fleet can catch a
typo before it becomes a missed service.

Difficulty: Medium

Acceptance criteria: a history file flags the sample row
whose last service date differs from its history record; a
row that agrees with history stays clean; a missing history
file exits 2 with a clear error; a test covers both cases;
README documents the flag.

## 4. Add a shop work list to the output

Title: Print a plain-text work list of overdue services

Description: The report flags overdue services one by one,
but a shop foreman needs a single list to work through. Add
an optional --worklist flag that prints a compact list of
the overdue services (unit, service type, days overdue,
miles overdue), sorted by days overdue descending, so the
shop can start with the most overdue truck first.

Difficulty: Medium

Acceptance criteria: the sample file lists the 3 date-overdue
services, starting with the DOT annual inspection at 45 days
overdue; a file with no overdue services prints an empty
list note; a test checks the ordering with two overdue rows;
README documents the flag.
