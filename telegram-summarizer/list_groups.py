"""
List all Telegram groups/chats you're a member of.
Run this to find group IDs for the summarizer.
"""
import asyncio
import os
from dotenv import load_dotenv
from pyrogram import Client

load_dotenv()

API_ID = os.getenv("TELEGRAM_API_ID")
API_HASH = os.getenv("TELEGRAM_API_HASH")

# Your phone number with country code (no spaces, no dashes)
PHONE_NUMBER = "+919624973000"  # Change this to your number


async def list_groups():
    print("\n🔐 Connecting to Telegram...")
    print("   (Check your Telegram app for OTP)\n")
    
    async with Client(
        "telegram_summarizer",
        api_id=API_ID,
        api_hash=API_HASH,
        phone_number=PHONE_NUMBER,
        workdir=os.path.dirname(os.path.abspath(__file__)),
    ) as client:
        me = await client.get_me()
        print(f"✅ Logged in as: {me.first_name} (@{me.username})\n")
        
        print("=" * 60)
        print("YOUR GROUPS & CHANNELS")
        print("=" * 60)
        
        from pyrogram.enums import ChatType
        
        groups = []
        count = 0
        async for dialog in client.get_dialogs(limit=500):
            count += 1
            chat = dialog.chat
            if chat.type in [ChatType.GROUP, ChatType.SUPERGROUP, ChatType.CHANNEL]:
                groups.append({
                    "id": chat.id,
                    "title": chat.title or "Unknown",
                    "type": str(chat.type).split(".")[-1],
                    "members": getattr(chat, "members_count", "?"),
                })
        
        print(f"\n(Scanned {count} dialogs)")
        
        # Sort by title
        groups.sort(key=lambda x: x["title"].lower())
        
        for g in groups:
            print(f"\n📱 {g['title']}")
            print(f"   ID: {g['id']}")
            print(f"   Type: {g['type']} | Members: {g['members']}")
        
        print("\n" + "=" * 60)
        print(f"Total: {len(groups)} groups/channels")
        print("=" * 60)
        
        print("\n📋 Copy the IDs you want to monitor and add them to .env:")
        print("   TELEGRAM_GROUPS=-1001234567890,-1009876543210")


if __name__ == "__main__":
    asyncio.run(list_groups())
