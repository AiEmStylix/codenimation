import html
import json
import re
from .prompt_loader import load_prompt_from_file
from .model_config import DEFAULT_LLM_MODEL
from .prompt_utils import _log_llm_failure


_LATEX_STRING_PATTERN = re.compile(r'((?:MathTex|Tex)\(\s*r?[\"\'])(.*?)([\"\'])', re.DOTALL)


def _fix_latex_backslashes(code: str) -> str:
    """Thu gọn backslash bị escape thừa bên trong chuỗi MathTex/Tex.

    LLM hay chép y nguyên LaTeX từ storyboard (đã qua json.dumps nên backslash
    bị nhân đôi thành \\in, \\mathbb, \\{ ...). Thu gọn 2+ backslash liên tiếp
    về 1 backslash chỉ bên trong chuỗi raw của MathTex/Tex.
    """

    def _collapse(match: re.Match) -> str:
        content = match.group(2)
        content = re.sub(r"\\{2,}", lambda m: "\\", content)
        return match.group(1) + content + match.group(3)

    return _LATEX_STRING_PATTERN.sub(_collapse, code)

def generate_manim_code(
    script: str,
    client,
    storyboard: dict | None = None,
    animation_plan: dict | None = None,
    voiceover: dict | None = None,
    scene_names: list[str] | None = None,
) -> str:
    system_instruction = load_prompt_from_file("CODE_GENERATOR.md")
    prompt = f"Viết code Manim cho kịch bản sau:\n{script}"
    if storyboard is not None:
        prompt += "\n\nStoryboard:\n" + json.dumps(storyboard, ensure_ascii=False, indent=2)
    if animation_plan is not None:
        prompt += "\n\nAnimation plan:\n" + json.dumps(animation_plan, ensure_ascii=False, indent=2)
    if voiceover is not None:
        prompt += "\n\nVoiceover guidance:\n" + json.dumps(voiceover, ensure_ascii=False, indent=2)
        prompt += "\n\nHãy đồng bộ animation với voiceover bằng cách sử dụng animation_instruction và hold_duration của mỗi scene khi viết code."
        prompt += "\n\nBắt buộc chèn comment dạng # [SCENE n] scene_id ngay trước khối code của từng scene để extractor có thể chia timings và phụ đề theo từng cảnh. Ví dụ: # [SCENE 1] scene_1_de_bai."
        prompt += "\n\nCấu trúc video bắt buộc: Scene 1 là đề bài, scene cuối là tổng kết + bài tập vận dụng, không được tự thêm hoặc bỏ scene."
        prompt += "\n\nTUYỆT ĐỐI không dùng HTML entity (&lt; &gt; &amp; &le; &ge; ...) trong code — phải viết ký tự thật (< > & ≤ ≥)."
        prompt += "\n\nCấm nhấn mạnh bằng cách cắt index của MathTex (vd n_set[0][-5:]) — kết quả không đáng tin. Muốn tô sáng một ký hiệu, tách nó thành MathTex/Text riêng rồi ghép VGroup."
    if scene_names:
        prompt += "\n\nDanh sách scene bắt buộc giữ nguyên thứ tự và số lượng:\n" + "\n".join(f"- {name}" for name in scene_names)
        prompt += "\nKhông được thêm hoặc bớt scene. Mỗi scene phải có đúng một khối code và đúng một comment # [SCENE n] scene_id."
    
    try:
        response = client.chat.completions.create(
            model=DEFAULT_LLM_MODEL,
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )
        raw_code = response.choices[0].message.content
    except Exception as exc:
        _log_llm_failure("text_failure", "CODE_GENERATOR.md", "", prompt, str(exc))
        raise
    
    # Xử lý an toàn: Xóa các thẻ markdown
    raw_code = re.sub(r"^```python\s*", "", raw_code)
    raw_code = re.sub(r"^```\s*", "", raw_code)
    raw_code = re.sub(r"\s*```$", "", raw_code)

    # Giải mã HTML entity (&lt; &gt; &amp; ...) mà LLM chép từ storyboard vào code.
    raw_code = html.unescape(raw_code)

    # Thu gọn backslash bị nhân đôi bên trong MathTex/Tex (json.dumps artifact).
    raw_code = _fix_latex_backslashes(raw_code)

    return raw_code
