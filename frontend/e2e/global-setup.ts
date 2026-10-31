import { execFileSync, spawn, type ChildProcess } from 'node:child_process'
import { mkdtempSync, mkdirSync, openSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import { E2E_PORT, E2E_TOKEN } from './constants.ts'

const PROJECT_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..')
const SERVER_LOG = resolve(dirname(fileURLToPath(import.meta.url)), '..', 'e2e-results', 'server.log')
const STARTUP_TIMEOUT_MS = 60_000
const POLL_INTERVAL_MS = 250

function git(repo: string, ...args: string[]) {
  execFileSync('git', args, { cwd: repo, stdio: 'ignore' })
}

function commit(repo: string, files: Record<string, string>, message: string) {
  for (const [path, content] of Object.entries(files)) {
    mkdirSync(dirname(join(repo, path)), { recursive: true })
    writeFileSync(join(repo, path), content)
  }
  git(repo, 'add', '-A')
  git(repo, 'commit', '-q', '-m', message)
}

function createRepository(root: string): string {
  const repo = join(root, 'demo')
  mkdirSync(repo)
  git(repo, 'init', '-q', '-b', 'main')
  git(repo, 'config', 'user.email', 'e2e@example.com')
  git(repo, 'config', 'user.name', 'E2E Reviewer')
  git(repo, 'config', 'commit.gpgsign', 'false')
  commit(repo, { 'app.py': 'def total(items):\n    return 0\n' }, 'base')
  git(repo, 'checkout', '-q', '-b', 'feature')
  commit(repo, { 'app.py': 'def total(items):\n    count = len(items)\n    return sum(items)\n' }, 'feature')
  return repo
}

async function waitForServer(server: ChildProcess) {
  const deadline = Date.now() + STARTUP_TIMEOUT_MS
  while (Date.now() < deadline) {
    if (server.exitCode !== null) {
      throw new Error(`bussola exited with code ${String(server.exitCode)}`)
    }
    try {
      const response = await fetch(`http://127.0.0.1:${String(E2E_PORT)}/api/health`, { headers: { cookie: `bussola_token_${String(E2E_PORT)}=${E2E_TOKEN}` } })
      if (response.ok) {
        return
      }
    } catch {
      await new Promise((done) => setTimeout(done, POLL_INTERVAL_MS))
    }
  }
  throw new Error('bussola did not start in time')
}

async function assertPortFree() {
  try {
    await fetch(`http://127.0.0.1:${String(E2E_PORT)}/`)
  } catch {
    return
  }
  throw new Error(`Port ${String(E2E_PORT)} is already in use. Stop the process using it or set BUSSOLA_E2E_PORT.`)
}

function stop(server: ChildProcess) {
  if (server.pid !== undefined && server.exitCode === null) {
    process.kill(-server.pid, 'SIGTERM')
  }
}

export default async function globalSetup() {
  await assertPortFree()
  const root = mkdtempSync(join(tmpdir(), 'bussola-e2e-'))
  const repo = createRepository(root)
  mkdirSync(dirname(SERVER_LOG), { recursive: true })
  const log = openSync(SERVER_LOG, 'w')
  const server = spawn('uv', ['run', '--project', PROJECT_ROOT, 'bussola', 'serve', '--no-open', '--port', String(E2E_PORT), '--repo', repo], {
    env: { ...process.env, BUSSOLA_DATA_DIR: join(root, 'data'), BUSSOLA_TOKEN: E2E_TOKEN },
    stdio: ['ignore', log, log],
    detached: true,
  })
  const teardown = () => {
    stop(server)
    rmSync(root, { recursive: true, force: true })
  }
  try {
    await waitForServer(server)
  } catch (error) {
    const output = readFileSync(SERVER_LOG, 'utf8')
    teardown()
    throw new Error(`${String(error)}\n${output}`, { cause: error })
  }
  return teardown
}
