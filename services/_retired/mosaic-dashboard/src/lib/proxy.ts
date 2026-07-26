import { type NextRequest } from "next/server";

type RouteContext = { params: Promise<{ path: string[] }> };

const HOP_BY_HOP = new Set([
  "connection",
  "keep-alive",
  "te",
  "trailer",
  "transfer-encoding",
  "upgrade",
]);

function stripHopByHop(headers: Headers): Headers {
  const clean = new Headers(headers);
  for (const h of HOP_BY_HOP) clean.delete(h);
  clean.delete("set-cookie");
  return clean;
}

function createHandler(upstream: string) {
  return async function handler(req: NextRequest, ctx: RouteContext) {
    const { path } = await ctx.params;
    const safePath = path.map((s) => encodeURIComponent(s)).join("/");
    const url = `${upstream}/api/${safePath}${req.nextUrl.search}`;

    const headers = new Headers(req.headers);
    headers.delete("host");

    const init: RequestInit & { duplex?: string } = {
      method: req.method,
      headers,
    };

    if (req.method !== "GET" && req.method !== "HEAD") {
      init.body = req.body;
      init.duplex = "half";
    }

    try {
      const res = await fetch(url, init);

      return new Response(res.body, {
        status: res.status,
        statusText: res.statusText,
        headers: stripHopByHop(res.headers),
      });
    } catch {
      return Response.json(
        { error: "upstream_unavailable" },
        { status: 502 },
      );
    }
  };
}

export function createProxyHandlers(upstream: string) {
  const handler = createHandler(upstream);
  return {
    GET: handler,
    POST: handler,
    PUT: handler,
    DELETE: handler,
    PATCH: handler,
  };
}
