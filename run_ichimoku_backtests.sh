#!/bin/bash
# Sequential Ichimoku backtests for different market cap and beta segments
# Each backtest will complete before the next one starts

set -e  # Exit on error

echo "========================================"
echo "Ichimoku Backtest Suite"
echo "Running 6 backtests sequentially"
echo "========================================"
echo ""

# Define the baskets to test
baskets=(
    "data/basket_largecap_lowbeta.txt"
    "data/basket_largecap_highbeta.txt"
    "data/basket_midcap_lowbeta.txt"
    "data/basket_midcap_highbeta.txt"
    "data/basket_smallcap_lowbeta.txt"
    "data/basket_smallcap_highbeta.txt"
)

basket_names=(
    "1. LargeCap LowBeta"
    "2. LargeCap HighBeta"
    "3. MidCap LowBeta"
    "4. MidCap HighBeta"
    "5. SmallCap LowBeta"
    "6. SmallCap HighBeta"
)

# Counter for completed backtests
completed=0
total=${#baskets[@]}

# Run each backtest
for i in "${!baskets[@]}"; do
    basket_file="${baskets[$i]}"
    basket_name="${basket_names[$i]}"
    
    echo ""
    echo "========================================"
    echo "Starting: ${basket_name}"
    echo "Basket: ${basket_file}"
    echo "Progress: $((completed))/${total} completed"
    echo "========================================"
    echo ""
    
    # Run the backtest
    python -m runners.run_basket \
        --basket_file "${basket_file}" \
        --strategy ichimoku \
        --interval 1d \
        --period max \
        --use_cache_only \
        --params '{}'
    
    # Check if backtest succeeded
    if [ $? -eq 0 ]; then
        ((completed++))
        echo ""
        echo "✅ Completed: ${basket_name}"
        echo "Progress: ${completed}/${total} completed"
        echo ""
    else
        echo ""
        echo "❌ Failed: ${basket_name}"
        echo "Stopping execution due to error"
        exit 1
    fi
    
    # Brief pause between backtests
    if [ $completed -lt $total ]; then
        echo "Waiting 2 seconds before next backtest..."
        sleep 2
    fi
done

echo ""
echo "========================================"
echo "✅ All Backtests Completed!"
echo "Total: ${completed}/${total} successful"
echo "========================================"
echo ""
echo "Results are saved in the reports/ directory"
