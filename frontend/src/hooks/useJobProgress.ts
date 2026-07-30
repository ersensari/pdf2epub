// All WebSocket connection logic for job progress lives here — components
// must consume this hook instead of opening sockets themselves.

import { useEffect, useState } from "react";
import {
  fetchJob,
  progressWsUrl,
  type BookMetadata,
  type JobInfo,
  type JobStatus,
  type Stage,
} from "../api";

const TERMINAL_STATUSES: JobStatus[] = ["done", "error", "cancelled"];
const POLL_INTERVAL_MS = 4000;

export interface JobProgressState {
  status: JobStatus;
  stage: Stage | null;
  currentPage: number;
  totalPages: number;
  metadata: BookMetadata | null;
  pagesNeedingReview: number[];
  error: string | null;
  connected: boolean;
}

const initialState: JobProgressState = {
  status: "queued",
  stage: null,
  currentPage: 0,
  totalPages: 0,
  metadata: null,
  pagesNeedingReview: [],
  error: null,
  connected: false,
};

export function useJobProgress(jobId: string | null): JobProgressState {
  const [state, setState] = useState<JobProgressState>(initialState);

  useEffect(() => {
    if (!jobId) {
      setState(initialState);
      return;
    }

    let disposed = false;
    let pollTimer: number | null = null;

    const applyInfo = (info: JobInfo) =>
      setState((s) => ({
        ...s,
        status: info.status,
        stage: info.progress.stage,
        currentPage: info.progress.current_page,
        totalPages: info.progress.total_pages,
        metadata: info.metadata,
        pagesNeedingReview: info.pages_needing_review,
        error: info.error,
      }));

    const stopPolling = () => {
      if (pollTimer !== null) {
        window.clearInterval(pollTimer);
        pollTimer = null;
      }
    };

    // Fallback when the WebSocket drops mid-job: the conversion keeps running
    // on the backend, so keep the UI alive by polling the REST endpoint.
    const startPolling = () => {
      if (disposed || pollTimer !== null) return;
      pollTimer = window.setInterval(async () => {
        try {
          const info = await fetchJob(jobId);
          applyInfo(info);
          if (TERMINAL_STATUSES.includes(info.status)) stopPolling();
        } catch {
          // Backend briefly unreachable — keep trying until cleanup.
        }
      }, POLL_INTERVAL_MS);
    };

    const socket = new WebSocket(progressWsUrl(jobId));

    socket.onopen = () => setState((s) => ({ ...s, connected: true }));

    socket.onmessage = (message: MessageEvent<string>) => {
      const event = JSON.parse(message.data);
      switch (event.type) {
        case "snapshot":
          setState((s) => ({
            ...s,
            status: event.status,
            stage: event.progress?.stage ?? null,
            currentPage: event.progress?.current_page ?? 0,
            totalPages: event.progress?.total_pages ?? 0,
            metadata: event.metadata ?? null,
            pagesNeedingReview: event.pages_needing_review ?? [],
            error: event.error ?? null,
          }));
          break;
        case "progress":
          setState((s) => ({
            ...s,
            status: event.status,
            stage: event.stage,
            currentPage: event.current_page,
            totalPages: event.total_pages,
          }));
          break;
        case "page":
          if (event.needs_review) {
            setState((s) => ({
              ...s,
              pagesNeedingReview: [...s.pagesNeedingReview, event.page_number],
            }));
          }
          break;
        case "metadata":
          setState((s) => ({ ...s, metadata: event.metadata }));
          break;
        case "finished":
          setState((s) => ({ ...s, status: event.status, error: event.error ?? null }));
          // The finished event is minimal; pull the full final state via REST.
          fetchJob(jobId)
            .then((info) =>
              setState((s) => ({
                ...s,
                status: info.status,
                metadata: info.metadata,
                pagesNeedingReview: info.pages_needing_review,
                error: info.error,
              })),
            )
            .catch(() => undefined);
          break;
      }
    };

    socket.onclose = () => {
      setState((s) => {
        // Socket closed while the job is still active → switch to polling.
        if (!TERMINAL_STATUSES.includes(s.status)) startPolling();
        return { ...s, connected: false };
      });
    };

    return () => {
      disposed = true;
      stopPolling();
      socket.close();
      setState(initialState);
    };
  }, [jobId]);

  return state;
}
