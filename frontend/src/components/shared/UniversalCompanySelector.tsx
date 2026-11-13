import React, { useState, useEffect, useRef } from 'react';
import { Search, Building2, Check, ChevronDown, Sparkles, X, Loader2 } from 'lucide-react';
import { useCompanyStore } from '../../stores/companyStore';
import { api } from '../../services/api';
import { Company } from '../../types';

interface UniversalCompanySelectorProps {
  onSelect?: (company: Company) => void;
  className?: string;
  placeholder?: string;
  showDetails?: boolean;
}

export const UniversalCompanySelector: React.FC<UniversalCompanySelectorProps> = ({
  onSelect,
  className = '',
  placeholder = 'Select Indian Equity (e.g. RELIANCE, TCS, SBIN, ZOMATO)...',
  showDetails = true,
}) => {
  const { selectedCompany, setSelectedCompany } = useCompanyStore();
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<Company[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Close dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Fetch initial top companies when opening if query is empty
  useEffect(() => {
    if (isOpen && !query.trim()) {
      setIsLoading(true);
      api.getCompanies({ limit: 8 } as any)
        .then((comps) => setResults(comps))
        .catch(() => {})
        .finally(() => setIsLoading(false));
    }
  }, [isOpen]);

  // Debounced multi-tiered search
  useEffect(() => {
    if (!query.trim()) return;
    const timeout = setTimeout(async () => {
      setIsLoading(true);
      try {
        const data = await api.searchCompanies(query.trim());
        setResults(data);
      } catch (err) {
        setResults([]);
      } finally {
        setIsLoading(false);
      }
    }, 200);

    return () => clearTimeout(timeout);
  }, [query]);

  const handleSelectCompany = async (company: Company) => {
    let resolved = company;
    // If company not yet fully provisioned, discover on selection
    if (!company.id || company.status === 'Ready to Discover') {
      try {
        setIsLoading(true);
        resolved = await api.discoverCompany(company.symbol);
      } catch (e) {
        // Fallback to existing object
      } finally {
        setIsLoading(false);
      }
    }

    setSelectedCompany(resolved);
    if (onSelect) {
      onSelect(resolved);
    }
    setIsOpen(false);
    setQuery('');
  };

  return (
    <div className={`relative ${className}`} ref={dropdownRef}>
      {/* Selector trigger bar */}
      <button
        type="button"
        onClick={() => {
          setIsOpen(!isOpen);
          setTimeout(() => inputRef.current?.focus(), 50);
        }}
        className="w-full flex items-center justify-between gap-3 px-3 py-2 bg-slate-50 dark:bg-slate-900/90 hover:bg-slate-100 dark:hover:bg-slate-850 border border-slate-200 dark:border-slate-800 rounded-lg text-left transition-all group"
      >
        <div className="flex items-center gap-2.5 truncate">
          <div className="w-7 h-7 rounded-md bg-cyan-500/10 text-cyan-600 dark:text-cyan-400 border border-cyan-500/20 flex items-center justify-center font-bold text-xs shrink-0">
            {selectedCompany ? selectedCompany.symbol.slice(0, 3) : <Building2 className="w-3.5 h-3.5" />}
          </div>
          <div className="truncate">
            {selectedCompany ? (
              <div className="flex items-center gap-2">
                <span className="font-semibold text-xs sm:text-sm text-slate-900 dark:text-slate-100 font-mono">
                  {selectedCompany.symbol}
                </span>
                <span className="text-[11px] text-slate-400 truncate hidden sm:inline">
                  {selectedCompany.name}
                </span>
                <span className="text-[10px] px-1.5 py-0.2 rounded bg-slate-200 dark:bg-slate-800 text-slate-600 dark:text-slate-300 font-medium">
                  {selectedCompany.exchange || 'NSE'}
                </span>
              </div>
            ) : (
              <span className="text-xs text-slate-400 font-normal truncate">
                {placeholder}
              </span>
            )}
          </div>
        </div>
        <ChevronDown className={`w-4 h-4 text-slate-400 group-hover:text-slate-600 dark:group-hover:text-slate-200 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {/* Dropdown panel */}
      {isOpen && (
        <div className="absolute top-full left-0 right-0 mt-1.5 z-50 bg-white dark:bg-[#0c1222] border border-slate-200 dark:border-slate-800 rounded-xl shadow-2xl overflow-hidden animate-in fade-in slide-in-from-top-2 duration-150">
          {/* Search Input bar */}
          <div className="p-2 border-b border-slate-100 dark:border-slate-800/80 flex items-center gap-2">
            <Search className="w-4 h-4 text-slate-400 shrink-0 ml-1.5" />
            <input
              ref={inputRef}
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search ticker, name, ISIN, or sector..."
              className="w-full bg-transparent text-xs sm:text-sm text-slate-900 dark:text-slate-100 placeholder-slate-400 focus:outline-none py-1"
            />
            {query && (
              <button onClick={() => setQuery('')} className="p-1 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200">
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </div>

          {/* Results List */}
          <div className="max-h-64 overflow-y-auto p-1.5 space-y-1">
            {isLoading ? (
              <div className="py-6 flex flex-col items-center justify-center gap-2 text-xs text-slate-400">
                <Loader2 className="w-4 h-4 animate-spin text-cyan-500" />
                <span>Searching universal equities registry...</span>
              </div>
            ) : results.length > 0 ? (
              results.map((comp) => {
                const isSelected = selectedCompany?.symbol === comp.symbol;
                return (
                  <button
                    key={comp.symbol}
                    type="button"
                    onClick={() => handleSelectCompany(comp)}
                    className={`w-full flex items-center justify-between p-2 rounded-lg text-left transition-colors ${
                      isSelected
                        ? 'bg-cyan-500/10 border border-cyan-500/30 text-cyan-600 dark:text-cyan-400'
                        : 'hover:bg-slate-100 dark:hover:bg-slate-850/80 text-slate-800 dark:text-slate-200'
                    }`}
                  >
                    <div className="flex items-center gap-2.5 truncate">
                      <div className="w-8 h-8 rounded bg-slate-200/60 dark:bg-slate-800 text-slate-700 dark:text-slate-300 flex items-center justify-center font-bold text-xs font-mono shrink-0">
                        {comp.symbol.slice(0, 3)}
                      </div>
                      <div className="truncate">
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-xs sm:text-sm font-mono text-slate-900 dark:text-slate-100">
                            {comp.symbol}
                          </span>
                          <span className="text-[10px] text-slate-400 uppercase font-medium">
                            {comp.exchange || 'NSE'}
                          </span>
                          {comp.status === 'Ready to Discover' && (
                            <span className="text-[9px] px-1 py-0.2 rounded bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20 font-medium flex items-center gap-0.5">
                              <Sparkles className="w-2.5 h-2.5" /> Auto-Discover
                            </span>
                          )}
                        </div>
                        <div className="text-[11px] text-slate-500 dark:text-slate-400 truncate">
                          {comp.name} {comp.sector ? `· ${comp.sector}` : ''}
                        </div>
                      </div>
                    </div>
                    {isSelected && <Check className="w-4 h-4 text-cyan-500 shrink-0 ml-2" />}
                  </button>
                );
              })
            ) : (
              <div className="py-6 text-center text-xs text-slate-400">
                No matching Indian equities found. Try searching by NSE ticker, BSE code, or ISIN.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

