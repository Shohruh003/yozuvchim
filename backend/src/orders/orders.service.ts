import {
  Injectable,
  NotFoundException,
  BadRequestException,
  ForbiddenException,
  Logger,
} from '@nestjs/common';
import { existsSync, statSync, createReadStream } from 'fs';
import { Readable } from 'stream';

import { PrismaService } from '../prisma/prisma.service';
import { CreateOrderDto } from './dto/create-order.dto';
import { quotePrice } from './pricing';
import { OrderQueueService } from './queue.service';

const DOC_TYPE_LABELS: Record<string, string> = {
  article: '📄 Maqola',
  taqdimot: '🎯 Taqdimot',
  coursework: '📚 Kurs ishi',
  independent: '📝 Mustaqil ish',
  thesis: '📌 Tezis',
  diploma: '🎓 Diplom ishi',
  dissertation: '🔬 Dissertatsiya',
  manual: '📖 O\'quv qo\'llanma',
};

@Injectable()
export class OrdersService {
  private readonly logger = new Logger(OrdersService.name);

  constructor(
    private readonly prisma: PrismaService,
    private readonly queue: OrderQueueService,
  ) {}

  // ----------- list -----------
  async list(userId: bigint, limit = 50) {
    const items = await this.prisma.request.findMany({
      where: { user_id: userId, is_deleted: false },
      orderBy: { created_at: 'desc' },
      take: Math.min(Math.max(limit, 1), 100),
    });
    return items.map((o) => this.serialize(o));
  }

  async getOne(userId: bigint, id: number) {
    const order = await this.prisma.request.findUnique({ where: { id } });
    if (!order || order.user_id !== userId || order.is_deleted) {
      throw new NotFoundException('Order not found');
    }
    return {
      ...this.serialize(order),
      meta: order.meta_json,
      result_text: (order.result_text || '').slice(0, 5000),
      error_log: order.error_log,
    };
  }

  // ----------- price preview -----------
  quote(docType: string, length: number) {
    return quotePrice(docType, length);
  }

  // ----------- create -----------
  async create(userId: bigint, dto: CreateOrderDto) {
    const length = Math.max(1, dto.length ?? 1);
    const { price: serverPrice } = quotePrice(dto.doc_type, length);

    // If frontend sent expected_price, it must match server's calculation
    if (
      dto.expected_price !== undefined &&
      dto.expected_price !== null &&
      dto.expected_price !== serverPrice
    ) {
      throw new BadRequestException(
        `Narx o'zgargan. Sahifani yangilang. Kutilgan: ${dto.expected_price}, hozirgi: ${serverPrice}`,
      );
    }

    const order = await this.prisma.$transaction(async (tx) => {
      const user = await tx.user.findUnique({ where: { id: userId } });
      if (!user) throw new NotFoundException('User not found');
      if (user.is_blocked) throw new ForbiddenException('User is blocked');

      // Free trial: first ever order is free
      const useFreeTrial = !user.has_used_free_trial;
      const finalPrice = useFreeTrial ? 0 : serverPrice;

      if (!useFreeTrial && user.balance < serverPrice) {
        throw new BadRequestException(
          `Yetarli mablag' yo'q. Kerak: ${serverPrice.toLocaleString('uz-UZ')} so'm, balansda: ${user.balance.toLocaleString('uz-UZ')} so'm`,
        );
      }

      const meta: Record<string, any> = {
        // Track exactly how much we charged so refund can return the same amount
        charged_price: finalPrice,
      };
      for (const k of [
        'subject', 'uni', 'major', 'ppt_style', 'ppt_template',
        'student_name', 'advisor', 'authors', 'workplace', 'author_email',
      ] as const) {
        if (dto[k]) meta[k] = dto[k];
      }

      const created = await tx.request.create({
        data: {
          user_id: userId,
          doc_type: dto.doc_type,
          title: dto.title,
          language: dto.language || 'uz',
          length: String(length),
          price: finalPrice,
          status: 'queued',
          is_free: useFreeTrial,
          meta_json: meta,
        },
      });

      if (useFreeTrial) {
        await tx.user.update({
          where: { id: userId },
          data: { has_used_free_trial: true, total_orders: { increment: 1 } },
        });
      } else {
        await tx.user.update({
          where: { id: userId },
          data: {
            balance: { decrement: serverPrice },
            total_spent: { increment: serverPrice },
            total_orders: { increment: 1 },
          },
        });
      }

      return created;
    });

    // Push to bot worker queue (after the transaction commits)
    await this.queue.enqueue(order.id);

    return {
      id: order.id,
      status: order.status,
      price: order.price,
      is_free: order.is_free,
    };
  }

  // ----------- cancel (user) -----------
  async cancel(userId: bigint, id: number) {
    const order = await this.prisma.request.findUnique({ where: { id } });
    if (!order || order.user_id !== userId || order.is_deleted) {
      throw new NotFoundException('Order not found');
    }
    if (order.status !== 'queued') {
      throw new BadRequestException('Faqat navbatdagi buyurtmani bekor qilish mumkin');
    }
    await this.prisma.$transaction(async (tx) => {
      await tx.request.update({
        where: { id },
        data: { status: 'cancelled' },
      });
      // Refund will be handled by RefundsService cron
    });
    return { ok: true };
  }

  // ----------- file download -----------
  async openFile(userId: bigint, id: number): Promise<{
    stream: Readable;
    filename: string;
    size: number;
  }> {
    const order = await this.prisma.request.findUnique({ where: { id } });
    if (!order || order.user_id !== userId || order.is_deleted) {
      throw new NotFoundException('Order not found');
    }
    if (!order.result_path) throw new BadRequestException('File not ready');
    if (!existsSync(order.result_path)) {
      throw new NotFoundException('File missing on disk');
    }
    const stat = statSync(order.result_path);
    const filename = order.result_path.split(/[\\/]/).pop() || `order-${id}.docx`;
    return {
      stream: createReadStream(order.result_path),
      filename,
      size: stat.size,
    };
  }

  // ----------- helpers -----------
  private serialize(o: any) {
    return {
      id: o.id,
      doc_type: o.doc_type,
      doc_label: DOC_TYPE_LABELS[o.doc_type] ?? o.doc_type,
      title: o.title,
      status: o.status,
      language: o.language,
      length: o.length,
      price: o.price,
      created_at: o.created_at.toISOString(),
      current_step: o.current_step,
      total_steps: o.total_steps,
      has_file: Boolean(o.result_path),
    };
  }
}
