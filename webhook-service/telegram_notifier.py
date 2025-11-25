#!/usr/bin/env python3
"""
Telegram Notification Module
Sends notifications for TradingView alerts and Dhan order executions
"""

import os
import logging
import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional, Dict, Any
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
        
        if not self.enabled:
            logger.warning("⚠️  Telegram notifications disabled (missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID)")
        else:
            logger.info(f"✅ Telegram notifications enabled for chat {self.chat_id}")
    
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
    
    async def notify_alert_received(
        self, 
        alert_type: str, 
        num_legs: int, 
        source_ip: str,
        legs_summary: list[Dict[str, Any]]
    ) -> bool:
        """
        Notify that a TradingView alert was received
        
        Args:
            alert_type: Type of alert (e.g., "multi_leg_order")
            num_legs: Number of order legs
            source_ip: IP address of the alert source
            legs_summary: List of dicts with leg details
            
        Returns:
            True if sent successfully
        """
        if not self.enabled:
            return False
        
        timestamp = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST")
        
        # Build legs summary
        legs_text = ""
        for i, leg in enumerate(legs_summary, 1):
            action = "🟢 BUY" if leg['transaction'] in ['B', 'BUY'] else "🔴 SELL"
            legs_text += f"\n  {i}. {action} {leg['quantity']} × <b>{leg['symbol']}</b> @ {leg['exchange']}"
            legs_text += f"\n     {leg['order_type']} | {leg['product_type']}"
        
        message = f"""
📊 <b>TradingView Alert Received</b>

⏰ Time: {timestamp}
📋 Type: {alert_type}
🔢 Legs: {num_legs}
🌐 Source: {source_ip}

<b>Orders:</b>{legs_text}

⚙️ Processing orders...
"""
        
        return await self.send_message(message.strip())
    
    async def notify_order_result(
        self,
        leg_number: int,
        total_legs: int,
        symbol: str,
        exchange: str,
        transaction: str,
        quantity: int,
        status: str,
        message: str,
        order_id: Optional[str] = None,
        validation_details: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Notify about order execution result from Dhan
        
        Args:
            leg_number: Current leg number
            total_legs: Total number of legs
            symbol: Trading symbol
            exchange: Exchange name
            transaction: B/BUY or S/SELL
            quantity: Order quantity
            status: success, failed, rejected, error
            message: Result message
            order_id: Dhan order ID (if successful)
            validation_details: SELL validation details (if rejected)
            
        Returns:
            True if sent successfully
        """
        if not self.enabled:
            return False
        
        timestamp = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST")
        
        # Status emoji
        status_emoji = {
            "success": "✅",
            "failed": "❌",
            "rejected": "⚠️",
            "error": "🚫"
        }.get(status, "❓")
        
        # Transaction type
        action = "🟢 BUY" if transaction in ['B', 'BUY'] else "🔴 SELL"
        
        # Build message
        msg_text = f"""
{status_emoji} <b>Order {status.upper()}</b>

⏰ Time: {timestamp}
📊 Leg: {leg_number}/{total_legs}
{action} {quantity} × <b>{symbol}</b> @ {exchange}
"""
        
        if status == "success" and order_id:
            msg_text += f"\n✅ Order ID: <code>{order_id}</code>"
            msg_text += f"\n🌙 AMO: Executes at market open"
        elif status == "rejected" and validation_details:
            msg_text += f"\n\n<b>Validation Failed:</b>"
            msg_text += f"\n• Reason: {validation_details.get('reason', 'Unknown')}"
            msg_text += f"\n• Available: {validation_details.get('available_quantity', 0)}"
            msg_text += f"\n• Required: {validation_details.get('required_quantity', 0)}"
            msg_text += f"\n• Source: {validation_details.get('source', 'unknown')}"
        else:
            msg_text += f"\n\n<b>Message:</b> {message}"
        
        return await self.send_message(msg_text.strip())
    
    async def notify_batch_summary(
        self,
        alert_type: str,
        total_legs: int,
        successful: int,
        failed: int,
        rejected: int
    ) -> bool:
        """
        Send summary notification after processing all legs
        
        Args:
            alert_type: Alert type
            total_legs: Total order legs processed
            successful: Number of successful orders
            failed: Number of failed orders
            rejected: Number of rejected orders
            
        Returns:
            True if sent successfully
        """
        if not self.enabled:
            return False
        
        timestamp = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST")
        
        # Overall status
        if failed > 0 or rejected > 0:
            overall = "⚠️ PARTIAL SUCCESS" if successful > 0 else "❌ FAILED"
        else:
            overall = "✅ SUCCESS"
        
        message = f"""
📈 <b>Alert Processing Complete</b>

⏰ Time: {timestamp}
📋 Type: {alert_type}
{overall}

<b>Results:</b>
• ✅ Successful: {successful}/{total_legs}
• ❌ Failed: {failed}/{total_legs}
• ⚠️ Rejected: {rejected}/{total_legs}
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

⏰ Time: {timestamp}
❌ Type: {error_type}

<b>Details:</b>
{details}
"""
        
        return await self.send_message(message.strip())


# Singleton instance
_notifier: Optional[TelegramNotifier] = None


def get_notifier() -> TelegramNotifier:
    """Get or create Telegram notifier singleton"""
    global _notifier
    if _notifier is None:
        _notifier = TelegramNotifier()
    return _notifier
