import os
import sys
from dotenv import load_dotenv

load_dotenv()

from app.translator import _build_llm

def test(key):
    llm = _build_llm("gemini", key, "gemini-2.0-flash", "")
    print(f"Testing key: {key}")
    try:
        r = llm.call("Hi")
        if r:
            print("SUCCESS. Response:", r)
            return True
        else:
            print("FAILED (no response or error)")
            return False
    except Exception as e:
        print("Exception:", e)
        return False

# Test both I and l
test("AIzaSyCjc-qCesV64aoF7LjhO5NttVIlwQf-WHA")
test("AIzaSyCjc-qCesV64aoF7LjhO5NttVllwQf-WHA")
