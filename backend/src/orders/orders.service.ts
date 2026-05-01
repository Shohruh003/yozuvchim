import {
  Injectable,
  NotFoundException,
  BadRequestException,
} from '@nestjs/common';
import { existsSync, statSync, createReadStream } from 'fs';
import { Readable } from 'stream';

import { PrismaService } from '../prisma/prisma.service';
import { CreateOrderDto } from './dto/create-order.dto';

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
  constructor(private readonly prisma: PrismaService) {}

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

  // ----------- create -----------
  async create(userId: bigint, dto: CreateOrderDto) {
    const meta: Record<string, any> = {};
    for (const k of [
      'subject', 'uni', 'major', 'ppt_style', 'ppt_template',
      'student_name', 'advisor', 'authors', 'workplace', 'author_email',
    ] as const) {
      if (dto[k]) meta[k] = dto[k];
    }

    const order = await this.prisma.request.create({
      data: {
        user_id: userId,
        doc_type: dto.doc_type,
        title: dto.title,
        language: dto.language || 'uz',
        length: String(dto.length ?? 1),
        status: 'queued',
        meta_json: meta,
      },
    });

    return { id: order.id, status: order.status };
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
