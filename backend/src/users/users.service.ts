import { Injectable, NotFoundException } from '@nestjs/common';
import { PrismaService } from '../prisma/prisma.service';

@Injectable()
export class UsersService {
  constructor(private readonly prisma: PrismaService) {}

  async profile(userId: bigint) {
    const user = await this.prisma.user.findUnique({ where: { id: userId } });
    if (!user) throw new NotFoundException('User not found');

    const [orders, completed, spentRow] = await Promise.all([
      this.prisma.request.count({ where: { user_id: userId, is_deleted: false } }),
      this.prisma.request.count({
        where: { user_id: userId, status: 'done', is_deleted: false },
      }),
      this.prisma.payment.aggregate({
        where: { user_id: userId, status: 'approved' },
        _sum: { amount: true },
      }),
    ]);

    return {
      id: user.id.toString(),
      username: user.username,
      full_name: user.full_name,
      balance: user.balance,
      plan: user.plan,
      role: user.role,
      language: user.language_code,
      total_documents: user.total_documents,
      total_orders: orders,
      completed_orders: completed,
      total_spent: spentRow._sum.amount ?? 0,
      vip_expires_at: user.vip_expires_at,
      referral_count: user.referral_count,
      has_used_free_trial: user.has_used_free_trial,
    };
  }
}
