"""
API route handlers for trip planning, follow-ups, sessions and health.
"""
from fastapi import APIRouter, HTTPException, status

from app.agent.graph import get_travel_agent
from app.agent.llm import LLMNotConfiguredError
from app.agent.prompt_builder import build_planning_prompt
from app.config import get_settings
from app.logging_config import get_logger
from app.models.schemas import (
    ChatMessage,
    FollowUpRequest,
    FollowUpResponse,
    HealthResponse,
    SessionHistoryResponse,
    TripPlanRequest,
    TripPlanResponse,
)
from app.services.session_service import SessionNotFoundError, get_session_service

logger = get_logger(__name__)
router = APIRouter()

APP_VERSION = "1.0.0"


@router.get("/health", response_model=HealthResponse, tags=["system"])
def health_check() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        app_name=settings.app_name,
        version=APP_VERSION,
        llm_provider=settings.llm_provider,
        llm_configured=settings.has_llm_credentials,
        mock_apis=settings.use_mock_apis,
    )


@router.post("/trip/plan", response_model=TripPlanResponse, tags=["trip"])
def plan_trip(request: TripPlanRequest) -> TripPlanResponse:
    session_service = get_session_service()
    agent = get_travel_agent()

    session_id = request.session_id or session_service.create_session(request.destination)
    if request.session_id:
        session_service.register_existing(session_id, request.destination)

    prompt = build_planning_prompt(request)

    try:
        result = agent.plan_trip(session_id=session_id, planning_prompt=prompt)
    except LLMNotConfiguredError as exc:
        logger.error("trip_plan.llm_not_configured", extra={"error": str(exc)})
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("trip_plan.failed", extra={"session_id": session_id})
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to generate itinerary. Please try again.",
        ) from exc

    session_service.touch(session_id)

    return TripPlanResponse(
        session_id=session_id,
        destination=request.destination,
        duration_days=request.duration_days,
        itinerary=result["answer"],
        tools_used=result["tools_used"],
    )


@router.post("/trip/followup", response_model=FollowUpResponse, tags=["trip"])
def followup(request: FollowUpRequest) -> FollowUpResponse:
    session_service = get_session_service()
    agent = get_travel_agent()

    if not session_service.exists(request.session_id) and not agent.session_exists(request.session_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{request.session_id}' not found or has expired. "
            "Start a new trip plan first via /trip/plan.",
        )

    try:
        result = agent.ask_followup(session_id=request.session_id, question=request.question)
    except LLMNotConfiguredError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("followup.failed", extra={"session_id": request.session_id})
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to answer follow-up question. Please try again.",
        ) from exc

    session_service.touch(request.session_id)

    return FollowUpResponse(
        session_id=request.session_id,
        answer=result["answer"],
        tools_used=result["tools_used"],
    )


@router.get("/trip/session/{session_id}", response_model=SessionHistoryResponse, tags=["trip"])
def get_session_history(session_id: str) -> SessionHistoryResponse:
    agent = get_travel_agent()
    history = agent.get_history(session_id)
    if not history:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found or empty.")
    return SessionHistoryResponse(
        session_id=session_id,
        messages=[ChatMessage(**m) for m in history],
    )


@router.delete("/trip/session/{session_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["trip"])
def delete_session(session_id: str) -> None:
    session_service = get_session_service()
    try:
        session_service.get(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    session_service.delete(session_id)
