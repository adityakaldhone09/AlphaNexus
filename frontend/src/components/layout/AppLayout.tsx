import React, { useState, useEffect } from 'react';
import { Outlet } from 'react-router-dom';
import { motion } from 'motion/react';
import { LiquidNavbar } from '../navigation/LiquidNavbar';
import { GlobalSearch } from '../shared/GlobalSearch';
import { Logo } from '../brand/Logo';

export const AppLayout: React.FC = () => {
  const [searchOpen, setSearchOpen] = useState(false);

  // ⌘K / Ctrl+K shortcut
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setSearchOpen(true);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  return (
    <div
      className="min-h-screen w-full max-w-full overflow-x-hidden flex flex-col justify-between"
      style={{ background: 'var(--bg)', color: 'var(--text-1)' }}
    >
      <div className="w-full">
        <LiquidNavbar onSearchOpen={() => setSearchOpen(true)} />

        <motion.main
          key="main"
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
          className="pb-16 w-full max-w-full overflow-x-hidden"
        >
          <Outlet />
        </motion.main>
      </div>

      {/* ── Institutional Footer ── */}
      <footer
        className="w-full border-t py-8 px-4 sm:px-6 lg:px-8 mt-auto"
        style={{
          borderColor: 'var(--border)',
          background: 'var(--surface-1)',
        }}
      >
        <div
          className="max-w-[1360px] mx-auto flex flex-col sm:flex-row items-center justify-between gap-4 text-xs"
          style={{ color: 'var(--text-3)' }}
        >
          <div className="flex items-center gap-3">
            <Logo variant="horizontal" height={22} asLink to="/" />
            <span className="hidden sm:inline" style={{ color: 'var(--border-strong)' }}>|</span>
            <span className="hidden sm:inline font-medium text-[11px]">See Beyond the Stock Price.</span>
          </div>

          <div className="flex flex-wrap items-center justify-center gap-4 sm:gap-6 text-[11px]">
            <span>NSE &amp; BSE Equity Intelligence</span>
            <span style={{ color: 'var(--border-strong)' }}>&bull;</span>
            <span>RAG &amp; MongoDB Atlas Vector Search</span>
            <span style={{ color: 'var(--border-strong)' }}>&bull;</span>
            <span>&copy; {new Date().getFullYear()} AlphaNexus. All rights reserved.</span>
          </div>
        </div>
      </footer>

      <GlobalSearch open={searchOpen} onClose={() => setSearchOpen(false)} />
    </div>
  );
};
