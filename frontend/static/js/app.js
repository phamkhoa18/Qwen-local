/**
 * VKS Legal AI - Frontend
 * 3 Chế độ: RAG (Tra cứu + Hỏi đáp), Search (Tìm kiếm văn bản), LLM (Hỏi AI trực tiếp)
 */

const S = {
  token: localStorage.getItem('vks_token') || null,
  apiKey: localStorage.getItem('vks_api_key') || null,
  convs: JSON.parse(localStorage.getItem('vks_convs') || '[]'),
  convId: null,
  msgs: [],
  streaming: false,
  mode: 'rag', // 'rag' | 'search' | 'llm'
};

// ============ AUTH ============
async function login() {
  const u = document.getElementById('login-user').value;
  const p = document.getElementById('login-pass').value;
  const err = document.getElementById('login-error');
  err.style.display = 'none';
  try {
    const r = await fetch('/admin/login', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({username:u, password:p})
    });
    const d = await r.json();
    if (!r.ok) throw new Error(d.detail?.error?.message || 'Đăng nhập thất bại');
    S.token = d.access_token;
    localStorage.setItem('vks_token', d.access_token);
    if (!S.apiKey) await autoKey();
    document.getElementById('login-overlay').style.display = 'none';
    init();
  } catch(e) { err.textContent = e.message; err.style.display = 'block'; }
}

async function autoKey() {
  try {
    const r = await fetch('/admin/api-keys', {
      method:'POST', headers:{'Content-Type':'application/json','Authorization':`Bearer ${S.token}`},
      body: JSON.stringify({name:'Khóa mặc định', description:'Tự động tạo'})
    });
    const d = await r.json();
    if (d.key) { S.apiKey = d.key; localStorage.setItem('vks_api_key', d.key); }
  } catch(e) {}
}

function logout() {
  localStorage.removeItem('vks_token');
  localStorage.removeItem('vks_api_key');
  location.reload();
}

// ============ INIT ============
async function init() {
  checkHealth();
  loadModels();
  renderConvs();
  setInterval(checkHealth, 30000);
}

async function checkHealth() {
  try {
    const r = await fetch('/admin/health');
    const d = await r.json();
    setStatus('st-ollama', d.ollama_connected, 'Ollama');
    setStatus('st-rag', d.rag_ready, 'RAG');
    const chEl = document.getElementById('st-chunks');
    if (chEl) chEl.textContent = `${d.total_legal_chunks} đoạn văn bản`;
    const badge = document.getElementById('rag-badge');
    if (badge) {
      if (d.rag_ready) {
        badge.className = 'rag-status ready';
        badge.innerHTML = `<span class="status-dot on"></span> ${d.total_legal_chunks.toLocaleString()} văn bản đã sẵn sàng`;
      } else {
        badge.className = 'rag-status off';
        badge.innerHTML = `<span class="status-dot off"></span> Chưa có dữ liệu`;
      }
    }
  } catch(e) {}
}

function setStatus(id, ok, label) {
  const el = document.getElementById(id);
  if (el) el.innerHTML = `<span class="status-dot ${ok?'on':'off'}"></span> ${label}`;
}

async function loadModels() {
  try {
    const r = await fetch('/v1/models');
    const d = await r.json();
    const sel = document.getElementById('model-select');
    if (sel && d.data?.length) sel.innerHTML = d.data.map(m=>`<option value="${m.id}">${m.id}</option>`).join('');
  } catch(e){}
}

// ============ MODE ============
function setMode(mode) {
  S.mode = mode;
  document.querySelectorAll('.mode-tab').forEach(t => t.classList.toggle('active', t.dataset.mode === mode));

  const hints = {
    rag: 'Chế độ: Tra cứu & Hỏi đáp — Kết hợp cơ sở dữ liệu pháp luật + AI',
    search: 'Chế độ: Tìm kiếm văn bản — Tìm trực tiếp trong cơ sở dữ liệu pháp luật',
    llm: 'Chế độ: Hỏi AI trực tiếp — Trò chuyện với AI không qua cơ sở dữ liệu'
  };
  const placeholders = {
    rag: 'Nhập câu hỏi pháp luật... (Enter để gửi)',
    search: 'Nhập từ khóa hoặc nội dung cần tìm kiếm...',
    llm: 'Nhập câu hỏi cho AI... (không sử dụng dữ liệu pháp luật)'
  };

  document.getElementById('input-hint').textContent = hints[mode];
  document.getElementById('chat-input').placeholder = placeholders[mode];
}

// ============ CONVERSATIONS ============
function saveConvs() { localStorage.setItem('vks_convs', JSON.stringify(S.convs)); }

function renderConvs() {
  const el = document.getElementById('conv-list');
  if (!el) return;
  if (!S.convs.length) {
    el.innerHTML = '<div style="padding:24px;text-align:center;color:var(--text-muted);font-size:12px;">Chưa có cuộc trò chuyện nào</div>';
    return;
  }
  el.innerHTML = S.convs.map(c => `
    <div class="conv-item ${c.id===S.convId?'active':''}" onclick="switchConv('${c.id}')">
      <svg class="icon-svg sm" style="color:var(--text-muted)"><use href="#i-chat"/></svg>
      <span class="conv-title">${esc(c.title)}</span>
      <button class="conv-delete" onclick="event.stopPropagation();delConv('${c.id}')">
        <svg class="icon-svg sm"><use href="#i-trash"/></svg>
      </button>
    </div>
  `).join('');
}

function newConversation() {
  const id = 'c_' + Date.now();
  S.convs.unshift({id, title:'Cuộc trò chuyện mới', msgs:[], mode:S.mode});
  S.convId = id; S.msgs = [];
  saveConvs(); renderConvs(); renderMsgs();
  document.getElementById('chat-input').focus();
}

function switchConv(id) {
  const c = S.convs.find(x=>x.id===id);
  if (!c) return;
  S.convId = id; S.msgs = c.msgs || [];
  if (c.mode) setMode(c.mode);
  renderConvs(); renderMsgs();
}

function delConv(id) {
  S.convs = S.convs.filter(c=>c.id!==id);
  if (S.convId===id) { S.convId=null; S.msgs=[]; renderMsgs(); }
  saveConvs(); renderConvs();
}

// ============ MESSAGES ============
function renderMsgs() {
  const box = document.getElementById('messages');
  const wel = document.getElementById('welcome');
  if (!box) return;

  if (!S.msgs.length) {
    box.innerHTML = ''; if(wel) wel.style.display='flex'; return;
  }
  if(wel) wel.style.display='none';

  box.innerHTML = S.msgs.map(m => {
    if (m.role==='user') return `<div class="msg user">${esc(m.content)}</div>`;

    if (m.role==='search') {
      return `<div class="msg search-result">
        <div class="msg-label"><svg class="icon-svg sm"><use href="#i-search"/></svg> Kết quả tìm kiếm</div>
        ${(m.results||[]).map((r,i)=>`
          <div class="search-result-item">
            <div class="sr-title">[${i+1}] ${esc(r.title||'Văn bản pháp luật')}</div>
            <div class="sr-content">${esc(r.content)}</div>
            <div class="sr-score">Độ chính xác: ${(r.score*100).toFixed(1)}%</div>
          </div>
        `).join('')}
      </div>`;
    }

    if (m.role==='assistant') {
      let srcHtml = '';
      if (m.sources?.length) {
        srcHtml = `<div class="sources-panel">
          <button class="sources-toggle" onclick="toggleSrc(this)">
            <svg class="icon-svg sm"><use href="#i-book"/></svg> ${m.sources.length} nguồn pháp luật
            <svg class="icon-svg sm"><use href="#i-chevron"/></svg>
          </button>
          <div class="sources-list">
            ${m.sources.map((s,j)=>`
              <div class="source-card">
                <div class="sc-head">[${j+1}] ${esc(s.title||'Văn bản pháp luật')}</div>
                <div class="sc-body">${esc(trunc(s.content,300))}</div>
                <div class="sc-score">Độ chính xác: ${(s.score*100).toFixed(1)}%</div>
              </div>
            `).join('')}
          </div>
        </div>`;
      }
      const modeLabel = m.mode==='llm' ? 'AI Trực tiếp' : 'Trợ lý Pháp luật';
      return `<div class="msg assistant">
        <div class="msg-label"><svg class="icon-svg sm"><use href="#i-scales"/></svg> ${modeLabel}</div>
        <div class="msg-body">${fmtMd(m.content)}</div>
        ${srcHtml}
      </div>`;
    }
    return '';
  }).join('');

  const area = document.getElementById('chat-area');
  if (area) area.scrollTop = area.scrollHeight;
}

function toggleSrc(btn) {
  const list = btn.nextElementSibling;
  list.classList.toggle('open');
  btn.classList.toggle('open');
}

// ============ SEND ============
async function sendMessage() {
  const inp = document.getElementById('chat-input');
  const text = inp.value.trim();
  if (!text || S.streaming) return;
  if (!S.convId) newConversation();

  S.msgs.push({role:'user', content:text});
  const conv = S.convs.find(c=>c.id===S.convId);
  if (conv && conv.title==='Cuộc trò chuyện mới') {
    conv.title = text.substring(0,50) + (text.length>50?'...':'');
    conv.mode = S.mode;
  }

  inp.value=''; inp.style.height='auto';
  renderMsgs(); showTyping(true); S.streaming=true;

  try {
    if (S.mode === 'search') {
      await doSearch(text);
    } else {
      await doChat(text);
    }
  } catch(e) {
    showTyping(false);
    S.msgs.push({role:'assistant', content:`Lỗi: ${e.message}`, mode: S.mode});
    renderMsgs();
  }

  S.streaming=false;
  if(conv) { conv.msgs=[...S.msgs]; saveConvs(); }
  renderConvs();
}

async function doChat(text) {
  const model = document.getElementById('model-select')?.value || 'qwen3:30b-a3b';
  const useRag = S.mode === 'rag';
  const msgs = S.msgs.filter(m=>m.role==='user'||m.role==='assistant').map(m=>({role:m.role==='search'?'assistant':m.role, content:m.role==='search'?JSON.stringify(m.results):m.content}));

  const res = await fetch('/v1/chat/completions', {
    method:'POST',
    headers:{'Content-Type':'application/json','Authorization':`Bearer ${S.apiKey}`},
    body: JSON.stringify({model, messages:msgs, stream:true, use_rag:useRag, temperature:0.3, max_tokens:4096})
  });

  if (!res.ok) { const e = await res.json(); throw new Error(e.detail?.error?.message || `Lỗi ${res.status}`); }

  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let aMsg = {role:'assistant', content:'', sources:[], mode:S.mode};
  S.msgs.push(aMsg);
  showTyping(false);

  let buf = '';
  while(true) {
    const {done,value} = await reader.read();
    if(done) break;
    buf += dec.decode(value, {stream:true});
    const lines = buf.split('\n'); buf = lines.pop()||'';
    for(const ln of lines) {
      if(!ln.startsWith('data: ')) continue;
      const raw = ln.slice(6).trim();
      if(raw==='[DONE]') continue;
      try {
        const p = JSON.parse(raw);
        if(p.sources) { aMsg.sources=p.sources; continue; }
        const c = p.choices?.[0]?.delta?.content;
        if(c) { aMsg.content+=c; renderMsgs(); }
      } catch(e){}
    }
  }
}

async function doSearch(query) {
  // Use RAG retrieve endpoint via a simple search
  const res = await fetch('/v1/chat/completions', {
    method:'POST',
    headers:{'Content-Type':'application/json','Authorization':`Bearer ${S.apiKey}`},
    body: JSON.stringify({
      model: document.getElementById('model-select')?.value || 'qwen3:30b-a3b',
      messages:[{role:'user',content:query}],
      stream:false, use_rag:true, temperature:0.1, max_tokens:100
    })
  });

  if (!res.ok) { const e = await res.json(); throw new Error(e.detail?.error?.message || `Lỗi ${res.status}`); }

  const data = await res.json();
  showTyping(false);

  // Show search results from sources
  if (data.sources?.length) {
    S.msgs.push({role:'search', results: data.sources});
  } else {
    S.msgs.push({role:'assistant', content:'Không tìm thấy văn bản pháp luật phù hợp. Hãy thử từ khóa khác hoặc kiểm tra cơ sở dữ liệu đã được nạp chưa.', mode:'search'});
  }
  renderMsgs();
}

function showTyping(v) { const el=document.getElementById('typing'); if(el) el.className=v?'typing show':'typing'; }
function usePrompt(t) { document.getElementById('chat-input').value=t; sendMessage(); }

// ============ MODALS ============
function closeModal() { document.getElementById('modal-bg').classList.remove('show'); }

async function openApiKeysModal() {
  document.getElementById('modal-bg').classList.add('show');
  document.getElementById('modal-title').textContent='Quản lý API Keys';
  const body = document.getElementById('modal-content');
  try {
    const r = await fetch('/admin/api-keys', {headers:{'Authorization':`Bearer ${S.token}`}});
    const d = await r.json();
    body.innerHTML = `
      <div style="display:flex;gap:8px;margin-bottom:18px;">
        <input type="text" id="nk-name" class="form-input" placeholder="Tên API key mới" style="flex:1;">
        <button class="btn btn-primary" style="width:auto;padding:10px 18px;" onclick="createKey()">Tạo khóa</button>
      </div>
      ${(d.keys||[]).map(k=>`
        <div class="key-card">
          <div style="display:flex;justify-content:space-between;align-items:center;">
            <div>
              <div class="kc-name">${esc(k.name)}</div>
              <div class="kc-preview">${k.key_preview}</div>
            </div>
            <div style="display:flex;gap:6px;">
              <button class="btn-sm danger" onclick="revokeKey('${k.id}')">Thu hồi</button>
            </div>
          </div>
          <div class="kc-meta">
            <span>Lượt dùng: ${k.total_requests}</span>
            <span>Giới hạn: ${k.rate_limit}/phút</span>
            <span style="color:${k.is_active?'var(--green)':'var(--red)'}">${k.is_active?'Đang hoạt động':'Đã thu hồi'}</span>
          </div>
        </div>
      `).join('')}`;
  } catch(e) { body.innerHTML=`<p style="color:var(--red)">Lỗi: ${e.message}</p>`; }
}

async function createKey() {
  const name = document.getElementById('nk-name').value.trim();
  if (!name) return;
  try {
    const r = await fetch('/admin/api-keys', {
      method:'POST', headers:{'Content-Type':'application/json','Authorization':`Bearer ${S.token}`},
      body: JSON.stringify({name})
    });
    const d = await r.json();
    if(d.key) { S.apiKey=d.key; localStorage.setItem('vks_api_key',d.key); alert('API Key mới:\n\n'+d.key+'\n\nVui lòng lưu lại! Khóa chỉ hiển thị một lần.'); }
    await openApiKeysModal();
  } catch(e) { alert('Lỗi: '+e.message); }
}

async function revokeKey(id) {
  if(!confirm('Bạn có chắc muốn thu hồi API key này?')) return;
  await fetch(`/admin/api-keys/${id}`, {method:'DELETE',headers:{'Authorization':`Bearer ${S.token}`}});
  await openApiKeysModal();
}

async function openRagModal() {
  document.getElementById('modal-bg').classList.add('show');
  document.getElementById('modal-title').textContent='Cơ sở dữ liệu pháp luật';
  const body = document.getElementById('modal-content');
  try {
    const r = await fetch('/admin/rag/status', {headers:{'Authorization':`Bearer ${S.token}`}});
    const d = await r.json();
    body.innerHTML = `
      <div class="key-card" style="margin-bottom:18px;">
        <div class="kc-name">Trạng thái Vector Store</div>
        <div class="kc-meta" style="flex-direction:column;gap:6px;margin-top:10px;">
          <span>Mô hình embedding: ${d.embedding_model}</span>
          <span>Tổng số đoạn: ${d.total_chunks.toLocaleString()}</span>
          <span>Đã sẵn sàng: ${d.index_loaded?'Có':'Chưa'}</span>
          <span>Trạng thái: ${d.indexing_progress?.status||'Sẵn sàng'}</span>
        </div>
      </div>
      <div style="margin-bottom:20px;">
        <h4 style="font-size:14px;font-weight:600;margin-bottom:10px;">Nạp dữ liệu từ HuggingFace</h4>
        <p style="font-size:12px;color:var(--text-secondary);margin-bottom:12px;">Dataset: th1nhng0/vietnamese-legal-documents — Hơn 518.000 văn bản pháp luật Việt Nam</p>
        <div style="display:flex;gap:8px;align-items:center;">
          <input type="number" id="idx-max" class="form-input" value="10000" style="width:130px;" placeholder="Số lượng">
          <button class="btn btn-primary" style="width:auto;padding:10px 20px;" onclick="startIdx()">Bắt đầu nạp</button>
        </div>
      </div>
      <div>
        <h4 style="font-size:14px;font-weight:600;margin-bottom:10px;">Thêm văn bản thủ công</h4>
        <input type="text" id="doc-title" class="form-input" placeholder="Tên văn bản (ví dụ: Bộ luật Hình sự 2015)" style="margin-bottom:8px;">
        <textarea id="doc-content" class="form-input" placeholder="Dán nội dung văn bản pháp luật vào đây..." style="height:140px;resize:vertical;"></textarea>
        <button class="btn btn-primary" style="width:auto;padding:9px 18px;margin-top:10px;" onclick="addDoc()">Thêm văn bản</button>
      </div>`;
  } catch(e) { body.innerHTML=`<p style="color:var(--red)">Lỗi: ${e.message}</p>`; }
}

async function startIdx() {
  const n = parseInt(document.getElementById('idx-max').value)||10000;
  const r = await fetch(`/admin/rag/index?max_docs=${n}`, {method:'POST',headers:{'Authorization':`Bearer ${S.token}`}});
  const d = await r.json();
  alert(`Đã bắt đầu nạp dữ liệu (${n.toLocaleString()} văn bản).\n\nQuá trình chạy nền, vui lòng kiểm tra lại sau vài phút.`);
}

async function addDoc() {
  const title = document.getElementById('doc-title').value.trim();
  const content = document.getElementById('doc-content').value.trim();
  if(!content) return alert('Vui lòng nhập nội dung văn bản');
  const r = await fetch('/admin/rag/add-document', {
    method:'POST', headers:{'Content-Type':'application/json','Authorization':`Bearer ${S.token}`},
    body: JSON.stringify({title,content,doc_type:'legal'})
  });
  const d = await r.json();
  alert(`Đã thêm ${d.chunks} đoạn vào cơ sở dữ liệu`);
  document.getElementById('doc-title').value='';
  document.getElementById('doc-content').value='';
  checkHealth();
}

async function openStatsModal() {
  document.getElementById('modal-bg').classList.add('show');
  document.getElementById('modal-title').textContent='Thống kê sử dụng';
  const body = document.getElementById('modal-content');
  try {
    const r = await fetch('/admin/usage', {headers:{'Authorization':`Bearer ${S.token}`}});
    const d = await r.json();
    body.innerHTML = `
      <div class="stat-grid">
        <div class="stat-card"><div class="sc-value">${d.total_requests}</div><div class="sc-label">Tổng yêu cầu</div></div>
        <div class="stat-card"><div class="sc-value">${(d.total_tokens||0).toLocaleString()}</div><div class="sc-label">Tổng tokens</div></div>
        <div class="stat-card"><div class="sc-value">${d.requests_today}</div><div class="sc-label">Hôm nay</div></div>
        <div class="stat-card"><div class="sc-value">${d.avg_response_time_ms}ms</div><div class="sc-label">Thời gian TB</div></div>
      </div>
      <h4 style="font-size:14px;font-weight:600;margin-bottom:10px;">30 ngày gần nhất</h4>
      ${(d.daily_stats||[]).map(s=>`
        <div style="display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid var(--border);font-size:13px;">
          <span>${s.date}</span>
          <span style="color:var(--text-secondary)">${s.requests} yêu cầu &middot; ${(s.tokens||0).toLocaleString()} tokens</span>
        </div>
      `).join('')||'<p style="color:var(--text-muted);font-size:13px;">Chưa có dữ liệu thống kê</p>'}`;
  } catch(e) { body.innerHTML=`<p style="color:var(--red)">Lỗi: ${e.message}</p>`; }
}

// ============ HELPERS ============
function esc(s) { const d=document.createElement('div'); d.textContent=s||''; return d.innerHTML; }
function trunc(s,n) { return s&&s.length>n?s.substring(0,n)+'...':s||''; }
function fmtMd(t) {
  if(!t) return '';
  let h = esc(t);
  h = h.replace(/\*\*(.*?)\*\*/g,'<strong>$1</strong>');
  h = h.replace(/`([^`]+)`/g,'<code>$1</code>');
  h = h.replace(/\n/g,'<br>');
  return h;
}

// ============ BOOT ============
document.addEventListener('DOMContentLoaded', () => {
  const inp = document.getElementById('chat-input');
  if(inp) {
    inp.addEventListener('input', ()=>{ inp.style.height='auto'; inp.style.height=Math.min(inp.scrollHeight,160)+'px'; });
    inp.addEventListener('keydown', e=>{ if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendMessage();} });
  }
  if(S.token) { document.getElementById('login-overlay').style.display='none'; init(); }
});
