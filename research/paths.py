import os
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.environ.get('LEGAL_DATA_DIR', ROOT)).resolve()
DB = DATA / 'database' / 'research.db'

def now():
    return datetime.now(ZoneInfo('Asia/Seoul'))

def timestamp():
    return now().isoformat(timespec='seconds')
