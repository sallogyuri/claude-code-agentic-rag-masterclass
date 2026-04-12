import { FileUpload } from '@/components/FileUpload'
import { DocumentList } from '@/components/DocumentList'
import { useIngestion } from '@/hooks/useIngestion'

export function IngestPage() {
  const { documents, uploadFile, deleteDocument } = useIngestion()

  return (
    <div className="max-w-2xl mx-auto p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Documents</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Upload <code>.txt</code>, <code>.md</code>, <code>.pdf</code>,{' '}
          <code>.docx</code>, or <code>.html</code> files to add them to your knowledge base.
        </p>
      </div>

      <FileUpload onUpload={uploadFile} />

      <div>
        <h2 className="text-lg font-medium mb-3">Uploaded documents</h2>
        <DocumentList documents={documents} onDelete={deleteDocument} />
      </div>
    </div>
  )
}
