#!/usr/bin/env python3
"""Batch converter: process all PDFs in data/uploads and generate EPUBs.

Usage:
    cd backend
    python3 batch_convert.py
"""

import asyncio
import sys
from pathlib import Path

from app.config import get_settings
from app.job_manager import job_manager
from app.worker import process_job


async def batch_convert() -> None:
    """Find all PDFs in uploads and convert each one."""
    settings = get_settings()
    upload_dir = settings.upload_dir
    output_dir = settings.output_dir

    output_dir.mkdir(parents=True, exist_ok=True)

    pdf_files = sorted(upload_dir.glob("*.pdf"))
    if not pdf_files:
        print("No PDFs found in", upload_dir, flush=True)
        return

    print(f"Found {len(pdf_files)} PDF(s) to convert", flush=True)
    for i, pdf_path in enumerate(pdf_files, start=1):
        print(f"\n[{i}/{len(pdf_files)}] Converting: {pdf_path.name}", flush=True)
        job = job_manager.create(pdf_path)
        try:
            print(f"  → Starting pipeline...", flush=True)
            await process_job(job, job_manager, settings)
            print(f"  → Job status: {job.status.value}", flush=True)
            if job.status.value == "done":
                print(f"  ✓ EPUB: {job.epub_path.name}", flush=True)
            else:
                print(f"  ✗ Failed: {job.error}", flush=True)
        except Exception as e:
            print(f"  ✗ Exception: {e}", flush=True)
            import traceback
            traceback.print_exc()
    print("\n=== Batch conversion complete ===", flush=True)


if __name__ == "__main__":
    asyncio.run(batch_convert())
