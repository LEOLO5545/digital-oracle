# Digital Oracle

A local financial research workbench that turns scattered market signals into layered, traceable analysis. Ask a probability, numeric forecast, or directional question; inspect the evidence, assumptions, counterarguments, and report behind the answer.

This fork adds a web application and a bounded multi-agent Codex workflow to [komako-workshop/digital-oracle](https://github.com/komako-workshop/digital-oracle). The interface and generated research currently use Traditional Chinese; this introduction is in English.

## Features

- Question planning and topic-specific core financial signals.
- Parallel data collection, caching, explicit failures, and anomaly promotion.
- Layered evidence tables and deterministic cross-market statistics.
- A headline answer, scenarios, counterevidence, and monitoring thresholds.
- Three parallel Codex research roles: direct evidence, cross-market interpretation, and counterarguments. A synthesis model combines their findings with the original evidence, followed by review and at most one revision.
- Draft reports, progress tracking, saved checkpoints, cancellation, and report recovery.
- Local research history, evidence inspection, resource checks, JSON downloads, and PDF export.
- Hong Kong adapters for official housing and unemployment baselines, HKMA monetary data, and southbound trading data, alongside the upstream financial providers.

## How analysis works

```text
Question → signal plan → parallel data collection → calculated statistics
    → direct-evidence / cross-market / counterargument agents
    → synthesis + layered report → draft → review and revision → final report
```

Agents share one evidence snapshot. Agreement between agents is not independent evidence, and their estimates are not averaged as votes. Prices and statistical observations are calculated in code; subjective adjustments are disclosed. Multi-agent analysis uses additional Codex quota and is not a guarantee of better accuracy or shorter latency.

## Local setup

Requirements: Python 3.10+, an installed and authenticated Codex CLI, and an internet connection for providers. macOS is the primary tested environment. Each user supplies their own Codex login; no account credentials are included.

From the repository root:

```sh
python3 -m venv work/oracle-venv
work/oracle-venv/bin/python -m pip install certifi yfinance -r outputs/oracle-local/requirements-local.txt
cd outputs/oracle-local
../../work/oracle-venv/bin/python server.py
```

Open **http://127.0.0.1:8765**. Start only one server on that port. The preserved directory layout is intentional: the application imports the locally adapted provider library in `work/digital-oracle`.

The server listens only on loopback. Publishing this repository does **not** deploy a hosted website. Do not expose the local server through a public tunnel or treat its page token as owner authentication. An internet deployment needs separate authentication, authorization, protected credentials, and a durable analysis backend.

### Optional provider configuration

Most enabled sources do not require a paid subscription. Availability, geography, limits, and data freshness vary. SEC requests require your own contact identification; CoinGecko is optional and has a key-based configuration. CoinLore offers a keyless crypto adapter. CME remains disabled in the local application.

Store any personal configuration locally, outside tracked source files. Never commit API keys, passwords, Codex authentication files, or runtime state. The application creates state in `work/oracle-app-state`, which is ignored by Git. Environment variables supported by the relevant adapters include `EDGAR_USER_EMAIL` and `COINGECKO_DEMO_API_KEY`; never put their real values in the repository.

### PDF export

The current PDF exporter uses Node.js, Playwright, and Chrome. Its default discovery is tailored to the original macOS desktop runtime. See `outputs/oracle-local/pdf_export.py` and `pdf_render.cjs` for executable and module configuration before using PDF export on another machine. The ordinary analysis website does not require PDF tooling to start.

## Configuration and tests

- `outputs/oracle-local/config/analysis.json`: signal profiles, thresholds, caching, and workflow settings.
- `outputs/oracle-local/config/research_agents.json`: enable or disable research roles, concurrency, and role timeouts.
- `outputs/oracle-local/docs/multi-agent-process.md`: multi-agent behavior and recovery details.

```sh
cd outputs/oracle-local
../../work/oracle-venv/bin/python -m unittest discover -s tests -v
```

Unit tests verify implementation behavior, not financial forecasting accuracy. A successful quality review is not statistical calibration. Re-run tests after changing dependencies or providers.

## Repository layout

```text
outputs/oracle-local/       Web app, backend, UI, configuration and tests
work/digital-oracle/        Adapted upstream source used by the web app
digital_oracle/            Upstream-compatible provider source at repository root
references/                Upstream provider and symbol documentation
scripts/                   Upstream examples and regression tools
SKILL.md                   Original methodology
README.upstream.md         Original project introduction
LICENSE                    Original MIT license and attribution
```

The duplicated provider source preserves both the original skill layout and the existing local application layout. Keep corresponding adapter changes synchronized.

## Limits and project status

This is an experimental research workbench, not an autonomous trading system. Market prices do not uniquely identify every real-world event or future economic level. Research estimates may depend on uncalibrated assumptions; scenario ranges are not automatically confidence intervals. Missing target data may lead to a direction-only answer.

Known areas needing further work include target-specific fallback validation, strict contract-level anchor verification, comprehensive forecast backtesting, and portable PDF setup. Providers can fail or change formats, and failed or partial agent outputs are disclosed. Data redistribution and commercial-use permissions must be checked with each source; the code license does not license third-party market data.

## Privacy and attribution

This publication contains source code, tests and documentation. It excludes personal reports, live caches, logs, local virtual environments, browser profiles, API keys and Codex credentials. Local development Git history is not imported; the existing public upstream history is retained.

Based on **Digital Oracle by komako-workshop**. The original MIT copyright notice and license are retained in [LICENSE](LICENSE). Original documentation is preserved in [README.upstream.md](README.upstream.md) and the provider snapshot. This fork's additions include the research web interface, local pipeline, Hong Kong adapters, report exports and multi-agent orchestration.
