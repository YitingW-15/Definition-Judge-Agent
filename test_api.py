import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv(".env")

key = os.environ.get("DEEPSEEK_API_KEY")
print(f"Key loaded: {key[:8]}..." if key else "ERROR: key not found")

client = OpenAI(api_key=key, base_url="https://api.deepseek.com", timeout=30)

print("Sending test request (deepseek-v4-flash, no thinking)...")
resp = client.chat.completions.create(
    model="deepseek-v4-flash",
    messages=[{"role": "user", "content": "用一句话介绍你自己"}],
)
msg = resp.choices[0].message
print("content:", msg.content)
