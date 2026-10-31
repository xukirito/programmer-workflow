from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "skills" / "programmer-workflow" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from lib.plan import normalize_plan, render_html, render_markdown, write_plan  # noqa: E402


class PlanTests(unittest.TestCase):
    def test_markdown_contains_review_gate(self) -> None:
        plan = normalize_plan({
            "title": "小改动",
            "goal": "验证计划",
            "steps": [{
                "title": "运行测试",
                "command": "python tests/run_tests.py",
                "change": "不改源码",
                "risk": "low",
                "verify": "全绿",
            }],
        })
        text = render_markdown(plan)
        self.assertIn("# 小改动", text)
        self.assertIn("回复 `执行`", text)
        self.assertIn("python tests/run_tests.py", text)
        self.assertIn("- [ ] 我批准执行", text)

    def test_html_escapes_content_and_has_no_external_dependency(self) -> None:
        plan = normalize_plan({
            "title": "计划 <x>",
            "steps": [{
                "title": "注入",
                "command": "echo <script>alert(1)</script>",
                "change": "<b>not html</b>",
            }],
        })
        page = render_html(plan)
        self.assertIn("计划 &lt;x&gt;", page)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", page)
        self.assertNotIn("<script>alert(1)</script>", page)
        self.assertNotIn("http://", page)
        self.assertNotIn("https://", page)
        self.assertIn("复制“执行”", page)

    def test_write_and_invalid_spec(self) -> None:
        tmp = ROOT / ".tmp-tests"
        tmp.mkdir(exist_ok=True)
        out = tmp / "plan-check.md"
        plan = normalize_plan({"steps": ["first"]})
        write_plan(plan, out, "md")
        self.assertTrue(out.exists())
        out.unlink()
        with self.assertRaises(ValueError):
            normalize_plan({"steps": []})

    def test_review_state_is_isolated_by_content_hash(self) -> None:
        import re
        first = normalize_plan({"title": "A", "steps": [{"title": "one", "change": "x"}]})
        second = normalize_plan({"title": "B", "steps": [{"title": "two", "change": "y"}]})
        first_again = normalize_plan({"title": "A", "steps": [{"title": "one", "change": "x"}]})
        page_a = render_html(first)
        page_b = render_html(second)
        page_a2 = render_html(first_again)
        key_a = re.search(r"pwf-plan-checks-v1:([0-9a-f]+)", page_a).group(1)
        key_b = re.search(r"pwf-plan-checks-v1:([0-9a-f]+)", page_b).group(1)
        key_a2 = re.search(r"pwf-plan-checks-v1:([0-9a-f]+)", page_a2).group(1)
        self.assertNotEqual(key_a, key_b)
        self.assertEqual(key_a, key_a2)


if __name__ == "__main__":
    unittest.main()
