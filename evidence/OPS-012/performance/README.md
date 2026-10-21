# OPS-012 baseline diagnostic

Existing main a4f127a was profiled read-only before this implementation. Instrumented total41.761s, safe_load914calls/24.980s; target load_yaml_text652calls/18.139s. See baseline-history-profile.json for actual argv and unchanged before/after. This is a baseline diagnostic, not a current-code speedup or hosted CI result. Current code must complete full hosted CI under the unchanged30-minute cap.
