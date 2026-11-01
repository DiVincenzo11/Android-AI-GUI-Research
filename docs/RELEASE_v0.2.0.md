# v0.2.0 — Live real-app experiments

- Added fresh GUI interaction and output evidence for PocketPal 1.20.0,
  ChatterUI 0.10.1 and DuckDuckGo 5.300.0 / Duck.ai. Two local apps use the same
  pinned Qwen GGUF; Duck.ai is a separate network-service case.
- All three selected final adapters observed a new nonce-bearing response twice,
  with assistant-container/role checks, screenshots, UI trees, OCR and recordings.
- Preserved all 16 development/verification attempts, including failures and the
  emulator interruption. One interrupted attempt has no completed recording.
- Added exact multi-step adapters, bounded UI-tree retries, an optional pinned
  UIAutomator2 backend, scenario snapshots, stable-response checks and safe
  Windows console JSON. App launch uses resolved activities rather than Monkey.
- 22 offline tests pass, including regressions against the actual captured UI
  trees. Evidence hashes and all available recordings were verified/decoded.

The apps and adapters were selected and tuned during development. These are
inspectable real-run cases, not a held-out benchmark, first-attempt success rate,
semantic-model evaluation, or ScenGen reproduction. Model weights and third-party
APKs are not redistributed. See docs/REAL_APPS.md for exact preparation steps.
