#!/usr/bin/env python3
"""
Export Firestore webhook order logs to CSV

Uses gcloud auth token (no ADC required).
Prerequisite: gcloud auth login

Usage:
    python scripts/export_webhook_logs.py                    # Export last 100 logs
    python scripts/export_webhook_logs.py --limit 500        # Export last 500 logs
    python scripts/export_webhook_logs.py --output my_logs.csv  # Custom output file
    python scripts/export_webhook_logs.py --all              # Export all logs (up to 1000)
"""

import argparse
import csv
import json
import subprocess
import sys
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path


def get_access_token() -> str:
    """Get access token from gcloud CLI."""
    try:
        result = subprocess.run(
            ["gcloud", "auth", "print-access-token"],
            capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to get access token: {e}")
        print("   Run: gcloud auth login")
        sys.exit(1)
    except FileNotFoundError:
        print("❌ gcloud CLI not found. Install Google Cloud SDK first.")
        sys.exit(1)


def query_firestore(access_token: str, limit: int = 100) -> list:
    """Query Firestore using REST API."""
    url = "https://firestore.googleapis.com/v1/projects/tradingview-webhook-prod/databases/(default)/documents:runQuery"
    
    query = {
        "structuredQuery": {
            "from": [{"collectionId": "webhook_orders"}],
            "orderBy": [{"field": {"fieldPath": "timestamp"}, "direction": "DESCENDING"}],
            "limit": limit
        }
    }
    
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    req = urllib.request.Request(url, data=json.dumps(query).encode(), headers=headers)
    
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        print(f"❌ Firestore error: {e.code} - {e.read().decode()}")
        sys.exit(1)


def parse_firestore_value(value_dict: dict):
    """Parse Firestore value format to Python."""
    if not value_dict:
        return ""
    if "stringValue" in value_dict:
        return value_dict["stringValue"]
    elif "integerValue" in value_dict:
        return int(value_dict["integerValue"])
    elif "doubleValue" in value_dict:
        return value_dict["doubleValue"]
    elif "timestampValue" in value_dict:
        return value_dict["timestampValue"]
    elif "booleanValue" in value_dict:
        return value_dict["booleanValue"]
    elif "nullValue" in value_dict:
        return ""
    else:
        return str(value_dict)


def export_logs(limit: int = 100, output_path: str = None, export_all: bool = False):
    """Export Firestore webhook_orders to CSV."""
    # Default output path
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"webhook_logs_{timestamp}.csv"
    
    output_file = Path(output_path)
    
    print("🔄 Getting access token from gcloud...")
    access_token = get_access_token()
    
    print("📥 Fetching logs from Firestore...")
    
    # For export_all, use a large limit (Firestore REST API max is 1000 per query)
    fetch_limit = 1000 if export_all else limit
    
    results = query_firestore(access_token, fetch_limit)
    
    if not results or (len(results) == 1 and "document" not in results[0]):
        print("⚠️  No logs found in Firestore")
        return
    
    # Filter out empty results
    docs = [r for r in results if "document" in r]
    print(f"📊 Found {len(docs)} logs")
    
    # Define CSV columns
    columns = [
        'timestamp', 'strategy', 'symbol', 'transaction_type', 'quantity', 'price',
        'status', 'order_id', 'alert_type', 'exchange', 'product_type',
        'order_type', 'security_id', 'leg_number', 'message'
    ]
    
    # Write to CSV
    with open(output_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        
        for item in docs:
            fields = item["document"]["fields"]
            
            row = {}
            for col in columns:
                if col in fields:
                    row[col] = parse_firestore_value(fields[col])
                else:
                    row[col] = ""
            
            writer.writerow(row)
    
    print(f"✅ Exported {len(docs)} logs to: {output_file}")
    print(f"\n📋 Recent orders:")
    print("-" * 85)
    
    # Print summary of recent orders
    for item in docs[:10]:
        fields = item["document"]["fields"]
        ts = parse_firestore_value(fields.get("timestamp", {}))
        symbol = parse_firestore_value(fields.get("symbol", {}))
        txn = parse_firestore_value(fields.get("transaction_type", {}))
        qty = parse_firestore_value(fields.get("quantity", {}))
        price = parse_firestore_value(fields.get("price", {}))
        status = parse_firestore_value(fields.get("status", {}))
        
        txn_emoji = "🟢 BUY " if txn == "B" else "🔴 SELL"
        price_str = f"₹{float(price):>10,.2f}" if price else "      N/A"
        ts_str = str(ts)[:19] if ts else "N/A"
        print(f"{ts_str}  {txn_emoji}  {symbol:12} x{qty:<3}  @ {price_str}  [{status}]")
    
    if len(docs) > 10:
        print(f"... and {len(docs) - 10} more orders")


def main():
    parser = argparse.ArgumentParser(description="Export Firestore webhook logs to CSV")
    parser.add_argument("--limit", type=int, default=100, help="Max number of logs to export")
    parser.add_argument("--output", "-o", type=str, help="Output CSV file path")
    parser.add_argument("--all", action="store_true", help="Export all logs (up to 1000)")
    
    args = parser.parse_args()
    
    export_logs(
        limit=args.limit,
        output_path=args.output,
        export_all=args.all
    )


if __name__ == "__main__":
    main()
