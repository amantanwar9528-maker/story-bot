"""
Story Bot package initializer.
Adds the src directory to sys.path so all modules can use
direct imports like `from config import ...`.
"""
import os
import sys

_src_dir = os.path.dirname(os.path.abspath(__file__))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)
