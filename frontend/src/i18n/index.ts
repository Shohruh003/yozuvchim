import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';

import uz from './locales/uz.json';
import en from './locales/en.json';
import ru from './locales/ru.json';

void i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      uz: { translation: uz },
      en: { translation: en },
      ru: { translation: ru },
    },
    lng: 'uz',
    fallbackLng: 'uz',
    supportedLngs: ['uz', 'en', 'ru'],
    interpolation: { escapeValue: false },
    detection: {
      // Only check localStorage — never fall back to the browser language.
      // New visitors and the Telegram WebApp always start in Uzbek.
      order: ['localStorage'],
      caches: ['localStorage'],
      lookupLocalStorage: 'yozuvchim-lang',
    },
  });

export default i18n;
