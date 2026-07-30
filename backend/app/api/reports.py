"""Reporting endpoints: live dashboard metrics + AI daily report."""
from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.agents.report import run_daily_report
from app.core.config import settings
from app.core.db import get_db
from app.core.deps import get_current_user
from app.core.tenancy import bypass_tenant_isolation
from app.llm import get_llm
from app.llm.base import LLMError
from app.models.organization import Organization
from app.models.user import User
from app.schemas.performance import PerformanceReport, RoiReport
from app.services.pdf import text_to_pdf
from app.services.performance import compute_performance
from app.services.report_service import compute_daily_metrics
from app.services.roi import RoiAssumptions, compute_roi, render_one_pager

router = APIRouter()


@router.get("/dashboard")
def dashboard_metrics(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> dict:
    """Live metrics for the dashboard cards (no LLM — fast)."""
    return compute_daily_metrics(db)


@router.get("/performance", response_model=PerformanceReport)
def performance_report(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    days: int = 30,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict:
    """Speed-to-quote metrics: response rate, response time, win rate by speed.

    Deterministic (no LLM) — these are the numbers a buyer is asked to act on,
    so they come straight from the database.
    """
    if days < 1 or days > 366:
        raise HTTPException(status_code=400, detail="days must be between 1 and 366")
    end = end_date or date.today()
    start = start_date or (end - timedelta(days=days - 1))
    if start > end:
        raise HTTPException(status_code=400, detail="start_date must not be after end_date")
    return compute_performance(db, start, end)


def _roi_window(days: int) -> tuple[date, date]:
    if days < 1 or days > 366:
        raise HTTPException(status_code=400, detail="days must be between 1 and 366")
    end = date.today()
    return end - timedelta(days=days - 1), end


@router.get("/roi", response_model=RoiReport)
def roi_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    days: int = 90,
    gross_profit_per_shipment: float = 400.0,
    fast_response_hours: float = 4.0,
    subscription_per_user_per_month: float = 99.0,
) -> dict:
    """What answering faster would be worth, from this company's own records.

    The projection uses the caller's own win rates by response speed; if their
    fast answers do not convert better, it reports no benefit, and if there is
    not enough history it refuses to project at all.
    """
    start, end = _roi_window(days)
    return compute_roi(
        db,
        start,
        end,
        RoiAssumptions(
            gross_profit_per_shipment=gross_profit_per_shipment,
            fast_response_hours=fast_response_hours,
            subscription_per_user_per_month=subscription_per_user_per_month,
        ),
    )


@router.get("/roi.pdf")
def roi_one_pager(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    days: int = 90,
    gross_profit_per_shipment: float = 400.0,
    fast_response_hours: float = 4.0,
    subscription_per_user_per_month: float = 99.0,
) -> Response:
    """The one-pager, generated from the numbers rather than decorated with them."""
    start, end = _roi_window(days)
    roi = compute_roi(
        db,
        start,
        end,
        RoiAssumptions(
            gross_profit_per_shipment=gross_profit_per_shipment,
            fast_response_hours=fast_response_hours,
            subscription_per_user_per_month=subscription_per_user_per_month,
        ),
    )
    with bypass_tenant_isolation(db):
        organization = db.get(Organization, current_user.organization_id)
    company = organization.name if organization else settings.company_name

    pdf = text_to_pdf(
        f"Response-time review — {company}", render_one_pager(roi, company)
    )
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="response-time-review-{end.isoformat()}.pdf"'
            )
        },
    )


@router.get("/performance.csv")
def performance_csv(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    days: int = 30,
) -> Response:
    """The daily series, for a spreadsheet or a board pack."""
    end = date.today()
    metrics = compute_performance(db, end - timedelta(days=max(days, 1) - 1), end)
    lines = ["date,rfqs_received,rfqs_quoted,median_response_hours"]
    for point in metrics["daily"]:
        median = point["median_response_hours"]
        lines.append(
            f"{point['date']},{point['rfqs']},{point['quoted']},"
            f"{'' if median is None else median}"
        )
    return Response(
        content="\n".join(lines) + "\n",
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="performance.csv"'},
    )


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
