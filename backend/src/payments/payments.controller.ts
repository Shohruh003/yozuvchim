import { Controller, Get, UseGuards } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';

import { JwtAuthGuard } from '../auth/jwt-auth.guard';
import { CurrentUser } from '../auth/current-user.decorator';
import { PrismaService } from '../prisma/prisma.service';

@Controller('payments')
@UseGuards(JwtAuthGuard)
export class PaymentsController {
  constructor(
    private readonly prisma: PrismaService,
    private readonly config: ConfigService,
  ) {}

  @Get('info')
  async info() {
    const cards = await this.prisma.paymentCard.findMany({
      where: { is_active: true },
      orderBy: [{ sort_order: 'asc' }, { id: 'asc' }],
    });
    return {
      currency: this.config.get<string>('CURRENCY') || 'UZS',
      cards: cards.map((c) => ({
        id: c.id,
        number: c.number,
        holder: c.holder,
        bank: c.bank,
      })),
    };
  }

  @Get('history')
  async history(@CurrentUser() user: any) {
    const items = await this.prisma.payment.findMany({
      where: { user_id: user.id },
      orderBy: { created_at: 'desc' },
      take: 30,
    });
    return items.map((p) => ({
      id: p.id,
      amount: p.amount,
      status: p.status,
      created_at: p.created_at.toISOString(),
    }));
  }
}
