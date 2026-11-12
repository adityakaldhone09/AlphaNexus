/**
 * ResearchSidebar — session history, new research button, and status panel.
 */

import React from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { Plus, Trash2, MessageSquare, Circle } from 'lucide-react';
import type { ResearchSession, AgentStatus } from '../types/research.types';
import { deleteAgentSession, getAgentSession } from '../services/research.service';

interface ResearchSidebarProps {
  sessions: ResearchSession[];
  activeSessions: string | null;
  agentStatus: AgentStatus | null;
  onNewResearch: () => void;
  onSelectSession: (session: ResearchSession, messages: any[]) => void;
  onDeleteSession: (sessionId: string) => void;
}

export const ResearchSidebar: React.FC<ResearchSidebarProps> = ({
  sessions,
  activeSessions,
  agentStatus,
  onNewResearch,
  onSelectSession,
  onDeleteSession,
}) => {
  const handleSelect = async (session: ResearchSession) => {
    try {
      const full = await getAgentSession(session.id);
      onSelectSession(full, full.messages ?? []);
    } catch {
      onSelectSession(session, []);
    }
  };

  const handleDelete = async (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation();
    if (!confirm('Delete this research session?')) return;
    try {
      await deleteAgentSession(sessionId);
      onDeleteSession(sessionId);
    } catch {/* ignore */}
  };

  return (
    <aside
      className="hidden md:flex flex-col h-full rounded-2xl overflow-hidden shrink-0"
      style={{
        width: 240,
        background: 'var(--surface-1)',
        border: '1px solid var(--border)',
      }}
    >
      {/* Header */}
      <div className="p-3" style={{ borderBottom: '1px solid var(--border)' }}>
        <button
          onClick={onNewResearch}
          className="btn-brand w-full flex items-center justify-center gap-2 px-3 py-2 text-xs font-bold rounded-xl"
        >
          <Plus className="w-3.5 h-3.5" />
          New Research
        </button>
      </div>

      {/* Agent Status */}
      {agentStatus && (
        <div
          className="px-3 py-2 mx-2 my-2 rounded-xl text-xs"
          style={{ background: 'var(--surface-2)', border: '1px solid var(--border)' }}
        >
          <div className="flex items-center gap-1.5 mb-1">
            <Circle
              className="w-2 h-2 fill-current shrink-0"
              style={{ color: agentStatus.status === 'ready' ? 'var(--positive-text)' : 'var(--warning)' }}
            />
            <span className="font-bold uppercase tracking-wider text-[9px]" style={{ color: 'var(--text-4)' }}>
              Agent {agentStatus.status}
            </span>
          </div>
          <div className="space-y-0.5">
            <div className="flex items-center justify-between">
              <span style={{ color: 'var(--text-4)' }}>LLM</span>
              <span className="font-semibold" style={{ color: agentStatus.llm_configured ? 'var(--positive-text)' : 'var(--negative-text)' }}>
                {agentStatus.llm_provider || 'None'}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span style={{ color: 'var(--text-4)' }}>IndianAPI</span>
              <span className="font-semibold" style={{ color: agentStatus.indianapi_configured ? 'var(--positive-text)' : 'var(--text-4)' }}>
                {agentStatus.indianapi_configured ? '✓' : '—'}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span style={{ color: 'var(--text-4)' }}>RAG Engine</span>
              <span className="font-semibold" style={{ color: agentStatus.rag_available ? 'var(--positive-text)' : 'var(--text-4)' }}>
                {agentStatus.rag_available ? '✓' : '—'}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Sessions */}
      <div className="flex-1 overflow-y-auto">
        <div className="px-3 py-2 text-[10px] font-bold uppercase tracking-wider" style={{ color: 'var(--text-4)' }}>
          Recent Research
        </div>

        {sessions.length === 0 ? (
          <div className="px-3 pb-4 text-xs text-center" style={{ color: 'var(--text-4)' }}>
            No sessions yet.<br />Start your first research above.
          </div>
        ) : (
          <div className="space-y-0.5 px-1.5 pb-2">
            <AnimatePresence>
              {sessions.map((s) => (
                <motion.button
                  key={s.id}
                  onClick={() => handleSelect(s)}
                  className="w-full text-left px-2.5 py-2.5 rounded-xl transition-colors group relative"
                  style={{
                    background: activeSessions === s.id ? 'var(--brand-muted)' : 'transparent',
                    border: `1px solid ${activeSessions === s.id ? 'var(--border-brand)' : 'transparent'}`,
                  }}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -8 }}
                  transition={{ duration: 0.15 }}
                >
                  <div className="flex items-start gap-2">
                    <MessageSquare
                      className="w-3.5 h-3.5 mt-0.5 shrink-0"
                      style={{ color: activeSessions === s.id ? 'var(--brand)' : 'var(--text-4)' }}
                    />
                    <div className="flex-1 min-w-0">
                      <div
                        className="text-xs font-semibold truncate"
                        style={{ color: activeSessions === s.id ? 'var(--brand)' : 'var(--text-2)' }}
                      >
                        {s.title || 'Research Session'}
                      </div>
                      <div className="text-[10px] font-mono mt-0.5" style={{ color: 'var(--text-4)' }}>
                        {new Date(s.updated_at).toLocaleDateString('en-IN', {
                          month: 'short',
                          day: 'numeric',
                        })}
                      </div>
                    </div>
                    <button
                      onClick={(e) => handleDelete(e, s.id)}
                      className="opacity-0 group-hover:opacity-100 p-0.5 rounded transition-opacity"
                      style={{ color: 'var(--text-4)' }}
                    >
                      <Trash2 className="w-3 h-3" />
                    </button>
                  </div>
                </motion.button>
              ))}
            </AnimatePresence>
          </div>
        )}
      </div>
    </aside>
  );
};
