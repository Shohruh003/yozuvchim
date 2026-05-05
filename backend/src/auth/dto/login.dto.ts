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

export class AdminLoginDto {
  @IsString()
  username!: string;

  @IsString()
  password!: string;
}

export class UpdateAdminCredsDto {
  @IsString()
  current_password!: string;

  @IsOptional()
  @IsString()
  new_username?: string;

  @IsOptional()
  @IsString()
  new_password?: string;
}
