from __future__ import annotations


ADMIN_SHELL_BODY = """
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
      <div style="display:flex; gap:8px;">
        <button id="refresh-accounts" class="secondary" style="flex:1;">刷新列表</button>
        <button id="show-import" class="secondary">导入</button>
      </div>
    </div>
    <div id="account-list" class="account-list-container"></div>
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
      <div style="display:flex; gap:24px;">
        <div><div class="muted">账号总数</div><div id="stat-total">0</div></div>
        <div><div class="muted">已注册</div><div id="stat-registered">0</div></div>
        <div><div class="muted">主账号</div><div id="stat-primary">0</div></div>
      </div>
      <div style="display:flex; gap:8px;">
        <button id="show-batch" class="secondary">批量操作</button>
        <button id="export-button" class="secondary">导出 JSON</button>
      </div>
    </header>

    <div class="scroll-area">
      <div id="welcome-screen" class="empty-state">
        <h2>请从左侧选择一个账号</h2>
        <p>点击账号后可以查看详情并接收验证码</p>
      </div>

      <div id="detail-view" style="display:none;">
        <section id="account-detail-panel" class="detail-card">
          <div style="display:flex; justify-content:space-between; gap:12px; margin-bottom:16px;">
            <div style="display:flex; align-items:center; gap:12px;">
              <h2 id="detail-email" style="margin:0;">email@example.com</h2>
              <button id="copy-email-button" class="secondary">复制</button>
            </div>
            <div style="display:flex; gap:8px;">
              <button id="change-group-btn" class="secondary">加入分组</button>
              <button id="toggle-reg-btn" class="secondary">切换注册状态</button>
              <button id="toggle-pri-btn" class="secondary">切换主账号</button>
            </div>
          </div>
          <div class="detail-grid">
            <div><div class="muted">所属分组</div><div id="detail-group">-</div></div>
            <div><div class="muted">注册状态</div><div id="detail-status">-</div></div>
            <div><div class="muted">最后更新</div><div id="detail-updated">-</div></div>
          </div>
        </section>

        <section id="inbox-panel">
          <div class="toolbar" style="display:flex; justify-content:space-between; gap:12px; align-items:center;">
            <h3 style="margin:0;">收件箱</h3>
            <div style="display:flex; gap:12px; align-items:center;">
              <div id="inbox-loading-indicator" aria-live="polite">加载邮件中</div>
              <label><input type="checkbox" id="auto-refresh-check"> 自动刷新</label>
              <div id="inbox-pagination" class="pager" style="display:none;">
                <button id="inbox-prev">&lt;</button>
                <span id="inbox-page-info">1 / 1</span>
                <button id="inbox-next">&gt;</button>
              </div>
              <button id="refresh-inbox-btn" class="secondary">刷新邮件</button>
            </div>
          </div>
          <div id="inbox-container" class="message-list"></div>
        </section>
      </div>
    </div>
  </main>
</div>

<div id="import-overlay" class="overlay">
  <div class="modal">
    <div style="display:flex; justify-content:space-between; align-items:center;">
      <h2 style="margin:0;">导入账号</h2>
      <button class="secondary" data-close-modal="import-overlay">关闭</button>
    </div>
    <p class="muted">请输入原始文本行，每行一个账号。</p>
    <textarea id="import-textarea" style="width:100%; height:220px;" placeholder="粘贴账号数据..."></textarea>
    <div class="modal-footer">
      <button class="secondary" data-close-modal="import-overlay">取消</button>
      <button id="import-button">开始导入</button>
    </div>
  </div>
</div>

<div id="batch-overlay" class="overlay">
  <div class="modal">
    <div style="display:flex; justify-content:space-between; align-items:center;">
      <h2 style="margin:0;">批量更新</h2>
      <button class="secondary" data-close-modal="batch-overlay">关闭</button>
    </div>
    <div style="display:flex; flex-direction:column; gap:12px;">
      <input id="batch-group-input" type="text" placeholder="留空不修改，或输入新分组名">
      <select id="batch-registered-input">
        <option value="">不修改</option>
        <option value="true">设为已注册</option>
        <option value="false">设为未注册</option>
      </select>
      <select id="batch-primary-input">
        <option value="">不修改</option>
        <option value="true">设为是</option>
        <option value="false">设为否</option>
      </select>
    </div>
    <div class="modal-footer">
      <button class="secondary" data-close-modal="batch-overlay">取消</button>
      <button id="apply-batch-button">应用更改</button>
    </div>
  </div>
</div>

<div id="group-overlay" class="overlay">
  <div class="modal">
    <div style="display:flex; justify-content:space-between; align-items:center;">
      <h2 style="margin:0;">加入分组</h2>
      <button class="secondary" data-close-modal="group-overlay">关闭</button>
    </div>
    <input id="group-input" type="text" list="group-datalist" placeholder="输入新分组名或选择已有分组" style="width:100%;">
    <datalist id="group-datalist"></datalist>
    <div class="modal-footer">
      <button class="secondary" data-close-modal="group-overlay">取消</button>
      <button id="apply-group-button">保存</button>
    </div>
  </div>
</div>
"""
