const CONFIG = {
  accountsPerPage: 50,
  inboxPerPage: 6,
  searchDebounceMs: 250,
  maxVisiblePageButtons: 7,
};

const state = {
  accounts: [],
  totalAccounts: 0,
  currentPage: 1,
  selectedAccount: null,
  selectedAccountId: null,
  selectedIds: new Set(),
  selectedEmails: new Set(),
  inbox: [],
  inboxPage: 1,
  inboxFilter: "all",
  allGroups: [],
  groupDialogTarget: null,
  searchTimer: null,
};

function $(id) {
  return document.getElementById(id);
}

function showLoading(show) {
  $("loading-overlay").classList.toggle("visible", show);
}

function openModal(id) {
  $(id).classList.remove("hidden");
}

function closeModal(id) {
  $(id).classList.add("hidden");
}

function setText(id, value) {
  $(id).textContent = value;
}

function createBadge(text, className) {
  const badge = document.createElement("span");
  badge.className = `badge rounded-pill ${className}`;
  badge.textContent = text;
  return badge;
}

function showToast(message, type = "success") {
  const container = $("toast-container");
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.textContent = message;
  container.appendChild(toast);
  window.setTimeout(() => {
    toast.remove();
  }, 3000);
}

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

async function copyToClipboard(text, successMessage) {
  try {
    await navigator.clipboard.writeText(text);
    showToast(successMessage || "已复制");
  } catch (error) {
    showToast(`复制失败: ${error.message}`, "error");
  }
}

function selectedEmailList() {
  return Array.from(state.selectedEmails.values()).sort();
}

function formatDate(value) {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

function exactGroupMatch(query) {
  const normalized = query.trim().toLowerCase();
  if (!normalized) {
    return null;
  }
  return state.allGroups.find((groupName) => groupName.toLowerCase() === normalized) || null;
}

function filteredGroupMatches(query) {
  const normalized = query.trim().toLowerCase();
  const groups = normalized
    ? state.allGroups.filter((groupName) => groupName.toLowerCase().includes(normalized))
    : [...state.allGroups];
  return groups.slice(0, 10);
}

async function loadSummary() {
  const summary = await api("/api/summary");
  setText("stat-total", String(summary.accounts));
  setText("stat-registered", String(summary.registered));
  setText("stat-primary", String(summary.primary));
  state.allGroups = Object.keys(summary.groups).sort((left, right) => left.localeCompare(right));

  const groupFilter = $("group-filter");
  const previousValue = groupFilter.value;
  groupFilter.innerHTML = "";
  const defaultOption = document.createElement("option");
  defaultOption.value = "";
  defaultOption.textContent = "所有分组";
  groupFilter.appendChild(defaultOption);
  state.allGroups.forEach((groupName) => {
    const option = document.createElement("option");
    option.value = groupName;
    option.textContent = groupName || "(无分组)";
    groupFilter.appendChild(option);
  });
  if (previousValue && state.allGroups.includes(previousValue)) {
    groupFilter.value = previousValue;
  }

  updateGroupDialogState();
}

async function loadAccounts(page = 1) {
  state.currentPage = page;
  const params = new URLSearchParams({
    limit: String(CONFIG.accountsPerPage),
    offset: String((page - 1) * CONFIG.accountsPerPage),
    query: $("account-search").value.trim(),
  });

  const groupName = $("group-filter").value;
  const status = $("status-filter").value;
  if (groupName) {
    params.set("group_name", groupName);
  }
  if (status === "registered") {
    params.set("is_registered", "true");
  }
  if (status === "unregistered") {
    params.set("is_registered", "false");
  }

  const payload = await api(`/api/accounts?${params.toString()}`);
  state.accounts = payload.items;
  state.totalAccounts = payload.total;
  renderAccountList();
}

function selectionStateForVisibleAccounts() {
  const visibleIds = state.accounts.map((account) => account.id);
  const selectedVisibleCount = visibleIds.filter((id) => state.selectedIds.has(id)).length;
  return {
    visibleCount: visibleIds.length,
    selectedVisibleCount,
    allSelected: visibleIds.length > 0 && selectedVisibleCount === visibleIds.length,
    partiallySelected: selectedVisibleCount > 0 && selectedVisibleCount < visibleIds.length,
  };
}

function updateBatchSelectionBar() {
  const count = state.selectedEmails.size;
  setText("selected-count", `已选 ${count} 项`);
  $("batch-selection-bar").classList.toggle("hidden", count === 0);
}

function updateSelectPageCheckbox() {
  const checkbox = $("select-page-checkbox");
  const selectionState = selectionStateForVisibleAccounts();
  checkbox.disabled = selectionState.visibleCount === 0;
  checkbox.checked = selectionState.allSelected;
  checkbox.indeterminate = selectionState.partiallySelected;
}

function getAccountPaginationItems(totalPages, currentPage) {
  if (totalPages <= CONFIG.maxVisiblePageButtons) {
    return Array.from({ length: totalPages }, (_, index) => index + 1);
  }

  const pages = new Set([1, totalPages]);
  for (let page = currentPage - 2; page <= currentPage + 2; page += 1) {
    if (page > 1 && page < totalPages) {
      pages.add(page);
    }
  }

  const sortedPages = Array.from(pages.values()).sort((left, right) => left - right);
  const items = [];

  sortedPages.forEach((page, index) => {
    items.push(page);
    const nextPage = sortedPages[index + 1];
    if (nextPage && nextPage - page > 1) {
      items.push("ellipsis");
    }
  });

  return items;
}

function renderAccountPagination() {
  const totalPages = Math.max(1, Math.ceil(state.totalAccounts / CONFIG.accountsPerPage));
  const pageList = $("account-page-list");
  pageList.innerHTML = "";
  setText("account-page-summary", `第 ${state.currentPage} / ${totalPages} 页`);

  const showPaginationControls = totalPages > 1;
  ["first-page", "prev-page", "next-page", "last-page", "account-page-list"].forEach((id) => {
    $(id).classList.toggle("hidden", !showPaginationControls);
  });

  getAccountPaginationItems(totalPages, state.currentPage).forEach((item) => {
    if (item === "ellipsis") {
      const span = document.createElement("span");
      span.className = "page-ellipsis";
      span.textContent = "...";
      pageList.appendChild(span);
      return;
    }

    const button = document.createElement("button");
    button.type = "button";
    button.className = `btn btn-outline-secondary btn-sm page-button ${item === state.currentPage ? "active" : ""}`.trim();
    button.textContent = String(item);
    button.disabled = item === state.currentPage;
    button.addEventListener("click", () => void loadAccounts(item));
    pageList.appendChild(button);
  });

  $("first-page").disabled = state.currentPage <= 1;
  $("prev-page").disabled = state.currentPage <= 1;
  $("next-page").disabled = state.currentPage >= totalPages;
  $("last-page").disabled = state.currentPage >= totalPages;
}

function toggleAccountSelection(account, shouldSelect) {
  if (shouldSelect) {
    state.selectedIds.add(account.id);
    state.selectedEmails.add(account.email);
  } else {
    state.selectedIds.delete(account.id);
    state.selectedEmails.delete(account.email);
  }
  updateBatchSelectionBar();
  updateSelectPageCheckbox();
}

function clearSelection() {
  state.selectedIds.clear();
  state.selectedEmails.clear();
  renderAccountList();
}

function renderAccountList() {
  const list = $("account-list");
  list.innerHTML = "";

  if (!state.accounts.length) {
    const emptyState = document.createElement("div");
    emptyState.className = "empty-state";
    emptyState.textContent = "未找到账号";
    list.appendChild(emptyState);
  } else {
    state.accounts.forEach((account) => {
      const row = document.createElement("div");
      row.className = `account-item ${state.selectedAccountId === account.id ? "active" : ""}`.trim();
      row.addEventListener("click", () => void selectAccount(account));

      const checkbox = document.createElement("input");
      checkbox.className = "form-check-input account-checkbox";
      checkbox.type = "checkbox";
      checkbox.checked = state.selectedIds.has(account.id);
      checkbox.addEventListener("click", (event) => {
        event.stopPropagation();
      });
      checkbox.addEventListener("change", () => {
        toggleAccountSelection(account, checkbox.checked);
      });

      const main = document.createElement("div");
      main.className = "account-main";

      const email = document.createElement("div");
      email.className = "account-email";
      email.textContent = account.email;
      main.appendChild(email);

      const metaLine = document.createElement("div");
      metaLine.className = "account-meta-line";

      // Registered Status Badge
      const regBadge = document.createElement("span");
      regBadge.className = `badge-mini ${account.is_registered ? "badge-reg" : "badge-unreg"}`;
      regBadge.textContent = account.is_registered ? "已注册" : "未注册";
      metaLine.appendChild(regBadge);

      // Primary Status Badge
      if (account.is_primary) {
        const priBadge = document.createElement("span");
        priBadge.className = "badge-mini badge-pri";
        priBadge.textContent = "主账号";
        metaLine.appendChild(priBadge);
      }

      // Group Tag
      const groupTag = document.createElement("span");
      groupTag.className = "badge-group";
      groupTag.textContent = account.group_name || "默认";
      metaLine.appendChild(groupTag);

      main.appendChild(metaLine);
      row.appendChild(checkbox);
      row.appendChild(main);
      list.appendChild(row);
    });
  }

  renderAccountPagination();
  updateBatchSelectionBar();
  updateSelectPageCheckbox();
  setText("total-count", `共 ${state.totalAccounts} 条`);
}

function setSingleAccountActionsDisabled(disabled) {
  [
    "copy-email-button",
    "sidebar-refresh-inbox-button",
    "change-group-btn",
    "toggle-reg-btn",
    "toggle-pri-btn",
    "refresh-inbox-btn",
  ].forEach((id) => {
    $(id).disabled = disabled;
  });
}

function renderSelectedAccountDisplays() {
  const account = state.selectedAccount;
  if (!account) {
    setText("context-email", "请从左侧选择一个账号");
    setText("context-group", "分组: -");
    setText("context-status", "状态: -");
    setText("context-primary", "主账号: -");
    setText("context-updated", "最后更新: -");
    setText("detail-email", "-");
    setText("detail-group", "-");
    setText("detail-status", "-");
    setText("detail-primary", "-");
    setText("detail-updated", "-");
    setSingleAccountActionsDisabled(true);
    return;
  }

  setText("context-email", account.email);
  setText("context-group", `分组: ${account.group_name || "默认"}`);
  setText("context-status", `状态: ${account.is_registered ? "已注册" : "未注册"}`);
  setText("context-primary", `主账号: ${account.is_primary ? "是" : "否"}`);
  setText("context-updated", `最后更新: ${formatDate(account.updated_at)}`);

  setText("detail-email", account.email);
  setText("detail-group", account.group_name || "默认");
  setText("detail-status", account.is_registered ? "已注册" : "未注册");
  setText("detail-primary", account.is_primary ? "是" : "否");
  setText("detail-updated", formatDate(account.updated_at));
  setSingleAccountActionsDisabled(false);
}

function renderInbox() {
  const container = $("inbox-container");
  const messages = state.inboxFilter === "verification"
    ? state.inbox.filter((message) => Boolean(message.verification_code))
    : state.inbox;

  const totalPages = Math.max(1, Math.ceil(messages.length / CONFIG.inboxPerPage));
  if (state.inboxPage > totalPages) {
    state.inboxPage = totalPages;
  }

  const start = (state.inboxPage - 1) * CONFIG.inboxPerPage;
  const visibleMessages = messages.slice(start, start + CONFIG.inboxPerPage);

  container.innerHTML = "";
  if (!state.selectedAccountId) {
    const emptyState = document.createElement("div");
    emptyState.className = "empty-state";
    emptyState.textContent = "从左侧选择账号后显示收件箱";
    container.appendChild(emptyState);
  } else if (!visibleMessages.length) {
    const emptyState = document.createElement("div");
    emptyState.className = "empty-state";
    emptyState.textContent = state.inboxFilter === "verification" ? "当前没有验证码邮件" : "收件箱为空";
    container.appendChild(emptyState);
  } else {
    visibleMessages.forEach((message) => {
      const card = document.createElement("article");
      card.className = `message-card ${message.verification_code ? "has-verification" : ""}`;

      // Header: 左侧主题+发件人，右侧时间
      const header = document.createElement("div");
      header.className = "message-header";

      const headerLeft = document.createElement("div");
      headerLeft.className = "message-header-left";

      const subject = document.createElement("div");
      subject.className = "message-subject";
      subject.textContent = message.subject || "(无主题)";
      headerLeft.appendChild(subject);

      const from = document.createElement("div");
      from.className = "message-from";
      from.textContent = message.from_address || "-";
      headerLeft.appendChild(from);

      const time = document.createElement("div");
      time.className = "message-time";
      time.textContent = formatDate(message.received_at);

      header.appendChild(headerLeft);
      header.appendChild(time);

      // Body: 邮件内容
      const body = document.createElement("div");
      body.className = "message-body";
      body.textContent = message.body_text || message.body_preview || "(无内容)";

      card.appendChild(header);
      card.appendChild(body);

      // Verification: 验证码区块
      if (message.verification_code) {
        const verificationBox = document.createElement("div");
        verificationBox.className = "verification-box";

        const textWrap = document.createElement("div");
        textWrap.className = "verification-content";
        const label = document.createElement("div");
        label.className = "verification-label";
        label.textContent = "验证码";
        const code = document.createElement("div");
        code.className = "verification-code";
        code.textContent = message.verification_code;
        textWrap.appendChild(label);
        textWrap.appendChild(code);

        const copyButton = document.createElement("button");
        copyButton.type = "button";
        copyButton.className = "btn btn-primary btn-sm";
        copyButton.textContent = "复制";
        copyButton.addEventListener("click", () => void copyToClipboard(message.verification_code, "验证码已复制"));

        verificationBox.appendChild(textWrap);
        verificationBox.appendChild(copyButton);
        card.appendChild(verificationBox);
      }

      container.appendChild(card);
    });
  }

  $("inbox-pagination").classList.toggle("hidden", messages.length <= CONFIG.inboxPerPage);
  setText("inbox-page-info", `${Math.max(state.inboxPage, 1)} / ${totalPages}`);
  $("inbox-prev").disabled = state.inboxPage <= 1;
  $("inbox-next").disabled = state.inboxPage >= totalPages;
  $("all-mail-filter").classList.toggle("active", state.inboxFilter === "all");
  $("verification-only-filter").classList.toggle("active", state.inboxFilter === "verification");
  setText("inbox-meta", `${messages.length} 封邮件${state.inboxFilter === "verification" ? "（仅验证码）" : ""}`);
}

function renderMailboxSummary() {
  const verificationMessages = state.inbox.filter((message) => Boolean(message.verification_code));
  const latestMessage = [...state.inbox]
    .filter((message) => message.received_at)
    .sort((left, right) => new Date(right.received_at).getTime() - new Date(left.received_at).getTime())[0];

  setText("mailbox-message-count", String(state.inbox.length));
  setText("verification-message-count", String(verificationMessages.length));
  setText("latest-message-time", latestMessage ? formatDate(latestMessage.received_at) : "-");

  const list = $("latest-code-list");
  list.innerHTML = "";
  if (!verificationMessages.length) {
    const emptyState = document.createElement("div");
    emptyState.className = "empty-state";
    emptyState.textContent = "当前没有验证码";
    list.appendChild(emptyState);
    return;
  }

  verificationMessages
    .slice()
    .sort((left, right) => new Date(right.received_at).getTime() - new Date(left.received_at).getTime())
    .slice(0, 3)
    .forEach((message) => {
      const item = document.createElement("div");
      item.className = "latest-code-item";

      const content = document.createElement("div");
      const code = document.createElement("strong");
      code.textContent = message.verification_code;
      const meta = document.createElement("div");
      meta.className = "latest-code-meta";
      meta.textContent = `${formatDate(message.received_at)} · ${message.subject || "(无主题)"}`;
      content.appendChild(code);
      content.appendChild(meta);

      const copyButton = document.createElement("button");
      copyButton.type = "button";
      copyButton.className = "btn btn-outline-secondary btn-sm";
      copyButton.textContent = "复制";
      copyButton.addEventListener("click", () => void copyToClipboard(message.verification_code, "验证码已复制"));

      item.appendChild(content);
      item.appendChild(copyButton);
      list.appendChild(item);
    });
}

async function refreshSelectedAccountDetail() {
  if (!state.selectedAccount) {
    renderSelectedAccountDisplays();
    state.inbox = [];
    renderInbox();
    renderMailboxSummary();
    return;
  }

  const params = new URLSearchParams({
    query: state.selectedAccount.email,
    limit: "1",
    offset: "0",
  });

  const payload = await api(`/api/accounts?${params.toString()}`);
  const updated = payload.items.find((account) => account.email.toLowerCase() === state.selectedAccount.email.toLowerCase());
  if (!updated) {
    state.selectedAccount = null;
    state.selectedAccountId = null;
    state.inbox = [];
    renderAccountList();
    renderSelectedAccountDisplays();
    renderInbox();
    renderMailboxSummary();
    return;
  }

  state.selectedAccount = updated;
  state.selectedAccountId = updated.id;
  renderAccountList();
  renderSelectedAccountDisplays();
}

async function selectAccount(account) {
  state.selectedAccount = account;
  state.selectedAccountId = account.id;
  state.inboxPage = 1;
  renderAccountList();
  renderSelectedAccountDisplays();
  await fetchInbox();
}

async function fetchInbox(showSuccessToast = false) {
  if (!state.selectedAccountId) {
    showToast("请先选择账号", "error");
    return;
  }

  $("inbox-loading-indicator").classList.remove("hidden");
  $("refresh-inbox-btn").disabled = true;
  $("sidebar-refresh-inbox-button").disabled = true;

  try {
    const payload = await api(`/api/accounts/${state.selectedAccountId}/inbox`);
    state.inbox = payload.messages;
    renderInbox();
    renderMailboxSummary();
    if (showSuccessToast) {
      showToast("邮件已刷新");
    }
  } catch (error) {
    state.inbox = [];
    renderInbox();
    renderMailboxSummary();
    showToast(`加载邮件失败: ${error.message}`, "error");
  } finally {
    $("inbox-loading-indicator").classList.add("hidden");
    $("refresh-inbox-btn").disabled = false;
    $("sidebar-refresh-inbox-button").disabled = false;
  }
}

function resetGroupDialog() {
  state.groupDialogTarget = null;
  $("group-name-input").value = "";
  setText("group-target-description", "未选择账号");
  updateGroupDialogState();
}

function openGroupDialog(target) {
  state.groupDialogTarget = target;
  $("group-name-input").value = "";
  setText(
    "group-target-description",
    target.mode === "single" ? `将更新 ${target.email}` : `已选 ${target.count} 个账号`,
  );
  updateGroupDialogState();
  openModal("group-overlay");
  $("group-name-input").focus();
}

function openSelectedGroupDialog() {
  const emails = selectedEmailList();
  if (!emails.length) {
    showToast("请先勾选账号", "error");
    return;
  }
  openGroupDialog({
    mode: "selected",
    emails,
    count: emails.length,
  });
}

function openSingleGroupDialog() {
  if (!state.selectedAccount || !state.selectedAccountId) {
    showToast("请先选择账号", "error");
    return;
  }
  openGroupDialog({
    mode: "single",
    email: state.selectedAccount.email,
    accountId: state.selectedAccountId,
  });
}

function updateGroupDialogState() {
  const input = $("group-name-input");
  const list = $("group-match-list");
  const preview = $("group-preview");
  const button = $("apply-group-button");
  const query = input.value.trim();
  const exactMatch = exactGroupMatch(query);
  const matches = filteredGroupMatches(query);

  list.innerHTML = "";
  if (!matches.length) {
    const emptyState = document.createElement("div");
    emptyState.className = "empty-state";
    emptyState.textContent = query ? "没有匹配分组，将创建新分组" : "暂无已有分组";
    list.appendChild(emptyState);
  } else {
    matches.forEach((groupName) => {
      const buttonElement = document.createElement("button");
      buttonElement.type = "button";
      buttonElement.className = `btn btn-outline-secondary btn-sm group-match-chip ${exactMatch === groupName ? "selected" : ""}`.trim();
      buttonElement.textContent = groupName;
      buttonElement.addEventListener("click", () => {
        input.value = groupName;
        updateGroupDialogState();
      });
      list.appendChild(buttonElement);
    });
  }

  if (!query || !state.groupDialogTarget) {
    preview.textContent = "输入分组后在这里预览操作";
    button.disabled = true;
    button.textContent = "加入分组";
    return;
  }

  const targetName = exactMatch || query;
  button.disabled = false;
  button.textContent = exactMatch ? "加入分组" : "创建并加入";
  preview.textContent = state.groupDialogTarget.mode === "single"
    ? `将把 ${state.groupDialogTarget.email} 加入：${targetName}`
    : `将把 ${state.groupDialogTarget.count} 个账号加入：${targetName}`;
}

async function applyGroupAssignment() {
  const query = $("group-name-input").value.trim();
  if (!query || !state.groupDialogTarget) {
    return;
  }
  const groupName = exactGroupMatch(query) || query;

  showLoading(true);
  try {
    if (state.groupDialogTarget.mode === "single") {
      await api(`/api/accounts/${state.groupDialogTarget.accountId}`, {
        method: "PATCH",
        body: { group_name: groupName },
      });
    } else {
      await api("/api/accounts/bulk-update", {
        method: "POST",
        body: { emails: state.groupDialogTarget.emails, group_name: groupName },
      });
      clearSelection();
    }

    closeModal("group-overlay");
    resetGroupDialog();
    await loadSummary();
    await loadAccounts(state.currentPage);
    await refreshSelectedAccountDetail();
    showToast(`已加入分组：${groupName}`);
  } finally {
    showLoading(false);
  }
}

async function importSources() {
  const text = $("import-textarea").value.trim();
  if (!text) {
    return;
  }

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
    showToast("导入完成");
  } finally {
    showLoading(false);
  }
}

async function toggleSelectedAccount(fieldName) {
  if (!state.selectedAccountId || !state.selectedAccount) {
    showToast("请先选择账号", "error");
    return;
  }

  await api(`/api/accounts/${state.selectedAccountId}`, {
    method: "PATCH",
    body: { [fieldName]: !state.selectedAccount[fieldName] },
  });
  await loadSummary();
  await loadAccounts(state.currentPage);
  await refreshSelectedAccountDetail();
  showToast("账号状态已更新");
}

async function exportAccounts() {
  const groupName = $("group-filter").value;
  const suffix = groupName ? `?group_name=${encodeURIComponent(groupName)}` : "";
  const payload = await api(`/api/accounts/export${suffix}`);
  const text = typeof payload === "string" ? payload : JSON.stringify(payload, null, 2);
  await copyToClipboard(text, "导出结果已复制到剪贴板");
}

function scheduleAccountSearch() {
  if (state.searchTimer) {
    window.clearTimeout(state.searchTimer);
  }
  state.searchTimer = window.setTimeout(() => {
    void loadAccounts(1);
  }, CONFIG.searchDebounceMs);
}

function bindEvents() {
  $("refresh-accounts").addEventListener("click", () => void loadAccounts(state.currentPage));
  $("account-search").addEventListener("input", scheduleAccountSearch);
  $("group-filter").addEventListener("change", () => void loadAccounts(1));
  $("status-filter").addEventListener("change", () => void loadAccounts(1));

  $("select-page-checkbox").addEventListener("change", (event) => {
    const shouldSelect = event.target.checked;
    state.accounts.forEach((account) => {
      if (shouldSelect) {
        state.selectedIds.add(account.id);
        state.selectedEmails.add(account.email);
      } else {
        state.selectedIds.delete(account.id);
        state.selectedEmails.delete(account.email);
      }
    });
    renderAccountList();
  });

  $("clear-selection-button").addEventListener("click", clearSelection);
  $("open-batch-group-button").addEventListener("click", openSelectedGroupDialog);
  $("first-page").addEventListener("click", () => void loadAccounts(1));
  $("prev-page").addEventListener("click", () => void loadAccounts(state.currentPage - 1));
  $("next-page").addEventListener("click", () => void loadAccounts(state.currentPage + 1));
  $("last-page").addEventListener("click", () => {
    const totalPages = Math.max(1, Math.ceil(state.totalAccounts / CONFIG.accountsPerPage));
    void loadAccounts(totalPages);
  });

  $("show-import").addEventListener("click", () => openModal("import-overlay"));
  $("import-button").addEventListener("click", () => void importSources());
  $("change-group-btn").addEventListener("click", openSingleGroupDialog);
  $("apply-group-button").addEventListener("click", () => void applyGroupAssignment());
  $("group-name-input").addEventListener("input", updateGroupDialogState);

  $("refresh-inbox-btn").addEventListener("click", () => void fetchInbox(true));
  $("sidebar-refresh-inbox-button").addEventListener("click", () => void fetchInbox(true));
  $("all-mail-filter").addEventListener("click", () => {
    state.inboxFilter = "all";
    state.inboxPage = 1;
    renderInbox();
  });
  $("verification-only-filter").addEventListener("click", () => {
    state.inboxFilter = "verification";
    state.inboxPage = 1;
    renderInbox();
  });
  $("inbox-prev").addEventListener("click", () => {
    state.inboxPage -= 1;
    renderInbox();
  });
  $("inbox-next").addEventListener("click", () => {
    state.inboxPage += 1;
    renderInbox();
  });

  $("toggle-reg-btn").addEventListener("click", () => void toggleSelectedAccount("is_registered"));
  $("toggle-pri-btn").addEventListener("click", () => void toggleSelectedAccount("is_primary"));
  $("copy-email-button").addEventListener("click", () => {
    if (state.selectedAccount) {
      void copyToClipboard(state.selectedAccount.email, "邮箱已复制");
    }
  });
  $("export-button").addEventListener("click", () => void exportAccounts());

  document.querySelectorAll("[data-close-modal]").forEach((button) => {
    button.addEventListener("click", () => {
      const modalId = button.getAttribute("data-close-modal");
      if (modalId) {
        closeModal(modalId);
        if (modalId === "group-overlay") {
          resetGroupDialog();
        }
      }
    });
  });

  document.querySelectorAll(".overlay").forEach((overlay) => {
    overlay.addEventListener("click", (event) => {
      if (event.target !== overlay) {
        return;
      }
      overlay.classList.add("hidden");
      if (overlay.id === "group-overlay") {
        resetGroupDialog();
      }
    });
  });
}

window.addEventListener("load", async () => {
  bindEvents();
  renderSelectedAccountDisplays();
  renderInbox();
  renderMailboxSummary();
  await loadSummary();
  await loadAccounts(1);
});
