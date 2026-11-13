import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import {
  Upload, FileText, Trash2, RefreshCw, CheckCircle2,
  XCircle, Loader2, CloudUpload, Building2, AlertCircle,
  Sparkles, Check, ArrowRight, ShieldAlert, Copy, ExternalLink,
  Search, Filter
} from 'lucide-react';
import { ANButton } from '../components/shared/ANButton';
import { api } from '../services/api';
import type { Company, DocumentItem, DocumentAnalysisResult } from '../types';

const DOC_TYPES = [
  'Annual Report', 'Quarterly Result', 'Investor Presentation',
  'Earnings Call Transcript', 'Corporate Announcement', 'Financial Statement',
  'Balance Sheet', 'Profit and Loss Statement', 'Cash Flow Statement',
  'Research Report', 'Shareholding Pattern', 'Other Financial Document',
];

const FY_OPTIONS = ['FY26', 'FY25', 'FY24', 'FY23', 'FY22', 'FY21', 'FY20'];

const StatusBadge: React.FC<{ status: DocumentItem['status'] }> = ({ status }) => {
  const map: Record<DocumentItem['status'], { label: string; color: string; icon: React.ReactNode }> = {
    UPLOADED:   { label: 'Uploaded',   color: 'badge-muted',  icon: <FileText className="w-3 h-3" /> },
    QUEUED:     { label: 'Queued',     color: 'badge-brand',  icon: <Loader2  className="w-3 h-3 animate-spin" /> },
    PROCESSING: { label: 'Processing', color: 'badge-brand',  icon: <Loader2  className="w-3 h-3 animate-spin" /> },
    PROCESSED:  { label: 'Indexed',    color: 'badge-lime',   icon: <CheckCircle2 className="w-3 h-3" /> },
    FAILED:     { label: 'Failed',     color: 'badge-neg',    icon: <XCircle  className="w-3 h-3" /> },
  };
  const { label, color, icon } = map[status] ?? map.UPLOADED;
  return <span className={`badge ${color} gap-1 font-mono text-[11px]`}>{icon}{label}</span>;
};

export const DocumentIntelligencePage: React.FC = () => {
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [loading, setLoading] = useState(true);
  const [dragOver, setDragOver] = useState(false);

  // Intelligent Inspection States
  // 'idle' | 'analyzing' | 'inspected' | 'confirming' | 'rejected' | 'failed'
  const [uploadState, setUploadState] = useState<'idle' | 'analyzing' | 'inspected' | 'confirming' | 'rejected'>('idle');
  const [analysisResult, setAnalysisResult] = useState<DocumentAnalysisResult | null>(null);
  const [analysisStep, setAnalysisStep] = useState<string>('');
  const [statusMessage, setStatusMessage] = useState<string>('');

  // Confirmation editable fields
  const [confirmedCompanyId, setConfirmedCompanyId] = useState<string>('');
  const [confirmedTitle, setConfirmedTitle] = useState<string>('');
  const [confirmedDocType, setConfirmedDocType] = useState<string>('Annual Report');
  const [confirmedFY, setConfirmedFY] = useState<string>('FY24');
  const [isEditingMetadata, setIsEditingMetadata] = useState(false);

  // Filters for indexed documents
  const [searchFilter, setSearchFilter] = useState('');
  const [companyFilter, setCompanyFilter] = useState('');
  const [typeFilter, setTypeFilter] = useState('');

  const fileRef = useRef<HTMLInputElement>(null);

  const loadDocuments = async () => {
    setLoading(true);
    try {
      const [docs, comps] = await Promise.all([
        api.getDocuments(),
        api.getCompanies(),
      ]);
      setDocuments(docs);
      setCompanies(comps);
    } catch (err) {
      console.error('Failed to load documents:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDocuments();
  }, []);

  // Step 1: Handle dropped or selected file
  const handleFileSelect = async (file: File) => {
    setUploadState('analyzing');
    setAnalysisResult(null);
    setStatusMessage('');
    setIsEditingMetadata(false);

    // Simulate inspection step notifications
    setAnalysisStep('Validating format and integrity...');
    const t1 = setTimeout(() => setAnalysisStep('Extracting content and financial tables...'), 600);
    const t2 = setTimeout(() => setAnalysisStep('Classifying corporate & financial relevance...'), 1200);
    const t3 = setTimeout(() => setAnalysisStep('Identifying company, ISIN, and reporting period...'), 1800);

    try {
      const result: DocumentAnalysisResult = await api.analyzeDocument(file);
      clearTimeout(t1);
      clearTimeout(t2);
      clearTimeout(t3);

      setAnalysisResult(result);

      if (!result.is_relevant) {
        setUploadState('rejected');
        return;
      }

      // Pre-fill confirmation parameters
      setConfirmedCompanyId(result.company_id || '');
      setConfirmedTitle(result.detected_title);
      setConfirmedDocType(result.document_type || 'Annual Report');
      setConfirmedFY(result.financial_year || 'FY24');
      setUploadState('inspected');
    } catch (err: any) {
      clearTimeout(t1);
      clearTimeout(t2);
      clearTimeout(t3);
      setUploadState('idle');
      setStatusMessage(`Upload failed: ${err?.response?.data?.detail || err.message}`);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFileSelect(file);
  };

  // Step 2: Confirm and index into pgvector
  const handleConfirmAndProcess = async () => {
    if (!analysisResult) return;
    setUploadState('confirming');

    try {
      const res = await api.confirmDocument({
        temp_file_token: analysisResult.temp_file_token,
        company_id: confirmedCompanyId || undefined,
        company_symbol: analysisResult.company_symbol || undefined,
        title: confirmedTitle || analysisResult.detected_title,
        financial_year: confirmedFY || analysisResult.financial_year,
        document_type: confirmedDocType || analysisResult.document_type,
        quarter: analysisResult.quarter || undefined,
        auto_process: true,
      });

      setStatusMessage(`✓ ${res.message || 'Document indexed successfully!'}`);
      setUploadState('idle');
      setAnalysisResult(null);
      loadDocuments();
    } catch (err: any) {
      setUploadState('inspected');
      setStatusMessage(`Error indexing document: ${err?.response?.data?.detail || err.message}`);
    }
  };

  const handleReprocess = async (id: string) => {
    try {
      await api.reprocessDocument(id);
      loadDocuments();
    } catch (err: any) {
      alert(`Reprocessing failed: ${err?.response?.data?.detail || err.message}`);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Permanently delete this document and its pgvector embeddings?')) return;
    try {
      await api.deleteDocument(id);
      setDocuments((prev) => prev.filter((d) => d.id !== id));
    } catch (err: any) {
      alert(`Deletion failed: ${err?.response?.data?.detail || err.message}`);
    }
  };

  const resetUpload = () => {
    setUploadState('idle');
    setAnalysisResult(null);
    setStatusMessage('');
  };

  // Filtered documents list
  const filteredDocuments = documents.filter((doc) => {
    if (searchFilter && !doc.title.toLowerCase().includes(searchFilter.toLowerCase()) && !doc.filename.toLowerCase().includes(searchFilter.toLowerCase())) {
      return false;
    }
    if (companyFilter && doc.company_id !== companyFilter && doc.company_symbol !== companyFilter) {
      return false;
    }
    if (typeFilter && doc.document_type !== typeFilter) {
      return false;
    }
    return true;
  });

  return (
    <div className="page-container py-8 space-y-7">
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-3xl font-black tracking-tight" style={{ color: 'var(--text-1)', letterSpacing: '-0.02em' }}>
              Intelligent Document <span style={{ color: 'var(--brand)' }}>Ingestion</span>
            </h1>
            <p className="text-sm mt-1" style={{ color: 'var(--text-3)' }}>
              Drop any financial filing. AlphaNexus extracts content, identifies company & ISIN, verifies relevance, and indexes into pgvector.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span className="badge badge-brand text-xs font-mono">
              <Sparkles className="w-3 h-3" /> Auto-Entity Recognition Active
            </span>
          </div>
        </div>
      </motion.div>

      {/* Main Grid: Upload & Inspection Card vs Documents List */}
      <div className="grid lg:grid-cols-12 gap-6">
        {/* Upload & Inspection Panel (5 cols) */}
        <div className="lg:col-span-5 space-y-4">
          <div className="card p-5 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="font-bold text-sm" style={{ color: 'var(--text-1)' }}>
                Upload Financial Document
              </h3>
              {uploadState !== 'idle' && (
                <button onClick={resetUpload} className="text-xs text-slate-400 hover:text-slate-200">
                  Cancel
                </button>
              )}
            </div>

            {/* STATE 1: Empty / Idle Dropzone */}
            {uploadState === 'idle' && (
              <div
                onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                onDragLeave={() => setDragOver(false)}
                onDrop={handleDrop}
                onClick={() => fileRef.current?.click()}
                className="rounded-xl flex flex-col items-center justify-center gap-3 p-8 cursor-pointer transition-all border-2 border-dashed"
                style={{
                  borderColor: dragOver ? 'var(--brand)' : 'var(--border-strong)',
                  background: dragOver ? 'var(--brand-muted)' : 'var(--surface-2)',
                }}
              >
                <div className="w-12 h-12 rounded-full bg-cyan-500/10 text-cyan-500 border border-cyan-500/20 flex items-center justify-center">
                  <CloudUpload className="w-6 h-6" />
                </div>
                <div className="text-center space-y-1">
                  <div className="text-sm font-semibold" style={{ color: 'var(--text-1)' }}>
                    Drop your financial document here
                  </div>
                  <div className="text-xs" style={{ color: 'var(--text-3)' }}>
                    or click to browse files
                  </div>
                  <div className="text-[11px] font-mono text-slate-400 pt-1">
                    PDF · DOCX · XLSX · CSV · TXT (Max 50 MB)
                  </div>
                </div>
                <input
                  ref={fileRef}
                  type="file"
                  accept=".pdf,.docx,.doc,.xlsx,.xls,.csv,.txt"
                  className="hidden"
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) handleFileSelect(f);
                  }}
                />
              </div>
            )}

            {/* STATE 2: Analyzing / Scanning */}
            {uploadState === 'analyzing' && (
              <div className="py-12 px-4 rounded-xl border border-cyan-500/30 bg-cyan-500/5 flex flex-col items-center justify-center text-center space-y-3">
                <Loader2 className="w-8 h-8 animate-spin text-cyan-500" />
                <div className="font-semibold text-sm text-slate-900 dark:text-slate-100">
                  Analyzing Document Intelligence...
                </div>
                <div className="text-xs text-cyan-600 dark:text-cyan-400 font-mono">
                  {analysisStep}
                </div>
              </div>
            )}

            {/* STATE 3: Document Identified & Inspected (Success / Relevant) */}
            {uploadState === 'inspected' && analysisResult && (
              <div className="space-y-4">
                <div className="p-4 rounded-xl border border-emerald-500/30 bg-emerald-500/5 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-bold uppercase tracking-wider text-emerald-600 dark:text-emerald-400 flex items-center gap-1.5 font-mono">
                      <CheckCircle2 className="w-4 h-4" /> Document Detected
                    </span>
                    <span className="badge badge-lime text-[10px] font-mono">
                      {Math.round(analysisResult.company_confidence * 100)}% Confidence
                    </span>
                  </div>

                  {/* Company Details */}
                  <div className="bg-white/70 dark:bg-slate-900/80 p-3 rounded-lg border border-slate-200 dark:border-slate-800 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-[11px] text-slate-400 uppercase font-semibold">Company</span>
                      <span className="font-mono text-xs font-bold text-cyan-500">
                        {analysisResult.company_symbol || 'DETECTED'} · {analysisResult.exchange}
                      </span>
                    </div>
                    <div className="text-sm font-bold text-slate-900 dark:text-slate-100">
                      {analysisResult.company_name || 'Detected Indian Equity'}
                    </div>
                    {analysisResult.isin && (
                      <div className="text-[11px] font-mono text-slate-500">
                        ISIN: {analysisResult.isin}
                      </div>
                    )}
                  </div>

                  {/* Extracted Metadata Grid */}
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div className="bg-slate-100 dark:bg-slate-900/60 p-2.5 rounded-lg border border-slate-200 dark:border-slate-800">
                      <span className="text-[10px] text-slate-400 block uppercase font-semibold">Document Type</span>
                      <span className="font-semibold text-slate-900 dark:text-slate-100">{confirmedDocType}</span>
                    </div>
                    <div className="bg-slate-100 dark:bg-slate-900/60 p-2.5 rounded-lg border border-slate-200 dark:border-slate-800">
                      <span className="text-[10px] text-slate-400 block uppercase font-semibold">Reporting Period</span>
                      <span className="font-semibold font-mono text-slate-900 dark:text-slate-100">{confirmedFY}</span>
                    </div>
                  </div>

                  {/* Duplicate notice if already exists */}
                  {analysisResult.is_duplicate && (
                    <div className="p-2.5 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-600 dark:text-amber-400 text-xs flex items-start gap-2">
                      <Copy className="w-4 h-4 shrink-0 mt-0.5" />
                      <div>
                        <span className="font-bold">Duplicate Document Detected:</span> Exact file has already been indexed. Confirming will re-index chunks.
                      </div>
                    </div>
                  )}

                  {/* Multiple candidates selection if ambiguous */}
                  {analysisResult.candidate_matches && analysisResult.candidate_matches.length > 1 && (
                    <div className="space-y-1.5 pt-1">
                      <label className="text-[11px] font-semibold text-slate-400 uppercase">
                        Select Exact Entity:
                      </label>
                      <select
                        value={confirmedCompanyId}
                        onChange={(e) => setConfirmedCompanyId(e.target.value)}
                        className="input w-full px-2.5 py-1.5 text-xs"
                      >
                        {analysisResult.candidate_matches.map((c) => (
                          <option key={c.symbol} value={c.id || c.symbol}>
                            {c.symbol} — {c.name} ({c.exchange})
                          </option>
                        ))}
                      </select>
                    </div>
                  )}

                  {/* Optional Metadata Editing Toggle */}
                  <div className="pt-1">
                    <button
                      type="button"
                      onClick={() => setIsEditingMetadata(!isEditingMetadata)}
                      className="text-[11px] text-cyan-600 dark:text-cyan-400 hover:underline font-medium"
                    >
                      {isEditingMetadata ? 'Hide adjustments' : 'Need adjustments? Click here to edit'}
                    </button>

                    {isEditingMetadata && (
                      <div className="mt-2 space-y-2 p-3 bg-slate-100 dark:bg-slate-900/90 rounded-lg border border-slate-200 dark:border-slate-800 text-xs">
                        <div>
                          <label className="text-[10px] font-semibold text-slate-400 uppercase">Document Title</label>
                          <input
                            type="text"
                            value={confirmedTitle}
                            onChange={(e) => setConfirmedTitle(e.target.value)}
                            className="input w-full px-2.5 py-1 text-xs mt-1"
                          />
                        </div>
                        <div className="grid grid-cols-2 gap-2">
                          <div>
                            <label className="text-[10px] font-semibold text-slate-400 uppercase">Type</label>
                            <select
                              value={confirmedDocType}
                              onChange={(e) => setConfirmedDocType(e.target.value)}
                              className="input w-full px-2 py-1 text-xs mt-1"
                            >
                              {DOC_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
                            </select>
                          </div>
                          <div>
                            <label className="text-[10px] font-semibold text-slate-400 uppercase">Financial Year</label>
                            <select
                              value={confirmedFY}
                              onChange={(e) => setConfirmedFY(e.target.value)}
                              className="input w-full px-2 py-1 text-xs mt-1"
                            >
                              {FY_OPTIONS.map((f) => <option key={f} value={f}>{f}</option>)}
                            </select>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                </div>

                {/* Confirm Action Button */}
                <ANButton
                  variant="brand"
                  className="w-full justify-center py-2.5 font-bold text-sm shadow-lg shadow-cyan-500/20"
                  icon={<Check className="w-4 h-4" />}
                  onClick={handleConfirmAndProcess}
                >
                  Confirm & Process into Vector Store
                </ANButton>
              </div>
            )}

            {/* STATE 4: Confirming / Indexing into pgvector */}
            {uploadState === 'confirming' && (
              <div className="py-12 px-4 rounded-xl border border-cyan-500/30 bg-cyan-500/5 flex flex-col items-center justify-center text-center space-y-3">
                <Loader2 className="w-8 h-8 animate-spin text-cyan-500" />
                <div className="font-semibold text-sm text-slate-900 dark:text-slate-100">
                  Processing & Indexing into pgvector...
                </div>
                <div className="text-xs text-slate-400 font-mono">
                  Generating BGE 384-d embeddings & configuring hybrid RRF search
                </div>
              </div>
            )}

            {/* STATE 5: Rejected Unrelated Document */}
            {uploadState === 'rejected' && analysisResult && (
              <div className="p-5 rounded-xl border border-rose-500/30 bg-rose-500/5 space-y-4">
                <div className="flex items-center gap-2 text-rose-600 dark:text-rose-400">
                  <ShieldAlert className="w-5 h-5 shrink-0" />
                  <span className="font-black text-xs uppercase tracking-wider font-mono">
                    Document Not Recognized
                  </span>
                </div>
                <div className="text-xs text-slate-700 dark:text-slate-300 leading-relaxed">
                  {analysisResult.rejection_message ||
                    'The uploaded file does not appear to be a company-related financial or corporate document. No document has been indexed into the vector store.'}
                </div>
                {analysisResult.relevance_reasons && analysisResult.relevance_reasons.length > 0 && (
                  <div className="text-[11px] text-slate-400 font-mono bg-slate-100 dark:bg-slate-900/60 p-2 rounded border border-slate-200 dark:border-slate-800">
                    Reason: {analysisResult.relevance_reasons[0]}
                  </div>
                )}
                <div className="pt-2">
                  <ANButton
                    variant="ghost"
                    size="sm"
                    className="w-full justify-center text-xs"
                    onClick={resetUpload}
                  >
                    Upload Another Document
                  </ANButton>
                </div>
              </div>
            )}

            {/* Feedback / Error Message */}
            {statusMessage && (
              <div
                className="text-xs rounded-lg p-3"
                style={{
                  background: statusMessage.startsWith('✓') ? 'var(--lime-muted)' : 'rgba(255,100,110,.08)',
                  color: statusMessage.startsWith('✓') ? 'var(--positive-text)' : 'var(--negative-text)',
                  border: `1px solid ${statusMessage.startsWith('✓') ? 'rgba(212,255,36,.2)' : 'rgba(255,100,110,.2)'}`,
                }}
              >
                {statusMessage}
              </div>
            )}
          </div>
        </div>

        {/* Document List Table Panel (7 cols) */}
        <div className="lg:col-span-7 card overflow-hidden flex flex-col">
          {/* Header & Filters */}
          <div className="p-4 space-y-3" style={{ borderBottom: '1px solid var(--border)' }}>
            <div className="flex items-center justify-between">
              <h3 className="font-bold text-sm" style={{ color: 'var(--text-1)' }}>
                Indexed Financial Documents <span style={{ color: 'var(--text-4)' }}>({filteredDocuments.length})</span>
              </h3>
              <ANButton variant="ghost" size="xs" icon={<RefreshCw className="w-3.5 h-3.5" />} onClick={loadDocuments}>
                Refresh
              </ANButton>
            </div>

            {/* Search and Filter Row */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-xs">
              <div className="relative">
                <Search className="w-3.5 h-3.5 absolute left-2.5 top-2.5 text-slate-400" />
                <input
                  type="text"
                  value={searchFilter}
                  onChange={(e) => setSearchFilter(e.target.value)}
                  placeholder="Search filings..."
                  className="input w-full pl-8 pr-3 py-1.5 text-xs"
                />
              </div>

              <div>
                <select
                  value={companyFilter}
                  onChange={(e) => setCompanyFilter(e.target.value)}
                  className="input w-full px-2.5 py-1.5 text-xs"
                >
                  <option value="">All Companies</option>
                  {companies.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.symbol} — {c.name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <select
                  value={typeFilter}
                  onChange={(e) => setTypeFilter(e.target.value)}
                  className="input w-full px-2.5 py-1.5 text-xs"
                >
                  <option value="">All Document Types</option>
                  {DOC_TYPES.map((t) => (
                    <option key={t} value={t}>{t}</option>
                  ))}
                </select>
              </div>
            </div>
          </div>

          {/* Table Container */}
          <div className="overflow-x-auto flex-1">
            {loading ? (
              <div className="p-6 space-y-3">
                {Array.from({ length: 4 }).map((_, i) => (
                  <div key={i} className="skeleton h-10 rounded-lg w-full" />
                ))}
              </div>
            ) : filteredDocuments.length === 0 ? (
              <div className="py-16 text-center" style={{ color: 'var(--text-4)' }}>
                <FileText className="w-8 h-8 mx-auto mb-2 opacity-30" />
                <div className="text-sm font-medium">No financial documents match the selected filter.</div>
              </div>
            ) : (
              <table className="w-full text-left text-xs">
                <thead style={{ background: 'var(--surface-2)' }}>
                  <tr className="text-[10px] font-bold uppercase tracking-wider" style={{ color: 'var(--text-4)' }}>
                    <th className="px-4 py-2.5">Company</th>
                    <th className="px-4 py-2.5">Document Title</th>
                    <th className="px-4 py-2.5">Type</th>
                    <th className="px-4 py-2.5">FY</th>
                    <th className="px-4 py-2.5">Chunks</th>
                    <th className="px-4 py-2.5">Status</th>
                    <th className="px-4 py-2.5 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredDocuments.map((doc) => (
                    <tr
                      key={doc.id}
                      style={{ borderTop: '1px solid var(--border)' }}
                      className="transition-colors hover:bg-[var(--surface-2)] group"
                    >
                      <td className="px-4 py-3 font-mono font-bold text-cyan-600 dark:text-cyan-400">
                        {doc.company_symbol || 'STOCK'}
                      </td>
                      <td className="px-4 py-3 max-w-[190px]">
                        <div className="font-semibold truncate" style={{ color: 'var(--text-1)' }} title={doc.title}>
                          {doc.title}
                        </div>
                        <div className="text-[10px] truncate" style={{ color: 'var(--text-4)' }}>
                          {doc.filename}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-xs" style={{ color: 'var(--text-3)' }}>
                        {doc.document_type}
                      </td>
                      <td className="px-4 py-3 font-mono text-xs" style={{ color: 'var(--text-3)' }}>
                        {doc.financial_year || '—'}
                      </td>
                      <td className="px-4 py-3 font-tabular font-semibold" style={{ color: 'var(--lime)' }}>
                        {doc.total_chunks}
                      </td>
                      <td className="px-4 py-3">
                        <StatusBadge status={doc.status} />
                      </td>
                      <td className="px-4 py-3 text-right">
                        <div className="flex items-center justify-end gap-1.5 opacity-90 group-hover:opacity-100">
                          <button
                            onClick={() => handleReprocess(doc.id)}
                            title="Reprocess Vector Embeddings"
                            className="p-1 rounded hover:bg-slate-200 dark:hover:bg-slate-800 transition-colors"
                            style={{ color: 'var(--brand)' }}
                          >
                            <RefreshCw className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={() => handleDelete(doc.id)}
                            title="Delete Document & Chunks"
                            className="p-1 rounded hover:bg-rose-500/10 transition-colors"
                            style={{ color: 'var(--negative-text)' }}
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
