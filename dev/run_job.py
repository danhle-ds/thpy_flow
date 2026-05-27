# dev/run_job.py
# Usage:
#   python -B dev/run_job.py weekly 2026-05-22
#   python -B dev/run_job.py monthly 2026-04-30
#   python -B dev/run_job.py weekly          <- dùng date.today()

import sys
from dotenv import load_dotenv
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

_e = Path(r"D:\PYTHON_TOOLS\env")
for f in ["path.env", "account.env", "telegram_token.env"]:
    load_dotenv(_e / f, override=True)

from datetime import date

job  = sys.argv[1] if len(sys.argv) > 1 else ""
d    = date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else date.today()

if job == "weekly":
    from job.weekly_report import run
    run(today=d)
elif job == "monthly":
    from job.monthly_report import run
    run(today=d)
else:
    print("Usage: python dev/run_job.py [weekly|monthly] [YYYY-MM-DD]")
    sys.exit(1)