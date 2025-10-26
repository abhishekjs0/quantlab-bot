import matplotlib.pyplot as plt
import pandas as pd


def plot_equity_and_dd(equity_df: pd.DataFrame, title="Equity & Drawdown"):
    eq = equity_df["equity"].astype(float)
    dd = eq / eq.cummax() - 1.0

    plt.figure(figsize=(10, 4))
    plt.plot(eq.index, eq.values)
    plt.title(f"{title} - Equity")
    plt.xlabel("Date")
    plt.ylabel("Equity")
    plt.tight_layout()
    plt.show()

    plt.figure(figsize=(10, 3))
    plt.plot(dd.index, dd.values)
    plt.title(f"{title} - Drawdown")
    plt.xlabel("Date")
    plt.ylabel("Drawdown")
    plt.tight_layout()
    plt.show()
