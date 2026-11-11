import React from 'react';
import { Link } from 'react-router-dom';
import { useThemeStore } from '../../stores/themeStore';

export interface LogoProps {
  /**
   * Logo presentation variant
   * - 'horizontal': Full icon + wordmark (default)
   * - 'icon': Standalone gradient 'A' symbol with chart node
   * - 'squircle': Standalone rounded app icon (dark navy background)
   * - 'stacked' | 'compact': Vertical orientation (symbol on top, wordmark below)
   * - 'monochrome': Single-color monochrome variant
   */
  variant?: 'horizontal' | 'icon' | 'squircle' | 'stacked' | 'compact' | 'monochrome';

  /**
   * Visual theme. When 'auto', inherits from active theme store.
   */
  theme?: 'light' | 'dark' | 'auto';

  /**
   * Explicit pixel or CSS height (e.g. 32, "32px", "2rem").
   * Width automatically scales to preserve exact aspect ratio unless explicitly overridden.
   */
  height?: number | string;

  /**
   * Explicit pixel or CSS width.
   */
  width?: number | string;

  /**
   * Additional CSS classes.
   */
  className?: string;

  /**
   * If provided or if asLink is true, wraps the logo in a React Router Link.
   * Defaults to '/' when asLink is true. Set to null to disable link wrapping.
   */
  to?: string | null;
  asLink?: boolean;

  /**
   * Whether to display the "FINANCIAL AI" uppercase sub-descriptor.
   */
  showDescriptor?: boolean;
  descriptorText?: string;

  /**
   * Accessible alternative text.
   */
  alt?: string;

  /**
   * Optional click handler.
   */
  onClick?: (e: React.MouseEvent) => void;
}

/**
 * Official AlphaNexus Brand Logo Component
 *
 * Implements the official cyan-to-blue-to-violet gradient visual identity,
 * with automatic theme adaptation, responsive sizing, and high-DPI rendering.
 */
export const Logo: React.FC<LogoProps> = ({
  variant = 'horizontal',
  theme: propTheme = 'auto',
  height,
  width,
  className = '',
  to,
  asLink = false,
  showDescriptor = false,
  descriptorText = 'Financial AI',
  alt = 'AlphaNexus — AI Financial Intelligence',
  onClick,
}) => {
  const currentTheme = useThemeStore((s) => s.theme);
  const activeTheme = propTheme === 'auto' ? currentTheme : propTheme;

  // Resolve source asset based on variant and active theme
  let src = '/brand/alphanexus-logo-dark.png';
  let defaultHeight = 32;
  let aspectRatio = 4.2;

  switch (variant) {
    case 'icon':
      src = '/brand/alphanexus-icon.png';
      defaultHeight = 32;
      aspectRatio = 1.17;
      break;
    case 'squircle':
      src = '/brand/alphanexus-icon-squircle.png';
      defaultHeight = 36;
      aspectRatio = 1.0;
      break;
    case 'compact':
    case 'stacked':
      src = '/brand/alphanexus-logo-stacked.png';
      defaultHeight = 64;
      aspectRatio = 1.57;
      break;
    case 'monochrome':
      src = '/brand/alphanexus-logo-monochrome.png';
      defaultHeight = 32;
      aspectRatio = 4.2;
      break;
    case 'horizontal':
    default:
      src = activeTheme === 'light'
        ? '/brand/alphanexus-logo-light.png'
        : '/brand/alphanexus-logo-dark.png';
      defaultHeight = 32;
      aspectRatio = activeTheme === 'light' ? 4.08 : 4.2;
      break;
  }

  // Calculate dimensions
  const finalHeight = height ?? defaultHeight;
  const finalWidth = width ?? (typeof finalHeight === 'number' ? Math.round(finalHeight * aspectRatio) : undefined);

  const style: React.CSSProperties = {
    height: typeof finalHeight === 'number' ? `${finalHeight}px` : finalHeight,
    width: finalWidth ? (typeof finalWidth === 'number' ? `${finalWidth}px` : finalWidth) : 'auto',
    objectFit: 'contain',
    display: 'block',
  };

  const imageElement = (
    <div className={`inline-flex items-center gap-2 select-none ${className}`}>
      <img
        src={src}
        alt={alt}
        style={style}
        loading="eager"
        decoding="async"
        className="transition-opacity duration-200"
      />
      {showDescriptor && (
        <span
          className="text-[9px] font-bold tracking-widest uppercase border-l pl-2 leading-none"
          style={{
            borderColor: 'var(--border-strong)',
            color: 'var(--text-3)',
            letterSpacing: '0.12em',
          }}
        >
          {descriptorText}
        </span>
      )}
    </div>
  );

  const shouldLink = asLink || (to !== undefined && to !== null);
  const targetTo = to ?? '/';

  if (shouldLink) {
    return (
      <Link
        to={targetTo}
        onClick={onClick}
        className="inline-flex items-center focus-visible:ring-2 focus-visible:ring-[var(--brand)] focus-visible:outline-none rounded-xl transition-transform hover:scale-[1.02]"
        aria-label={alt}
      >
        {imageElement}
      </Link>
    );
  }

  return imageElement;
};

export default Logo;

