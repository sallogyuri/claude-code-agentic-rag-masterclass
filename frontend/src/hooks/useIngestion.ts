import { useState, useCallback, useEffect } from 'react'
import { apiFetch } from '@/lib/api'
import { supabase } from '@/lib/supabase'

export interface DocumentMetadata {
  title?: string
  summary?: string
  document_type?: string
  topics?: string[]
  language?: string
  author?: string
  date?: string
}

export interface Document {
  id: string
  name: string
  size: number
  mime_type: string
  status: 'pending' | 'processing' | 'complete' | 'error'
  created_at: string
  metadata?: DocumentMetadata
}

export interface IngestionJob {
  id: string
  document_id: string
  status: 'pending' | 'processing' | 'complete' | 'error'
  error_message: string | null
}

export function useIngestion() {
  const [documents, setDocuments] = useState<Document[]>([])
  const [jobs, setJobs] = useState<Map<string, IngestionJob>>(new Map())

  const loadDocuments = useCallback(async () => {
    const res = await apiFetch('/ingest/documents')
    if (res.ok) {
      const data: Document[] = await res.json()
      setDocuments(data)
    }
  }, [])

  const uploadFile = useCallback(async (file: File): Promise<{ duplicate: boolean }> => {
    const formData = new FormData()
    formData.append('file', file)

    const { data } = await supabase.auth.getSession()
    const token = data.session?.access_token
    const apiUrl = import.meta.env.VITE_API_URL as string

    const res = await fetch(`${apiUrl}/ingest/upload`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
      body: formData,
    })

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Upload failed' }))
      throw new Error(err.detail ?? 'Upload failed')
    }

    const result = await res.json()

    // Only refresh list for new/updated files — duplicates need no change
    if (!result.duplicate) {
      await loadDocuments()
    }

    return { duplicate: result.duplicate ?? false }
  }, [loadDocuments])

  // Supabase Realtime subscription for ingestion_jobs
  useEffect(() => {
    let userId: string | null = null

    supabase.auth.getSession().then(({ data }) => {
      userId = data.session?.user.id ?? null
      if (!userId) return

      const channel = supabase
        .channel('ingestion_jobs')
        .on(
          'postgres_changes',
          {
            event: '*',
            schema: 'public',
            table: 'ingestion_jobs',
            filter: `user_id=eq.${userId}`,
          },
          (payload) => {
            const job = payload.new as IngestionJob
            setJobs((prev) => new Map(prev).set(job.id, job))

            // Refresh document list when a job reaches a terminal state
            if (job.status === 'complete' || job.status === 'error') {
              loadDocuments()
            }
          }
        )
        .subscribe()

      return () => {
        supabase.removeChannel(channel)
      }
    })
  }, [loadDocuments])

  useEffect(() => {
    loadDocuments()
  }, [loadDocuments])

  const deleteDocument = useCallback(async (documentId: string) => {
    const res = await apiFetch(`/ingest/documents/${documentId}`, { method: 'DELETE' })
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Delete failed' }))
      throw new Error(err.detail ?? 'Delete failed')
    }
    setDocuments((prev) => prev.filter((d) => d.id !== documentId))
  }, [])

  return { documents, jobs, uploadFile, loadDocuments, deleteDocument }
}
