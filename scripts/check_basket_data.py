"""
Check basket symbols for local Dhan CSV availability and candidate SECURITY_ID mapping.
Prints a small report listing:
 - symbols with local CSV available
 - symbols mapped but CSV missing
 - symbols unmapped (candidate SECIDs from instrument master if found)
"""

import json
import os

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(__file__))
BASKET = os.path.join(ROOT, "data", "basket.txt")
MAPPING = os.path.join(ROOT, "reports", "basket_mapping_refined.json")
INST_CSV = os.path.join(ROOT, "data", "api-scrip-master-detailed.csv")

with open(BASKET) as f:
    syms = [ln.strip() for ln in f if ln.strip()]

mapping = {}
if os.path.exists(MAPPING):
    mapping = json.loads(open(MAPPING).read())

inst_df = None
if os.path.exists(INST_CSV):
    inst_df = pd.read_csv(INST_CSV)

have_local = []
mapped_missing = []
unmapped = []

for s in syms:
    recs = mapping.get(s)
    if recs:
        sec = recs[0].get("SECURITY_ID")
        csvp = os.path.join(ROOT, "data", f"dhan_historical_{sec}.csv")
        if os.path.exists(csvp):
            have_local.append((s, sec, csvp))
        else:
            mapped_missing.append((s, sec, csvp))
    else:
        # try to find in inst_df
        base = s.replace("NSE:", "").replace(".NS", "").split(".")[0]
        found = []
        if inst_df is not None:
            cand = inst_df[
                (inst_df.get("SYMBOL_NAME") == base)
                | (inst_df.get("UNDERLYING_SYMBOL") == base)
            ]
            if not cand.empty:
                try:
                    ids = [int(x) for x in cand["SECURITY_ID"].tolist()]
                except Exception:
                    ids = [int(cand.iloc[0]["SECURITY_ID"])]
                for cid in ids:
                    csvp = os.path.join(ROOT, "data", f"dhan_historical_{cid}.csv")
                    found.append((cid, os.path.exists(csvp), csvp))
        if found:
            unmapped.append((s, found))
        else:
            unmapped.append((s, []))

print("Summary for basket: total symbols=", len(syms))
print(f"\nHave local CSVs (count={len(have_local)}):")
for s, sec, p in have_local[:50]:
    print("  ", s, "SECID=", sec, "file=", p)

print(f"\nMapped but CSV missing (count={len(mapped_missing)}):")
for s, sec, p in mapped_missing[:50]:
    print("  ", s, "SECID=", sec, "expected file=", p)

print(f"\nUnmapped or candidate SECIDs (count={len(unmapped)}):")
for s, cand in unmapped[:50]:
    if not cand:
        print("  ", s, "-> NO mapping found in refined map or instrument CSV")
    else:
        print("  ", s, "-> candidate SECIDs:")
        for cid, exists, path in cand:
            print("      ", cid, "csv_exists=", exists, "path=", path)

# exit with status 0
print("\nDone")
