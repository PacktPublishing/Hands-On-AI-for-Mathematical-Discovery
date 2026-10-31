from io import BytesIO
import unittest
from unittest.mock import patch

from ollama_discovery import parse_suggestion, suggest_candidate


class OllamaSuggestionTests(unittest.TestCase):
    def test_parses_valid_suggestion(self) -> None:
        self.assertEqual(
            parse_suggestion(
                '{"candidate_n": 4, "reason": "the value is a square"}'
            ),
            (4, "the value is a square"),
        )

    def test_rejects_non_json_response(self) -> None:
        with self.assertRaisesRegex(ValueError, "valid JSON"):
            parse_suggestion("I think n=4 might work")

    def test_rejects_boolean_as_integer(self) -> None:
        with self.assertRaisesRegex(ValueError, "integer candidate_n"):
            parse_suggestion('{"candidate_n": true, "reason": "guess"}')

    def test_rejects_invalid_reason(self) -> None:
        with self.assertRaisesRegex(ValueError, "must be text"):
            parse_suggestion('{"candidate_n": 4, "reason": 12}')

    @patch(
        "ollama_discovery.urlopen",
        return_value=BytesIO(
            b'{"message":{"content":"{\\"candidate_n\\":4,\\"reason\\":\\"square\\"}"}}'
        ),
    )
    def test_requests_candidate_from_ollama(self, mock_urlopen) -> None:
        self.assertEqual(
            suggest_candidate("test-model"),
            (4, "square"),
        )
        request = mock_urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "http://localhost:11434/api/chat")


if __name__ == "__main__":
    unittest.main()
