import { useCallback, useState } from "react";
import type { AttachmentRef } from "../types/protocol";

export interface PendingFile {
  id: string;
  file: File;
  status: "pending" | "uploading" | "done" | "error";
  progress: number;
  result?: AttachmentRef;
  error?: string;
}

const MAX_FILE_SIZE = 600 * 1024 * 1024;

export function useFileUpload(sessionId: string | null) {
  const [files, setFiles] = useState<PendingFile[]>([]);

  const addFiles = useCallback((newFiles: FileList | File[]) => {
    const entries: PendingFile[] = [];
    for (const file of Array.from(newFiles)) {
      if (file.size > MAX_FILE_SIZE) {
        entries.push({
          id: crypto.randomUUID(),
          file,
          status: "error",
          progress: 0,
          error: `File exceeds ${MAX_FILE_SIZE / (1024 * 1024)} MB limit`,
        });
        continue;
      }
      entries.push({
        id: crypto.randomUUID(),
        file,
        status: "pending",
        progress: 0,
      });
    }
    setFiles((prev) => [...prev, ...entries]);
  }, []);

  const removeFile = useCallback((id: string) => {
    setFiles((prev) => prev.filter((f) => f.id !== id));
  }, []);

  const clearFiles = useCallback(() => {
    setFiles([]);
  }, []);

  const uploadAll = useCallback(async (): Promise<AttachmentRef[]> => {
    if (!sessionId) {
      return [];
    }

    const pending = files.filter((f) => f.status === "pending");
    if (pending.length === 0) {
      return files
        .filter((f) => f.status === "done" && f.result)
        .map((f) => f.result!);
    }

    const results: AttachmentRef[] = [];

    for (const pf of pending) {
      setFiles((prev) =>
        prev.map((f) =>
          f.id === pf.id ? { ...f, status: "uploading" as const, progress: 30 } : f,
        ),
      );

      try {
        const formData = new FormData();
        formData.append("file", pf.file);
        formData.append("session_id", sessionId);

        const res = await fetch("/api/upload", { method: "POST", body: formData });
        if (!res.ok) {
          const body = (await res.json().catch(() => ({ error: "Upload failed" }))) as {
            error?: string;
          };
          throw new Error(body.error || `HTTP ${res.status}`);
        }

        const data = (await res.json()) as AttachmentRef[];
        const ref = data[0];
        if (!ref) throw new Error("Empty response");

        setFiles((prev) =>
          prev.map((f) =>
            f.id === pf.id ? { ...f, status: "done" as const, progress: 100, result: ref } : f,
          ),
        );
        results.push(ref);
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Upload failed";
        setFiles((prev) =>
          prev.map((f) =>
            f.id === pf.id ? { ...f, status: "error" as const, progress: 0, error: msg } : f,
          ),
        );
      }
    }

    const alreadyDone = files
      .filter((f) => f.status === "done" && f.result)
      .map((f) => f.result!);

    return [...alreadyDone, ...results];
  }, [files, sessionId]);

  const hasFiles = files.length > 0;
  const isUploading = files.some((f) => f.status === "uploading");

  return { files, addFiles, removeFile, clearFiles, uploadAll, hasFiles, isUploading };
}
