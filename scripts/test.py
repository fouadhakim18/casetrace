"""Preload the native index library before pytest installs output capture on Windows."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import faiss
import pytest
if __name__=='__main__':raise SystemExit(pytest.main(['-q',*sys.argv[1:]]))
