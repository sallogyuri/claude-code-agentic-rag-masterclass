import { useEffect, useRef } from 'react'
import type { Message } from '@/hooks/useChat'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { AgentEventBlock } from '@/components/AgentEventBlock'

interface Props {
  messages: Message[]
  streaming: boolean
}

export function MessageList({ messages, streaming }: Props) {
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = scrollRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [messages])

  if (messages.length === 0) {
    return (
      <div className="flex flex-1 items-center justify-center text-muted-foreground">
        Start a conversation
      </div>
    )
  }

  return (
    <div ref={scrollRef} className="flex-1 overflow-y-auto p-4">
      <div className="space-y-6">
        {messages.map((msg) => (
          <div key={msg.id} className={`flex gap-3 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
            <Avatar className="h-8 w-8 shrink-0">
              <AvatarFallback>{msg.role === 'user' ? 'U' : 'AI'}</AvatarFallback>
            </Avatar>
            <div
              className={`max-w-[75%] rounded-lg px-4 py-2 text-sm ${
                msg.role === 'user'
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-muted'
              }`}
            >
              {msg.role === 'assistant' && msg.events && msg.events.length > 0 && (
                <AgentEventBlock
                  events={msg.events}
                  subAgentContent={msg.subAgentContent}
                  isStreaming={streaming}
                />
              )}
              {msg.content}
              {streaming && msg.role === 'assistant' && msg.content === '' && !msg.events?.length && (
                <span className="animate-pulse">▋</span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
