import { UploadForm } from "@/components/upload/upload-form";

export default function UploadPage() {
  return (
    <div className="space-y-8">
      <div className="animate-fade-in border-b border-border pb-5">
        <h1 className="page-title">Upload</h1>
        <p className="text-sm text-muted-foreground mt-1.5">
          Drop a meeting recording (audio or video) to kick off the
          transcription, summary, and action-item pipeline. Up to 100 MB
          per file. Recordings land under{" "}
          <code className="font-mono text-xs">meetings/&lt;id&gt;/</code> in
          B2 alongside their transcript, summary, and actions JSON.
        </p>
      </div>
      <div className="animate-fade-in-up stagger-2">
        <UploadForm />
      </div>
    </div>
  );
}
