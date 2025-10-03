import sys
import os

def resource_path(relative_path) -> str | None:
    """Get absolute path to resource, works for dev and for PyInstaller/Nuitka."""
    
    candidates = [
        os.path.join(os.path.dirname(os.path.dirname(__file__)), relative_path),
        os.path.join(getattr(sys, '_MEIPASS', ''), relative_path),
        os.path.join(os.path.abspath('.'), relative_path),
    ]

    for path in candidates:
        if path and os.path.exists(path):
            return path
    
    return None
