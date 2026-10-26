# Tooling decisions (researched 2026-10-25)

## Formula engine: own engine for grading, three independent engines to validate it

A subagent built a 10-formula workbook and ran each engine on it locally (Win11, Python
3.12). The workbook covered NPV, IRR, PMT, SUMPRODUCT, INDEX/MATCH, OFFSET, INDIRECT,
IFERROR and a two-cell circular loop.

| Engine | License | Coverage | Circular refs | Load / recalc |
|---|---|---|---|---|
| formualizer 0.12.0 | MIT/Apache, Rust | All OK | Converges with iterative calc on | 52 ms / 0.07 ms |
| ironcalc 0.9.1 | MIT/Apache, Rust | All OK | `#CIRC!` (no iterative calc) | 9 ms / 0.02 ms |
| formulas 1.3.4 | EUPL | No OFFSET | Breaks the cycle and returns 0 (wrong) | 740–900 ms / 0.8 ms |
| pycel 1.0b30 | GPL-3 | No IRR/PMT; SUM(OFFSET) silently 0 | Wrong | — (CVE-2024-53924, no release since 2021) |
| xlcalculator 0.5.0 | MIT | INDEX and IFERROR fail | Hung > 120 s | — |

**Decision.** The grader uses this project's own engine (`spreadsheet_env/engine`) for
four reasons:

1. **Branch instrumentation.** No library exposes which IF/MAX/MIN arm fired, and
   coverage-guided scenario selection needs that.
2. **A strict, portable subset.** Constructs whose meaning differs between Excel and
   LibreOffice, or that defeat dependency analysis, are *errors* rather than
   approximations:
   - implicit intersection and spilled arrays;
   - OFFSET, INDIRECT and volatile functions.

   This closes "engine disagreement" exploits by construction.
3. **Deterministic iterative calculation.** Circular components are solved by Gauss–Seidel
   iteration to a relative tolerance of 1e-11, so the fixed point does not depend on
   evaluation order.
4. **Speed and no native dependencies.** About 3 ms to compile a three-statement model and
   0.25 ms per scenario.

The claim "the engine computes what Excel computes" is checked rather than assumed.
`scripts/crosscheck_engines.py` evaluates every reference and mutant workbook with
formualizer, ironcalc and LibreOffice (headless) and reports the agreement rate.

## LibreOffice headless recalculation

- openpyxl-written files carry no cached values and a "Microsoft Excel Compatible" generator
  string. With LibreOffice's default `OOXMLRecalcMode=1` ("never"), formulas may *not*
  be recalculated on load. Set
  `/org.openoffice.Office.Calc/Formula/Load/OOXMLRecalcMode = 0` in the profile's
  `registrymodifications.xcu`.
- Give each concurrent process its own `-env:UserInstallation` profile.
- Docker on Debian trixie: `libreoffice-calc-nogui` (25.2.3).

## OpenEnv 0.9.0 (installed; verified from source)

- `MCPEnvironment(FastMCP)` routes `ListToolsAction` and `CallToolAction`; everything else
  goes to `_step_impl`. `CallToolObservation` does not carry episode reward, so
  `SpreadsheetEnvironment` stamps `done`, `reward` and the components after `submit`.
- The server deserializes MCP payloads only when `action_cls` is an MCP type. The server
  therefore uses `CallToolAction`, and batch edits are a tool (`write_cells`).
- HTTP `POST /reset` and `/step` are stateless (each builds a fresh env). Multi-step
  episodes must use the WebSocket client.
- `openenv push` creates a Docker Space. Hub discovery uses a dataset repo tagged
  `rl-environment` + `openenv` (blog, 2026-09-28).

## TRL 1.16 multi-turn GRPO (verified from source)

- `GRPOTrainer(environment_factory=Cls)`: every public method becomes a tool. Type hints
  and a Google-style docstring with `Args:` are required. A raised exception is shown to
  the model as an error.
- `reset(**row)` returns text that is appended to the prompt.
- `get_reward()` adds a reward column with weight 1.
- Works with `use_vllm=False` (plain `generate`), so it runs on Windows.
- `max_tool_calling_iterations` caps turns. `max_completion_length` caps tokens across all
  turns.
- A reward function may return `None`; that row is then excluded from the group baseline.

## Calibration data

- Damodaran industry datasets (`margin.xls`, `capex.xls`, `wcdata.xls`, `wacc.xls`,
  `taxrate.xls`; updated 2026-01-09). They are legacy `.xls`, read with `xlrd`. The terms
  are "no strings attached" with acknowledgement appreciated. Ship *derived* ranges with a
  citation, not the raw files.
- SEC Financial Statement Data Sets and the XBRL companyfacts API: public information.
  The API needs a User-Agent with a contact address and allows at most 10 requests per
  second.
