// Permanent library: every generated EPUB with download + delete actions.

import { useCallback, useEffect, useState } from "react";
import { deleteEpub, epubDownloadUrl, listEpubs, type EpubEntry } from "../api";

function formatSize(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

function formatDate(unixSeconds: number): string {
  return new Date(unixSeconds * 1000).toLocaleDateString("tr-TR", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

interface Props {
  /** Bump this counter to force a refresh (e.g. after a conversion finishes). */
  refreshKey: number;
}

export default function EpubList({ refreshKey }: Props) {
  const [entries, setEntries] = useState<EpubEntry[]>([]);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(() => {
    listEpubs()
      .then((epubs) => {
        setEntries(epubs);
        setError(null);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Liste alınamadı"));
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh, refreshKey]);

  const handleDelete = async (filename: string) => {
    if (!window.confirm(`"${filename}" kalıcı olarak silinsin mi?`)) return;
    try {
      await deleteEpub(filename);
      refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Silme başarısız");
    }
  };

  return (
    <section className="rounded-2xl bg-white p-6 shadow-sm dark:bg-gray-900">
      <h2 className="mb-4 text-lg font-semibold">📚 Kütüphane</h2>

      {error && (
        <p className="mb-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
          {error}
        </p>
      )}

      {entries.length === 0 && !error && (
        <p className="text-sm text-gray-500 dark:text-gray-400">
          Henüz dönüştürülmüş kitap yok.
        </p>
      )}

      <ul className="divide-y divide-gray-100 dark:divide-gray-800">
        {entries.map((entry) => (
          <li key={entry.filename} className="flex items-center gap-3 py-3">
            <div className="min-w-0 flex-1">
              <p className="truncate font-medium" title={entry.filename}>
                {entry.filename.replace(/\.epub$/, "")}
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                {formatSize(entry.size)} · {formatDate(entry.modified_at)}
              </p>
            </div>
            <a
              href={epubDownloadUrl(entry.filename)}
              download
              className="rounded-lg bg-blue-600 px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-blue-700"
            >
              İndir
            </a>
            <button
              onClick={() => handleDelete(entry.filename)}
              className="rounded-lg border border-red-200 px-3 py-1.5 text-sm text-red-600 transition-colors hover:bg-red-50 dark:border-red-900 dark:hover:bg-red-950"
            >
              Sil
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
