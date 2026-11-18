const DEFAULT_PORT = '8765'

const OFFLINE_PAGE = `<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
    <title>bussola is not running</title>
    <style>
      :root { color-scheme: light dark; --text: #16213a; --muted: #5b6478; --background: #ffffff; --surface: #f4f6fa; --accent: #2952cc; }
      @media (prefers-color-scheme: dark) {
        :root { --text: #e4e9f2; --muted: #9aa5bc; --background: #0e1424; --surface: #141c2e; --accent: #8aabff; }
      }
      body { margin: 0; min-height: 100vh; display: grid; place-items: center; background: var(--background); color: var(--text); font: 15px/1.5 system-ui, sans-serif; }
      main { max-width: 32rem; padding: 2rem; }
      h1 { font-size: 1.4rem; margin: 0 0 0.75rem; }
      p { margin: 0.75rem 0; }
      code { background: var(--surface); border-radius: 4px; padding: 0.1rem 0.35rem; }
      a { color: var(--accent); }
      .muted { color: var(--muted); }
    </style>
  </head>
  <body>
    <main>
      <h1>bussola is not running</h1>
      <p>Start it in a terminal with <code id="command">bussola serve</code><span id="link">, or open a <a href="bussola://">bussola:// link</a> if you ran <code>bussola install-handler</code></span>.</p>
      <p class="muted">This page reloads by itself once bussola is running.</p>
    </main>
    <script>
      if (location.port && location.port !== '${DEFAULT_PORT}') {
        document.getElementById('command').textContent = 'bussola serve --port ' + location.port
        document.getElementById('link').remove()
      }
      const isBussola = (body) => body.app === 'bussola' || body.code === 'invalid_token'
      setInterval(() => fetch('/api/health', { cache: 'no-store' }).then((response) => response.json()).then((body) => isBussola(body) && location.reload(), () => undefined), 2000)
    </script>
  </body>
</html>`

self.addEventListener('install', (event) => {
  event.addRoutes?.({ condition: { not: { requestMode: 'navigate' } }, source: 'network' })?.catch(() => undefined)
  self.skipWaiting()
})

self.addEventListener('fetch', (event) => {
  if (event.request.mode === 'navigate') {
    event.respondWith(fetch(event.request).catch(() => new Response(OFFLINE_PAGE, { status: 503, headers: { 'Content-Type': 'text/html; charset=utf-8' } })))
  }
})
