// frontend/src/pages/ConnectionsPage.tsx

import { useEffect, useState, useCallback } from 'react'
import type { Connection, ConnectionCreate, SecurityMode, SecurityPolicy, AuthType } from '@/lib/api'
import { connectionsApi } from '@/lib/api'
import { useWatchlist } from '@/lib/watchlist'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import {
  Trash2, Plus, Power, PowerOff, Loader2,
  Cable, AlertCircle, CheckCircle2, Server,
  ChevronDown, ChevronUp, ShieldCheck, ShieldOff, User, Lock, KeyRound,
} from 'lucide-react'

// ── Constants ─────────────────────────────────────────────────────────────

const SECURITY_MODES: SecurityMode[] = ['None', 'Sign', 'SignAndEncrypt']

const SECURITY_POLICIES: { value: SecurityPolicy; label: string }[] = [
  { value: 'None',                  label: 'None' },
  { value: 'Basic256Sha256',        label: 'Basic256Sha256' },
  { value: 'Aes128Sha256RsaOaep',   label: 'Aes128Sha256RsaOaep' },
  { value: 'Aes256Sha256RsaPss',    label: 'Aes256Sha256RsaPss' },
]

const DEFAULT_FORM: ConnectionCreate = {
  name: '',
  endpoint: '',
  auth_type: 'anonymous',
  username: '',
  password: '',
  security_mode: 'None',
  security_policy: 'None',
  certificate_path: '',
  private_key_path: '',
}

// ── Helpers ───────────────────────────────────────────────────────────────

function StatusBadge({ active }: { active: boolean }) {
  return (
    <span
      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium"
      style={active
        ? { background: '#F0FDF4', color: '#16A34A', border: '1px solid #BBF7D0' }
        : { background: '#F8FAFC', color: '#94A3B8', border: '1px solid #E2E8F0' }
      }
    >
      <span
        className="inline-block rounded-full shrink-0"
        style={{ width: '6px', height: '6px', background: active ? '#16A34A' : '#CBD5E1' }}
      />
      {active ? 'Connected' : 'Disconnected'}
    </span>
  )
}

function SecurityBadge({ mode }: { mode: string }) {
  if (mode === 'None') return null
  return (
    <span
      className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium"
      style={{ background: '#EEF2FF', color: '#6366F1', border: '1px solid #C7D2FE' }}
    >
      <ShieldCheck style={{ width: '11px', height: '11px' }} />
      {mode}
    </span>
  )
}

// ── Form field component ──────────────────────────────────────────────────

function FormField({
  label, children, hint,
}: { label: string; children: React.ReactNode; hint?: string }) {
  return (
    <div className="space-y-1.5">
      <Label style={{ fontSize: '11.5px', fontWeight: 600, color: '#475569' }}>
        {label}
      </Label>
      {children}
      {hint && (
        <p style={{ fontSize: '11px', color: '#94A3B8' }}>{hint}</p>
      )}
    </div>
  )
}

// ── Select component ──────────────────────────────────────────────────────

function Select<T extends string>({
  value, onChange, options,
}: {
  value: T
  onChange: (v: T) => void
  options: { value: T; label: string }[]
}) {
  return (
    <select
      value={value}
      onChange={e => onChange(e.target.value as T)}
      style={{
        width: '100%',
        padding: '7px 10px',
        borderRadius: '7px',
        border: '1px solid #E2E8F0',
        background: '#fff',
        fontSize: '12.5px',
        color: '#0F172A',
        outline: 'none',
        cursor: 'pointer',
      }}
    >
      {options.map(opt => (
        <option key={opt.value} value={opt.value}>{opt.label}</option>
      ))}
    </select>
  )
}

// ── Add Connection Form ───────────────────────────────────────────────────

function AddConnectionForm({ onCreated }: { onCreated: () => void }) {
  const [form, setForm]           = useState<ConnectionCreate>(DEFAULT_FORM)
  const [error, setError]         = useState('')
  const [showSecurity, setShowSecurity] = useState(false)
  const [open, setOpen]           = useState(false)
  const [generatingCert, setGeneratingCert] = useState(false)
  const [certMsg, setCertMsg]     = useState('')

  const set = (key: keyof ConnectionCreate, value: string) =>
    setForm(prev => ({ ...prev, [key]: value }))

  const handleGenerateCert = async () => {
    setGeneratingCert(true)
    setCertMsg('')
    try {
      const res = await fetch('/api/v1/certificates/generate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({}) })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Failed to generate certificate')
      setForm(prev => ({ ...prev, certificate_path: data.certificate_path, private_key_path: data.private_key_path }))
      setCertMsg(data.message)
    } catch (e) {
      setCertMsg((e as Error).message)
    } finally {
      setGeneratingCert(false)
    }
  }

  // Auto-reset policy when mode changes to None
  const setSecurityMode = (mode: SecurityMode) => {
    setForm(prev => ({
      ...prev,
      security_mode: mode,
      security_policy: mode === 'None' ? 'None' : (prev.security_policy === 'None' ? 'Basic256Sha256' : prev.security_policy),
    }))
  }

  const needsCert = form.security_mode !== 'None'

  const handleCreate = async () => {
    setError('')
    if (!form.name || !form.endpoint) {
      setError('Name and endpoint are required.')
      return
    }
    if (form.auth_type === 'username' && !form.username) {
      setError('Username is required for username/password authentication.')
      return
    }
    if (needsCert && (!form.certificate_path || !form.private_key_path)) {
      setError('Certificate and private key paths are required for Sign/SignAndEncrypt mode.')
      return
    }

    try {
      await connectionsApi.create({
        ...form,
        // Don't send empty strings — send undefined instead
        username:         form.username         || undefined,
        password:         form.password         || undefined,
        certificate_path: form.certificate_path || undefined,
        private_key_path: form.private_key_path || undefined,
      })
      setForm(DEFAULT_FORM)
      setOpen(false)
      setShowSecurity(false)
      onCreated()
    } catch (e) {
      const err = e as { response?: { data?: { detail?: string } } }
      setError(err.response?.data?.detail || 'Something went wrong.')
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <button
          style={{
            padding: '8px 14px', borderRadius: '8px',
            fontSize: '12.5px', fontWeight: 500,
            background: '#6366F1', color: '#fff',
            border: 'none', cursor: 'pointer',
            display: 'flex', alignItems: 'center', gap: '6px',
          }}
        >
          <Plus className="w-3.5 h-3.5" />
          Add Connection
        </button>
      </DialogTrigger>

      <DialogContent className="border border-slate-200" style={{ borderRadius: '14px', maxWidth: '480px' }}>
        <DialogHeader>
          <DialogTitle style={{ fontSize: '15px', fontWeight: 600, color: '#0F172A' }}>
            New OPC UA Connection
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4 mt-2">
          {/* ── Basic fields ── */}
          <FormField label="Name">
            <Input
              placeholder="e.g. Reactor PLC"
              value={form.name}
              onChange={e => set('name', e.target.value)}
              className="border-slate-200 focus:border-indigo-400 focus:ring-indigo-300"
              style={{ fontSize: '12.5px' }}
            />
          </FormField>

          <FormField label="Endpoint">
            <Input
              placeholder="opc.tcp://192.168.1.100:4840"
              value={form.endpoint}
              onChange={e => set('endpoint', e.target.value)}
              className="border-slate-200 focus:border-indigo-400 focus:ring-indigo-300"
              style={{ fontSize: '12px', fontFamily: 'ui-monospace, monospace' }}
            />
          </FormField>

          {/* ── Security section toggle ── */}
          <button
            onClick={() => setShowSecurity(p => !p)}
            className="w-full flex items-center justify-between transition-colors"
            style={{
              padding: '8px 12px',
              borderRadius: '8px',
              border: '1px solid',
              borderColor: showSecurity ? '#C7D2FE' : '#E2E8F0',
              background: showSecurity ? '#EEF2FF' : '#F8FAFC',
              cursor: 'pointer',
              fontSize: '12.5px',
              fontWeight: 500,
              color: showSecurity ? '#6366F1' : '#475569',
            }}
          >
            <div className="flex items-center gap-2">
              {form.security_mode !== 'None'
                ? <ShieldCheck className="w-3.5 h-3.5" />
                : <ShieldOff className="w-3.5 h-3.5" style={{ color: '#94A3B8' }} />
              }
              Security Configuration
              {form.security_mode !== 'None' && (
                <span style={{
                  fontSize: '10.5px', fontWeight: 600,
                  padding: '1px 6px', borderRadius: '4px',
                  background: '#6366F1', color: '#fff',
                }}>
                  {form.security_mode}
                </span>
              )}
            </div>
            {showSecurity
              ? <ChevronUp className="w-3.5 h-3.5" />
              : <ChevronDown className="w-3.5 h-3.5" />
            }
          </button>

          {showSecurity && (
            <div
              className="space-y-3"
              style={{
                padding: '14px',
                borderRadius: '8px',
                background: '#F8FAFC',
                border: '1px solid #E2E8F0',
              }}
            >
              {/* Authentication */}
              <div style={{
                fontSize: '10px', fontWeight: 700, color: '#94A3B8',
                textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: '8px',
              }}>
                Authentication
              </div>

              <FormField label="Auth Type">
                <Select<AuthType>
                  value={form.auth_type as AuthType}
                  onChange={v => set('auth_type', v)}
                  options={[
                    { value: 'anonymous', label: 'Anonymous' },
                    { value: 'username',  label: 'Username / Password' },
                  ]}
                />
              </FormField>

              {form.auth_type === 'username' && (
                <>
                  <FormField label="Username">
                    <div className="relative">
                      <User className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5"
                            style={{ color: '#94A3B8' }} />
                      <Input
                        placeholder="admin"
                        value={form.username ?? ''}
                        onChange={e => set('username', e.target.value)}
                        className="border-slate-200 pl-8"
                        style={{ fontSize: '12.5px' }}
                      />
                    </div>
                  </FormField>
                  <FormField label="Password">
                    <div className="relative">
                      <Lock className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5"
                            style={{ color: '#94A3B8' }} />
                      <Input
                        type="password"
                        placeholder="••••••••"
                        value={form.password ?? ''}
                        onChange={e => set('password', e.target.value)}
                        className="border-slate-200 pl-8"
                        style={{ fontSize: '12.5px' }}
                      />
                    </div>
                  </FormField>
                </>
              )}

              {/* Security Mode */}
              <div style={{
                fontSize: '10px', fontWeight: 700, color: '#94A3B8',
                textTransform: 'uppercase', letterSpacing: '0.07em',
                marginTop: '12px', marginBottom: '8px',
              }}>
                Security Mode
              </div>

              <FormField label="Security Mode">
                <div className="flex gap-2">
                  {SECURITY_MODES.map(mode => (
                    <button
                      key={mode}
                      onClick={() => setSecurityMode(mode)}
                      style={{
                        flex: 1,
                        padding: '6px 8px',
                        borderRadius: '6px',
                        fontSize: '11.5px',
                        fontWeight: 500,
                        border: '1px solid',
                        cursor: 'pointer',
                        borderColor: form.security_mode === mode ? '#6366F1' : '#E2E8F0',
                        background: form.security_mode === mode ? '#6366F1' : '#fff',
                        color: form.security_mode === mode ? '#fff' : '#475569',
                      }}
                    >
                      {mode}
                    </button>
                  ))}
                </div>
              </FormField>

              {form.security_mode !== 'None' && (
                <>
                  <FormField label="Security Policy">
                    <Select<SecurityPolicy>
                      value={form.security_policy as SecurityPolicy}
                      onChange={v => set('security_policy', v)}
                      options={SECURITY_POLICIES.filter(p => p.value !== 'None')}
                    />
                  </FormField>

                  <FormField
                    label="Client Certificate Path"
                    hint="Absolute path to the PEM certificate file on the server filesystem"
                  >
                    <Input
                      placeholder="/certs/client_cert.pem"
                      value={form.certificate_path ?? ''}
                      onChange={e => set('certificate_path', e.target.value)}
                      className="border-slate-200"
                      style={{ fontSize: '11.5px', fontFamily: 'ui-monospace, monospace' }}
                    />
                  </FormField>

                  <FormField
                    label="Private Key Path"
                    hint="Absolute path to the PEM private key file on the server filesystem"
                  >
                    <Input
                      placeholder="/certs/client_key.pem"
                      value={form.private_key_path ?? ''}
                      onChange={e => set('private_key_path', e.target.value)}
                      className="border-slate-200"
                      style={{ fontSize: '11.5px', fontFamily: 'ui-monospace, monospace' }}
                    />
                  </FormField>

                  <button
                    onClick={handleGenerateCert}
                    disabled={generatingCert}
                    className="flex items-center gap-2 w-full justify-center transition-colors disabled:opacity-50"
                    style={{
                      padding: '7px', borderRadius: '7px', fontSize: '12px', fontWeight: 500,
                      border: '1px solid #C7D2FE', background: '#EEF2FF', color: '#6366F1', cursor: 'pointer',
                    }}
                  >
                    {generatingCert
                      ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      : <KeyRound className="w-3.5 h-3.5" />
                    }
                    {generatingCert ? 'Generating...' : 'Generate Client Certificate'}
                  </button>

                  {certMsg && (
                    <div style={{ fontSize: '11px', color: '#16A34A', background: '#F0FDF4', border: '1px solid #BBF7D0', borderRadius: '6px', padding: '8px 10px' }}>
                      {certMsg}
                    </div>
                  )}
                </>
              )}
            </div>
          )}

          {/* Error */}
          {error && (
            <div
              className="flex items-start gap-2 text-xs px-3 py-2.5 rounded-lg"
              style={{ color: '#DC2626', background: '#FEF2F2', border: '1px solid #FECACA' }}
            >
              <AlertCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
              {error}
            </div>
          )}

          <button
            onClick={handleCreate}
            style={{
              width: '100%', padding: '9px', borderRadius: '8px',
              fontSize: '12.5px', fontWeight: 500,
              background: '#6366F1', color: '#fff', border: 'none', cursor: 'pointer',
            }}
          >
            Create Connection
          </button>
        </div>
      </DialogContent>
    </Dialog>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────

export default function ConnectionsPage() {
  const { removeTagsByConnection } = useWatchlist()

  const [connections, setConnections]       = useState<Connection[]>([])
  const [loadingId, setLoadingId]           = useState<number | null>(null)
  const [connectionErrors, setConnectionErrors] = useState<Record<number, string>>({})

  const fetchConnections = useCallback(async () => {
    const res = await connectionsApi.list()
    setConnections(res.data)
  }, [])

  useEffect(() => { fetchConnections() }, [fetchConnections])

  const handleDelete = async (id: number) => {
    removeTagsByConnection(id)
    await connectionsApi.delete(id)
    setConnectionErrors(prev => { const n = { ...prev }; delete n[id]; return n })
    fetchConnections()
  }

  const handleConnect = async (id: number) => {
    setLoadingId(id)
    setConnectionErrors(prev => { const n = { ...prev }; delete n[id]; return n })
    try {
      await connectionsApi.connect(id)
      fetchConnections()
    } catch (e) {
      const err = e as { response?: { data?: { detail?: string } } }
      const msg = err.response?.data?.detail || 'Failed to connect.'
      setConnectionErrors(prev => ({ ...prev, [id]: msg }))
      fetchConnections()
    } finally {
      setLoadingId(null)
    }
  }

  const handleDisconnect = async (id: number) => {
    setLoadingId(id)
    try {
      await connectionsApi.disconnect(id)
      fetchConnections()
    } catch (e) {
      console.error('Failed to disconnect:', e)
    } finally {
      setLoadingId(null)
    }
  }

  const total       = connections.length
  const connected   = connections.filter(c => c.is_active).length
  const disconnected = total - connected

  return (
    <div className="p-8 max-w-5xl mx-auto">

      {/* ── Header ── */}
      <div className="flex items-start justify-between mb-8">
        <div>
          <h1 style={{ fontSize: '20px', fontWeight: 600, color: '#0F172A', letterSpacing: '-0.02em' }}>
            OPC UA Connections
          </h1>
          <p style={{ fontSize: '12.5px', color: '#94A3B8', marginTop: '4px' }}>
            Manage your OPC UA server connections
          </p>
        </div>
        <AddConnectionForm onCreated={fetchConnections} />
      </div>

      {/* ── Stat cards ── */}
      {total > 0 && (
        <div className="grid grid-cols-3 gap-4 mb-7">
          {[
            { icon: <Cable className="w-4 h-4" />, value: total,       label: 'Total Connections', iconStyle: { background: '#EEF2FF', color: '#6366F1' } },
            { icon: <CheckCircle2 className="w-4 h-4" />, value: connected,    label: 'Connected',         iconStyle: { background: '#F0FDF4', color: '#16A34A' }, valueColor: connected > 0 ? '#16A34A' : undefined },
            { icon: <AlertCircle className="w-4 h-4" />, value: disconnected,  label: 'Disconnected',      iconStyle: { background: '#FFFBEB', color: '#D97706' }, valueColor: disconnected > 0 ? '#D97706' : undefined },
          ].map(s => (
            <div key={s.label} className="card flex items-center gap-3 px-4 py-3.5">
              <div className="flex items-center justify-center shrink-0"
                   style={{ width: '36px', height: '36px', borderRadius: '8px', ...s.iconStyle }}>
                {s.icon}
              </div>
              <div>
                <div style={{ fontSize: '22px', fontWeight: 700, letterSpacing: '-0.03em', lineHeight: 1, color: s.valueColor ?? '#0F172A' }}>
                  {s.value}
                </div>
                <div style={{ fontSize: '11px', color: '#94A3B8', marginTop: '3px', fontWeight: 500 }}>
                  {s.label}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ── Empty state ── */}
      {connections.length === 0 ? (
        <div className="card flex flex-col items-center justify-center py-16 text-center">
          <div style={{ width: '48px', height: '48px', borderRadius: '12px', background: '#F8FAFC', border: '1px solid #E2E8F0', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 12px' }}>
            <Cable className="w-5 h-5" style={{ color: '#CBD5E1' }} />
          </div>
          <p style={{ fontSize: '13.5px', fontWeight: 600, color: '#475569' }}>No connections yet</p>
          <p style={{ fontSize: '12px', color: '#94A3B8', marginTop: '4px' }}>
            Click "Add Connection" to connect to an OPC UA server
          </p>
        </div>
      ) : (
        <div className="card overflow-hidden">

          {/* Table head */}
          <div style={{
            display: 'grid', gridTemplateColumns: '1fr 2fr 140px 110px 160px',
            gap: '12px', padding: '9px 16px',
            background: '#F8FAFC', borderBottom: '1px solid #E2E8F0',
          }}>
            {['Name', 'Endpoint', 'Status', 'Created', 'Actions'].map(h => (
              <span key={h} style={{ fontSize: '10.5px', fontWeight: 600, color: '#94A3B8', textTransform: 'uppercase', letterSpacing: '0.07em' }}>
                {h}
              </span>
            ))}
          </div>

          {connections.map((conn, i) => (
            <div key={conn.id}>
              <div
                style={{
                  display: 'grid', gridTemplateColumns: '1fr 2fr 140px 110px 160px',
                  gap: '12px', padding: '13px 16px', alignItems: 'center',
                  borderBottom: i < connections.length - 1 ? '1px solid #F1F5F9' : 'none',
                }}
                onMouseEnter={e => (e.currentTarget.style.background = '#FAFBFF')}
                onMouseLeave={e => (e.currentTarget.style.background = '')}
              >
                {/* Name */}
                <div className="flex items-center gap-2.5 min-w-0">
                  <div style={{
                    width: '28px', height: '28px', borderRadius: '7px',
                    background: conn.is_active ? '#EEF2FF' : '#F8FAFC',
                    border: `1px solid ${conn.is_active ? '#C7D2FE' : '#E2E8F0'}`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
                  }}>
                    <Server className="w-3.5 h-3.5" style={{ color: conn.is_active ? '#6366F1' : '#CBD5E1' }} />
                  </div>
                  <div className="min-w-0">
                    <div style={{ fontSize: '13px', fontWeight: 600, color: '#0F172A' }} className="truncate">
                      {conn.name}
                    </div>
                    <div className="flex items-center gap-1.5 mt-0.5 flex-wrap">
                      <SecurityBadge mode={conn.security_mode} />
                      {conn.auth_type === 'username' && (
                        <span style={{ fontSize: '10px', color: '#94A3B8' }}>
                          👤 {/* username auth indicator */}
                        </span>
                      )}
                      {conn.retry_count > 0 && (
                        <span style={{ fontSize: '10.5px', color: '#EF4444' }}>
                          {conn.retry_count} failed
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                {/* Endpoint */}
                <span className="truncate" style={{
                  display: 'inline-block', background: '#F8FAFC',
                  border: '1px solid #E2E8F0', borderRadius: '5px',
                  padding: '3px 8px', fontFamily: 'ui-monospace, monospace',
                  fontSize: '11.5px', color: '#475569', maxWidth: '100%',
                }}>
                  {conn.endpoint}
                </span>

                {/* Status */}
                <StatusBadge active={conn.is_active} />

                {/* Created */}
                <span style={{ fontSize: '12px', color: '#94A3B8' }}>
                  {new Date(conn.created_at).toLocaleDateString()}
                </span>

                {/* Actions */}
                <div className="flex items-center gap-1.5">
                  {conn.is_active ? (
                    <button
                      disabled={loadingId === conn.id}
                      onClick={() => handleDisconnect(conn.id)}
                      className="flex items-center gap-1.5 transition-colors disabled:opacity-50"
                      style={{ padding: '5px 11px', borderRadius: '7px', fontSize: '12px', fontWeight: 500, border: '1px solid #E2E8F0', background: '#fff', color: '#475569', cursor: 'pointer' }}
                    >
                      {loadingId === conn.id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <PowerOff className="w-3.5 h-3.5" />}
                      Disconnect
                    </button>
                  ) : (
                    <button
                      disabled={loadingId === conn.id}
                      onClick={() => handleConnect(conn.id)}
                      className="flex items-center gap-1.5 transition-colors disabled:opacity-50"
                      style={{ padding: '5px 11px', borderRadius: '7px', fontSize: '12px', fontWeight: 500, border: '1px solid #6366F1', background: '#6366F1', color: '#fff', cursor: 'pointer' }}
                    >
                      {loadingId === conn.id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Power className="w-3.5 h-3.5" />}
                      Connect
                    </button>
                  )}

                  <button
                    onClick={() => handleDelete(conn.id)}
                    style={{ width: '30px', height: '30px', display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: '7px', border: '1px solid #E2E8F0', background: '#fff', color: '#CBD5E1', cursor: 'pointer' }}
                    onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.color = '#DC2626'; (e.currentTarget as HTMLButtonElement).style.borderColor = '#FECACA'; (e.currentTarget as HTMLButtonElement).style.background = '#FEF2F2' }}
                    onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.color = '#CBD5E1'; (e.currentTarget as HTMLButtonElement).style.borderColor = '#E2E8F0'; (e.currentTarget as HTMLButtonElement).style.background = '#fff' }}
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>

              {/* Error row */}
              {connectionErrors[conn.id] && (
                <div className="flex items-start gap-2 px-4 py-2.5 text-xs"
                     style={{ background: '#FEF2F2', borderBottom: '1px solid #FECACA', color: '#DC2626' }}>
                  <AlertCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                  {connectionErrors[conn.id]}
                </div>
              )}

              {/* Connected since */}
              {conn.last_connected_at && conn.is_active && (
                <div className="flex items-center gap-2 px-4 py-1.5 text-xs"
                     style={{ background: '#F0FDF4', borderBottom: '1px solid #BBF7D0', color: '#16A34A' }}>
                  <CheckCircle2 className="w-3.5 h-3.5 shrink-0" />
                  Connected since {new Date(conn.last_connected_at).toLocaleTimeString()}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
