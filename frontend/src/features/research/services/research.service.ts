/**
 * AlphaNexus — Research Service
 * Handles both synchronous and SSE-streaming research API calls.
 */

import axios from 'axios';
import type {
  AgentResearchRequest,
  AgentResearchResponse,
  AgentStatus,
  ResearchSession,
  SSEEventType,
  SSEActivityEvent,
  SSEAnswerEvent,
  SSESourcesEvent,
  SSEDoneEvent,
} from '../types/research.types';

const BASE = '/api/v1/agent';

// ─── Synchronous research ────────────────────────────────────────────────────

export async function runResearch(
  payload: AgentResearchRequest,
): Promise<AgentResearchResponse> {
  const res = await axios.post<AgentResearchResponse>(`${BASE}/research`, payload, {
    timeout: 120_000,
  });
  return res.data;
}

// ─── Streaming research (SSE) ────────────────────────────────────────────────

export interface StreamHandlers {
  onActivity: (event: SSEActivityEvent) => void;
  onAnswer: (event: SSEAnswerEvent) => void;
  onSources: (event: SSESourcesEvent) => void;
  onDone: (event: SSEDoneEvent) => void;
  onError: (error: string) => void;
  onPersisted?: (data: { message_id: string; session_id: string }) => void;
}

/**
 * Run research with SSE streaming using fetch ReadableStream.
 * Returns an AbortController so the caller can cancel mid-stream.
 */
export function streamResearch(
  payload: AgentResearchRequest,
  handlers: StreamHandlers,
): AbortController {
  const controller = new AbortController();

  (async () => {
    try {
      const response = await fetch(`${BASE}/research/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        signal: controller.signal,
      });

      if (!response.ok) {
        handlers.onError(`Server error: ${response.status} ${response.statusText}`);
        return;
      }

      const reader = response.body?.getReader();
      if (!reader) {
        handlers.onError('No readable stream from server');
        return;
      }

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // SSE messages are separated by double newlines
        const messages = buffer.split('\n\n');
        buffer = messages.pop() ?? '';

        for (const msg of messages) {
          if (!msg.trim()) continue;

          let eventType: SSEEventType = 'activity';
          let dataStr = '';

          for (const line of msg.split('\n')) {
            if (line.startsWith('event: ')) {
              eventType = line.slice(7).trim() as SSEEventType;
            } else if (line.startsWith('data: ')) {
              dataStr = line.slice(6).trim();
            }
          }

          if (!dataStr) continue;

          try {
            const data = JSON.parse(dataStr);
            switch (eventType) {
              case 'activity':
                handlers.onActivity(data as SSEActivityEvent);
                break;
              case 'answer':
                handlers.onAnswer(data as SSEAnswerEvent);
                break;
              case 'sources':
                handlers.onSources(data as SSESourcesEvent);
                break;
              case 'done':
                handlers.onDone(data as SSEDoneEvent);
                break;
              case 'error':
                handlers.onError(data.message || 'Unknown error');
                break;
              case 'persisted':
                handlers.onPersisted?.(data);
                break;
            }
          } catch {
            // Malformed SSE data — ignore
          }
        }
      }
    } catch (err: any) {
      if (err?.name === 'AbortError') return; // Cancelled by user
      handlers.onError(err?.message ?? 'Stream connection failed');
    }
  })();

  return controller;
}

// ─── Sessions ────────────────────────────────────────────────────────────────

export async function listAgentSessions(limit = 25): Promise<ResearchSession[]> {
  const res = await axios.get<ResearchSession[]>(`${BASE}/sessions`, {
    params: { limit },
  });
  return res.data;
}

export async function getAgentSession(sessionId: string): Promise<ResearchSession> {
  const res = await axios.get<ResearchSession>(`${BASE}/sessions/${sessionId}`);
  return res.data;
}

export async function createAgentSession(
  title?: string,
  companyId?: string,
): Promise<{ session_id: string; title: string }> {
  const res = await axios.post(`${BASE}/sessions`, null, {
    params: { title: title || 'New Research', company_id: companyId },
  });
  return res.data;
}

export async function deleteAgentSession(sessionId: string): Promise<void> {
  await axios.delete(`${BASE}/sessions/${sessionId}`);
}

// ─── Status ──────────────────────────────────────────────────────────────────

export async function getAgentStatus(): Promise<AgentStatus> {
  const res = await axios.get<AgentStatus>(`${BASE}/status`);
  return res.data;
}
