import type { JobProgressState } from "../hooks/useJobProgress";
import type { Stage } from "../api";

const STAGE_LABELS: Record<Stage, string> = {
  extracting: "Extracting pages from PDF",
  ocr: "Running OCR",
  correcting: "Correcting OCR with the vision model",
  metadata: "Inferring book metadata",
  building_epub: "Assembling the EPUB",
};

export default function ProgressView({ progress }: { progress: JobProgressState }) {
  const { stage, currentPage, totalPages, pagesNeedingReview, connected } = progress;
  const percent =
    totalPages > 0 ? Math.round((currentPage / totalPages) * 100) : 0;
  const stageLabel = stage ? STAGE_LABELS[stage] : "Queued…";
  const perPage = stage === "ocr" || stage === "correcting";

  return (
    <div className="space-y-4 rounded-2xl bg-white p-6 shadow dark:bg-gray-900">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-800 dark:text-gray-100">
          Converting…
        </h2>
        <span
          className={`text-xs ${connected ? "text-green-600 dark:text-green-400" : "text-gray-400"}`}
        >
          {connected ? "● live" : "○ reconnecting"}
        </span>
      </div>

      <p className="text-sm text-gray-600 dark:text-gray-300">
        {perPage && totalPages > 0
          ? `Page ${currentPage}/${totalPages} — ${stageLabel}`
          : stageLabel}
      </p>

      <div className="h-3 w-full overflow-hidden rounded-full bg-gray-200 dark:bg-gray-700">
        <div
          className="h-full rounded-full bg-blue-500 transition-all duration-300"
          style={{ width: `${percent}%` }}
        />
      </div>

      {pagesNeedingReview.length > 0 && (
        <p className="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800 dark:bg-amber-950 dark:text-amber-200">
          ⚠️ {pagesNeedingReview.length} page(s) may need manual review:{" "}
          {pagesNeedingReview.join(", ")}
        </p>
      )}
    </div>
  );
}
