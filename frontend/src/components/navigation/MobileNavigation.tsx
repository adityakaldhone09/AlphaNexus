import React, { useEffect } from 'react';
import { NavLink, Link } from 'react-router-dom';
import { motion, AnimatePresence } from 'motion/react';
import {
  Search, Sun, Moon, Bell, Settings, X,
  LucideIcon,
} from 'lucide-react';
import { useThemeStore } from '../../stores/themeStore';
import { Logo } from '../brand/Logo';

export interface MobileNavItem {
  path: string;
  label: string;
  icon: LucideIcon;
}

interface MobileNavigationProps {
  isOpen: boolean;
  onClose: () => void;
  items: MobileNavItem[];
  activePath: string;
  onSearchOpen: () => void;
}

export const MobileNavigation: React.FC<MobileNavigationProps> = ({
  isOpen,
  onClose,
  items,
  activePath,
  onSearchOpen,
}) => {
  const { theme, toggleTheme } = useThemeStore();

  // Close on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  // Lock body scroll when mobile menu is open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => {
      document.body.style.overflow = '';
    };
  }, [isOpen]);

  return (
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-50 lg:hidden flex flex-col">
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            onClick={onClose}
            className="fixed inset-0 bg-black/60 backdrop-blur-sm"
            aria-hidden="true"
          />

          {/* Drawer Sheet */}
          <motion.div
            initial={{ y: -30, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: -30, opacity: 0 }}
            transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
            className="relative z-10 w-full glass-navbar shadow-2xl border-b border-[var(--border)] overflow-hidden max-h-[90vh] flex flex-col"
            style={{
              background: 'var(--glass-bg)',
              backdropFilter: 'blur(32px) saturate(190%)',
              WebkitBackdropFilter: 'blur(32px) saturate(190%)',
            }}
            role="dialog"
            aria-modal="true"
            aria-label="Mobile Navigation Menu"
          >
            {/* Header */}
            <div className="flex items-center justify-between h-14 px-4 border-b border-[var(--border)]">
              <Logo
                variant="horizontal"
                height={26}
                asLink
                to="/"
                onClick={onClose}
                showDescriptor
                descriptorText="Financial AI"
              />

              <button
                onClick={onClose}
                className="p-2 rounded-xl text-[var(--text-2)] hover:text-[var(--text-1)] hover:bg-[var(--surface-2)] transition-colors"
                aria-label="Close navigation menu"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Quick Search Button */}
            <div className="p-3 border-b border-[var(--border)]">
              <button
                onClick={() => {
                  onClose();
                  onSearchOpen();
                }}
                className="w-full flex items-center justify-between px-3.5 py-2.5 rounded-xl text-xs font-medium transition-all"
                style={{
                  background: 'var(--surface-2)',
                  color: 'var(--text-2)',
                  border: '1px solid var(--border)',
                }}
              >
                <span className="flex items-center gap-2">
                  <Search className="w-4 h-4 text-[var(--brand)]" />
                  <span>Search Indian Equities (NSE/BSE)...</span>
                </span>
                <kbd
                  className="text-[10px] px-1.5 py-0.5 rounded font-mono"
                  style={{
                    background: 'var(--surface-3)',
                    color: 'var(--text-3)',
                    border: '1px solid var(--border)',
                  }}
                >
                  ⌘K
                </kbd>
              </button>
            </div>

            {/* Navigation Links */}
            <nav className="p-3 space-y-1 overflow-y-auto" aria-label="Mobile Navigation Links">
              {items.map((item) => {
                const Icon = item.icon;
                const isActive = activePath === item.path;

                return (
                  <NavLink
                    key={item.path}
                    to={item.path}
                    onClick={onClose}
                    className="flex items-center justify-between px-3.5 py-2.5 rounded-xl text-sm font-semibold transition-all relative"
                    style={{
                      background: isActive ? 'var(--brand-muted)' : 'transparent',
                      color: isActive ? 'var(--brand)' : 'var(--text-2)',
                      border: isActive ? '1px solid var(--border-brand)' : '1px solid transparent',
                    }}
                    aria-current={isActive ? 'page' : undefined}
                  >
                    <span className="flex items-center gap-3">
                      <Icon className="w-4 h-4 shrink-0" style={{ color: isActive ? 'var(--brand)' : 'var(--text-3)' }} />
                      <span>{item.label}</span>
                    </span>

                    {isActive && (
                      <span
                        className="w-2 h-2 rounded-full"
                        style={{
                          background: 'var(--lime)',
                          boxShadow: '0 0 8px var(--lime)',
                        }}
                        aria-hidden="true"
                      />
                    )}
                  </NavLink>
                );
              })}
            </nav>

            {/* Footer Utilities */}
            <div className="p-3 mt-auto border-t border-[var(--border)] bg-[var(--surface-1)]/40 flex items-center justify-between gap-2">
              {/* Theme Toggle */}
              <button
                onClick={toggleTheme}
                className="flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-medium text-[var(--text-2)] hover:text-[var(--text-1)] hover:bg-[var(--surface-2)] transition-colors"
                aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
              >
                {theme === 'dark' ? (
                  <>
                    <Sun className="w-4 h-4 text-amber-400" />
                    <span>Light Mode</span>
                  </>
                ) : (
                  <>
                    <Moon className="w-4 h-4 text-[var(--brand)]" />
                    <span>Dark Mode</span>
                  </>
                )}
              </button>

              <div className="flex items-center gap-1.5">
                {/* Notifications */}
                <button
                  className="relative p-2.5 rounded-xl text-[var(--text-2)] hover:text-[var(--text-1)] hover:bg-[var(--surface-2)] transition-colors"
                  aria-label="Notifications"
                >
                  <Bell className="w-4 h-4" />
                  <span
                    className="absolute top-2 right-2 w-2 h-2 rounded-full"
                    style={{ background: 'var(--lime)', boxShadow: '0 0 6px var(--lime)' }}
                  />
                </button>

                {/* Profile Link */}
                <Link
                  to="/settings"
                  onClick={onClose}
                  className="flex items-center gap-2 p-1.5 rounded-xl hover:bg-[var(--surface-2)] transition-colors"
                  aria-label="User profile and settings"
                >
                  <div
                    className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold"
                    style={{
                      background: 'var(--brand-muted)',
                      color: 'var(--brand)',
                      border: '1px solid var(--border-brand)',
                    }}
                  >
                    AN
                  </div>
                </Link>
              </div>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
};

