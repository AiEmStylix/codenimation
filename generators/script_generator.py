from .prompt_loader import load_prompt_from_file

def generate_script(math_problem: str, client) -> str:
    system_instruction = load_prompt_from_file("SCRIPT_GENERATOR.md")
    
    response = client.chat.completions.create(
        model="gemini-2.5-flash",
        messages=[
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": f"Tạo kịch bản cho bài toán sau:\n{math_problem}"}
        ],
        temperature=0.3
    )
    return response.choices[0].message.content
