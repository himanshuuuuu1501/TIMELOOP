
const DJANGO_ORIGIN =
  "https://ben-selective-provisions-zum.trycloudflare.com";

export const config = {
  api: {
    bodyParser: false,
  },
};

export default async function handler(req, res) {
  try {
    const path = Array.isArray(req.query.path)
      ? req.query.path.join("/")
      : String(req.query.path || "");

    const incomingUrl = new URL(req.url, "https://vercel.local");
    const target = new URL(`/api/${path}`, DJANGO_ORIGIN);
    target.search = incomingUrl.search;

    const headers = new Headers();

    for (const [name, value] of Object.entries(req.headers)) {
      const key = name.toLowerCase();

      if (
        ["host", "connection", "content-length", "transfer-encoding"].includes(key)
      ) continue;

      if (value != null) {
        headers.set(name, Array.isArray(value) ? value.join(", ") : String(value));
      }
    }

    let body;

    if (req.method !== "GET" && req.method !== "HEAD") {
      const chunks = [];

      for await (const chunk of req) {
        chunks.push(Buffer.from(chunk));
      }

      body = Buffer.concat(chunks);
    }

    const upstream = await fetch(target, {
      method: req.method,
      headers,
      body,
      redirect: "manual",
    });

    res.statusCode = upstream.status;

    for (const [name, value] of upstream.headers.entries()) {
      if (
        !["connection", "content-length", "transfer-encoding",
          "content-encoding", "set-cookie"].includes(name.toLowerCase())
      ) {
        res.setHeader(name, value);
      }
    }

    const cookies = upstream.headers.getSetCookie?.() || [];

    if (cookies.length) {
      res.setHeader("Set-Cookie", cookies);
    } else {
      const cookie = upstream.headers.get("set-cookie");
      if (cookie) res.setHeader("Set-Cookie", cookie);
    }

    const responseBody = Buffer.from(await upstream.arrayBuffer());
    res.end(responseBody);

  } catch (error) {
    console.error("TIMELOOP proxy error:", error);

    res.statusCode = 502;
    res.setHeader("Content-Type", "application/json");
    res.end(JSON.stringify({
      error: "Could not connect to TIMELOOP Django backend."
    }));
  }
}
