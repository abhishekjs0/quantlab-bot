#!/usr/bin/env python3
"""
Create comprehensive symbol mapping from CSV files and Dhan security master
"""

import logging
import os

import pandas as pd
from dhanhq import DhanContext, dhanhq

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_basket_symbols():
    """Load all symbols from basket CSV files"""
    from config import DATA_DIR

    all_symbols = {}

    basket_files = [
        "Large_2.5M Vol.csv",
        "Mega_5M Vol.csv",
        "Mid_500K Vol.csv",
        "Small_100K Vol.csv",
    ]

    for file in basket_files:
        file_path = DATA_DIR / file
        if file_path.exists():
            df = pd.read_csv(file_path)
            logger.info(f"Loading {len(df)} symbols from {file}")

            for _, row in df.iterrows():
                symbol = row["Symbol"]
                description = row["Description"]
                isin = row["ISIN"]

                all_symbols[symbol] = {
                    "description": description,
                    "isin": isin,
                    "basket": file.replace(".csv", ""),
                }
        else:
            logger.warning(f"File not found: {file}")

    logger.info(f"Total unique symbols loaded: {len(all_symbols)}")
    return all_symbols


def load_dhan_security_master():
    """Load Dhan security master"""
    from config import CACHE_DIR

    cache_file = CACHE_DIR / "api-scrip-master-detailed.parquet"

    if not cache_file.exists():
        logger.info("Fetching fresh security master from Dhan...")

        # Initialize Dhan client
        access_token = os.getenv("DHAN_ACCESS_TOKEN")
        client_id = os.getenv("DHAN_CLIENT_ID", "1000")

        if not access_token:
            raise ValueError("DHAN_ACCESS_TOKEN not found in environment")

        dhan_context = DhanContext(client_id, access_token)
        dhan = dhanhq(dhan_context)

        # Fetch security master
        securities = dhan.fetch_security_list(mode="detailed")
        df = pd.DataFrame(securities)

        # Cache it
        CACHE_DIR.mkdir(exist_ok=True)
        df.to_parquet(cache_file)
        logger.info(f"Cached {len(df)} securities to {cache_file}")
    else:
        logger.info(f"Loading cached security master from {cache_file}")
        df = pd.read_parquet(cache_file)

    # Filter to NSE equities only
    nse_equities = df[(df["EXCH_ID"] == "NSE") & (df["SEGMENT"] == "E")].copy()

    logger.info(f"Found {len(nse_equities)} NSE equity securities")
    return nse_equities


def create_symbol_mapping(basket_symbols, dhan_securities):
    """Create mapping from basket symbols to Dhan security IDs"""

    mapping = {}
    unmatched = []

    logger.info("Creating symbol mapping...")

    for symbol, info in basket_symbols.items():
        description = info["description"]
        isin = info["isin"]

        # Strategy 1: Match by ISIN (most reliable)
        isin_match = dhan_securities[dhan_securities["ISIN"] == isin]
        if not isin_match.empty:
            security_id = isin_match.iloc[0]["SECURITY_ID"]
            company_name = isin_match.iloc[0]["SYMBOL_NAME"]
            mapping[symbol] = {
                "security_id": security_id,
                "company_name": company_name,
                "description": description,
                "isin": isin,
                "match_method": "ISIN",
                "basket": info["basket"],
            }
            continue

        # Strategy 2: Match by partial company name
        description_words = description.upper().split()
        matches = dhan_securities[
            dhan_securities["SYMBOL_NAME"]
            .str.upper()
            .str.contains("|".join(description_words[:2]), na=False, regex=True)
        ]

        if len(matches) == 1:
            security_id = matches.iloc[0]["SECURITY_ID"]
            company_name = matches.iloc[0]["SYMBOL_NAME"]
            mapping[symbol] = {
                "security_id": security_id,
                "company_name": company_name,
                "description": description,
                "isin": isin,
                "match_method": "Name_Match",
                "basket": info["basket"],
            }
            continue

        # Strategy 3: Fuzzy match on symbol names (common variations)
        symbol_variations = [
            symbol,
            symbol.replace("&", "AND"),
            symbol.replace("LTD", ""),
            symbol.replace("BANK", "BK"),
            symbol + " LT",
            symbol + " LIMITED",
        ]

        for variation in symbol_variations:
            variation_matches = dhan_securities[
                dhan_securities["SYMBOL_NAME"]
                .str.upper()
                .str.contains(variation.upper(), na=False)
            ]
            if len(variation_matches) == 1:
                security_id = variation_matches.iloc[0]["SECURITY_ID"]
                company_name = variation_matches.iloc[0]["SYMBOL_NAME"]
                mapping[symbol] = {
                    "security_id": security_id,
                    "company_name": company_name,
                    "description": description,
                    "isin": isin,
                    "match_method": f"Symbol_Variation_{variation}",
                    "basket": info["basket"],
                }
                break
        else:
            # No match found
            unmatched.append(
                {
                    "symbol": symbol,
                    "description": description,
                    "isin": isin,
                    "basket": info["basket"],
                }
            )

    logger.info(f"Successfully mapped {len(mapping)} symbols")
    logger.info(f"Failed to map {len(unmatched)} symbols")

    return mapping, unmatched


def save_mapping_results(mapping, unmatched):
    """Save mapping results to files"""

    from config import DATA_DIR

    # Save successful mappings
    mapping_df = pd.DataFrame.from_dict(mapping, orient="index")
    mapping_df.index.name = "symbol"
    mapping_file = DATA_DIR / "dhan_symbol_mapping.csv"
    mapping_df.to_csv(mapping_file)
    logger.info(f"Saved {len(mapping_df)} mappings to {mapping_file}")

    # Save unmatched symbols
    if unmatched:
        unmatched_df = pd.DataFrame(unmatched)
        unmatched_file = DATA_DIR / "dhan_unmatched_symbols.csv"
        unmatched_df.to_csv(unmatched_file, index=False)
        logger.info(f"Saved {len(unmatched_df)} unmatched symbols to {unmatched_file}")

    # Print summary
    print("\n📊 SYMBOL MAPPING SUMMARY:")
    print(f"✅ Successfully mapped: {len(mapping)} symbols")
    print(f"❌ Failed to map: {len(unmatched)} symbols")
    print(f"📈 Success rate: {len(mapping)/(len(mapping)+len(unmatched))*100:.1f}%")

    if mapping:
        print(f"\n📝 Mapping file: {mapping_file}")
        print("🔗 Sample mappings:")
        for _i, (symbol, info) in enumerate(list(mapping.items())[:5]):
            print(f"  {symbol} → {info['company_name']} (ID: {info['security_id']})")

    if unmatched:
        print(f"\n❌ Unmatched file: {unmatched_file}")
        print("🔍 Unmatched symbols (first 5):")
        for symbol_info in unmatched[:5]:
            print(f"  {symbol_info['symbol']} - {symbol_info['description']}")


def main():
    """Main function"""
    try:
        # Load basket symbols
        basket_symbols = load_basket_symbols()

        # Load Dhan security master
        dhan_securities = load_dhan_security_master()

        # Create mapping
        mapping, unmatched = create_symbol_mapping(basket_symbols, dhan_securities)

        # Save results
        save_mapping_results(mapping, unmatched)

    except Exception as e:
        logger.error(f"Error creating symbol mapping: {e}")
        raise


if __name__ == "__main__":
    main()
