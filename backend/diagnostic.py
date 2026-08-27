import os
import sys
import asyncio
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

print("============================================================")
print("       DEEPVERIFY SERVICE & API DIAGNOSTIC SUITE            ")
print("============================================================")

# 1. Environment Keys
keys = [
    "OPENAI_API_KEY",
    "GROQ_API_KEY",
    "SERPAPI_API_KEY",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "SUPABASE_URL",
    "SUPABASE_SERVICE_KEY",
    "BLOCKCHAIN_RPC_URL",
    "WALLET_PRIVATE_KEY",
    "CONTRACT_ADDRESS",
]
print("\n[1] Environment Variables:")
for k in keys:
    val = os.getenv(k, "")
    status = f"PRESENT ({val[:8]}...)" if val else "MISSING"
    print(f"  - {k:22}: {status}")

# 2. OpenAI API
print("\n[2] Testing OpenAI API:")
try:
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    res = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Hello"}],
        max_tokens=5,
    )
    print("  ✅ OpenAI API SUCCESS:", res.choices[0].message.content.strip())
except Exception as e:
    print("  ❌ OpenAI API ERROR:", e)

# 3. Groq API
print("\n[3] Testing Groq API:")
try:
    from groq import Groq
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    res = client.chat.completions.create(
        model="groq/compound",
        messages=[{"role": "user", "content": "Hello"}],
        max_tokens=5,
    )
    print("  ✅ Groq API SUCCESS:", res.choices[0].message.content.strip())
except Exception as e:
    print("  ❌ Groq API ERROR:", e)

# 4. SerpApi (Google Search / Lens)
print("\n[4] Testing SerpApi:")
try:
    from serpapi import GoogleSearch
    search = GoogleSearch({"engine": "google", "q": "test", "api_key": os.getenv("SERPAPI_API_KEY")})
    res = search.get_dict()
    if "search_metadata" in res and res["search_metadata"].get("status") == "Success":
        print("  ✅ SerpApi SUCCESS")
    else:
        print("  ❌ SerpApi RESPONSE ERROR:", res.get("error", res))
except Exception as e:
    print("  ❌ SerpApi ERROR:", e)

# 5. Telegram Bot
print("\n[5] Testing Telegram Bot:")
try:
    import httpx
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    res = httpx.get(f"https://api.telegram.org/bot{bot_token}/getMe", timeout=10).json()
    if res.get("ok"):
        print(f"  ✅ Telegram Bot SUCCESS: @{res['result']['username']}")
    else:
        print("  ❌ Telegram Bot ERROR:", res)
except Exception as e:
    print("  ❌ Telegram Bot ERROR:", e)

# 6. Blockchain Connection & Smart Contract
print("\n[6] Testing Blockchain Connection:")
try:
    from web3 import Web3
    rpc_url = os.getenv("BLOCKCHAIN_RPC_URL")
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    if w3.is_connected():
        print(f"  ✅ Blockchain RPC connected ({rpc_url}), Latest block: {w3.eth.block_number}")
        contract_addr = os.getenv("CONTRACT_ADDRESS")
        if contract_addr:
            code = w3.eth.get_code(Web3.to_checksum_address(contract_addr))
            if len(code) > 2:
                print(f"  ✅ Smart Contract deployed at {contract_addr} (bytecode length: {len(code)})")
            else:
                print(f"  ⚠️ Smart Contract address has NO code: {contract_addr}")
    else:
        print(f"  ❌ Cannot connect to RPC: {rpc_url}")
except Exception as e:
    print("  ❌ Blockchain ERROR:", e)

# 7. System Executables
print("\n[7] Testing System Executables:")
import shutil
for tool in ["ffmpeg", "yt-dlp", "c2patool"]:
    p = shutil.which(tool)
    msg = f"FOUND at {p}" if p else "NOT FOUND"
    symbol = "✅" if p else ("⚠️" if tool == "c2patool" else "❌")
    print(f"  {symbol} {tool:12}: {msg}")

# 8. Check Backend Running Port 8000
print("\n[8] Checking Backend API Server on http://localhost:8000:")
try:
    import httpx
    res = httpx.get("http://localhost:8000/health", timeout=3)
    if res.status_code == 200:
        print("  ✅ Backend Server is RUNNING:", res.json())
    else:
        print(f"  ❌ Backend Server returned HTTP {res.status_code}")
except Exception as e:
    print("  ❌ Backend Server is NOT running (Connection Refused):", e)

print("\n============================================================")
