"""GET /api/debug/models — audit ว่าแต่ละ LLM slot (agent + tool layer) resolve ไปที่ model ไหน"""
from fastapi import APIRouter, Depends

from api.auth import require_session
from core.model_registry import get_registry_summary

router = APIRouter(
    prefix="/api/debug",
    tags=["Debug"],
    dependencies=[Depends(require_session)],
)


@router.get("/models")
def get_model_registry() -> list[dict]:
    """Return resolved model registry for all LLM slots."""
    return get_registry_summary()
