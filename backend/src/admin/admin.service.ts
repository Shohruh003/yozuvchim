import { Injectable, Logger, NotFoundException } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { Prisma } from '@prisma/client';
import * as bcrypt from 'bcrypt';
import { randomBytes } from 'crypto';
import { PrismaService } from '../prisma/prisma.service';

function generatePassword(len = 14): string {
  // base64url, no ambiguous chars (no padding) — easy to copy-paste
  return randomBytes(len)
    .toString('base64url')
    .replace(/[-_]/g, '')
    .slice(0, len);
}

function generateUsernameFor(userId: bigint, fullName: string): string {
  const slug = (fullName || '')
    .toLowerCase()
    .replace(/[^a-z0-9]/g, '')
    .slice(0, 12);
  const idTail = userId.toString().slice(-5);
  return slug ? `${slug}_${idTail}` : `admin_${idTail}`;
}

@Injectable()
export class AdminService {
  private readonly logger = new Logger(AdminService.name);

  constructor(
    private readonly prisma: PrismaService,
    private readonly config: ConfigService,
  ) {}

  /**
   * Best-effort: edit/clean up the Telegram messages the bot sent to admins
   * for a payment, so they reflect the new approved/rejected status.
   */
  private async notifyAdminsFinalised(
    paymentId: number,
    text: string,
  ): Promise<void> {
    const botToken = this.config.get<string>('BOT_TOKEN') || '';
    if (!botToken) return;

    const messages = await this.prisma.paymentAdminMessage.findMany({
      where: { payment_id: paymentId },
    });
    if (!messages.length) return;

    await Promise.allSettled(
      messages.map(async (m) => {
        // Drop the inline keyboard and replace the text. If editing fails
        // (e.g. message deleted), we silently skip.
        const url = `https://api.telegram.org/bot${botToken}/editMessageText`;
        const body = {
          chat_id: m.admin_id.toString(),
          message_id: m.message_id,
          text,
          parse_mode: 'HTML',
        };
        try {
          const res = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
          });
          if (!res.ok) {
            this.logger.warn(
              `editMessageText failed for admin ${m.admin_id}: ${res.status}`,
            );
          }
        } catch (e) {
          this.logger.warn(`Telegram edit failed: ${e}`);
        }
      }),
    );

    // Clean up — these messages no longer need tracking.
    await this.prisma.paymentAdminMessage.deleteMany({
      where: { payment_id: paymentId },
    });
  }

  // ----------- Statistics -----------
  async stats() {
    const now = new Date();
    const startOfDay = new Date(now);
    startOfDay.setUTCHours(0, 0, 0, 0);
    const sevenDaysAgo = new Date(Date.now() - 7 * 86_400_000);
    const thirtyDaysAgo = new Date(Date.now() - 30 * 86_400_000);

    const [
      users,
      blocked,
      newUsersWeek,
      ordersTotal,
      ordersToday,
      todaySum,
      weekSum,
      monthSum,
      totalSum,
      byType,
      byStatus,
      revenueRows,
      growthRows,
    ] = await Promise.all([
      this.prisma.user.count(),
      this.prisma.user.count({ where: { is_blocked: true } }),
      this.prisma.user.count({ where: { created_at: { gte: sevenDaysAgo } } }),
      this.prisma.request.count({ where: { is_deleted: false } }),
      this.prisma.request.count({
        where: { is_deleted: false, created_at: { gte: startOfDay } },
      }),
      this.prisma.payment.aggregate({
        _sum: { amount: true },
        where: { status: 'approved', created_at: { gte: startOfDay } },
      }),
      this.prisma.payment.aggregate({
        _sum: { amount: true },
        where: { status: 'approved', created_at: { gte: sevenDaysAgo } },
      }),
      this.prisma.payment.aggregate({
        _sum: { amount: true },
        where: { status: 'approved', created_at: { gte: thirtyDaysAgo } },
      }),
      this.prisma.payment.aggregate({
        _sum: { amount: true },
        where: { status: 'approved' },
      }),
      this.prisma.request.groupBy({
        by: ['doc_type'],
        _count: { _all: true },
        where: { is_deleted: false },
      }),
      this.prisma.request.groupBy({
        by: ['status'],
        _count: { _all: true },
        where: { is_deleted: false },
      }),
      // Daily approved revenue (last 30 days) — Postgres `date_trunc`
      this.prisma.$queryRaw<Array<{ day: Date; total: bigint }>>(Prisma.sql`
        SELECT date_trunc('day', created_at) AS day, COALESCE(SUM(amount), 0)::bigint AS total
        FROM payments
        WHERE status = 'approved' AND created_at >= ${thirtyDaysAgo}
        GROUP BY 1
        ORDER BY 1 ASC
      `),
      // Daily new users (last 30 days)
      this.prisma.$queryRaw<Array<{ day: Date; total: bigint }>>(Prisma.sql`
        SELECT date_trunc('day', created_at) AS day, COUNT(*)::bigint AS total
        FROM users
        WHERE created_at >= ${thirtyDaysAgo}
        GROUP BY 1
        ORDER BY 1 ASC
      `),
    ]);

    const fillSeries = (
      rows: Array<{ day: Date; total: bigint }>,
      days: number,
    ) => {
      const map = new Map<string, number>();
      for (const r of rows) {
        const key = new Date(r.day).toISOString().slice(0, 10);
        map.set(key, Number(r.total));
      }
      const out: Array<{ date: string; value: number }> = [];
      for (let i = days - 1; i >= 0; i--) {
        const d = new Date(Date.now() - i * 86_400_000);
        const key = d.toISOString().slice(0, 10);
        out.push({ date: key, value: map.get(key) ?? 0 });
      }
      return out;
    };

    return {
      users: { total: users, blocked, new_this_week: newUsersWeek },
      orders: { total: ordersTotal, today: ordersToday },
      revenue: {
        today: todaySum._sum.amount ?? 0,
        week: weekSum._sum.amount ?? 0,
        month: monthSum._sum.amount ?? 0,
        total: totalSum._sum.amount ?? 0,
      },
      orders_by_type: byType.map((r) => ({
        doc_type: r.doc_type,
        count: r._count._all,
      })),
      orders_by_status: byStatus.map((r) => ({
        status: r.status,
        count: r._count._all,
      })),
      revenue_series: fillSeries(revenueRows, 30),
      users_growth: fillSeries(growthRows, 30),
    };
  }

  // ----------- Users -----------
  async listUsers(limit = 50, offset = 0, search = '') {
    const where: Prisma.UserWhereInput = search
      ? {
          OR: [
            { username: { contains: search, mode: 'insensitive' } },
            { full_name: { contains: search, mode: 'insensitive' } },
          ],
        }
      : {};

    const [items, total] = await Promise.all([
      this.prisma.user.findMany({
        where,
        orderBy: { created_at: 'desc' },
        take: Math.min(limit, 200),
        skip: offset,
      }),
      this.prisma.user.count({ where }),
    ]);

    return {
      total,
      items: items.map((u) => ({
        id: u.id.toString(),
        username: u.username,
        full_name: u.full_name,
        balance: u.balance,
        is_blocked: u.is_blocked,
        role: u.role,
        total_orders: u.total_orders,
        total_spent: u.total_spent,
        created_at: u.created_at.toISOString(),
      })),
    };
  }

  async setBlocked(userId: bigint, blocked: boolean) {
    await this.prisma.user.update({
      where: { id: userId },
      data: { is_blocked: blocked },
    });
    return { ok: true };
  }

  async adjustBalance(userId: bigint, delta: number) {
    const user = await this.prisma.user.update({
      where: { id: userId },
      data: { balance: { increment: delta } },
    });
    return { id: user.id.toString(), balance: user.balance };
  }

  // ----------- Pending payments -----------
  async pendingPayments(limit = 20, offset = 0) {
    const where = { status: 'pending' };
    const [items, total] = await Promise.all([
      this.prisma.payment.findMany({
        where,
        orderBy: { created_at: 'desc' },
        take: Math.min(limit, 100),
        skip: offset,
        include: { user: { select: { username: true, full_name: true } } },
      }),
      this.prisma.payment.count({ where }),
    ]);
    return {
      total,
      items: items.map((p) => ({
        id: p.id,
        user_id: p.user_id.toString(),
        username: p.user?.username ?? '',
        full_name: p.user?.full_name ?? '',
        amount: p.amount,
        status: p.status,
        screenshot_file_id: p.screenshot_file_id,
        created_at: p.created_at.toISOString(),
      })),
    };
  }

  async approvePayment(id: number, amount?: number) {
    const result = await this.prisma.$transaction(async (tx) => {
      const existing = await tx.payment.findUnique({ where: { id } });
      if (!existing) throw new NotFoundException('Payment not found');
      if (existing.status !== 'pending') {
        throw new NotFoundException('Already processed');
      }

      // Admin can override the amount (screenshot-based payments arrive with 0).
      const finalAmount =
        typeof amount === 'number' && amount > 0 ? Math.floor(amount) : existing.amount;
      if (!finalAmount || finalAmount <= 0) {
        throw new NotFoundException('Amount required');
      }

      await tx.payment.update({
        where: { id },
        data: { status: 'approved', amount: finalAmount },
      });
      await tx.user.update({
        where: { id: existing.user_id },
        data: { balance: { increment: finalAmount } },
      });
      return { ok: true, amount: finalAmount, invoice_id: existing.invoice_id };
    });

    // Update admin notifications in Telegram (best-effort)
    void this.notifyAdminsFinalised(
      id,
      `💰 <b>To'lov cheki</b>\n` +
        `Invoice: <code>${result.invoice_id}</code>\n\n` +
        `✅ <b>Tasdiqlandi</b> — ${result.amount.toLocaleString('uz-UZ')} so'm\n` +
        `Web admin panel orqali ko'rib chiqildi.`,
    );

    return { ok: true, amount: result.amount };
  }

  async rejectPayment(id: number) {
    const existing = await this.prisma.payment.findUnique({ where: { id } });
    if (!existing) throw new NotFoundException('Payment not found');
    if (existing.status !== 'pending') {
      throw new NotFoundException('Already processed');
    }
    await this.prisma.payment.update({
      where: { id },
      data: { status: 'rejected' },
    });
    void this.notifyAdminsFinalised(
      id,
      `💰 <b>To'lov cheki</b>\n` +
        `Invoice: <code>${existing.invoice_id}</code>\n\n` +
        `❌ <b>Rad etildi</b>\n` +
        `Web admin panel orqali ko'rib chiqildi.`,
    );
    return { ok: true };
  }

  async getPaymentFileId(id: number): Promise<string> {
    const p = await this.prisma.payment.findUnique({ where: { id } });
    if (!p?.screenshot_file_id) throw new NotFoundException('No screenshot');
    return p.screenshot_file_id;
  }

  // ----------- Transactions list (filterable by date range) -----------
  async listTransactions(opts: {
    from?: Date;
    to?: Date;
    status?: string;
    limit?: number;
    offset?: number;
  }) {
    const where: Prisma.PaymentWhereInput = {};
    if (opts.from || opts.to) {
      where.created_at = {};
      if (opts.from) (where.created_at as any).gte = opts.from;
      if (opts.to) (where.created_at as any).lte = opts.to;
    }
    if (opts.status && opts.status !== 'all') where.status = opts.status;

    const limit = Math.min(opts.limit ?? 50, 200);
    const offset = opts.offset ?? 0;

    const [items, total, sumApproved] = await Promise.all([
      this.prisma.payment.findMany({
        where,
        orderBy: { created_at: 'desc' },
        take: limit,
        skip: offset,
        include: { user: { select: { username: true, full_name: true } } },
      }),
      this.prisma.payment.count({ where }),
      this.prisma.payment.aggregate({
        _sum: { amount: true },
        _count: { _all: true },
        where: { ...where, status: 'approved' },
      }),
    ]);

    return {
      total,
      sum_approved: sumApproved._sum.amount ?? 0,
      count_approved: sumApproved._count._all,
      items: items.map((p) => ({
        id: p.id,
        user_id: p.user_id.toString(),
        username: p.user?.username ?? '',
        full_name: p.user?.full_name ?? '',
        invoice_id: p.invoice_id,
        amount: p.amount,
        status: p.status,
        created_at: p.created_at.toISOString(),
      })),
    };
  }

  // ----------- Revenue timeseries (filterable + bucketed) -----------
  async revenueTimeseries(opts: { from: Date; to: Date; bucket: 'hour' | 'day' }) {
    const { from, to, bucket } = opts;
    const trunc = bucket === 'hour' ? 'hour' : 'day';

    const rows = await this.prisma.$queryRaw<Array<{ ts: Date; total: bigint }>>(Prisma.sql`
      SELECT date_trunc(${trunc}, created_at) AS ts,
             COALESCE(SUM(amount), 0)::bigint AS total
      FROM payments
      WHERE status = 'approved'
        AND created_at >= ${from}
        AND created_at <= ${to}
      GROUP BY 1
      ORDER BY 1 ASC
    `);

    // Fill missing buckets with zeros so the chart axis is continuous
    const stepMs = bucket === 'hour' ? 3_600_000 : 86_400_000;
    const map = new Map<number, number>();
    for (const r of rows) {
      const t = new Date(r.ts).getTime();
      map.set(t, Number(r.total));
    }
    const out: Array<{ ts: string; value: number }> = [];
    const start = new Date(from);
    if (bucket === 'hour') start.setMinutes(0, 0, 0);
    else start.setUTCHours(0, 0, 0, 0);
    for (let t = start.getTime(); t <= to.getTime(); t += stepMs) {
      out.push({ ts: new Date(t).toISOString(), value: map.get(t) ?? 0 });
    }
    return out;
  }

  // ----------- User detail (for drawer) -----------
  async userDetail(userId: bigint) {
    const user = await this.prisma.user.findUnique({ where: { id: userId } });
    if (!user) throw new NotFoundException('User not found');

    const [ordersCount, completedCount, paymentsCount, spentSum] = await Promise.all([
      this.prisma.request.count({ where: { user_id: userId, is_deleted: false } }),
      this.prisma.request.count({
        where: { user_id: userId, is_deleted: false, status: 'done' },
      }),
      this.prisma.payment.count({ where: { user_id: userId } }),
      this.prisma.payment.aggregate({
        _sum: { amount: true },
        where: { user_id: userId, status: 'approved' },
      }),
    ]);

    return {
      user: {
        id: user.id.toString(),
        username: user.username,
        full_name: user.full_name,
        balance: user.balance,
        is_blocked: user.is_blocked,
        role: user.role,
        language: user.language_code,
        plan: user.plan,
        has_used_free_trial: user.has_used_free_trial,
        created_at: user.created_at.toISOString(),
        last_active: user.last_active.toISOString(),
      },
      stats: {
        total_orders: ordersCount,
        completed_orders: completedCount,
        total_payments: paymentsCount,
        total_spent: spentSum._sum.amount ?? 0,
      },
    };
  }

  async userOrders(userId: bigint, limit = 20, offset = 0) {
    const where = { user_id: userId, is_deleted: false };
    const [items, total] = await Promise.all([
      this.prisma.request.findMany({
        where,
        orderBy: { created_at: 'desc' },
        take: Math.min(limit, 100),
        skip: offset,
        select: {
          id: true,
          doc_type: true,
          title: true,
          status: true,
          length: true,
          price: true,
          is_free: true,
          created_at: true,
        },
      }),
      this.prisma.request.count({ where }),
    ]);
    return {
      total,
      items: items.map((o) => ({
        id: o.id,
        doc_type: o.doc_type,
        title: o.title,
        status: o.status,
        length: o.length,
        price: o.price,
        is_free: o.is_free,
        created_at: o.created_at.toISOString(),
      })),
    };
  }

  async userPayments(userId: bigint, limit = 20, offset = 0) {
    const where = { user_id: userId };
    const [items, total] = await Promise.all([
      this.prisma.payment.findMany({
        where,
        orderBy: { created_at: 'desc' },
        take: Math.min(limit, 100),
        skip: offset,
      }),
      this.prisma.payment.count({ where }),
    ]);
    return {
      total,
      items: items.map((p) => ({
        id: p.id,
        amount: p.amount,
        status: p.status,
        invoice_id: p.invoice_id,
        created_at: p.created_at.toISOString(),
      })),
    };
  }

  // ----------- Superadmin: role management -----------
  async setRole(
    actorId: bigint,
    userId: bigint,
    role: 'user' | 'admin' | 'superadmin',
  ) {
    if (role !== 'user' && role !== 'admin' && role !== 'superadmin') {
      throw new NotFoundException('Invalid role');
    }

    const target = await this.prisma.user.findUnique({ where: { id: userId } });
    if (!target) throw new NotFoundException('User not found');

    if (
      actorId === userId &&
      target.role === 'superadmin' &&
      role !== 'superadmin'
    ) {
      throw new NotFoundException('You cannot demote yourself');
    }

    if (target.role === 'superadmin' && role !== 'superadmin') {
      const otherSuperadmins = await this.prisma.user.count({
        where: { role: 'superadmin', id: { not: userId } },
      });
      if (otherSuperadmins === 0) {
        throw new NotFoundException(
          'Cannot demote the last superadmin. Promote another superadmin first.',
        );
      }
    }

    const promoting = (role === 'admin' || role === 'superadmin');
    const wasNotAdmin = !target.admin_username;

    let credentials: { username: string; password: string } | null = null;
    const data: Prisma.UserUpdateInput = { role };

    if (promoting && wasNotAdmin) {
      // Auto-generate per-user web login the first time someone is promoted.
      let username = generateUsernameFor(userId, target.full_name || target.username || '');
      // Ensure uniqueness (pad with random if collision)
      let attempt = 0;
      while (
        await this.prisma.user.findUnique({ where: { admin_username: username } })
      ) {
        attempt += 1;
        username = `${generateUsernameFor(userId, target.full_name || '')}${attempt}`;
        if (attempt > 5) break;
      }
      const password = generatePassword(14);
      const hash = await bcrypt.hash(password, 12);
      data.admin_username = username;
      data.admin_password_hash = hash;
      credentials = { username, password };
    }

    const u = await this.prisma.user.update({ where: { id: userId }, data });
    return {
      id: u.id.toString(),
      role: u.role,
      // Returned ONLY on first promotion, plain-text password for the
      // promoting superadmin to copy & forward. Never shown again.
      credentials,
    };
  }

  /** Reset/regenerate a user's web login password (returns plaintext once). */
  async resetAdminPassword(userId: bigint) {
    const user = await this.prisma.user.findUnique({ where: { id: userId } });
    if (!user) throw new NotFoundException('User not found');
    if (user.role !== 'admin' && user.role !== 'superadmin') {
      throw new NotFoundException('User is not an admin');
    }
    const username = user.admin_username
      || generateUsernameFor(userId, user.full_name || user.username || '');
    const password = generatePassword(14);
    const hash = await bcrypt.hash(password, 12);
    await this.prisma.user.update({
      where: { id: userId },
      data: { admin_username: username, admin_password_hash: hash },
    });
    return { username, password };
  }

  // ----------- Superadmin: list admins with activity counts -----------
  async listAdmins() {
    const admins = await this.prisma.user.findMany({
      where: { role: { in: ['admin', 'superadmin'] } },
      orderBy: { created_at: 'asc' },
    });
    if (!admins.length) return [];

    const ids = admins.map((a) => a.id);
    const counts = await this.prisma.request.groupBy({
      by: ['user_id', 'doc_type'],
      _count: { _all: true },
      where: { user_id: { in: ids }, is_deleted: false },
    });

    const totals = await this.prisma.request.groupBy({
      by: ['user_id'],
      _count: { _all: true },
      where: { user_id: { in: ids }, is_deleted: false },
    });

    const totalsMap = new Map<string, number>(
      totals.map((t) => [t.user_id.toString(), t._count._all]),
    );
    const breakdownMap = new Map<string, Record<string, number>>();
    for (const c of counts) {
      const k = c.user_id.toString();
      const m = breakdownMap.get(k) ?? {};
      m[c.doc_type] = c._count._all;
      breakdownMap.set(k, m);
    }

    return admins.map((a) => ({
      id: a.id.toString(),
      username: a.username,
      full_name: a.full_name,
      role: a.role,
      created_at: a.created_at.toISOString(),
      last_active: a.last_active.toISOString(),
      total_orders: totalsMap.get(a.id.toString()) ?? 0,
      by_type: breakdownMap.get(a.id.toString()) ?? {},
    }));
  }

  // ----------- Payment cards (CRUD) -----------
  async listCards() {
    const items = await this.prisma.paymentCard.findMany({
      orderBy: [{ sort_order: 'asc' }, { id: 'asc' }],
    });
    return items.map((c) => ({
      id: c.id,
      number: c.number,
      holder: c.holder,
      bank: c.bank,
      is_active: c.is_active,
      sort_order: c.sort_order,
      created_at: c.created_at.toISOString(),
    }));
  }

  async createCard(data: {
    number: string;
    holder: string;
    bank?: string;
    is_active?: boolean;
    sort_order?: number;
  }) {
    const c = await this.prisma.paymentCard.create({
      data: {
        number: data.number.trim(),
        holder: data.holder.trim(),
        bank: (data.bank || '').trim(),
        is_active: data.is_active ?? true,
        sort_order: data.sort_order ?? 0,
      },
    });
    return { id: c.id };
  }

  async updateCard(
    id: number,
    data: {
      number?: string;
      holder?: string;
      bank?: string;
      is_active?: boolean;
      sort_order?: number;
    },
  ) {
    const c = await this.prisma.paymentCard.update({
      where: { id },
      data: {
        ...(data.number !== undefined && { number: data.number.trim() }),
        ...(data.holder !== undefined && { holder: data.holder.trim() }),
        ...(data.bank !== undefined && { bank: data.bank.trim() }),
        ...(data.is_active !== undefined && { is_active: data.is_active }),
        ...(data.sort_order !== undefined && { sort_order: data.sort_order }),
      },
    });
    return { id: c.id };
  }

  async deleteCard(id: number) {
    await this.prisma.paymentCard.delete({ where: { id } });
    return { ok: true };
  }

  // ----------- Superadmin: a specific admin's order list -----------
  async adminActivity(userId: bigint, limit = 100) {
    const orders = await this.prisma.request.findMany({
      where: { user_id: userId, is_deleted: false },
      orderBy: { created_at: 'desc' },
      take: Math.min(limit, 500),
      select: {
        id: true,
        doc_type: true,
        title: true,
        status: true,
        length: true,
        price: true,
        is_free: true,
        created_at: true,
      },
    });
    return orders.map((o) => ({
      id: o.id,
      doc_type: o.doc_type,
      title: o.title,
      status: o.status,
      length: o.length,
      price: o.price,
      is_free: o.is_free,
      created_at: o.created_at.toISOString(),
    }));
  }
}
