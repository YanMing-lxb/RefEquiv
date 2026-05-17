import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
sys.path.append(str(BASE_DIR))

from src.version import __version__

PROJECT_NAME = "RefEquiv"
ROOT_DIR = BASE_DIR
SRC_DIR = ROOT_DIR / "src"
ENTRY_POINT = SRC_DIR / "__main__.py"
DATA_DIR = SRC_DIR / "assets"
ICON_FILE = DATA_DIR / "logo.ico"
