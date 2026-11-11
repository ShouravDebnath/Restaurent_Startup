import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";
type Context = { params: Promise<{ path: string[] }> };

async function proxy(request: NextRequest, context: Context) {
  const { path } = await context.params;
  if (path[0] !== "v1" || path[1] === "edge" || path.some((part) => part === "." || part === "..")) {
    return NextResponse.json({ error: { message: "Resource not found." } }, { status: 404 });
  }
  const upstream = new URL(
    "/" + path.map(encodeURIComponent).join("/"),
    process.env.API_INTERNAL_URL || "http://127.0.0.1:8000",
  );
  upstream.search = request.nextUrl.search;
  const streaming = request.method === "GET" && path.length === 4
    && path[1] === "locations" && path[3] === "stream";
  const headers = new Headers();
  for (const name of ["accept", "content-type", "cookie", "origin", "x-csrf-token", "last-event-id"]) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }
  const body = ["GET", "HEAD"].includes(request.method) ? undefined : await request.arrayBuffer();
  if (body && body.byteLength > 65536) {
    return NextResponse.json({ error: { message: "Request is too large." } }, { status: 413 });
  }
  try {
    // Keep connect/header time bounded; a healthy stream then lives until browser cancellation.
    const controller = new AbortController();
    const cancel = () => controller.abort();
    request.signal.addEventListener("abort", cancel, { once: true });
    const headerDeadline = setTimeout(cancel, 10000);
    const result = await fetch(upstream, {
      method: request.method, headers, body, cache: "no-store", redirect: "manual",
      signal: streaming ? controller.signal : AbortSignal.timeout(10000),
    });
    clearTimeout(headerDeadline);
    if (!streaming) request.signal.removeEventListener("abort", cancel);
    const outgoing = new Headers({ "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff" });
    for (const name of ["content-type", "x-request-id", "retry-after"]) {
      const value = result.headers.get(name);
      if (value) outgoing.set(name, value);
    }
    for (const cookie of result.headers.getSetCookie()) outgoing.append("set-cookie", cookie);
    if (!streaming || !result.ok || !result.body) {
      request.signal.removeEventListener("abort", cancel);
      return new Response(result.body, { status: result.status, headers: outgoing });
    }
    outgoing.set("X-Accel-Buffering", "no");
    const reader = result.body.getReader();
    let idleDeadline: ReturnType<typeof setTimeout>;
    const stream = new ReadableStream({
      async pull(target) {
        idleDeadline = setTimeout(cancel, 15000);
        try {
          const chunk = await reader.read();
          clearTimeout(idleDeadline);
          if (chunk.done) {
            request.signal.removeEventListener("abort", cancel);
            target.close();
          } else target.enqueue(chunk.value);
        } catch {
          clearTimeout(idleDeadline);
          request.signal.removeEventListener("abort", cancel);
          target.error(new Error("Updates interrupted."));
        }
      },
      async cancel() {
        clearTimeout(idleDeadline); controller.abort();
        request.signal.removeEventListener("abort", cancel);
        await reader.cancel().catch(() => undefined);
      },
    });
    return new Response(stream, { status: result.status, headers: outgoing });
  } catch {
    return NextResponse.json({ error: { message: "The service is unavailable. Please try again." } },
      { status: 503, headers: { "Cache-Control": "no-store" } });
  }
}

export { proxy as GET, proxy as POST, proxy as PATCH, proxy as PUT, proxy as DELETE };
