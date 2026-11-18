const DEFAULT_PORT = '8765'

const OFFLINE_PAGE = `<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
    <title>bussola is not running</title>
    <style>
      :root { color-scheme: light dark; --bg: #ffffff; --text: #1f2328; --muted: #59636e; --code: #f4f6fa; --accent: #2952cc; }
      @media (prefers-color-scheme: dark) {
        :root { --bg: #0e1424; --text: #e6edf3; --muted: #9198a1; --code: #141c2e; --accent: #8aabff; }
      }
      body { margin: 0; min-height: 100vh; display: grid; place-items: center; background: var(--bg); color: var(--text); font: 15px/1.5 system-ui, sans-serif; }
      main { max-width: 32rem; padding: 2rem; }
      h1 { font-size: 1.4rem; margin: 0 0 0.75rem; }
      p { margin: 0.75rem 0; }
      code { background: var(--code); border-radius: 4px; padding: 0.1rem 0.35rem; }
      a { color: var(--accent); }
      .muted { color: var(--muted); }
    </style>
  </head>
  <body>
    <main>
      <h1>bussola is not running</h1>
      <p>Start it in a terminal with <code id="command">bussola serve</code>, or open a <a href="bussola://">bussola:// link</a> if you ran <code>bussola install-handler</code>.</p>
      <p class="muted">This page reloads by itself once bussola is running.</p>
    </main>
    <script>
      if (location.port && location.port !== '${DEFAULT_PORT}') {
        document.getElementById('command').textContent = 'bussola serve --port ' + location.port
      }
      setInterval(() => fetch('/api/health', { cache: 'no-store' }).then(() => location.reload(), () => undefined), 2000)
    </script>
  </body>
</html>`

function offlineResponse() {
  return new Response(OFFLINE_PAGE, { status: 503, headers: { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store' } })
}

self.addEventListener('install', () => self.skipWaiting())

self.addEventListener('activate', (event) => event.waitUntil(self.clients.claim()))

self.addEventListener('fetch', (event) => {
  if (event.request.mode === 'navigate') {
    event.respondWith(fetch(event.request).catch(offlineResponse))
  }
})
