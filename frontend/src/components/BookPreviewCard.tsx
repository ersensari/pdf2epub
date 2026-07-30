import { useEffect, useState } from "react";
import { coverUrl, patchMetadata, type BookMetadata } from "../api";

interface Props {
  jobId: string;
  metadata: BookMetadata | null;
  pagesNeedingReview: number[];
  onMetadataSaved: (metadata: BookMetadata | null) => void;
}

export default function BookPreviewCard({
  jobId,
  metadata,
  pagesNeedingReview,
  onMetadataSaved,
}: Props) {
  const [title, setTitle] = useState(metadata?.title ?? "");
  const [author, setAuthor] = useState(metadata?.author ?? "");
  const [year, setYear] = useState(metadata?.year ?? "");
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [coverFailed, setCoverFailed] = useState(false);

  // Refresh the form when detected metadata arrives after mount.
  useEffect(() => {
    setTitle(metadata?.title ?? "");
    setAuthor(metadata?.author ?? "");
    setYear(metadata?.year ?? "");
  }, [metadata]);

  const dirty =
    title !== (metadata?.title ?? "") ||
    author !== (metadata?.author ?? "") ||
    year !== (metadata?.year ?? "");

  const save = async () => {
    setSaving(true);
    setSaveError(null);
    try {
      const info = await patchMetadata(jobId, {
        title,
        author,
        ...(year ? { year } : {}),
      });
      onMetadataSaved(info.metadata);
    } catch (error) {
      setSaveError(error instanceof Error ? error.message : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  const inputClass =
    "w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:border-blue-500 focus:outline-none dark:border-gray-700 dark:bg-gray-800 dark:text-gray-100";

  return (
    <div className="flex gap-6 rounded-2xl bg-white p-6 shadow dark:bg-gray-900">
      <div className="w-32 shrink-0">
        {coverFailed ? (
          <div className="flex h-44 w-32 items-center justify-center rounded-lg bg-gray-100 text-3xl dark:bg-gray-800">
            📕
          </div>
        ) : (
          <img
            src={coverUrl(jobId)}
            alt="Detected book cover"
            className="h-44 w-32 rounded-lg object-cover shadow"
            onError={() => setCoverFailed(true)}
          />
        )}
      </div>

      <div className="flex-1 space-y-3">
        <h2 className="text-lg font-semibold text-gray-800 dark:text-gray-100">
          Book details
          {metadata && (
            <span className="ml-2 text-xs font-normal text-gray-400">
              detected from {metadata.source}
            </span>
          )}
        </h2>

        <label className="block text-sm text-gray-600 dark:text-gray-300">
          Title
          <input value={title} onChange={(e) => setTitle(e.target.value)} className={inputClass} />
        </label>
        <label className="block text-sm text-gray-600 dark:text-gray-300">
          Author
          <input value={author} onChange={(e) => setAuthor(e.target.value)} className={inputClass} />
        </label>
        <label className="block text-sm text-gray-600 dark:text-gray-300">
          Year
          <input value={year ?? ""} onChange={(e) => setYear(e.target.value)} className={inputClass} />
        </label>

        {pagesNeedingReview.length > 0 && (
          <p className="rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-800 dark:bg-amber-950 dark:text-amber-200">
            ⚠️ Pages {pagesNeedingReview.join(", ")} had low OCR confidence — the
            EPUB may need manual review there.
          </p>
        )}

        {saveError && <p className="text-xs text-red-600 dark:text-red-400">{saveError}</p>}

        <button
          onClick={save}
          disabled={!dirty || saving}
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {saving ? "Saving…" : "Save & rebuild EPUB"}
        </button>
      </div>
    </div>
  );
}
