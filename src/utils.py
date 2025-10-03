import sys
import os

def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller or Nuitka"""

    if os.path.exists(os.path.join(os.path.dirname(os.path.dirname(__file__)),relative_path)):
        return os.path.join(os.path.dirname(os.path.dirname(__file__)),relative_path)

    try:
        if os.path.exists(os.path.join(sys._MEIPASS, relative_path)):
            return os.path.join(sys._MEIPASS, relative_path)
    except:
        ...

    if os.path.exists(os.path.join(os.path.abspath("."), relative_path)):
        return os.path.join(os.path.abspath("."), relative_path)
