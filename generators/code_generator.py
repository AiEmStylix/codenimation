import json
import re
from .prompt_loader import load_prompt_from_file

def generate_manim_code(
    script: str,
    client,
    storyboard: dict | None = None,
    animation_plan: dict | None = None,
    voiceover: dict | None = None,
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
    
    response = client.chat.completions.create(
        model="gemini-2.5-flash",
        messages=[
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3
    )
    
    raw_code = response.choices[0].message.content
    
    # Xử lý an toàn: Xóa các thẻ markdown
    raw_code = re.sub(r"^```python\s*", "", raw_code)
    raw_code = re.sub(r"^```\s*", "", raw_code)
    raw_code = re.sub(r"\s*```$", "", raw_code)
    
    return raw_code
