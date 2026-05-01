import { Injectable, UnauthorizedException } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { PassportStrategy } from '@nestjs/passport';
import { ExtractJwt, Strategy } from 'passport-jwt';

import { PrismaService } from '../prisma/prisma.service';

export interface JwtPayload {
  sub: string; // user id (BigInt as string)
  iat: number;
  exp: number;
}

@Injectable()
export class JwtStrategy extends PassportStrategy(Strategy) {
  constructor(
    config: ConfigService,
    private readonly prisma: PrismaService,
  ) {
    super({
      jwtFromRequest: ExtractJwt.fromAuthHeaderAsBearerToken(),
      ignoreExpiration: false,
      secretOrKey: config.get<string>('JWT_SECRET') || 'dev_secret',
    });
  }

  async validate(payload: JwtPayload) {
    const id = BigInt(payload.sub);
    const user = await this.prisma.user.findUnique({ where: { id } });
    if (!user || user.is_blocked) throw new UnauthorizedException();
    return user; // attached to request as req.user
  }
}
