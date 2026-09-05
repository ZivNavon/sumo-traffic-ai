@echo off
echo ============================================================
echo  Multi-seed evaluation on test seeds 201-205
echo  Uses _ms weights (trained on seeds 1-20)
echo  TIMER and SCRIPT are seed-agnostic (no weights needed)
echo ============================================================
cd /d "D:\Ziv - OS\Projects\Trafic AI"
py sim/eval_multiseed.py
echo.
echo Done. Results saved to sim/results/multiseed_summary.json
echo and sim/results/RESULTS_MULTISEED.md
pause
