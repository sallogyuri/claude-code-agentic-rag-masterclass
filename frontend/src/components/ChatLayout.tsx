import { useEffect } from 'react'
import { useChat } from '@/hooks/useChat'
import { ThreadList } from './ThreadList'
import { MessageList } from './MessageList'
import { MessageInput } from './MessageInput'

export function ChatLayout() {
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
    <div className="flex h-full overflow-hidden">
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
  )
}
