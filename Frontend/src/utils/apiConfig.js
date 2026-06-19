const configuredBase = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '');

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
  return resolveApiUrl(path);
}

export function getApiBaseUrl() {
  return configuredBase;
}
