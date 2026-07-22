import re
from .prompt_loader import load_prompt_from_file

def generate_manim_code(script: str, client) -> str:
    system_instruction = load_prompt_from_file("CODE_GENERATOR.md")
    
    response = client.chat.completions.create(
        model="gemini-2.5-pro",
        messages=[
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": f"Viết code Manim cho kịch bản sau:\n{script}"}
        ],
        temperature=0.2
    )
    
    raw_code = response.choices[0].message.content
    
    # Xử lý an toàn: Xóa các thẻ markdown
    raw_code = re.sub(r"^```python\s*", "", raw_code)
    raw_code = re.sub(r"^```\s*", "", raw_code)
    raw_code = re.sub(r"\s*```$", "", raw_code)
    
    return raw_code
