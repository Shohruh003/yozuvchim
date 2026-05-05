import {
  Injectable,
  UnauthorizedException,
  Logger,
  BadRequestException,
} from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { JwtService } from '@nestjs/jwt';
import { createHash, randomBytes } from 'crypto';
import * as bcrypt from 'bcrypt';

import { PrismaService } from '../prisma/prisma.service';
import { LoginTokensService } from './login-tokens.service';
import { verifyWebAppInitData, TelegramUser } from './telegram.util';

const ADMIN_USER_KEY = 'admin_username';
const ADMIN_HASH_KEY = 'admin_password_hash';

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

  /**
   * Look up the stored admin username/hash, seeding from env on first run
   * if the DB has no record yet.
   */
  private async getAdminCreds(): Promise<{ username: string; hash: string } | null> {
    const [userRow, hashRow] = await Promise.all([
      this.prisma.appSettings.findUnique({ where: { key: ADMIN_USER_KEY } }),
      this.prisma.appSettings.findUnique({ where: { key: ADMIN_HASH_KEY } }),
    ]);

    if (userRow?.value && hashRow?.value) {
      return { username: userRow.value, hash: hashRow.value };
    }

    // Seed from env on first run only.
    const seedUser = (this.config.get<string>('ADMIN_LOGIN_USERNAME') || '').trim();
    const seedPass = this.config.get<string>('ADMIN_LOGIN_PASSWORD') || '';
    if (!seedUser || !seedPass) return null;

    const hash = await bcrypt.hash(seedPass, 12);
    await this.prisma.appSettings.upsert({
      where: { key: ADMIN_USER_KEY },
      create: { key: ADMIN_USER_KEY, value: seedUser },
      update: { value: seedUser },
    });
    await this.prisma.appSettings.upsert({
      where: { key: ADMIN_HASH_KEY },
      create: { key: ADMIN_HASH_KEY, value: hash },
      update: { value: hash },
    });
    this.logger.log('Seeded admin credentials from env into the DB');
    return { username: seedUser, hash };
  }

  /**
   * Web admin login via username + password.
   *
   * Lookup order:
   *   1. Per-user credentials stored on the User row (admin_username +
   *      admin_password_hash). Each admin/superadmin has their own login,
   *      auto-generated when promoted.
   *   2. Shared bootstrap creds (AppSettings, seeded from env). Used for the
   *      very first superadmin before per-user creds exist.
   *
   * Telegram WebApp users don't need this — they auto-login via initData.
   */
  async loginAsAdmin(
    username: string,
    password: string,
    ua?: string,
    ip?: string,
  ): Promise<AuthTokens> {
    const trimmed = username.trim();

    // 1) Per-user lookup
    const user = await this.prisma.user.findUnique({
      where: { admin_username: trimmed },
    });
    if (user && user.admin_password_hash) {
      const ok = await bcrypt.compare(password, user.admin_password_hash);
      if (ok) {
        if (user.role !== 'admin' && user.role !== 'superadmin') {
          throw new UnauthorizedException('User is no longer an admin');
        }
        if (user.is_blocked) throw new UnauthorizedException('User is blocked');
        return this.issueTokens(user.id, ua, ip);
      }
    }

    // 2) Shared bootstrap fallback
    const creds = await this.getAdminCreds();
    if (!creds) throw new UnauthorizedException('Invalid credentials');
    if (trimmed !== creds.username) {
      throw new UnauthorizedException('Invalid credentials');
    }
    const ok = await bcrypt.compare(password, creds.hash);
    if (!ok) throw new UnauthorizedException('Invalid credentials');

    const ids = (this.config.get<string>('SUPERADMIN_IDS') || '')
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);
    if (!ids.length) {
      throw new UnauthorizedException('No superadmin configured');
    }
    const userId = BigInt(ids[0]);

    await this.prisma.user.upsert({
      where: { id: userId },
      update: { role: 'superadmin' },
      create: {
        id: userId,
        username: creds.username,
        full_name: `Admin ${creds.username}`,
        role: 'superadmin',
      },
    });

    return this.issueTokens(userId, ua, ip);
  }

  /**
   * Update the *current admin's own* login username and/or password.
   * If the caller has a per-user admin login (User.admin_username), we update
   * that row. Otherwise we fall back to the shared bootstrap creds.
   */
  async updateAdminCreds(
    callerId: bigint,
    currentPassword: string | undefined,
    newUsername?: string,
    newPassword?: string,
  ): Promise<{ ok: true; username: string }> {
    const me = await this.prisma.user.findUnique({ where: { id: callerId } });

    if (me?.admin_username && me.admin_password_hash) {
      // Per-user creds path
      if (currentPassword) {
        const ok = await bcrypt.compare(currentPassword, me.admin_password_hash);
        if (!ok) throw new UnauthorizedException('Current password is incorrect');
      }
      const username = (newUsername ?? me.admin_username).trim();
      if (!username) throw new BadRequestException('Username cannot be empty');

      // Username must stay unique
      if (username !== me.admin_username) {
        const clash = await this.prisma.user.findUnique({
          where: { admin_username: username },
        });
        if (clash && clash.id !== callerId) {
          throw new BadRequestException('Username is taken');
        }
      }

      let hash = me.admin_password_hash;
      if (newPassword) {
        if (newPassword.length < 8) {
          throw new BadRequestException('Password must be at least 8 characters');
        }
        hash = await bcrypt.hash(newPassword, 12);
      }
      await this.prisma.user.update({
        where: { id: callerId },
        data: { admin_username: username, admin_password_hash: hash },
      });
      this.logger.log(`Admin credentials updated for user ${callerId}`);
      return { ok: true, username };
    }

    // Fallback: shared bootstrap creds (legacy)
    const creds = await this.getAdminCreds();
    if (!creds) throw new UnauthorizedException('Admin login is not configured');

    if (currentPassword) {
      const ok = await bcrypt.compare(currentPassword, creds.hash);
      if (!ok) throw new UnauthorizedException('Current password is incorrect');
    }
    const username = (newUsername ?? creds.username).trim();
    if (!username) throw new BadRequestException('Username cannot be empty');

    let hash = creds.hash;
    if (newPassword) {
      if (newPassword.length < 8) {
        throw new BadRequestException('Password must be at least 8 characters');
      }
      hash = await bcrypt.hash(newPassword, 12);
    }
    await this.prisma.appSettings.upsert({
      where: { key: ADMIN_USER_KEY },
      create: { key: ADMIN_USER_KEY, value: username },
      update: { value: username },
    });
    await this.prisma.appSettings.upsert({
      where: { key: ADMIN_HASH_KEY },
      create: { key: ADMIN_HASH_KEY, value: hash },
      update: { value: hash },
    });
    this.logger.log('Shared bootstrap admin credentials updated');
    return { ok: true, username };
  }

  /** Read the caller's web-login username (per-user, falls back to shared). */
  async getMyAdminUsername(callerId: bigint): Promise<string> {
    const me = await this.prisma.user.findUnique({ where: { id: callerId } });
    if (me?.admin_username) return me.admin_username;
    const creds = await this.getAdminCreds();
    return creds?.username ?? '';
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
