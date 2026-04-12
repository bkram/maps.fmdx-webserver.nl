# AGENTS.md

This repository hosts the Flask-based FMDX statistics web app. Keep changes
small, reviewable, and aligned with the current deployment model.

## Guardrails

- Do not reintroduce local dataset mode. The app is remote-only and must load
  receiver data from `REMOTE_API_URL`.
- Preserve the public routes `/`, `/statistics`, `/api/servers`, and
  `/api/stats` unless the task explicitly requires an API change.
- Do not commit generated files such as `__pycache__/`, coverage output, lint
  caches, or temporary datasets.
- Keep Docker/runtime dependencies separate from development tooling. Add test
  and lint tools to `requirements-dev.txt`, not `requirements.txt`.
- Prefer focused changes over broad cleanup. Do not rewrite unrelated modules
  while addressing a narrow task.
- Avoid adding network-dependent tests. Unit tests should stub remote API calls.
- When changing statistics behavior, preserve blacklist handling and scoped
  filtering semantics unless the task explicitly changes them.

## Required Checks

Run these before handing work over:

```bash
python3 -m pytest
python3 -m pylint fmdx_statistics tests
python3 -m vulture fmdx_statistics tests
```

If a check cannot be run, say so explicitly and explain why.

## Testing Notes

- Use `fmdx_statistics.cache.InMemoryCache` in tests instead of depending on
  Redis.
- Mock `requests.get` for app-level tests so test results are deterministic.
- Keep test fixtures local to the test module unless they are reused.
