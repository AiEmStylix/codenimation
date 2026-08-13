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


def test_foreign_import_is_flagged_and_removed() -> None:
    code = """
import numpy as np
from PIL import Image
from manim import *

class TestScene(Scene):
    def construct(self):
        title = Text('Tiêu đề')
        self.play(Write(title))
"""
    result = analyze_code(code)
    codes = [issue["error_code"] for issue in result["issues"]]
    assert codes.count("IMP-007") >= 2

    fixed = run_review_cycle(code)["fixed_code"]
    assert "import numpy" not in fixed
    assert "from PIL" not in fixed
    assert "from manim import *" in fixed


def test_legacy_api_usage_is_replaced() -> None:
    code = """
from manim import *

class TestScene(Scene):
    def construct(self):
        box = SurroundingRect(Text('x'))
        self.play(Create(box))
"""
    result = run_review_cycle(code)
    assert "SurroundingRectangle" in result["fixed_code"]
    assert "SurroundingRect(" not in result["fixed_code"]


def test_long_wait_is_flagged_pace_001() -> None:
    code = """
from manim import *

class TestScene(Scene):
    def construct(self):
        title = Text('Tiêu đề', font='Arial')
        self.play(Write(title))
        self.wait(8)
"""
    result = analyze_code(code)
    issues = [issue for issue in result["issues"] if issue["error_code"] == "PACE-001"]
    assert issues, "Phải phát hiện self.wait() quá dài"
    assert issues[0]["severity"] == "ERROR"
    assert issues[0]["auto_fixable"] is False


def test_normal_wait_is_not_flagged() -> None:
    code = """
from manim import *

class TestScene(Scene):
    def construct(self):
        title = Text('Tiêu đề', font='Arial')
        self.play(Write(title))
        self.wait(1.5)
"""
    result = analyze_code(code)
    assert not any(issue["error_code"] == "PACE-001" for issue in result["issues"])


def test_long_run_time_is_flagged_pace_002() -> None:
    code = """
from manim import *

class TestScene(Scene):
    def construct(self):
        title = Text('Tiêu đề', font='Arial')
        self.play(Write(title), run_time=5)
"""
    result = analyze_code(code)
    assert any(issue["error_code"] == "PACE-002" for issue in result["issues"])


def test_chained_subscript_highlight_is_flagged() -> None:
    code = """
from manim import *

class TestScene(Scene):
    def construct(self):
        n_set = MathTex(r"\\mathbb{N} = {0, 1, 2}")
        self.play(Indicate(n_set[0][2]))
"""
    result = analyze_code(code)
    assert any(issue["error_code"] == "EMPH-003" for issue in result["issues"])


def test_vietnamese_in_mathtx_is_error() -> None:
    code = """
from manim import *

class TestScene(Scene):
    def construct(self):
        formula = MathTex(r"\\text{Đúng: } K = {1, 2}")
        self.play(Write(formula))
"""
    result = analyze_code(code)
    issues = [issue for issue in result["issues"] if issue["error_code"] == "LATEX-005"]
    assert issues
    assert issues[0]["severity"] == "ERROR"


def test_previous_scene_without_fadeout_is_flagged() -> None:
    code = """
from manim import *

class TestScene(Scene):
    def construct(self):
        # [SCENE 1] scene_1
        a = Text('A', font='Arial')
        self.play(Write(a))
        self.wait(1)
        # [SCENE 2] scene_2
        b = Text('B', font='Arial')
        self.play(Write(b))
        self.play(FadeOut(b))
"""
    result = analyze_code(code)
    assert any(issue["error_code"] == "LAY-002" for issue in result["issues"])


def test_unpositioned_multiple_objects_is_flagged() -> None:
    code = """
from manim import *

class TestScene(Scene):
    def construct(self):
        # [SCENE 1] scene_1
        x = MathTex(r"x")
        y = MathTex(r"y")
        self.play(Write(x))
        self.play(Write(y))
        self.play(FadeOut(VGroup(x, y)))
"""
    result = analyze_code(code)
    assert any(issue["error_code"] == "LAY-001" for issue in result["issues"])


def test_arranged_group_is_not_flagged() -> None:
    code = """
from manim import *

class TestScene(Scene):
    def construct(self):
        # [SCENE 1] scene_1
        a = Text('A', font='Arial')
        b = Text('B', font='Arial')
        vg = VGroup(a, b).arrange(DOWN, buff=0.5)
        self.play(Write(vg))
        self.wait(1)
        self.play(FadeOut(vg))
"""
    result = analyze_code(code)
    assert not any(issue["error_code"].startswith("LAY") for issue in result["issues"])
