/** Pricing for AI generation orders. Adjust freely from admin panel later. */

export interface PriceQuote {
  price: number;          // total in UZS
  details: string;        // human-readable breakdown
}

const PER_PAGE: Record<string, number> = {
  article: 5000,
  taqdimot: 800,           // per slide
  coursework: 3000,
  independent: 2500,
  thesis: 4000,
  diploma: 4000,
  dissertation: 5000,
  manual: 3500,
};

const MIN_PRICE: Record<string, number> = {
  article: 10000,
  taqdimot: 3000,
  coursework: 30000,
  independent: 15000,
  thesis: 8000,
  diploma: 60000,
  dissertation: 100000,
  manual: 30000,
};

export function quotePrice(docType: string, length: number): PriceQuote {
  const perUnit = PER_PAGE[docType] ?? 3000;
  const min = MIN_PRICE[docType] ?? 5000;
  const raw = perUnit * Math.max(1, length);
  const price = Math.max(raw, min);
  return {
    price,
    details: `${length} × ${perUnit.toLocaleString('uz-UZ')} so'm = ${price.toLocaleString('uz-UZ')} so'm`,
  };
}
