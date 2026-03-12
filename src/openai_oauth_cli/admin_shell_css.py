from __future__ import annotations


ADMIN_SHELL_CSS = """
:root {
  --bg: #f8fafc;
  --surface: #ffffff;
  --border: #e2e8f0;
  --text: #1e293b;
  --text-muted: #64748b;
  --accent: #0f172a;
  --primary: #3b82f6;
  --danger: #ef4444;
  --warning: #f59e0b;
  --sidebar-width: 340px;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  background: var(--bg);
  color: var(--text);
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
  background: var(--accent);
  color: white;
  border: none;
  cursor: pointer;
}
button.secondary {
  background: var(--surface);
  color: var(--text);
  border: 1px solid var(--border);
}
button:disabled { opacity: 0.6; cursor: not-allowed; }
.app-container { display: flex; height: 100vh; }
.sidebar {
  width: var(--sidebar-width);
  background: var(--surface);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
}
.sidebar-header, .sidebar-footer, .content-header, .toolbar {
  padding: 16px;
  border-bottom: 1px solid var(--border);
}
.sidebar-footer { border-top: 1px solid var(--border); border-bottom: none; }
.search-box { width: 100%; margin-bottom: 12px; }
.filter-row { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 12px; }
.account-list-container { flex: 1; overflow-y: auto; }
.account-item { padding: 12px 16px; border-bottom: 1px solid var(--border); cursor: pointer; }
.account-item.active { background: #eff6ff; border-left: 4px solid var(--primary); }
.email { font-weight: 600; overflow: hidden; text-overflow: ellipsis; }
.meta { color: var(--text-muted); font-size: 0.85rem; display: flex; gap: 8px; }
.content { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
.scroll-area { flex: 1; overflow-y: auto; padding: 24px; }
.detail-card, .message-item {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 16px;
}
.detail-card { margin-bottom: 24px; }
.detail-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 16px; }
.message-list { display: flex; flex-direction: column; gap: 12px; }
.message-header { display: flex; justify-content: space-between; gap: 12px; }
.message-body { white-space: pre-wrap; line-height: 1.5; color: #475569; }
.message-from, .muted { color: var(--text-muted); }
.badge {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 2px 8px;
  font-size: 0.75rem;
  font-weight: 700;
}
.badge-reg { background: #dcfce7; color: #166534; }
.badge-unreg { background: #fee2e2; color: #991b1b; }
.badge-primary { background: #dbeafe; color: #1e40af; }
.verification-code-box {
  margin-top: 12px;
  padding: 10px 12px;
  border-left: 4px solid var(--warning);
  background: #fef3c7;
  border-radius: 6px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}
.code-val { font-family: monospace; font-size: 1.1rem; font-weight: 700; color: #92400e; }
.overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: none;
  align-items: center;
  justify-content: center;
}
.modal {
  width: min(520px, 90vw);
  background: var(--surface);
  border-radius: 12px;
  padding: 24px;
}
.modal-footer { display: flex; justify-content: flex-end; gap: 12px; margin-top: 16px; }
.empty-state { text-align: center; color: var(--text-muted); padding: 48px; }
.pager { display: flex; gap: 8px; align-items: center; }
#loading-overlay {
  position: fixed;
  inset: 0;
  background: rgba(255, 255, 255, 0.7);
  display: none;
  align-items: center;
  justify-content: center;
  z-index: 200;
  font-weight: 700;
}
#inbox-loading-indicator { display: none; color: var(--text-muted); }
#inbox-loading-indicator.visible { display: inline-flex; }
"""
