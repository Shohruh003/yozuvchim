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
import { Response } from 'express';

import { JwtAuthGuard } from '../auth/jwt-auth.guard';
import { CurrentUser } from '../auth/current-user.decorator';
import { OrdersService } from './orders.service';
import { CreateOrderDto, DOC_TYPES } from './dto/create-order.dto';

@Controller('orders')
@UseGuards(JwtAuthGuard)
export class OrdersController {
  constructor(private readonly orders: OrdersService) {}

  @Get('types')
  types() {
    return DOC_TYPES.map((key) => ({ key }));
  }

  @Get()
  list(@CurrentUser() user: any, @Query('limit') limit?: string) {
    return this.orders.list(user.id, limit ? Number(limit) : 50);
  }

  @Get(':id')
  one(@CurrentUser() user: any, @Param('id', ParseIntPipe) id: number) {
    return this.orders.getOne(user.id, id);
  }

  @Post()
  create(@CurrentUser() user: any, @Body() dto: CreateOrderDto) {
    return this.orders.create(user.id, dto);
  }

  @Get(':id/download')
  async download(
    @CurrentUser() user: any,
    @Param('id', ParseIntPipe) id: number,
    @Res({ passthrough: true }) res: Response,
  ) {
    const { stream, filename, size } = await this.orders.openFile(user.id, id);
    res.set({
      'Content-Type': 'application/octet-stream',
      'Content-Disposition': `attachment; filename="${filename}"`,
      'Content-Length': size,
    });
    return new StreamableFile(stream);
  }
}
