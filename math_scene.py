from manim import *

class MathProblemScene(Scene):
    def construct(self):
        # [SCENE 1] Giới thiệu Bài toán và Công cụ
        title = Text("Tìm số tự nhiên", font_size=40, weight=BOLD, color=YELLOW)
        title.to_edge(UP)
        
        problem_text = Text(
            "Dùng các chữ số 0; 3 và 5, viết một số tự nhiên\ncó ba chữ số khác nhau mà chữ số 5 có giá trị là 50.",
            font_size=28,
            t2c={"0; 3 và 5": BLUE, "50": RED}
        )
        problem_text.next_to(title, DOWN, buff=0.5)
        
        self.play(FadeIn(title), FadeIn(problem_text))
        self.wait(3)
        
        problem_group = VGroup(title, problem_text)
        self.play(
            problem_group.animate.scale(0.6).to_corner(UL)
        )
        self.wait(1)
        
        def create_card(num_str):
            sq = Square(side_length=1, color=WHITE)
            num = MathTex(num_str, font_size=48)
            return VGroup(sq, num)
            
        card_0 = create_card("0")
        card_3 = create_card("3")
        card_5 = create_card("5")
        
        cards = VGroup(card_0, card_3, card_5).arrange(RIGHT, buff=1).shift(UP * 1)
        
        self.play(
            Create(card_0),
            Create(card_3),
            Create(card_5)
        )
        self.wait(1)
        
        sq_tram = Square(side_length=1.2, color=BLUE)
        sq_chuc = Square(side_length=1.2, color=BLUE)
        sq_donvi = Square(side_length=1.2, color=BLUE)
        
        squares = VGroup(sq_tram, sq_chuc, sq_donvi).arrange(RIGHT, buff=0.2).shift(DOWN * 1.5)
        
        lbl_tram = Text("Hàng Trăm", font_size=20).next_to(sq_tram, UP)
        lbl_chuc = Text("Hàng Chục", font_size=20).next_to(sq_chuc, UP)
        lbl_donvi = Text("Hàng Đơn vị", font_size=20).next_to(sq_donvi, UP)
        
        labels = VGroup(lbl_tram, lbl_chuc, lbl_donvi)
        
        self.play(
            Create(squares),
            Write(labels)
        )
        self.wait(3)
        
        # [SCENE 2] Phân tích Dữ kiện "Giá trị của Chữ số 5"
        highlight = SurroundingRectangle(problem_text, color=YELLOW, buff=0.1)
        self.play(Create(highlight))
        self.play(FadeOut(highlight))
        
        self.play(card_5.animate.next_to(squares, UP, buff=1.5))
        self.wait(1)
        
        arrow_tram = Arrow(start=card_5.get_bottom(), end=sq_tram.get_top(), color=YELLOW)
        bubble_tram = Text("Nếu 5 ở đây, giá trị là 500. Sai!", font_size=20, color=RED).next_to(card_5, UP)
        cross_tram = MathTex("\\times", color=RED, font_size=48).move_to(sq_tram.get_center())
        
        self.play(GrowArrow(arrow_tram))
        self.play(FadeIn(bubble_tram), FadeIn(cross_tram))
        self.wait(1)
        self.play(FadeOut(arrow_tram), FadeOut(bubble_tram), FadeOut(cross_tram))
        
        arrow_donvi = Arrow(start=card_5.get_bottom(), end=sq_donvi.get_top(), color=YELLOW)
        bubble_donvi = Text("Nếu 5 ở đây, giá trị là 5. Sai!", font_size=20, color=RED).next_to(card_5, UP)
        cross_donvi = MathTex("\\times", color=RED, font_size=48).move_to(sq_donvi.get_center())
        
        self.play(GrowArrow(arrow_donvi))
        self.play(FadeIn(bubble_donvi), FadeIn(cross_donvi))
        self.wait(1)
        self.play(FadeOut(arrow_donvi), FadeOut(bubble_donvi), FadeOut(cross_donvi))
        
        arrow_chuc = Arrow(start=card_5.get_bottom(), end=sq_chuc.get_top(), color=YELLOW)
        bubble_chuc = Text("Nếu 5 ở đây, giá trị là 50. Đúng!", font_size=20, color=GREEN).next_to(card_5, UP)
        tick_chuc = MathTex("\\checkmark", color=GREEN, font_size=48).move_to(sq_chuc.get_center())
        
        self.play(GrowArrow(arrow_chuc))
        self.play(FadeIn(bubble_chuc), FadeIn(tick_chuc))
        self.wait(1)
        self.play(FadeOut(arrow_chuc), FadeOut(bubble_chuc), FadeOut(tick_chuc))
        
        self.play(card_5.animate.move_to(sq_chuc.get_center()))
        self.wait(2)
        
        # [SCENE 3] Tìm Chữ số Hàng trăm
        rule_text = Text("Chữ số hàng trăm phải khác 0 và khác 5", font_size=24, color=YELLOW)
        rule_text.to_edge(DOWN)
        self.play(Write(rule_text))
        self.wait(1)
        
        card_0_original_pos = card_0.get_center()
        self.play(card_0.animate.move_to(sq_tram.get_center()))
        
        barrier = MathTex("\\times", color=RED, font_size=60).move_to(sq_tram.get_center())
        self.play(FadeIn(barrier))
        self.wait(0.5)
        self.play(
            card_0.animate.move_to(card_0_original_pos),
            FadeOut(barrier)
        )
        self.wait(1)
        
        self.play(card_3.animate.move_to(sq_tram.get_center()))
        self.wait(2)
        
        # [SCENE 4] Hoàn thành Số
        self.play(FadeOut(rule_text))
        
        self.play(card_0.animate.move_to(sq_donvi.get_center()))
        self.wait(1)
        
        self.play(
            FadeOut(squares),
            FadeOut(labels),
            FadeOut(card_0[0]),
            FadeOut(card_3[0]),
            FadeOut(card_5[0]),
            FadeOut(problem_group)
        )
        
        num_3 = card_3[1]
        num_5 = card_5[1]
        num_0 = card_0[1]
        
        final_number = VGroup(num_3, num_5, num_0)
        
        self.play(
            final_number.animate.arrange(RIGHT, buff=0.1).move_to(ORIGIN).scale(2.5)
        )
        self.wait(1)
        
        # [SCENE 5] Kết luận và Kiểm tra
        self.play(final_number.animate.shift(UP * 2))
        
        check1 = Text("1. Các chữ số khác nhau? (3, 5, 0)", font_size=28)
        tick1 = MathTex("\\checkmark", color=GREEN, font_size=36)
        check1_group = VGroup(check1, tick1).arrange(RIGHT).next_to(final_number, DOWN, buff=1)
        
        check2 = Text("2. Chữ số 5 có giá trị là 50? (5 ở hàng chục)", font_size=28)
        tick2 = MathTex("\\checkmark", color=GREEN, font_size=36)
        check2_group = VGroup(check2, tick2).arrange(RIGHT).next_to(check1_group, DOWN, buff=0.5)
        
        self.play(FadeIn(check1))
        self.play(Write(tick1))
        self.wait(1)
        
        self.play(FadeIn(check2))
        self.play(Write(tick2))
        self.wait(1)
        
        conclusion = Text("Kết luận: Số cần tìm là 350", font_size=36, color=YELLOW, weight=BOLD)
        box = SurroundingRectangle(conclusion, color=YELLOW, buff=0.3)
        conclusion_group = VGroup(conclusion, box).next_to(check2_group, DOWN, buff=1)
        
        self.play(FadeIn(conclusion_group, shift=UP))
        
        self.play(Indicate(final_number, color=YELLOW, scale_factor=1.2))
        
        self.wait(3)