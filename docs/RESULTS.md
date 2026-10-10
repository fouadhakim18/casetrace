# Recorded results

Generated from `artifacts/evaluation.json` (2026-10-09T19:18:31.284887+00:00).

This is a development-used, synthetic smoke benchmark with one current attempt per condition. It does not establish general agent superiority. Older available development attempts remain in the raw JSON.

| Case | Mode | Status | Matched / extra / missed categories | Quote-valid findings | Calls | Chat tokens | Seconds |
|---|---|---|---|---|---:|---:|---:|
| 01_consistent | agents | completed | 0 / 0 / 0 | 3 / 3 | 3 | 6289 | 6.73 |
| 01_consistent | baseline | completed | 0 / 0 / 0 | 3 / 3 | 1 | 1906 | 3.8 |
| 01_consistent | offline | completed | 0 / 0 / 0 | 0 / 0 | 0 | 0 | 0.0 |
| 02_conflicting | agents | failed | — / — / — | — / — | — | — | 0.9 |
| 02_conflicting | baseline | completed | 3 / 0 / 0 | 4 / 4 | 1 | 2388 | 4.97 |
| 02_conflicting | offline | completed | 3 / 0 / 0 | 3 / 3 | 0 | 0 | 0.0 |
| 03_incomplete | baseline | failed | — / — / — | — / — | — | — | 0.7 |
| 03_incomplete | offline | completed | 1 / 0 / 0 | 1 / 1 | 0 | 0 | 0.0 |

## Recorded failures

- 02_conflicting/agents: Provider quota/rate limit reached (HTTP 429). Wait or check your free quota. Billing was not changed.
- 03_incomplete/baseline: Provider quota/rate limit reached (HTTP 429). Wait or check your free quota. Billing was not changed.

Retrieval Recall@3: 1.0 on 8 queries.

A denominator of zero means no findings, not proof of perfect accuracy. Quote-valid means that listed quotes match source text, not that every interpretation is correct. Category scoring excludes supported-only findings.

The clean dossier illustrates an audit/cost tradeoff: a verifier can confirm the same answer as a single-pass baseline while consuming more calls and tokens. This project does not claim a demonstrated accuracy gain.

Execution scope: Python unit/API tests and real Gemini calls were executed. Docker, remote GitHub Actions, local Ollama and public hosting have not been validated. Browser verification status is recorded separately in `artifacts/verification.json`.

Free-tier quota errors during development were retained where available. Calls are not silently replaced by offline outputs.
The agent experiment on 03_incomplete was not attempted after the quota stop. An older successful 02_conflicting agent run is retained in development_history and explicitly labelled historical in the recorded demo; it is not substituted for the failed current attempt in the table.
