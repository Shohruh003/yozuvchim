import { Injectable, Logger } from '@nestjs/common';
import { Cron, CronExpression } from '@nestjs/schedule';

import { PrismaService } from '../prisma/prisma.service';

/**
 * Periodic job: refund users for failed/cancelled orders.
 * - Runs every 30 seconds.
 * - Picks orders where status ∈ ('error','cancelled') AND meta.refunded != true AND price > 0.
 * - Adds the *exact charged_price* (saved in meta when the order was created) back to the user balance.
 * - Marks meta.refunded = true so the refund only happens once.
 */
@Injectable()
export class RefundsService {
  private readonly logger = new Logger(RefundsService.name);

  constructor(private readonly prisma: PrismaService) {}

  @Cron(CronExpression.EVERY_30_SECONDS)
  async sweep() {
    const failed = await this.prisma.request.findMany({
      where: {
        status: { in: ['error', 'cancelled'] },
        is_free: false,
        price: { gt: 0 },
      },
      orderBy: { id: 'asc' },
      take: 50,
    });

    let processed = 0;
    for (const r of failed) {
      const meta = (r.meta_json ?? {}) as Record<string, unknown>;
      if (meta.refunded === true) continue;

      const charged = typeof meta.charged_price === 'number' ? meta.charged_price : r.price;
      if (charged <= 0) continue;

      try {
        await this.prisma.$transaction(async (tx) => {
          // Re-check status to avoid double refund if another worker grabbed it
          const fresh = await tx.request.findUnique({ where: { id: r.id } });
          if (!fresh) return;
          const m = (fresh.meta_json ?? {}) as Record<string, unknown>;
          if (m.refunded === true) return;
          if (!['error', 'cancelled'].includes(fresh.status)) return;

          await tx.user.update({
            where: { id: fresh.user_id },
            data: { balance: { increment: charged } },
          });
          await tx.request.update({
            where: { id: r.id },
            data: {
              meta_json: { ...m, refunded: true, refunded_amount: charged, refunded_at: new Date().toISOString() },
            },
          });
        });
        processed++;
        this.logger.log(`Refunded order #${r.id}: ${charged} so'm to user ${r.user_id}`);
      } catch (err) {
        this.logger.error(`Refund failed for order #${r.id}: ${err}`);
      }
    }
    if (processed > 0) {
      this.logger.log(`Refund sweep: ${processed} order(s) processed.`);
    }
  }
}
