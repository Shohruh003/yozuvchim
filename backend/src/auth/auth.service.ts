import {
  Injectable,
  UnauthorizedException,
  Logger,
} from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { JwtService } from '@nestjs/jwt';
import { createHash, randomBytes } from 'crypto';

import { PrismaService } from '../prisma/prisma.service';
import { LoginTokensService } from './login-tokens.service';
import { verifyWebAppInitData, TelegramUser } from './telegram.util';

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
}

@Injectable()
export class AuthService {
  private readonly logger = new Logger(AuthService.name);

  constructor(
    private readonly prisma: PrismaService,
    private readonly jwt: JwtService,
    private readonly config: ConfigService,
    private readonly tokens: LoginTokensService,
  ) {}

  // ------------------------------------------------------------
  // Login flows
  // ------------------------------------------------------------

  /** Login via Telegram WebApp initData (preferred when available). */
  async loginWithWebApp(initData: string, ua?: string, ip?: string): Promise<AuthTokens> {
    const botToken = this.config.get<string>('BOT_TOKEN') || '';
    const verified = verifyWebAppInitData(initData, botToken);
    if (!verified) throw new UnauthorizedException('Invalid Telegram initData');

    await this.upsertUser(verified.user);
    return this.issueTokens(BigInt(verified.user.id), ua, ip);
  }

  /** Login via one-time token issued by the bot (fallback when initData unavailable). */
  async loginWithToken(token: string, ua?: string, ip?: string): Promise<AuthTokens> {
    const userId = await this.tokens.consume(token);
    if (!userId) throw new UnauthorizedException('Invalid or expired token');

    // Make sure a user row exists
    await this.prisma.user.upsert({
      where: { id: userId },
      update: {},
      create: { id: userId, username: '', full_name: `User ${userId}` },
    });

    return this.issueTokens(userId, ua, ip);
  }

  /** Refresh access + refresh tokens. */
  async refresh(refreshToken: string, ua?: string, ip?: string): Promise<AuthTokens> {
    if (!refreshToken) throw new UnauthorizedException('Missing refresh token');

    const hash = this.hashToken(refreshToken);
    const session = await this.prisma.session.findUnique({ where: { refresh_hash: hash } });
    if (!session || session.expires_at < new Date()) {
      throw new UnauthorizedException('Refresh token invalid or expired');
    }

    // Rotate: delete old, issue new
    await this.prisma.session.delete({ where: { id: session.id } });
    return this.issueTokens(session.user_id, ua, ip);
  }

  /** Revoke a session (logout). */
  async logout(refreshToken?: string): Promise<void> {
    if (!refreshToken) return;
    const hash = this.hashToken(refreshToken);
    await this.prisma.session.deleteMany({ where: { refresh_hash: hash } });
  }

  // ------------------------------------------------------------
  // Internal helpers
  // ------------------------------------------------------------

  private async upsertUser(tg: TelegramUser): Promise<void> {
    const fullName = [tg.first_name, tg.last_name].filter(Boolean).join(' ').trim();
    await this.prisma.user.upsert({
      where: { id: BigInt(tg.id) },
      update: {
        username: tg.username || '',
        full_name: fullName || tg.username || `User ${tg.id}`,
      },
      create: {
        id: BigInt(tg.id),
        username: tg.username || '',
        full_name: fullName || tg.username || `User ${tg.id}`,
        language_code: tg.language_code || 'uz',
      },
    });
  }

  private async issueTokens(userId: bigint, ua?: string, ip?: string): Promise<AuthTokens> {
    const accessSecret = this.config.get<string>('JWT_SECRET');
    const refreshSecret = this.config.get<string>('JWT_REFRESH_SECRET');
    const accessTtl = this.config.get<string>('JWT_ACCESS_EXPIRES_IN') || '15m';
    const refreshTtl = this.config.get<string>('JWT_REFRESH_EXPIRES_IN') || '7d';

    const payload = { sub: userId.toString() };
    const access_token = await this.jwt.signAsync(payload, {
      secret: accessSecret,
      expiresIn: accessTtl as any,
    });
    const refresh_token = randomBytes(48).toString('base64url');

    const refreshExpiresAt = this.parseDuration(refreshTtl);
    await this.prisma.session.create({
      data: {
        user_id: userId,
        refresh_hash: this.hashToken(refresh_token),
        user_agent: ua?.slice(0, 256),
        ip: ip?.slice(0, 64),
        expires_at: refreshExpiresAt,
      },
    });

    return { access_token, refresh_token };
  }

  private hashToken(token: string): string {
    return createHash('sha256').update(token).digest('hex');
  }

  /** Parse "7d", "15m", "1h" → Date in the future */
  private parseDuration(s: string): Date {
    const m = /^(\d+)\s*([smhd])$/.exec(s.trim());
    if (!m) return new Date(Date.now() + 7 * 86400 * 1000);
    const n = parseInt(m[1], 10);
    const unit = m[2];
    const ms =
      unit === 's' ? n * 1000 :
      unit === 'm' ? n * 60_000 :
      unit === 'h' ? n * 3_600_000 :
      n * 86_400_000;
    return new Date(Date.now() + ms);
  }
}
