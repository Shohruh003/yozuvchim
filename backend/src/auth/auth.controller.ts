import {
  Body,
  Controller,
  HttpCode,
  Post,
  Req,
  Res,
  UseGuards,
  Get,
} from '@nestjs/common';
import type { Request, Response } from 'express';

import { AuthService } from './auth.service';
import { WebAppLoginDto, TokenLoginDto, RefreshDto } from './dto/login.dto';
import { JwtAuthGuard } from './jwt-auth.guard';
import { CurrentUser } from './current-user.decorator';

@Controller('auth')
export class AuthController {
  constructor(private readonly auth: AuthService) {}

  @Post('telegram/webapp')
  @HttpCode(200)
  async webapp(
    @Body() dto: WebAppLoginDto,
    @Req() req: Request,
    @Res({ passthrough: true }) res: Response,
  ) {
    const tokens = await this.auth.loginWithWebApp(
      dto.init_data,
      req.headers['user-agent'],
      req.ip,
    );
    this.setRefreshCookie(res, tokens.refresh_token);
    return { access_token: tokens.access_token };
  }

  @Post('telegram/token')
  @HttpCode(200)
  async tokenLogin(
    @Body() dto: TokenLoginDto,
    @Req() req: Request,
    @Res({ passthrough: true }) res: Response,
  ) {
    const tokens = await this.auth.loginWithToken(
      dto.token,
      req.headers['user-agent'],
      req.ip,
    );
    this.setRefreshCookie(res, tokens.refresh_token);
    return { access_token: tokens.access_token };
  }

  @Post('refresh')
  @HttpCode(200)
  async refresh(
    @Body() dto: RefreshDto,
    @Req() req: Request,
    @Res({ passthrough: true }) res: Response,
  ) {
    const refresh = dto.refresh_token || req.cookies?.['refresh_token'];
    const tokens = await this.auth.refresh(
      refresh,
      req.headers['user-agent'],
      req.ip,
    );
    this.setRefreshCookie(res, tokens.refresh_token);
    return { access_token: tokens.access_token };
  }

  @Post('logout')
  @HttpCode(204)
  async logout(@Req() req: Request, @Res({ passthrough: true }) res: Response) {
    const refresh = req.cookies?.['refresh_token'];
    await this.auth.logout(refresh);
    res.clearCookie('refresh_token');
  }

  @Get('me')
  @UseGuards(JwtAuthGuard)
  async me(@CurrentUser() user: any) {
    return {
      id: user.id.toString(),
      username: user.username,
      full_name: user.full_name,
      role: user.role,
    };
  }

  private setRefreshCookie(res: Response, token: string) {
    res.cookie('refresh_token', token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax',
      maxAge: 7 * 24 * 60 * 60 * 1000,
      path: '/api/auth',
    });
  }
}
