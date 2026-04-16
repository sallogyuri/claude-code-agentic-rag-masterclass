import { useState } from 'react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import type { AgentEvent } from '@/hooks/useChat'

interface Props {
  events: AgentEvent[]
  subAgentContent?: string
  isStreaming: boolean
}

interface ToolCallBlock {
  kind: 'tool_call'
  tool: string
  args?: AgentEvent['args']
  sql?: string
  completed: boolean
}

interface SubAgentBlock {
  kind: 'sub_agent'
  task: string
  document: string
  toolCalls: Array<{ query: string }>
  completed: boolean
}

type Block = ToolCallBlock | SubAgentBlock

function buildBlocks(events: AgentEvent[]): Block[] {
  const blocks: Block[] = []
  let currentSub: SubAgentBlock | null = null

  for (const e of events) {
    if (e.type === 'tool_call_start') {
      blocks.push({ kind: 'tool_call', tool: e.tool ?? '', args: e.args, completed: false })
    } else if (e.type === 'tool_call_end') {
      const last = blocks[blocks.length - 1]
      if (last?.kind === 'tool_call') {
        last.completed = true
        if (e.sql) last.sql = e.sql
      }
    } else if (e.type === 'sub_agent_start') {
      currentSub = { kind: 'sub_agent', task: e.task ?? '', document: e.document ?? '', toolCalls: [], completed: false }
      blocks.push(currentSub)
    } else if (e.type === 'sub_agent_tool_call') {
      currentSub?.toolCalls.push({ query: e.query ?? '' })
    } else if (e.type === 'sub_agent_end') {
      if (currentSub) currentSub.completed = true
      currentSub = null
    }
  }

  return blocks
}

export function AgentEventBlock({ events, subAgentContent, isStreaming }: Props) {
  const [expandedIndices, setExpandedIndices] = useState<Set<number>>(new Set())
  const blocks = buildBlocks(events)

  function toggleExpand(i: number) {
    setExpandedIndices((prev) => {
      const s = new Set(prev)
      s.has(i) ? s.delete(i) : s.add(i)
      return s
    })
  }

  if (blocks.length === 0) return null

  return (
    <div className="mb-2 space-y-1">
      {blocks.map((block, i) => {
        if (block.kind === 'tool_call') {
          const expanded = expandedIndices.has(i)
          return (
            <div key={i} className="rounded border border-border bg-muted/40 px-3 py-1.5 text-xs">
              <div className="flex items-center gap-2">
                {!block.completed && isStreaming ? (
                  <span
                    className="inline-block h-3 w-3 animate-spin rounded-full border border-muted-foreground border-t-transparent"
                    aria-label="loading"
                  />
                ) : (
                  <span className="text-muted-foreground">⟲</span>
                )}
                <span className="font-medium text-muted-foreground">{block.tool}</span>
                {block.args?.query && (
                  <span className="max-w-[220px] truncate text-muted-foreground/70">
                    "{block.args.query}"
                  </span>
                )}
                <Button
                  variant="ghost"
                  size="xs"
                  className="ml-auto text-muted-foreground"
                  onClick={() => toggleExpand(i)}
                >
                  {expanded ? '▲' : '▼'}
                </Button>
              </div>
              {expanded && block.tool === 'text_to_sql' && block.sql && (
                <pre className="mt-1 overflow-auto rounded bg-muted px-2 py-1 text-xs text-muted-foreground font-mono">
                  {block.sql}
                </pre>
              )}
              {expanded && block.tool !== 'text_to_sql' && block.args && (
                <pre className="mt-1 overflow-auto rounded bg-muted px-2 py-1 text-xs text-muted-foreground">
                  {JSON.stringify(block.args, null, 2)}
                </pre>
              )}
            </div>
          )
        }

        if (block.kind === 'sub_agent') {
          const expanded = expandedIndices.has(i)
          const isActive = !block.completed

          // Completed and collapsed → show summary row
          if (block.completed && !expanded) {
            return (
              <div key={i} className="rounded border border-border bg-muted/40 px-3 py-1.5 text-xs">
                <div className="flex items-center gap-2">
                  <span className="text-muted-foreground">🤖</span>
                  <span className="text-muted-foreground">
                    Sub-agent analysed "{block.document}"
                  </span>
                  <Button
                    variant="ghost"
                    size="xs"
                    className="ml-auto text-muted-foreground"
                    onClick={() => toggleExpand(i)}
                  >
                    ▼
                  </Button>
                </div>
              </div>
            )
          }

          // Active or expanded → show full card
          return (
            <div
              key={i}
              className={cn(
                'rounded border bg-muted/40 px-3 py-2 text-xs',
                isActive ? 'border-blue-300 dark:border-blue-700' : 'border-border'
              )}
            >
              <div className="mb-1.5 flex items-center gap-2">
                {isActive && isStreaming ? (
                  <span
                    className="inline-block h-3 w-3 animate-spin rounded-full border border-muted-foreground border-t-transparent"
                    aria-label="loading"
                  />
                ) : (
                  <span className="text-muted-foreground">🤖</span>
                )}
                <span className="font-medium text-muted-foreground">
                  Sub-agent: {block.document}
                </span>
                {block.completed && (
                  <Button
                    variant="ghost"
                    size="xs"
                    className="ml-auto text-muted-foreground"
                    onClick={() => toggleExpand(i)}
                  >
                    ▲
                  </Button>
                )}
              </div>
              <div className="ml-4 space-y-1">
                {block.toolCalls.map((tc, j) => (
                  <div key={j} className="text-muted-foreground/70">
                    Searching for: "{tc.query}"
                  </div>
                ))}
                {subAgentContent && (
                  <div className="mt-1 whitespace-pre-wrap text-muted-foreground">
                    {subAgentContent}
                    {isActive && isStreaming && (
                      <span className="animate-pulse">▋</span>
                    )}
                  </div>
                )}
              </div>
            </div>
          )
        }

        return null
      })}
    </div>
  )
}
