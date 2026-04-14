from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))
from behavioral_memory import assess_yesterday
assess_yesterday()
