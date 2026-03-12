from __future__ import annotations


def render_admin_shell() -> str:
    return """<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8">
    <title>账号管理系统</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
      :root {
        --bg: #f8fafc;
        --surface: #ffffff;
        --border: #e2e8f0;
        --text: #1e293b;
        --text-muted: #64748b;
        --accent: #0f172a;
        --accent-hover: #1e293b;
        --primary: #3b82f6;
        --danger: #ef4444;
        --success: #22c55e;
        --warning: #f59e0b;
        --sidebar-width: 350px;
      }
      * { box-sizing: border-box; }
      body {
        margin: 0;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        color: var(--text);
        background: var(--bg);
        height: 100vh;
        overflow: hidden;
      }
      button, input, select, textarea {
        font: inherit;
        border-radius: 6px;
        border: 1px solid var(--border);
        padding: 8px 12px;
      }
      button {
        cursor: pointer;
        background: var(--accent);
        color: white;
        border: none;
        transition: background 0.2s;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 6px;
      }
      button:hover { background: var(--accent-hover); }
      button.secondary {
        background: var(--surface);
        color: var(--text);
        border: 1px solid var(--border);
      }
      button.secondary:hover { background: var(--bg); }
      button.danger { background: var(--danger); }
      button:disabled { opacity: 0.5; cursor: not-allowed; }

      .app-container {
        display: flex;
        height: 100vh;
      }

      /* Sidebar - Account List */
      aside.sidebar {
        width: var(--sidebar-width);
        border-right: 1px solid var(--border);
        display: flex;
        flex-direction: column;
        background: var(--surface);
      }
      .sidebar-header {
        padding: 16px;
        border-bottom: 1px solid var(--border);
      }
      .sidebar-header h1 { margin: 0 0 12px 0; font-size: 1.25rem; }
      .search-box { width: 100%; margin-bottom: 12px; }
      .filter-row { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 12px; }
      
      .account-list-container {
        flex: 1;
        overflow-y: auto;
      }
      .account-item {
        padding: 12px 16px;
        border-bottom: 1px solid var(--border);
        cursor: pointer;
        transition: background 0.1s;
      }
      .account-item:hover { background: var(--bg); }
      .account-item.active { background: #eff6ff; border-left: 4px solid var(--primary); }
      .account-item .email { font-weight: 600; font-size: 0.95rem; margin-bottom: 4px; overflow: hidden; text-overflow: ellipsis; }
      .account-item .meta { font-size: 0.8rem; color: var(--text-muted); display: flex; gap: 8px; }
      
      .sidebar-footer {
        padding: 12px;
        border-top: 1px solid var(--border);
        display: flex;
        justify-content: space-between;
        align-items: center;
        font-size: 0.85rem;
      }

      /* Main Content */
      main.content {
        flex: 1;
        display: flex;
        flex-direction: column;
        overflow: hidden;
      }
      .content-header {
        padding: 16px 24px;
        background: var(--surface);
        border-bottom: 1px solid var(--border);
        display: flex;
        justify-content: space-between;
        align-items: center;
      }
      .stats-bar { display: flex; gap: 24px; }
      .stat-item { display: flex; flex-direction: column; }
      .stat-item .label { font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase; }
      .stat-item .value { font-weight: 700; font-size: 1.1rem; }

      .scroll-area {
        flex: 1;
        overflow-y: auto;
        padding: 24px;
      }

      .detail-card {
        background: var(--surface);
        border-radius: 12px;
        border: 1px solid var(--border);
        padding: 20px;
        margin-bottom: 24px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
      }
      .detail-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
        gap: 16px;
      }
      .info-box .label { font-size: 0.85rem; color: var(--text-muted); margin-bottom: 4px; }
      .info-box .val { font-weight: 500; }

      /* Inbox Styles */
      .inbox-section {
        display: flex;
        flex-direction: column;
        gap: 16px;
      }
      .inbox-toolbar {
        display: flex;
        justify-content: space-between;
        align-items: center;
      }
      .inbox-title { font-size: 1.25rem; font-weight: 700; margin: 0; }
      .inbox-controls { display: flex; gap: 12px; align-items: center; }
      .inbox-loading {
        display: none;
        align-items: center;
        gap: 8px;
        font-size: 0.85rem;
        color: var(--text-muted);
      }
      .inbox-loading.visible {
        display: inline-flex;
      }
      .inbox-loading-dot {
        width: 8px;
        height: 8px;
        border-radius: 999px;
        background: var(--primary);
        animation: inbox-pulse 0.9s ease-in-out infinite;
      }
      @keyframes inbox-pulse {
        0%, 100% { transform: scale(0.75); opacity: 0.45; }
        50% { transform: scale(1); opacity: 1; }
      }

      .message-list {
        display: flex;
        flex-direction: column;
        gap: 12px;
      }
      .message-item {
        background: var(--surface);
        border-radius: 8px;
        border: 1px solid var(--border);
        padding: 16px;
        transition: transform 0.1s;
      }
      .message-item:hover { transform: translateY(-1px); box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); }
      .message-header { display: flex; justify-content: space-between; margin-bottom: 8px; }
      .message-subject { font-weight: 700; color: var(--text); }
      .message-time { font-size: 0.8rem; color: var(--text-muted); }
      .message-from { font-size: 0.85rem; color: var(--primary); margin-bottom: 8px; }
      .message-body { font-size: 0.9rem; line-height: 1.5; white-space: pre-wrap; color: #475569; }
      
      .verification-code-box {
        margin-top: 12px;
        padding: 8px 12px;
        background: #fef3c7;
        border-left: 4px solid var(--warning);
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-radius: 4px;
      }
      .code-val { font-family: monospace; font-size: 1.2rem; font-weight: 700; color: #92400e; }

      /* Modals / Overlays */
      .overlay {
        position: fixed;
        top: 0; left: 0; right: 0; bottom: 0;
        background: rgba(0,0,0,0.5);
        display: none;
        align-items: center;
        justify-content: center;
        z-index: 100;
      }
      .modal {
        background: var(--surface);
        padding: 24px;
        border-radius: 12px;
        width: 500px;
        max-width: 90vw;
      }
      .modal-header { margin-bottom: 16px; display: flex; justify-content: space-between; }
      .modal-footer { margin-top: 20px; display: flex; justify-content: flex-end; gap: 12px; }

      /* Utility */
      .badge { font-size: 0.7rem; padding: 2px 6px; border-radius: 4px; font-weight: 600; text-transform: uppercase; }
      .badge-reg { background: #dcfce7; color: #166534; }
      .badge-unreg { background: #fee2e2; color: #991b1b; }
      .badge-primary { background: #dbeafe; color: #1e40af; }
      
      .empty-state {
        text-align: center;
        padding: 48px;
        color: var(--text-muted);
      }
      
      .pager { display: flex; gap: 4px; align-items: center; }
      .pager button { padding: 4px 8px; min-width: 32px; }
      
      #loading-overlay {
        position: fixed; top: 0; left: 0; right: 0; bottom: 0;
        background: rgba(255,255,255,0.7);
        display: none; align-items: center; justify-content: center;
        z-index: 200; font-weight: 600;
      }

      /* Batch & Import Bar */
      .tools-row {
        display: flex; gap: 12px; padding: 16px 24px; background: var(--surface); border-bottom: 1px solid var(--border);
      }
    </style>
  </head>
  <body>
    <div id="loading-overlay">加载中...</div>
    
    <div class="app-container">
      <aside class="sidebar">
        <div class="sidebar-header">
          <h1>账号管理</h1>
          <input id="account-search" class="search-box" type="search" placeholder="搜索邮箱/备注...">
          <div class="filter-row">
            <select id="group-filter">
              <option value="">所有分组</option>
            </select>
            <select id="status-filter">
              <option value="">所有状态</option>
              <option value="registered">已注册</option>
              <option value="unregistered">未注册</option>
            </select>
          </div>
          <div style="display: flex; gap: 8px;">
            <button id="refresh-accounts" class="secondary" style="flex: 1;">刷新列表</button>
            <button id="show-import" class="secondary">导入</button>
          </div>
        </div>
        
        <div id="account-list" class="account-list-container">
          <!-- Account items injected here -->
        </div>
        
        <div class="sidebar-footer">
          <div id="account-pagination" class="pager">
            <button id="prev-page" disabled>&lt;</button>
            <span id="page-info">1 / 1</span>
            <button id="next-page" disabled>&gt;</button>
          </div>
          <div id="total-count" class="muted">共 0 条</div>
        </div>
      </aside>
      
      <main class="content">
        <header class="content-header">
          <div class="stats-bar">
            <div class="stat-item">
              <span class="label">账号总数</span>
              <span id="stat-total" class="value">0</span>
            </div>
            <div class="stat-item">
              <span class="label">已注册</span>
              <span id="stat-registered" class="value">0</span>
            </div>
            <div class="stat-item">
              <span class="label">主账号</span>
              <span id="stat-primary" class="value">0</span>
            </div>
          </div>
          <div class="actions">
            <button id="show-batch" class="secondary">批量操作</button>
            <button id="export-button" class="secondary">导出 JSON</button>
          </div>
        </header>
        
        <div class="scroll-area">
          <div id="welcome-screen" class="empty-state">
            <h2>请从左侧选择一个账号</h2>
            <p>点击账号后可以查看详情并接收验证码</p>
          </div>
          
          <div id="detail-view" style="display: none;">
            <section id="account-detail-panel" class="detail-card">
              <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 20px;">
                <div style="display: flex; align-items: center; gap: 12px;">
                  <h2 id="detail-email" style="margin: 0; font-size: 1.5rem;">email@example.com</h2>
                  <button class="secondary" style="padding: 4px 8px; font-size: 0.8rem;" onclick="copyToClipboard($('detail-email').textContent)">复制</button>
                </div>
                <div style="display: flex; gap: 8px;">
                  <button id="change-group-btn" class="secondary">加入分组</button>
                  <button id="toggle-reg-btn" class="secondary">切换注册状态</button>
                  <button id="toggle-pri-btn" class="secondary">切换主账号</button>
                </div>
              </div>
              <div class="detail-grid">
                <div class="info-box">
                  <div class="label">所属分组</div>
                  <div id="detail-group" class="val">-</div>
                </div>
                <div class="info-box">
                  <div class="label">注册状态</div>
                  <div id="detail-status" class="val">-</div>
                </div>
                <div class="info-box">
                  <div class="label">最后更新</div>
                  <div id="detail-updated" class="val">-</div>
                </div>
              </div>
            </section>
            
            <section class="inbox-section">
              <div class="inbox-toolbar">
                <h3 class="inbox-title">收件箱</h3>
                <div class="inbox-controls">
                  <div id="inbox-loading-indicator" class="inbox-loading" aria-live="polite">
                    <span class="inbox-loading-dot"></span>
                    <span>加载邮件中</span>
                  </div>
                  <label style="display: flex; align-items: center; gap: 4px; font-size: 0.85rem; cursor: pointer;">
                    <input type="checkbox" id="auto-refresh-check"> 自动刷新
                  </label>
                  <div id="inbox-pagination" class="pager" style="display: none;">
                    <button id="inbox-prev">&lt;</button>
                    <span id="inbox-page-info">1 / 1</span>
                    <button id="inbox-next">&gt;</button>
                  </div>
                  <button id="refresh-inbox-btn" class="secondary">刷新邮件</button>
                </div>
              </div>
              
              <div id="inbox-panel" class="message-list">
                <div id="inbox-container"></div>
              </div>
            </section>
          </div>
        </div>
      </main>
    </div>

    <!-- Import Modal -->
    <div id="import-overlay" class="overlay">
      <div class="modal">
        <div class="modal-header">
          <h2 style="margin: 0;">导入账号</h2>
          <button class="secondary" onclick="closeModal('import-overlay')">✕</button>
        </div>
        <p class="text-muted" style="font-size: 0.85rem; margin-bottom: 12px;">请输入原始文本行，每行一个账号。</p>
        <textarea id="import-textarea" style="width: 100%; height: 200px; margin-bottom: 12px;" placeholder="粘贴账号数据..."></textarea>
        <div class="modal-footer">
          <button class="secondary" onclick="closeModal('import-overlay')">取消</button>
          <button id="import-button">开始导入</button>
        </div>
      </div>
    </div>

    <!-- Batch Modal -->
    <div id="batch-overlay" class="overlay">
      <div class="modal">
        <div class="modal-header">
          <h2 style="margin: 0;">批量更新</h2>
          <button class="secondary" onclick="closeModal('batch-overlay')">✕</button>
        </div>
        <div style="display: flex; flex-direction: column; gap: 12px;">
          <div>
            <label class="label">修改分组</label>
            <input id="batch-group-input" type="text" placeholder="留空不修改，或输入新分组名">
          </div>
          <div>
            <label class="label">注册状态</label>
            <select id="batch-registered-input">
              <option value="">不修改</option>
              <option value="true">设为已注册</option>
              <option value="false">设为未注册</option>
            </select>
          </div>
          <div>
            <label class="label">主账号状态</label>
            <select id="batch-primary-input">
              <option value="">不修改</option>
              <option value="true">设为是</option>
              <option value="false">设为否</option>
            </select>
          </div>
          <p style="font-size: 0.8rem; color: var(--danger);">* 注意：仅对左侧当前过滤出的所有账号生效。</p>
        </div>
        <div class="modal-footer">
          <button class="secondary" onclick="closeModal('batch-overlay')">取消</button>
          <button id="apply-batch-button">应用更改</button>
        </div>
      </div>
    </div>

    <!-- Change Group Modal -->
    <div id="group-overlay" class="overlay">
      <div class="modal">
        <div class="modal-header">
          <h2 style="margin: 0;">加入分组</h2>
          <button class="secondary" onclick="closeModal('group-overlay')">✕</button>
        </div>
        <div style="display: flex; flex-direction: column; gap: 12px;">
          <div>
            <label class="label">选择或输入分组名</label>
            <input id="group-input" type="text" list="group-datalist" placeholder="输入新分组名或选择已有分组" style="width: 100%;">
            <datalist id="group-datalist"></datalist>
          </div>
          <p style="font-size: 0.8rem; color: var(--text-muted);">* 输入新分组名将自动创建。</p>
        </div>
        <div class="modal-footer">
          <button class="secondary" onclick="closeModal('group-overlay')">取消</button>
          <button id="apply-group-button">保存</button>
        </div>
      </div>
    </div>

    <script>
      const CONFIG = {
        accountsPerPage: 50,
        inboxPerPage: 5,
        refreshInterval: 10000
      };

      const state = {
        accounts: [],
        totalAccounts: 0,
        currentPage: 1,
        selectedAccountId: null,
        selectedAccount: null,
        inbox: [],
        inboxPage: 1,
        autoRefreshTimer: null,
        allGroups: []
      };

      // --- Utilities ---
      function $(id) { return document.getElementById(id); }
      function showLoading(show) { $("loading-overlay").style.display = show ? "flex" : "none"; }
      function openModal(id) { $(id).style.display = "flex"; }
      function closeModal(id) { $(id).style.display = "none"; }

      async function api(path, options = {}) {
        const opts = { credentials: "same-origin", ...options };
        opts.headers = { "Content-Type": "application/json", ...(options.headers || {}) };
        if (opts.body && typeof opts.body === "object") opts.body = JSON.stringify(opts.body);
        
        const res = await fetch(path, opts);
        if (!res.ok) {
          const text = await res.text();
          throw new Error(text || `Error ${res.status}`);
        }
        return res.headers.get("Content-Type")?.includes("application/json") ? res.json() : res.text();
      }

      function extractCode(text) {
        if (!text) return null;
        const patterns = [/\\b(\\d{6})\\b/, /code[:\\s]+(\\d{6})/i, /验证码[:\\s]+(\\d{6})/];
        for (const p of patterns) {
          const m = text.match(p);
          if (m) return m[1];
        }
        return null;
      }

      function copyToClipboard(text) {
        navigator.clipboard.writeText(text).then(() => {
          alert("已复制到剪贴板: " + text);
        });
      }

      // --- Core Actions ---

      async function loadSummary() {
        const s = await api("/api/summary");
        $("stat-total").textContent = s.accounts;
        $("stat-registered").textContent = s.registered;
        $("stat-primary").textContent = s.primary;

        // Store groups for datalist
        state.allGroups = Object.keys(s.groups).sort();

        const gFilter = $("group-filter");
        const current = gFilter.value;
        gFilter.innerHTML = '<option value="">所有分组</option>';
        state.allGroups.forEach(g => {
          const opt = document.createElement("option");
          opt.value = g;
          opt.textContent = g || "(无分组)";
          gFilter.appendChild(opt);
        });
        gFilter.value = current;
      }

      async function loadGroupsDatalist() {
        const groups = await api("/api/groups");
        state.allGroups = groups;
        const datalist = $("group-datalist");
        datalist.innerHTML = "";
        groups.forEach(g => {
          const opt = document.createElement("option");
          opt.value = g;
          datalist.appendChild(opt);
        });
      }

      async function loadAccounts(page = 1) {
        state.currentPage = page;
        const query = $("account-search").value;
        const group = $("group-filter").value;
        const status = $("status-filter").value;
        
        const params = new URLSearchParams({
          limit: CONFIG.accountsPerPage,
          offset: (page - 1) * CONFIG.accountsPerPage,
          query: query
        });
        if (group) params.set("group_name", group);
        if (status === "registered") params.set("is_registered", "true");
        if (status === "unregistered") params.set("is_registered", "false");

        const data = await api(`/api/accounts?${params}`);
        state.accounts = data.items;
        state.totalAccounts = data.total;
        renderAccountList();
      }

      function renderAccountList() {
        const list = $("account-list");
        list.innerHTML = "";
        
        if (state.accounts.length === 0) {
          list.innerHTML = '<div class="empty-state">未找到账号</div>';
        } else {
          state.accounts.forEach(acc => {
            const item = document.createElement("div");
            item.className = `account-item ${state.selectedAccountId === acc.id ? "active" : ""}`;
            item.onclick = () => selectAccount(acc);
            
            const badges = [];
            if (acc.is_registered) badges.push('<span class="badge badge-reg">已注册</span>');
            if (acc.is_primary) badges.push('<span class="badge badge-primary">主账号</span>');
            
            item.innerHTML = `
              <div class="email" title="${acc.email}">${acc.email}</div>
              <div class="meta">
                <span>${acc.group_name || "默认"}</span>
                ${badges.join(" ")}
              </div>
            `;
            list.appendChild(item);
          });
        }
        
        // Pager update
        const totalPages = Math.ceil(state.totalAccounts / CONFIG.accountsPerPage) || 1;
        $("page-info").textContent = `${state.currentPage} / ${totalPages}`;
        $("prev-page").disabled = state.currentPage <= 1;
        $("next-page").disabled = state.currentPage >= totalPages;
        $("total-count").textContent = `共 ${state.totalAccounts} 条`;
      }

      async function selectAccount(acc) {
        state.selectedAccountId = acc.id;
        state.selectedAccount = acc;
        renderAccountList();
        
        $("welcome-screen").style.display = "none";
        $("detail-view").style.display = "block";
        
        $("detail-email").textContent = acc.email;
        $("detail-group").textContent = acc.group_name || "默认";
        $("detail-status").innerHTML = acc.is_registered ? 
          '<span class="badge badge-reg">已注册</span>' : 
          '<span class="badge badge-unreg">未注册</span>';
        $("detail-updated").textContent = new Date(acc.updated_at).toLocaleString();
        
        state.inboxPage = 1;
        await fetchInbox();
      }

      async function fetchInbox() {
        if (!state.selectedAccountId) return;
        $("inbox-loading-indicator").classList.add("visible");
        $("refresh-inbox-btn").disabled = true;
        try {
          const data = await api(`/api/accounts/${state.selectedAccountId}/inbox`);
          state.inbox = data.messages;
          renderInbox();
        } catch (e) {
          console.error(e);
          $("inbox-container").innerHTML = `<div class="empty-state" style="color:var(--danger)">加载失败: ${e.message}</div>`;
        } finally {
          $("inbox-loading-indicator").classList.remove("visible");
          $("refresh-inbox-btn").disabled = false;
        }
      }

      function renderInbox() {
        const container = $("inbox-container");
        container.innerHTML = "";
        
        if (!state.inbox || state.inbox.length === 0) {
          container.innerHTML = '<div class="empty-state">收件箱为空</div>';
          $("inbox-pagination").style.display = "none";
          return;
        }

        const start = (state.inboxPage - 1) * CONFIG.inboxPerPage;
        const pageItems = state.inbox.slice(start, start + CONFIG.inboxPerPage);
        
        pageItems.forEach(msg => {
          const article = document.createElement("div");
          article.className = "message-item";
          
          const code = extractCode(msg.body_text || msg.body_preview);
          let codeHtml = "";
          if (code) {
            codeHtml = `
              <div class="verification-code-box">
                <div>验证码: <span class="code-val">${code}</span></div>
                <button class="secondary" style="padding: 2px 8px; font-size: 0.8rem;" onclick="copyToClipboard('${code}')">复制</button>
              </div>
            `;
          }
          
          article.innerHTML = `
            <div class="message-header">
              <span class="message-subject">${msg.subject || "(无主题)"}</span>
              <span class="message-time">${new Date(msg.received_at).toLocaleString()}</span>
            </div>
            <div class="message-from">${msg.from_address}</div>
            <div class="message-body">${msg.body_text || msg.body_preview || "(无内容)"}</div>
            ${codeHtml}
          `;
          container.appendChild(article);
        });

        const totalPages = Math.ceil(state.inbox.length / CONFIG.inboxPerPage);
        if (totalPages > 1) {
          $("inbox-pagination").style.display = "flex";
          $("inbox-page-info").textContent = `${state.inboxPage} / ${totalPages}`;
          $("inbox-prev").disabled = state.inboxPage <= 1;
          $("inbox-next").disabled = state.inboxPage >= totalPages;
        } else {
          $("inbox-pagination").style.display = "none";
        }
      }

      async function applyBulkUpdate() {
        const emails = state.accounts.map(a => a.email);
        if (!emails.length) return;

        const body = {};
        const group = $("batch-group-input").value.trim();
        const reg = $("batch-registered-input").value;
        const pri = $("batch-primary-input").value;

        if (group) body.group_name = group;
        if (reg) body.is_registered = reg === "true";
        if (pri) body.is_primary = pri === "true";

        if (Object.keys(body).length === 0) return;
        body.emails = emails;

        showLoading(true);
        try {
          await api("/api/accounts/bulk-update", { method: "POST", body });
          closeModal("batch-overlay");
          await $("refresh-accounts").onclick();
        } catch (e) { alert(e.message); }
        showLoading(false);
      }

      async function changeAccountGroup() {
        if (!state.selectedAccountId) return;
        const groupName = $("group-input").value.trim();
        if (!groupName) {
          alert("请输入分组名");
          return;
        }

        showLoading(true);
        try {
          await api(`/api/accounts/${state.selectedAccountId}`, {
            method: "PATCH",
            body: { group_name: groupName }
          });
          closeModal("group-overlay");
          $("group-input").value = "";
          // Refresh account details
          const updated = await api(`/api/accounts?query=${state.selectedAccount.email}`);
          if (updated.items.length) selectAccount(updated.items[0]);
          loadSummary();
          loadAccounts(state.currentPage);
        } catch (e) { alert(e.message); }
        showLoading(false);
      }

      function openGroupModal() {
        loadGroupsDatalist();
        $("group-input").value = state.selectedAccount?.group_name || "";
        openModal("group-overlay");
      }

      async function importSources() {
        const text = $("import-textarea").value;
        if (!text.trim()) return;
        showLoading(true);
        try {
          await api("/api/accounts/import-txt", {
            method: "POST",
            body: { sources: [{ source_name: "web-import.txt", text }] }
          });
          closeModal("import-overlay");
          $("import-textarea").value = "";
          await $("refresh-accounts").onclick();
        } catch (e) { alert(e.message); }
        showLoading(false);
      }

      // --- Event Handlers ---

      $("refresh-accounts").onclick = async () => {
        showLoading(true);
        await Promise.all([loadSummary(), loadAccounts(1)]);
        showLoading(false);
      };

      $("prev-page").onclick = () => loadAccounts(state.currentPage - 1);
      $("next-page").onclick = () => loadAccounts(state.currentPage + 1);
      
      $("account-search").oninput = debounce(() => loadAccounts(1), 500);
      $("group-filter").onchange = () => loadAccounts(1);
      $("status-filter").onchange = () => loadAccounts(1);

      $("inbox-prev").onclick = () => { state.inboxPage--; renderInbox(); };
      $("inbox-next").onclick = () => { state.inboxPage++; renderInbox(); };
      $("refresh-inbox-btn").onclick = () => fetchInbox();

      $("auto-refresh-check").onchange = (e) => {
        if (e.target.checked) {
          state.autoRefreshTimer = setInterval(fetchInbox, CONFIG.refreshInterval);
        } else {
          clearInterval(state.autoRefreshTimer);
        }
      };

      $("show-import").onclick = () => openModal("import-overlay");
      $("import-button").onclick = () => importSources();

      $("show-batch").onclick = () => openModal("batch-overlay");
      $("apply-batch-button").onclick = () => applyBulkUpdate();

      $("change-group-btn").onclick = () => openGroupModal();
      $("apply-group-button").onclick = () => changeAccountGroup();

      $("export-button").onclick = () => {
        const group = $("group-filter").value;
        const url = `/api/accounts/export${group ? "?group_name=" + encodeURIComponent(group) : ""}`;
        window.open(url, "_blank");
      };

      $("toggle-reg-btn").onclick = async () => {
        if (!state.selectedAccount) return;
        await api(`/api/accounts/${state.selectedAccountId}`, {
          method: "PATCH",
          body: { is_registered: !state.selectedAccount.is_registered }
        });
        const updated = await api(`/api/accounts?query=${state.selectedAccount.email}`);
        if (updated.items.length) selectAccount(updated.items[0]);
        loadSummary();
        loadAccounts(state.currentPage);
      };

      $("toggle-pri-btn").onclick = async () => {
        if (!state.selectedAccount) return;
        await api(`/api/accounts/${state.selectedAccountId}`, {
          method: "PATCH",
          body: { is_primary: !state.selectedAccount.is_primary }
        });
        const updated = await api(`/api/accounts?query=${state.selectedAccount.email}`);
        if (updated.items.length) selectAccount(updated.items[0]);
        loadSummary();
        loadAccounts(state.currentPage);
      };

      function debounce(fn, delay) {
        let timer;
        return function() {
          clearTimeout(timer);
          timer = setTimeout(() => fn.apply(this, arguments), delay);
        };
      }

      // Init
      window.onload = () => $("refresh-accounts").onclick();
    </script>
  </body>
</html>
"""
