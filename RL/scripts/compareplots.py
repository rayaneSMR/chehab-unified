import pandas as pd

pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', None)
pd.set_option('display.width', 1000)

df_b = pd.read_excel("./results_dnn_film_b.xlsx")

print("=== ALL RECORDED METRICS IN DATASET ===")
print(list(df_b.columns))

print("\n=== COMPREHENSIVE MULTI-OBJECTIVE SUMMARY (FiLM-B) ===")
# Print mean of ALL numeric metrics grouped by Budget
print(df_b.groupby("Budget").mean(numeric_only=True).T)