import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, Building2, TrendingUp, ArrowRight, X, Sparkles } from 'lucide-react';
import { api } from '../../services/api';
import { Company } from '../../types';
import { Badge } from '../ui/Badge';
import { useCompanyStore } from '../../stores/companyStore';

interface GlobalSearchModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const GlobalSearchModal: React.FC<GlobalSearchModalProps> = ({ isOpen, onClose }) => {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<Company[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 50);
      // Load top companies on open
      api.getCompanies({ limit: 6 } as any).then(setResults).catch(() => {});
    } else {
      setQuery('');
    }
  }, [isOpen]);

  useEffect(() => {
    if (!query.trim()) return;
    const timeout = setTimeout(async () => {
      setIsLoading(true);
      try {
        const data = await api.searchCompanies(query.trim());
        setResults(data);
      } catch (e) {
        setResults([]);
      } finally {
        setIsLoading(false);
      }
    }, 200);

    return () => clearTimeout(timeout);
  }, [query]);

  const { setSelectedCompany } = useCompanyStore();

  const handleSelect = async (comp: Company) => {
    setSelectedCompany(comp);
    onClose();
    navigate(`/company/${comp.symbol}`);
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-20 p-4">
      <div className="fixed inset-0 bg-slate-950/70 backdrop-blur-sm" onClick={onClose} />
      <div className="relative w-full max-w-2xl bg-white dark:bg-[#0c1222] border border-slate-200 dark:border-slate-800 rounded-xl shadow-2xl z-10 overflow-hidden flex flex-col">
        {/* Input bar */}
        <div className="flex items-center gap-3 px-4 py-3.5 border-b border-slate-200 dark:border-slate-800">
          <Search className="w-5 h-5 text-slate-400" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search by company symbol (RELIANCE, TCS) or name..."
            className="flex-1 bg-transparent text-sm sm:text-base text-slate-900 dark:text-slate-100 placeholder-slate-400 focus:outline-none"
          />
          {query && (
            <button onClick={() => setQuery('')} className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200">
              <X className="w-4 h-4" />
            </button>
          )}
          <kbd className="hidden sm:inline-block text-[10px] bg-slate-100 dark:bg-slate-800 text-slate-500 px-2 py-0.5 rounded border border-slate-300 dark:border-slate-700 font-mono">
            ESC to close
          </kbd>
        </div>

        {/* Results List */}
        <div className="max-h-96 overflow-y-auto p-2">
          {isLoading ? (
            <div className="py-8 text-center text-xs text-slate-400">Searching Indian Equities database...</div>
          ) : results.length > 0 ? (
            <div className="space-y-1">
              <div className="px-3 py-1 text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
                {query ? 'Search Results' : 'Top Listed Equities'}
              </div>
              {results.map((c) => (
                <button
                  key={c.symbol}
                  onClick={() => handleSelect(c)}
                  className="w-full flex items-center justify-between p-3 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-850/80 transition-colors text-left group"
                >
                  <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded bg-cyan-500/10 text-cyan-600 dark:text-cyan-400 border border-cyan-500/20 flex items-center justify-center font-bold text-xs font-mono">
                      {c.symbol.slice(0, 3)}
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-sm text-slate-900 dark:text-slate-100 font-mono">
                          {c.symbol}
                        </span>
                        <Badge variant="terminal" size="xs">
                          {c.exchange || 'NSE'}
                        </Badge>
                        {c.status === 'Ready to Discover' && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20 font-medium flex items-center gap-1">
                            <Sparkles className="w-2.5 h-2.5" /> Ready to Discover
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-slate-500 dark:text-slate-400 line-clamp-1">
                        {c.name} {c.sector ? `· ${c.sector}` : ''}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-4">
                    <div className="text-right">
                      <div className="text-sm font-semibold font-tabular text-slate-900 dark:text-slate-100">
                        ₹{c.current_price?.toLocaleString('en-IN') || '—'}
                      </div>
                      <div className={`text-xs font-tabular font-medium ${c.day_change && c.day_change >= 0 ? 'text-emerald-500' : 'text-rose-500'}`}>
                        {c.day_change && c.day_change > 0 ? '+' : ''}{c.day_change_percent || 0}%
                      </div>
                    </div>
                    <ArrowRight className="w-4 h-4 text-slate-400 opacity-0 group-hover:opacity-100 transition-opacity" />
                  </div>
                </button>
              ))}
            </div>
          ) : (
            <div className="py-8 text-center text-xs text-slate-400">
              No listed company found matching "{query}".
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

