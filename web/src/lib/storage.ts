export function readLS<T>(key: string, fallback: T): T {
  try {
    const v = localStorage.getItem(key);
    return v == null ? fallback : (JSON.parse(v) as T);
  } catch {
    return fallback;
  }
}

export function writeLS(key: string, value: unknown): void {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* gizli pencere / engelli depolama: sessizce geç */
  }
}

export function removeLS(key: string): void {
  try { localStorage.removeItem(key); } catch { /* yok say */ }
}
