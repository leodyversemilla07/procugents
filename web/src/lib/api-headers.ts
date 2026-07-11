/**
 * Shared headers for proxied API calls to the ProcuGents backend.
 *
 * Every route handler in `app/api/*` should spread these headers into its
 * fetch calls so the backend receives the dashboard's API key and
 * content-type regardless of which env the code runs in.
 */

const API_KEY = process.env.NEXT_PUBLIC_API_KEY || ""

export const API_HEADERS: Record<string, string> = {
  "Content-Type": "application/json",
  ...(API_KEY ? { "X-API-Key": API_KEY } : {}),
}
