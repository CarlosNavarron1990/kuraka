Run the project's full test suite.

Run it from the repository root (or the backend workspace root declared in
`kuraka.config.yaml` → `architecture.paths.backend_root`), using the project's configured
`test_cmd` (`kuraka.config.yaml` → `stack.backend.test_cmd`; e.g. `make test`):
```
<test_cmd> > test-run.log 2>&1; echo $? > test-run.exit
```

Never pipe the test command — the gate is its own exit code (rule 17 T7).

Report the results: exit code, how many passed, failed, and any errors.
