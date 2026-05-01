import { Injectable } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';

@Injectable()
export class AdminService {
  constructor(private readonly prisma: PrismaService) {}

  // ----------- Statistics -----------
  async stats() {
    const now = new Date();
    const startOfDay = new Date(now);
    startOfDay.setUTCHours(0, 0, 0, 0);
    const sevenDaysAgo = new Date(Date.now() - 7 * 86_400_000);
    const thirtyDaysAgo = new Date(Date.now() - 30 * 86_400_000);

    const [users, blocked, todaySum, weekSum, monthSum, totalSum, byType] = await Promise.all([
      this.prisma.user.count(),
      this.prisma.user.count({ where: { is_blocked: true } }),
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
    ]);

    return {
      users: { total: users, blocked },
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
    };
  }

  // ----------- Users -----------
  async listUsers(limit = 50, offset = 0) {
    const items = await this.prisma.user.findMany({
      orderBy: { created_at: 'desc' },
      take: Math.min(limit, 200),
      skip: offset,
    });
    return items.map((u) => ({
      id: u.id.toString(),
      username: u.username,
      full_name: u.full_name,
      balance: u.balance,
      is_blocked: u.is_blocked,
      role: u.role,
      total_orders: u.total_orders,
      total_spent: u.total_spent,
      created_at: u.created_at.toISOString(),
    }));
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
  async pendingPayments() {
    const items = await this.prisma.payment.findMany({
      where: { status: 'pending' },
      orderBy: { created_at: 'desc' },
      take: 50,
    });
    return items.map((p) => ({
      id: p.id,
      user_id: p.user_id.toString(),
      amount: p.amount,
      status: p.status,
      screenshot_file_id: p.screenshot_file_id,
      created_at: p.created_at.toISOString(),
    }));
  }

  async approvePayment(id: number) {
    const payment = await this.prisma.payment.update({
      where: { id },
      data: { status: 'approved' },
    });
    await this.prisma.user.update({
      where: { id: payment.user_id },
      data: { balance: { increment: payment.amount } },
    });
    return { ok: true };
  }

  async rejectPayment(id: number) {
    await this.prisma.payment.update({
      where: { id },
      data: { status: 'rejected' },
    });
    return { ok: true };
  }
}
