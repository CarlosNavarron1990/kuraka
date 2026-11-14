Truncate cases and task logs from the local database.

Run it from the repository root (or the backend workspace root declared in
`kuraka.config.yaml` → `architecture.paths.backend_root`), using the project's clean target:
```
make clean-cases
```

After running, confirm what was truncated.
