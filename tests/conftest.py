"""Test bootstrap — runs before any test module import.

Phase 0 stubs never call the LLM, but config.py reads LLM_API_KEY at import;
tests stay hermetic with a dummy value (unit tests never hit the network).
"""

import os

os.environ.setdefault("LLM_API_KEY", "test-key")
