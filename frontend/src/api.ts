// Thin REST client + shared types mirroring the backend's Pydantic models.

export const API_BASE_URL: string =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8001";

export type JobStatus = "queued" | "processing" | "done" | "error" | "cancelled";

export type Stage =
  | "extracting"
  | "ocr"
  | "correcting"
  | "metadata"
  | "building_epub";

export interface BookMetadata {
  title: string;
  author: string;
  year: string | null;
  language: string;
  source: "pdf" | "llm" | "user" | "unknown";
}

export interface Progress {
  current_page: number;
  total_pages: number;
  stage: Stage | null;
}

export interface JobInfo {
  job_id: string;
  status: JobStatus;
  progress: Progress;
  metadata: BookMetadata | null;
  pages_needing_review: number[];
  error: string | null;
}

export async function uploadPdf(file: File): Promise<string> {
  const body = new FormData();
  body.append("file", file);
  const response = await fetch(`${API_BASE_URL}/api/upload`, { method: "POST", body });
  if (!response.ok) throw new Error(`Upload failed: ${response.statusText}`);
  const data: { job_id: string } = await response.json();
  return data.job_id;
}

export async function fetchJob(jobId: string): Promise<JobInfo> {
  const response = await fetch(`${API_BASE_URL}/api/jobs/${jobId}`);
  if (!response.ok) throw new Error(`Job fetch failed: ${response.statusText}`);
  return response.json();
}

export async function patchMetadata(
  jobId: string,
  patch: { title?: string; author?: string; year?: string },
): Promise<JobInfo> {
  const response = await fetch(`${API_BASE_URL}/api/jobs/${jobId}/metadata`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  if (!response.ok) throw new Error(`Metadata update failed: ${response.statusText}`);
  return response.json();
}

export async function cancelJob(jobId: string): Promise<JobInfo> {
  const response = await fetch(`${API_BASE_URL}/api/jobs/${jobId}/cancel`, { method: "POST" });
  if (!response.ok) throw new Error(`Cancel failed: ${response.statusText}`);
  return response.json();
}

export function coverUrl(jobId: string): string {
  return `${API_BASE_URL}/api/jobs/${jobId}/cover`;
}

export function downloadUrl(jobId: string): string {
  return `${API_BASE_URL}/api/jobs/${jobId}/download`;
}

export function progressWsUrl(jobId: string): string {
  const wsBase = API_BASE_URL.replace(/^http/, "ws");
  return `${wsBase}/api/jobs/${jobId}/progress`;
}

export interface EpubEntry {
  filename: string;
  size: number;
  modified_at: number;
}

export async function listEpubs(): Promise<EpubEntry[]> {
  const response = await fetch(`${API_BASE_URL}/api/epubs`);
  if (!response.ok) throw new Error(`List EPUBs failed: ${response.statusText}`);
  const data: { epubs: EpubEntry[] } = await response.json();
  return data.epubs;
}

export function epubDownloadUrl(filename: string): string {
  return `${API_BASE_URL}/api/epubs/${encodeURIComponent(filename)}`;
}

export async function deleteEpub(filename: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/epubs/${encodeURIComponent(filename)}`, {
    method: "DELETE",
  });
  if (!response.ok) throw new Error(`Delete failed: ${response.statusText}`);
}
