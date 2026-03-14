import { useState, useEffect, useCallback } from 'react';
import {
  List,
  Button,
  Input,
  Select,
  Tag,
  Pagination,
  Typography,
  Empty,
  Spin,
  Toast,
  Modal,
  TextArea,
  ButtonGroup,
} from '@douyinfe/semi-ui';
import { IconSearch, IconRefresh, IconCopy } from '@douyinfe/semi-icons';
import type { Account, Message, Summary } from './api';
import {
  getSummary,
  getAccounts,
  getInbox,
  updateAccount,
  bulkUpdate,
  importTxt,
  exportAccounts as exportAccountsApi,
} from './api';

const { Title, Text } = Typography;

const ACCOUNTS_PER_PAGE = 25;
const INBOX_PER_PAGE = 6;

function formatDate(value: string | null): string {
  if (!value) return '-';
  const date = new Date(value);
  if (isNaN(date.getTime())) return value;
  return date.toLocaleString('zh-CN');
}

async function copyText(text: string, successMessage: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(text);
    Toast.success(successMessage);
  } catch {
    Toast.error('复制失败');
  }
}

function MessageCard({ message }: { message: Message }) {
  return (
    <article className={`message-card ${message.verification_code ? 'has-verification' : ''}`}>
      <div className="message-header">
        <div className="message-header-left">
          <div className="message-subject">{message.subject || '(无主题)'}</div>
          <div className="message-from">{message.from_address || '-'}</div>
        </div>
        <div className="message-time">{formatDate(message.received_at)}</div>
      </div>

      <div className="message-body">{message.body_text || message.body_preview || '(无内容)'}</div>

      {message.verification_code && (
        <div className="verification-box">
          <div className="verification-content">
            <div className="verification-label">验证码</div>
            <div className="verification-code">{message.verification_code}</div>
          </div>
          <Button size="small" theme="solid" onClick={() => copyText(message.verification_code!, '验证码已复制')}>
            复制
          </Button>
        </div>
      )}
    </article>
  );
}

function ImportModal({
  visible,
  onClose,
  onSuccess,
}: {
  visible: boolean;
  onClose: () => void;
  onSuccess: () => void;
}) {
  const [text, setText] = useState('');
  const [loading, setLoading] = useState(false);

  const handleImport = async () => {
    if (!text.trim()) return;
    setLoading(true);
    try {
      await importTxt([{ source_name: 'web-import.txt', text: text.trim() }]);
      Toast.success('导入完成');
      setText('');
      onClose();
      onSuccess();
    } catch (err) {
      Toast.error(`导入失败: ${err}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal
      title="导入账号"
      visible={visible}
      onCancel={onClose}
      footer={
        <>
          <Button onClick={onClose}>取消</Button>
          <Button theme="solid" loading={loading} onClick={handleImport}>
            开始导入
          </Button>
        </>
      }
    >
      <TextArea placeholder="粘贴账号数据..." rows={10} value={text} onChange={setText} />
    </Modal>
  );
}

function GroupModal({
  visible,
  onClose,
  onSuccess,
  target,
  groups,
}: {
  visible: boolean;
  onClose: () => void;
  onSuccess: () => void;
  target: { mode: 'single'; email: string; accountId: number } | { mode: 'batch'; emails: string[] } | null;
  groups: string[];
}) {
  const [groupName, setGroupName] = useState('');
  const [loading, setLoading] = useState(false);

  const trimmedGroupName = groupName.trim();
  const matchedGroups = groups
    .filter(group => group.toLowerCase().includes(trimmedGroupName.toLowerCase()))
    .slice(0, 10);
  const matchesExistingGroup = groups.includes(trimmedGroupName);

  const handleApply = async () => {
    if (!trimmedGroupName || !target) return;
    setLoading(true);
    try {
      if (target.mode === 'single') {
        await updateAccount(target.accountId, { group_name: trimmedGroupName });
      } else {
        await bulkUpdate(target.emails, { group_name: trimmedGroupName });
      }
      Toast.success(`已加入分组：${trimmedGroupName}`);
      setGroupName('');
      onClose();
      onSuccess();
    } catch (err) {
      Toast.error(`操作失败: ${err}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal
      title="加入分组"
      visible={visible}
      onCancel={() => {
        setGroupName('');
        onClose();
      }}
      footer={
        <>
          <Button
            onClick={() => {
              setGroupName('');
              onClose();
            }}
          >
            取消
          </Button>
          <Button theme="solid" loading={loading} onClick={handleApply} disabled={!trimmedGroupName}>
            {matchesExistingGroup ? '加入分组' : '创建并加入'}
          </Button>
        </>
      }
    >
      <div className="group-modal-stack">
        <Text type="tertiary">
          {target?.mode === 'single'
            ? `将更新 ${target.email}`
            : `已选 ${(target as { mode: 'batch'; emails: string[] } | null)?.emails?.length ?? 0} 个账号`}
        </Text>
        <div>
          <label className="group-modal-label">分组名</label>
          <Input placeholder="搜索已有分组或输入新分组名" value={groupName} onChange={setGroupName} />
        </div>
        {trimmedGroupName && (
          <div className="group-preview">
            将把 {target?.mode === 'single' ? '当前账号' : `${(target as { mode: 'batch'; emails: string[] })?.emails?.length ?? 0} 个账号`}
            {' '}加入：{trimmedGroupName}
          </div>
        )}
        {matchedGroups.length > 0 && (
          <div>
            <Text type="tertiary" size="small">
              匹配结果
            </Text>
            <div className="group-match-list">
              {matchedGroups.map(group => (
                <Tag key={group} size="large" className="group-match-tag" onClick={() => setGroupName(group)}>
                  {group}
                </Tag>
              ))}
            </div>
          </div>
        )}
      </div>
    </Modal>
  );
}

export default function App() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [totalAccounts, setTotalAccounts] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [inbox, setInbox] = useState<Message[]>([]);
  const [inboxPage, setInboxPage] = useState(1);
  const [inboxFilter, setInboxFilter] = useState<'all' | 'verification'>('all');
  const [groups, setGroups] = useState<string[]>([]);

  const [selectedAccount, setSelectedAccount] = useState<Account | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [selectedEmails, setSelectedEmails] = useState<Set<string>>(new Set());

  const [searchQuery, setSearchQuery] = useState('');
  const [groupFilter, setGroupFilter] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [inboxLoading, setInboxLoading] = useState(false);

  const [importVisible, setImportVisible] = useState(false);
  const [groupVisible, setGroupVisible] = useState(false);
  const [groupTarget, setGroupTarget] = useState<
    { mode: 'single'; email: string; accountId: number } | { mode: 'batch'; emails: string[] } | null
  >(null);

  const loadSummary = useCallback(async () => {
    const data = await getSummary();
    setSummary(data);
    setGroups(Object.keys(data.groups).sort());
  }, []);

  const loadAccounts = useCallback(
    async (page = 1) => {
      setCurrentPage(page);
      setLoading(true);
      try {
        const params: {
          limit: number;
          offset: number;
          query?: string;
          group_name?: string;
          is_registered?: boolean;
        } = {
          limit: ACCOUNTS_PER_PAGE,
          offset: (page - 1) * ACCOUNTS_PER_PAGE,
        };
        if (searchQuery.trim()) params.query = searchQuery.trim();
        if (groupFilter) params.group_name = groupFilter;
        if (statusFilter === 'registered') params.is_registered = true;
        if (statusFilter === 'unregistered') params.is_registered = false;

        const data = await getAccounts(params);
        setAccounts(data.items);
        setTotalAccounts(data.total);
      } finally {
        setLoading(false);
      }
    },
    [searchQuery, groupFilter, statusFilter],
  );

  const loadInbox = useCallback(async (accountId: number, showToast = false) => {
    setInboxLoading(true);
    try {
      const data = await getInbox(accountId);
      setInbox(data.messages);
      if (showToast) Toast.success('邮件已刷新');
    } catch (err) {
      Toast.error(`加载邮件失败: ${err}`);
      setInbox([]);
    } finally {
      setInboxLoading(false);
    }
  }, []);

  useEffect(() => {
    loadSummary();
    loadAccounts(1);
  }, [loadSummary, loadAccounts]);

  const handleSelectAccount = (account: Account) => {
    setSelectedAccount(account);
    setInboxPage(1);
    loadInbox(account.id);
  };

  const toggleSelection = (account: Account, checked: boolean) => {
    const newIds = new Set(selectedIds);
    const newEmails = new Set(selectedEmails);
    if (checked) {
      newIds.add(account.id);
      newEmails.add(account.email);
    } else {
      newIds.delete(account.id);
      newEmails.delete(account.email);
    }
    setSelectedIds(newIds);
    setSelectedEmails(newEmails);
  };

  const toggleSelectAll = (checked: boolean) => {
    const newIds = new Set(selectedIds);
    const newEmails = new Set(selectedEmails);
    accounts.forEach(account => {
      if (checked) {
        newIds.add(account.id);
        newEmails.add(account.email);
      } else {
        newIds.delete(account.id);
        newEmails.delete(account.email);
      }
    });
    setSelectedIds(newIds);
    setSelectedEmails(newEmails);
  };

  const clearSelection = () => {
    setSelectedIds(new Set());
    setSelectedEmails(new Set());
  };

  const openGroupModal = (mode: 'single' | 'batch') => {
    let nextTarget: typeof groupTarget = null;
    if (mode === 'single' && selectedAccount) {
      nextTarget = { mode: 'single', email: selectedAccount.email, accountId: selectedAccount.id };
    }
    if (mode === 'batch' && selectedEmails.size > 0) {
      nextTarget = { mode: 'batch', emails: Array.from(selectedEmails) };
    }
    if (nextTarget) {
      setGroupTarget(nextTarget);
      setGroupVisible(true);
    }
  };

  const handleExport = async () => {
    try {
      const text = await exportAccountsApi(groupFilter || undefined);
      await copyText(text, '导出结果已复制到剪贴板');
    } catch (err) {
      Toast.error(`导出失败: ${err}`);
    }
  };

  const toggleAccountField = async (field: 'is_registered' | 'is_primary') => {
    if (!selectedAccount) return;
    try {
      await updateAccount(selectedAccount.id, { [field]: !selectedAccount[field] });
      Toast.success('账号状态已更新');
      const nextSelectedAccount = { ...selectedAccount, [field]: !selectedAccount[field] };
      setSelectedAccount(nextSelectedAccount);
      await Promise.all([loadSummary(), loadAccounts(currentPage)]);
    } catch (err) {
      Toast.error(`操作失败: ${err}`);
    }
  };

  const filteredInbox = inboxFilter === 'verification' ? inbox.filter(message => message.verification_code) : inbox;
  const inboxTotalPages = Math.max(1, Math.ceil(filteredInbox.length / INBOX_PER_PAGE));
  const visibleInbox = filteredInbox.slice((inboxPage - 1) * INBOX_PER_PAGE, inboxPage * INBOX_PER_PAGE);
  const verificationMessages = inbox.filter(message => message.verification_code);
  const latestCodes = [...verificationMessages]
    .filter(message => message.received_at)
    .sort((left, right) => new Date(right.received_at!).getTime() - new Date(left.received_at!).getTime())
    .slice(0, 3);
  const latestInboxMessage = [...inbox]
    .filter(message => message.received_at)
    .sort((left, right) => new Date(right.received_at!).getTime() - new Date(left.received_at!).getTime())[0];
  const allAccountsSelectedOnPage = accounts.length > 0 && accounts.every(account => selectedIds.has(account.id));

  return (
    <div className="app-shell">
      <header className="shell-header">
        <div className="shell-title-block">
          <Title heading={3} className="shell-title">
            账号管理系统
          </Title>
          <Text type="tertiary" className="shell-subtitle">
            分组、筛选、收件箱查看和验证码处理工作台
          </Text>
        </div>
        <div className="shell-summary-row">
          <div className="summary-stat-card">
            <span className="summary-stat-label">账号总数</span>
            <span className="summary-stat-value">{summary?.accounts ?? 0}</span>
          </div>
          <div className="summary-stat-card">
            <span className="summary-stat-label">已注册</span>
            <span className="summary-stat-value">{summary?.registered ?? 0}</span>
          </div>
          <div className="summary-stat-card">
            <span className="summary-stat-label">主账号</span>
            <span className="summary-stat-value">{summary?.primary ?? 0}</span>
          </div>
          <Button theme="solid" className="export-button" onClick={handleExport}>
            导出 JSON
          </Button>
        </div>
      </header>

      <main className="workspace-grid">
        <section className="workspace-panel workspace-left-rail">
          <div className="left-rail-toolbar">
            <Input
              prefix={<IconSearch />}
              placeholder="搜索邮箱..."
              value={searchQuery}
              onChange={setSearchQuery}
              onBlur={() => loadAccounts(1)}
            />
            <div className="workspace-filter-row">
              <Select
                style={{ width: '100%' }}
                placeholder="所有分组"
                value={groupFilter || undefined}
                onChange={value => {
                  setGroupFilter(String(value || ''));
                  loadAccounts(1);
                }}
              >
                <Select.Option value="">所有分组</Select.Option>
                {groups.map(group => (
                  <Select.Option key={group} value={group}>
                    {group || '(无分组)'}
                  </Select.Option>
                ))}
              </Select>
              <Select
                style={{ width: '100%' }}
                placeholder="所有状态"
                value={statusFilter || undefined}
                onChange={value => {
                  setStatusFilter(String(value || ''));
                  loadAccounts(1);
                }}
              >
                <Select.Option value="">所有状态</Select.Option>
                <Select.Option value="registered">已注册</Select.Option>
                <Select.Option value="unregistered">未注册</Select.Option>
              </Select>
            </div>
            <div className="left-rail-actions">
              <label className="checkbox-row">
                <input type="checkbox" checked={allAccountsSelectedOnPage} onChange={event => toggleSelectAll(event.target.checked)} />
                <Text size="small" type="tertiary">
                  全选本页
                </Text>
              </label>
              <Button size="small" onClick={() => setImportVisible(true)}>
                导入
              </Button>
            </div>
            {selectedEmails.size > 0 && (
              <div className="batch-selection-bar">
                <span className="batch-selection-count">已选 {selectedEmails.size} 项</span>
                <Button size="small" theme="solid" onClick={() => openGroupModal('batch')}>
                  加入分组
                </Button>
                <Button size="small" theme="light" onClick={clearSelection}>
                  清空
                </Button>
              </div>
            )}
          </div>

          <div className="account-list-scroll">
            <Spin spinning={loading}>
              <List
                className="account-list"
                dataSource={accounts}
                renderItem={item => (
                  <List.Item
                    className={`account-list-item ${selectedAccount?.id === item.id ? 'selected' : ''}`}
                    onClick={() => handleSelectAccount(item)}
                  >
                    <div className="account-row">
                      <input
                        type="checkbox"
                        checked={selectedIds.has(item.id)}
                        onChange={event => {
                          event.stopPropagation();
                          toggleSelection(item, event.target.checked);
                        }}
                        onClick={event => event.stopPropagation()}
                      />
                      <div className="account-row-content">
                        <div className="account-email">{item.email}</div>
                        <div className="account-row-meta">
                          <Tag size="small" color={item.is_registered ? 'green' : 'grey'}>
                            {item.is_registered ? '已注册' : '未注册'}
                          </Tag>
                          {item.is_primary && (
                            <Tag size="small" color="indigo">
                              主账号
                            </Tag>
                          )}
                          <Text size="small" type="tertiary">
                            {item.group_name || '默认分组'}
                          </Text>
                        </div>
                      </div>
                    </div>
                  </List.Item>
                )}
                emptyContent={<Empty description="未找到账号" />}
              />
            </Spin>
          </div>

          <div className="panel-footer account-pagination">
            <Pagination
              size="small"
              currentPage={currentPage}
              total={totalAccounts}
              pageSize={ACCOUNTS_PER_PAGE}
              onPageChange={page => loadAccounts(page)}
            />
          </div>
        </section>

        <section className="workspace-center-rail">
          <div className="workspace-panel account-context-strip">
            <div>
              <div className="panel-eyebrow">当前账号</div>
              <div className="context-email">{selectedAccount?.email || '请从左侧选择一个账号'}</div>
            </div>
            {selectedAccount && (
              <div className="context-strip-meta">
                <Tag size="small">分组: {selectedAccount.group_name || '默认分组'}</Tag>
                <Tag size="small" color={selectedAccount.is_registered ? 'green' : 'grey'}>
                  {selectedAccount.is_registered ? '已注册' : '未注册'}
                </Tag>
                <Tag size="small" color={selectedAccount.is_primary ? 'indigo' : 'grey'}>
                  主账号: {selectedAccount.is_primary ? '是' : '否'}
                </Tag>
                <Text size="small" type="tertiary">
                  最后更新: {formatDate(selectedAccount.updated_at)}
                </Text>
              </div>
            )}
          </div>

          <div className="workspace-panel inbox-panel">
            <div className="panel-header inbox-panel-header">
              <div>
                <Title heading={5} className="panel-title">
                  收件箱
                </Title>
                <Text type="tertiary" size="small">
                  {filteredInbox.length} 封邮件{inboxFilter === 'verification' ? '（仅验证码）' : ''}
                </Text>
              </div>
              <div className="inbox-toolbar-actions">
                <ButtonGroup>
                  <Button type={inboxFilter === 'all' ? 'primary' : 'tertiary'} onClick={() => { setInboxFilter('all'); setInboxPage(1); }}>
                    全部
                  </Button>
                  <Button
                    type={inboxFilter === 'verification' ? 'primary' : 'tertiary'}
                    onClick={() => {
                      setInboxFilter('verification');
                      setInboxPage(1);
                    }}
                  >
                    仅验证码
                  </Button>
                </ButtonGroup>
                {inboxTotalPages > 1 && (
                  <div className="pager-cluster">
                    <Button size="small" disabled={inboxPage <= 1} onClick={() => setInboxPage(page => page - 1)}>
                      上一页
                    </Button>
                    <Text>
                      {inboxPage} / {inboxTotalPages}
                    </Text>
                    <Button size="small" disabled={inboxPage >= inboxTotalPages} onClick={() => setInboxPage(page => page + 1)}>
                      下一页
                    </Button>
                  </div>
                )}
                <Button
                  size="small"
                  icon={<IconRefresh />}
                  disabled={!selectedAccount}
                  loading={inboxLoading}
                  onClick={() => selectedAccount && loadInbox(selectedAccount.id, true)}
                >
                  刷新
                </Button>
              </div>
            </div>

            <div className="inbox-scroll-region">
              <Spin spinning={inboxLoading}>
                {!selectedAccount ? (
                  <Empty description="从左侧选择账号后显示收件箱" />
                ) : visibleInbox.length === 0 ? (
                  <Empty description={inboxFilter === 'verification' ? '当前没有验证码邮件' : '收件箱为空'} />
                ) : (
                  <div className="message-grid">
                    {visibleInbox.map(message => (
                      <MessageCard key={message.id} message={message} />
                    ))}
                  </div>
                )}
              </Spin>
            </div>
          </div>
        </section>

        <aside className="workspace-right-rail">
          <div className="workspace-panel status-panel">
            <div className="panel-header compact-panel-header">
              <div>
                <Title heading={5} className="panel-title">
                  账号状态
                </Title>
                <Text type="tertiary">单账号快捷操作</Text>
              </div>
            </div>
            <div className="detail-grid">
              <div className="detail-row">
                <span className="detail-label">邮箱</span>
                <strong>{selectedAccount?.email || '-'}</strong>
              </div>
              <div className="detail-row">
                <span className="detail-label">分组</span>
                <span>{selectedAccount?.group_name || '默认分组'}</span>
              </div>
              <div className="detail-row">
                <span className="detail-label">注册状态</span>
                <span>{selectedAccount?.is_registered ? '已注册' : '未注册'}</span>
              </div>
              <div className="detail-row">
                <span className="detail-label">主账号</span>
                <span>{selectedAccount?.is_primary ? '是' : '否'}</span>
              </div>
              <div className="detail-row">
                <span className="detail-label">最后更新</span>
                <span>{selectedAccount ? formatDate(selectedAccount.updated_at) : '-'}</span>
              </div>
            </div>
            <div className="action-button-grid">
              <Button icon={<IconCopy />} disabled={!selectedAccount} onClick={() => selectedAccount && copyText(selectedAccount.email, '邮箱已复制')}>
                复制邮箱
              </Button>
              <Button
                icon={<IconRefresh />}
                disabled={!selectedAccount}
                loading={inboxLoading}
                onClick={() => selectedAccount && loadInbox(selectedAccount.id, true)}
              >
                刷新邮件
              </Button>
              <Button theme="solid" disabled={!selectedAccount} onClick={() => openGroupModal('single')}>
                加入分组
              </Button>
              <Button disabled={!selectedAccount} onClick={() => toggleAccountField('is_registered')}>
                切换注册状态
              </Button>
              <Button disabled={!selectedAccount} onClick={() => toggleAccountField('is_primary')}>
                切换主账号
              </Button>
            </div>
          </div>

          <div className="workspace-panel summary-panel">
            <div className="panel-header compact-panel-header">
              <div>
                <Title heading={5} className="panel-title">
                  验证码与摘要
                </Title>
                <Text type="tertiary">展示最近 3 个验证码</Text>
              </div>
            </div>
            <div className="summary-scroll-region">
              <div className="summary-detail-grid">
                <div className="detail-row">
                  <span className="detail-label">当前邮件数</span>
                  <span>{inbox.length}</span>
                </div>
                <div className="detail-row">
                  <span className="detail-label">验证码邮件</span>
                  <span>{verificationMessages.length}</span>
                </div>
                <div className="detail-row">
                  <span className="detail-label">最近一封</span>
                  <span>{latestInboxMessage?.received_at ? formatDate(latestInboxMessage.received_at) : '-'}</span>
                </div>
              </div>
              <div className="latest-code-section">
                <div className="panel-eyebrow">最近验证码</div>
                {latestCodes.length === 0 ? (
                  <Empty description="当前没有验证码" image={null} />
                ) : (
                  <div className="latest-code-list">
                    {latestCodes.map(message => (
                      <div key={message.id} className="latest-code-item">
                        <div>
                          <strong className="latest-code-value">{message.verification_code}</strong>
                          <div className="latest-code-meta">
                            {formatDate(message.received_at)} · {message.subject || '(无主题)'}
                          </div>
                        </div>
                        <Button onClick={() => copyText(message.verification_code!, '验证码已复制')}>复制</Button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        </aside>
      </main>

      <ImportModal
        visible={importVisible}
        onClose={() => setImportVisible(false)}
        onSuccess={() => {
          loadSummary();
          loadAccounts(1);
        }}
      />
      <GroupModal
        visible={groupVisible}
        onClose={() => {
          setGroupVisible(false);
          setGroupTarget(null);
        }}
        onSuccess={() => {
          loadSummary();
          loadAccounts(currentPage);
          clearSelection();
        }}
        target={groupTarget}
        groups={groups}
      />
    </div>
  );
}
