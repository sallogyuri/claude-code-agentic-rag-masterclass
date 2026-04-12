import { useRef, useState } from 'react'
import { Button } from '@/components/ui/button'

interface FileUploadProps {
  onUpload: (file: File) => Promise<{ duplicate: boolean }>
}

export function FileUpload({ onUpload }: FileUploadProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  const [status, setStatus] = useState<'idle' | 'uploading' | 'duplicate'>('idle')

  async function handleFile(file: File) {
    setStatus('uploading')
    try {
      const result = await onUpload(file)
      if (result.duplicate) {
        setStatus('duplicate')
        setTimeout(() => setStatus('idle'), 3000)
      } else {
        setStatus('idle')
      }
    } catch {
      setStatus('idle')
    }
  }

  function onDrop(e: React.DragEvent) {
    e.preventDefault()
    setDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) handleFile(file)
  }

  function onInputChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (file) handleFile(file)
    e.target.value = ''
  }

  return (
    <div
      className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
        dragging ? 'border-primary bg-primary/5' : 'border-muted-foreground/25'
      }`}
      onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".txt,.md,.pdf,.docx,.html"
        className="hidden"
        onChange={onInputChange}
      />
      <p className="text-sm text-muted-foreground mb-3">
        Drag and drop a <code>.txt</code>, <code>.md</code>, <code>.pdf</code>,{' '}
        <code>.docx</code>, or <code>.html</code> file here, or
      </p>
      <Button
        variant="outline"
        onClick={() => inputRef.current?.click()}
        disabled={status === 'uploading'}
      >
        {status === 'uploading' ? 'Uploading…' : 'Browse files'}
      </Button>
      {status === 'duplicate' && (
        <p className="text-sm text-muted-foreground mt-3">
          This file is already up to date.
        </p>
      )}
    </div>
  )
}
