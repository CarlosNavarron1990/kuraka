**Manual protocol if the constraint is violated (platforms without the Kuraka
guard hook):**

1. Revert the change.
2. Announce the violation to the user.
3. Route through the correct agent.
4. Log the bypass in telemetry with `"agent": "orchestrator-direct"`.

This constraint was added after retros where the bypass produced type errors
and broken telemetry.
