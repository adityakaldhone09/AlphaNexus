/**
 * ResearchMessage — renders a single user or assistant message.
 * Assistant messages include source badges, citations, and copy action.
 */

import React, { useState } from 'react';
import { motion } from 'motion/react';
import {
  Bot, User, Copy, Check, ExternalLink,
  FileText, Globe, Database, Newspaper,
} from 'lucide-react';
import type { ResearchMessage as IResearchMessage } from '../types/research.types';
import { AgentActivity } from './AgentActivity';

interface ResearchMessageProps {
  message: IResearchMessage;
  isLatest?: boolean;
}

const SOURCE_ICONS: Record<string, React.ReactNode> = {
  'AlphaNexus Database':          <Database className="w-3 h-3" />,
  'IndianAPI (Live Market Data)': <Globe className="w-3 h-3" />,
  'IndianAPI (Exchange Announcements)': <FileText className="w-3 h-3" />,
  'IndianAPI + Marketaux (News)': <Newspaper className="w-3 h-3" />,
  'AlphaNexus RAG (Indexed Filings)': <FileText className="w-3 h-3" />,
};

function formatMarkdown(text: string): string {
  // Simple markdown-to-HTML for the most common patterns
  return text
    .replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/^### (.+)$/gm, '<h4 class="font-bold text-sm mt-3 mb-1">$1</h4>')
    .replace(/^## (.+)$/gm, '<h3 class="font-bold text-base mt-4 mb-1.5">$1</h3>')
    .replace(/^# (.+)$/gm, '<h2 class="font-bold text-lg mt-4 mb-2">$1</h2>')
    .replace(/^- (.+)$/gm, '<li class="ml-4 list-disc">$1</li>')
    .replace(/^(\d+)\. (.+)$/gm, '<li class="ml-4 list-decimal"><span class="font-semibold">$1.</span> $2</li>')
    .replace(/`(.+?)`/g, '<code class="font-mono text-[11px] px-1 py-0.5 rounded" style="background:var(--surface-3);color:var(--lime)">$1</code>')
    .replace(/\n\n/g, '</p><p class="mt-2">')
    .replace(/^/, '<p>')
    .replace(/$/, '</p>');
}

export const ResearchMessage: React.FC<ResearchMessageProps> = ({
  message,
  isLatest = false,
}) => {
  const [copied, setCopied] = useState(false);
  const isUser = message.role === 'user';

  const handleCopy = () => {
    navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (isUser) {
    return (
      <motion.div
        className="flex justify-end"
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.25 }}
      >
        <div
          className="max-w-[75%] rounded-2xl rounded-tr-sm px-4 py-3 text-sm"
          style={{ background: 'var(--brand)', color: '#fff' }}
        >
          <div className="flex items-center gap-2 mb-1.5">
            <User className="w-3.5 h-3.5 shrink-0 opacity-70" />
            <span className="text-[10px] font-bold uppercase tracking-wider opacity-70">Your question</span>
          </div>
          <p className="leading-relaxed">{message.content}</p>
        </div>
      </motion.div>
    );
  }

  // Assistant message
  return (
    <motion.div
      className="space-y-2"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
    >
      {/* Activity log for this message */}
      {message.activity_log && message.activity_log.length > 0 && (
        <AgentActivity
          events={message.activity_log}
          currentStage=""
          isStreaming={false}
        />
      )}

      {/* Answer bubble */}
      <div
        className="rounded-2xl rounded-tl-sm overflow-hidden"
        style={{ background: 'var(--surface-1)', border: '1px solid var(--border)' }}
      >
        {/* Header */}
        <div
          className="flex items-center justify-between px-4 py-2.5"
          style={{ borderBottom: '1px solid var(--border)', background: 'var(--surface-2)' }}
        >
          <div className="flex items-center gap-2">
            <div
              className="w-6 h-6 rounded-lg flex items-center justify-center shrink-0"
              style={{ background: 'var(--brand-muted)' }}
            >
              <Bot className="w-3.5 h-3.5" style={{ color: 'var(--brand)' }} />
            </div>
            <div>
              <span className="text-xs font-bold" style={{ color: 'var(--text-1)' }}>
                AlphaNexus Intelligence Agent
              </span>
              {message.research_mode && (
                <span className="ml-2 badge badge-brand text-[9px]">
                  {message.research_mode}
                </span>
              )}
            </div>
          </div>

          <div className="flex items-center gap-2">
            {message.answer_type === 'fact_grounded' && (
              <span className="badge badge-lime">Fact-Grounded</span>
            )}
            {message.answer_type === 'insufficient_data' && (
              <span className="badge badge-neg">Insufficient Data</span>
            )}
            <button
              onClick={handleCopy}
              className="p-1 rounded transition-opacity hover:opacity-70"
              style={{ color: 'var(--text-4)' }}
              title="Copy answer"
            >
              {copied
                ? <Check className="w-3.5 h-3.5" style={{ color: 'var(--positive-text)' }} />
                : <Copy className="w-3.5 h-3.5" />}
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="px-5 py-4">
          <div
            className="text-sm leading-relaxed prose-financial"
            style={{ color: 'var(--text-1)' }}
            dangerouslySetInnerHTML={{ __html: formatMarkdown(message.content) }}
          />
        </div>

        {/* Sources used */}
        {message.sources && message.sources.length > 0 && (
          <div
            className="px-4 py-2.5 flex flex-wrap gap-1.5"
            style={{ borderTop: '1px solid var(--border)', background: 'var(--surface-2)' }}
          >
            <span className="text-[10px] font-bold uppercase tracking-wider self-center mr-1" style={{ color: 'var(--text-4)' }}>
              Sources:
            </span>
            {message.sources.map((s, i) => (
              <span key={i} className="flex items-center gap-1 badge badge-muted">
                {SOURCE_ICONS[s] || <Globe className="w-3 h-3" />}
                {s}
              </span>
            ))}
          </div>
        )}

        {/* Citations */}
        {message.citations && message.citations.length > 0 && (
          <div
            className="px-4 py-3 space-y-2"
            style={{ borderTop: '1px solid var(--border)' }}
          >
            <div className="text-[10px] font-bold uppercase tracking-wider" style={{ color: 'var(--text-4)' }}>
              Document Citations ({message.citations.length})
            </div>
            {message.citations.map((c, i) => (
              <div
                key={i}
                className="rounded-lg p-2.5 text-xs space-y-1"
                style={{ background: 'var(--surface-2)', border: '1px solid var(--border)' }}
              >
                <div className="flex items-center justify-between">
                  <span className="font-semibold" style={{ color: 'var(--brand)' }}>
                    [{i + 1}] {c.document_title || 'Filing'}{c.page_number ? ` · Page ${c.page_number}` : ''}
                    {c.section ? ` · ${c.section}` : ''}
                  </span>
                  <div className="flex items-center gap-2">
                    <span className="font-mono" style={{ color: 'var(--text-4)' }}>
                      {(c.confidence_score * 100).toFixed(0)}%
                    </span>
                    {c.source_url && (
                      <a
                        href={c.source_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{ color: 'var(--brand)' }}
                      >
                        <ExternalLink className="w-3 h-3" />
                      </a>
                    )}
                  </div>
                </div>
                <p className="italic leading-relaxed" style={{ color: 'var(--text-3)' }}>
                  "{c.excerpt}"
                </p>
              </div>
            ))}
          </div>
        )}

        {/* Timing */}
        {(message.started_at || message.completed_at) && (
          <div
            className="px-4 py-1.5 text-[10px] font-mono flex items-center gap-3"
            style={{ borderTop: '1px solid var(--border)', color: 'var(--text-4)' }}
          >
            {message.started_at && (
              <span>Started: {new Date(message.started_at).toLocaleTimeString()}</span>
            )}
            {message.completed_at && (
              <span>Completed: {new Date(message.completed_at).toLocaleTimeString()}</span>
            )}
            {message.tools_used && message.tools_used.length > 0 && (
              <span>{[...new Set(message.tools_used)].length} tools used</span>
            )}
          </div>
        )}
      </div>
    </motion.div>
  );
};
