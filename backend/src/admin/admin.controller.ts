import {
  Body,
  Controller,
  Get,
  Param,
  ParseIntPipe,
  Post,
  Query,
  Res,
  StreamableFile,
  UseGuards,
} from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import type { Response } from 'express';
import { JwtAuthGuard } from '../auth/jwt-auth.guard';
import { CurrentUser } from '../auth/current-user.decorator';
import { AdminGuard } from './admin.guard';
import { SuperAdminGuard } from './superadmin.guard';
import { AdminService } from './admin.service';

@Controller('admin')
@UseGuards(JwtAuthGuard, AdminGuard)
export class AdminController {
  constructor(
    private readonly admin: AdminService,
    private readonly config: ConfigService,
  ) {}

  @Get('stats')
  stats() {
    return this.admin.stats();
  }

  @Get('users')
  listUsers(
    @Query('limit') limit?: string,
    @Query('offset') offset?: string,
    @Query('search') search?: string,
  ) {
    return this.admin.listUsers(
      limit ? Number(limit) : 50,
      offset ? Number(offset) : 0,
      search ?? '',
    );
  }

  @Post('users/:id/block')
  block(@Param('id') id: string) {
    return this.admin.setBlocked(BigInt(id), true);
  }

  @Post('users/:id/unblock')
  unblock(@Param('id') id: string) {
    return this.admin.setBlocked(BigInt(id), false);
  }

  @Post('users/:id/balance')
  balance(@Param('id') id: string, @Body() body: { delta: number }) {
    return this.admin.adjustBalance(BigInt(id), body.delta);
  }

  @Get('users/:id/detail')
  userDetail(@Param('id') id: string) {
    return this.admin.userDetail(BigInt(id));
  }

  @Get('users/:id/orders')
  userOrders(
    @Param('id') id: string,
    @Query('limit') limit?: string,
    @Query('offset') offset?: string,
  ) {
    return this.admin.userOrders(
      BigInt(id),
      limit ? Number(limit) : 20,
      offset ? Number(offset) : 0,
    );
  }

  @Get('users/:id/payments')
  userPayments(
    @Param('id') id: string,
    @Query('limit') limit?: string,
    @Query('offset') offset?: string,
  ) {
    return this.admin.userPayments(
      BigInt(id),
      limit ? Number(limit) : 20,
      offset ? Number(offset) : 0,
    );
  }

  // ----------- Superadmin: role management -----------
  @Post('users/:id/role')
  @UseGuards(SuperAdminGuard)
  setRole(
    @Param('id') id: string,
    @Body() body: { role: 'user' | 'admin' | 'superadmin' },
    @CurrentUser() actor: any,
  ) {
    return this.admin.setRole(actor.id, BigInt(id), body.role);
  }

  // ----------- Superadmin: see admins and what they're doing -----------
  @Get('admins')
  @UseGuards(SuperAdminGuard)
  listAdmins() {
    return this.admin.listAdmins();
  }

  @Get('admins/:id/activity')
  @UseGuards(SuperAdminGuard)
  adminActivity(@Param('id') id: string, @Query('limit') limit?: string) {
    return this.admin.adminActivity(BigInt(id), limit ? Number(limit) : 100);
  }

  // ----------- Payment cards (CRUD) -----------
  @Get('cards')
  listCards() {
    return this.admin.listCards();
  }

  @Post('cards')
  createCard(
    @Body()
    body: {
      number: string;
      holder: string;
      bank?: string;
      is_active?: boolean;
      sort_order?: number;
    },
  ) {
    return this.admin.createCard(body);
  }

  @Post('cards/:id')
  updateCard(
    @Param('id', ParseIntPipe) id: number,
    @Body()
    body: {
      number?: string;
      holder?: string;
      bank?: string;
      is_active?: boolean;
      sort_order?: number;
    },
  ) {
    return this.admin.updateCard(id, body);
  }

  @Post('cards/:id/delete')
  deleteCard(@Param('id', ParseIntPipe) id: number) {
    return this.admin.deleteCard(id);
  }

  @Get('payments/pending')
  pendingPayments(
    @Query('limit') limit?: string,
    @Query('offset') offset?: string,
  ) {
    return this.admin.pendingPayments(
      limit ? Number(limit) : 20,
      offset ? Number(offset) : 0,
    );
  }

  @Get('transactions')
  transactions(
    @Query('from') from?: string,
    @Query('to') to?: string,
    @Query('status') status?: string,
    @Query('limit') limit?: string,
    @Query('offset') offset?: string,
  ) {
    return this.admin.listTransactions({
      from: from ? new Date(from) : undefined,
      to: to ? new Date(to) : undefined,
      status,
      limit: limit ? Number(limit) : 50,
      offset: offset ? Number(offset) : 0,
    });
  }

  @Get('revenue/timeseries')
  revenueTimeseries(
    @Query('from') from: string,
    @Query('to') to: string,
    @Query('bucket') bucket?: 'hour' | 'day',
  ) {
    return this.admin.revenueTimeseries({
      from: new Date(from),
      to: new Date(to),
      bucket: bucket === 'hour' ? 'hour' : 'day',
    });
  }

  @Post('payments/:id/approve')
  approvePayment(
    @Param('id', ParseIntPipe) id: number,
    @Body() body: { amount?: number },
  ) {
    return this.admin.approvePayment(id, body?.amount);
  }

  @Post('payments/:id/reject')
  rejectPayment(@Param('id', ParseIntPipe) id: number) {
    return this.admin.rejectPayment(id);
  }

  /**
   * Proxy a Telegram payment-screenshot file_id back to the admin panel as raw bytes.
   * Telegram CDN URLs require the bot token, so we cannot expose them to the browser.
   */
  @Get('payments/:id/screenshot')
  async screenshot(
    @Param('id', ParseIntPipe) id: number,
    @Res({ passthrough: true }) res: Response,
  ): Promise<StreamableFile> {
    const fileId = await this.admin.getPaymentFileId(id);
    const botToken = this.config.get<string>('BOT_TOKEN') || '';
    const meta = await fetch(
      `https://api.telegram.org/bot${botToken}/getFile?file_id=${encodeURIComponent(fileId)}`,
    ).then((r) => r.json() as Promise<{ ok: boolean; result?: { file_path: string } }>);
    if (!meta.ok || !meta.result?.file_path) {
      res.status(404);
      throw new Error('Screenshot not available');
    }
    const fileResp = await fetch(
      `https://api.telegram.org/file/bot${botToken}/${meta.result.file_path}`,
    );
    if (!fileResp.ok || !fileResp.body) {
      res.status(404);
      throw new Error('Screenshot fetch failed');
    }
    const ct = fileResp.headers.get('content-type') || 'image/jpeg';
    res.setHeader('Content-Type', ct);
    res.setHeader('Cache-Control', 'private, max-age=300');
    const buf = Buffer.from(await fileResp.arrayBuffer());
    return new StreamableFile(buf);
  }
}
