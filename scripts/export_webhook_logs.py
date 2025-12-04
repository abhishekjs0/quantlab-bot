#!/usr/bin/env python3
"""
Export Firestore webhook order logs to CSV

Usage:
    python scripts/export_webhook_logs.py                    # Export last 100 logs
    python scripts/export_webhook_logs.py --limit 500        # Export last 500 logs
    python scripts/export_webhook_logs.py --output my_logs.csv  # Custom output file
    python scripts/export_webhook_logs.py --all              # Export all logs
"""

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path

# Add webhook-service to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "webhook-service"))

try:
    from google.cloud import firestore
    FIRESTORE_AVAILABLE = True
except ImportError:
    FIRESTORE_AVAILABLE = False
    print("❌ google-cloud-firestore not installed. Run: pip install google-cloud-firestore")
    sys.exit(1)


def export_logs(limit: int = 100, output_path: str = None, export_all: bool = False):
    """
    Export Firestore webhook_orders to CSV
    
    Args:
        limit: Max number of logs to export (ignored if export_all=True)
        output_path: Output CSV file path
        export_all: If True, export all logs
    """
    # Default output path
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"data/webhook_logs_{timestamp}.csv"
    
    # Ensure output directory exists
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"🔄 Connecting to Firestore...")
    
    try:
        db = firestore.Client(project="tradingview-webhook-prod")
        collection = db.collection("webhook_orders")
        
        # Build query
        query = collection.order_by("timestamp", direction=firestore.Query.DESCENDING)
        if not export_all:
            query = query.limit(limit)
        
        print(f"📥 Fetching logs from Firestore...")
        docs = list(query.stream())
        
        if not docs:
            print("⚠️  No logs found in Firestore")
            return
        
        print(f"📊 Found {len(docs)} logs")
        
        # Define CSV columns
        columns = [
            'timestamp', 'alert_type', 'leg_number', 'symbol', 'exchange',
            'transaction_type', 'quantity', 'order_type', 'product_type',
            'price', 'status', 'message', 'order_id', 'security_id', 'source_ip'
        ]
        
        # Write to CSV
        with open(output_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=columns)
            writer.writeheader()
            
            for doc in docs:
                data = doc.to_dict()
                
                # Format timestamp
                ts = data.get('timestamp')
                if hasattr(ts, 'isoformat'):
                    ts = ts.isoformat()
                
                row = {
                    'timestamp': ts,
                    'alert_type': data.get('alert_type', ''),
                    'leg_number': data.get('leg_number', ''),
                    'symbol': data.get('symbol', ''),
                    'exchange': data.get('exchange', ''),
                    'transaction_type': data.get('transaction_type', ''),
                    'quantity': data.get('quantity', ''),
                    'order_type': data.get('order_type', ''),
                    'product_type': data.get('product_type', ''),
                    'price': data.get('price', ''),
                    'status': data.get('status', ''),
                    'message': data.get('message', ''),
                    'order_id': data.get('order_id', ''),
                    'security_id': data.get('security_id', ''),
                    'source_ip': data.get('source_ip', '')
                }
                writer.writerow(row)
        
        print(f"✅ Exported {len(docs)} logs to: {output_file}")
        print(f"   Open with: open {output_file}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Export Firestore webhook logs to CSV")
    parser.add_argument("--limit", type=int, default=100, help="Max number of logs to export")
    parser.add_argument("--output", "-o", type=str, help="Output CSV file path")
    parser.add_argument("--all", action="store_true", help="Export all logs (no limit)")
    
    args = parser.parse_args()
    
    export_logs(
        limit=args.limit,
        output_path=args.output,
        export_all=args.all
    )


if __name__ == "__main__":
    main()
