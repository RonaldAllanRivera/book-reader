from typing import List


def build_quiz_prompt(question: str, options: List[str]) -> str:
    lines = ["Question:", question, "", "Options:"]
    for index, option in enumerate(options):
        letter = chr(ord("A") + index)
        lines.append(f"{letter}. {option}")
    lines.append("")
    lines.append("Choose the single best option and answer with the letter and full option text.")
    return "\n".join(lines)
