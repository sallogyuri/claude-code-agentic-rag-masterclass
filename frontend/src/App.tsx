import { useState } from 'react'
import { AuthGuard } from './components/AuthGuard'
import { ChatPage } from './pages/ChatPage'
import { IngestPage } from './pages/IngestPage'

type View = 'chat' | 'ingest'

export default function App() {
  const [view, setView] = useState<View>('chat')

  return (
    <AuthGuard>
      <div className="flex flex-col h-screen">
        <nav className="border-b bg-background px-4 py-2 flex gap-2 shrink-0">
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
        </nav>

        <div className="flex-1 overflow-hidden">
          {view === 'chat' ? <ChatPage /> : <IngestPage />}
        </div>
      </div>
    </AuthGuard>
  )
}
