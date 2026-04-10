import { useState } from 'react'
import { ChevronRight } from 'lucide-react'
import { Button } from '@/components/ui/button'
import type { Document } from '@/hooks/useIngestion'

const STATUS_CLASSES: Record<string, string> = {
  pending: 'bg-gray-100 text-gray-600',
  processing: 'bg-yellow-100 text-yellow-700',
  complete: 'bg-green-100 text-green-700',
  error: 'bg-red-100 text-red-700',
}

const DOC_TYPE_CLASSES: Record<string, string> = {
  article: 'bg-blue-100 text-blue-700',
  report: 'bg-purple-100 text-purple-700',
  contract: 'bg-orange-100 text-orange-700',
  email: 'bg-teal-100 text-teal-700',
  manual: 'bg-indigo-100 text-indigo-700',
  invoice: 'bg-pink-100 text-pink-700',
  memo: 'bg-cyan-100 text-cyan-700',
  other: 'bg-gray-100 text-gray-600',
}

interface DocumentListProps {
  documents: Document[]
  onDelete: (id: string) => Promise<void>
}

export function DocumentList({ documents, onDelete }: DocumentListProps) {
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [expandedId, setExpandedId] = useState<string | null>(null)

  async function handleDelete(id: string) {
    if (!window.confirm('Delete this document and all its chunks?')) return
    setDeletingId(id)
    try {
      await onDelete(id)
    } finally {
      setDeletingId(null)
    }
  }

  function isExpandable(doc: Document): boolean {
    return doc.status === 'complete' && !!doc.metadata && Object.keys(doc.metadata).length > 0
  }

  function toggleExpand(doc: Document) {
    if (!isExpandable(doc)) return
    setExpandedId((prev) => (prev === doc.id ? null : doc.id))
  }

  if (documents.length === 0) {
    return (
      <p className="text-sm text-muted-foreground text-center py-8">
        No documents uploaded yet
      </p>
    )
  }

  return (
    <ul className="space-y-1">
      {documents.map((doc) => {
        const expandable = isExpandable(doc)
        const isExpanded = expandedId === doc.id
        const meta = doc.metadata

        return (
          <li key={doc.id} className="rounded-lg border overflow-hidden">
            {/* Row */}
            <div
              className={`flex items-center gap-2 px-4 py-3 text-sm select-none${expandable ? ' cursor-pointer hover:bg-accent/50' : ''}`}
              onClick={() => toggleExpand(doc)}
            >
              {/* Chevron icon — visible only for expandable docs */}
              <div
                className="shrink-0 text-muted-foreground"
                style={{
                  width: 16,
                  transition: 'transform 150ms ease',
                  transform: isExpanded ? 'rotate(90deg)' : 'rotate(0deg)',
                  visibility: expandable ? 'visible' : 'hidden',
                }}
              >
                <ChevronRight size={14} />
              </div>

              <span className="font-medium truncate flex-1">{doc.name}</span>

              <div className="flex items-center gap-3 shrink-0">
                <span className="text-muted-foreground text-xs">
                  {new Date(doc.created_at).toLocaleDateString()}
                </span>
                <span
                  className={`px-2 py-0.5 rounded-full text-xs font-medium capitalize ${
                    STATUS_CLASSES[doc.status] ?? STATUS_CLASSES.pending
                  }`}
                >
                  {doc.status}
                </span>
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-destructive hover:text-destructive h-7 px-2"
                  disabled={deletingId === doc.id}
                  onClick={(e) => {
                    e.stopPropagation()
                    handleDelete(doc.id)
                  }}
                >
                  {deletingId === doc.id ? '...' : 'Delete'}
                </Button>
              </div>
            </div>

            {/* Metadata Panel */}
            {isExpanded && meta && (
              <div className="px-5 pb-4 pt-3 border-t bg-accent/30 text-sm space-y-2">
                {/* Title — only if different from filename */}
                {meta.title && meta.title !== doc.name && (
                  <p className="font-semibold text-foreground">{meta.title}</p>
                )}

                {/* document_type pill */}
                {meta.document_type && (
                  <span
                    className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium capitalize ${
                      DOC_TYPE_CLASSES[meta.document_type] ?? DOC_TYPE_CLASSES.other
                    }`}
                  >
                    {meta.document_type}
                  </span>
                )}

                {/* Summary */}
                {meta.summary && (
                  <p className="text-muted-foreground leading-snug">{meta.summary}</p>
                )}

                {/* Topics chips */}
                {meta.topics && meta.topics.length > 0 && (
                  <div className="flex flex-wrap gap-1">
                    {meta.topics.slice(0, 5).map((topic) => (
                      <span
                        key={topic}
                        className="px-2 py-0.5 rounded-md bg-secondary text-secondary-foreground text-xs"
                      >
                        {topic}
                      </span>
                    ))}
                    {meta.topics.length > 5 && (
                      <span className="px-2 py-0.5 rounded-md bg-secondary text-secondary-foreground text-xs opacity-60">
                        +{meta.topics.length - 5} more
                      </span>
                    )}
                  </div>
                )}

                {/* Author / Date / Language detail line */}
                {(meta.author || meta.date || meta.language) && (
                  <p className="text-xs text-muted-foreground flex gap-3 flex-wrap">
                    {meta.author && <span>Author: {meta.author}</span>}
                    {meta.date && <span>Date: {meta.date}</span>}
                    {meta.language && <span>Language: {meta.language.toUpperCase()}</span>}
                  </p>
                )}
              </div>
            )}
          </li>
        )
      })}
    </ul>
  )
}
