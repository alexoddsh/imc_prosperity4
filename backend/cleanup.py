"""
Periodic cleanup job — runs every INTERVAL_MINUTES in the background.

Rules (all except #3 wait GRACE_MINUTES before acting):
  1. Delete FAILED runs
  2. Delete completed runs with total_pnl < MIN_PNL
  3. Delete PENDING runs stuck for > STUCK_MINUTES
  4. For every round that is not the latest, keep only top TOP_N_PREV_ROUNDS by PnL
  5. After AGE_HOURS hours, keep only the top TOP_N_GLOBAL runs globally

Child rows (trades, prices, internal) cascade automatically via FK constraints.
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy import text
from database import engine

log = logging.getLogger(__name__)

INTERVAL_MINUTES  = 30
STUCK_MINUTES     = 10
GRACE_MINUTES     = 15
MIN_PNL           = 20
TOP_N_PREV_ROUNDS = 20
TOP_N_GLOBAL      = 100
AGE_HOURS         = 3


def _rule_failed(conn) -> list[str]:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=GRACE_MINUTES)
    rows = conn.execute(
        text(
            "SELECT id FROM backtest_runs "
            "WHERE status = 'FAILED' AND created_at < :cutoff"
        ),
        {"cutoff": cutoff},
    ).fetchall()
    return [r[0] for r in rows]


def _rule_low_pnl(conn) -> list[str]:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=GRACE_MINUTES)
    rows = conn.execute(
        text(
            "SELECT id FROM backtest_runs "
            "WHERE status = 'COMPLETED' AND created_at < :cutoff "
            "AND (total_pnl < :min_pnl OR total_pnl IS NULL)"
        ),
        {"cutoff": cutoff, "min_pnl": MIN_PNL},
    ).fetchall()
    return [r[0] for r in rows]


def _rule_stuck_pending(conn) -> list[str]:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=STUCK_MINUTES)
    rows = conn.execute(
        text(
            "SELECT id FROM backtest_runs "
            "WHERE status = 'PENDING' AND created_at < :cutoff"
        ),
        {"cutoff": cutoff},
    ).fetchall()
    return [r[0] for r in rows]


def _rule_prev_rounds_bottom(conn) -> list[str]:
    """For every round except the most recent, delete runs ranked below TOP_N_PREV_ROUNDS."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=GRACE_MINUTES)
    rows = conn.execute(
        text(
            """
            WITH latest_round AS (
                SELECT round_id FROM backtest_runs
                WHERE status = 'COMPLETED'
                ORDER BY created_at DESC
                LIMIT 1
            ),
            ranked AS (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY round_id
                           ORDER BY total_pnl DESC NULLS LAST
                       ) AS rn
                FROM backtest_runs
                WHERE status = 'COMPLETED'
                  AND created_at < :cutoff
                  AND round_id NOT IN (SELECT round_id FROM latest_round)
            )
            SELECT id FROM ranked WHERE rn > :top_n
            """
        ),
        {"cutoff": cutoff, "top_n": TOP_N_PREV_ROUNDS},
    ).fetchall()
    return [r[0] for r in rows]


def _rule_global_top_n(conn) -> list[str]:
    """For runs older than AGE_HOURS, keep only the top TOP_N_GLOBAL globally."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=AGE_HOURS)
    rows = conn.execute(
        text(
            """
            WITH ranked AS (
                SELECT id,
                       ROW_NUMBER() OVER (
                           ORDER BY total_pnl DESC NULLS LAST
                       ) AS rn
                FROM backtest_runs
                WHERE status = 'COMPLETED'
                  AND created_at < :cutoff
            )
            SELECT id FROM ranked WHERE rn > :top_n
            """
        ),
        {"cutoff": cutoff, "top_n": TOP_N_GLOBAL},
    ).fetchall()
    return [r[0] for r in rows]


def run_cleanup():
    log.info("[cleanup] running...")
    try:
        with engine.begin() as conn:
            to_delete: set[str] = set()
            to_delete.update(_rule_failed(conn))
            to_delete.update(_rule_low_pnl(conn))
            to_delete.update(_rule_stuck_pending(conn))
            to_delete.update(_rule_prev_rounds_bottom(conn))
            to_delete.update(_rule_global_top_n(conn))

            if to_delete:
                conn.execute(
                    text("DELETE FROM backtest_runs WHERE id = ANY(:ids)"),
                    {"ids": list(to_delete)},
                )
                log.info("[cleanup] deleted %d run(s)", len(to_delete))
            else:
                log.info("[cleanup] nothing to delete")

    except Exception as e:
        log.exception("[cleanup] error: %s", e)


async def cleanup_loop():
    while True:
        await asyncio.sleep(INTERVAL_MINUTES * 60)
        run_cleanup()
