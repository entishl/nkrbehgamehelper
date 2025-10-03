import sys
import os
from pathlib import Path


def resource_path(relative_path: str) -> str:
    try:
        base_path = Path(sys._MEIPASS)  # type: ignore
    except AttributeError:
        base_path = Path(__file__).resolve().parent.parent

    final_path = base_path / relative_path

    # 可选：如果希望在返回前就确认文件存在，可以取消下面的注释。
    # 但这会改变原始函数的行为，需要评估对项目的影响。
    # if not final_path.exists():
    #     raise FileNotFoundError(f"Resource not found at: {final_path}")

    return str(final_path)
