import React from 'react'
import { Zap } from 'lucide-react'
import { useApp } from '../App.jsx'

const MODE_CFG = {
  full_auto:  { label: 'Full Auto',   bg: 'rgba(29,158,117,0.18)', color: '#1D9E75', pulse: true  },
  assist:     { label: 'Assist',      bg: 'rgba(83,74,183,0.18)',  color: '#534AB7', pulse: false },
  human_only: { label: 'Human Only',  bg: 'rgba(107,114,128,0.15)',color: '#9ca3af', pulse: false },
}

export default function HermesPill({ onClick }) {
  const { hermesMode, cycleHermes } = useApp()
  const cfg = MODE_CFG[hermesMode]
  const handleClick = onClick || cycleHermes
  return (
    <button onClick={handleClick} title="Click to cycle Hermes mode" style={{
      display: 'inline-flex', alignItems: 'center', gap: 7,
      background: cfg.bg, color: cfg.color,
      border: `1px solid ${cfg.color}44`,
      borderRadius: 20, padding: '5px 12px',
      fontSize: 12, fontWeight: 600, cursor: 'pointer',
      transition: 'all .2s',
    }}>
      {cfg.pulse
        ? <span style={{ width:7,height:7,borderRadius:'50%',background:cfg.color,
            animation:'pulse-dot 1.5s ease-in-out infinite',flexShrink:0 }} />
        : <Zap size={12} />
      }
      Hermes · {cfg.label}
    </button>
  )
}
