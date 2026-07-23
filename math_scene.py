from manim import *

class MathProblemScene(Scene):
    def construct(self):
        # [SCENE 1] Giới thiệu bài toán và hình ảnh trực quan
        pole = Line(DOWN * 2.5, UP * 2.5, stroke_width=6)
        marker_A = MathTex("A", color=BLUE).next_to(pole, RIGHT, buff=0.2).shift(DOWN * 2)
        marker_B = MathTex("B", color=BLUE).next_to(pole, RIGHT, buff=0.2)
        marker_C = MathTex("C", color=BLUE).next_to(pole, RIGHT, buff=0.2).shift(UP * 2)
        pole_group = VGroup(pole, marker_A, marker_B, marker_C).center()

        an_text = Text("An: 150 cm", font="Noto Sans")
        bac_text = Text("Bắc: 153 cm", font="Noto Sans")
        cuong_text = Text("Cường: 148 cm", font="Noto Sans")
        students_group = VGroup(an_text, bac_text, cuong_text).arrange(DOWN, buff=0.5).scale(0.8).to_edge(LEFT, buff=1)

        self.play(Create(pole))
        self.play(Write(marker_A))
        self.play(Write(marker_B))
        self.play(Write(marker_C))
        self.wait(1)

        self.play(FadeIn(students_group[0]))
        self.wait(0.5)
        self.play(FadeIn(students_group[1]))
        self.wait(0.5)
        self.play(FadeIn(students_group[2]))
        
        self.wait(3)

        # [SCENE 2] Giả thuyết của bạn Cường
        cuong_hypo_an = Text("An (150 cm)", font="Noto Sans").scale(0.7)
        cuong_hypo_bac = Text("Bắc (153 cm)", font="Noto Sans").scale(0.7)
        cuong_hypo_cuong = Text("Cường (148 cm)", font="Noto Sans").scale(0.7)
        
        hypothesis_group = VGroup(cuong_hypo_an, cuong_hypo_bac, cuong_hypo_cuong).arrange(DOWN, buff=1.2).to_edge(RIGHT, buff=1)
        
        # Align text to markers
        cuong_hypo_an.align_to(marker_A, UP)
        cuong_hypo_bac.align_to(marker_B, UP)
        cuong_hypo_cuong.align_to(marker_C, UP)

        self.play(FadeOut(students_group))
        self.play(Write(hypothesis_group))
        self.wait(1)

        arrow_A = Arrow(marker_A.get_right(), cuong_hypo_an.get_left(), color=YELLOW, buff=0.2)
        arrow_B = Arrow(marker_B.get_right(), cuong_hypo_bac.get_left(), color=YELLOW, buff=0.2)
        arrow_C = Arrow(marker_C.get_right(), cuong_hypo_cuong.get_left(), color=YELLOW, buff=0.2)
        arrows = VGroup(arrow_A, arrow_B, arrow_C)

        self.play(Create(arrows))
        self.play(Flash(arrows, flash_radius=0.3, num_lines=10))
        self.wait(1)

        question = Text("Cường giải thích như vậy có đúng không?", font="Noto Sans").scale(0.7).to_edge(UP)
        self.play(Write(question))

        self.wait(3)

        # [SCENE 3] So sánh chiều cao thực tế
        self.play(FadeOut(*self.mobjects))
        self.wait(1)

        title = Text("So sánh chiều cao của ba bạn:", font="Noto Sans").to_edge(UP)
        
        cuong_info = VGroup(MathTex("148\\,\\text{cm}"), Text("Cường", font="Noto Sans")).arrange(DOWN)
        an_info = VGroup(MathTex("150\\,\\text{cm}"), Text("An", font="Noto Sans")).arrange(DOWN)
        bac_info = VGroup(MathTex("153\\,\\text{cm}"), Text("Bắc", font="Noto Sans")).arrange(DOWN)
        
        height_comparison_group = VGroup(cuong_info, an_info, bac_info).arrange(RIGHT, buff=1.5).center()

        self.play(FadeIn(title))
        self.wait(1)
        self.play(Write(height_comparison_group))
        self.wait(1)

        comparison_tex = MathTex("148\\,\\text{cm}", "<", "150\\,\\text{cm}", "<", "153\\,\\text{cm}").next_to(height_comparison_group, DOWN, buff=1)
        name_comparison_tex = VGroup(
            Text("Cường", font="Noto Sans"), MathTex("<"), Text("An", font="Noto Sans"), MathTex("<"), Text("Bắc", font="Noto Sans")
        ).arrange(RIGHT).next_to(comparison_tex, DOWN, buff=0.5)

        self.play(Write(comparison_tex[0]), Write(comparison_tex[2]), Write(comparison_tex[4]))
        self.wait(0.5)
        self.play(Write(comparison_tex[1]))
        self.wait(0.5)
        self.play(Write(comparison_tex[3]))
        self.wait(1)
        self.play(Write(name_comparison_tex))

        self.wait(4)

        # [SCENE 4] Phân tích sự vô lý
        self.play(FadeOut(*self.mobjects))
        self.wait(1)

        pole_group.center().to_edge(LEFT, buff=1.5)
        order_text = MathTex("A < B < C").scale(0.8).next_to(pole_group, DOWN, buff=0.5)
        
        cuong_map_A = MathTex("A = 150\\,\\text{cm}")
        cuong_map_B = MathTex("B = 153\\,\\text{cm}")
        cuong_map_C = MathTex("C = 148\\,\\text{cm}")
        cuong_map_group = VGroup(cuong_map_C, cuong_map_B, cuong_map_A).arrange(DOWN, buff=0.5).next_to(pole_group, RIGHT, buff=1)

        self.play(Create(pole_group))
        self.play(Write(order_text))
        self.wait(1)
        self.play(Write(cuong_map_group))
        self.wait(1)

        self.play(Flash(cuong_map_C, color=RED, flash_radius=0.7))
        self.wait(1)

        cross = Cross(cuong_map_group, stroke_color=RED, stroke_width=8)
        sai_text = Text("SAI", font="Noto Sans", color=RED, weight=BOLD).scale(1.5).next_to(cross, RIGHT, buff=0.5)
        
        self.play(Create(cross))
        self.play(Write(sai_text))

        self.wait(4)

        # [SCENE 5] Đưa ra lời giải đúng và Kết luận
        self.play(FadeOut(*self.mobjects))
        self.wait(1)

        pole_group.center()
        
        correct_cuong = VGroup(Text("Cường", font="Noto Sans"), MathTex("148\\,\\text{cm}")).arrange(DOWN, buff=0.2).scale(0.8)
        correct_an = VGroup(Text("An", font="Noto Sans"), MathTex("150\\,\\text{cm}")).arrange(DOWN, buff=0.2).scale(0.8)
        correct_bac = VGroup(Text("Bắc", font="Noto Sans"), MathTex("153\\,\\text{cm}")).arrange(DOWN, buff=0.2).scale(0.8)
        
        correct_group = VGroup(correct_bac, correct_an, correct_cuong).arrange(DOWN, buff=1.2).next_to(pole_group, RIGHT, buff=1.5)
        
        # Manually align to markers
        correct_cuong.move_to(marker_A.get_center() + RIGHT * 2.5)
        correct_an.move_to(marker_B.get_center() + RIGHT * 2.5)
        correct_bac.move_to(marker_C.get_center() + RIGHT * 2.5)

        line_A = Line(marker_A.get_right(), correct_cuong.get_left(), color=GREEN, buff=0.2)
        line_B = Line(marker_B.get_right(), correct_an.get_left(), color=GREEN, buff=0.2)
        line_C = Line(marker_C.get_right(), correct_bac.get_left(), color=GREEN, buff=0.2)
        correct_lines = VGroup(line_A, line_B, line_C)

        self.play(Create(pole_group))
        self.wait(1)
        self.play(Write(correct_group))
        self.wait(1)
        self.play(Create(correct_lines))
        self.wait(1)

        conclusion_text = Text(
            "Cường giải thích chưa đúng. Thứ tự đúng từ dưới lên phải là:\nA ứng với Cường, B ứng với An, và C ứng với Bắc.",
            font="Noto Sans",
            line_spacing=1.2
        ).scale(0.65).to_edge(DOWN, buff=0.5)
        
        self.play(Write(conclusion_text))

        self.wait(5)