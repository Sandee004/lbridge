# LedgerBridge: Task Checklist

Work through phases in order. Each task lists where to change and a "done when" check.

## Ground rules (read first)

- Make **minimal, targeted changes**. Do not rewrite files or restructure the project beyond what a task says.
- Do not add features that are not listed here.
- After each task: run the test suite, and commit with a message naming the task id (e.g. `P1.2: pin deps`).
- If a task's premise looks wrong when you open the code, stop and say so instead of improvising.
- Never write accuracy, latency, or coverage numbers into docs unless they come from the eval harness output (Phase 5).
- Never commit real bank data. Fixtures must be fully synthetic.

---

## Phase 1: Fresh clone works, failures are loud

- [x] **P1.1 Fix requirements.** `backend/requirements.txt` is missing `httpx` and `openpyxl`. Add them, add `pytest` and `pytest-asyncio` (or put test deps in `requirements-dev.txt`).
  *Done when:* in a new venv, `pip install -r requirements.txt` then `python -c "import parser, pipeline"` (run from `backend/`) succeeds.
- [x] **P1.2 Pin all dependency versions.** Pin every package in `requirements.txt` to the exact version that currently works. `pypdf` must be pinned to a version that parses the fixture (5.1.0 parses 56 rows; 7.2.0 parses 0).
  *Done when:* requirements has `==` pins only, and a fresh install parses the Access fixture to 56 rows.
- [x] **P1.3 Make the PDF parser fail loudly.** In `backend/parser/pdf_parser.py` (and `excel_parser.py` for the same case):
  - Raise `ValueError` with a clear message if 0 transactions are parsed.
  - If opening or closing balance could not be found, set `math_ok=False` and `math_error_detail="Could not verify: balances not found"`. Do not return `math_ok=True` with 0.0 balances.
  *Done when:* a test feeding a PDF with no recognizable table returns HTTP 422, and a test with missing balances returns `math_ok=False`.
- [x] **P1.4 Convert tests to pytest with a temp DB.** Files in `backend/tests/` are print scripts with no assertions, and they call `drop_all` on the real `project.db`.
  - Add `conftest.py` that sets `DATABASE_URL` to a temp SQLite file per test session and creates tables.
  - Convert `test_ingestion.py`, `test_pipeline_and_excel.py`, `test_new_routes.py`, `test_e2e_integration.py` to real assertions (row counts, `math_ok`, dedup returns 0 new rows, PATCH updates element and writes an Override). Remove the unconditional "ALL TESTS PASSED" prints.
  - Mock Ollama (patch `httpx.AsyncClient.post`) in every test that reaches the LLM tier.
  *Done when:* `pytest` passes from `backend/`, and running it does not modify `backend/project.db`.

## Phase 2: Pipeline correctness

For each task, add a failing test first, then fix.

- [x] **P2.1 Use the real JSON schema.** In `backend/pipeline/llm.py`, `OLLAMA_RESULT_SCHEMA` is defined but the request sends `"format": "json"`. Send the schema as `format`.
  *Done when:* a test asserts the request body's `format` is the schema dict.
- [x] **P2.2 Align the element set.** The schema/prompt know 5 elements; categories and rules also use `cogs`, `transfer`, `taxes`. Make the schema enum and the system prompt come from one list (the category slugs plus `needs_review`), and describe all categories in the prompt.
  *Done when:* a test asserts the schema enum equals the default category slugs plus `needs_review`.
- [x] **P2.3 Validate model output.** In `classify_batch_with_ollama`, if the returned `element` is not in the allowed set, set `needs_review` with reason "Model returned unknown category". Also clamp `confidence` to 0-1 and handle non-numeric values.
  *Done when:* tests with `"Expenses"`, `"foo"`, and `confidence: "high"` all end as `needs_review` without raising.
- [x] **P2.4 Short row ids.** Send `"0".."n"` indices to the model instead of 64-char fingerprints; map back by index.
  *Done when:* a test with a mocked response keyed by index maps correctly, and an omitted index becomes `needs_review`.
- [x] **P2.5 Dedup before classification.** In `routers/statements.py` / `pipeline/orchestrator.py`, drop rows whose fingerprint already exists before running rules or the LLM. Do the lookup in one query (`WHERE fingerprint IN (...)`), not one per row. Also dedupe within the same upload.
  *Done when:* re-uploading overlapping data makes zero LLM calls (assert on the mock) and does not change rule `hit_count`.
- [x] **P2.6 Fix user-rule behavior** in `routers/transactions.py` and `routers/rules.py`:
  - User rules get priority above all seed rules (e.g. 200).
  - Escape user-supplied patterns with `re.escape` and wrap in `\b...\b` at creation time (or use `exact_counterparty` with whole-token matching).
  - The "existing rule" lookup must match on `(pattern, direction)`.
  - Validate `element` against the categories table; return 422 otherwise (also on PATCH).
  *Done when:* a test overrides a row that a seed rule matched, saves a rule, re-ingests a similar row, and gets the user's element.
- [x] **P2.7 Seed rule cleanup** in `backend/pipeline/rules.py`:
  - Remove `slot systems` from the asset rule (keep specific equipment terms).
  - Resolve the `fgn stamp duty` overlap: it should live in one rule only (taxes or expense, pick one, document why).
  - Replace `oct invoice|nov invoice|dec invoice` with a month-agnostic `invoice` pattern, or drop it.
  - Remove or tighten overly broad tokens (`internet`, `glo`, `spar`, `sweep`, `cot`).
  *Done when:* a test shows "SLOT SYSTEMS ... LAPTOP REPAIR" is not auto-classified as an asset.
- [x] **P2.8 Use the capitalization threshold.** `CAPITALIZATION_THRESHOLD` in `config.py` is unused. Apply it in `validate_and_guard`: an `asset` below the threshold is demoted to `needs_review` with a reason (or reclassified as `expense` if you choose that policy; state it in a comment).
  *Done when:* tests cover an asset below and above the threshold.
- [x] **P2.9 Strengthen guardrails and keep provenance** in `validate_and_guard`:
  - Add: `asset`, `cogs`, `taxes` must be debits; `capital` requires a configured owner name match (add an `owner_names` setting; if unset, `capital` from the LLM goes to `needs_review`).
  - When a guard demotes a row, set `tier="validator"`, keep the original prediction in `reason`, and set `confidence` to 0.0.
  *Done when:* tests cover each guard and assert `tier == "validator"` after demotion.
- [x] **P2.10 Few-shot retrieval by similarity.** In `get_few_shot_examples`, select the top-k overrides most similar to the current batch (token overlap on `description_norm` is enough for now) instead of the last 5 globally. Include the user's final element and drop the amount from the example line.
  *Done when:* a test shows a relevant older override is chosen over an irrelevant newer one.

## Phase 3: Privacy and security hygiene

- [x] **P3.1 Scrub fixtures.** `tests/generate_access_bank_statement.py`, `generate_demo_excel.py`, `generate_demo_statement.py` contain a real-looking personal name and long reference numbers. Replace names with obviously fake ones and generate random reference numbers. Regenerate all fixtures.
  *Done when:* `grep -ri "oyarekhua\|tomsin" .` returns nothing.
- [x] **P3.2 Remove committed artifacts.** `git rm --cached backend/project.db`, and keep exactly one copy of each fixture under `backend/tests/fixtures/` (delete the root-level and `backend/` duplicates, and update paths in `routers/statements.py` sample loader and `seed_db.py`).
  *Done when:* `git ls-files | grep -E "\.db|\.pdf|\.xlsx"` lists only files under `tests/fixtures/`.
- [x] **P3.3 Secrets.** Remove the hardcoded fallback JWT secret in `backend/utils.py`. Read one `JWT_SECRET` setting (delete the duplicate in `config.py`). If unset, generate a random secret at first run and store it outside the repo, or refuse to start with a clear message. Add `backend/.env.example`.
  *Done when:* no secret literal exists in the repo (`grep -rn "secret-key" backend` is empty).
- [x] **P3.4 Decide on auth (ask the owner before doing this one).** The tool is positioned as single-user and local. Options: (a) remove auth, bind to `127.0.0.1`; (b) keep auth and add `user_id` to statements, transactions, rules, overrides, and scope every query. Do not do both and do not leave the middle state. (Selected Option A: single-user local mode, no 401 gating, bound to 127.0.0.1).
- [x] **P3.5 Remove deploy-oriented code** that contradicts "100% local": the `RENDER` env branch in `main.py`, the `onrender.com` CORS origin, and `--host 0.0.0.0` in comments.

## Phase 4: Export

- [x] **P4.1 Move export to the backend** `GET /statements/{id}/export?format=csv|xlsx` so it is testable. Keep the existing flat and journal CSV modes.
- [x] **P4.2 Block or segregate unresolved rows.** Journal mode must not post `needs_review` rows to an account. Either refuse with a count of unresolved rows, or write them to a separate "unresolved" file.
- [x] **P4.3 CSV formula-injection guard.** Prefix any cell starting with `=`, `+`, `-`, `@` (after trimming) with a single quote, in every text column.
  *Done when:* a test exports a narration `=HYPERLINK("x")` and the cell is neutralized.
- [x] **P4.4 XLSX export** with three sheets: Categorized Rows, 5-Element Summary (SUMIFS formulas referencing the rows sheet), Audit Log (tier, rule id or model, confidence, override).
  *Done when:* a test opens the workbook with openpyxl and checks the summary totals equal the row sums.
- [x] **P4.5 Make README match the actual export columns.** Remove the Zoho step-by-step unless it has been tested against a real Zoho account; if untested, say "column mapping may be required" and list the exact columns exported.

## Phase 5: Eval harness (this is what makes the project credible)

Follow `mvp.md` Section 7.

- [x] **P5.1 Create `eval/` layout**: `data/dev.jsonl`, `data/test.jsonl`, `data/synthetic.jsonl`, `configs/`, `run.py`, `metrics.py`, `report.py`.
- [x] **P5.2 Dataset format.** One JSON object per row: `statement_id`, `date`, `description_raw`, `amount`, `direction`, `gold_element`, optional `acceptable_alternates`, `should_review`. Commit only synthetic data. Real data stays in a gitignored folder.
- [x] **P5.3 Configs A, C, E** first (rules only; rules + LLM zero-shot; full system with validators and threshold). Add B, D, and the model sweep after.
- [x] **P5.4 Metrics**: coverage by tier, Needs Review rate, **auto-accept error rate**, per-tier accuracy, review precision, error capture, macro-F1, 5x5 confusion matrix, rows/sec.
- [x] **P5.5 Report generator** writes `eval/reports/<config>-<timestamp>.md` plus per-row JSON, and records model name, model digest, prompt hash, ruleset hash, and dataset version.
- [x] **P5.6 Threshold tuning on dev only**, then one verification run on test. Plot the risk-coverage curve.
- [x] **P5.7 Cold vs. warm replay** (overrides accumulate over statements in time order).
- [x] **P5.8 CI gate**: a GitHub Action that runs config E on dev with a mocked or recorded model response set, and fails if the auto-accept error rate exceeds the stored baseline by a set margin.
- [x] **P5.9 Replace every claim** in `README.md`, `architecture.md`, and `frontend/src/components/LandingPage.tsx` ("98%", "40-65%", "~5%", the benchmark table, the "100%" stat) with numbers from the latest report, or delete the claim. Keep "100% local" only as a statement about data flow, not accuracy.

## Phase 6: Cleanup and honesty pass

- [x] **P6.1** Fix `architecture.md` inaccuracies: it says the parser is `backend/parser.py` and uses `pypdf`/"pdfplumber" inconsistently; batch size comments say 10-15 while `BATCH_SIZE` is 6; it describes schema-constrained decoding (true only after P2.1).
- [x] **P6.2** Add a "Known limitations" section to the README: text PDFs only, banks actually tested (list them), Asset vs. Expense depends on the capitalization threshold, own-account transfers and loan principal/interest cannot be split from a statement alone.
- [x] **P6.3** Add a short "Accounting scope" note: a bank statement shows only the cash side of each event.
- [x] **P6.4** Make the 8 default categories and the 5-element framing consistent across README, prompt, and UI.

---

## Definition of done for the MVP

- A fresh clone installs and runs the demo with the documented commands.
- `pytest` passes and never touches the dev database.
- The eval report exists and every number in the README traces to it.
- No real personal data, secrets, or database files are tracked in git.
