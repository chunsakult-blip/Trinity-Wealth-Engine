"""POST /api/agents/dispatch, GET /api/agents/stream/{job_id}, POST /api/agents/jobs/{job_id}/resume

SSE à¹„à¸¡à¹ˆà¸œà¸¹à¸à¸à¸±à¸š live run à¹‚à¸”à¸¢à¸•à¸£à¸‡ â€” tail à¸ˆà¸²à¸ job_logs table à¹€à¸ªà¸¡à¸­ (Rev.3/5 à¸‚à¹‰à¸­ 5)
à¸›à¸´à¸”/à¹€à¸›à¸´à¸” tab à¹ƒà¸«à¸¡à¹ˆ à¸«à¸£à¸·à¸­à¸£à¸µà¹€à¸Ÿà¸£à¸Šà¸à¸¥à¸²à¸‡à¸„à¸±à¸™ à¸¢à¸±à¸‡à¹€à¸«à¹‡à¸™ log à¸—à¸µà¹ˆà¸žà¸¥à¸²à¸”à¹„à¸›à¹„à¸”à¹‰à¸„à¸£à¸š à¹€à¸žà¸£à¸²à¸° log à¸–à¸¹à¸à¹€à¸‚à¸µà¸¢à¸™à¸¥à¸‡ DB
à¸à¹ˆà¸­à¸™à¹à¸¥à¹‰à¸§à¸„à¹ˆà¸­à¸¢ stream à¸­à¸­à¸à¹„à¸› à¹„à¸¡à¹ˆà¹ƒà¸Šà¹ˆ push à¸ªà¸”à¸ˆà¸²à¸ generator à¸—à¸µà¹ˆà¸«à¸²à¸¢à¹„à¸›à¸žà¸£à¹‰à¸­à¸¡ connection
"""
import asyncio
import hashlib
import json
from contextlib import closing
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api import state_db
from api.auth import require_session
from api.schemas import ActiveAgentStatusDTO, JobOutputsDTO, JobStatusDTO, SpecialistOutputDTO, UnverifiedDraftSelection

router = APIRouter(dependencies=[Depends(require_session)])

_POLL_INTERVAL_SECONDS = 1.0
_TERMINAL_STATUSES = ("done", "done_with_warnings", "done_with_errors", "error", "awaiting_approval")
_SUMMARY_NODES = ("manager_summary", "supervisor", "synthesize_notebooklm")


def _job_outputs_to_dto(conn, job) -> JobOutputsDTO:
    reply_logs = state_db.get_job_reply_logs(conn, job["job_id"])
    summary_row = next((row for row in reversed(reply_logs) if row["node_name"] == "manager_summary"), None)
    if summary_row is None:
        summary_row = next((row for row in reversed(reply_logs) if row["node_name"] == "supervisor"), None)
    if summary_row is None:
        summary_row = next((row for row in reversed(reply_logs) if row["node_name"] in ("synthesize", "synthesize_notebooklm")), None)

    latest_by_node = {}
    for row in reply_logs:
        node_name = row["node_name"] or ""
        if node_name in _SUMMARY_NODES or node_name.startswith(("post_", "prepare_")):
            continue
        latest_by_node[node_name] = row

    specialists = [
        SpecialistOutputDTO(
            node_name=row["node_name"] or "Specialist",
            label=row["label"] or row["node_name"] or "Specialist",
            content=row["content"] or "",
            seq=row["seq"],
            created_at=row["created_at"],
        )
        for row in sorted(latest_by_node.values(), key=lambda row: row["seq"])
    ]

    return JobOutputsDTO(
        job_id=job["job_id"],
        status=job["status"],
        executive_summary=summary_row["content"] if summary_row else None,
        executive_summary_created_at=summary_row["created_at"] if summary_row else None,
        specialists=specialists,
        last_seq=reply_logs[-1]["seq"] if reply_logs else 0,
        error_message=job["error_message"],
    )


class DispatchRequest(BaseModel):
    instruction: str
    card_id: Optional[str] = None
    flow: str = "manager"
    scope: str = "both"


class ResumeRequest(BaseModel):
    approved_news_links: list[str] = []
    approved_youtube_links: list[str] = []
    approved_event_ids: Optional[list[str]] = None
    approved_pitch_ids: Optional[list[str]] = None
    unverified_draft_selections: Optional[list[UnverifiedDraftSelection]] = None
    pitch_presentation_styles: dict[str, str] = {}
    action: Literal["approve", "refresh_sources"] = "approve"


def _job_to_dto(conn, job) -> JobStatusDTO:
    current_node = state_db.get_latest_job_log_node(conn, job["job_id"]) if job["status"] == "running" else None
    interrupt_payload = json.loads(job["interrupt_payload"]) if job["interrupt_payload"] else None
    return JobStatusDTO(
        job_id=job["job_id"],
        status=job["status"],
        card_id=job["card_id"],
        error_message=job["error_message"],
        current_node=current_node,
        interrupt_payload=interrupt_payload,
        log_count=state_db.get_job_log_count(conn, job["job_id"]),
        created_at=job["created_at"],
        updated_at=job["updated_at"],
    )


@router.post("/api/agents/dispatch", response_model=JobStatusDTO)
def dispatch_job(payload: DispatchRequest, request: Request) -> JobStatusDTO:
    if not payload.instruction.strip():
        raise HTTPException(status_code=400, detail="instruction ว่างเปล่า")

    job_queue = request.app.state.job_queue
    job_id = job_queue.dispatch(payload.instruction, payload.card_id, flow=payload.flow, scope=payload.scope)

    with closing(state_db.get_connection()) as conn:
        # à¸¢à¹‰à¸²à¸¢à¸à¸²à¸£à¹Œà¸”à¹€à¸›à¹‡à¸™ executing + à¸œà¸¹à¸ job_id à¹ƒà¸™à¸„à¸³à¸‚à¸­à¹€à¸”à¸µà¸¢à¸§à¸à¸±à¸š dispatch â€” à¸à¸±à¸™à¹€à¸„à¸ªà¸—à¸µà¹ˆ frontend
        # à¸¢à¸´à¸‡ PUT /api/kanban/move à¸•à¸²à¸¡à¸«à¸¥à¸±à¸‡à¹à¸¥à¹‰à¸§à¸¥à¹‰à¸¡à¹€à¸«à¸¥à¸§ à¸—à¸³à¹ƒà¸«à¹‰à¸à¸²à¸£à¹Œà¸”à¸„à¹‰à¸²à¸‡ backlog à¸—à¸±à¹‰à¸‡à¸—à¸µà¹ˆ job à¸£à¸±à¸™à¸­à¸¢à¸¹à¹ˆà¸ˆà¸£à¸´à¸‡
        if payload.card_id is not None:
            existing_card = state_db.get_kanban_card(conn, payload.card_id)
            if existing_card is not None:
                state_db.move_kanban_card(conn, payload.card_id, "executing", job_id=job_id)
        job = state_db.get_job(conn, job_id)
        return _job_to_dto(conn, job)


@router.get("/api/agents/jobs/{job_id}", response_model=JobStatusDTO)
def get_job_status(job_id: str) -> JobStatusDTO:
    with closing(state_db.get_connection()) as conn:
        job = state_db.get_job(conn, job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="ไม่พบ job นี้")
        return _job_to_dto(conn, job)


@router.get("/api/agents/jobs/{job_id}/outputs", response_model=JobOutputsDTO)
def get_job_outputs(job_id: str) -> JobOutputsDTO:
    with closing(state_db.get_connection()) as conn:
        job = state_db.get_job(conn, job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="ไม่พบ job นี้")
        return _job_outputs_to_dto(conn, job)


@router.get("/api/agents/active", response_model=ActiveAgentStatusDTO)
def get_active_agent_status() -> ActiveAgentStatusDTO:
    # single-worker queue (api/jobs.py) â€” à¸ˆà¸°à¸¡à¸µ job à¸ªà¸–à¸²à¸™à¸° running à¸žà¸£à¹‰à¸­à¸¡à¸à¸±à¸™à¹„à¸”à¹‰à¹à¸„à¹ˆ 0 à¸«à¸£à¸·à¸­ 1 à¸£à¸²à¸¢à¸à¸²à¸£à¹€à¸ªà¸¡à¸­
    with closing(state_db.get_connection()) as conn:
        running_jobs = state_db.list_jobs_by_status(conn, ["running"])
        if not running_jobs:
            return ActiveAgentStatusDTO(running=False)
        job = running_jobs[0]
        return ActiveAgentStatusDTO(
            running=True,
            flow=job["flow"],
            node=state_db.get_latest_job_log_node(conn, job["job_id"]),
            job_id=job["job_id"],
        )


@router.post("/api/agents/jobs/{job_id}/resume", response_model=JobStatusDTO)
def resume_job(job_id: str, payload: ResumeRequest, request: Request) -> JobStatusDTO:
    """Validate and atomically claim one human approval resume."""

    token_uses: list[dict[str, str | int]] = []
    with closing(state_db.get_connection()) as conn:
        job = state_db.get_job(conn, job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="job not found")
        if job["status"] != "awaiting_approval":
            raise HTTPException(status_code=409, detail="job is no longer awaiting approval")

        interrupt_payload = json.loads(job["interrupt_payload"]) if job["interrupt_payload"] else {}
        pitches = interrupt_payload.get("pitches") if isinstance(interrupt_payload, dict) else None
        approval_revision = interrupt_payload.get("approval_revision") if isinstance(interrupt_payload, dict) else None
        pitch_by_id = {
            str(pitch.get("pitch_id")): pitch
            for pitch in (pitches or [])
            if isinstance(pitch, dict) and pitch.get("pitch_id")
        }

        approved_ids = payload.approved_pitch_ids or []
        if len(approved_ids) != len(set(approved_ids)):
            raise HTTPException(status_code=400, detail="duplicate publishable pitch IDs")

        for p_id in approved_ids:
            pitch = pitch_by_id.get(p_id)
            if not pitch:
                raise HTTPException(status_code=400, detail=f"approved pitch {p_id} not found")
            if pitch.get("source_readiness") != "ready":
                raise HTTPException(status_code=400, detail=f"pitch {p_id} is not source-ready")

        draft_selections = payload.unverified_draft_selections or []
        draft_ids = [selection.pitch_id for selection in draft_selections]
        if len(draft_ids) != len(set(draft_ids)):
            raise HTTPException(status_code=400, detail="duplicate Unverified Draft pitch IDs")
        if set(approved_ids).intersection(draft_ids):
            raise HTTPException(status_code=400, detail="a pitch cannot be both publishable and an Unverified Draft")

        if payload.action == "refresh_sources":
            if draft_selections or approved_ids:
                raise HTTPException(status_code=400, detail="refresh_sources cannot include pitch selections")
            refresh_attempts = int(interrupt_payload.get("source_refresh_attempts", 0) or 0)
            if refresh_attempts >= 1:
                raise HTTPException(status_code=409, detail="refresh_sources already attempted")

        if draft_selections:
            from tools.content.provenance_enrichment import verify_eligibility_token

            if not isinstance(approval_revision, int) or approval_revision <= 0:
                raise HTTPException(status_code=409, detail="approval checkpoint has no current Draft revision metadata")
            for selection in draft_selections:
                pitch = pitch_by_id.get(selection.pitch_id)
                if not pitch or not pitch.get("unverified_draft_eligible"):
                    raise HTTPException(status_code=400, detail=f"pitch {selection.pitch_id} is not Draft-eligible")
                expected_token = str(pitch.get("unverified_draft_eligibility_token") or "")
                if not expected_token or selection.ack.eligibility_token != expected_token:
                    raise HTTPException(status_code=409, detail=f"stale or mismatched token for pitch {selection.pitch_id}")
                claims = verify_eligibility_token(
                    selection.ack.eligibility_token,
                    expected_job_id=job_id,
                    expected_thread_id=str(job["thread_id"]),
                    expected_pitch_id=selection.pitch_id,
                    expected_revision=approval_revision,
                    expected_issue_codes=list(pitch.get("unverified_draft_issue_codes") or []),
                )
                if claims is None:
                    raise HTTPException(status_code=400, detail=f"invalid, expired, or mismatched token for pitch {selection.pitch_id}")
                token_uses.append({
                    "token_hash": hashlib.sha256(selection.ack.eligibility_token.encode("utf-8")).hexdigest(),
                    "jti": claims.jti,
                    "thread_id": claims.thread_id,
                    "pitch_id": claims.pitch_id,
                    "approval_revision": claims.approval_revision,
                })

        resume_value: dict[str, Any] = {
            "approved_news_links": payload.approved_news_links or [],
            "approved_youtube_links": payload.approved_youtube_links or [],
            "approved_event_ids": payload.approved_event_ids or [],
            "approved_pitch_ids": payload.approved_pitch_ids or [],
            "unverified_draft_selections": [selection.model_dump() for selection in draft_selections] or [],
            "pitch_presentation_styles": payload.pitch_presentation_styles or {},
            "action": payload.action,
        }
        try:
            state_db.claim_job_resume(
                conn,
                job_id=job_id,
                resume_value_json=json.dumps(resume_value, ensure_ascii=False),
                token_uses=token_uses,
            )
        except ValueError as exc:
            detail = str(exc)
            status_code = 409 if detail in {"approval_already_claimed", "eligibility_token_already_used"} else 400
            raise HTTPException(status_code=status_code, detail=detail) from exc
        claimed_job = state_db.get_job(conn, job_id)
        response = _job_to_dto(conn, claimed_job)

    request.app.state.job_queue.enqueue(job_id)
    return response


@router.get("/api/agents/stream/{job_id}")
async def stream_job(job_id: str) -> StreamingResponse:
    def _read_next_batch(after_seq: int):
        with closing(state_db.get_connection()) as conn:
            job = state_db.get_job(conn, job_id)
            if job is None:
                return None, []
            logs = state_db.get_job_logs_since(conn, job_id, after_seq)
            return job, logs

    def _read_final_dto():
        with closing(state_db.get_connection()) as conn:
            job = state_db.get_job(conn, job_id)
            return _job_to_dto(conn, job)

    async def event_generator():
        after_seq = 0
        while True:
            job, logs = await asyncio.to_thread(_read_next_batch, after_seq)
            if job is None:
                yield f"event: error\ndata: {json.dumps({'detail': 'job not found'})}\n\n"
                return

            for row in logs:
                after_seq = row["seq"]
                payload = {
                    "node": row["node_name"],
                    "content": row["content"],
                    "role": row["role"],
                    "label": row["label"],
                }
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

            if job["status"] in _TERMINAL_STATUSES:
                dto = await asyncio.to_thread(_read_final_dto)
                yield f"event: {job['status']}\ndata: {dto.model_dump_json()}\n\n"
                return

            await asyncio.sleep(_POLL_INTERVAL_SECONDS)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
