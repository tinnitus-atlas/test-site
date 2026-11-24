# Test fixtures

`tinnitus.records.json` is a frozen copy of the records (24 Nov 2026). Tests that apply made-up proposals to a copy of
the records use it, so a review that changes the live records (for example by filling in a trial's enrolment) cannot
break those tests. Tests that check the live data itself still read `records/`.
