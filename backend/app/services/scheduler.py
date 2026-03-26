from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from typing import Any

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db import SessionLocal
from app.models import SchedulerJobRun
from app.services.exchange_rate import fetch_and_save_rates

logger = logging.getLogger(__name__)
SCHEDULER_JOB_FX_WEEKLY = "fx-weekly"
_scheduler: BackgroundScheduler | None = None


def get_scheduler() -> BackgroundScheduler | None:
    return _scheduler


def start_scheduler() -> None:
    global _scheduler
    if not settings.scheduler_enabled:
        logger.info("scheduler disabled by config")
        return
    if _scheduler is not None:
        return

    scheduler = BackgroundScheduler(timezone=settings.scheduler_timezone)
    scheduler.add_job(
        run_weekly_fx_job,
        trigger="cron",
        id=SCHEDULER_JOB_FX_WEEKLY,
        day_of_week=settings.scheduler_fx_day_of_week,
        hour=settings.scheduler_fx_hour,
        minute=settings.scheduler_fx_minute,
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    scheduler.start()
    _scheduler = scheduler
    logger.info("scheduler started with weekly FX job")


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is None:
        return
    _scheduler.shutdown(wait=False)
    _scheduler = None


def _open_job_run(db: Session, job_name: str, trigger_source: str) -> SchedulerJobRun:
    row = SchedulerJobRun(
        job_name=job_name,
        trigger_source=trigger_source,
        status="running",
        started_at=datetime.now(timezone.utc),
        detail_json="{}",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _close_job_run(db: Session, row: SchedulerJobRun, status: str, message: str, detail: dict[str, Any]) -> SchedulerJobRun:
    row.status = status
    row.message = message
    row.detail_json = json.dumps(detail, ensure_ascii=False)
    row.finished_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return row


def run_weekly_fx_job(trigger_source: str = "scheduler") -> dict[str, Any]:
    db = SessionLocal()
    job_run = _open_job_run(db, SCHEDULER_JOB_FX_WEEKLY, trigger_source)
    snapshot_date = date.today()
    pairs = []
    fetched = []

    try:
        for raw_pair in settings.scheduler_fx_pairs.split(","):
            normalized = raw_pair.strip().upper()
            if not normalized:
                continue
            base, quote = normalized.split(":", 1)
            pairs.append({"base": base, "quote": quote})
            row = fetch_and_save_rates(db, base, quote, snapshot_date)
            fetched.append(
                {
                    "base": row.base_currency,
                    "quote": row.quote_currency,
                    "rate": float(row.rate),
                    "snapshot_date": row.snapshot_date.isoformat(),
                }
            )

        result = {
            "job_name": SCHEDULER_JOB_FX_WEEKLY,
            "trigger_source": trigger_source,
            "snapshot_date": snapshot_date.isoformat(),
            "pairs": pairs,
            "fetched": fetched,
        }
        _close_job_run(db, job_run, "success", f"fetched {len(fetched)} FX pairs", result)
        return result
    except Exception as exc:
        logger.exception("weekly FX job failed")
        detail = {
            "job_name": SCHEDULER_JOB_FX_WEEKLY,
            "trigger_source": trigger_source,
            "snapshot_date": snapshot_date.isoformat(),
            "pairs": pairs,
            "error": str(exc),
        }
        _close_job_run(db, job_run, "failed", str(exc), detail)
        raise
    finally:
        db.close()


def list_job_runs(db: Session, limit: int = 50, job_name: str | None = None) -> list[dict[str, Any]]:
    query = db.query(SchedulerJobRun)
    if job_name:
        query = query.filter(SchedulerJobRun.job_name == job_name)
    rows = query.order_by(SchedulerJobRun.started_at.desc(), SchedulerJobRun.id.desc()).limit(limit).all()
    return [serialize_job_run(row) for row in rows]


def serialize_job_run(row: SchedulerJobRun) -> dict[str, Any]:
    return {
        "id": row.id,
        "job_name": row.job_name,
        "trigger_source": row.trigger_source,
        "status": row.status,
        "message": row.message,
        "detail": row.detail,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "finished_at": row.finished_at.isoformat() if row.finished_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }
