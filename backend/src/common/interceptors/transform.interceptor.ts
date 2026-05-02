import {
  CallHandler,
  ExecutionContext,
  Injectable,
  NestInterceptor,
  StreamableFile,
} from '@nestjs/common';
import { Observable } from 'rxjs';
import { map } from 'rxjs/operators';

export interface ApiResponse<T> {
  data: T;
}

@Injectable()
export class TransformInterceptor<T>
  implements NestInterceptor<T, ApiResponse<T> | T>
{
  intercept(
    _context: ExecutionContext,
    next: CallHandler,
  ): Observable<ApiResponse<T> | T> {
    return next.handle().pipe(
      map((data) => {
        // Don't wrap binary responses
        if (data instanceof StreamableFile) return data as T;
        if (data instanceof Buffer) return data as T;
        // Don't double-wrap { data: ... }
        if (data && typeof data === 'object' && 'data' in data) {
          return data as ApiResponse<T>;
        }
        return { data } as ApiResponse<T>;
      }),
    );
  }
}
