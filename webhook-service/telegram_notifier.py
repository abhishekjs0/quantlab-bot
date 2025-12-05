#!/usr/bin/env python3
"""
Telegram Notification Module
Sends consolidated notifications for TradingView alerts and Dhan order executions
"""

import os
import logging
import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional, Dict, Any, List
import aiohttp

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")


class TelegramNotifier:
    """Handle Telegram notifications for trading events"""
    
    def __init__(self, bot_token: Optional[str] = None, chat_id: Optional[str] = None):
        """
        Initialize Telegram notifier
        
        Args:
            bot_token: Telegram Bot API token (from BotFather)
            chat_id: Telegram chat ID to send messages to
        """
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")
        self.enabled = bool(self.bot_token and self.chat_id)
        
        # Track daily order counts
        self._daily_stats = {
            "date": None,
            "total": 0,
            "successful": 0,
            "failed": 0,
            "rejected": 0
        }
        
        if not self.enabled:
            logger.warning("⚠️  Telegram notifications disabled (missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID)")
        else:
            logger.info(f"✅ Telegram notifications enabled for chat {self.chat_id}")
    
    def _update_daily_stats(self, success: bool, rejected: bool = False):
        """Update daily order statistics"""
        today = datetime.now(IST).date()
        
        # Reset if new day
        if self._daily_stats["date"] != today:
            self._daily_stats = {
                "date": today,
                "total": 0,
                "successful": 0,
                "failed": 0,
                "rejected": 0
            }
        
        self._daily_stats["total"] += 1
        if rejected:
            self._daily_stats["rejected"] += 1
        elif success:
            self._daily_stats["successful"] += 1
        else:
            self._daily_stats["failed"] += 1
    
    def _get_daily_summary(self) -> str:
        """Get daily order summary string"""
        stats = self._daily_stats
        return f"{stats['successful']}/{stats['total']} today"
    
    async def send_message(self, message: str, parse_mode: str = "HTML") -> bool:
        """
        Send a message to Telegram
        
        Args:
            message: Message text (supports HTML formatting)
            parse_mode: Message formatting (HTML or Markdown)
            
        Returns:
            True if sent successfully, False otherwise
        """
        if not self.enabled:
            return False
        
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=10) as response:
                    if response.status == 200:
                        logger.info("✅ Telegram message sent successfully")
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ Telegram API error {response.status}: {error_text}")
                        return False
        except asyncio.TimeoutError:
            logger.error("❌ Telegram API timeout")
            return False
        except Exception as e:
            logger.error(f"❌ Failed to send Telegram message: {e}")
            return False
    
    async def notify_order_complete(
        self, 
        legs: List[Dict[str, Any]],
        results: List[Dict[str, Any]],
        execution_mode: str = "IMMEDIATE"
    ) -> bool:
        """
        Send a single consolidated notification for an alert with all order results
        
        Args:
            legs: List of order legs from the alert
            results: List of order results
            execution_mode: IMMEDIATE, AMO, or QUEUED
            
        Returns:
            True if sent successfully
        """
        if not self.enabled:
            return False
        
        timestamp = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST")
        
        # Count results
        successful = sum(1 for r in results if r.get("status") == "success")
        failed = sum(1 for r in results if r.get("status") == "failed")
        rejected = sum(1 for r in results if r.get("status") == "rejected")
        total = len(results)
        
        # Update daily stats
        for r in results:
            self._update_daily_stats(
                success=r.get("status") == "success",
                rejected=r.get("status") == "rejected"
            )
        
        # Overall status
        if failed > 0 or rejected > 0:
            overall_emoji = "⚠️" if successful > 0 else "❌"
            overall_status = "PARTIAL" if successful > 0 else "FAILED"
        else:
            overall_emoji = "✅"
            overall_status = "SUCCESS"
        
        # Execution mode description
        mode_desc = {
            "IMMEDIATE": "🟢 Executed immediately (market open)",
            "AMO": "🌙 AMO placed (executes at pre-market)",
            "QUEUED": "📋 Queued (will place when market opens)"
        }.get(execution_mode, f"⚙️ {execution_mode}")
        
        # Build orders section
        orders_text = ""
        for i, (leg, result) in enumerate(zip(legs, results), 1):
            status_emoji = {
                "success": "✅",
                "failed": "❌",
                "rejected": "⚠️"
            }.get(result.get("status", ""), "❓")
            
            action = "🟢" if leg.get('transactionType', leg.get('transaction', '')) in ['B', 'BUY'] else "🔴"
            symbol = leg.get('symbol', 'UNKNOWN')
            qty = leg.get('quantity', 0)
            exchange = leg.get('exchange', 'NSE').replace('_DLY', '')
            order_id = result.get('order_id', '')
            
            orders_text += f"\n{status_emoji} {action} {qty} × <b>{symbol}</b> @ {exchange}"
            if order_id:
                orders_text += f"\n   📝 ID: <code>{order_id}</code>"
            elif result.get("status") == "rejected":
                orders_text += f"\n   ⚠️ {result.get('message', 'Rejected')}"
            elif result.get("status") == "failed":
                orders_text += f"\n   ❌ {result.get('message', 'Failed')}"
        
        message = f"""
{overall_emoji} <b>Order {overall_status}</b>

⏰ {timestamp}
{mode_desc}

<b>Orders ({successful}/{total}):</b>{orders_text}

📊 Daily: {self._get_daily_summary()}
"""
        
        return await self.send_message(message.strip())
    
    async def notify_queued(
        self,
        legs: List[Dict[str, Any]],
        scheduled_time: datetime
    ) -> bool:
        """
        Notify that orders have been queued for later execution
        
        Args:
            legs: Order legs that were queued
            scheduled_time: When the orders will be executed
            
        Returns:
            True if sent successfully
        """
        if not self.enabled:
            return False
        
        timestamp = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST")
        scheduled_str = scheduled_time.strftime("%Y-%m-%d %H:%M IST")
        
        # Build orders section
        orders_text = ""
        for leg in legs:
            action = "🟢" if leg.get('transactionType', leg.get('transaction', '')) in ['B', 'BUY'] else "🔴"
            symbol = leg.get('symbol', 'UNKNOWN')
            qty = leg.get('quantity', 0)
            exchange = leg.get('exchange', 'NSE').replace('_DLY', '')
            orders_text += f"\n  {action} {qty} × <b>{symbol}</b> @ {exchange}"
        
        message = f"""
📋 <b>Orders Queued</b>

⏰ {timestamp}
⏳ Scheduled: {scheduled_str}

<b>Pending Orders ({len(legs)}):</b>{orders_text}
"""
        
        return await self.send_message(message.strip())
    
    async def notify_error(self, error_type: str, details: str) -> bool:
        """
        Notify about system errors
        
        Args:
            error_type: Type of error
            details: Error details
            
        Returns:
            True if sent successfully
        """
        if not self.enabled:
            return False
        
        timestamp = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST")
        
        message = f"""
🚨 <b>System Error</b>

⏰ {timestamp}
❌ {error_type}

{details}
"""
        
        return await self.send_message(message.strip())
    
    # Legacy methods for backward compatibility - just log but don't send
    async def notify_alert_received(self, *args, **kwargs) -> bool:
        """Legacy - no longer sends separate message"""
        return True
    
    async def notify_order_result(self, *args, **kwargs) -> bool:
        """Legacy - no longer sends separate message"""
        return True
    
    async def notify_batch_summary(self, *args, **kwargs) -> bool:
        """Legacy - no longer sends separate message"""
        return True


# Singleton instance
_notifier: Optional[TelegramNotifier] = None


def get_notifier() -> TelegramNotifier:
    """Get or create Telegram notifier singleton"""
    global _notifier
    if _notifier is None:
        _notifier = TelegramNotifier()
    return _notifier
