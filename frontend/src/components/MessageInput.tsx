import { useState } from 'react'
import type { KeyboardEvent } from 'react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'

interface Props {
  onSend: (text: string) => void
  disabled: boolean
}

export function MessageInput({ onSend, disabled }: Props) {
  const [value, setValue] = useState('')

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  function submit() {
    if (!value.trim()) return
    onSend(value.trim())
    setValue('')
  }

  return (
    <div className="border-t p-4">
      <div className="flex gap-2">
        <Textarea
          rows={1}
          placeholder="Message..."
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          className="resize-none"
        />
        <Button onClick={submit} disabled={disabled || !value.trim()}>
          Send
        </Button>
      </div>
    </div>
  )
}
