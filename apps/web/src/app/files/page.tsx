import Link from "next/link";
import { Upload } from "lucide-react";

import { Button } from "@/components/ui/button";
import { FileBrowser } from "@/components/files/file-browser";

export default function FilesPage() {
  return (
    <div className="space-y-8">
      <div className="animate-fade-in border-b border-border pb-5 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="page-title">Files</h1>
          <p className="text-sm text-muted-foreground mt-1.5">
            Full-bucket explorer — every object in your B2 bucket, including the
            per-meeting bundles. For the meeting-centric view, see{" "}
            <Link href="/meetings" className="underline">
              Meetings
            </Link>
            .
          </p>
        </div>
        <Button asChild size="sm" className="h-8">
          <Link href="/upload">
            <Upload className="h-3.5 w-3.5" />
            Upload
          </Link>
        </Button>
      </div>
      <div className="animate-fade-in-up stagger-2">
        <FileBrowser />
      </div>
    </div>
  );
}
