"""把项目根目录加入 sys.path，保证 `import crop_questions` 在测试中可用。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
