import { useState, useCallback, useRef } from 'react'
import { apiFetch } from '@/lib/api'
import { supabase } from '@/lib/supabase'

export interface AgentEvent {
  type: 'tool_call_start' | 'tool_call_end' | 'sub_agent_start'
       | 'sub_agent_tool_call' | 'sub_agent_delta' | 'sub_agent_end'
  tool?: string
  args?: { query?: string; metadata_filter?: Record<string, unknown> | null }
  sql?: string
  task?: string
  document?: string
  query?: string
  delta?: string
}

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  created_at: string
  events?: AgentEvent[]
  subAgentContent?: string
}

export interface Thread {
  id: string
  title: string
  created_at: string
  updated_at: string
}

export function useChat() {
  const [threads, setThreads] = useState<Thread[]>([])
  const [activeThreadId, setActiveThreadId] = useState<string | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [streaming, setStreaming] = useState(false)
  const abortRef = useRef<AbortController | null>(null)

  const loadThreads = useCallback(async () => {
    const res = await apiFetch('/chat/threads')
    if (res.ok) setThreads(await res.json())
  }, [])

  const loadMessages = useCallback(async (threadId: string) => {
    const res = await apiFetch(`/chat/threads/${threadId}/messages`)
    if (res.ok) setMessages(await res.json())
  }, [])

  const selectThread = useCallback(async (threadId: string) => {
    setActiveThreadId(threadId)
    await loadMessages(threadId)
  }, [loadMessages])

  const sendMessage = useCallback(async (text: string) => {
    if (!text.trim() || streaming) return

    // Optimistically add user message
    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content: text,
      created_at: new Date().toISOString(),
    }
    const assistantMsg: Message = {
      id: crypto.randomUUID(),
      role: 'assistant',
      content: '',
      created_at: new Date().toISOString(),
      events: [],
      subAgentContent: '',
    }
    setMessages((prev) => [...prev, userMsg, assistantMsg])
    setStreaming(true)

    const { data } = await supabase.auth.getSession()
    const token = data.session?.access_token
    const apiUrl = import.meta.env.VITE_API_URL as string

    abortRef.current = new AbortController()

    const res = await fetch(`${apiUrl}/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ message: text, thread_id: activeThreadId }),
      signal: abortRef.current.signal,
    })

    if (!res.body) { setStreaming(false); return }

    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n\n')
      buffer = lines.pop() ?? ''

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        const payload = JSON.parse(line.slice(6))

        // Text delta — new typed format or legacy format
        if (payload.type === 'delta' || (!payload.type && payload.delta)) {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantMsg.id
                ? { ...m, content: m.content + payload.delta }
                : m
            )
          )
        }

        // Sub-agent text — accumulate into subAgentContent
        else if (payload.type === 'sub_agent_delta') {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantMsg.id
                ? { ...m, subAgentContent: (m.subAgentContent ?? '') + payload.delta }
                : m
            )
          )
        }

        // Structured agent events
        else if (
          payload.type === 'tool_call_start' ||
          payload.type === 'tool_call_end' ||
          payload.type === 'sub_agent_start' ||
          payload.type === 'sub_agent_tool_call' ||
          payload.type === 'sub_agent_end'
        ) {
          const event: AgentEvent = {
            type: payload.type,
            tool: payload.tool,
            args: payload.args,
            sql: payload.sql,
            task: payload.task,
            document: payload.document,
            query: payload.query,
            delta: payload.delta,
          }
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantMsg.id
                ? { ...m, events: [...(m.events ?? []), event] }
                : m
            )
          )
        }

        // Done — new typed format or legacy format
        else if (payload.type === 'done' || payload.done) {
          const threadId: string = payload.thread_id
          setActiveThreadId(threadId)
          await loadThreads()
        }

        else if (payload.type === 'error' || payload.error) {
          console.error('SSE error:', payload.error)
        }
      }
    }

    setStreaming(false)
  }, [activeThreadId, streaming, loadThreads])

  return {
    threads,
    activeThreadId,
    messages,
    streaming,
    loadThreads,
    selectThread,
    sendMessage,
  }
}
