export interface Summary {
  accounts: number;
  registered: number;
  primary: number;
  groups: Record<string, number>;
}

export interface Account {
  id: number;
  email: string;
  group_name: string | null;
  is_registered: boolean;
  is_primary: boolean;
  updated_at: string | null;
}

export interface AccountsResponse {
  items: Account[];
  total: number;
}

export interface Message {
  id: number;
  subject: string | null;
  from_address: string | null;
  received_at: string | null;
  body_text: string | null;
  body_preview: string | null;
  verification_code: string | null;
}

export interface InboxResponse {
  messages: Message[];
}

interface AccountsParams {
  limit?: number;
  offset?: number;
  query?: string;
  group_name?: string;
  is_registered?: boolean;
}

async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const request: RequestInit = {
    credentials: 'same-origin',
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  };
  if (request.body && typeof request.body === 'object') {
    request.body = JSON.stringify(request.body);
  }

  const response = await fetch(path, request);
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Error ${response.status}`);
  }
  const contentType = response.headers.get('Content-Type');
  if (contentType?.includes('application/json')) {
    return response.json();
  }
  return response.text() as Promise<T>;
}

export async function getSummary(): Promise<Summary> {
  return api<Summary>('/api/summary');
}

export async function getAccounts(params: AccountsParams): Promise<AccountsResponse> {
  const searchParams = new URLSearchParams();
  if (params.limit) searchParams.set('limit', String(params.limit));
  if (params.offset) searchParams.set('offset', String(params.offset));
  if (params.query) searchParams.set('query', params.query);
  if (params.group_name) searchParams.set('group_name', params.group_name);
  if (params.is_registered !== undefined) searchParams.set('is_registered', String(params.is_registered));
  return api<AccountsResponse>(`/api/accounts?${searchParams.toString()}`);
}

export async function getInbox(accountId: number): Promise<InboxResponse> {
  return api<InboxResponse>(`/api/accounts/${accountId}/inbox`);
}

export async function updateAccount(id: number, data: Partial<Account>): Promise<void> {
  await api(`/api/accounts/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export async function bulkUpdate(emails: string[], data: Partial<Account>): Promise<void> {
  await api('/api/accounts/bulk-update', {
    method: 'POST',
    body: JSON.stringify({ emails, ...data }),
  });
}

export async function importTxt(sources: { source_name: string; text: string }[]): Promise<void> {
  await api('/api/accounts/import-txt', {
    method: 'POST',
    body: JSON.stringify({ sources }),
  });
}

export async function exportAccounts(group?: string): Promise<string> {
  const suffix = group ? `?group_name=${encodeURIComponent(group)}` : '';
  return api<string>(`/api/accounts/export${suffix}`);
}
