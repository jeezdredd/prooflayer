import { create } from "zustand";
import ru from "./ru.json";

export type Lang = "en" | "ru";

const STORAGE_KEY = "lang";
const STRINGS: Record<string, string> = ru.strings;
const PLURALS: Record<string, string[]> = ru.plural;
const PATTERNS: [RegExp, string][] = Object.entries(ru.patterns as Record<string, string>).map(([source, target]) => [new RegExp(source), target]);

type Vars = Record<string, string | number>;

function initialLang(): Lang {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === "en" || saved === "ru") return saved;
  } catch {
    return "en";
  }
  if (typeof navigator !== "undefined" && navigator.language?.toLowerCase().startsWith("ru")) return "ru";
  return "en";
}

interface LangState {
  lang: Lang;
  setLang: (lang: Lang) => void;
}

export const useLangStore = create<LangState>((set) => ({
  lang: initialLang(),
  setLang: (lang) => {
    try {
      localStorage.setItem(STORAGE_KEY, lang);
    } catch {
      set({ lang });
    }
    document.documentElement.lang = lang;
    set({ lang });
  },
}));

if (typeof document !== "undefined") document.documentElement.lang = useLangStore.getState().lang;

export function currentLang(): Lang {
  return useLangStore.getState().lang;
}

function fill(text: string, vars?: Vars): string {
  if (!vars) return text;
  return text.replace(/\{(\w+)\}/g, (whole, name: string) => (name in vars ? String(vars[name]) : whole));
}

function byPattern(text: string): string | undefined {
  for (const [pattern, target] of PATTERNS) {
    if (pattern.test(text)) return text.replace(pattern, target);
  }
  return undefined;
}

export function t(text: string, vars?: Vars): string {
  const translated = currentLang() === "ru" ? STRINGS[text] ?? byPattern(text) ?? text : text;
  return fill(translated, vars);
}

function ruForm(n: number): number {
  const mod10 = Math.abs(n) % 10;
  const mod100 = Math.abs(n) % 100;
  if (mod10 === 1 && mod100 !== 11) return 0;
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return 1;
  return 2;
}

export function tn(n: number, one: string, other: string, vars?: Vars): string {
  const all = { n, ...vars };
  if (currentLang() === "ru") {
    const forms = PLURALS[other];
    if (forms) return fill(forms[ruForm(n)], all);
  }
  return fill(n === 1 ? one : other, all);
}

export function msg(text: string): string {
  return text;
}

export function locale(): string {
  return currentLang() === "ru" ? "ru-RU" : "en-GB";
}

const VERDICT_TEXT: Record<string, string> = {
  authentic: msg("authentic"),
  authentic_edited: msg("authentic, edited"),
  suspicious: msg("suspicious"),
  likely_fake: msg("likely fake"),
  fake: msg("fake"),
  needs_review: msg("needs review"),
  inconclusive: msg("inconclusive"),
  pending: msg("pending"),
  processing: msg("processing"),
  completed: msg("completed"),
  failed: msg("failed"),
};

export function verdictText(code: string | null | undefined): string {
  if (!code) return "-";
  return t(VERDICT_TEXT[code] ?? code.replace(/_/g, " "));
}
