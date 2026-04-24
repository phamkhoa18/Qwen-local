"""
VKS Legal AI v3.0 — API Test Suite (Fixed)
"""
import requests
import json
import time
import sys
import os

os.environ["PYTHONIOENCODING"] = "utf-8"
sys.stdout.reconfigure(encoding='utf-8') if hasattr(sys.stdout, 'reconfigure') else None

BASE_URL = "https://roy-than-bone-england.trycloudflare.com"
API_KEY = "vks-b260204cac8c9428077b71ebae9121c6e9df12e771fc475f"
HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {API_KEY}"
}

results = []

def test(name, func):
    print(f"\n{'='*60}")
    print(f"TEST: {name}")
    print(f"{'='*60}")
    try:
        start = time.time()
        result = func()
        elapsed = round((time.time() - start) * 1000)
        print(f"PASS ({elapsed}ms)")
        results.append({"test": name, "status": "PASS", "time_ms": elapsed})
        return result
    except Exception as e:
        print(f"FAIL: {e}")
        results.append({"test": name, "status": "FAIL", "error": str(e)})
        return None


# ============ TEST 5 FIX: Chat Direct ============
def test_chat_direct():
    """Test 5 failed because Qwen returns empty due to /no_think stripping.
    Check raw response more carefully."""
    r = requests.post(f"{BASE_URL}/v1/chat/completions", headers=HEADERS, json={
        "model": "qwen3:30b-a3b",
        "messages": [{"role": "user", "content": "1 + 1 bang bao nhieu?"}],
        "use_rag": False,
        "stream": False,
        "temperature": 0.3,
        "max_tokens": 500
    }, timeout=120)
    print(f"  HTTP Status: {r.status_code}")
    data = r.json()
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    print(f"  Raw response keys: {list(data.keys())}")
    print(f"  Content length: {len(content)}")
    print(f"  Content: [{content[:300]}]")
    print(f"  Usage: {data.get('usage')}")
    return data


# ============ TEST 7 FIX: Streaming ============
def test_streaming():
    """Test 7 failed - investigate streaming format"""
    r = requests.post(f"{BASE_URL}/v1/chat/completions", headers=HEADERS, json={
        "model": "qwen3:30b-a3b",
        "messages": [{"role": "user", "content": "Xin chao"}],
        "use_rag": False,
        "stream": True,
        "temperature": 0.3,
        "max_tokens": 100
    }, timeout=120, stream=True)
    print(f"  HTTP Status: {r.status_code}")
    print(f"  Headers: content-type={r.headers.get('content-type')}")
    
    chunks = 0
    full_text = ""
    raw_lines = []
    for line in r.iter_lines():
        if not line:
            continue
        decoded = line.decode("utf-8")
        raw_lines.append(decoded)
        if len(raw_lines) <= 10:
            print(f"  RAW[{len(raw_lines)}]: {decoded[:120]}")
        
        if not decoded.startswith("data:"):
            # Try without "data:" prefix
            if decoded.startswith("{"):
                try:
                    p = json.loads(decoded)
                    c = p.get("choices", [{}])[0].get("delta", {}).get("content", "")
                    if c:
                        full_text += c
                        chunks += 1
                except:
                    pass
            continue
        raw = decoded[5:].strip()
        if raw == "[DONE]":
            break
        try:
            p = json.loads(raw)
            if "sources" in p:
                print(f"  Sources received: {len(p.get('sources', []))}")
                continue
            c = p.get("choices", [{}])[0].get("delta", {}).get("content", "")
            if c:
                full_text += c
                chunks += 1
        except:
            pass
    
    print(f"  Total raw lines: {len(raw_lines)}")
    print(f"  Content chunks: {chunks}")
    print(f"  Full text: [{full_text[:200]}]")
    return {"chunks": chunks, "raw_lines": len(raw_lines)}


if __name__ == "__main__":
    print(f"\nDEBUG: Investigating 2 failing tests")
    print(f"Server: {BASE_URL}\n")

    test("5-FIX: Chat Direct (simple question)", test_chat_direct)
    test("7-FIX: Streaming Debug", test_streaming)

    print(f"\n{'='*60}")
    print(f"RESULTS")
    print(f"{'='*60}")
    for r in results:
        icon = "PASS" if r["status"] == "PASS" else "FAIL"
        time_str = f" ({r.get('time_ms')}ms)" if 'time_ms' in r else ""
        print(f"  [{icon}] {r['test']}{time_str}")
