"""
VKS Legal AI v3.0 — API Test Suite
Tests all endpoints against live server
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
    print(f"🧪 TEST: {name}")
    print(f"{'='*60}")
    try:
        start = time.time()
        result = func()
        elapsed = round((time.time() - start) * 1000)
        print(f"✅ PASS ({elapsed}ms)")
        results.append({"test": name, "status": "PASS", "time_ms": elapsed})
        return result
    except Exception as e:
        print(f"❌ FAIL: {e}")
        results.append({"test": name, "status": "FAIL", "error": str(e)})
        return None


# ============ TEST 1: Health Check ============
def test_health():
    r = requests.get(f"{BASE_URL}/admin/health", timeout=15)
    data = r.json()
    print(f"  Status:    {data.get('status')}")
    print(f"  Version:   {data.get('version')}")
    print(f"  Ollama:    {data.get('ollama_connected')}")
    print(f"  RAG:       {data.get('rag_ready')}")
    print(f"  Chunks:    {data.get('total_legal_chunks')}")
    print(f"  Agent:     {data.get('agent_enabled')}")
    print(f"  Search:    {data.get('search_mode')}")
    print(f"  OpenRouter:{data.get('openrouter_configured')}")
    assert data.get("status") in ["ok", "degraded"], f"Bad status: {data}"
    return data

# ============ TEST 2: List Models ============
def test_models():
    r = requests.get(f"{BASE_URL}/v1/models", timeout=15)
    data = r.json()
    models = data.get("data", [])
    print(f"  Total models: {len(models)}")
    for m in models[:5]:
        provider = m.get("provider", "?")
        print(f"  - [{provider}] {m.get('id')}")
    assert len(models) > 0, "No models found"
    return data

# ============ TEST 3: Chat Direct (no RAG) ============
def test_chat_direct():
    r = requests.post(f"{BASE_URL}/v1/chat/completions", headers=HEADERS, json={
        "model": "qwen3:30b-a3b",
        "messages": [{"role": "user", "content": "Xin chào, bạn là ai?"}],
        "use_rag": False,
        "stream": False,
        "temperature": 0.3,
        "max_tokens": 200
    }, timeout=120)
    assert r.status_code == 200, f"HTTP {r.status_code}: {r.text[:300]}"
    data = r.json()
    content = data["choices"][0]["message"]["content"]
    print(f"  Model:   {data.get('model')}")
    print(f"  Tokens:  {data.get('usage', {}).get('total_tokens', '?')}")
    print(f"  Answer:  {content[:200]}...")
    assert len(content) > 10, "Answer too short"
    assert "sources" not in data or len(data.get("sources", [])) == 0, "Should have no sources in direct mode"
    return data

# ============ TEST 4: Chat RAG (Agentic) ============
def test_chat_rag():
    r = requests.post(f"{BASE_URL}/v1/chat/completions", headers=HEADERS, json={
        "model": "qwen3:30b-a3b",
        "messages": [{"role": "user", "content": "Phân tích Điều 173 Bộ luật Hình sự 2015 về tội trộm cắp tài sản"}],
        "use_rag": True,
        "stream": False,
        "temperature": 0.3,
        "max_tokens": 2000
    }, timeout=180)
    assert r.status_code == 200, f"HTTP {r.status_code}: {r.text[:300]}"
    data = r.json()
    content = data["choices"][0]["message"]["content"]
    sources = data.get("sources", [])
    agent = data.get("agent", {})
    print(f"  Model:     {data.get('model')}")
    print(f"  Tokens:    {data.get('usage', {}).get('total_tokens', '?')}")
    print(f"  Sources:   {len(sources)} nguồn")
    print(f"  Agent:     intent={agent.get('intent')}, steps={len(agent.get('steps', []))}")
    if agent.get("steps"):
        for s in agent["steps"]:
            print(f"    → {s['step']}: {s['found']} kết quả")
    print(f"  Answer:    {content[:300]}...")
    assert len(content) > 50, "RAG answer too short"
    return data

# ============ TEST 5: Chat Streaming ============
def test_chat_stream():
    r = requests.post(f"{BASE_URL}/v1/chat/completions", headers=HEADERS, json={
        "model": "qwen3:30b-a3b",
        "messages": [{"role": "user", "content": "Thế nào là tội phạm?"}],
        "use_rag": True,
        "stream": True,
        "temperature": 0.3,
        "max_tokens": 500
    }, timeout=120, stream=True)
    assert r.status_code == 200, f"HTTP {r.status_code}"
    
    chunks = 0
    full_text = ""
    sources_received = False
    for line in r.iter_lines():
        if not line:
            continue
        line = line.decode("utf-8")
        if not line.startswith("data:"):
            continue
        raw = line[5:].strip()
        if raw == "[DONE]":
            break
        try:
            p = json.loads(raw)
            if "sources" in p:
                sources_received = True
                print(f"  Sources:   {len(p['sources'])} nguồn received")
                continue
            c = p.get("choices", [{}])[0].get("delta", {}).get("content", "")
            if c:
                full_text += c
                chunks += 1
        except:
            pass
    
    print(f"  Chunks:    {chunks}")
    print(f"  Sources:   {'✅' if sources_received else '❌'}")
    print(f"  Answer:    {full_text[:200]}...")
    assert chunks > 0, "No chunks received"
    return {"chunks": chunks, "text_len": len(full_text)}

# ============ TEST 6: Document Search ============
def test_search():
    r = requests.post(f"{BASE_URL}/v1/documents/search", headers=HEADERS, json={
        "messages": [{"role": "user", "content": "Điều 173 BLHS tội trộm cắp"}]
    }, timeout=60)
    assert r.status_code == 200, f"HTTP {r.status_code}: {r.text[:300]}"
    data = r.json()
    sources = data.get("sources", [])
    print(f"  Query:     {data.get('query')}")
    print(f"  Intent:    {data.get('intent')}")
    print(f"  Results:   {len(sources)}")
    print(f"  Time:      {data.get('time_ms')}ms")
    if sources:
        for i, s in enumerate(sources[:3]):
            print(f"  [{i+1}] {s.get('title', '?')[:50]} — score: {s.get('score', 0):.4f}")
            print(f"      {s.get('content', '')[:100]}...")
    return data

# ============ TEST 7: Auth Error ============
def test_bad_auth():
    r = requests.post(f"{BASE_URL}/v1/chat/completions", 
        headers={"Authorization": "Bearer bad-key", "Content-Type": "application/json"},
        json={"model": "qwen3:30b-a3b", "messages": [{"role": "user", "content": "test"}]},
        timeout=15)
    print(f"  Status:    {r.status_code}")
    assert r.status_code == 401, f"Expected 401, got {r.status_code}"
    return {"status": r.status_code}

# ============ TEST 8: Documentation Page ============
def test_docs_page():
    r = requests.get(f"{BASE_URL}/documentation", timeout=15)
    print(f"  Status:    {r.status_code}")
    print(f"  Size:      {len(r.text)} bytes")
    assert r.status_code == 200, f"HTTP {r.status_code}"
    assert "VKS Legal AI" in r.text, "Page content missing"
    return {"status": r.status_code, "size": len(r.text)}


# ============ RUN ALL ============
if __name__ == "__main__":
    print(f"\n{'🚀'*20}")
    print(f"VKS Legal AI v3.0 — API Test Suite")
    print(f"Server: {BASE_URL}")
    print(f"{'🚀'*20}\n")

    test("1. Health Check", test_health)
    test("2. List Models", test_models)
    test("3. Documentation Page", test_docs_page)
    test("4. Bad Auth (expect 401)", test_bad_auth)
    test("5. Chat Direct (no RAG)", test_chat_direct)
    test("6. Chat RAG (Agentic)", test_chat_rag)
    test("7. Chat Streaming", test_chat_stream)
    test("8. Document Search", test_search)

    # SUMMARY
    print(f"\n\n{'='*60}")
    print(f"📊 KẾT QUẢ TỔNG HỢP")
    print(f"{'='*60}")
    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    for r in results:
        icon = "✅" if r["status"] == "PASS" else "❌"
        time_str = f" ({r.get('time_ms')}ms)" if 'time_ms' in r else ""
        err = f" — {r.get('error', '')}" if r["status"] == "FAIL" else ""
        print(f"  {icon} {r['test']}{time_str}{err}")
    
    print(f"\n  Tổng: {passed}/{len(results)} PASS, {failed} FAIL")
    if failed == 0:
        print(f"  🎉 TẤT CẢ ĐỀU PASS!")
    sys.exit(0 if failed == 0 else 1)
