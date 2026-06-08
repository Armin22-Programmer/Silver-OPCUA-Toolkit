// frontend/src/App.tsx

import { useState } from 'react'
import ConnectionsPage from '@/pages/ConnectionsPage'
import TagBrowserPage from '@/pages/TagBrowserPage'
import MonitorPage from '@/pages/MonitorPage'
import { WatchlistProvider, useWatchlist } from '@/lib/watchlist'
import { useSystemStatus, type StatusLevel } from '@/lib/useSystemStatus'
import { Activity, Cable, Tag } from 'lucide-react'

type Page = 'connections' | 'tags' | 'monitor'

const NAV_ITEMS: { id: Page; label: string; icon: React.ReactNode }[] = [
  { id: 'connections', label: 'Connections', icon: <Cable className="w-[15px] h-[15px]" /> },
  { id: 'tags',        label: 'Tag Browser', icon: <Tag className="w-[15px] h-[15px]" /> },
  { id: 'monitor',     label: 'Live Monitor', icon: <Activity className="w-[15px] h-[15px]" /> },
]

// ── Status dot colors ──
const STATUS_COLORS: Record<StatusLevel, string> = {
  green:  '#22C55E',
  yellow: '#F59E0B',
  red:    '#EF4444',
  gray:   '#6B7280',
}

const STATUS_BG: Record<StatusLevel, string> = {
  green:  'rgba(34,197,94,0.12)',
  yellow: 'rgba(245,158,11,0.12)',
  red:    'rgba(239,68,68,0.12)',
  gray:   'rgba(107,114,128,0.10)',
}

function Sidebar({ page, setPage }: { page: Page; setPage: (p: Page) => void }) {
  const { watchlist, isStreaming, isPaused, isWsConnected } = useWatchlist()
  const status = useSystemStatus({
    isStreaming,
    isPaused,
    watchlistCount: watchlist.length,
    isWsConnected,
  })

  return (
    <aside
      className="fixed top-0 left-0 h-screen flex flex-col z-40"
      style={{
        width: '200px',
        background: '#0F172A',
        borderRight: '1px solid rgba(255,255,255,0.06)',
      }}
    >
      {/* Logo */}
      <div
        className="flex items-center gap-2.5 px-4 shrink-0"
        style={{
          height: '56px',
          borderBottom: '1px solid rgba(255,255,255,0.07)',
        }}
      >
        <div
          className="flex items-center justify-center shrink-0"
          style={{
            width: '28px',
            height: '28px',
            background: '#6366F1',
            borderRadius: '7px',
          }}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
               stroke="#fff" strokeWidth="2.5" strokeLinecap="round">
            <circle cx="12" cy="12" r="3" />
            <path d="M12 2v3M12 19v3M2 12h3M19 12h3" />
            <path d="M5.64 5.64l2.12 2.12M16.24 16.24l2.12 2.12M5.64 18.36l2.12-2.12M16.24 7.76l2.12-2.12" />
          </svg>
        </div>
        <div>
          <div style={{ fontSize: '12.5px', fontWeight: 600, color: '#F1F5F9', letterSpacing: '-0.01em' }}>
            Silver OPC UA
          </div>
          <div style={{ fontSize: '10px', color: '#6B7280', marginTop: '1px' }}>
            v0.4.0-alpha
          </div>
        </div>
      </div>

      {/* Nav links */}
      <nav className="flex-1 px-2 py-3 overflow-y-auto">
        <div className="px-2 pb-2"
             style={{ fontSize: '9.5px', fontWeight: 600, color: '#4B5563',
                      textTransform: 'uppercase', letterSpacing: '0.08em' }}>
          Workspace
        </div>

        {NAV_ITEMS.map(item => {
          const isActive = page === item.id
          return (
            <button
              key={item.id}
              onClick={() => setPage(item.id)}
              className="relative w-full flex items-center gap-2.5 transition-colors duration-150"
              style={{
                padding: '8px 10px',
                marginBottom: '1px',
                borderRadius: '6px',
                fontSize: '12.5px',
                fontWeight: 500,
                color: isActive ? '#FFFFFF' : '#9CA3AF',
                background: isActive ? '#6366F1' : 'transparent',
                border: 'none',
                cursor: 'pointer',
                textAlign: 'left',
              }}
              onMouseEnter={e => {
                if (!isActive) {
                  (e.currentTarget as HTMLButtonElement).style.background = 'rgba(255,255,255,0.07)'
                  ;(e.currentTarget as HTMLButtonElement).style.color = '#E2E8F0'
                }
              }}
              onMouseLeave={e => {
                if (!isActive) {
                  (e.currentTarget as HTMLButtonElement).style.background = 'transparent'
                  ;(e.currentTarget as HTMLButtonElement).style.color = '#9CA3AF'
                }
              }}
            >
              {item.icon}
              {item.label}

              {/* Watchlist badge */}
              {item.id === 'monitor' && watchlist.length > 0 && (
                <span
                  className="absolute flex items-center justify-center font-bold"
                  style={{
                    top: '6px', right: '8px',
                    width: '17px', height: '17px',
                    borderRadius: '50%',
                    background: isActive ? 'rgba(255,255,255,0.25)' : '#6366F1',
                    color: '#fff',
                    fontSize: '10px',
                  }}
                >
                  {watchlist.length}
                </span>
              )}
            </button>
          )
        })}
      </nav>

      {/* Footer — System Status panel */}
      <div
        className="shrink-0"
        style={{ borderTop: '1px solid rgba(255,255,255,0.07)', padding: '10px 8px 12px' }}
      >
        {/* Header row */}
        <div
          style={{
            display: 'flex', alignItems: 'center', gap: '7px',
            padding: '4px 8px 8px',
          }}
        >
          <span
            style={{
              width: '7px', height: '7px', borderRadius: '50%',
              background: STATUS_COLORS[status.overall],
              display: 'inline-block', flexShrink: 0,
              transition: 'background 0.4s',
            }}
          />
          <span style={{ fontSize: '11px', fontWeight: 600, color: '#E2E8F0' }}>
            System Status
          </span>
        </div>

        {/* Status items */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
          {status.items.map(item => (
            <div
              key={item.label}
              style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                padding: '4px 8px',
                borderRadius: '5px',
                background: STATUS_BG[item.level],
                transition: 'background 0.4s',
              }}
            >
              <span style={{ fontSize: '10.5px', color: '#9CA3AF', fontWeight: 500 }}>
                {item.label}
              </span>
              <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                <span
                  style={{
                    width: '5px', height: '5px', borderRadius: '50%',
                    background: STATUS_COLORS[item.level],
                    flexShrink: 0,
                    transition: 'background 0.4s',
                  }}
                />
                <span
                  style={{
                    fontSize: '10px',
                    color: STATUS_COLORS[item.level],
                    fontWeight: 500,
                    transition: 'color 0.4s',
                  }}
                >
                  {item.detail}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </aside>
  )
}

function AppContent() {
  const [page, setPage] = useState<Page>('connections')

  return (
    <div className="min-h-screen flex" style={{ backgroundColor: '#F1F5F9' }}>
      <Sidebar page={page} setPage={setPage} />

      {/* Main area — offset by sidebar width */}
      <div className="flex-1 min-h-screen" style={{ marginLeft: '200px' }}>
        {page === 'connections' && <ConnectionsPage />}
        {page === 'tags' && <TagBrowserPage />}
        {page === 'monitor' && <MonitorPage />}
      </div>
    </div>
  )
}

function App() {
  return (
    <WatchlistProvider>
      <AppContent />
    </WatchlistProvider>
  )
}

export default App
