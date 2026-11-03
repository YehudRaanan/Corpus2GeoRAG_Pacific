"""Installed pure-Python RapidFuzz fallback for the verified Python 3.12 runtime."""
import os
import sys

sys.path.append(r'D:\Projects\GeoAI\Agent\.venv\Lib\site-packages')
os.environ.setdefault('RAPIDFUZZ_IMPLEMENTATION','python')
