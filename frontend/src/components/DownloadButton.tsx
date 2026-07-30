import { downloadUrl } from "../api";

export default function DownloadButton({ jobId }: { jobId: string }) {
  return (
    <a
      href={downloadUrl(jobId)}
      download
      className="block w-full rounded-2xl bg-green-600 px-6 py-4 text-center text-lg font-semibold text-white shadow transition-colors hover:bg-green-700"
    >
      ⬇️ Download EPUB
    </a>
  );
}
