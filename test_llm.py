import os
import sys
from dotenv import load_dotenv

# Load env before importing app modules
load_dotenv()

from app.translator import _build_llm, _TRANSLATION_PROMPT, _parse_numbered_blocks

def main():
    api_key = os.getenv("LLM_API_KEY")
    if not api_key:
        print("No API key")
        return
        
    llm = _build_llm("gemini", api_key, "gemini-2.0-flash", "")
    
    blocks = [
        "In pioneer days they used oxen for heavy pulling, and when one ox couldn't budge a log,",
        "they didn't try to grow a larger ox. We shouldn't be trying for bigger computers, but for",
        "more systems of computers."
    ]
    
    numbered = "\n\n".join(f"[{i+1}] {t}" for i, t in enumerate(blocks))
    prompt = _TRANSLATION_PROMPT.format(blocks=numbered)
    
    print("--- PROMPT ---")
    print(prompt)
    
    print("\n--- CALLING LLM ---")
    try:
        response = llm.call(prompt)
        print("--- RAW LLM RESPONSE ---")
        print(response)
        
        print("\n--- PARSING ---")
        parsed = _parse_numbered_blocks(response, len(blocks))
        print("Parsed:", parsed)
        
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    main()
