import type { Thread } from '@/hooks/useChat'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Separator } from '@/components/ui/separator'

interface Props {
  threads: Thread[]
  activeThreadId: string | null
  onSelect: (id: string) => void
  onNew: () => void
}

export function ThreadList({ threads, activeThreadId, onSelect, onNew }: Props) {
  return (
    <div className="flex h-full w-64 flex-col border-r">
      <div className="p-4">
        <Button onClick={onNew} className="w-full" variant="outline">
          New Chat
        </Button>
      </div>
      <Separator />
      <ScrollArea className="flex-1">
        <div className="space-y-1 p-2">
          {threads.map((t) => (
            <button
              key={t.id}
              onClick={() => onSelect(t.id)}
              className={`w-full rounded-md px-3 py-2 text-left text-sm hover:bg-accent ${
                activeThreadId === t.id ? 'bg-accent' : ''
              }`}
            >
              {t.title}
            </button>
          ))}
        </div>
      </ScrollArea>
    </div>
  )
}
