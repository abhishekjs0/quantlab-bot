"""
Signal Queue Module for Handling Non-Trading Hours Orders
Stores signals received during weekends/holidays and executes them on next trading day
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class SignalQueue:
    """Manages queued trading signals for delayed execution"""

    def __init__(self, db_path: str = "signal_queue.db"):
        """
        Initialize signal queue with SQLite database

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._init_database()
        logger.info(f"✅ Signal queue initialized: {db_path}")

    def _init_database(self) -> None:
        """Create database table if not exists"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS signal_queue (
                signal_id INTEGER PRIMARY KEY AUTOINCREMENT,
                received_time TEXT NOT NULL,
                scheduled_time TEXT,
                execution_time TEXT,
                status TEXT NOT NULL,
                payload TEXT NOT NULL,
                result TEXT,
                error TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create index for faster queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_status 
            ON signal_queue(status)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_scheduled_time 
            ON signal_queue(scheduled_time)
        """)

        conn.commit()
        conn.close()

    def add_signal(
        self,
        payload: dict[str, Any],
        scheduled_time: datetime | None = None,
        reason: str = "outside_trading_hours"
    ) -> int:
        """
        Add signal to queue for later execution

        Args:
            payload: Full webhook payload (dict)
            scheduled_time: When to execute (if None, calculated based on trading calendar)
            reason: Reason for queueing

        Returns:
            signal_id: Unique ID of queued signal
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        received_time = datetime.now().isoformat()
        scheduled_time_str = scheduled_time.isoformat() if scheduled_time else None

        cursor.execute("""
            INSERT INTO signal_queue 
            (received_time, scheduled_time, status, payload)
            VALUES (?, ?, ?, ?)
        """, (
            received_time,
            scheduled_time_str,
            "QUEUED",
            json.dumps(payload)
        ))

        signal_id = cursor.lastrowid
        conn.commit()
        conn.close()

        logger.info(
            f"📥 Signal queued: ID={signal_id}, scheduled={scheduled_time_str}, "
            f"reason={reason}"
        )

        return signal_id

    def get_pending_signals(self, limit: int = 100) -> list[dict]:
        """
        Get all pending signals ready for execution

        Args:
            limit: Maximum number of signals to return

        Returns:
            List of pending signals with metadata
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT 
                signal_id,
                received_time,
                scheduled_time,
                status,
                payload
            FROM signal_queue
            WHERE status = 'QUEUED'
            AND (scheduled_time IS NULL OR scheduled_time <= ?)
            ORDER BY received_time ASC
            LIMIT ?
        """, (datetime.now().isoformat(), limit))

        rows = cursor.fetchall()
        conn.close()

        signals = []
        for row in rows:
            signals.append({
                "signal_id": row["signal_id"],
                "received_time": row["received_time"],
                "scheduled_time": row["scheduled_time"],
                "status": row["status"],
                "payload": json.loads(row["payload"])
            })

        if signals:
            logger.info(f"📋 Found {len(signals)} pending signals")

        return signals

    def mark_processing(self, signal_id: int) -> None:
        """Mark signal as currently being processed"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE signal_queue
            SET status = 'PROCESSING'
            WHERE signal_id = ?
        """, (signal_id,))

        conn.commit()
        conn.close()

        logger.info(f"⚙️  Processing signal: ID={signal_id}")

    def mark_executed(
        self,
        signal_id: int,
        result: dict[str, Any],
        execution_time: datetime | None = None
    ) -> None:
        """
        Mark signal as successfully executed

        Args:
            signal_id: Signal ID
            result: Execution result (order responses, etc.)
            execution_time: When executed (default: now)
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        exec_time = execution_time or datetime.now()

        cursor.execute("""
            UPDATE signal_queue
            SET 
                status = 'EXECUTED',
                execution_time = ?,
                result = ?
            WHERE signal_id = ?
        """, (
            exec_time.isoformat(),
            json.dumps(result),
            signal_id
        ))

        conn.commit()
        conn.close()

        logger.info(f"✅ Signal executed: ID={signal_id}, time={exec_time}")

    def mark_failed(
        self,
        signal_id: int,
        error: str,
        execution_time: datetime | None = None
    ) -> None:
        """
        Mark signal as failed

        Args:
            signal_id: Signal ID
            error: Error message
            execution_time: When attempted (default: now)
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        exec_time = execution_time or datetime.now()

        cursor.execute("""
            UPDATE signal_queue
            SET 
                status = 'FAILED',
                execution_time = ?,
                error = ?
            WHERE signal_id = ?
        """, (
            exec_time.isoformat(),
            error,
            signal_id
        ))

        conn.commit()
        conn.close()

        logger.error(f"❌ Signal failed: ID={signal_id}, error={error}")

    def get_signal(self, signal_id: int) -> dict | None:
        """
        Get signal details by ID

        Args:
            signal_id: Signal ID

        Returns:
            Signal details or None if not found
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT *
            FROM signal_queue
            WHERE signal_id = ?
        """, (signal_id,))

        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return {
            "signal_id": row["signal_id"],
            "received_time": row["received_time"],
            "scheduled_time": row["scheduled_time"],
            "execution_time": row["execution_time"],
            "status": row["status"],
            "payload": json.loads(row["payload"]) if row["payload"] else None,
            "result": json.loads(row["result"]) if row["result"] else None,
            "error": row["error"]
        }

    def recover_on_startup(self) -> dict:
        """
        Recover queue state on application startup.
        
        - Reset all PROCESSING signals back to QUEUED
        - Log recovery statistics
        
        Should be called once during application lifespan startup.
        
        Returns:
            Dict with recovery statistics
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Reset any signals stuck in PROCESSING state (from previous crash)
        cursor.execute("""
            UPDATE signal_queue
            SET status = 'QUEUED'
            WHERE status = 'PROCESSING'
        """)
        reset_count = cursor.rowcount
        
        # Get pending signals count
        cursor.execute("""
            SELECT COUNT(*) FROM signal_queue WHERE status = 'QUEUED'
        """)
        pending_count = cursor.fetchone()[0]
        
        conn.commit()
        conn.close()
        
        if reset_count > 0:
            logger.warning(f"⚠️  Startup recovery: Reset {reset_count} stuck PROCESSING signals")
        
        if pending_count > 0:
            logger.info(f"📥 Startup recovery: {pending_count} signals pending in queue")
        else:
            logger.info("✅ Startup recovery: Queue is empty")
        
        return {
            "reset_processing": reset_count,
            "pending_queued": pending_count
        }

    def get_queue_stats(self) -> dict[str, int]:
        """
        Get queue statistics

        Returns:
            Dict with counts by status
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT 
                status,
                COUNT(*) as count
            FROM signal_queue
            GROUP BY status
        """)

        stats = {}
        for row in cursor.fetchall():
            stats[row[0]] = row[1]

        conn.close()

        return stats

    def cleanup_old_signals(self, days: int = 30) -> int:
        """
        Delete old executed/failed signals

        Args:
            days: Delete signals older than this many days

        Returns:
            Number of signals deleted
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cutoff_date = datetime.now().replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        cutoff_date = cutoff_date.replace(day=cutoff_date.day - days)

        cursor.execute("""
            DELETE FROM signal_queue
            WHERE status IN ('EXECUTED', 'FAILED')
            AND created_at < ?
        """, (cutoff_date.isoformat(),))

        deleted = cursor.rowcount
        conn.commit()
        conn.close()

        logger.info(f"🗑️  Cleaned up {deleted} old signals (older than {days} days)")

        return deleted

    def reset_stuck_signals(self, timeout_minutes: int = 10) -> int:
        """
        Reset signals stuck in PROCESSING state

        Args:
            timeout_minutes: Reset signals in PROCESSING for more than this duration

        Returns:
            Number of signals reset
        """
        from datetime import timedelta
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Calculate timeout timestamp (subtract minutes properly with timedelta)
        timeout_time = datetime.now() - timedelta(minutes=timeout_minutes)

        cursor.execute("""
            UPDATE signal_queue
            SET status = 'QUEUED'
            WHERE status = 'PROCESSING'
            AND created_at < ?
        """, (timeout_time.isoformat(),))

        reset_count = cursor.rowcount
        conn.commit()
        conn.close()

        if reset_count > 0:
            logger.warning(
                f"⚠️  Reset {reset_count} stuck signals "
                f"(PROCESSING > {timeout_minutes} min)"
            )

        return reset_count


# Helper functions for webhook integration

def calculate_amo_scheduled_time(next_trading_date, amo_timing: str = "PRE_OPEN"):
    """
    Calculate scheduled execution time based on AMO timing preference
    
    Args:
        next_trading_date: Date object for next trading day
        amo_timing: AMO timing preference (PRE_OPEN, OPEN, OPEN_30, OPEN_60)
    
    Returns:
        datetime with appropriate time based on AMO timing
    """
    from zoneinfo import ZoneInfo
    
    # AMO timing to hours/minutes mapping
    amo_timing_map = {
        "PRE_OPEN": (9, 0),   # 9:00 AM - Pre-open
        "OPEN": (9, 15),       # 9:15 AM - Market open
        "OPEN_30": (9, 45),    # 9:45 AM - 30 min after open
        "OPEN_60": (10, 15),   # 10:15 AM - 60 min after open
    }
    
    hour, minute = amo_timing_map.get(amo_timing, (9, 0))
    
    return datetime.combine(next_trading_date, datetime.min.time()).replace(
        hour=hour, minute=minute, second=0, microsecond=0,
        tzinfo=ZoneInfo("Asia/Kolkata")
    )


def should_queue_signal(amo_timing: str = "PRE_OPEN") -> tuple[bool, str, datetime | None]:
    """
    Check if signal should be queued based on market status
    
    Uses trading_calendar functions (not a class)
    
    Args:
        amo_timing: AMO timing preference for scheduling

    Returns:
        Tuple of (should_queue, reason, scheduled_time)
    """
    from trading_calendar import get_market_status, is_trading_day, get_next_trading_day
    
    # Check if it's a trading day
    if not is_trading_day():
        next_trading_date = get_next_trading_day()
        scheduled_time = calculate_amo_scheduled_time(next_trading_date, amo_timing)

        return (
            True,
            "Non-trading day (weekend/holiday)",
            scheduled_time
        )

    # Get market status
    market_status, market_message = get_market_status()

    # Check if market is closed
    if market_status == "CLOSED":
        # Queue for next trading day with appropriate timing
        next_trading_date = get_next_trading_day()
        scheduled_time = calculate_amo_scheduled_time(next_trading_date, amo_timing)

        return (
            True,
            f"Market closed - queued for next trading day ({market_message})",
            scheduled_time
        )

    # Market is open or in acceptable AMO window
    return (False, f"Market accepting orders ({market_status})", None)


def execute_queued_signal(
    signal: dict,
    webhook_handler,
    signal_queue: SignalQueue
) -> dict:
    """
    Execute a queued signal

    Args:
        signal: Signal from queue with 'signal_id' and 'payload'
        webhook_handler: Function/method to process webhook payload
        signal_queue: SignalQueue instance

    Returns:
        Execution result dict
    """
    signal_id = signal["signal_id"]
    payload = signal["payload"]

    try:
        # Mark as processing
        signal_queue.mark_processing(signal_id)

        # Execute webhook handler
        logger.info(f"🚀 Executing queued signal: ID={signal_id}")
        result = webhook_handler(payload)

        # Mark as executed
        signal_queue.mark_executed(signal_id, result)

        return {
            "status": "success",
            "signal_id": signal_id,
            "result": result
        }

    except Exception as e:
        error_msg = f"Exception executing signal: {str(e)}"
        logger.error(f"❌ {error_msg}")

        # Mark as failed
        signal_queue.mark_failed(signal_id, error_msg)

        return {
            "status": "failed",
            "signal_id": signal_id,
            "error": error_msg
        }
