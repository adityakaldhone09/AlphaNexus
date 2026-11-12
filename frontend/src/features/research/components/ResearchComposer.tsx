/**
 * ResearchComposer — Premium input area for the research workspace.
 * Includes mode selector, company selector, and the query textarea.
 */

import React, { useRef, useEffect } from 'react';
import { motion } from 'motion/react';
import { Send, StopCircle, ChevronDown } from 'lucide-react';
import { RESEARCH_MODES, type ResearchMode } from '../types/research.types';
import type { Company } from '../../../types';

interface ResearchComposerProps {
  query: string;
  onQueryChange: (q: string) => void;
  mode: ResearchMode;
  onModeChange: (m: ResearchMode) => void;
  companyId: string;
  onCompanyChange: (id: string) => void;
  companies: Company[];
  isStreaming: boolean;
  onSubmit: () => void;
  onCancel: () => void;
}

export const ResearchComposer: React.FC<ResearchComposerProps> = ({
  query,
  onQueryChange,
  mode,
  onModeChange,
  companyId,
  onCompanyChange,
  companies,
  isStreaming,
  onSubmit,
  onCancel,
}) => {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const selectedMode = RESEARCH_MODES.find((m) => m.id === mode)!;

  // Auto-resize textarea
  useEffect(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = 'auto';
    ta.style.height = Math.min(ta.scrollHeight, 160) + 'px';
  }, [query]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (!isStreaming && query.trim()) onSubmit();
    }
  };

  return (
    <div
      className="rounded-2xl overflow-hidden"
      style={{ background: 'var(--surface-1)', border: '1px solid var(--border-strong)' }}
    >
      {/* Mode + Company selectors */}
      <div
        className="flex flex-wrap items-center gap-2 px-4 py-2.5"
        style={{ borderBottom: '1px solid var(--border)', background: 'var(--surface-2)' }}
      >
        {/* Research Mode */}
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] font-bold uppercase tracking-wider" style={{ color: 'var(--text-4)' }}>Mode</span>
          <div className="relative">
            <select
              value={mode}
              onChange={(e) => onModeChange(e.target.value as ResearchMode)}
              className="appearance-none input text-xs pl-2.5 pr-7 py-1 font-semibold"
              style={{ color: 'var(--brand)', background: 'var(--brand-muted)', border: '1px solid var(--border-brand)' }}
            >
              {RESEARCH_MODES.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.icon} {m.label}
                </option>
              ))}
            </select>
            <ChevronDown className="absolute right-1.5 top-1/2 -translate-y-1/2 w-3 h-3 pointer-events-none" style={{ color: 'var(--brand)' }} />
          </div>
        </div>

        {/* Est. time */}
        <span className="text-[10px] font-mono" style={{ color: 'var(--text-4)' }}>
          ~{selectedMode.estimatedTime}
        </span>

        <div className="ml-auto flex items-center gap-2">
          {/* Company selector */}
          <span className="text-[10px] font-bold uppercase tracking-wider hidden sm:inline" style={{ color: 'var(--text-4)' }}>
            Company
          </span>
          <div className="relative">
            <select
              value={companyId}
              onChange={(e) => onCompanyChange(e.target.value)}
              className="appearance-none input text-xs pl-2.5 pr-7 py-1"
            >
              <option value="">All companies</option>
              {companies.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.symbol} — {c.name}
                </option>
              ))}
            </select>
            <ChevronDown className="absolute right-1.5 top-1/2 -translate-y-1/2 w-3 h-3 pointer-events-none" style={{ color: 'var(--text-3)' }} />
          </div>
        </div>
      </div>

      {/* Textarea */}
      <div className="px-4 py-3">
        <textarea
          ref={textareaRef}
          value={query}
          onChange={(e) => onQueryChange(e.target.value)}
          onKeyDown={handleKeyDown}
          rows={2}
          placeholder={`${selectedMode.icon} ${selectedMode.description}…\n\nAsk about financials, announcements, management commentary, or competitive positioning. Press Enter to research, Shift+Enter for a new line.`}
          disabled={isStreaming}
          className="w-full bg-transparent text-sm resize-none focus:outline-none leading-relaxed placeholder:text-[var(--text-4)]"
          style={{ color: 'var(--text-1)', minHeight: 60 }}
        />
      </div>

      {/* Actions */}
      <div
        className="flex items-center justify-between px-4 py-2.5"
        style={{ borderTop: '1px solid var(--border)' }}
      >
        {/* Tool hints */}
        <div className="flex gap-1.5 flex-wrap">
          {selectedMode.toolsUsed.map((t) => (
            <span key={t} className="badge badge-muted text-[9px]">{t}</span>
          ))}
        </div>

        {/* Submit / Cancel */}
        <div className="flex items-center gap-2 shrink-0">
          {isStreaming ? (
            <motion.button
              whileTap={{ scale: 0.96 }}
              onClick={onCancel}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold"
              style={{ background: 'rgba(255,100,110,.12)', color: 'var(--negative-text)', border: '1px solid rgba(255,100,110,.2)' }}
            >
              <StopCircle className="w-3.5 h-3.5" />
              Stop
            </motion.button>
          ) : (
            <motion.button
              whileTap={{ scale: 0.96 }}
              whileHover={{ scale: 1.02 }}
              onClick={onSubmit}
              disabled={!query.trim()}
              className="btn-brand flex items-center gap-1.5 px-4 py-1.5 text-xs font-bold disabled:opacity-40"
            >
              <Send className="w-3.5 h-3.5" />
              Research
            </motion.button>
          )}
        </div>
      </div>
    </div>
  );
};
