#!/usr/bin/env python3
"""单元测试：解析 MinerU MD。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib.parse_md import parse_md_file  # noqa: E402

MD = Path(
    r"d:\赵亚菲\yafei-one-context\features\research\pdf-math-exam-to-latex-skill-survey"
    r"\pilot\output\mineru\2023-2024-2高等数学C（二）A卷\auto\2023-2024-2高等数学C（二）A卷.md"
)


class TestParseMineru(unittest.TestCase):
    @unittest.skipUnless(MD.is_file(), "mineru sample md missing")
    def test_parse_five_questions(self) -> None:
        data = parse_md_file(MD)
        qs = data["sections"][0]["questions"]
        self.assertEqual(len(qs), 5)
        self.assertEqual(data["meta"]["course_id"], "MATH1029")
        self.assertIn("原函数", qs[0]["stem"])
        self.assertIn("\\lim", qs[1]["stem"])
        self.assertTrue(all(q["choices"]["A"] for q in qs))


if __name__ == "__main__":
    unittest.main()
