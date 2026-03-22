import os
from dotenv import load_dotenv

load_dotenv()

from app.translator import _build_llm, _TRANSLATION_PROMPT, _parse_numbered_blocks

key = os.getenv("LLM_API_KEY")
llm = _build_llm("gemini", key, "gemini-2.0-flash", "")

blocks = [
    "Table of Contents",
    "Foreword. . . . . . . . . . . . . . . . . . . . . xvii",
    "Preface. . . . . . . . . . . . . . . . . . . . . xix",
    "1. Meet Hadoop. . . . . . . . . . . . . . . 3",
    "Data!",
    "Data Storage and Analysis"
]

numbered = "\n\n".join(f"[{i+1}] {t}" for i, t in enumerate(blocks))
prompt = _TRANSLATION_PROMPT.format(blocks=numbered)
response = llm.call(prompt)
parsed = _parse_numbered_blocks(response, len(blocks))

for p in parsed:
    print(p)
