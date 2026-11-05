import { useEffect, useState } from 'react';
import { removeLS } from './storage';

export type ThemePref = 'light' | 'dark' | 'system';
const KEY = 'ozbet-theme';

function systemDark() {
  return typeof window !== 'undefined' && window.matchMedia?.('(prefers-color-scheme: dark)').matches;
}

function apply(pref: ThemePref) {
  const dark = pref === 'dark' || (pref === 'system' && systemDark());
  document.documentElement.classList.toggle('dark', dark);
  const meta = document.querySelector('meta[name="theme-color"]');
  meta?.setAttribute('content', dark ? '#0D121E' : '#EFF2F1');
}

export function useTheme() {
  const [pref, setPref] = useState<ThemePref>(() => {
    try {
      const raw = localStorage.getItem(KEY);
      return raw === 'light' || raw === 'dark' ? raw : 'system';
    } catch { return 'system'; }
  });
  useEffect(() => {
    apply(pref);
    if (pref !== 'system') return;
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    const fn = () => apply('system');
    mq.addEventListener?.('change', fn);
    return () => mq.removeEventListener?.('change', fn);
  }, [pref]);
  const isDark = pref === 'dark' || (pref === 'system' && systemDark());
  const toggle = () => {
    const next: ThemePref = isDark ? 'light' : 'dark';
    // Sistem tercihine eşitse elle seçimi kaldır
    if ((next === 'dark') === systemDark()) { removeLS(KEY); setPref('system'); }
    else { try { localStorage.setItem(KEY, next); } catch { /* yok say */ } setPref(next); }
  };
  return { isDark, toggle };
}
