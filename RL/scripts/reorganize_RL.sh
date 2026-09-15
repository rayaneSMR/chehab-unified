#!/bin/bash
# Run from ~/chehab-unified/RL (on branch `maroua`, conda env `chehabEnv`)
# Review with `git status` / `git diff --stat` before committing.
set -e

# 1. Delete real junk (0-byte accidental files)
rm -f './0' './1.0' './14818.0,' './[rotate_32,'

# 2. New folders
mkdir -p scripts models results/plots logs

# 3. Move analysis/debug scripts
git mv check_dataset_size.py scripts/ 2>/dev/null || mv check_dataset_size.py scripts/
git mv check_matches.py scripts/       2>/dev/null || mv check_matches.py scripts/
git mv clean.py scripts/               2>/dev/null || mv clean.py scripts/
git mv compare.py scripts/             2>/dev/null || mv compare.py scripts/
git mv compareplots.py scripts/        2>/dev/null || mv compareplots.py scripts/
git mv diagnose_rotations2.py scripts/ 2>/dev/null || mv diagnose_rotations2.py scripts/
git mv script.py scripts/              2>/dev/null || mv script.py scripts/
git mv unified_full_report.py scripts/ 2>/dev/null || mv unified_full_report.py scripts/

# 4. Move the correct, final trained model (post-fix, kept from your own
#    Sep 13 cleanup commit "where i stopped") — do NOT delete this one.
git mv model_jobid_lagrangian_od_ov_film_b.zip models/ 2>/dev/null || mv model_jobid_lagrangian_od_ov_film_b.zip models/

# 5. Remove STALE checkpoints only — early mid-training snapshots superseded
#    by the final model above, and the legacy pre-merge run that's
#    architecturally incompatible with the current merged policy code anyway.
rm -rf checkpoints/model_jobid_lagrangian_od_ov_film_b   # 40k/80k snapshots, superseded
rm -rf checkpoints/model_14388982                        # legacy pre-merge, incompatible
rm -rf eval/best_model_model_14388982                    # tied to the same legacy checkpoint

# 5. Consolidate results
for f in results_film_a.xlsx results_film_b.xlsx results_dnn_film_a.xlsx results_dnn_film_b.xlsx \
         results_rotations_film_a.xlsx results_rotations_film_b.xlsx results_scalar_film_b.xlsx \
         results_film_a_multibudget.xlsx results_film_b_multibudget.xlsx \
         midtrain_check_film_a_50k.xlsx midtrain_rotations_film_a_40k.xlsx job_logs.xlsx; do
  [ -f "$f" ] && (git mv "$f" results/ 2>/dev/null || mv "$f" results/)
done
[ -f film_comparison_plots.png ] && (git mv film_comparison_plots.png results/plots/ 2>/dev/null || mv film_comparison_plots.png results/plots/)

# Fold existing test_results/ in as a subfolder (keeps its own history)
[ -d test_results ] && git mv test_results results/test_results 2>/dev/null || mv test_results results/test_results

# 6. Logs
[ -f smoke.log ] && (git mv smoke.log logs/ 2>/dev/null || mv smoke.log logs/)

echo "Done. Run: git status   (review)   then commit."
echo "models/model_jobid_lagrangian_od_ov_film_b.zip is your kept, correct, post-fix model."
echo "Stale checkpoints (40k/80k snapshots + legacy model_14388982) were removed."