import { useHealth } from './api/health'

export default function App() {
  const health = useHealth()

  return (
    <main className="app">
      <h1>rtool</h1>
      <p>
        Backend: <span data-testid="health-status">{health.isPending ? 'checking' : health.isError ? 'unreachable' : health.data.status}</span>
      </p>
    </main>
  )
}
