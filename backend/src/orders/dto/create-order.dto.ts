import {
  IsIn,
  IsInt,
  IsOptional,
  IsString,
  Length,
  Max,
  Min,
} from 'class-validator';

export const DOC_TYPES = [
  'article',
  'taqdimot',
  'coursework',
  'independent',
  'thesis',
  'manual',
  'diploma',
  'dissertation',
] as const;

export class CreateOrderDto {
  @IsString()
  @IsIn(DOC_TYPES as unknown as string[])
  doc_type!: string;

  @IsString()
  @Length(3, 512)
  title!: string;

  @IsOptional() @IsString() @Length(2, 8) language?: string;

  @IsOptional() @IsInt() @Min(1) @Max(50)
  length?: number;

  /** Price the user saw on the form. Backend rejects if it disagrees with the server price. */
  @IsOptional() @IsInt() @Min(0)
  expected_price?: number;

  // Free-form metadata
  @IsOptional() @IsString() subject?: string;
  @IsOptional() @IsString() uni?: string;
  @IsOptional() @IsString() major?: string;
  @IsOptional() @IsString() ppt_style?: string;
  @IsOptional() @IsString() ppt_template?: string;
  @IsOptional() @IsString() student_name?: string;
  @IsOptional() @IsString() advisor?: string;
  @IsOptional() @IsString() authors?: string;
  @IsOptional() @IsString() workplace?: string;
  @IsOptional() @IsString() author_email?: string;
}
