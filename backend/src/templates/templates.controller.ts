import { Controller, Get } from '@nestjs/common';

const TEMPLATE_META: Record<string, { label: string; description: string; image_url: string }> = {
  navy:     { label: '🔵 Navy (To\'q ko\'k)',    description: 'Klassik, akademik',      image_url: '/static/templates/template_1_navy.png' },
  green:    { label: '🟢 Green (Yashil)',         description: 'Yashil, sokin',          image_url: '/static/templates/template_2_green.png' },
  burgundy: { label: '🔴 Burgundy (Qizg\'ish)',  description: 'Klassik, jiddiy',        image_url: '/static/templates/template_3_burgundy.png' },
  charcoal: { label: '⚫ Charcoal (Tech)',         description: 'Zamonaviy, texnologik',  image_url: '/static/templates/template_4_charcoal.png' },
  maroon:   { label: '🟤 Maroon (Jigarrang)',     description: 'Rasmiy, an\'anaviy',     image_url: '/static/templates/template_5_maroon.png' },
};

@Controller('templates')
export class TemplatesController {
  @Get()
  list() {
    return Object.entries(TEMPLATE_META).map(([key, meta]) => ({ key, ...meta }));
  }
}
