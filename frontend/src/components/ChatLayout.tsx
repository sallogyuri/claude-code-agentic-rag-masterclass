import { useEffect } from 'react'
import { useAuth } from '@/hooks/useAuth'
import { useChat } from '@/hooks/useChat'
import { ThreadList } from './ThreadList'
import { MessageList } from './MessageList'
import { MessageInput } from './MessageInput'
import { Button } from '@/components/ui/button'

export function ChatLayout() {
  const { signOut, user } = useAuth()
  const {
    threads,
    activeThreadId,
    messages,
    streaming,
    loadThreads,
    selectThread,
    sendMessage,
  } = useChat()

  useEffect(() => { loadThreads() }, [loadThreads])

  function handleNewChat() {
    // Clear current thread — next message will create one
    window.location.reload()
  }

  return (
    <div className="flex h-screen flex-col">
      {/* Top bar */}
      <header className="flex items-center justify-between border-b px-4 py-2">
        <span className="font-semibold">RAG Masterclass</span>
        <div className="flex items-center gap-4">
          <span className="text-sm text-muted-foreground">{user?.email}</span>
          <Button variant="ghost" size="sm" onClick={signOut}>Sign out</Button>
        </div>
      </header>

      {/* Body */}
      <div className="flex flex-1 overflow-hidden">
        <ThreadList
          threads={threads}
          activeThreadId={activeThreadId}
          onSelect={selectThread}
          onNew={handleNewChat}
        />
        <div className="flex flex-1 flex-col overflow-hidden">
          <MessageList messages={messages} streaming={streaming} />
          <MessageInput onSend={sendMessage} disabled={streaming} />
        </div>
      </div>
    </div>
  )
}
