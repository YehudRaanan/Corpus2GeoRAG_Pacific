# 100-page pilot: GPU available, training active

Checked 29 October 2026 at 07:39 Asia/Jerusalem (UTC+02).
This supersedes the GPU-blocked status in the previous checkpoint.
The full pilot is not complete.

- Four new start attempts failed with L4 capacity errors. The fifth succeeded.
- The original VM `geoai-luke-pilot-20261028` is running in `us-central1-c`.
  No temporary VM, snapshot or copied disk was created.
- New GPU runtime began at 05:27:14.838 UTC. Automatic STOP is configured for
  six hours, at 13:27:14.838 Asia/Jerusalem. Automatic restart is disabled.
- CUDA and the L4 were verified. The uploaded V2 bundle SHA256 matches the
  local manifest. The saved 100-page data was reused without regeneration.
- The real-optimizer benchmark passed with 81 alternatives and peak allocated
  GPU memory of 3,379,803,136 bytes. Whole-pool throughput gives about 145 minutes
  for the two full training epochs, before validation and other overhead.
- Training PID 1498 runs in `/home/User/hundred-page-pilot`, using the existing
  `/home/User/luke-pilot-venv` and cached LUKE weights. Output is
  `outputs/train_20261029`. Command limits training to four hours, two encoder
  epochs and checkpoints every 500 encoder optimizer steps.
- The frozen head met the stability rule after 11 validation observations.
  Its validation selection accuracy was 47.3% and synthetic stop precision
  was 52.0%, below the pilot targets. These are not final results.
- Encoder tuning was verified at 25 optimizer steps, 200/5,060 states in the
  first epoch. No memory error was reported; GPU use was 99%.

Pending: complete encoder tuning and held-out diagnostics; select the final
checkpoint; run the saved 12,342 matching jobs; export and verify the original
40,070 rows; download results; stop the VM and report actual runtime and cost.
The US$10 budget and six-hour aggregate GPU limit remain unchanged. Forecasts
are not an invoice or a billing-account cap. Active work time is unmeasured.

Local evidence: `Data/external/hundred_page_pilot_20261028/benchmark_20261029/`,
`vm_started_20261029.json`, `pilot_status.json` and `runtime_cost_ledger.jsonl`.
Backup: **Local checkpoint only**. No push was made. The pre-existing change
to `luke_pilot/evaluate.py` remains unstaged and unchanged.
