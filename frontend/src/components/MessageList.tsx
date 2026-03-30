import { useEffect, useRef } from 'react'
import type { Message } from '@/hooks/useChat'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'

interface Props {
  messages: Message[]
  streaming: boolean
}

export function MessageList({ messages, streaming }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  if (messages.length === 0) {
    return (
      <div className="flex flex-1 items-center justify-center text-muted-foreground">
        Start a conversation
      </div>
    )
  }

  return (
    <ScrollArea className="flex-1 p-4">
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
              {msg.content}
              {streaming && msg.role === 'assistant' && msg.content === '' && (
                <span className="animate-pulse">▋</span>
              )}
            </div>
          </div>
        ))}
      </div>
      <div ref={bottomRef} />
    </ScrollArea>
  )
}
