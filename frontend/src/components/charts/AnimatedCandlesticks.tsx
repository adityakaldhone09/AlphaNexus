import React, { useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';

/* ----------------------------------------------------------------
   Animated Candlestick Hero — AlphaNexus
   Premium institutional financial composition using SVG + Motion.
   - Reduced to 9 prominent, cleanly spaced candlesticks
   - Substantially elongated candle bodies (50px–93px) & wicks (74px–128px)
   - Authentic financial market colors: Green (#10B981) & Red (#EF4444)
   - Smooth cubic Bezier spline trend curve (Moving Average)
   - Staggered spring expansion animations
   - Active live forming candle with price breathing & dashed price beam
   - Pulsing ATH / HIGH beacon indicator
   - Interactive hover cards with OHLC and percentage movement
   ---------------------------------------------------------------- */

interface CandleData {
  id: number;
  x: number;
  open: number;
  close: number;
  high: number;
  low: number;
  bullish: boolean;
  price: string;
  change: string;
  delay: number;
}

// 9 balanced, elongated candles with pronounced price ranges
const CANDLES: CandleData[] = [
  { id: 0, x: 80,  open: 200, close: 260, high: 175, low: 282, bullish: false, price: '₹2,580', change: '-1.45%', delay: 0.05 },
  { id: 1, x: 175, open: 255, close: 162, high: 144, low: 272, bullish: true,  price: '₹2,690', change: '+3.20%', delay: 0.18 },
  { id: 2, x: 270, open: 166, close: 102, high: 84,  low: 184, bullish: true,  price: '₹2,775', change: '+2.50%', delay: 0.31 },
  { id: 3, x: 365, open: 104, close: 164, high: 88,  low: 182, bullish: false, price: '₹2,715', change: '-1.35%', delay: 0.44 },
  { id: 4, x: 460, open: 160, close: 82,  high: 66,  low: 174, bullish: true,  price: '₹2,820', change: '+3.45%', delay: 0.57 },
  { id: 5, x: 555, open: 86,  close: 138, high: 72,  low: 156, bullish: false, price: '₹2,760', change: '-1.10%', delay: 0.70 },
  { id: 6, x: 650, open: 134, close: 62,  high: 46,  low: 148, bullish: true,  price: '₹2,875', change: '+3.60%', delay: 0.83 },
  { id: 7, x: 745, open: 72,  close: 32,  high: 18,  low: 92,  bullish: true,  price: '₹2,950', change: '+2.90%', delay: 0.96 },
  { id: 8, x: 840, open: 38,  close: 84,  high: 26,  low: 104, bullish: false, price: '₹2,910', change: '-0.95%', delay: 1.09 },
];

// Authentic financial market colors
const COLORS = {
  green: {
    fill: '#10B981',       // Vibrant Emerald Green
    stroke: '#34D399',     // Crisp Highlight Rim
    wick: '#10B981',
    glow: 'rgba(16, 185, 129, 0.45)',
    faint: 'rgba(16, 185, 129, 0.12)',
  },
  red: {
    fill: '#EF4444',       // Vibrant Crimson Red
    stroke: '#F87171',     // Crisp Highlight Rim
    wick: '#EF4444',
    glow: 'rgba(239, 68, 68, 0.45)',
    faint: 'rgba(239, 68, 68, 0.12)',
  },
};

// Smooth cubic Bezier spline through candle closing prices
function buildSmoothSpline(candles: CandleData[]): string {
  if (candles.length === 0) return '';
  const pts = candles.map((c) => ({ x: c.x, y: c.close }));
  let d = `M ${pts[0].x},${pts[0].y}`;
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = i > 0 ? pts[i - 1] : pts[i];
    const p1 = pts[i];
    const p2 = pts[i + 1];
    const p3 = i < pts.length - 2 ? pts[i + 2] : p2;

    const cp1x = p1.x + (p2.x - p0.x) / 5;
    const cp1y = p1.y + (p2.y - p0.y) / 5;
    const cp2x = p2.x - (p3.x - p1.x) / 5;
    const cp2y = p2.y - (p3.y - p1.y) / 5;

    d += ` C ${cp1x.toFixed(1)},${cp1y.toFixed(1)} ${cp2x.toFixed(1)},${cp2y.toFixed(1)} ${p2.x},${p2.y}`;
  }
  return d;
}

const SPLINE_PATH = buildSmoothSpline(CANDLES);
const APPROX_PATH_LENGTH = 1100;

interface CandleStickProps {
  candle: CandleData;
  isHovered: boolean;
  onHover: (c: CandleData | null) => void;
  isLive?: boolean;
}

const CandleStick: React.FC<CandleStickProps> = ({ candle, isHovered, onHover, isLive }) => {
  const { x, open, close, high, low, bullish, delay } = candle;
  const bodyTop = Math.min(open, close);
  const bodyHeight = Math.max(Math.abs(open - close), 6);
  const candleWidth = 34; // Prominent width harmonized with elongated length
  const theme = bullish ? COLORS.green : COLORS.red;

  return (
    <g
      className="cursor-pointer"
      onMouseEnter={() => onHover(candle)}
      onMouseLeave={() => onHover(null)}
    >
      {/* Dynamic ambient bloom glow */}
      {(isHovered || isLive) && (
        <motion.ellipse
          cx={x}
          cy={bodyTop + bodyHeight / 2}
          rx={candleWidth * 0.95}
          ry={bodyHeight * 0.65 + 12}
          fill={theme.glow}
          initial={{ opacity: 0 }}
          animate={{ opacity: isHovered ? 0.75 : [0.22, 0.52, 0.22] }}
          transition={{ duration: 2.2, repeat: Infinity, ease: 'easeInOut' }}
          style={{ filter: 'blur(8px)' }}
        />
      )}

      {/* Wick */}
      <motion.line
        x1={x}
        y1={high}
        x2={x}
        y2={low}
        stroke={theme.wick}
        strokeWidth={2}
        strokeLinecap="round"
        initial={{ pathLength: 0, opacity: 0 }}
        animate={{ pathLength: 1, opacity: isHovered ? 1 : 0.85 }}
        transition={{ duration: 0.45, delay, ease: 'easeOut' }}
      />

      {/* Elongated Candle Body */}
      <motion.rect
        x={x - candleWidth / 2}
        y={bodyTop}
        width={candleWidth}
        height={bodyHeight}
        rx={4}
        fill={theme.fill}
        fillOpacity={isHovered ? 1 : 0.92}
        stroke={theme.stroke}
        strokeWidth={1.5}
        initial={{ scaleY: 0 }}
        animate={{
          scaleY: isHovered ? 1.05 : 1,
          scaleX: isHovered ? 1.04 : 1,
        }}
        style={{
          transformOrigin: `${x}px ${open}px`,
        }}
        transition={{
          duration: 0.55,
          delay: delay + 0.08,
          ease: [0.16, 1, 0.3, 1],
        }}
      />

      {/* Inner glass highlight rim for premium depth */}
      <motion.rect
        x={x - candleWidth / 2 + 2}
        y={bodyTop + 1}
        width={candleWidth - 4}
        height={Math.max(bodyHeight * 0.22, 3)}
        rx={2}
        fill="#FFFFFF"
        fillOpacity={0.18}
        initial={{ opacity: 0 }}
        animate={{ opacity: 0.18 }}
        transition={{ delay: delay + 0.35, duration: 0.3 }}
      />
    </g>
  );
};

export const AnimatedCandlesticks: React.FC = () => {
  const [hoveredCandle, setHoveredCandle] = useState<CandleData | null>(null);

  // Peak High Candle (Candle 7)
  const peakCandle = CANDLES[7];
  // Live Active Candle (Candle 8)
  const liveCandle = CANDLES[8];

  return (
    <div
      className="relative select-none"
      style={{ width: '100%', maxWidth: 960 }}
      aria-label="Decorative animated financial chart — illustrative data only"
      role="img"
    >
      {/* Floating container with smooth organic float */}
      <motion.div
        animate={{ y: [0, -6, 0] }}
        transition={{ duration: 7, repeat: Infinity, ease: 'easeInOut' }}
      >
        <svg
          viewBox="0 0 940 310"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          style={{ width: '100%', height: 'auto', overflow: 'visible' }}
        >
          {/* Gradient definitions */}
          <defs>
            <linearGradient id="splineGradient" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="#3B82F6" stopOpacity={0.9} />
              <stop offset="50%" stopColor="#60A5FA" stopOpacity={0.95} />
              <stop offset="100%" stopColor="#38BDF8" stopOpacity={1} />
            </linearGradient>

            <linearGradient id="areaGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#2563EB" stopOpacity={0.28} />
              <stop offset="60%" stopColor="#1E40AF" stopOpacity={0.08} />
              <stop offset="100%" stopColor="#1E40AF" stopOpacity={0} />
            </linearGradient>

            <filter id="softGlow" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="3" result="blur" />
              <feComposite in="SourceGraphic" in2="blur" operator="over" />
            </filter>
          </defs>

          {/* Grid lines */}
          {[70, 130, 190, 250].map((y) => (
            <line
              key={y}
              x1="30"
              y1={y}
              x2="910"
              y2={y}
              stroke="var(--border)"
              strokeWidth={0.8}
              strokeDasharray="4 8"
              opacity={0.65}
            />
          ))}

          {/* Smooth Trend Spline (Moving Average Curve) */}
          <motion.path
            d={SPLINE_PATH}
            stroke="url(#splineGradient)"
            strokeWidth={2.2}
            strokeLinecap="round"
            strokeLinejoin="round"
            fill="none"
            filter="url(#softGlow)"
            strokeDasharray={APPROX_PATH_LENGTH}
            strokeDashoffset={APPROX_PATH_LENGTH}
            animate={{ strokeDashoffset: 0 }}
            transition={{ duration: 2.4, delay: 1.2, ease: [0.25, 1, 0.5, 1] }}
          />

          {/* Shaded Area fill under trend line */}
          <motion.path
            d={`${SPLINE_PATH} L${liveCandle.x},290 L${CANDLES[0].x},290 Z`}
            fill="url(#areaGradient)"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 1.2, delay: 1.8, ease: 'easeOut' }}
          />

          {/* Elongated Candlesticks */}
          {CANDLES.map((c) => (
            <CandleStick
              key={c.id}
              candle={c}
              isHovered={hoveredCandle?.id === c.id}
              onHover={setHoveredCandle}
              isLive={c.id === liveCandle.id}
            />
          ))}

          {/* --- ACTIVE LIVE FORMING CANDLE (BEAM & PULSE) --- */}
          <g>
            {/* Horizontal dashed price beam to right axis */}
            <motion.line
              x1={liveCandle.x}
              y1={liveCandle.close}
              x2={925}
              y2={liveCandle.close}
              stroke={COLORS.red.stroke}
              strokeWidth={1.2}
              strokeDasharray="4 4"
              opacity={0.65}
              initial={{ pathLength: 0 }}
              animate={{ pathLength: 1 }}
              transition={{ delay: 2.2, duration: 0.6 }}
            />

            {/* Live radar wave at candle close */}
            <motion.circle
              cx={liveCandle.x}
              cy={liveCandle.close}
              r={4}
              fill={COLORS.red.fill}
              initial={{ scale: 0 }}
              animate={{ scale: [1, 1.3, 1] }}
              transition={{ delay: 2.4, duration: 1.8, repeat: Infinity, ease: 'easeInOut' }}
            />
            <motion.circle
              cx={liveCandle.x}
              cy={liveCandle.close}
              r={12}
              fill="none"
              stroke={COLORS.red.stroke}
              strokeWidth={1.5}
              initial={{ scale: 0.5, opacity: 0 }}
              animate={{ scale: [0.8, 2.2], opacity: [0.7, 0] }}
              transition={{ delay: 2.4, duration: 1.8, repeat: Infinity, ease: 'easeOut' }}
            />

            {/* Live price tag on right margin */}
            <motion.g
              initial={{ opacity: 0, x: -6 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 2.4, duration: 0.5 }}
            >
              <rect
                x={870}
                y={liveCandle.close - 10}
                width={56}
                height={20}
                rx={4}
                fill="#0F172A"
                stroke={COLORS.red.stroke}
                strokeWidth={1}
                strokeOpacity={0.8}
              />
              <circle cx={878} cy={liveCandle.close} r={3} fill={COLORS.red.fill} />
              <text
                x={904}
                y={liveCandle.close + 3.5}
                textAnchor="middle"
                fontSize={9.5}
                fill="#F87171"
                fontWeight="700"
                fontFamily="monospace"
              >
                LIVE
              </text>
            </motion.g>
          </g>

          {/* --- PEAK HIGH INDICATOR (CANDLE 7) --- */}
          <g>
            {/* Concentric radar rings at peak high */}
            <motion.circle
              cx={peakCandle.x}
              cy={peakCandle.high}
              r={4}
              fill={COLORS.green.fill}
              initial={{ scale: 0, opacity: 0 }}
              animate={{ scale: [0, 1.4, 1], opacity: 1 }}
              transition={{ delay: 2.5, duration: 0.5 }}
            />
            <motion.circle
              cx={peakCandle.x}
              cy={peakCandle.high}
              r={14}
              fill="none"
              stroke={COLORS.green.stroke}
              strokeWidth={1.5}
              initial={{ scale: 0, opacity: 0 }}
              animate={{ scale: [0.6, 2], opacity: [0.8, 0] }}
              transition={{ delay: 2.5, duration: 1.8, repeat: Infinity, repeatDelay: 1.5 }}
            />

            {/* Connecting pointer pin to High badge */}
            <motion.line
              x1={peakCandle.x}
              y1={peakCandle.high}
              x2={peakCandle.x + 18}
              y2={peakCandle.high - 1}
              stroke={COLORS.green.stroke}
              strokeWidth={1}
              strokeDasharray="2 2"
              initial={{ opacity: 0 }}
              animate={{ opacity: 0.8 }}
              transition={{ delay: 2.8, duration: 0.4 }}
            />

            {/* ▲ HIGH Pill Badge */}
            <motion.g
              initial={{ opacity: 0, x: -6, y: -2 }}
              animate={{ opacity: 1, x: 0, y: 0 }}
              transition={{ delay: 2.8, duration: 0.5 }}
            >
              <rect
                x={peakCandle.x + 18}
                y={peakCandle.high - 12}
                width={76}
                height={22}
                rx={5}
                fill="rgba(16, 185, 129, 0.16)"
                stroke={COLORS.green.stroke}
                strokeWidth={1.2}
                strokeOpacity={0.85}
              />
              <text
                x={peakCandle.x + 56}
                y={peakCandle.high + 2.5}
                textAnchor="middle"
                fontSize={10}
                fill="#34D399"
                fontWeight="700"
                fontFamily="monospace"
                letterSpacing="0.5px"
              >
                ▲ HIGH
              </text>
            </motion.g>
          </g>

          {/* Interactive Crosshair & Tooltip when hovering over a candle */}
          {hoveredCandle && (
            <g pointerEvents="none">
              {/* Vertical dashed crosshair */}
              <line
                x1={hoveredCandle.x}
                y1={30}
                x2={hoveredCandle.x}
                y2={280}
                stroke="var(--text-4)"
                strokeWidth={1}
                strokeDasharray="3 4"
                opacity={0.5}
              />

              {/* Tooltip Card above candle */}
              <g transform={`translate(${Math.max(60, Math.min(800, hoveredCandle.x - 65))}, ${Math.max(10, hoveredCandle.high - 40)})`}>
                <rect
                  width={130}
                  height={32}
                  rx={6}
                  fill="#0B132B"
                  fillOpacity={0.95}
                  stroke={hoveredCandle.bullish ? COLORS.green.stroke : COLORS.red.stroke}
                  strokeWidth={1}
                  style={{ filter: 'drop-shadow(0 4px 12px rgba(0,0,0,0.4))' }}
                />
                <text x={12} y={15} fontSize={10.5} fill="#FFFFFF" fontWeight="700" fontFamily="monospace">
                  {hoveredCandle.price}
                </text>
                <text
                  x={118}
                  y={15}
                  textAnchor="end"
                  fontSize={10}
                  fill={hoveredCandle.bullish ? COLORS.green.stroke : COLORS.red.stroke}
                  fontWeight="700"
                  fontFamily="monospace"
                >
                  {hoveredCandle.change}
                </text>
                <text x={12} y={26} fontSize={8} fill="#94A3B8" fontFamily="monospace">
                  O:{hoveredCandle.open} H:{hoveredCandle.high} L:{hoveredCandle.low}
                </text>
              </g>
            </g>
          )}

          {/* Demo disclaimer */}
          <motion.text
            x={470}
            y={300}
            textAnchor="middle"
            fontSize={9}
            fill="var(--text-4)"
            fontFamily="monospace"
            initial={{ opacity: 0 }}
            animate={{ opacity: 0.8 }}
            transition={{ delay: 3.2, duration: 0.6 }}
          >
            ILLUSTRATIVE DATA — NOT REAL MARKET PRICES
          </motion.text>
        </svg>
      </motion.div>

      {/* Atmospheric glow behind chart */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background:
            'radial-gradient(ellipse 65% 45% at 50% 55%, rgba(16, 185, 129, 0.05) 0%, rgba(37, 99, 235, 0.06) 40%, transparent 75%)',
        }}
      />
    </div>
  );
};
