import unittest
import contextlib
import io
import json
import sys
import types
from unittest.mock import patch

from runner import (
    build_result,
    main,
    parse_response,
    request_completion,
    safe_page_url,
    substitute_environment,
    unique,
    validate_assertions,
)


class CountedLocator:
    def __init__(self, matches):
        self.matches = matches

    def count(self):
        return self.matches


class FakeLocator:
    def __init__(self, visible):
        self.visible = visible

    @property
    def first(self):
        return self

    def filter(self, **kwargs):
        return self

    def wait_for(self, **kwargs):
        if not self.visible:
            raise TimeoutError("not visible")

    def count(self):
        return int(self.visible)


class FakePage:
    url = "https://example.org/"

    def __init__(self, text):
        self.visible_text = text
        self.frames = [self]

    def goto(self, url, **kwargs):
        self.url = url

    def evaluate(self, script):
        return {"title": "Example", "text": self.visible_text, "controls": []}

    def get_by_text(self, text, **kwargs):
        return FakeLocator(text.casefold() in self.visible_text.casefold())

    def title(self):
        return "Example"


class FakeContext:
    def __init__(self, page):
        self.pages = [page]

    def new_page(self):
        return self.pages[0]


class FakeBrowser:
    def __init__(self, page):
        self.context = FakeContext(page)

    def new_context(self):
        return self.context

    def close(self):
        pass


class FakePlaywright:
    def __init__(self, page):
        self.chromium = types.SimpleNamespace(launch=lambda **kwargs: FakeBrowser(page))


class FakePlaywrightManager:
    def __init__(self, page):
        self.page = page

    def __enter__(self):
        return FakePlaywright(self.page)

    def __exit__(self, *_):
        pass


class RunnerChecks(unittest.TestCase):
    def test_cli_pass_requires_and_observes_assertion(self):
        page = FakePage("Dashboard")
        answer = json.dumps({
            "action": "done",
            "reason": "The page already shows the dashboard",
            "assertions": [{"kind": "text", "value": "Dashboard"}],
        })
        fake_openai = types.ModuleType("openai")
        fake_response = types.SimpleNamespace(choices=[types.SimpleNamespace(
            message=types.SimpleNamespace(content=answer))])
        fake_completions = types.SimpleNamespace(create=lambda **request: fake_response)
        fake_openai.OpenAI = lambda **kwargs: types.SimpleNamespace(
            chat=types.SimpleNamespace(completions=fake_completions))
        fake_playwright_sync = types.ModuleType("playwright.sync_api")
        fake_playwright_sync.TimeoutError = TimeoutError
        fake_playwright_sync.sync_playwright = lambda: FakePlaywrightManager(page)
        fake_playwright = types.ModuleType("playwright")
        fake_playwright.sync_api = fake_playwright_sync
        fake_dotenv = types.ModuleType("dotenv")
        fake_dotenv.load_dotenv = lambda: None
        output = io.StringIO()
        with patch.dict(sys.modules, {"openai": fake_openai, "dotenv": fake_dotenv, "playwright": fake_playwright,
                                     "playwright.sync_api": fake_playwright_sync}), \
             patch.dict("os.environ", {"OPENAI_API_KEY": "test", "OPENAI_MODEL": "test-model"}), \
             patch.object(sys, "argv", ["runner.py", "--url", "https://example.org", "--case", "Show dashboard"]), \
             contextlib.redirect_stdout(output):
            exit_code = main()
        self.assertEqual(exit_code, 0)
        self.assertEqual(json.loads(output.getvalue())["status"], "PASS")

    def test_pass_requires_all_checks_and_completed_plan(self):
        checks = [{"kind": "text", "value": "Dashboard", "observed": True}]
        self.assertEqual(build_result(checks, [], "", 0.2, completed=True)["status"], "PASS")
        self.assertEqual(build_result(checks, [], "", 0.2, completed=False)["status"], "FAIL")

    def test_any_failed_acceptance_condition_fails(self):
        checks = [
            {"kind": "text", "value": "Dashboard", "observed": True},
            {"kind": "url", "value": "/dashboard", "observed": False},
        ]
        result = build_result(checks, [], "", 0.2, completed=True)
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("1 of 2", result["reason"])

    def test_empty_assertion_set_never_passes(self):
        self.assertEqual(build_result([], [], "", 0.2, completed=True)["status"], "FAIL")

    def test_first_response_must_include_observable_assertions(self):
        with self.assertRaisesRegex(ValueError, "omitted"):
            parse_response('{"action":"done"}', first_response=True)
        step = parse_response('{"action":"done","assertions":[]}', first_response=True)
        self.assertEqual(step["assertions"], [])

    def test_acceptance_assertions_are_validated(self):
        valid = validate_assertions([{"kind": "text", "value": "Dashboard"}])
        self.assertEqual(valid[0]["frame"], 0)
        with self.assertRaisesRegex(ValueError, "non-empty"):
            validate_assertions([{"kind": "url", "value": ""}])
        with self.assertRaisesRegex(ValueError, "frame"):
            validate_assertions([{"kind": "text", "value": "Done", "frame": True}])
        with self.assertRaisesRegex(ValueError, "visible"):
            validate_assertions([{"kind": "role", "role": "heading", "value": "Done", "visible": "yes"}])

    def test_rejects_unknown_actions(self):
        with self.assertRaisesRegex(ValueError, "allowed action"):
            parse_response('{"action":"run_javascript"}')

    def test_retries_without_json_mode_when_provider_does_not_support_it(self):
        class Completions:
            calls = []

            def create(self, **kwargs):
                self.calls.append(kwargs)
                if "response_format" in kwargs:
                    raise ValueError("response_format is not supported")
                return "ok"

        completions = Completions()
        client = types.SimpleNamespace(chat=types.SimpleNamespace(completions=completions))
        self.assertEqual(request_completion(client, "model", {"case": "check"}), "ok")
        self.assertEqual(len(completions.calls), 2)
        self.assertNotIn("response_format", completions.calls[1])

    def test_environment_values_are_resolved_locally_and_redacted(self):
        with patch.dict("os.environ", {"TASK_TEST_SECRET": "not-for-trace"}):
            value, safe = substitute_environment("${TASK_TEST_SECRET}")
        self.assertEqual(value, "not-for-trace")
        self.assertEqual(safe, "<env:TASK_TEST_SECRET>")

    def test_missing_environment_value_fails_clearly(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(ValueError, "required by this test"):
                substitute_environment("${MISSING_TEST_VALUE}")

    def test_model_url_drops_credentials_and_query_values(self):
        safe = safe_page_url("https://tester:secret@example.org/path?token=private#fragment")
        self.assertEqual(safe, "https://example.org/path")

    def test_duplicate_locator_is_not_selected_arbitrarily(self):
        with self.assertRaisesRegex(ValueError, "found 2"):
            unique(CountedLocator(2), "control")


if __name__ == "__main__":
    unittest.main()

