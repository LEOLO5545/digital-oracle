# Bounded Codex research roles

The existing pipeline already generated layers concurrently, but synthesis did not consume independent research perspectives. With `config/research_agents.json` enabled, three separate ephemeral Codex calls now read one immutable evidence snapshot:

1. Direct evidence: target baseline, settlement terms, horizon and liquidity.
2. Cross-market: economic channels, anomalies and duplicated evidence.
3. Challenge: counterevidence and alternative explanations.

The synthesis call receives all validated role notes alongside the original evidence. Notes are not market data, votes or calibrated probabilities. Existing layers, numeric materialization, draft publication, focused audit and revision remain in place. This is application-orchestrated multi-agent inference; recursive CLI subagent spawning remains disabled to bound resource use.

Each role has a configurable 90-second model timeout, additionally bounded by the job's remaining budget. At most four model calls run concurrently in this report generator. Roles run concurrently first; synthesis and existing layers then run concurrently. Three additional calls increase aggregate input and may increase latency; no speed or accuracy improvement is assumed.

Successful notes are checkpointed by prompt hash. Invalid notes are removed from checkpoints; role failures are disclosed in report limitations. Failed roles do not manufacture evidence, and the existing synthesis may continue against the original snapshot. All role statuses and notes are saved in `report.research_agents`; normal model timings include role names and character counts. Existing UI model activity display uses the same timings. Old reports need no migration.

Set `enabled` to false to restore the previous workflow. Configuration is read for each new report generation. A process running pre-change code must restart while idle; do not interrupt another agent's UAT or a running analysis. Resuming a report with an already-generated draft continues that draft's audit rather than retroactively running new roles.

Verification: unit tests cover concurrency, successful-note checkpoint reuse, invalid citations, failure disclosure, invalid-cache removal and early draft publication. A real Codex smoke test reuses a saved housing evidence snapshot; it is not a new financial forecast or an end-to-end accuracy benchmark.

Known pre-existing issues: broad direction-only fallback and market-anchor verification gaps remain outside this change. Multi-agent reasoning does not resolve those deterministic validation defects.
