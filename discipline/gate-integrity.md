**Manual gate-integrity discipline (platforms without the Kuraka hook):**
run every gate command WITHOUT a pipe and assert on **its own** exit code
(e.g. run `make test-run`, then check `$?`). NEVER pipe the gate command
(`make ... | tail`, `... | head`, `... | grep`) — the shell reports the LAST
command's exit code (the pipe's), so a failing suite can read as green. If
output must be trimmed, redirect to a file and read the file; the gate still
reads the test command's own exit code. Evidence: REQ-20260611 S3 advanced on
a FALSE GREEN (`make ... | tail`) while the suite was failing at collection.
