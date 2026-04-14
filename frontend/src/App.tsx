import { useState } from 'react'
import { AuthGuard } from './components/AuthGuard'
import { ChatPage } from './pages/ChatPage'
import { IngestPage } from './pages/IngestPage'
import { useAuth } from './hooks/useAuth'
import { Button } from './components/ui/button'

type View = 'chat' | 'ingest'

function AppInner() {
  const [view, setView] = useState<View>('chat')
  const { user, signOut } = useAuth()

  return (
    <div className="flex flex-col h-screen">
      <nav className="border-b bg-background px-4 py-2 flex items-center gap-4 shrink-0">
        <span className="font-semibold mr-2">RAG Masterclass</span>
        <div className="flex gap-2">
          <button
            onClick={() => setView('chat')}
            className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${
              view === 'chat'
                ? 'bg-primary text-primary-foreground'
                : 'text-muted-foreground hover:text-foreground'
            }`}
          >
            Chat
          </button>
          <button
            onClick={() => setView('ingest')}
            className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${
              view === 'ingest'
                ? 'bg-primary text-primary-foreground'
                : 'text-muted-foreground hover:text-foreground'
            }`}
          >
            Documents
          </button>
        </div>
        <div className="ml-auto flex items-center gap-4">
          <span className="text-sm text-muted-foreground">{user?.email}</span>
          <Button variant="ghost" size="sm" onClick={signOut}>Sign out</Button>
        </div>
      </nav>

      <div className="flex-1 overflow-hidden">
        {view === 'chat' ? <ChatPage /> : <IngestPage />}
      </div>
    </div>
  )
}

export default function App() {
  return (
    <AuthGuard>
      <AppInner />
    </AuthGuard>
  )
}
