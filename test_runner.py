import unittest
from unittest.mock import patch

from runner import finish_result, parse_step, safe_page_url, substitute_environment, unique


class CountedLocator:
    def __init__(self, matches):
        self.matches = matches

    def count(self):
        return self.matches


class DecisionChecks(unittest.TestCase):
    def test_success_requires_observed_assertion(self):
        result = finish_result({"passed": True, "reason": "Looks good"}, [])
        self.assertEqual(result["status"], "FAIL")

    def test_success_after_observed_assertion(self):
        trace = [{"action": "assert_text", "text": "Dashboard", "observed": True}]
        result = finish_result({"passed": True, "reason": "Dashboard is visible"}, trace)
        self.assertEqual(result["status"], "PASS")

    def test_failed_assertion_cannot_be_overridden(self):
        trace = [{"action": "assert_text", "text": "Dashboard", "observed": False}]
        result = finish_result({"passed": True}, trace)
        self.assertEqual(result["status"], "FAIL")

    def test_rejects_unknown_action(self):
        with self.assertRaises(ValueError):
            parse_step('{"action":"run_javascript"}')

    def test_secret_placeholder_is_resolved_locally_and_redacted(self):
        with patch.dict("os.environ", {"TASK_TEST_SECRET": "not-for-trace"}):
            value, safe = substitute_environment("${TASK_TEST_SECRET}")
        self.assertEqual(value, "not-for-trace")
        self.assertEqual(safe, "<env:TASK_TEST_SECRET>")

    def test_missing_environment_placeholder_fails_clearly(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(ValueError, "required by this test"):
                substitute_environment("${MISSING_TEST_VALUE}")

    def test_model_context_url_drops_credentials_and_query_values(self):
        safe = safe_page_url("https://tester:secret@example.org/path?token=private#fragment")
        self.assertEqual(safe, "https://example.org/path")

    def test_duplicate_locator_is_not_selected_arbitrarily(self):
        with self.assertRaisesRegex(ValueError, "found 2"):
            unique(CountedLocator(2), "control")


if __name__ == "__main__":
    unittest.main()

