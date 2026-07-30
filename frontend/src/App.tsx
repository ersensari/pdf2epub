import { useState } from "react";
import { cancelJob, downloadUrl, uploadPdf } from "./api";
import EpubList from "./components/EpubList";
import ProgressView from "./components/ProgressView";
import UploadDropzone from "./components/UploadDropzone";
import { useJobProgress } from "./hooks/useJobProgress";

export default function App() {
  const [jobId, setJobId] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [cancelling, setCancelling] = useState(false);
  const [libraryRefresh, setLibraryRefresh] = useState(0);
  const progress = useJobProgress(jobId);

  const handleFile = async (file: File) => {
    setUploadError(null);
    try {
      const id = await uploadPdf(file);
      setJobId(id);
    } catch (error) {
      setUploadError(error instanceof Error ? error.message : "Upload failed");
    }
  };

  const reset = () => {
    setJobId(null);
    setUploadError(null);
    setCancelling(false);
    // A finished conversion may have added a book — refresh the library.
    setLibraryRefresh((n) => n + 1);
  };

  const handleStop = async () => {
    if (!jobId) return;
    setCancelling(true);
    try {
      await cancelJob(jobId);
    } catch {
      setCancelling(false);
    }
  };

  const isProcessing =
    jobId !== null && (progress.status === "queued" || progress.status === "processing");
  const isDone = jobId !== null && progress.status === "done";
  const isError = jobId !== null && progress.status === "error";
  const isCancelled = jobId !== null && progress.status === "cancelled";

  return (
    <div className="min-h-screen bg-gray-100 text-gray-900 dark:bg-gray-950 dark:text-gray-100">
      <main className="mx-auto flex max-w-2xl flex-col gap-6 px-4 py-12">
        <header className="text-center">
          <h1 className="text-3xl font-bold">pdf2epub</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            Turn scanned old Turkish books into clean EPUBs — OCR corrected by a
            local vision model.
          </p>
        </header>

        {jobId === null && (
          <>
            <UploadDropzone onFileSelected={handleFile} />
            {uploadError && (
              <p className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
                {uploadError}
              </p>
            )}
          </>
        )}

        {isProcessing && (
          <div className="space-y-4">
            <ProgressView progress={progress} />
            <button
              onClick={handleStop}
              disabled={cancelling}
              className="w-full rounded-lg border border-red-300 bg-white px-4 py-2 text-sm font-medium text-red-600 transition-colors hover:bg-red-50 disabled:opacity-50 dark:border-red-900 dark:bg-gray-900 dark:hover:bg-red-950"
            >
              {cancelling ? "Durduruluyor…" : "⏹ Dönüştürmeyi Durdur"}
            </button>
          </div>
        )}

        {isDone && jobId && (
          <div className="space-y-4">
            <div className="rounded-2xl bg-green-50 p-6 dark:bg-green-950">
              <h2 className="font-semibold text-green-800 dark:text-green-200">✓ Tamamlandı!</h2>
              <p className="mt-1 text-sm text-green-700 dark:text-green-300">
                {progress.metadata?.title || "Kitap"} — EPUB hazır; aşağıdan indirebilir ya da
                kütüphanede saklayabilirsin.
              </p>
            </div>
            <a
              href={downloadUrl(jobId)}
              download
              className="block w-full rounded-2xl bg-blue-600 px-6 py-4 text-center text-lg font-semibold text-white shadow transition-colors hover:bg-blue-700"
            >
              📥 EPUB İndir
            </a>
            <button
              onClick={reset}
              className="w-full rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm text-gray-700 transition-colors hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-300 dark:hover:bg-gray-800"
            >
              Başka Kitap Dönüştür
            </button>
          </div>
        )}

        {isCancelled && (
          <div className="space-y-4 rounded-2xl bg-yellow-50 p-6 dark:bg-yellow-950">
            <div>
              <h2 className="font-semibold text-yellow-800 dark:text-yellow-200">⏹ Durduruldu</h2>
              <p className="mt-1 text-sm text-yellow-700 dark:text-yellow-300">
                Dönüştürme iptal edildi; yüklenen PDF silindi.
              </p>
            </div>
            <button
              onClick={reset}
              className="w-full rounded-lg bg-yellow-600 px-4 py-2 text-sm text-white transition-colors hover:bg-yellow-700"
            >
              Yeni Dönüştürme
            </button>
          </div>
        )}

        {isError && (
          <div className="space-y-4 rounded-2xl bg-red-50 p-6 dark:bg-red-950">
            <div>
              <h2 className="font-semibold text-red-800 dark:text-red-200">❌ Dönüştürme Başarısız</h2>
              <p className="mt-1 text-sm text-red-700 dark:text-red-300">{progress.error ?? "Bilinmeyen hata"}</p>
            </div>
            <button
              onClick={reset}
              className="w-full rounded-lg bg-red-600 px-4 py-2 text-sm text-white transition-colors hover:bg-red-700"
            >
              Tekrar Dene
            </button>
          </div>
        )}

        <EpubList refreshKey={libraryRefresh} />
      </main>
    </div>
  );
}
