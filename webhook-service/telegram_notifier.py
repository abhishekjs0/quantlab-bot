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
        execution_mode: str = "IMMEDIATE",
        holdings_data: Optional[Dict[str, Dict]] = None,
        ltp_data: Optional[Dict[str, float]] = None
    ) -> bool:
        """
        Send a single consolidated notification for an alert with all order results.
        
        For SELL orders, shows entry price, exit price, and P&L if holdings_data is provided.
        
        Args:
            legs: List of order legs from the alert
            results: List of order results
            execution_mode: IMMEDIATE, AMO, or QUEUED
            holdings_data: Dict of symbol -> {avg_price, quantity} for P&L calculation
            ltp_data: Dict of symbol -> LTP for exit price
            
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
        
        # Build title with symbol info for single-leg orders
        if total == 1:
            leg = legs[0]
            result = results[0]
            symbol = leg.get("symbol", "UNKNOWN")
            qty = leg.get("quantity", 0)
            action = "BUY" if leg.get("transactionType", leg.get("transaction", "")) in ["B", "BUY"] else "SELL"
            title = f"{overall_emoji} <b>Order {overall_status}: {symbol} ({qty}) - {action}</b>"
        else:
            title = f"{overall_emoji} <b>Order {overall_status}</b>"
        
        # Execution mode description
        mode_desc = {
            "IMMEDIATE": "🟢 Executed immediately (market open)",
            "AMO": "🌙 AMO placed (executes at pre-market)",
            "QUEUED": "📋 Queued (will place when market opens)"
        }.get(execution_mode, f"⚙️ {execution_mode}")
        
        # Build orders section with prices and P&L
        orders_text = ""
        total_pnl = 0.0
        has_pnl = False
        
        for i, (leg, result) in enumerate(zip(legs, results), 1):
            status_emoji = {
                "success": "✅",
                "failed": "❌",
                "rejected": "⚠️"
            }.get(result.get("status", ""), "❓")
            
            is_buy = leg.get('transactionType', leg.get('transaction', '')) in ['B', 'BUY']
            action = "🟢 BUY" if is_buy else "🔴 SELL"
            symbol = leg.get('symbol', 'UNKNOWN')
            qty = int(leg.get('quantity', 0))
            exchange = leg.get('exchange', 'NSE').replace('_DLY', '')
            order_id = result.get('order_id', '')
            
            # Get price info
            leg_price = float(leg.get('price', 0)) if leg.get('price') else 0
            ltp = ltp_data.get(symbol, 0) if ltp_data else 0
            exit_price = leg_price if leg_price > 0 else ltp
            
            # Base order line with price
            price_str = f" @ ₹{exit_price:.2f}" if exit_price > 0 else ""
            orders_text += f"\n{status_emoji} {action} {qty} × <b>{symbol}</b>{price_str}"
            
            # For SELL orders: Show entry price, exit price, and P&L
            if not is_buy and result.get("status") == "success":
                entry_price = 0
                if holdings_data and symbol in holdings_data:
                    entry_price = holdings_data[symbol].get('avg_price', 0)
                
                if entry_price > 0 and exit_price > 0:
                    pnl = (exit_price - entry_price) * qty
                    pnl_pct = ((exit_price - entry_price) / entry_price) * 100
                    total_pnl += pnl
                    has_pnl = True
                    
                    pnl_emoji = "📈" if pnl >= 0 else "📉"
                    pnl_sign = "+" if pnl >= 0 else ""
                    
                    orders_text += f"\n   💰 Entry: ₹{entry_price:.2f} → Exit: ₹{exit_price:.2f}"
                    orders_text += f"\n   {pnl_emoji} P&L: <b>{pnl_sign}₹{pnl:,.2f}</b> ({pnl_sign}{pnl_pct:.1f}%)"
            
            # For BUY orders: Just show entry price
            elif is_buy and result.get("status") == "success" and exit_price > 0:
                orders_text += f"\n   💰 Entry Price: ₹{exit_price:.2f}"
            
            # Order ID or error message
            if order_id:
                orders_text += f"\n   📝 ID: <code>{order_id}</code>"
            elif result.get("status") == "rejected":
                orders_text += f"\n   ⚠️ {result.get('message', 'Rejected')}"
            elif result.get("status") == "failed":
                orders_text += f"\n   ❌ {result.get('message', 'Failed')}"
        
        # Build message
        message = f"""
{title}

⏰ {timestamp}
{mode_desc}

<b>Orders ({successful}/{total}):</b>{orders_text}
"""
        
        # Add total P&L summary for multi-sell or significant P&L
        if has_pnl:
            pnl_emoji = "📈" if total_pnl >= 0 else "📉"
            pnl_sign = "+" if total_pnl >= 0 else ""
            message += f"\n{pnl_emoji} <b>Total P&L: {pnl_sign}₹{total_pnl:,.2f}</b>"
        
        message += f"\n\n📊 Daily: {self._get_daily_summary()}"
        
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
