import { CanActivate, ExecutionContext, ForbiddenException, Injectable } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';

@Injectable()
export class AdminGuard implements CanActivate {
  constructor(private readonly config: ConfigService) {}

  canActivate(context: ExecutionContext): boolean {
    const req = context.switchToHttp().getRequest();
    const user = req.user;
    if (!user) throw new ForbiddenException();

    if (user.role === 'admin' || user.role === 'superadmin') return true;

    // Bootstrap superadmins via env var (so the very first admin can log in)
    const ids = (this.config.get<string>('SUPERADMIN_IDS') || '')
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);
    if (ids.includes(user.id.toString())) return true;

    throw new ForbiddenException('Admins only');
  }
}
