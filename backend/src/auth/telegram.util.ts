import { createHash, createHmac, timingSafeEqual } from 'crypto';

export interface TelegramUser {
  id: number;
  first_name?: string;
  last_name?: string;
  username?: string;
  language_code?: string;
  photo_url?: string;
}

/**
 * Verify Telegram WebApp `initData` according to:
 * https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
 *
 * Returns the parsed user (and other fields) if valid, or null.
 */
export function verifyWebAppInitData(
  initData: string,
  botToken: string,
  maxAgeSeconds = 86400,
): { user: TelegramUser; auth_date: number } | null {
  if (!initData || !botToken) return null;

  const url = new URLSearchParams(initData);
  const hash = url.get('hash');
  if (!hash) return null;
  url.delete('hash');

  const dataCheckString = [...url.entries()]
    .map(([k, v]) => `${k}=${v}`)
    .sort()
    .join('\n');

  const secret = createHmac('sha256', 'WebAppData').update(botToken).digest();
  const computed = createHmac('sha256', secret).update(dataCheckString).digest('hex');

  const a = Buffer.from(hash, 'hex');
  const b = Buffer.from(computed, 'hex');
  if (a.length !== b.length || !timingSafeEqual(a, b)) return null;

  const auth_date = parseInt(url.get('auth_date') || '0', 10);
  if (!auth_date || Date.now() / 1000 - auth_date > maxAgeSeconds) return null;

  const userJson = url.get('user');
  if (!userJson) return null;
  let user: TelegramUser;
  try {
    user = JSON.parse(userJson) as TelegramUser;
  } catch {
    return null;
  }
  if (!user || typeof user.id !== 'number') return null;

  return { user, auth_date };
}

/**
 * Verify Telegram Login Widget data (different format than WebApp).
 * https://core.telegram.org/widgets/login#checking-authorization
 */
export function verifyLoginWidget(
  payload: Record<string, string>,
  botToken: string,
  maxAgeSeconds = 86400,
): TelegramUser | null {
  const { hash, ...rest } = payload;
  if (!hash) return null;

  const dataCheckString = Object.entries(rest)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([k, v]) => `${k}=${v}`)
    .join('\n');

  const secret = createHash('sha256').update(botToken).digest();
  const computed = createHmac('sha256', secret).update(dataCheckString).digest('hex');

  const a = Buffer.from(hash, 'hex');
  const b = Buffer.from(computed, 'hex');
  if (a.length !== b.length || !timingSafeEqual(a, b)) return null;

  const authDate = parseInt(rest.auth_date || '0', 10);
  if (!authDate || Date.now() / 1000 - authDate > maxAgeSeconds) return null;

  return {
    id: parseInt(rest.id, 10),
    first_name: rest.first_name,
    last_name: rest.last_name,
    username: rest.username,
    photo_url: rest.photo_url,
  };
}
