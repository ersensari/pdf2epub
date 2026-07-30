import { useCallback, useRef, useState, type DragEvent } from "react";

interface Props {
  onFileSelected: (file: File) => void;
  disabled?: boolean;
}

export default function UploadDropzone({ onFileSelected, disabled = false }: Props) {
  const [isDragging, setIsDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFile = useCallback(
    (file: File | undefined) => {
      if (!file || disabled) return;
      if (!file.name.toLowerCase().endsWith(".pdf")) return;
      onFileSelected(file);
    },
    [onFileSelected, disabled],
  );

  const onDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setIsDragging(false);
    handleFile(event.dataTransfer.files[0]);
  };

  return (
    <div
      role="button"
      tabIndex={0}
      aria-label="Upload a PDF file"
      onClick={() => inputRef.current?.click()}
      onKeyDown={(e) => e.key === "Enter" && inputRef.current?.click()}
      onDragOver={(e) => {
        e.preventDefault();
        setIsDragging(true);
      }}
      onDragLeave={() => setIsDragging(false)}
      onDrop={onDrop}
      className={`flex cursor-pointer flex-col items-center justify-center gap-3 rounded-2xl border-2 border-dashed p-12 text-center transition-colors ${
        isDragging
          ? "border-blue-500 bg-blue-50 dark:bg-blue-950"
          : "border-gray-300 bg-white hover:border-blue-400 dark:border-gray-700 dark:bg-gray-900 dark:hover:border-blue-600"
      } ${disabled ? "pointer-events-none opacity-50" : ""}`}
    >
      <span className="text-4xl" aria-hidden>
        📖
      </span>
      <p className="text-lg font-medium text-gray-800 dark:text-gray-100">
        Drop a scanned PDF here
      </p>
      <p className="text-sm text-gray-500 dark:text-gray-400">
        or click to choose a file — old Turkish books welcome
      </p>
      <input
        ref={inputRef}
        type="file"
        accept="application/pdf"
        className="hidden"
        onChange={(e) => handleFile(e.target.files?.[0])}
      />
    </div>
  );
}
