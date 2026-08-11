from validators.review_engine import run_review_cycle, analyze_code


def test_analyze_code_returns_issue_for_direct_play_mobject() -> None:
    code = """
from manim import *

class TestScene(Scene):
    def construct(self):
        title = Text('Tiêu đề')
        self.play(title)
"""
    result = analyze_code(code)
    assert result["issue_count"] >= 1
    issue = result["issues"][0]
    assert issue["error_code"] == "MAN-001"
    assert issue["fix_strategy"] == "WRAP_WITH_WRITE"
    assert issue["auto_fixable"] is True


def test_run_review_cycle_autofixes_direct_play_mobject() -> None:
    code = """
from manim import *

class TestScene(Scene):
    def construct(self):
        title = Text('Tiêu đề')
        self.play(title)
"""
    result = run_review_cycle(code)
    assert result["auto_fixed"] is True
    assert "Write(title)" in result["fixed_code"]


def test_detect_mathtx_unicode_issue() -> None:
    code = """
from manim import *

class TestScene(Scene):
    def construct(self):
        formula = MathTex("Số tự nhiên nhỏ hơn 5")
        self.play(Write(formula))
"""
    result = analyze_code(code)
    assert any(issue["error_code"] == "LATEX-005" for issue in result["issues"])
