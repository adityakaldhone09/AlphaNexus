/**
 * AgentActivity — Shows live research execution steps in a clean timeline.
 * Rendered while the agent is running and preserved after completion.
 */

import React from 'react';
import { motion, AnimatePresence } from 'motion/react';
import {
  Loader2, CheckCircle2, XCircle, Database, Globe,
  FileText, Calculator, Newspaper, Zap, Search,
} from 'lucide-react';
import type { AgentActivityEvent } from '../types/research.types';

interface AgentActivityProps {
  events: AgentActivityEvent[];
  currentStage: string;
  isStreaming: boolean;
}

const TOOL_ICONS: Record<string, React.ReactNode> = {
  get_company_profile_db:   <Database className="w-3 h-3" />,
  get_company_live_data:    <Globe className="w-3 h-3" />,
  get_company_announcements: <FileText className="w-3 h-3" />,
  get_corporate_actions:    <Zap className="w-3 h-3" />,
  get_market_news:          <Newspaper className="w-3 h-3" />,
  retrieve_company_documents: <Search className="w-3 h-3" />,
  calculate_financial_ratios: <Calculator className="w-3 h-3" />,
};

const STAGE_LABELS: Record<string, string> = {
  plan_created:          '📋 Research plan created',
  tool_started:          '🔍 Accessing source',
  tool_completed:        '✓ Data retrieved',
  tool_skipped:          '⤵ Source skipped',
  synthesis_completed:   '🧠 Synthesizing report',
  synthesis_skipped:     '⚠ Insufficient data',
  validation_completed:  '✅ Response validated',
  started:               '🚀 Research started',
};

export const AgentActivity: React.FC<AgentActivityProps> = ({
  events,
  currentStage,
  isStreaming,
}) => {
  if (events.length === 0 && !isStreaming) return null;

  return (
    <div
      className="rounded-xl p-3 mb-2 text-xs space-y-1.5"
      style={{ background: 'var(--surface-2)', border: '1px solid var(--border)' }}
    >
      <div className="flex items-center gap-2 pb-1.5" style={{ borderBottom: '1px solid var(--border)' }}>
        {isStreaming ? (
          <Loader2 className="w-3.5 h-3.5 animate-spin shrink-0" style={{ color: 'var(--brand)' }} />
        ) : (
          <CheckCircle2 className="w-3.5 h-3.5 shrink-0" style={{ color: 'var(--positive-text)' }} />
        )}
        <span className="font-bold uppercase tracking-wider text-[10px]" style={{ color: 'var(--text-3)' }}>
          {isStreaming ? 'Research in progress' : 'Research completed'}
        </span>
        {isStreaming && currentStage && (
          <span className="text-[10px] truncate" style={{ color: 'var(--text-4)' }}>
            — {currentStage}
          </span>
        )}
      </div>

      <div className="space-y-1 max-h-32 overflow-y-auto">
        <AnimatePresence initial={false}>
          {events.map((ev, idx) => {
            const toolIcon = ev.tool ? TOOL_ICONS[ev.tool] : null;
            const label = STAGE_LABELS[ev.stage] || ev.message;
            const isOk = ev.status !== 'unavailable' && ev.status !== 'skipped';
            const isLive = ev.is_live;

            return (
              <motion.div
                key={idx}
                className="flex items-center gap-2"
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.2 }}
              >
                {/* Stage icon */}
                <span style={{ color: isOk ? 'var(--brand)' : 'var(--text-4)' }}>
                  {toolIcon || <span className="w-3 h-3 inline-block" />}
                </span>

                <span className="flex-1 truncate" style={{ color: 'var(--text-2)' }}>
                  {label}
                </span>

                {ev.elapsed_ms && (
                  <span className="font-mono shrink-0" style={{ color: 'var(--text-4)' }}>
                    {ev.elapsed_ms}ms
                  </span>
                )}

                {ev.is_live === true && (
                  <span className="badge badge-lime shrink-0 text-[8px]">LIVE</span>
                )}
                {ev.status === 'unavailable' && (
                  <XCircle className="w-3 h-3 shrink-0" style={{ color: 'var(--negative-text)' }} />
                )}
              </motion.div>
            );
          })}
        </AnimatePresence>

        {/* Current stage pulse */}
        {isStreaming && (
          <motion.div
            className="flex items-center gap-2"
            animate={{ opacity: [0.4, 1, 0.4] }}
            transition={{ duration: 1.4, repeat: Infinity }}
          >
            <Loader2 className="w-3 h-3 animate-spin" style={{ color: 'var(--brand)' }} />
            <span style={{ color: 'var(--text-3)' }}>{currentStage || 'Working…'}</span>
          </motion.div>
        )}
      </div>
    </div>
  );
};
