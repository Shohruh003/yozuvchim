import {
  Body,
  Controller,
  Get,
  Param,
  ParseIntPipe,
  Post,
  Query,
  UseGuards,
} from '@nestjs/common';
import { JwtAuthGuard } from '../auth/jwt-auth.guard';
import { AdminGuard } from './admin.guard';
import { AdminService } from './admin.service';

@Controller('admin')
@UseGuards(JwtAuthGuard, AdminGuard)
export class AdminController {
  constructor(private readonly admin: AdminService) {}

  @Get('stats')
  stats() {
    return this.admin.stats();
  }

  @Get('users')
  listUsers(@Query('limit') limit?: string, @Query('offset') offset?: string) {
    return this.admin.listUsers(
      limit ? Number(limit) : 50,
      offset ? Number(offset) : 0,
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

  @Get('payments/pending')
  pendingPayments() {
    return this.admin.pendingPayments();
  }

  @Post('payments/:id/approve')
  approvePayment(@Param('id', ParseIntPipe) id: number) {
    return this.admin.approvePayment(id);
  }

  @Post('payments/:id/reject')
  rejectPayment(@Param('id', ParseIntPipe) id: number) {
    return this.admin.rejectPayment(id);
  }
}
