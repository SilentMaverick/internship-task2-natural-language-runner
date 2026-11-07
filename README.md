# Task 2 â€” plain-English browser runner

A Python CLI that turns a plain-English case into bounded Playwright actions on the supplied URL. The model proposes both the actions and explicit acceptance conditions. Playwright checks those conditions against the browser; the model cannot declare a test passed by itself.

## Requirements

- Python 3.10 or later
- An OpenAI-compatible chat-completion API key and model name
- Chromium installed by Playwright

## Linux setup

From this directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m playwright install chromium
cp .env.example .env
# Edit .env and set OPENAI_API_KEY and OPENAI_MODEL.
```

If Chromium reports missing Linux system libraries on Debian or Ubuntu, install them with:

```bash
python -m playwright install-deps chromium
```

For a compatible endpoint other than the default, also set `OPENAI_BASE_URL`, for example `export OPENAI_BASE_URL='http://localhost:11434/v1'`. Keep API keys in environment variables; do not commit them.

## Windows setup (PowerShell)

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m playwright install chromium
Copy-Item .env.example .env
# Edit .env and set OPENAI_API_KEY and OPENAI_MODEL.
```

## Run

```bash
python runner.py --url https://phptravels.com/demo --case "Open the page and verify the demo access form is shown"
```

The runner prints JSON with `PASS` or `FAIL`, the acceptance checks and their observed results, a redacted action trace, and elapsed time. It exits `0` for PASS and `1` for FAIL. Use `--headless` for headless Chromium; `--max-actions` sets the action limit (1â€“20); `--negative-settle-ms` sets the wait for delayed text in a negative assertion (default 800 ms).

Another site and case:

```bash
python runner.py --url https://example.org --case "Open the page and verify the main heading contains Example Domain"
```

Fill multiple labeled form fields without submitting the form:

```bash
python runner.py --url https://phptravels.com/demo --case "Fill the First name textbox with Demo and Last name with Tester and Business name with xyz and whatsapp number with 0000000000"
```

Explicit fill requests are performed before the model plans further steps. The runner verifies each field retained its requested value; it does not submit the form unless the case explicitly asks it to.

Recheck the local decision and privacy safeguards without an API key or browser installation:

```bash
python -m unittest -v
```

## How it works

1. Playwright opens the requested URL and collects a compact snapshot of visible text, accessible controls, and same-page frames.
2. The model receives the case and snapshot, then proposes one action and the acceptance conditions on its first response. Later responses can adapt actions to the updated page.
3. The runner executes only the allowed actions (`click`, `fill`, `select`, `check`, `wait_text`, `done`). It rejects duplicate visible matches instead of choosing the first control.
4. The test passes only after the planner finishes and every generated acceptance condition is observed in Playwright. Supported checks include visible text, URL, page title, and accessible role/name.

The runner has a bounded action count and timeouts. It uses JSON mode when the model endpoint supports it and retries without that option when an OpenAI-compatible endpoint explicitly rejects it; local schema validation still applies. It does not run arbitrary JavaScript or submit file uploads. Page content is treated as untrusted data, not as instructions.

## Privacy and limits

The plain-English case and visible page text are sent to the configured model API. Input values are omitted from snapshots. For login tests, store values in environment variables and refer to them in the case as `${TEST_EMAIL}` and `${TEST_PASSWORD}`; the runner resolves those placeholders locally and redacts filled values in its trace. Do not put real passwords directly in the case.

This is an LLM-assisted test planner, not a formal natural-language verifier. It can misunderstand vague requirements or propose a weak acceptance condition, so inspect the emitted checks and trace. A negative text assertion waits for the configured settle interval; a very late page update can still arrive afterward. CAPTCHA, MFA, complex canvas controls, custom inaccessible widgets, and dynamic pages may need manual setup or a site-specific adapter. The included PHPTRAVELS case checks the public demo request page only; it does not request access or enter personal information.

