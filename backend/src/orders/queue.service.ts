import { Injectable, Logger, OnModuleDestroy } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { Redis } from 'ioredis';

/**
 * Pushes new order ids onto the Redis queue that the Python bot worker
 * consumes (BLPOP). Same key names as bot/bot/queue_manager.py.
 */
@Injectable()
export class OrderQueueService implements OnModuleDestroy {
  private readonly logger = new Logger(OrderQueueService.name);
  private readonly redis: Redis;
  private readonly queueKey: string;
  private readonly seenKey: string;

  constructor(config: ConfigService) {
    this.redis = new Redis(
      config.get<string>('REDIS_URL') || 'redis://localhost:6379',
      { lazyConnect: false, maxRetriesPerRequest: 3 },
    );
    const queueName = config.get<string>('REDIS_QUEUE_NAME') || 'academic_bot_queue';
    this.queueKey = queueName;
    this.seenKey = `${queueName}:seen`;
  }

  async enqueue(reqId: number): Promise<boolean> {
    try {
      const isNew = await this.redis.sadd(this.seenKey, String(reqId));
      if (!isNew) return false;
      await this.redis.rpush(this.queueKey, String(reqId));
      return true;
    } catch (err) {
      this.logger.error(`Failed to enqueue ${reqId}: ${err}`);
      return false;
    }
  }

  async onModuleDestroy() {
    try {
      await this.redis.quit();
    } catch {
      /* noop */
    }
  }
}
