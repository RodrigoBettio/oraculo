import unittest
from sanitizer import StringSanitizer

class TestStringSanitizer(unittest.TestCase):
    
    def test_sanitize_string_basic(self):
        malicious = "<script>alert('xss')</script>"
        safe = StringSanitizer.sanitize_string(malicious, escape_quotes=True)
        self.assertNotIn("<script>", safe)

    def test_sanitize_payload_dictionary(self):
        payload = {
            "username": "admin''--",
            "comment": "<script>alert(1)</script>"
        }
        sanitized = StringSanitizer.sanitize_payload(payload)
        self.assertEqual(sanitized["username"], "admin''--")
        self.assertNotIn("<script>", sanitized["comment"])

if __name__ == "__main__":
    unittest.main()