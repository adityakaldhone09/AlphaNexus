import React from 'react';
import { NavLink } from 'react-router-dom';
import { Logo } from '../brand/Logo';
import {
  LayoutDashboard,
  Search,
  Bot,
  FileText,
  TrendingUp,
  BarChart3,
  Newspaper,
  CalendarDays,
  Briefcase,
  GitCompare,
  Bookmark,
  FileSpreadsheet,
  Settings,
  ChevronLeft,
  ChevronRight,
  ShieldAlert,
} from 'lucide-react';

interface SidebarProps {
  isCollapsed: boolean;
  onToggle: () => void;
}

export const NAV_ITEMS = [
  { path: '/', label: 'Overview', icon: LayoutDashboard },
  { path: '/explore', label: 'Explore Companies', icon: Search },
  { path: '/research', label: 'AI Research', icon: Bot, badge: 'RAG' },
  { path: '/documents', label: 'Document Intelligence', icon: FileText },
  { path: '/financials', label: 'Financial Analysis', icon: BarChart3 },
  { path: '/forecasts', label: 'Performance Forecasts', icon: TrendingUp },
  { path: '/news', label: 'News Intelligence', icon: Newspaper },
  { path: '/corporate-actions', label: 'Corporate Actions', icon: CalendarDays },
  { path: '/market-events', label: 'Market Events & Deals', icon: Briefcase },
  { path: '/compare', label: 'Peer Comparison', icon: GitCompare },
  { path: '/watchlist', label: 'Watchlist', icon: Bookmark },
  { path: '/reports', label: 'Research Reports', icon: FileSpreadsheet },
  { path: '/settings', label: 'Settings & Status', icon: Settings },
];

export const Sidebar: React.FC<SidebarProps> = ({ isCollapsed, onToggle }) => {
  return (
    <aside
      className={`relative z-40 flex flex-col bg-slate-50 dark:bg-[#070b16] border-r border-slate-200 dark:border-slate-800/80 transition-all duration-200 select-none ${
        isCollapsed ? 'w-16' : 'w-64'
      }`}
    >
      {/* Brand Header */}
      <div className="h-14 flex items-center justify-between px-3 border-b border-slate-200 dark:border-slate-800/80">
        <div className="overflow-hidden">
          <Logo
            variant={isCollapsed ? 'icon' : 'horizontal'}
            height={isCollapsed ? 26 : 24}
            asLink
            to="/"
          />
        </div>

        <button
          onClick={onToggle}
          className="p-1 rounded text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-200/60 dark:hover:bg-slate-800/60 transition-colors"
          title={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {isCollapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
        </button>
      </div>

      {/* Navigation List */}
      <nav className="flex-1 overflow-y-auto py-3 px-2 space-y-1">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                `flex items-center gap-3 px-2.5 py-2 rounded-md text-xs font-medium transition-all group relative ${
                  isActive
                    ? 'bg-cyan-500/10 text-cyan-600 dark:text-cyan-400 font-semibold border-l-2 border-cyan-500'
                    : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 hover:bg-slate-200/50 dark:hover:bg-slate-800/50'
                }`
              }
              title={isCollapsed ? item.label : undefined}
            >
              <Icon className="w-4 h-4 shrink-0 transition-transform group-hover:scale-105" />
              {!isCollapsed && (
                <div className="flex-1 flex items-center justify-between">
                  <span className="truncate">{item.label}</span>
                  {item.badge && (
                    <span className="text-[9px] px-1.5 py-0.2 rounded font-mono font-medium bg-cyan-500/15 text-cyan-500 border border-cyan-500/30">
                      {item.badge}
                    </span>
                  )}
                </div>
              )}
            </NavLink>
          );
        })}
      </nav>

      {/* Market Tag / Bottom badge */}
      {!isCollapsed && (
        <div className="p-3 m-2 rounded-md bg-slate-100 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800 text-[11px]">
          <div className="flex items-center justify-between font-mono text-slate-500 dark:text-slate-400 mb-1">
            <span>Market Mode</span>
            <span className="text-emerald-500 flex items-center gap-1 font-semibold">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-ping" />
              NSE / BSE
            </span>
          </div>
          <p className="text-[10px] text-slate-400 dark:text-slate-500 leading-tight">
            Terminal active for Indian Equities research.
          </p>
        </div>
      )}
    </aside>
  );
};

