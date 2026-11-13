/**
 * AlphaNexus Intelligence Agent — Research Workspace
 * ====================================================
 * Full agentic financial research workspace with:
 *  - 6 research modes (Quick, Deep, Live, Document, Comparative, Event)
 *  - SSE streaming with real-time agent activity display
 *  - Session history (sidebar)
 *  - Company selector
 *  - Source citations and answer metadata
 *  - Agent health status panel
 */

import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Bot, Sparkles, TrendingUp, Newspaper, FileText, BarChart2 } from 'lucide-react';

import { useResearch } from '../features/research/hooks/useResearch';
import { ResearchSidebar } from '../features/research/components/ResearchSidebar';
import { ResearchComposer } from '../features/research/components/ResearchComposer';
import { ResearchMessage as ResearchMessageCard } from '../features/research/components/ResearchMessage';
import { AgentActivity } from '../features/research/components/AgentActivity';
import { listAgentSessions, getAgentStatus } from '../features/research/services/research.service';
import type {
  ResearchMode,
  ResearchSession,
  ResearchMessage,
  AgentStatus,
} from '../features/research/types/research.types';
import { api } from '../services/api';
import { useCompanyStore } from '../stores/companyStore';
import type { Company } from '../types';

// Sample prompts for the empty state
const SAMPLE_PROMPTS: { label: string; query: string; mode: ResearchMode; icon: React.ReactNode }[] = [
  {
    label: 'Company Profile',
    query: 'What is Reliance Industries current profile, key financial metrics, and recent performance?',
    mode: 'quick',
    icon: <BarChart2 className="w-4 h-4" />,
  },
  {
    label: 'Deep Analysis',
    query: 'Analyze TCS financial performance over FY22–FY24: revenue growth, margin trends, and strategic outlook.',
    mode: 'deep',
    icon: <TrendingUp className="w-4 h-4" />,
  },
  {
    label: 'Latest News',
    query: 'What are the latest exchange announcements and corporate actions for HDFCBANK?',
    mode: 'live',
    icon: <Newspaper className="w-4 h-4" />,
  },
  {
    label: 'Document Research',
    query: 'Summarize key risks and management commentary from the uploaded annual report.',
    mode: 'document',
    icon: <FileText className="w-4 h-4" />,
  },
];

export const AIResearchPage: React.FC = () => {
  const { state, submit, cancel, startNew, loadSession } = useResearch();
  const [sessions, setSessions] = useState<ResearchSession[]>([]);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [agentStatus, setAgentStatus] = useState<AgentStatus | null>(null);
  const { selectedCompany: storeCompany } = useCompanyStore();
  const [mode, setMode] = useState<ResearchMode>('quick');
  const [query, setQuery] = useState('');
  const [companyId, setCompanyId] = useState(storeCompany?.id || '');
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (storeCompany?.id && !companyId) {
      setCompanyId(storeCompany.id);
    }
  }, [storeCompany]);

  // Load initial data
  useEffect(() => {
    Promise.all([
      listAgentSessions(25),
      api.getCompanies(),
      getAgentStatus(),
    ]).then(([sess, comps, status]) => {
      setSessions(sess);
      setCompanies(comps);
      setAgentStatus(status);
    }).catch(() => {/* ignore */});
  }, []);

  // Auto-scroll
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [state.messages, state.activityLog.length]);

  const handleSubmit = () => {
    if (!query.trim() || state.isStreaming) return;
    const selectedCompany = companies.find((c) => c.id === companyId) || storeCompany;
    submit(query, mode, selectedCompany?.symbol, companyId || undefined);
    setQuery('');
  };

  const handleNewResearch = () => {
    startNew();
    setQuery('');
  };

  const handleSessionSelect = (session: ResearchSession, messages: any[]) => {
    // Map API message format to our internal format
    const mapped: ResearchMessage[] = messages.map((m: any) => ({
      id: m.id,
      session_id: m.session_id,
      role: m.role,
      content: m.content,
      message_type: m.message_type,
      tokens_used: m.tokens_used,
      citations: m.citations ?? [],
      created_at: m.created_at,
    }));
    loadSession(mapped, session.id);
  };

  const handleDeleteSession = (sessionId: string) => {
    setSessions((prev) => prev.filter((s) => s.id !== sessionId));
    if (state.sessionId === sessionId) handleNewResearch();
  };

  const handleSamplePrompt = (prompt: typeof SAMPLE_PROMPTS[0]) => {
    setMode(prompt.mode);
    setQuery(prompt.query);
  };

  const selectedCompany = companies.find((c) => c.id === companyId) || storeCompany;

  return (
    <div
      className="page-container py-4"
      style={{ height: 'calc(100vh - 80px)', display: 'flex', flexDirection: 'column', gap: 16 }}
    >
      {/* Page header */}
      <motion.div
        className="flex items-center gap-3 shrink-0"
        initial={{ opacity: 0, y: -6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
      >
        <div
          className="w-9 h-9 rounded-xl flex items-center justify-center shrink-0"
          style={{ background: 'var(--brand-muted)', border: '1px solid var(--border-brand)' }}
        >
          <Bot className="w-5 h-5" style={{ color: 'var(--brand)' }} />
        </div>
        <div>
          <h1
            className="text-xl font-black tracking-tight leading-none"
            style={{ color: 'var(--text-1)', letterSpacing: '-0.02em' }}
          >
            AlphaNexus Intelligence Agent
          </h1>
          <p className="text-xs mt-0.5" style={{ color: 'var(--text-3)' }}>
            Your AI-powered financial research and intelligence workspace
            {selectedCompany && (
              <> · <span className="font-bold" style={{ color: 'var(--brand)' }}>{selectedCompany.symbol}</span></>
            )}
          </p>
        </div>

        <div className="ml-auto flex items-center gap-2">
          {agentStatus && (
            <div className="hidden lg:flex items-center gap-1.5 text-xs font-mono">
              <span
                className="w-2 h-2 rounded-full"
                style={{ background: agentStatus.status === 'ready' ? 'var(--positive-text)' : 'var(--warning)' }}
              />
              <span style={{ color: 'var(--text-3)' }}>
                {agentStatus.llm_provider ? `${agentStatus.llm_provider} · ` : ''}
                {agentStatus.tools_available.length} tools
              </span>
            </div>
          )}
        </div>
      </motion.div>

      {/* Main workspace: sidebar + chat */}
      <div className="flex gap-4 flex-1 min-h-0">
        {/* Sidebar */}
        <ResearchSidebar
          sessions={sessions}
          activeSessions={state.sessionId}
          agentStatus={agentStatus}
          onNewResearch={handleNewResearch}
          onSelectSession={handleSessionSelect}
          onDeleteSession={handleDeleteSession}
        />

        {/* Chat area */}
        <div className="flex-1 flex flex-col min-h-0 gap-3">
          {/* Messages */}
          <div
            className="flex-1 overflow-y-auto space-y-5 px-1"
            style={{ minHeight: 0 }}
          >
            {/* Empty state */}
            {state.messages.length === 0 && !state.isStreaming && (
              <motion.div
                className="flex flex-col items-center justify-center h-full text-center space-y-6 py-8"
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4 }}
              >
                <div
                  className="w-16 h-16 rounded-2xl flex items-center justify-center"
                  style={{ background: 'var(--brand-muted)', border: '1px solid var(--border-brand)' }}
                >
                  <Sparkles className="w-8 h-8" style={{ color: 'var(--brand)' }} />
                </div>
                <div className="max-w-md">
                  <h2 className="text-xl font-black mb-2" style={{ color: 'var(--text-1)' }}>
                    Start Your Research
                  </h2>
                  <p className="text-sm leading-relaxed" style={{ color: 'var(--text-3)' }}>
                    Ask anything about Indian equities — financial performance, corporate announcements,
                    management commentary, or competitive analysis. Every answer is grounded in
                    official sources with real-time data where available.
                  </p>
                </div>

                {/* Sample prompts */}
                <div className="grid sm:grid-cols-2 gap-2 w-full max-w-2xl text-left">
                  {SAMPLE_PROMPTS.map((p) => (
                    <button
                      key={p.label}
                      onClick={() => handleSamplePrompt(p)}
                      className="p-3.5 rounded-xl text-left transition-all group"
                      style={{
                        background: 'var(--surface-1)',
                        border: '1px solid var(--border)',
                      }}
                    >
                      <div className="flex items-center gap-2 mb-1.5">
                        <span style={{ color: 'var(--brand)' }}>{p.icon}</span>
                        <span className="text-xs font-bold" style={{ color: 'var(--brand)' }}>{p.label}</span>
                        <span className="badge badge-muted ml-auto text-[9px]">{p.mode}</span>
                      </div>
                      <p className="text-xs leading-snug line-clamp-2" style={{ color: 'var(--text-3)' }}>
                        {p.query}
                      </p>
                    </button>
                  ))}
                </div>
              </motion.div>
            )}

            {/* Messages list */}
            {state.messages.map((msg, idx) => (
              <ResearchMessageCard
                key={msg.id}
                message={msg}
                isLatest={idx === state.messages.length - 1}
              />
            ))}

            {/* Live activity stream (while streaming) */}
            {state.isStreaming && (
              <AgentActivity
                events={state.activityLog}
                currentStage={state.currentStage}
                isStreaming={state.isStreaming}
              />
            )}

            <div ref={bottomRef} />
          </div>

          {/* Composer */}
          <div className="shrink-0">
            <ResearchComposer
              query={query}
              onQueryChange={setQuery}
              mode={mode}
              onModeChange={setMode}
              companyId={companyId}
              onCompanyChange={setCompanyId}
              companies={companies}
              isStreaming={state.isStreaming}
              onSubmit={handleSubmit}
              onCancel={cancel}
            />

            <div className="mt-1.5 flex items-center justify-between px-1">
              <p className="text-[10px]" style={{ color: 'var(--text-4)' }}>
                Enter to research · Shift+Enter for new line · Research is grounded in official filings and live data
              </p>
              {state.sourcesFound.length > 0 && (
                <div className="flex gap-1.5">
                  {state.sourcesFound.slice(0, 3).map((s, i) => (
                    <span key={i} className="badge badge-muted text-[9px]">{s}</span>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
