/**
 * VKS Legal AI - Frontend v3
 * No login required, auto API key, 3 modes, HCMUTE-style
 */
const S = {
  apiKey: localStorage.getItem('vks_api_key') || null,
  token: localStorage.getItem('vks_token') || null,
  convs: JSON.parse(localStorage.getItem('vks_convs') || '[]'),
  convId: null,
  msgs: [],
  streaming: false,
  mode: 'llm',
};

// ===== AUTO SETUP (no login) =====
async function autoSetup() {
  if (S.apiKey) return;
  try {
    // Auto-login with default admin credentials
    const r = await fetch('/admin/login', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: 'admin', password: 'vks@2024' })
    });
    const d = await r.json();
    if (d.access_token) {
      S.token = d.access_token;
      localStorage.setItem('vks_token', d.access_token);
      // Auto-create API key
      const r2 = await fetch('/admin/api-keys', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${S.token}` },
        body: JSON.stringify({ name: 'Khóa tự động', description: 'Tự động tạo' })
      });
      const d2 = await r2.json();
      if (d2.key) { S.apiKey = d2.key; localStorage.setItem('vks_api_key', d2.key); }
    }
  } catch (e) { console.warn('Auto setup failed:', e); }
}

// ===== INIT =====
async function init() {
  updateGreeting();
  await autoSetup();
  checkHealth();
  loadModels();
  renderConvs();
  setInterval(checkHealth, 30000);
}

function updateGreeting() {
  const h = new Date().getHours();
  let g = 'buổi sáng', e = '☀️';
  if (h >= 12 && h < 18) { g = 'buổi chiều'; e = '🌤️'; }
  else if (h >= 18 || h < 5) { g = 'buổi tối'; e = '🌙'; }
  const el = document.querySelector('.welcome h2');
  if (el) el.innerHTML = `Chào <span class="highlight">${g}</span> ${e}`;
}

async function checkHealth() {
  try {
    const r = await fetch('/admin/health'); const d = await r.json();
    setDot('st-ollama', d.ollama_connected, 'Ollama');
    setDot('st-rag', d.rag_ready, 'RAG');
    const c = document.getElementById('st-chunks'); if (c) c.textContent = `${d.total_legal_chunks} đoạn văn bản`;
    
    // Indexing Banner
    const banner = document.getElementById('idx-banner');
    if (banner) {
      if (d.indexing) {
        banner.classList.add('show');
        const p = d.indexing_progress || {};
        let text = 'Đang tự động tải dữ liệu pháp luật...';
        let pct = 0;
        if (p.status === 'downloading') text = 'Đang tải dataset từ HuggingFace...';
        else if (p.status === 'processing' || p.status === 'embedding') {
          pct = p.total ? Math.round((p.current / p.total) * 100) : 0;
          text = `Đang phân tích văn bản: ${p.current.toLocaleString()}/${p.total.toLocaleString()} (${pct}%)`;
        }
        document.getElementById('idx-text').textContent = text;
        document.getElementById('idx-fill').style.width = pct + '%';
        
        // Poll faster while indexing
        if (!window.idxPoller) window.idxPoller = setInterval(checkHealth, 3000);
      } else {
        banner.classList.remove('show');
        if (window.idxPoller) { clearInterval(window.idxPoller); window.idxPoller = null; }
      }
    }

    const b = document.getElementById('rag-badge');
    if (b) {
      if (d.rag_ready) { b.className = 'rag-status ready'; b.innerHTML = `<span class="status-dot on"></span> ${d.total_legal_chunks.toLocaleString()} văn bản sẵn sàng`; }
      else if (d.indexing) { b.className = 'rag-status indexing'; b.innerHTML = `<span class="status-dot on" style="background:var(--gold);box-shadow:none;"></span> Đang nạp...`; }
      else { b.className = 'rag-status off'; b.innerHTML = `<span class="status-dot off"></span> Chưa có dữ liệu`; }
    }
  } catch (e) { }
}
function setDot(id, ok, label) { const el = document.getElementById(id); if (el) el.innerHTML = `<span class="status-dot ${ok ? 'on' : 'off'}"></span> ${label}`; }

async function loadModels() {
  try { const r = await fetch('/v1/models'); const d = await r.json(); const sel = document.getElementById('model-select');
    if (sel && d.data?.length) {
      const local = d.data.filter(m => m.provider === 'local' || !m.provider);
      const cloud = d.data.filter(m => m.provider === 'cloud');
      let html = '';
      if (local.length) {
        html += '<optgroup label="🖥️ Local (Ollama)">';
        html += local.map(m => `<option value="${m.id}">${m.id}</option>`).join('');
        html += '</optgroup>';
      }
      if (cloud.length) {
        html += '<optgroup label="☁️ Cloud (OpenRouter)">';
        html += cloud.map(m => `<option value="${m.id}">${m.display_name || m.id}</option>`).join('');
        html += '</optgroup>';
      }
      sel.innerHTML = html || d.data.map(m => `<option value="${m.id}">${m.id}</option>`).join('');
    }
  } catch (e) { }
}

// ===== MODE =====
function setMode(mode) {
  S.mode = mode;
  document.querySelectorAll('.mode-tab').forEach(t => t.classList.toggle('active', t.dataset.mode === mode));
  const h = { rag: 'Tra cứu & Hỏi đáp', search: 'Tìm kiếm văn bản', llm: 'Hỏi AI trực tiếp' };
  const p = { rag: 'Bạn muốn hỏi gì?', search: 'Nhập từ khóa hoặc nội dung cần tìm...', llm: 'Hỏi AI bất kỳ điều gì...' };
  document.getElementById('input-hint').textContent = h[mode];
  document.getElementById('chat-input').placeholder = p[mode];
}

// ===== CONVERSATIONS =====
function saveConvs() { localStorage.setItem('vks_convs', JSON.stringify(S.convs)); }
function renderConvs() {
  const el = document.getElementById('conv-list'); if (!el) return;
  if (!S.convs.length) { el.innerHTML = '<div style="padding:24px;text-align:center;color:var(--text-muted);font-size:12px;">Chưa có cuộc trò chuyện</div>'; return; }
  el.innerHTML = S.convs.map(c => `
    <div class="conv-item ${c.id === S.convId ? 'active' : ''}" onclick="switchConv('${c.id}')">
      <svg class="icon-svg sm" style="color:var(--text-muted)"><use href="#i-chat"/></svg>
      <span class="conv-title">${esc(c.title)}</span>
      <button class="conv-delete" onclick="event.stopPropagation();delConv('${c.id}')"><svg class="icon-svg sm"><use href="#i-trash"/></svg></button>
    </div>`).join('');
}
function newConversation() {
  const id = 'c_' + Date.now();
  S.convs.unshift({ id, title: 'Cuộc trò chuyện mới', msgs: [], mode: S.mode });
  S.convId = id; S.msgs = []; saveConvs(); renderConvs(); renderMsgs();
  document.getElementById('chat-input').focus();
}
function switchConv(id) { const c = S.convs.find(x => x.id === id); if (!c) return; S.convId = id; S.msgs = c.msgs || []; if (c.mode) setMode(c.mode); renderConvs(); renderMsgs(); }
function delConv(id) { S.convs = S.convs.filter(c => c.id !== id); if (S.convId === id) { S.convId = null; S.msgs = []; renderMsgs(); } saveConvs(); renderConvs(); }

// ===== MESSAGES =====
function renderMsgs() {
  const box = document.getElementById('messages'), wel = document.getElementById('welcome');
  if (!box) return;
  if (!S.msgs.length) { box.innerHTML = ''; if (wel) wel.style.display = 'flex'; return; }
  if (wel) wel.style.display = 'none';

  box.innerHTML = S.msgs.map(m => {
    if (m.role === 'user') return `<div class="msg user">${esc(m.content)}</div>`;
    if (m.role === 'search') return `<div class="msg search-result">
      <div class="msg-label"><svg class="icon-svg sm"><use href="#i-search"/></svg> Kết quả tìm kiếm</div>
      ${(m.results || []).map((r, i) => `<div class="search-result-item"><div class="sr-title">[${i + 1}] ${esc(r.title || 'Văn bản pháp luật')}</div><div class="sr-content">${esc(r.content)}</div><div class="sr-score">Độ chính xác: ${(r.score * 100).toFixed(1)}%</div></div>`).join('')}
    </div>`;
    if (m.role === 'assistant') {
      let src = '';
      if (m.sources?.length) {
        src = `<div class="sources-panel"><button class="sources-toggle" onclick="toggleSrc(this)"><svg class="icon-svg sm"><use href="#i-book"/></svg> ${m.sources.length} nguồn pháp luật <svg class="icon-svg sm"><use href="#i-chevron"/></svg></button>
        <div class="sources-list">${m.sources.map((s, j) => `<div class="source-card"><div class="sc-head">[${j + 1}] ${esc(s.title || 'Văn bản pháp luật')}</div><div class="sc-body">${esc(trunc(s.content, 300))}</div><div class="sc-score">Độ chính xác: ${(s.score * 100).toFixed(1)}%</div></div>`).join('')}</div></div>`;
      }
      const lb = m.mode === 'llm' ? 'AI Trực tiếp' : 'Trợ lý Pháp luật';
      const agentBadge = m.agent ? `<span style="margin-left:8px;padding:2px 8px;background:rgba(99,102,241,0.1);border:1px solid rgba(99,102,241,0.3);border-radius:10px;font-size:10px;color:#818cf8;font-weight:600;">🤖 Agent: ${m.agent.intent} · ${m.agent.total_sources} nguồn</span>` : '';
      return `<div class="msg assistant"><div class="msg-label"><svg class="icon-svg sm"><use href="#i-scales"/></svg> ${lb}${agentBadge}</div><div class="msg-body">${fmtMd(m.content)}</div>${src}</div>`;
    }
    return '';
  }).join('');
  scrollDown();
}
function scrollDown() { const a = document.getElementById('chat-area'); if (a) a.scrollTop = a.scrollHeight; }
function toggleSrc(btn) { btn.nextElementSibling.classList.toggle('open'); btn.classList.toggle('open'); }

// ===== SEND =====
async function sendMessage() {
  const inp = document.getElementById('chat-input');
  const text = inp.value.trim();
  if (!text || S.streaming) return;
  if (!S.convId) newConversation();
  S.msgs.push({ role: 'user', content: text });
  const conv = S.convs.find(c => c.id === S.convId);
  if (conv && conv.title === 'Cuộc trò chuyện mới') { conv.title = text.substring(0, 50) + (text.length > 50 ? '...' : ''); conv.mode = S.mode; }
  inp.value = ''; inp.style.height = 'auto';
  renderMsgs(); showTyping(true); S.streaming = true;
  try {
    if (S.mode === 'search') await doSearch(text);
    else await doChat(text);
  } catch (e) { showTyping(false); S.msgs.push({ role: 'assistant', content: `Lỗi: ${e.message}`, mode: S.mode }); renderMsgs(); }
  S.streaming = false;
  if (conv) { conv.msgs = [...S.msgs]; saveConvs(); }
  renderConvs();
}

async function doChat(text) {
  const model = document.getElementById('model-select')?.value || 'qwen3:30b-a3b';
  const useRag = S.mode === 'rag';
  const msgs = S.msgs.filter(m => m.role === 'user' || m.role === 'assistant').map(m => ({ role: m.role, content: m.content }));
  const res = await fetch('/v1/chat/completions', {
    method: 'POST', headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${S.apiKey}` },
    body: JSON.stringify({ model, messages: msgs, stream: true, use_rag: useRag, temperature: 0.3, max_tokens: 8192 })
  });
  if (!res.ok) { const e = await res.json(); throw new Error(e.detail?.error?.message || `Lỗi ${res.status}`); }

  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let aMsg = { role: 'assistant', content: '', sources: [], mode: S.mode };
  S.msgs.push(aMsg); showTyping(false); renderMsgs();

  let buf = '';
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    while (buf.includes('\n\n')) {
      const idx = buf.indexOf('\n\n');
      const block = buf.substring(0, idx).trim();
      buf = buf.substring(idx + 2);
      if (!block.startsWith('data:')) continue;
      const raw = block.substring(5).trim();
      if (raw === '[DONE]') continue;
      try {
        const p = JSON.parse(raw);
        if (p.sources) { aMsg.sources = p.sources; if (p.agent) aMsg.agent = p.agent; renderMsgs(); continue; }
        const c = p.choices?.[0]?.delta?.content;
        if (c) { 
          aMsg.content += c; 
          const bodies = document.querySelectorAll('.msg.assistant .msg-body');
          if (bodies.length > 0) {
            bodies[bodies.length - 1].innerHTML = fmtMd(aMsg.content);
          } else {
            renderMsgs(); 
          }
          scrollDown(); 
        }
      } catch (e) { }
    }
  }
}

async function doSearch(query) {
  const res = await fetch('/v1/documents/search', {
    method: 'POST', headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${S.apiKey}` },
    body: JSON.stringify({ messages: [{ role: 'user', content: query }] })
  });
  if (!res.ok) { const e = await res.json(); throw new Error(e.detail?.error?.message || `Lỗi ${res.status}`); }
  const data = await res.json(); showTyping(false);
  if (data.sources?.length) S.msgs.push({ role: 'search', results: data.sources });
  else S.msgs.push({ role: 'assistant', content: 'Không tìm thấy văn bản phù hợp. Hãy thử từ khóa khác.', mode: 'search' });
  renderMsgs();
}

function showTyping(v) { const el = document.getElementById('typing'); if (el) el.className = v ? 'typing show' : 'typing'; }
function usePrompt(t) { document.getElementById('chat-input').value = t; sendMessage(); }

// ===== MODALS =====
function closeModal() { document.getElementById('modal-bg').classList.remove('show'); }

async function openApiKeysModal() {
  document.getElementById('modal-bg').classList.add('show');
  document.getElementById('modal-title').textContent = 'Quản lý API Keys';
  const body = document.getElementById('modal-content');
  try {
    const r = await fetch('/admin/api-keys', { headers: { 'Authorization': `Bearer ${S.token}` } });
    const d = await r.json();
    body.innerHTML = `
      <div style="display:flex;gap:8px;margin-bottom:18px;">
        <input type="text" id="nk-name" class="form-input" placeholder="Tên API key mới" style="flex:1;">
        <button class="btn btn-primary" style="width:auto;padding:10px 18px;" onclick="createKey()">Tạo khóa</button>
      </div>
      ${(d.keys || []).map(k => `
        <div class="key-card">
          <div style="display:flex;justify-content:space-between;align-items:center;">
            <div><div class="kc-name">${esc(k.name)}</div><div class="kc-preview">${k.key_preview}</div></div>
            <button class="btn-sm danger" onclick="revokeKey('${k.id}')">Thu hồi</button>
          </div>
          <div class="kc-meta"><span>Lượt dùng: ${k.total_requests}</span><span>Giới hạn: ${k.rate_limit}/phút</span><span style="color:${k.is_active ? 'var(--green)' : 'var(--red)'}">${k.is_active ? 'Hoạt động' : 'Thu hồi'}</span></div>
        </div>`).join('')}`;
  } catch (e) { body.innerHTML = `<p style="color:var(--red)">Lỗi: ${e.message}</p>`; }
}
async function createKey() {
  const name = document.getElementById('nk-name').value.trim(); if (!name) return;
  try {
    const r = await fetch('/admin/api-keys', { method: 'POST', headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${S.token}` }, body: JSON.stringify({ name }) });
    const d = await r.json();
    if (d.key) {
      // Show beautiful key popup instead of alert
      document.getElementById('modal-content').innerHTML = `
        <div style="text-align:center;padding:8px 0 16px;">
          <div style="width:56px;height:56px;background:linear-gradient(135deg,#22c55e,#16a34a);border-radius:50%;display:flex;align-items:center;justify-content:center;margin:0 auto 16px;box-shadow:0 4px 16px rgba(34,197,94,0.3);">
            <svg style="width:28px;height:28px;stroke:#fff;fill:none;stroke-width:2;stroke-linecap:round;stroke-linejoin:round;"><polyline points="20 6 9 17 4 12"/></svg>
          </div>
          <h3 style="font-size:18px;font-weight:700;margin-bottom:4px;">Tạo API Key Thành Công!</h3>
          <p style="color:var(--text-secondary);font-size:13px;margin-bottom:20px;">Key: <strong>${esc(name)}</strong></p>
        </div>
        <div style="background:var(--bg-input);border:1px solid var(--border);border-radius:var(--radius-sm);padding:14px 16px;margin-bottom:12px;position:relative;">
          <div style="font-size:10px;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.5px;font-weight:600;margin-bottom:8px;">🔑 API Key của bạn</div>
          <code id="new-key-value" style="font-family:'JetBrains Mono',monospace;font-size:12px;word-break:break-all;line-height:1.6;color:var(--accent);display:block;">${esc(d.key)}</code>
          <button onclick="copyNewKey()" id="copy-key-btn" style="position:absolute;top:12px;right:12px;padding:5px 12px;background:var(--accent);color:#fff;border:none;border-radius:6px;font-size:11px;font-weight:600;cursor:pointer;font-family:inherit;">Sao chép</button>
        </div>
        <div style="background:rgba(245,158,11,0.08);border:1px solid rgba(245,158,11,0.2);border-radius:var(--radius-sm);padding:12px 16px;display:flex;gap:10px;align-items:flex-start;">
          <span style="font-size:16px;flex-shrink:0;">⚠️</span>
          <div style="font-size:12px;color:#fbbf24;line-height:1.5;"><strong>Quan trọng:</strong> Đây là lần duy nhất key được hiển thị đầy đủ. Hãy sao chép và lưu trữ an toàn ngay bây giờ!</div>
        </div>
        <button class="btn btn-primary" style="width:100%;margin-top:16px;" onclick="openApiKeysModal()">Đã lưu, quay lại</button>`;
      document.getElementById('modal-title').textContent = '✅ Tạo Key Thành Công';
    }
  } catch (e) {
    document.getElementById('modal-content').innerHTML = `
      <div style="text-align:center;padding:20px 0;">
        <div style="font-size:40px;margin-bottom:12px;">❌</div>
        <p style="color:var(--red);font-size:14px;">Lỗi: ${esc(e.message)}</p>
        <button class="btn btn-primary" style="margin-top:16px;" onclick="openApiKeysModal()">Thử lại</button>
      </div>`;
  }
}
async function revokeKey(id) {
  if (!confirm('Thu hồi API key này?')) return;
  await fetch(`/admin/api-keys/${id}`, { method: 'DELETE', headers: { 'Authorization': `Bearer ${S.token}` } });
  await openApiKeysModal();
}

async function openRagModal() {
  document.getElementById('modal-bg').classList.add('show');
  document.getElementById('modal-title').textContent = 'Cơ sở dữ liệu pháp luật';
  const body = document.getElementById('modal-content');
  try {
    const r = await fetch('/admin/rag/status', { headers: { 'Authorization': `Bearer ${S.token}` } });
    const d = await r.json();
    body.innerHTML = `
      <div class="key-card" style="margin-bottom:18px;">
        <div class="kc-name">Trạng thái</div>
        <div class="kc-meta" style="flex-direction:column;gap:6px;margin-top:10px;">
          <span>Mô hình: ${d.embedding_model}</span>
          <span>Tổng số đoạn: ${d.total_chunks.toLocaleString()}</span>
          <span>Sẵn sàng: ${d.index_loaded ? 'Có' : 'Chưa'}</span>
          <span>Trạng thái: ${d.indexing_progress?.status || 'Sẵn sàng'}</span>
        </div>
      </div>
      <div style="margin-bottom:20px;">
        <h4 style="font-size:14px;font-weight:600;margin-bottom:10px;">Nạp dữ liệu từ HuggingFace</h4>
        <p style="font-size:12px;color:var(--text-secondary);margin-bottom:12px;">518.000+ văn bản pháp luật Việt Nam</p>
        <div style="display:flex;gap:8px;align-items:center;">
          <input type="number" id="idx-max" class="form-input" value="10000" style="width:130px;">
          <button class="btn btn-primary" style="width:auto;padding:10px 20px;" onclick="startIdx()">Bắt đầu nạp</button>
        </div>
      </div>
      <div>
        <h4 style="font-size:14px;font-weight:600;margin-bottom:10px;">Thêm văn bản thủ công</h4>
        <input type="text" id="doc-title" class="form-input" placeholder="Tên văn bản" style="margin-bottom:8px;">
        <textarea id="doc-content" class="form-input" placeholder="Nội dung văn bản pháp luật..." style="height:140px;resize:vertical;"></textarea>
        <button class="btn btn-primary" style="width:auto;padding:9px 18px;margin-top:10px;" onclick="addDoc()">Thêm</button>
      </div>`;
  } catch (e) { body.innerHTML = `<p style="color:var(--red)">Lỗi: ${e.message}</p>`; }
}
async function startIdx() { const n = parseInt(document.getElementById('idx-max').value) || 10000; await fetch(`/admin/rag/index?max_docs=${n}`, { method: 'POST', headers: { 'Authorization': `Bearer ${S.token}` } }); alert(`Đang nạp ${n.toLocaleString()} văn bản. Quá trình chạy nền.`); }
async function addDoc() {
  const title = document.getElementById('doc-title').value.trim(), content = document.getElementById('doc-content').value.trim();
  if (!content) return alert('Nhập nội dung'); const r = await fetch('/admin/rag/add-document', { method: 'POST', headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${S.token}` }, body: JSON.stringify({ title, content, doc_type: 'legal' }) });
  const d = await r.json(); alert(`Đã thêm ${d.chunks} đoạn`); document.getElementById('doc-title').value = ''; document.getElementById('doc-content').value = ''; checkHealth();
}

async function openStatsModal() {
  document.getElementById('modal-bg').classList.add('show');
  document.getElementById('modal-title').textContent = 'Thống kê sử dụng';
  const body = document.getElementById('modal-content');
  try {
    const r = await fetch('/admin/usage', { headers: { 'Authorization': `Bearer ${S.token}` } });
    const d = await r.json();
    body.innerHTML = `
      <div class="stat-grid">
        <div class="stat-card"><div class="sc-value">${d.total_requests}</div><div class="sc-label">Tổng yêu cầu</div></div>
        <div class="stat-card"><div class="sc-value">${(d.total_tokens || 0).toLocaleString()}</div><div class="sc-label">Tổng tokens</div></div>
        <div class="stat-card"><div class="sc-value">${d.requests_today}</div><div class="sc-label">Hôm nay</div></div>
        <div class="stat-card"><div class="sc-value">${d.avg_response_time_ms}ms</div><div class="sc-label">Thời gian TB</div></div>
      </div>
      <h4 style="font-size:14px;font-weight:600;margin-bottom:10px;">30 ngày gần nhất</h4>
      ${(d.daily_stats || []).map(s => `<div style="display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid var(--border);font-size:13px;"><span>${s.date}</span><span style="color:var(--text-secondary)">${s.requests} yêu cầu · ${(s.tokens || 0).toLocaleString()} tokens</span></div>`).join('') || '<p style="color:var(--text-muted);font-size:13px;">Chưa có dữ liệu</p>'}`;
  } catch (e) { body.innerHTML = `<p style="color:var(--red)">Lỗi: ${e.message}</p>`; }
}

function openSettingsModal() {
  document.getElementById('modal-bg').classList.add('show');
  document.getElementById('modal-title').textContent = 'Cài đặt';
  document.getElementById('modal-content').innerHTML = `
    <div class="key-card">
      <div class="kc-name">Đăng nhập quản trị</div>
      <div class="kc-meta" style="flex-direction:column;gap:8px;margin-top:12px;">
        <input type="text" id="s-user" class="form-input" placeholder="Tài khoản" value="admin">
        <input type="password" id="s-pass" class="form-input" placeholder="Mật khẩu">
        <button class="btn btn-primary" style="width:auto;padding:9px 18px;" onclick="adminLogin()">Đăng nhập</button>
      </div>
    </div>
    <div class="key-card" style="margin-top:12px;">
      <div class="kc-name">Xóa dữ liệu trò chuyện</div>
      <div class="kc-meta" style="margin-top:8px;"><button class="btn-sm danger" onclick="clearAll()">Xóa tất cả</button></div>
    </div>`;
}
async function adminLogin() {
  const u = document.getElementById('s-user').value, p = document.getElementById('s-pass').value;
  try {
    const r = await fetch('/admin/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ username: u, password: p }) });
    const d = await r.json(); if (!r.ok) throw new Error(d.detail?.error?.message || 'Sai mật khẩu');
    S.token = d.access_token; localStorage.setItem('vks_token', d.access_token);
    alert('Đăng nhập quản trị thành công!'); closeModal();
  } catch (e) { alert('Lỗi: ' + e.message); }
}
function clearAll() { if (!confirm('Xóa tất cả cuộc trò chuyện?')) return; S.convs = []; S.convId = null; S.msgs = []; saveConvs(); renderConvs(); renderMsgs(); closeModal(); }

// ===== HELPERS =====
function copyNewKey() {
  const key = document.getElementById('new-key-value').textContent;
  navigator.clipboard.writeText(key).then(() => {
    const btn = document.getElementById('copy-key-btn');
    btn.textContent = '✓ Đã sao chép!';
    btn.style.background = '#16a34a';
    setTimeout(() => { btn.textContent = 'Sao chép'; btn.style.background = ''; }, 2000);
  });
}
function esc(s) { const d = document.createElement('div'); d.textContent = s || ''; return d.innerHTML; }
function trunc(s, n) { return s && s.length > n ? s.substring(0, n) + '...' : s || ''; }
function fmtMd(t) { 
  if (!t) return ''; 
  if (typeof marked !== 'undefined') {
    return marked.parse(t);
  }
  let h = esc(t); 
  h = h.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>'); 
  h = h.replace(/`([^`]+)`/g, '<code>$1</code>'); 
  h = h.replace(/\n/g, '<br>'); 
  return h; 
}

// ===== BOOT =====
document.addEventListener('DOMContentLoaded', () => {
  const inp = document.getElementById('chat-input');
  if (inp) {
    inp.addEventListener('input', () => { inp.style.height = 'auto'; inp.style.height = Math.min(inp.scrollHeight, 140) + 'px'; });
    inp.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); } });
  }
  init();
});
