"""Reporting endpoints: live dashboard metrics + AI daily report."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.agents.report import run_daily_report
from app.core.db import get_db
from app.core.deps import get_current_user
from app.llm import get_llm
from app.llm.base import LLMError
from app.models.user import User
from app.services.pdf import text_to_pdf
from app.services.report_service import compute_daily_metrics

router = APIRouter()


@router.get("/dashboard")
def dashboard_metrics(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    """Live metrics for the dashboard cards (no LLM — fast)."""
    return compute_daily_metrics(db)


@router.get("/daily")
def daily_report(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    """Compute today's metrics and generate the management report text."""
    metrics = compute_daily_metrics(db)
    try:
        report_text = run_daily_report(metrics, get_llm())
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"metrics": metrics, "report_text": report_text}


@router.get("/daily/pdf")
def daily_report_pdf(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> Response:
    metrics = compute_daily_metrics(db)
    try:
        report_text = run_daily_report(metrics, get_llm())
    except LLMError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    pdf = text_to_pdf(f"Daily Report {date.today().isoformat()}", report_text)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="daily-report-{date.today().isoformat()}.pdf"'
        },
    )
