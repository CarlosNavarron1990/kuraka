**Manual telemetry capture (platforms without the Kuraka PostToolUse hook):**
write the telemetry entry IMMEDIATELY after each agent invocation — not at the
end of the phase, not "later". An invocation with no entry is invisible to the
audit and the cycle's reported cost is then wrong, not merely imprecise
(REQ-20260801 recorded 19 of 31 runs; reconstructing the missing 12 moved the
cycle from a reported 3.76M to an actual 5.90M tokens). If the platform does
not expose usage metrics, record `null` / `"unknown"` — never fabricate `0`.
