from __future__ import annotations


ADMIN_SHELL_JS = """
const CONFIG = { accountsPerPage: 50, inboxPerPage: 5, refreshInterval: 10000 };
const state = {
  accounts: [],
  totalAccounts: 0,
  currentPage: 1,
  selectedAccount: null,
  selectedAccountId: null,
  inbox: [],
  inboxPage: 1,
  autoRefreshTimer: null,
  allGroups: [],
};

function $(id) { return document.getElementById(id); }
function showLoading(show) { $("loading-overlay").style.display = show ? "flex" : "none"; }
function openModal(id) { $(id).style.display = "flex"; }
function closeModal(id) { $(id).style.display = "none"; }

async function api(path, options = {}) {
  const request = { credentials: "same-origin", ...options };
  request.headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (request.body && typeof request.body === "object") {
    request.body = JSON.stringify(request.body);
  }
  const response = await fetch(path, request);
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Error ${response.status}`);
  }
  return response.headers.get("Content-Type")?.includes("application/json") ? response.json() : response.text();
}

async function copyToClipboard(text) {
  await navigator.clipboard.writeText(text);
}

async function loadSummary() {
  const summary = await api("/api/summary");
  $("stat-total").textContent = summary.accounts;
  $("stat-registered").textContent = summary.registered;
  $("stat-primary").textContent = summary.primary;
  state.allGroups = Object.keys(summary.groups).sort();
  const groupFilter = $("group-filter");
  const selected = groupFilter.value;
  groupFilter.innerHTML = '<option value="">所有分组</option>';
  state.allGroups.forEach((groupName) => {
    const option = document.createElement("option");
    option.value = groupName;
    option.textContent = groupName || "(无分组)";
    groupFilter.appendChild(option);
  });
  groupFilter.value = selected;
}

async function loadAccounts(page = 1) {
  state.currentPage = page;
  const params = new URLSearchParams({
    limit: String(CONFIG.accountsPerPage),
    offset: String((page - 1) * CONFIG.accountsPerPage),
    query: $("account-search").value,
  });
  const groupName = $("group-filter").value;
  const status = $("status-filter").value;
  if (groupName) params.set("group_name", groupName);
  if (status === "registered") params.set("is_registered", "true");
  if (status === "unregistered") params.set("is_registered", "false");
  const payload = await api(`/api/accounts?${params.toString()}`);
  state.accounts = payload.items;
  state.totalAccounts = payload.total;
  renderAccountList();
}

function renderAccountList() {
  const list = $("account-list");
  list.innerHTML = "";
  if (!state.accounts.length) {
    list.innerHTML = '<div class="empty-state">未找到账号</div>';
  } else {
    state.accounts.forEach((account) => {
      const item = document.createElement("div");
      item.className = `account-item ${state.selectedAccountId === account.id ? "active" : ""}`;
      item.onclick = () => void selectAccount(account);
      const badges = [];
      if (account.is_registered) badges.push('<span class="badge badge-reg">已注册</span>');
      if (account.is_primary) badges.push('<span class="badge badge-primary">主账号</span>');
      item.innerHTML = `
        <div class="email" title="${account.email}">${account.email}</div>
        <div class="meta"><span>${account.group_name || "默认"}</span>${badges.join(" ")}</div>
      `;
      list.appendChild(item);
    });
  }
  const totalPages = Math.max(1, Math.ceil(state.totalAccounts / CONFIG.accountsPerPage));
  $("page-info").textContent = `${state.currentPage} / ${totalPages}`;
  $("prev-page").disabled = state.currentPage <= 1;
  $("next-page").disabled = state.currentPage >= totalPages;
  $("total-count").textContent = `共 ${state.totalAccounts} 条`;
}

function renderSelectedAccountDetail(account) {
  $("welcome-screen").style.display = "none";
  $("detail-view").style.display = "block";
  $("detail-email").textContent = account.email;
  $("detail-group").textContent = account.group_name || "默认";
  $("detail-status").innerHTML = account.is_registered
    ? '<span class="badge badge-reg">已注册</span>'
    : '<span class="badge badge-unreg">未注册</span>';
  $("detail-updated").textContent = new Date(account.updated_at).toLocaleString();
}

async function refreshSelectedAccountDetail() {
  if (!state.selectedAccount) return;
  const params = new URLSearchParams({
    query: state.selectedAccount.email,
    limit: "1",
    offset: "0",
  });
  const payload = await api(`/api/accounts?${params.toString()}`);
  const updated = payload.items.find((account) => account.email === state.selectedAccount.email);
  if (!updated) {
    state.selectedAccount = null;
    state.selectedAccountId = null;
    $("detail-view").style.display = "none";
    $("welcome-screen").style.display = "block";
    renderAccountList();
    return;
  }
  state.selectedAccount = updated;
  state.selectedAccountId = updated.id;
  renderAccountList();
  renderSelectedAccountDetail(updated);
}

async function selectAccount(account) {
  state.selectedAccount = account;
  state.selectedAccountId = account.id;
  renderAccountList();
  renderSelectedAccountDetail(account);
  state.inboxPage = 1;
  await fetchInbox();
}

async function fetchInbox() {
  if (!state.selectedAccountId) return;
  $("inbox-loading-indicator").classList.add("visible");
  $("refresh-inbox-btn").disabled = true;
  try {
    const payload = await api(`/api/accounts/${state.selectedAccountId}/inbox`);
    state.inbox = payload.messages;
    renderInbox();
  } catch (error) {
    $("inbox-container").innerHTML = `<div class="empty-state" style="color:#ef4444;">加载失败: ${error.message}</div>`;
  } finally {
    $("inbox-loading-indicator").classList.remove("visible");
    $("refresh-inbox-btn").disabled = false;
  }
}

function renderInbox() {
  const container = $("inbox-container");
  container.innerHTML = "";
  if (!state.inbox.length) {
    container.innerHTML = '<div class="empty-state">收件箱为空</div>';
    $("inbox-pagination").style.display = "none";
    return;
  }

  const start = (state.inboxPage - 1) * CONFIG.inboxPerPage;
  const pageItems = state.inbox.slice(start, start + CONFIG.inboxPerPage);
  pageItems.forEach((message) => {
    const item = document.createElement("article");
    item.className = "message-item";
    const codeHtml = message.verification_code
      ? `<div class="verification-code-box"><div>验证码: <span class="code-val">${message.verification_code}</span></div><button class="secondary" data-copy-code="${message.verification_code}">复制</button></div>`
      : "";
    item.innerHTML = `
      <div class="message-header">
        <strong>${message.subject || "(无主题)"}</strong>
        <span class="muted">${message.received_at ? new Date(message.received_at).toLocaleString() : "-"}</span>
      </div>
      <div class="message-from">${message.from_address || ""}</div>
      <div class="message-body">${message.body_text || message.body_preview || "(无内容)"}</div>
      ${codeHtml}
    `;
    container.appendChild(item);
  });
  container.querySelectorAll("[data-copy-code]").forEach((button) => {
    button.addEventListener("click", () => void copyToClipboard(button.getAttribute("data-copy-code") || ""));
  });

  const totalPages = Math.ceil(state.inbox.length / CONFIG.inboxPerPage);
  $("inbox-pagination").style.display = totalPages > 1 ? "flex" : "none";
  $("inbox-page-info").textContent = `${state.inboxPage} / ${Math.max(totalPages, 1)}`;
  $("inbox-prev").disabled = state.inboxPage <= 1;
  $("inbox-next").disabled = state.inboxPage >= totalPages;
}

async function applyBulkUpdate() {
  const emails = state.accounts.map((account) => account.email);
  if (!emails.length) return;
  const body = { emails };
  const groupName = $("batch-group-input").value.trim();
  const registered = $("batch-registered-input").value;
  const primary = $("batch-primary-input").value;
  if (groupName) body.group_name = groupName;
  if (registered) body.is_registered = registered === "true";
  if (primary) body.is_primary = primary === "true";
  if (Object.keys(body).length === 1) return;
  showLoading(true);
  try {
    await api("/api/accounts/bulk-update", { method: "POST", body });
    closeModal("batch-overlay");
    await loadSummary();
    await loadAccounts(state.currentPage);
    await refreshSelectedAccountDetail();
  } finally {
    showLoading(false);
  }
}

async function changeAccountGroup() {
  if (!state.selectedAccountId) return;
  const groupName = $("group-input").value.trim();
  if (!groupName) return;
  showLoading(true);
  try {
    await api(`/api/accounts/${state.selectedAccountId}`, {
      method: "PATCH",
      body: { group_name: groupName },
    });
    closeModal("group-overlay");
    await loadSummary();
    await loadAccounts(state.currentPage);
    await refreshSelectedAccountDetail();
  } finally {
    showLoading(false);
  }
}

function openGroupModal() {
  const datalist = $("group-datalist");
  datalist.innerHTML = "";
  state.allGroups.forEach((groupName) => {
    const option = document.createElement("option");
    option.value = groupName;
    datalist.appendChild(option);
  });
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
      body: { sources: [{ source_name: "web-import.txt", text }] },
    });
    $("import-textarea").value = "";
    closeModal("import-overlay");
    await loadSummary();
    await loadAccounts(1);
  } finally {
    showLoading(false);
  }
}

async function toggleSelectedAccount(fieldName) {
  if (!state.selectedAccountId || !state.selectedAccount) return;
  const body = {};
  body[fieldName] = !state.selectedAccount[fieldName];
  await api(`/api/accounts/${state.selectedAccountId}`, { method: "PATCH", body });
  await loadSummary();
  await loadAccounts(state.currentPage);
  await refreshSelectedAccountDetail();
}

async function exportAccounts() {
  const groupName = $("group-filter").value;
  const suffix = groupName ? `?group_name=${encodeURIComponent(groupName)}` : "";
  const payload = await api(`/api/accounts/export${suffix}`);
  await copyToClipboard(typeof payload === "string" ? payload : JSON.stringify(payload));
}

function bindEvents() {
  $("refresh-accounts").addEventListener("click", () => void loadAccounts(state.currentPage));
  $("account-search").addEventListener("input", () => void loadAccounts(1));
  $("group-filter").addEventListener("change", () => void loadAccounts(1));
  $("status-filter").addEventListener("change", () => void loadAccounts(1));
  $("prev-page").addEventListener("click", () => void loadAccounts(state.currentPage - 1));
  $("next-page").addEventListener("click", () => void loadAccounts(state.currentPage + 1));
  $("refresh-inbox-btn").addEventListener("click", () => void fetchInbox());
  $("inbox-prev").addEventListener("click", () => { state.inboxPage -= 1; renderInbox(); });
  $("inbox-next").addEventListener("click", () => { state.inboxPage += 1; renderInbox(); });
  $("show-import").addEventListener("click", () => openModal("import-overlay"));
  $("show-batch").addEventListener("click", () => openModal("batch-overlay"));
  $("import-button").addEventListener("click", () => void importSources());
  $("apply-batch-button").addEventListener("click", () => void applyBulkUpdate());
  $("change-group-btn").addEventListener("click", openGroupModal);
  $("apply-group-button").addEventListener("click", () => void changeAccountGroup());
  $("toggle-reg-btn").addEventListener("click", () => void toggleSelectedAccount("is_registered"));
  $("toggle-pri-btn").addEventListener("click", () => void toggleSelectedAccount("is_primary"));
  $("export-button").addEventListener("click", () => void exportAccounts());
  $("copy-email-button").addEventListener("click", () => void copyToClipboard($("detail-email").textContent || ""));
  document.querySelectorAll("[data-close-modal]").forEach((button) => {
    button.addEventListener("click", () => closeModal(button.getAttribute("data-close-modal")));
  });
}

window.addEventListener("load", async () => {
  bindEvents();
  await loadSummary();
  await loadAccounts(1);
});
"""
