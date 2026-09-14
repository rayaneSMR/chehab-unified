import pandas as pd

pd.set_option('display.max_columns', None)
pd.set_option('display.width', 1000)

try:
    df_a = pd.read_excel("./results_dnn_film_a.xlsx")
    df_b = pd.read_excel("./results_dnn_film_b.xlsx")

    metrics = [
        "Initial Keys",
        "Safe Final Keys",
        "Safe Cost Reduction (%)",
        "Agent Violated",
        "Safety Activated",
        "RL Time (ms)"
    ]

    summary_a = df_a.groupby("Budget")[metrics].mean().add_prefix("FiLM-A ")
    summary_b = df_b.groupby("Budget")[metrics].mean().add_prefix("FiLM-B ")

    comparison = pd.concat([summary_a, summary_b], axis=1)

    print("\n=== UNIFIED DNN BENCHMARKS: MELZI + MOKRANE METRICS ===")
    print(comparison)

except FileNotFoundError as e:
    print(f"File not found: {e}. Run the evaluation commands first.")