import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";
type Context = { params: Promise<{ path: string[] }> };

async function proxy(request: NextRequest, context: Context) {
  const { path } = await context.params;
  if (path[0] !== "v1" || path.some((part) => part === "." || part === "..")) {
    return NextResponse.json({ error: { message: "Resource not found." } }, { status: 404 });
  }
  const upstream = new URL(
    "/" + path.map(encodeURIComponent).join("/"),
    process.env.API_INTERNAL_URL || "http://127.0.0.1:8000",
  );
  upstream.search = request.nextUrl.search;
  const headers = new Headers();
  for (const name of ["accept", "content-type", "cookie", "origin", "x-csrf-token"]) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }
  const body = ["GET", "HEAD"].includes(request.method) ? undefined : await request.arrayBuffer();
  if (body && body.byteLength > 65536) {
    return NextResponse.json({ error: { message: "Request is too large." } }, { status: 413 });
  }
  try {
    const result = await fetch(upstream, {
      method: request.method, headers, body, cache: "no-store", redirect: "manual",
      signal: AbortSignal.timeout(10000),
    });
    const outgoing = new Headers({ "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff" });
    for (const name of ["content-type", "x-request-id", "retry-after"]) {
      const value = result.headers.get(name);
      if (value) outgoing.set(name, value);
    }
    for (const cookie of result.headers.getSetCookie()) outgoing.append("set-cookie", cookie);
    return new Response(result.body, { status: result.status, headers: outgoing });
  } catch {
    return NextResponse.json({ error: { message: "The service is unavailable. Please try again." } },
      { status: 503, headers: { "Cache-Control": "no-store" } });
  }
}

export { proxy as GET, proxy as POST, proxy as PATCH, proxy as PUT, proxy as DELETE };
