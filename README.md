# Task 2 â€” plain-English browser runner

A small Python CLI that asks an OpenAI-compatible chat model to turn a test case into one browser action at a time, executes those actions with Playwright, and returns PASS only when the model observes evidence for the requested condition. URL and case are command-line inputs; the site is not embedded in the implementation.

## Requirements

- Python 3.10+
- An OpenAI-compatible chat completion API key and model
- Chromium installed by Playwright

## Setup (PowerShell)

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m playwright install chromium
$env:OPENAI_API_KEY = "your-key"
$env:OPENAI_MODEL = "your-compatible-model-name"
```

For another OpenAI-compatible provider set `OPENAI_BASE_URL` as well. Keep keys in environment variables; never commit them.

## Run

```powershell
python runner.py --url https://phptravels.com/demo --case "Open the page and verify the demo access form is shown"
```

The runner prints a JSON result with status, explanation, and action trace; PASS exits 0 and FAIL exits 1. It refuses ambiguous duplicate controls and only accepts PASS after a visible-text assertion succeeds. Other example:

```powershell
python runner.py --url https://example.org --case "Open the page and verify the main heading contains Example Domain"
```

The model receives the current page title, URL and visible interactive elements. It can choose from a small set of actions (`click`, `fill`, `select`, `check`, `assert_text`, `finish`) using accessible names/labels. It cannot execute arbitrary JavaScript or issue network requests. It stops after a bounded number of actions and reports errors as FAIL. To recheck the decision safeguards, run `python -m unittest`.

The test case and visible page text are sent to the configured model API. URL userinfo, query values, and fragments are removed from the URL shown to the model. Use fictional test data. For login checks, put credentials in environment variables and refer to them as `${TEST_EMAIL}` or `${TEST_PASSWORD}` in the case; the runner resolves fill values locally and redacts them from the action trace. Never put real passwords directly in the case text.

## Approach and limitations

The model interprets new language cases and plans against the live page, while Playwright executes and validates each step. Pass/fail is evidence based: a case must include an observable condition. This remains probabilistic; ambiguous wording, CAPTCHA/MFA, login credentials, complex canvas widgets and rapidly changing pages can defeat the planner. A model may also choose a poor locator or misread evidence. Review the trace and use a controlled test account for authenticated workflows. The included PHPTRAVELS example checks the public demo request page and does not request access or enter personal data.

