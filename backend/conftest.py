"""Pytest configuration — add the backend directory to sys.path so tests can
import backend modules without package installation."""

import sys
from pathlib import Path

# Add the backend directory to sys.path
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))
