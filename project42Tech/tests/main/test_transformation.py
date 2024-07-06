import pandas as pd
import unittest
import sys
sys.path.append("src/main")
from transformation import *


class TestTransformation(unittest.TestCase):
    def test_normalize_company_name(self):
        expected = "web aruba"
        self.assertEqual(expected, normalize_company_name("Web Aruba"))


if __name__ == "__main__":
    unittest.main()