"""Market Data Schemas

Defines contracts for macroeconomic observations and financial market data,
ensuring central source of truth for downstream analytics and validators.
"""
from typing import Dict, Literal, Optional
from pydantic import BaseModel, Field


class MacroObservation(BaseModel):
    series_id: str = Field(description="Ticker or FRED Series ID e.g. BZ=F, CPIAUCSL")
    category: Literal[
        "inflation",
        "rates",
        "energy",
        "equity",
        "sector",
        "commodity",
        "fx",
        "yield",
        "other",
    ] = Field(description="หมวดหมู่ของดัชนีสำหรับใช้อ้างอิงใน Validator อย่างรัดกุม")
    label: str = Field(description="ชื่อภาษาไทย/อังกฤษของดัชนี")
    value: float = Field(description="ค่าตัวเลขล่าสุด")
    unit: str = Field(description="หน่วยของดัชนี e.g. USD/bbl, %, Points")
    observed_at: str = Field(description="วันที่และเวลาของค่าล่าสุด (ISO format)")
    provider: str = Field(description="ผู้ให้บริการข้อมูล e.g. Yahoo Finance, FRED")
    source_url: str | None = Field(default=None, description="URL อ้างอิง")
    previous_value: Optional[float] = Field(default=None, description="ค่าก่อนหน้า")
    change_pct: Optional[float] = Field(default=None, description="% เปลี่ยนแปลงล่าสุด")
    returns: Dict[str, Optional[float]] = Field(default_factory=dict, description="ผลตอบแทน 1D, 5D, 30D, 90D (%)")
    is_stale: bool = Field(default=False, description="ข้อมูลเก่าเกิน 5 วันทำการหรือไม่")
    confidence: Literal["high", "medium", "low"] = Field(default="high")
    frequency: Optional[str] = Field(default=None, description="Provider reporting frequency")
    provider_updated_at: Optional[str] = Field(
        default=None,
        description="Provider publication/update time, distinct from the economic observation period",
    )
    freshness_reason: str = Field(default="", description="Auditable freshness decision")
