import React from 'react';

export const Card: React.FC<{
  children: React.ReactNode;
  className?: string;
  style?: React.CSSProperties;
}> = ({
  children,
  className = '',
  style,
}) => {
  return (
    <div
      className={`bg-white dark:bg-[#0c1222] border border-slate-200 dark:border-slate-800/80 rounded-lg shadow-sm transition-all duration-150 ${className}`}
      style={style}
    >
      {children}
    </div>
  );
};

export const CardHeader: React.FC<{ children: React.ReactNode; className?: string }> = ({
  children,
  className = '',
}) => {
  return <div className={`p-4 sm:p-5 border-b border-slate-100 dark:border-slate-800/60 ${className}`}>{children}</div>;
};

export const CardTitle: React.FC<{ children: React.ReactNode; className?: string }> = ({
  children,
  className = '',
}) => {
  return <h3 className={`text-sm sm:text-base font-semibold text-slate-900 dark:text-slate-100 tracking-tight ${className}`}>{children}</h3>;
};

export const CardDescription: React.FC<{ children: React.ReactNode; className?: string }> = ({
  children,
  className = '',
}) => {
  return <p className={`text-xs text-slate-500 dark:text-slate-400 mt-0.5 ${className}`}>{children}</p>;
};

export const CardContent: React.FC<{ children: React.ReactNode; className?: string }> = ({
  children,
  className = '',
}) => {
  return <div className={`p-4 sm:p-5 ${className}`}>{children}</div>;
};

export const CardFooter: React.FC<{ children: React.ReactNode; className?: string }> = ({
  children,
  className = '',
}) => {
  return <div className={`p-3 sm:p-4 bg-slate-50/50 dark:bg-slate-900/30 border-t border-slate-100 dark:border-slate-800/60 rounded-b-lg ${className}`}>{children}</div>;
};
