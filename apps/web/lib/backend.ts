import { NextResponse } from "next/server";

/**
 * Server-side proxy to the FastAPI backend.
 *
 * The browser never talks to FastAPI directly and never sees the token:
 * every request flows through an app/api route handler which calls this
 * helper. `PAPERFEED_API_URL` / `PAPERFEED_API_TOKEN` are server-only env
 * vars (no NEXT_PUBLIC_ prefix), so they are never bundled for the client.
 */

interface ProxyOptions {
  method?: "GET" | "POST";
  /** JSON-serializable body (already parsed/validated by the route handler). */
  body?: unknown;
}

export async function proxyToBackend(
  path: string,
  options: ProxyOptions = {},
): Promise<NextResponse> {
  const baseUrl = process.env.PAPERFEED_API_URL;
  const token = process.env.PAPERFEED_API_TOKEN;

  if (!baseUrl || !token) {
    return NextResponse.json(
      {
        error:
          "Backend not configured: set PAPERFEED_API_URL and PAPERFEED_API_TOKEN (see .env.local.example).",
      },
      { status: 500 },
    );
  }

  const url = `${baseUrl.replace(/\/$/, "")}${path}`;

  let res: Response;
  try {
    res = await fetch(url, {
      method: options.method ?? "GET",
      headers: {
        Authorization: `Bearer ${token}`,
        ...(options.body !== undefined
          ? { "Content-Type": "application/json" }
          : {}),
      },
      body:
        options.body !== undefined ? JSON.stringify(options.body) : undefined,
      cache: "no-store",
    });
  } catch {
    return NextResponse.json(
      { error: `Backend unreachable at ${baseUrl}` },
      { status: 502 },
    );
  }

  // Pass the backend response through verbatim, preserving its status code
  // so client-side error handling sees real 4xx/5xx.
  const text = await res.text();
  return new NextResponse(text, {
    status: res.status,
    headers: {
      "Content-Type": res.headers.get("content-type") ?? "application/json",
    },
  });
}
