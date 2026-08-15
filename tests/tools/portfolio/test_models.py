import pytest
from datetime import datetime, date
from pydantic import ValidationError
from tools.portfolio.models import _coerce_iso_string, AllocationTarget

def test_coerce_iso_string():
    # Test datetime (has hour)
    dt = datetime(2026, 6, 21, 10, 30, 45)
    assert _coerce_iso_string(dt) == "2026-06-21T10:30:45"

    # Test date (no hour)
    d = date(2026, 6, 21)
    assert _coerce_iso_string(d) == "2026-06-21"

    # Test string (no isoformat)
    s = "2026-06-21T10:30:45"
    assert _coerce_iso_string(s) == s


class TestAllocationTargetBounds:
    """Phase F: target_percent ต้องอยู่ในช่วง 0-100 ต่อรายการ"""

    def test_valid_range_ok(self):
        t = AllocationTarget(bucket_id="core", name="Core", target_percent=60.0)
        assert t.target_percent == 60.0
        AllocationTarget(bucket_id="edge0", name="Zero", target_percent=0.0)
        AllocationTarget(bucket_id="edge100", name="Hundred", target_percent=100.0)

    def test_over_100_rejected(self):
        with pytest.raises(ValidationError):
            AllocationTarget(bucket_id="core", name="Core", target_percent=150.0)

    def test_negative_rejected(self):
        with pytest.raises(ValidationError):
            AllocationTarget(bucket_id="core", name="Core", target_percent=-50.0)
