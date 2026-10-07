# Evaluation report

## PFE 1 - MORL metrics (IC higher, HV higher, SP lower, EU lower)

| benchmark | noise_budget | n_runs | IC | HV | SP | EU | Tmin | Tmax | Kmax | bounds_source | values_clipped |
|---|---|---|---|---|---|---|---|---|---|---|---|
| dot_product_4 | 240 | 2 | 1 | 0.6785 | 0.0 | 0.1813 | 215 | 1756 | 3 | manuscript Table 5.2 | False |
| dot_product_4 | 300 | 2 | 1 | 0.6785 | 0.0 | 0.1813 | 215 | 1756 | 3 | manuscript Table 5.2 | False |
| dot_product_4 | 1000000 | 2 | 1 | 0.6785 | 0.0 | 0.1813 | 215 | 1756 | 3 | manuscript Table 5.2 | False |

## PFE 1 - Compiler metrics at extreme preferences

| benchmark | noise_budget | preference | w_ops | w_keys | execution_time_s | total_time_s | rotation_key_size_MB | rotation_keys |
|---|---|---|---|---|---|---|---|---|
| dot_product_4 | 240 | speed (max w_ops) | 1.0 | 0.0 | 1.161 | 1.446 | 18.1967 | 1 |
| dot_product_4 | 240 | memory (max w_keys) | 0.5 | 0.5 | 0.636 | 0.875 | 18.1967 | 1 |
| dot_product_4 | 300 | speed (max w_ops) | 1.0 | 0.0 | 0.722 | 0.902 | 18.1967 | 1 |
| dot_product_4 | 300 | memory (max w_keys) | 0.5 | 0.5 | 0.705 | 0.863 | 18.1967 | 1 |
| dot_product_4 | 1000000 | speed (max w_ops) | 1.0 | 0.0 | 0.642 | 0.816 | 18.1967 | 1 |
| dot_product_4 | 1000000 | memory (max w_keys) | 0.5 | 0.5 | 0.752 | 0.941 | 18.1967 | 1 |

## PFE 2 - Constrained agent (CR%, violations, safe metrics)

| agent | noise_budget | n | safe_violations | safe_viol_rate_% | safe_CR_% | violations | viol_rate_% | CR_% | rollback_rate_% | measured_violations | within_budget | above_budget | safe_violations_within | safe_viol_rate_%_within | safe_CR_%_within | violations_within | viol_rate_%_within | CR_%_within | rollback_rate_%_within | measured_violations_within |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| unified | 240 | 1 | 0 | 0.0 | 85.19 | 0 | 0.0 | 85.19 | 0.0 | 0 | 1 | 0 | 0 | 0.0 | 85.19 | 0 | 0.0 | 85.19 | 0.0 | 0 |
| unified | 300 | 1 | 0 | 0.0 | 85.19 | 0 | 0.0 | 85.19 | 0.0 | 0 | 1 | 0 | 0 | 0.0 | 85.19 | 0 | 0.0 | 85.19 | 0.0 | 0 |
| unified | 1000000 | 1 | 0 | 0.0 | 85.19 | 0 | 0.0 | 85.19 | 0.0 | 0 | 1 | 0 | 0 | 0.0 | 85.19 | 0 | 0.0 | 85.19 | 0.0 | 0 |

## PFE 2 - Noise estimator accuracy (estimated vs measured)

| n | MAE | MSE | RMSE | R2 | mean_signed_error(est-measured) |
|---|---|---|---|---|---|
| 6.0 | 0.597 | 0.495 | 0.703 | -2.5633 | -0.597 |

