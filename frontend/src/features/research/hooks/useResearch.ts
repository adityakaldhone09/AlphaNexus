/**
 * useResearch — core research state and submission hook.
 * Manages both streaming and non-streaming research runs.
 */

import { useState, useCallback, useRef } from 'react';
import { streamResearch, runResearch } from '../services/research.service';
import type {
  ResearchMode,
  AgentActivityEvent,
  ResearchMessage,
  SSEActivityEvent,
  SSEAnswerEvent,
  SSESourcesEvent,
} from '../types/research.types';

export interface UseResearchState {
  messages: ResearchMessage[];
  activityLog: AgentActivityEvent[];
  isStreaming: boolean;
  currentStage: string;
  sourcesFound: string[];
  toolsUsed: string[];
  error: string | null;
  sessionId: string | null;
}

export function useResearch(initialSessionId?: string) {
  const [state, setState] = useState<UseResearchState>({
    messages: [],
    activityLog: [],
    isStreaming: false,
    currentStage: '',
    sourcesFound: [],
    toolsUsed: [],
    error: null,
    sessionId: initialSessionId ?? null,
  });

  const abortRef = useRef<AbortController | null>(null);

  const submit = useCallback(
    async (
      query: string,
      mode: ResearchMode,
      companySymbol?: string,
      companyId?: string,
      financialYear?: string,
    ) => {
      if (!query.trim()) return;

      // Add user message immediately
      const userMsg: ResearchMessage = {
        id: `user-${Date.now()}`,
        session_id: state.sessionId ?? '',
        role: 'user',
        content: query,
        message_type: 'user_query',
        created_at: new Date().toISOString(),
      };

      setState((prev) => ({
        ...prev,
        messages: [...prev.messages, userMsg],
        activityLog: [],
        isStreaming: true,
        currentStage: 'Starting research…',
        sourcesFound: [],
        toolsUsed: [],
        error: null,
      }));

      let finalAnswer = '';
      let finalSources: string[] = [];
      let finalTools: string[] = [];
      let finalSessionId = state.sessionId;
      let answerType = 'synthesis';

      const controller = streamResearch(
        {
          query,
          research_mode: mode,
          company_symbol: companySymbol,
          company_id: companyId,
          financial_year: financialYear,
          session_id: state.sessionId ?? undefined,
        },
        {
          onActivity: (ev: SSEActivityEvent) => {
            setState((prev) => ({
              ...prev,
              currentStage: ev.message,
              activityLog: [
                ...prev.activityLog,
                {
                  stage: ev.stage,
                  message: ev.message,
                  tool: ev.tool,
                  status: ev.status as AgentActivityEvent['status'],
                  is_live: ev.is_live,
                  elapsed_ms: ev.elapsed_ms,
                  timestamp: ev.timestamp,
                },
              ],
            }));
          },

          onSources: (ev: SSESourcesEvent) => {
            finalSources = ev.sources ?? [];
            finalTools = ev.tools_used ?? [];
            setState((prev) => ({
              ...prev,
              sourcesFound: ev.sources ?? [],
              toolsUsed: ev.tools_used ?? [],
            }));
          },

          onAnswer: (ev: SSEAnswerEvent) => {
            finalAnswer = ev.content;
            answerType = ev.answer_type;
            finalSessionId = ev.session_id ?? finalSessionId;
          },

          onDone: (ev) => {
            const assistantMsg: ResearchMessage = {
              id: `asst-${Date.now()}`,
              session_id: finalSessionId ?? '',
              role: 'assistant',
              content: finalAnswer || 'No answer was generated.',
              message_type: answerType,
              tools_used: finalTools,
              sources: finalSources,
              research_mode: mode,
              answer_type: answerType,
              activity_log: [],
              created_at: new Date().toISOString(),
            };

            setState((prev) => ({
              ...prev,
              messages: [...prev.messages, assistantMsg],
              isStreaming: false,
              currentStage: '',
              sessionId: finalSessionId,
            }));
          },

          onError: (err: string) => {
            setState((prev) => ({
              ...prev,
              isStreaming: false,
              currentStage: '',
              error: err,
              messages: [
                ...prev.messages,
                {
                  id: `err-${Date.now()}`,
                  session_id: prev.sessionId ?? '',
                  role: 'assistant',
                  content: `⚠️ Research error: ${err}`,
                  message_type: 'error',
                  created_at: new Date().toISOString(),
                },
              ],
            }));
          },

          onPersisted: (data) => {
            setState((prev) => ({
              ...prev,
              sessionId: data.session_id,
            }));
          },
        },
      );

      abortRef.current = controller;
    },
    [state.sessionId],
  );

  const cancel = useCallback(() => {
    abortRef.current?.abort();
    setState((prev) => ({
      ...prev,
      isStreaming: false,
      currentStage: '',
    }));
  }, []);

  const startNew = useCallback(() => {
    abortRef.current?.abort();
    setState({
      messages: [],
      activityLog: [],
      isStreaming: false,
      currentStage: '',
      sourcesFound: [],
      toolsUsed: [],
      error: null,
      sessionId: null,
    });
  }, []);

  const loadSession = useCallback((messages: ResearchMessage[], sessionId: string) => {
    setState((prev) => ({
      ...prev,
      messages,
      sessionId,
      activityLog: [],
      isStreaming: false,
      currentStage: '',
    }));
  }, []);

  return { state, submit, cancel, startNew, loadSession };
}
