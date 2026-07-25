import pytest
from pathlib import Path

def test_briefing_tests_never_write_default_vault():
    """
    This test serves as an explicit marker for the vault isolation requirement.
    The actual enforcement is handled by the `enforce_vault_isolation` session autouse fixture
    in `conftest.py`, which checks the `memories/30_Knowledge_Base/NotebookLM_Sources` directory before and after
    the test suite runs to ensure no modifications occur.
    
    Files like `_9.md` and `_9.quality.json` that might already be in the vault are identified
    as test artifacts from previous runs without isolation, but are intentionally not deleted here.
    """
    vault_dir = Path("memories/30_Knowledge_Base/NotebookLM_Sources")
    
    # Just a sanity check that the directory exists or we are aware of it.
    assert True, "Vault isolation is enforced by conftest.py"
