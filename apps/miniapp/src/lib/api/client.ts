import { getTelegramWebApp } from '$lib/telegram/webapp';

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
    public readonly body?: unknown
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

export class ApiClient {
  private readonly baseUrl: string;

  constructor(baseUrl = '', private readonly initData = getTelegramWebApp().initData) {
    this.baseUrl = baseUrl.replace(/\/$/, '');
  }

  async get<T>(path: string): Promise<T> {
    return this.request<T>(path, { method: 'GET' });
  }

  async post<T>(path: string, body: unknown, actionId: string): Promise<T> {
    return this.request<T>(path, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Request-ID': actionId
      },
      body: JSON.stringify(body)
    });
  }

  private async request<T>(path: string, init: RequestInit): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      ...init,
      headers: {
        'X-Telegram-Init-Data': this.initData,
        ...init.headers
      }
    });
    const body = await response.json().catch(() => undefined);
    if (!response.ok) {
      throw new ApiError(response.status, `API request failed with ${response.status}`, body);
    }
    return body as T;
  }
}
