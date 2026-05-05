import {
  CanActivate,
  ExecutionContext,
  ForbiddenException,
  Injectable,
} from '@nestjs/common';
import { ConfigService } from '@nestjs/config';

@Injectable()
export class SuperAdminGuard implements CanActivate {
  constructor(private readonly config: ConfigService) {}

  canActivate(context: ExecutionContext): boolean {
    const req = context.switchToHttp().getRequest();
    const user = req.user;
    if (!user) throw new ForbiddenException();

    if (user.role === 'superadmin') return true;

    // Bootstrap superadmin via env var (fallback if no row has role='superadmin' yet)
    const ids = (this.config.get<string>('SUPERADMIN_IDS') || '')
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean);
    if (ids.includes(user.id.toString())) return true;

    throw new ForbiddenException('Superadmin only');
  }
}
