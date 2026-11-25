import os
import sys
from pathlib import Path

os.environ.pop("SE_REPLAY", None)  # tests never run against the demo sandbox

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
