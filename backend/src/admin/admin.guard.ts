import { CanActivate, ExecutionContext, ForbiddenException, Injectable } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';

@Injectable()
export class AdminGuard implements CanActivate {
  constructor(private readonly config: ConfigService) {}

  canActivate(context: ExecutionContext): boolean {
    const req = context.switchToHttp().getRequest();
    const user = req.user;
    if (!user) throw new ForbiddenException();

    const adminIds = (this.config.get<string>('ADMIN_IDS') || '')
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);

    if (user.role === 'admin' || user.role === 'superadmin') return true;
    if (adminIds.includes(user.id.toString())) return true;
    throw new ForbiddenException('Admins only');
  }
}
