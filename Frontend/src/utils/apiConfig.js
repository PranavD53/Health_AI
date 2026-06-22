const configuredBase = (import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_API_URL || '').replace(/\/$/, '');

/**
 * Resolves an API path to a fetchable URL.
 * - With VITE_API_BASE_URL: points at the backend (cloud / direct access).
 * - Without it: uses a relative path so the Vite dev proxy can forward requests.
 */
export function resolveApiUrl(path) {
  if (!path) return configuredBase || '/';
  if (/^https?:\/\//i.test(path)) return path;

  const normalized = path.startsWith('/') ? path : `/${path}`;
  return configuredBase ? `${configuredBase}${normalized}` : normalized;
}

/** Resolves stored upload paths (/uploads/...) to a browser-loadable URL. */
export function resolveMediaUrl(path) {
  if (!path) return '';
  if (/^https?:\/\//i.test(path)) return path;

  const normalized = path.startsWith('/') ? path : `/${path}`;
  if (configuredBase) {
    return `${configuredBase}${normalized}`;
  }

  // In development, if running via Vite's port (5173), direct requests to the backend (port 8000)
  // to avoid Vite dev server's HTML fallback routing intercepting direct file clicks/downloads.
  if (typeof window !== 'undefined' && window.location.port === '5173') {
    return `http://127.0.0.1:8000${normalized}`;
  }

  return normalized;
}

export function getApiBaseUrl() {
  return configuredBase;
}
