"""Sum the MOONSHOT run ledger: loop-running time used vs the 24 h video budget.

    py ledger.py            -> prints each segment, total used, remaining
An open segment (empty end) counts up to now.
"""
import csv
from datetime import datetime, timedelta
from pathlib import Path

LEDGER = Path(__file__).resolve().parent.parent.parent.parent / "exports" / "moonshot" / "run_ledger.csv"
BUDGET = timedelta(hours=24)
FMT = "%Y-%m-%d %H:%M"


def main() -> None:
    used = timedelta()
    with LEDGER.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            start = datetime.strptime(row["start_local_edt"], FMT)
            end = datetime.strptime(row["end_local_edt"], FMT) if row["end_local_edt"] else datetime.now()
            used += end - start
            print(f"seg {row['segment']}: {row['start_local_edt']} -> {row['end_local_edt'] or 'now'} = {end - start}")
    left = BUDGET - used
    print(f"USED {used}  |  LEFT {left}  (budget 24:00:00, loop-running time only)")


if __name__ == "__main__":
    main()
