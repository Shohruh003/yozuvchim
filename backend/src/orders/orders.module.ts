import { Module } from '@nestjs/common';
import { OrdersController } from './orders.controller';
import { OrdersService } from './orders.service';
import { OrderQueueService } from './queue.service';
import { RefundsService } from './refunds.service';

@Module({
  controllers: [OrdersController],
  providers: [OrdersService, OrderQueueService, RefundsService],
})
export class OrdersModule {}
