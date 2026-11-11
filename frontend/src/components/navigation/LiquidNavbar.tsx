import React, { useState } from 'react';
import { NavLink, Link, useLocation } from 'react-router-dom';
import { motion, AnimatePresence } from 'motion/react';
import {
  LayoutDashboard,
  Compass,
  Bot,
  FileText,
  BarChart2,
  Newspaper,
  TrendingUp,
  Search,
  Sun,
  Moon,
  Bell,
  Menu,
} from 'lucide-react';
import { useThemeStore } from '../../stores/themeStore';
import { NavigationIndicator } from './NavigationIndicator';
import { MobileNavigation, MobileNavItem } from './MobileNavigation';
import { Logo } from '../brand/Logo';

export const NAV_ITEMS: MobileNavItem[] = [
  { path: '/',          label: 'Overview',      icon: LayoutDashboard },
  { path: '/discover',  label: 'Discover',      icon: Compass },
  { path: '/research',  label: 'Research',      icon: Bot },
  { path: '/documents', label: 'Documents',     icon: FileText },
  { path: '/analytics', label: 'Analytics',     icon: BarChart2 },
  { path: '/news',      label: 'News & Events', icon: Newspaper },
  { path: '/forecasts', label: 'Forecasts',     icon: TrendingUp },
];

/**
 * Deterministically resolves the active navigation path for top-level
 * and nested routes, guaranteeing that exactly one navigation item is active.
 */
export const getActiveNavPath = (pathname: string): string => {
  if (pathname === '/') return '/';
  if (pathname.startsWith('/discover') || pathname.startsWith('/explore') || pathname.startsWith('/company')) {
    return '/discover';
  }
  if (pathname.startsWith('/research') || pathname.startsWith('/reports')) {
    return '/research';
  }
  if (pathname.startsWith('/documents')) {
    return '/documents';
  }
  if (pathname.startsWith('/analytics') || pathname.startsWith('/financials') || pathname.startsWith('/compare')) {
    return '/analytics';
  }
  if (pathname.startsWith('/news') || pathname.startsWith('/corporate-actions') || pathname.startsWith('/market-events')) {
    return '/news';
  }
  if (pathname.startsWith('/forecasts')) {
    return '/forecasts';
  }
  return '';
};

interface LiquidNavbarProps {
  onSearchOpen: () => void;
}

export const LiquidNavbar: React.FC<LiquidNavbarProps> = ({ onSearchOpen }) => {
  const { theme, toggleTheme } = useThemeStore();
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);

  const activePath = getActiveNavPath(location.pathname);

  return (
    <>
      {/* ─────────────────────────────────────────────────────────────
          1. DESKTOP / TABLET HORIZONTAL NAVBAR (>= 1024px)
          ───────────────────────────────────────────────────────────── */}
      <header className="sticky top-0 z-40 w-full px-3 xl:px-4 pt-3 pb-2 hidden lg:block">
        <motion.div
          initial={{ y: -16, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
          className="glass-navbar rounded-2xl mx-auto w-full max-w-[1360px] px-3 xl:px-4"
        >
          <div className="flex items-center justify-between h-14 w-full">
            {/* ── LEFT: Logo & Brand Identity ── */}
            <div className="flex items-center shrink-0 mr-1 xl:mr-3">
              <Logo
                variant="horizontal"
                height={28}
                asLink
                to="/"
                showDescriptor
                descriptorText="Financial AI"
              />
            </div>

            {/* ── CENTER: Primary Navigation Links ── */}
            <nav
              className="flex items-center justify-center gap-0.5 xl:gap-1.5 shrink-0"
              aria-label="Main Navigation"
            >
              {NAV_ITEMS.map((item) => {
                const Icon = item.icon;
                const isActive = activePath === item.path;

                return (
                  <NavLink
                    key={item.path}
                    to={item.path}
                    className="relative flex items-center gap-1 xl:gap-1.5 px-2 xl:px-3 py-1.5 rounded-xl text-[11px] xl:text-xs font-semibold transition-colors duration-150 select-none whitespace-nowrap focus-visible:ring-2 focus-visible:ring-[var(--brand)] focus-visible:outline-none"
                    style={{
                      color: isActive ? 'var(--text-1)' : 'var(--text-2)',
                    }}
                    aria-current={isActive ? 'page' : undefined}
                  >
                    {/* Active Sliding Frosted Pill & Lime Dot */}
                    {isActive && (
                      <NavigationIndicator layoutId="desktop-nav-active-pill" showDot={true} />
                    )}

                    {/* Non-active Hover Highlight */}
                    {!isActive && (
                      <span className="absolute inset-0 rounded-xl hover:bg-[var(--surface-2)]/60 transition-colors pointer-events-none" />
                    )}

                    {/* Content */}
                    <span className="relative z-10 flex items-center gap-1 xl:gap-1.5">
                      <Icon
                        className="w-3.5 h-3.5 shrink-0 transition-colors"
                        style={{
                          color: isActive ? 'var(--brand)' : 'var(--text-3)',
                        }}
                      />
                      <span>{item.label}</span>
                    </span>
                  </NavLink>
                );
              })}
            </nav>

            {/* ── RIGHT: Search, Theme Toggle, Notifications & Profile ── */}
            <div className="flex items-center gap-1 xl:gap-2 shrink-0 ml-1 xl:ml-3">
              {/* Search Trigger */}
              <button
                onClick={onSearchOpen}
                className="flex items-center gap-1.5 xl:gap-2 px-2 xl:px-3 py-1.5 rounded-xl text-xs transition-all duration-150 group hover:border-[var(--border-brand)] focus-visible:ring-2 focus-visible:ring-[var(--brand)] focus-visible:outline-none"
                style={{
                  background: 'var(--surface-2)',
                  color: 'var(--text-3)',
                  border: '1px solid var(--border)',
                }}
                aria-label="Search Indian Equities (⌘K)"
                title="Search Indian Equities (⌘K)"
              >
                <Search className="w-3.5 h-3.5 transition-colors group-hover:text-[var(--brand)]" />
                <span className="hidden xl:inline group-hover:text-[var(--text-2)]">Search</span>
                <kbd
                  className="hidden 2xl:inline-block text-[10px] px-1.5 py-0.5 rounded font-mono transition-colors"
                  style={{
                    background: 'var(--surface-3)',
                    color: 'var(--text-4)',
                    border: '1px solid var(--border)',
                  }}
                >
                  ⌘K
                </kbd>
              </button>

              {/* Theme Toggle */}
              <motion.button
                whileTap={{ scale: 0.92 }}
                onClick={toggleTheme}
                className="w-8 h-8 rounded-xl flex items-center justify-center transition-colors text-[var(--text-3)] hover:text-[var(--text-1)] hover:bg-[var(--surface-2)] focus-visible:ring-2 focus-visible:ring-[var(--brand)] focus-visible:outline-none"
                aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
                title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
              >
                <AnimatePresence mode="wait" initial={false}>
                  {theme === 'dark' ? (
                    <motion.span
                      key="sun"
                      initial={{ rotate: -45, opacity: 0, scale: 0.8 }}
                      animate={{ rotate: 0, opacity: 1, scale: 1 }}
                      exit={{ rotate: 45, opacity: 0, scale: 0.8 }}
                      transition={{ duration: 0.2 }}
                      className="flex items-center justify-center"
                    >
                      <Sun className="w-4 h-4 text-amber-400" />
                    </motion.span>
                  ) : (
                    <motion.span
                      key="moon"
                      initial={{ rotate: 45, opacity: 0, scale: 0.8 }}
                      animate={{ rotate: 0, opacity: 1, scale: 1 }}
                      exit={{ rotate: -45, opacity: 0, scale: 0.8 }}
                      transition={{ duration: 0.2 }}
                      className="flex items-center justify-center"
                    >
                      <Moon className="w-4 h-4 text-[var(--brand)]" />
                    </motion.span>
                  )}
                </AnimatePresence>
              </motion.button>

              {/* Notifications */}
              <button
                className="relative w-8 h-8 rounded-xl flex items-center justify-center text-[var(--text-3)] hover:text-[var(--text-1)] hover:bg-[var(--surface-2)] transition-colors focus-visible:ring-2 focus-visible:ring-[var(--brand)] focus-visible:outline-none"
                aria-label="View notifications (1 unread)"
                title="Notifications"
              >
                <Bell className="w-4 h-4" />
                <span
                  className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full pointer-events-none"
                  style={{
                    background: 'var(--lime)',
                    boxShadow: '0 0 6px var(--lime)',
                  }}
                  aria-hidden="true"
                />
              </button>

              {/* Profile Avatar */}
              <Link
                to="/settings"
                className="flex items-center pl-1.5 xl:pl-2 ml-0.5 xl:ml-1 focus-visible:ring-2 focus-visible:ring-[var(--brand)] focus-visible:outline-none rounded-full"
                style={{ borderLeft: '1px solid var(--border)' }}
                aria-label="User profile and settings"
                title="Settings & Profile"
              >
                <div
                  className="w-7 h-7 rounded-full flex items-center justify-center text-[11px] font-bold transition-transform hover:scale-105"
                  style={{
                    background: 'var(--brand-muted)',
                    color: 'var(--brand)',
                    border: '1px solid var(--border-brand)',
                    boxShadow: '0 0 8px rgba(21, 88, 201, 0.15)',
                  }}
                >
                  AN
                </div>
              </Link>
            </div>
          </div>
        </motion.div>
      </header>

      {/* ─────────────────────────────────────────────────────────────
          2. MOBILE & TABLET COMPACT NAVBAR (< 1024px)
          ───────────────────────────────────────────────────────────── */}
      <header className="sticky top-0 z-40 w-full max-w-[100vw] lg:hidden px-3 pt-2 pb-1">
        <div className="glass-navbar rounded-xl mx-auto w-full px-3 h-14 flex items-center justify-between">
          {/* Mobile Brand */}
          <Logo
            variant="horizontal"
            height={24}
            asLink
            to="/"
          />

          {/* Mobile Controls */}
          <div className="flex items-center gap-1 shrink-0">
            <button
              onClick={onSearchOpen}
              className="p-2 rounded-lg text-[var(--text-2)] hover:text-[var(--text-1)] hover:bg-[var(--surface-2)] transition-colors"
              aria-label="Search Indian Equities"
            >
              <Search className="w-4 h-4" />
            </button>

            <button
              onClick={toggleTheme}
              className="p-2 rounded-lg text-[var(--text-2)] hover:text-[var(--text-1)] hover:bg-[var(--surface-2)] transition-colors"
              aria-label="Toggle theme"
            >
              {theme === 'dark' ? (
                <Sun className="w-4 h-4 text-amber-400" />
              ) : (
                <Moon className="w-4 h-4 text-[var(--brand)]" />
              )}
            </button>

            <button
              onClick={() => setMobileOpen(true)}
              className="p-2 rounded-lg text-[var(--text-1)] hover:bg-[var(--surface-2)] transition-colors"
              aria-label="Open navigation menu"
            >
              <Menu className="w-5 h-5" />
            </button>
          </div>
        </div>
      </header>

      {/* ─────────────────────────────────────────────────────────────
          3. MOBILE NAVIGATION DRAWER
          ───────────────────────────────────────────────────────────── */}
      <MobileNavigation
        isOpen={mobileOpen}
        onClose={() => setMobileOpen(false)}
        items={NAV_ITEMS}
        activePath={activePath}
        onSearchOpen={onSearchOpen}
      />
    </>
  );
};
