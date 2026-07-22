from manim import *

class MathProblemScene(Scene):
    def construct(self):
        # [SCENE 1]
        title = Text("Luyện tập 2: Viết các tập hợp sau bằng cách liệt kê phần tử", font_size=28)
        title.to_edge(UP)
        
        eq_A = MathTex(r"A = \{x \in ", r"\mathbb{N}", r" \mid ", r"x < 5", r"\}")
        eq_B = MathTex(r"B = \{x \in ", r"\mathbb{N}^*", r" \mid ", r"x < 5", r"\}")
        
        group_eqs = VGroup(eq_A, eq_B).arrange(DOWN, buff=0.8)
        
        self.play(FadeIn(title))
        self.wait(1)
        self.play(Write(eq_A))
        self.wait(1)
        self.play(Write(eq_B))
        self.wait(3)
        
        # [SCENE 2]
        self.play(FadeOut(title), FadeOut(eq_B))
        self.play(eq_A.animate.to_edge(UP, buff=1.5))
        self.wait(1)
        
        self.play(eq_A[1].animate.set_color(YELLOW))
        
        exp_N_math = MathTex(r"\mathbb{N}", color=YELLOW)
        exp_N_text = Text(": Tập hợp các số tự nhiên (bao gồm số 0)", font_size=24)
        exp_N = VGroup(exp_N_math, exp_N_text).arrange(RIGHT, buff=0.2)
        exp_N.next_to(eq_A, DOWN, buff=0.6)
        
        self.play(FadeIn(exp_N, shift=RIGHT))
        self.wait(1)
        
        self.play(eq_A[3].animate.set_color(GREEN))
        cond_A = MathTex(r"x < 5", color=GREEN)
        cond_A.next_to(exp_N, DOWN, buff=0.6)
        self.play(FadeIn(cond_A, shift=UP))
        self.wait(1)
        
        nums_A = MathTex("0", ";", "1", ";", "2", ";", "3", ";", "4")
        nums_A.next_to(cond_A, DOWN, buff=0.6)
        for i in range(0, len(nums_A), 2):
            self.play(Create(nums_A[i]), run_time=0.4)
            if i + 1 < len(nums_A):
                self.play(Write(nums_A[i+1]), run_time=0.2)
        self.wait(1)
        
        res_A = MathTex("A", "=", "\\{", "0", ";", "1", ";", "2", ";", "3", ";", "4", "\\}")
        res_A.move_to(nums_A.get_center())
        box_A = SurroundingRectangle(res_A, color=YELLOW)
        self.play(ReplacementTransform(nums_A, res_A))
        self.play(Create(box_A))
        self.wait(4)
        
        # [SCENE 3]
        self.play(FadeOut(eq_A), FadeOut(exp_N), FadeOut(cond_A), FadeOut(res_A), FadeOut(box_A))
        self.wait(1)
        
        eq_B.move_to(ORIGIN)
        self.play(Write(eq_B))
        self.wait(1)
        self.play(eq_B.animate.to_edge(UP, buff=1.5))
        self.wait(1)
        
        self.play(eq_B[1].animate.set_color(RED))
        
        exp_N_star_math = MathTex(r"\mathbb{N}^*", color=RED)
        exp_N_star_text = Text(": Tập hợp các số tự nhiên khác 0", font_size=24)
        exp_N_star = VGroup(exp_N_star_math, exp_N_star_text).arrange(RIGHT, buff=0.2)
        exp_N_star.next_to(eq_B, DOWN, buff=0.6)
        
        self.play(FadeIn(exp_N_star))
        self.wait(1)
        
        self.play(eq_B[3].animate.set_color(GREEN))
        cond_B = MathTex(r"x < 5", color=GREEN)
        cond_B.next_to(exp_N_star, DOWN, buff=0.6)
        self.play(FadeIn(cond_B, shift=UP))
        self.wait(1)
        
        nums_B = MathTex("1", ";", "2", ";", "3", ";", "4")
        nums_B.next_to(cond_B, DOWN, buff=0.6)
        for i in range(0, len(nums_B), 2):
            self.play(Create(nums_B[i]), run_time=0.4)
            if i + 1 < len(nums_B):
                self.play(Write(nums_B[i+1]), run_time=0.2)
        self.wait(1)
        
        res_B = MathTex("B", "=", "\\{", "1", ";", "2", ";", "3", ";", "4", "\\}")
        res_B.move_to(nums_B.get_center())
        box_B = SurroundingRectangle(res_B, color=RED)
        self.play(ReplacementTransform(nums_B, res_B))
        self.play(Create(box_B))
        self.wait(4)
        
        # [SCENE 4]
        self.play(FadeOut(eq_B), FadeOut(exp_N_star), FadeOut(cond_B))
        self.wait(1)
        
        group_B = VGroup(res_B, box_B)
        self.play(group_B.animate.move_to(DOWN * 1.5))
        self.wait(1)
        
        group_A = VGroup(res_A, box_A)
        group_A.move_to(UP * 1.5)
        self.play(FadeIn(group_A))
        self.wait(1)
        
        label_A = MathTex(r"(\mathbb{N})", color=YELLOW, font_size=36).next_to(group_A, RIGHT, buff=0.5)
        label_B = MathTex(r"(\mathbb{N}^*)", color=RED, font_size=36).next_to(group_B, RIGHT, buff=0.5)
        self.play(FadeIn(label_A), FadeIn(label_B))
        self.wait(1)
        
        circle_0 = DashedVMobject(Circle(color=YELLOW, radius=0.3).move_to(res_A[3].get_center()), num_dashes=12)
        self.play(Create(circle_0))
        self.wait(1)
        
        self.play(res_A[3].animate.set_opacity(0), run_time=0.2)
        self.play(res_A[3].animate.set_opacity(1), run_time=0.2)
        self.play(res_A[3].animate.set_opacity(0), run_time=0.2)
        self.play(res_A[3].animate.set_opacity(1), run_time=0.2)
        
        self.wait(5)