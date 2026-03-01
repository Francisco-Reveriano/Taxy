import React from 'react'

interface Props {
  score: number  // 0-100
}

export default function ConfidenceGauge({ score }: Props) {
  const r = 36
  const cx = 44
  const cy = 44
  const circumference = Math.PI * r  // half circle
  const pct = Math.min(100, Math.max(0, score))
  const offset = circumference * (1 - pct / 100)

  const color = pct >= 90 ? '#22c55e' : pct >= 75 ? '#f59e0b' : '#ef4444'

  return (
    <div style={{ textAlign: 'center' }}>
      <svg width={88} height={50} viewBox="0 0 88 50">
        {/* Background arc */}
        <path
          d={`M 8 44 A ${r} ${r} 0 0 1 80 44`}
          fill="none"
          stroke="#e2e8f0"
          strokeWidth="10"
          strokeLinecap="round"
        />
        {/* Score arc */}
        <path
          d={`M 8 44 A ${r} ${r} 0 0 1 80 44`}
          fill="none"
          stroke={color}
          strokeWidth="10"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
        />
        <text x={cx} y={44} textAnchor="middle" fontSize={13} fontWeight="bold" fill={color}>
          {pct.toFixed(0)}
        </text>
        <text x={cx} y={56} textAnchor="middle" fontSize={9} fill="#888">
          confidence
        </text>
      </svg>
    </div>
  )
}
