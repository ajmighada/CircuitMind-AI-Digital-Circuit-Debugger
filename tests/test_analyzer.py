import unittest
from analyzer import analyze_xor, analyze_dff
from generate_data import make_xor_data, make_dff_data


class CircuitMindTests(unittest.TestCase):
    def test_healthy_xor(self):
        self.assertEqual(analyze_xor(make_xor_data(False))["findings"], [])

    def test_glitch_and_mismatch(self):
        findings = analyze_xor(make_xor_data(True))["findings"]
        kinds = {finding["type"] for finding in findings}
        self.assertIn("Logic mismatch", kinds)
        self.assertIn("Possible output glitch", kinds)

    def test_dff_setup_warning(self):
        findings = analyze_dff(make_dff_data())["findings"]
        kinds = {finding["type"] for finding in findings}
        self.assertIn("Potential setup-time violation", kinds)
        self.assertIn("Q differs from ideal D-FF model", kinds)


if __name__ == "__main__":
    unittest.main()
