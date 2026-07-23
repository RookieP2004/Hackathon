from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aegis_api_common import Page, PaginationParams, apply_filters, apply_sorting, get_logger, paginate, parse_sort
from aegis_db.models import Prediction, RiskScore
from app.auth import auth
from app.db import get_db
from app.modules.risk_engine import service
from app.modules.risk_engine.schemas import (
    PredictionCreate,
    PredictionFilter,
    PredictionOutcomeRequest,
    PredictionRead,
    RiskScoreCreate,
    RiskScoreFilter,
    RiskScoreRead,
)

router = APIRouter(prefix="/risk-engine", tags=["risk-engine"])
logger = get_logger("predictive-risk-engine.risk-engine")

_READ_ROLES = ("system_admin", "plant_admin", "safety_officer", "maintenance_engineer", "operator", "emergency_team")
_WRITE_ROLES = ("system_admin", "plant_admin")

_RISK_SORTABLE_FIELDS = {"id", "score", "confidence", "computed_at"}
_PREDICTION_SORTABLE_FIELDS = {"id", "predicted_value", "confidence", "predicted_at"}


@router.get("/risk-scores", response_model=Page[RiskScoreRead], summary="List computed risk scores")
async def list_risk_scores(
    pagination: PaginationParams = Depends(),
    sort_fields: list[tuple[str, bool]] = Depends(parse_sort),
    filters: RiskScoreFilter = Depends(),
    db: AsyncSession = Depends(get_db),
    _principal=Depends(auth.require_roles(*_READ_ROLES)),
) -> Page[RiskScoreRead]:
    query = apply_filters(select(RiskScore), RiskScore, filters)
    query = apply_sorting(query, RiskScore, sort_fields, _RISK_SORTABLE_FIELDS, default_field="computed_at")
    return await paginate(db, query, pagination, RiskScoreRead)


@router.post(
    "/risk-scores",
    response_model=RiskScoreRead,
    status_code=201,
    summary="Record a computed risk score",
    description="Ingested by the Risk Fusion Agent (RISK_FUSION_ENGINE.md) — append-only.",
)
async def create_risk_score(
    payload: RiskScoreCreate,
    db: AsyncSession = Depends(get_db),
    _principal=Depends(auth.require_roles(*_WRITE_ROLES)),
) -> RiskScoreRead:
    risk_score = await service.create_risk_score(db, payload)
    logger.info("risk_score_recorded", risk_score_id=risk_score.id, score=risk_score.score)
    return RiskScoreRead.model_validate(risk_score)


@router.get("/predictions", response_model=Page[PredictionRead], summary="List predictions")
async def list_predictions(
    pagination: PaginationParams = Depends(),
    sort_fields: list[tuple[str, bool]] = Depends(parse_sort),
    filters: PredictionFilter = Depends(),
    db: AsyncSession = Depends(get_db),
    _principal=Depends(auth.require_roles(*_READ_ROLES)),
) -> Page[PredictionRead]:
    query = apply_filters(select(Prediction), Prediction, filters)
    query = apply_sorting(query, Prediction, sort_fields, _PREDICTION_SORTABLE_FIELDS, default_field="predicted_at")
    return await paginate(db, query, pagination, PredictionRead)


@router.get(
    "/predictions/{prediction_id}",
    response_model=PredictionRead,
    summary="Get a prediction by ID",
    responses={404: {"description": "Prediction not found"}},
)
async def get_prediction(
    prediction_id: int,
    db: AsyncSession = Depends(get_db),
    _principal=Depends(auth.require_roles(*_READ_ROLES)),
) -> PredictionRead:
    prediction = await service.get_prediction_or_404(db, prediction_id)
    return PredictionRead.model_validate(prediction)


@router.post(
    "/predictions",
    response_model=PredictionRead,
    status_code=201,
    summary="Record a model prediction",
)
async def create_prediction(
    payload: PredictionCreate,
    db: AsyncSession = Depends(get_db),
    _principal=Depends(auth.require_roles(*_WRITE_ROLES)),
) -> PredictionRead:
    prediction = await service.create_prediction(db, payload)
    logger.info("prediction_recorded", prediction_id=prediction.id, model_name=prediction.model_name)
    return PredictionRead.model_validate(prediction)


@router.post(
    "/predictions/{prediction_id}/outcome",
    response_model=PredictionRead,
    summary="Record a prediction's actual outcome",
    description="Feeds the Learning Agent (AGENT_ARCHITECTURE.md §11) — a prediction's outcome is recorded once.",
    responses={404: {"description": "Prediction not found"}, 422: {"description": "Outcome already recorded"}},
)
async def record_outcome(
    prediction_id: int,
    payload: PredictionOutcomeRequest,
    db: AsyncSession = Depends(get_db),
    _principal=Depends(auth.require_roles(*_WRITE_ROLES)),
) -> PredictionRead:
    prediction = await service.record_outcome(db, prediction_id, payload.actual_outcome)
    logger.info("prediction_outcome_recorded", prediction_id=prediction.id)
    return PredictionRead.model_validate(prediction)
