import { describe, expect, test, vi, beforeEach } from "vitest";
import { createProxyHandlers } from "@/lib/proxy";

// Mock NextRequest
function mockRequest(
  method: string,
  url: string,
  headers?: Record<string, string>,
): { method: string; headers: Headers; nextUrl: { search: string }; body: ReadableStream | null } {
  const parsed = new URL(url, "http://localhost:3000");
  const hdrs = new Headers(headers);
  hdrs.set("host", "localhost:3000");
  return {
    method,
    headers: hdrs,
    nextUrl: { search: parsed.search },
    body: method === "GET" || method === "HEAD" ? null : new ReadableStream(),
  };
}

function mockContext(path: string[]): { params: Promise<{ path: string[] }> } {
  return { params: Promise.resolve({ path }) };
}

describe("createProxyHandlers", () => {
  test("returns handlers for all HTTP methods", () => {
    const handlers = createProxyHandlers("http://localhost:3001");
    expect(handlers.GET).toBeTypeOf("function");
    expect(handlers.POST).toBeTypeOf("function");
    expect(handlers.PUT).toBeTypeOf("function");
    expect(handlers.DELETE).toBeTypeOf("function");
    expect(handlers.PATCH).toBeTypeOf("function");
  });
});

describe("proxy handler", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  test("constructs correct upstream URL from path segments", async () => {
    const handlers = createProxyHandlers("http://localhost:3001");
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("ok", { status: 200 }),
    );

    const req = mockRequest("GET", "http://localhost:3000/api/delta/health");
    await handlers.GET(req as never, mockContext(["health"]));

    expect(fetchSpy).toHaveBeenCalledOnce();
    const calledUrl = fetchSpy.mock.calls[0][0] as string;
    expect(calledUrl).toBe("http://localhost:3001/api/health");
  });

  test("passes query string through", async () => {
    const handlers = createProxyHandlers("http://localhost:3001");
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("ok", { status: 200 }),
    );

    const req = mockRequest("GET", "http://localhost:3000/api/delta/state?mode=BUILD");
    await handlers.GET(req as never, mockContext(["state"]));

    const calledUrl = fetchSpy.mock.calls[0][0] as string;
    expect(calledUrl).toBe("http://localhost:3001/api/state?mode=BUILD");
  });

  test("encodes path segments to prevent traversal", async () => {
    const handlers = createProxyHandlers("http://localhost:3001");
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("ok", { status: 200 }),
    );

    // Segments with slashes get encoded, preventing path escape
    const req = mockRequest("GET", "http://localhost:3000/api/delta/foo");
    await handlers.GET(req as never, mockContext(["../admin"]));

    const calledUrl = fetchSpy.mock.calls[0][0] as string;
    expect(calledUrl).toBe("http://localhost:3001/api/..%2Fadmin");
  });

  test("strips host header", async () => {
    const handlers = createProxyHandlers("http://localhost:3001");
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("ok", { status: 200 }),
    );

    const req = mockRequest("GET", "http://localhost:3000/api/delta/health");
    await handlers.GET(req as never, mockContext(["health"]));

    const init = fetchSpy.mock.calls[0][1] as RequestInit;
    const headers = init.headers as Headers;
    expect(headers.get("host")).toBeNull();
  });

  test("GET request has no body", async () => {
    const handlers = createProxyHandlers("http://localhost:3001");
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("ok", { status: 200 }),
    );

    const req = mockRequest("GET", "http://localhost:3000/api/delta/health");
    await handlers.GET(req as never, mockContext(["health"]));

    const init = fetchSpy.mock.calls[0][1] as RequestInit;
    expect(init.body).toBeUndefined();
  });

  test("POST request streams body with duplex", async () => {
    const handlers = createProxyHandlers("http://localhost:3001");
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("ok", { status: 200 }),
    );

    const req = mockRequest("POST", "http://localhost:3000/api/delta/ingest");
    await handlers.POST(req as never, mockContext(["ingest"]));

    const init = fetchSpy.mock.calls[0][1] as RequestInit & { duplex?: string };
    expect(init.body).toBeInstanceOf(ReadableStream);
    expect(init.duplex).toBe("half");
  });

  test("returns 502 without leaking upstream URL", async () => {
    const handlers = createProxyHandlers("http://localhost:3001");
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("ECONNREFUSED"));

    const req = mockRequest("GET", "http://localhost:3000/api/delta/health");
    const res = await handlers.GET(req as never, mockContext(["health"]));

    expect(res.status).toBe(502);
    const body = await res.json();
    expect(body.error).toBe("upstream_unavailable");
    expect(body.upstream).toBeUndefined();
  });

  test("passes upstream status and allowed headers through", async () => {
    const handlers = createProxyHandlers("http://localhost:3001");
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response('{"mode":"BUILD"}', {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );

    const req = mockRequest("GET", "http://localhost:3000/api/delta/state");
    const res = await handlers.GET(req as never, mockContext(["state"]));

    expect(res.status).toBe(200);
    expect(res.headers.get("content-type")).toBe("application/json");
  });

  test("strips hop-by-hop headers from upstream response", async () => {
    const handlers = createProxyHandlers("http://localhost:3001");
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("ok", {
        status: 200,
        headers: {
          "content-type": "text/plain",
          "connection": "keep-alive",
          "transfer-encoding": "chunked",
          "set-cookie": "session=abc",
        },
      }),
    );

    const req = mockRequest("GET", "http://localhost:3000/api/delta/health");
    const res = await handlers.GET(req as never, mockContext(["health"]));

    expect(res.headers.get("content-type")).toBe("text/plain");
    expect(res.headers.get("connection")).toBeNull();
    expect(res.headers.get("transfer-encoding")).toBeNull();
    expect(res.headers.get("set-cookie")).toBeNull();
  });
});
