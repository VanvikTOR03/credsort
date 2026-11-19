// Server-only configuration. Nothing here reaches the browser.
export const SERVICE_PORTS: Record<string, number> = {
  identity: 8001, accounting: 8002, intelligence: 8003, marketplace: 8004, billing: 8005, advisory: 8006, notification: 8007, audit: 8008,
};

export function serviceUrl(name: string): string | null {
  if (!(name in SERVICE_PORTS)) return null;
  return process.env[`${name.toUpperCase()}_URL`] || `http://127.0.0.1:${SERVICE_PORTS[name]}`;
}

export const AUTH_MODE = (process.env.AUTH_MODE || "dev") as "dev" | "keycloak";
export const DEV_USER_TOKEN_SECRET = process.env.DEV_USER_TOKEN_SECRET || "dev-only-user-secret-change-me-0123456789";
export const COOKIE_NAME = "cs_session";
