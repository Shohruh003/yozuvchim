import { Injectable } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { Redis } from 'ioredis';
import { randomBytes } from 'crypto';

const KEY_PREFIX = 'login_token:';
const TTL_SECONDS = 3600; // 1 hour

@Injectable()
export class LoginTokensService {
  private readonly redis: Redis;

  constructor(config: ConfigService) {
    this.redis = new Redis(
      config.get<string>('REDIS_URL') || 'redis://localhost:6379',
      { lazyConnect: false, maxRetriesPerRequest: 3 },
    );
  }

  /** Issue a new one-time login token for the bot to embed in WebApp URL. */
  async make(userId: bigint | number): Promise<string> {
    const token = randomBytes(24).toString('base64url');
    await this.redis.set(KEY_PREFIX + token, String(userId), 'EX', TTL_SECONDS);
    return token;
  }

  /** Validate a token; returns user id if valid (token remains usable until TTL). */
  async consume(token: string): Promise<bigint | null> {
    if (!token) return null;
    const value = await this.redis.get(KEY_PREFIX + token);
    if (!value) return null;
    return BigInt(value);
  }
}
