"""
Signal Queue Module for Handling Non-Trading Hours Orders
Stores signals in Firestore for persistence across container restarts/deployments.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Try to import Firestore
try:
    from google.cloud import firestore
    FIRESTORE_AVAILABLE = True
except ImportError:
    FIRESTORE_AVAILABLE = False
    logger.warning("⚠️  Firestore not available for signal queue")


class SignalQueue:
    """Manages queued trading signals with Firestore persistence"""

    COLLECTION_NAME = "signal_queue"

    def __init__(self, db_path: str = "signal_queue.db"):
        """
        Initialize signal queue with Firestore
        
        Args:
            db_path: Ignored - kept for backward compatibility
        """
        self.db: Optional[firestore.Client] = None
        
        if FIRESTORE_AVAILABLE:
            try:
                self.db = firestore.Client(project="tradingview-webhook-prod")
                logger.info("✅ Signal queue initialized with Firestore persistence")
            except Exception as e:
                logger.error(f"❌ Failed to initialize Firestore for signal queue: {e}")
                self.db = None
        else:
            logger.warning("⚠️  Signal queue running without persistence (Firestore unavailable)")

    def _get_collection(self):
        """Get the signal queue collection"""
        if not self.db:
            return None
        return self.db.collection(self.COLLECTION_NAME)

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
        collection = self._get_collection()
        if not collection:
            logger.error("❌ Cannot add signal: Firestore not available")
            return -1

        received_time = datetime.now()
        
        # Generate a unique signal ID using timestamp
        signal_id = int(received_time.timestamp() * 1000) % 1000000000
        
        doc_data = {
            "signal_id": signal_id,
            "received_time": received_time,
            "scheduled_time": scheduled_time,
            "execution_time": None,
            "status": "QUEUED",
            "payload": json.dumps(payload),
            "result": None,
            "error": None,
            "reason": reason,
            "created_at": firestore.SERVER_TIMESTAMP
        }

        try:
            doc_ref = collection.document(str(signal_id))
            doc_ref.set(doc_data)
            
            logger.info(
                f"📥 Signal queued: ID={signal_id}, scheduled={scheduled_time}, "
                f"reason={reason}"
            )
            return signal_id
            
        except Exception as e:
            logger.error(f"❌ Failed to queue signal: {e}")
            return -1

    def get_pending_signals(self, limit: int = 100) -> list[dict]:
        """
        Get all pending signals ready for execution

        Args:
            limit: Maximum number of signals to return

        Returns:
            List of pending signals with metadata
        """
        collection = self._get_collection()
        if not collection:
            return []

        try:
            now = datetime.now()
            
            # Query for QUEUED signals where scheduled_time <= now or is None
            query = (
                collection
                .where("status", "==", "QUEUED")
                .order_by("received_time")
                .limit(limit)
            )
            
            docs = query.stream()
            
            signals = []
            for doc in docs:
                data = doc.to_dict()
                scheduled = data.get("scheduled_time")
                
                # Check if signal is ready for execution
                if scheduled is None or (hasattr(scheduled, 'timestamp') and scheduled <= now) or \
                   (isinstance(scheduled, datetime) and scheduled <= now):
                    signals.append({
                        "signal_id": data.get("signal_id"),
                        "received_time": self._format_datetime(data.get("received_time")),
                        "scheduled_time": self._format_datetime(scheduled),
                        "status": data.get("status"),
                        "payload": json.loads(data.get("payload", "{}"))
                    })
            
            if signals:
                logger.info(f"📋 Found {len(signals)} pending signals")
            
            return signals
            
        except Exception as e:
            logger.error(f"❌ Error getting pending signals: {e}")
            return []

    def _format_datetime(self, dt) -> str | None:
        """Format datetime to ISO string"""
        if dt is None:
            return None
        if hasattr(dt, 'isoformat'):
            return dt.isoformat()
        return str(dt)

    def mark_processing(self, signal_id: int) -> None:
        """Mark signal as currently being processed"""
        collection = self._get_collection()
        if not collection:
            return

        try:
            doc_ref = collection.document(str(signal_id))
            doc_ref.update({"status": "PROCESSING"})
            logger.info(f"⚙️  Processing signal: ID={signal_id}")
        except Exception as e:
            logger.error(f"❌ Error marking signal as processing: {e}")

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
        collection = self._get_collection()
        if not collection:
            return

        exec_time = execution_time or datetime.now()

        try:
            doc_ref = collection.document(str(signal_id))
            doc_ref.update({
                "status": "EXECUTED",
                "execution_time": exec_time,
                "result": json.dumps(result)
            })
            logger.info(f"✅ Signal executed: ID={signal_id}, time={exec_time}")
        except Exception as e:
            logger.error(f"❌ Error marking signal as executed: {e}")

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
        collection = self._get_collection()
        if not collection:
            return

        exec_time = execution_time or datetime.now()

        try:
            doc_ref = collection.document(str(signal_id))
            doc_ref.update({
                "status": "FAILED",
                "execution_time": exec_time,
                "error": error
            })
            logger.error(f"❌ Signal failed: ID={signal_id}, error={error}")
        except Exception as e:
            logger.error(f"❌ Error marking signal as failed: {e}")

    def get_signal(self, signal_id: int) -> dict | None:
        """
        Get signal details by ID

        Args:
            signal_id: Signal ID

        Returns:
            Signal details or None if not found
        """
        collection = self._get_collection()
        if not collection:
            return None

        try:
            doc_ref = collection.document(str(signal_id))
            doc = doc_ref.get()
            
            if not doc.exists:
                return None
            
            data = doc.to_dict()
            return {
                "signal_id": data.get("signal_id"),
                "received_time": self._format_datetime(data.get("received_time")),
                "scheduled_time": self._format_datetime(data.get("scheduled_time")),
                "execution_time": self._format_datetime(data.get("execution_time")),
                "status": data.get("status"),
                "payload": json.loads(data.get("payload", "{}")) if data.get("payload") else None,
                "result": json.loads(data.get("result", "{}")) if data.get("result") else None,
                "error": data.get("error")
            }
        except Exception as e:
            logger.error(f"❌ Error getting signal: {e}")
            return None

    def recover_on_startup(self) -> dict:
        """
        Recover queue state on application startup.
        
        - Reset all PROCESSING signals back to QUEUED
        - Log recovery statistics
        
        Returns:
            Dict with recovery statistics
        """
        collection = self._get_collection()
        if not collection:
            return {"reset_processing": 0, "pending_queued": 0}

        try:
            # Reset PROCESSING signals
            processing_query = collection.where("status", "==", "PROCESSING")
            processing_docs = processing_query.stream()
            
            reset_count = 0
            for doc in processing_docs:
                doc.reference.update({"status": "QUEUED"})
                reset_count += 1
            
            # Count pending signals
            pending_query = collection.where("status", "==", "QUEUED")
            pending_docs = list(pending_query.stream())
            pending_count = len(pending_docs)
            
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
        except Exception as e:
            logger.error(f"❌ Error during startup recovery: {e}")
            return {"reset_processing": 0, "pending_queued": 0, "error": str(e)}

    def get_queue_stats(self) -> dict[str, int]:
        """
        Get queue statistics

        Returns:
            Dict with counts by status
        """
        collection = self._get_collection()
        if not collection:
            return {}

        try:
            stats = {}
            for status in ["QUEUED", "PROCESSING", "EXECUTED", "FAILED"]:
                query = collection.where("status", "==", status)
                docs = list(query.stream())
                if docs:
                    stats[status] = len(docs)
            
            return stats
        except Exception as e:
            logger.error(f"❌ Error getting queue stats: {e}")
            return {}

    def cleanup_old_signals(self, days: int = 30) -> int:
        """
        Delete old executed/failed signals

        Args:
            days: Delete signals older than this many days

        Returns:
            Number of signals deleted
        """
        collection = self._get_collection()
        if not collection:
            return 0

        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            deleted = 0
            for status in ["EXECUTED", "FAILED"]:
                query = (
                    collection
                    .where("status", "==", status)
                    .where("execution_time", "<", cutoff_date)
                )
                docs = query.stream()
                
                for doc in docs:
                    doc.reference.delete()
                    deleted += 1
            
            logger.info(f"🗑️  Cleaned up {deleted} old signals (older than {days} days)")
            return deleted
        except Exception as e:
            logger.error(f"❌ Error cleaning up old signals: {e}")
            return 0

    def reset_stuck_signals(self, timeout_minutes: int = 10) -> int:
        """
        Reset signals stuck in PROCESSING state

        Args:
            timeout_minutes: Reset signals in PROCESSING for more than this duration

        Returns:
            Number of signals reset
        """
        collection = self._get_collection()
        if not collection:
            return 0

        try:
            cutoff_time = datetime.now() - timedelta(minutes=timeout_minutes)
            
            # Find PROCESSING signals older than timeout
            query = collection.where("status", "==", "PROCESSING")
            docs = query.stream()
            
            reset_count = 0
            for doc in docs:
                data = doc.to_dict()
                received = data.get("received_time")
                
                # Check if signal has been processing too long
                if received and hasattr(received, 'timestamp'):
                    if received < cutoff_time:
                        doc.reference.update({"status": "QUEUED"})
                        reset_count += 1
                        logger.warning(f"⚠️  Reset stuck signal: {data.get('signal_id')}")
            
            return reset_count
        except Exception as e:
            logger.error(f"❌ Error resetting stuck signals: {e}")
            return 0


def calculate_amo_scheduled_time(target_date, amo_timing: str = "OPEN_30") -> datetime:
    """
    Calculate the scheduled execution time for AMO order
    
    Args:
        target_date: Target trading date
        amo_timing: AMO timing preference
        
    Returns:
        Scheduled datetime for order execution
    """
    from pytz import timezone
    IST = timezone("Asia/Kolkata")
    
    # AMO timing mappings (when to execute the order)
    timing_map = {
        "PRE_OPEN": (9, 0),   # 9:00 AM - Pre-market
        "OPEN": (9, 15),      # 9:15 AM - Market open
        "OPEN_30": (9, 45),   # 9:45 AM - 30 min after open
        "OPEN_60": (10, 15),  # 10:15 AM - 60 min after open
    }
    
    hour, minute = timing_map.get(amo_timing, (9, 15))
    
    if hasattr(target_date, 'replace'):
        scheduled = target_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
    else:
        from datetime import datetime as dt
        scheduled = dt.combine(target_date, dt.min.time()).replace(
            hour=hour, minute=minute, second=0, microsecond=0
        )
    
    # Ensure timezone aware
    if scheduled.tzinfo is None:
        scheduled = IST.localize(scheduled)
    
    return scheduled


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
