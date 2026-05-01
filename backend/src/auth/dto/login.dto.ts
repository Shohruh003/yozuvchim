import { IsOptional, IsString } from 'class-validator';

export class WebAppLoginDto {
  @IsString()
  init_data!: string;
}

export class TokenLoginDto {
  @IsString()
  token!: string;
}

export class RefreshDto {
  @IsOptional()
  @IsString()
  refresh_token?: string;
}
