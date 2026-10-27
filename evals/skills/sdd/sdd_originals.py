"""検分済みの共通openat/NOFOLLOW読取りをSDD原証拠にも適用する。"""
from pathlib import Path
import sys

ROUTING = Path(__file__).resolve().parents[1] / "routing"
if str(ROUTING) not in sys.path:
    sys.path.insert(0, str(ROUTING))
from production_ledger import read_regular


def read_original(path):
    # resolveでリンクを辿らず、各親と末尾をdescriptorで開いて検査する。
    return read_regular(Path(path).absolute())
