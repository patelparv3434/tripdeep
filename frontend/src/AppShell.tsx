import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { BrowserRouter, HashRouter, NavLink, Route, Routes, useLocation } from 'react-router-dom'
import { AlertTriangle, ArrowRight, BriefcaseBusiness, Check, Compass, FileText, LogOut, Menu, Plus, Sparkles, X } from 'lucide-react'
import { apiFetch, supabase, type Session } from './supabase'
import './tripdeep.css'
import './workflow.css'

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? ''
const CLOUD_AI_ENABLED = import.meta.env.VITE_CLOUD_AI_ENABLED === 'true'
const PREVIEW_ONLY = import.meta.env.VITE_PREVIEW_ONLY === 'true'
const AppRouter = PREVIEW_ONLY ? HashRouter : BrowserRouter

type TripForm = {
  origin: string
  destination: string
  start_date: string
  end_date: string
  adults: string
  children: string
  child_ages: string
  travel_mode: string
  hotel_category: string
  food_preference: string
}

type PlanSection = {
  id: string
  title: string
  status: string
  summary: string
  items: Array<Record<string, unknown>>
  details?: Record<string, unknown>
  sources?: string[]
  updated_at?: string | null
}

type TripPlan = {
  title: string
  origin: string
  destination: string
  start_date: string
  end_date: string
  traveler_count: number
  sections: PlanSection[]
}

type SavedTrip = {
  id: string
  title: string
  origin: string
  destination: string
  status: string
  request_data: Record<string, unknown>
}

type PlanTabId = 'overview' | 'weather' | 'stays' | 'itinerary' | 'clothing' | 'essentials'

const PLAN_TABS: Array<{ id: PlanTabId; label: string; sectionIds: string[] }> = [
  { id: 'overview', label: 'Overview', sectionIds: [] },
  { id: 'weather', label: 'Weather', sectionIds: ['weather'] },
  { id: 'stays', label: 'Stays', sectionIds: ['hotels'] },
  { id: 'itinerary', label: 'Itinerary', sectionIds: ['activities', 'itinerary'] },
  { id: 'clothing', label: 'Clothing', sectionIds: ['clothing'] },
  { id: 'essentials', label: 'Essentials', sectionIds: ['documents', 'packing', 'transport', 'budget', 'insurance', 'food'] },
]

const navItems = [
  ['/', 'Plan a trip', Sparkles],
  ['/documents', 'Travel documents', FileText],
] as const

function dateAfter(days: number): string {
  const date = new Date()
  date.setDate(date.getDate() + days)
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

const initialForm: TripForm = {
  origin: '',
  destination: '',
  start_date: dateAfter(7),
  end_date: dateAfter(10),
  adults: '1',
  children: '0',
  child_ages: '',
  travel_mode: 'Flight',
  hotel_category: 'Hotel / Guest house',
  food_preference: '',
}

export default function AppShell() {
  const [apiState, setApiState] = useState<'loading' | 'connected' | 'offline'>(PREVIEW_ONLY ? 'offline' : 'loading')
  const [menuOpen, setMenuOpen] = useState(false)
  const [session, setSession] = useState<Session | null>(null)
  const [authReady, setAuthReady] = useState(!supabase)

  useEffect(() => {
    if (PREVIEW_ONLY) return
    let active = true
    apiFetch(`${API_BASE}/api/health`)
      .then((response) => {
        if (!response.ok) throw new Error('API is unavailable')
        return response.json() as Promise<{ status: string }>
      })
      .then((health) => {
        if (active) setApiState(health.status === 'healthy' ? 'connected' : 'offline')
      })
      .catch(() => {
        if (active) setApiState('offline')
      })
    return () => { active = false }
  }, [])

  useEffect(() => {
    if (!supabase) return
    let active = true
    void supabase.auth.getSession().then(({ data }) => {
      if (active) {
        setSession(data.session)
        setAuthReady(true)
      }
    })
    const { data: listener } = supabase.auth.onAuthStateChange((_event, nextSession) => {
      setSession(nextSession)
      setAuthReady(true)
    })
    return () => {
      active = false
      listener.subscription.unsubscribe()
    }
  }, [])

  if (supabase && !authReady) {
    return <main className="page-content"><p role="status">Checking your session…</p></main>
  }
  if (supabase && !session) return <AuthPage />
  const signOut = () => {
    if (supabase) void supabase.auth.signOut()
  }

  return <AppRouter basename={PREVIEW_ONLY ? undefined : import.meta.env.BASE_URL}>
    <div className="app-shell">
      <aside className={`sidebar ${menuOpen ? 'sidebar-open' : ''}`}>
        <div className="brand-lockup">
          <div className="brand-mark"><Compass size={20} /></div>
          <div><span className="brand-name">tripdeep</span><span className="brand-caption">TRAVEL PLANNING</span></div>
          <button className="icon-button sidebar-close" aria-label="Close navigation" onClick={() => setMenuOpen(false)}><X size={18} /></button>
        </div>
        <div className="workspace-switcher">
          <span className="workspace-avatar">TD</span>
          <span className="workspace-copy"><strong>Tripdeep workspace</strong><small>{PREVIEW_ONLY ? 'Static preview' : 'Personal account'}</small></span>
        </div>
        <div className="nav-label">YOUR WORKSPACE</div>
        <nav className="primary-nav" aria-label="Main navigation">
          {navItems.map(([to, label, Icon]) => <NavLink
            key={to}
            to={to}
            end={to === '/'}
            onClick={() => setMenuOpen(false)}
            className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
          ><Icon size={18} /><span>{label}</span></NavLink>)}
        </nav>
        <div className="sidebar-spacer" />
        <div className="help-card"><span className="help-icon"><BriefcaseBusiness size={17} /></span><div><strong>Plan with confidence</strong><span>One place for your trip details</span></div></div>
        <div className="profile-row"><div className="profile-avatar">{session?.user.email?.slice(0, 1).toUpperCase() ?? 'P'}</div><div className="profile-copy"><strong>{session?.user.email ?? (PREVIEW_ONLY ? 'GitHub Pages preview' : 'Local workspace')}</strong><span>{session ? 'Signed in' : PREVIEW_ONLY ? 'No account or saved data' : 'Development account'}</span></div>{session && supabase && <button className="icon-button" aria-label="Sign out" title="Sign out" onClick={signOut}><LogOut size={16} /></button>}</div>
      </aside>
      {menuOpen && <button className="mobile-scrim" aria-label="Close menu" onClick={() => setMenuOpen(false)} />}
      <main className="main-area">
        <header className="topbar">
          <button className="icon-button mobile-menu" aria-label="Open navigation" onClick={() => setMenuOpen(true)}><Menu size={20} /></button>
          <div className="breadcrumbs"><span>Workspace</span><span className="crumb-slash">/</span><strong><CurrentSection /></strong></div>
          <div className="topbar-actions"><div className={`connection-pill ${apiState}`}><span className="connection-dot" />{PREVIEW_ONLY ? 'Static preview' : apiState === 'connected' ? 'Ready to plan' : apiState === 'offline' ? 'API offline' : 'Connecting'}</div><div className="top-avatar">P</div></div>
        </header>
        {PREVIEW_ONLY
          ? <div className="system-banner"><AlertTriangle size={16} /><span>GitHub Pages hosts this static preview only. Sign-in, trip planning, saved trips, and document uploads need a backend and are disabled here.</span></div>
          : apiState === 'offline' && <div className="system-banner"><AlertTriangle size={16} /><span>Trip services are unavailable. Check that the API service is running.</span></div>}
        <Routes>
          <Route path="/" element={<TripPlannerPage />} />
          <Route path="/trips" element={<TripPlannerPage />} />
          <Route path="/documents" element={<DocumentsPage />} />
          <Route path="*" element={<TripPlannerPage />} />
        </Routes>
        <footer className="app-footer"><span>TRIPDEEP · TRAVEL PLANNER</span><span><i className="footer-dot" />{PREVIEW_ONLY ? 'Static preview · trip details are not saved' : 'Your travel details are private to your account'}</span></footer>
      </main>
    </div>
  </AppRouter>
}

function AuthPage() {
  const [isSignUp, setIsSignUp] = useState(false)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState(PREVIEW_ONLY ? 'Document storage is unavailable in the static GitHub Pages preview.' : '')

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!supabase) return
    const form = new FormData(event.currentTarget)
    const email = String(form.get('email') ?? '').trim()
    const password = String(form.get('password') ?? '')
    setBusy(true)
    setMessage('')
    try {
      const result = isSignUp
        ? await supabase.auth.signUp({ email, password })
        : await supabase.auth.signInWithPassword({ email, password })
      if (result.error) throw result.error
      if (isSignUp && !result.data.session) {
        setMessage('Check your email to confirm your account, then sign in.')
      }
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : 'Authentication failed.')
    } finally {
      setBusy(false)
    }
  }

  return <main className="page-content">
    <section className="form-panel" style={{ maxWidth: 460, margin: '10vh auto' }}>
      <div className="eyebrow"><i className="eyebrow-rule" />TRIPDEEP ACCOUNT</div>
      <h1>{isSignUp ? 'Create your account' : 'Sign in to Tripdeep'}</h1>
      <p className="page-intro">Your trips and uploaded documents are private to your account.</p>
      <form className="dynamic-form" onSubmit={(event) => void submit(event)}>
        <label className="field-label"><span>Email</span><input name="email" required type="email" autoComplete="email" /></label>
        <label className="field-label"><span>Password</span><input name="password" required type="password" minLength={8} autoComplete={isSignUp ? 'new-password' : 'current-password'} /></label>
        {message && <p role="status" className="trip-message">{message}</p>}
        <button className="primary-button" disabled={busy} type="submit">{busy ? 'Please wait…' : isSignUp ? 'Create account' : 'Sign in'}</button>
      </form>
      <p className="trip-message">{isSignUp ? 'Already registered?' : 'New to Tripdeep?'} <button className="text-button" type="button" onClick={() => { setIsSignUp((value) => !value); setMessage('') }}>{isSignUp ? 'Sign in' : 'Create an account'}</button></p>
    </section>
  </main>
}

function CurrentSection() {
  const { pathname } = useLocation()
  return pathname === '/documents' ? 'Travel documents' : 'Plan a trip'
}

function TripPlannerPage() {
  const [form, setForm] = useState<TripForm>(initialForm)
  const [trips, setTrips] = useState<SavedTrip[]>([])
  const [activeTripId, setActiveTripId] = useState<string | null>(null)
  const [plan, setPlan] = useState<TripPlan | null>(null)
  const [busy, setBusy] = useState(false)
  const [phase, setPhase] = useState('')
  const [error, setError] = useState('')
  const [cloudAiStyleNotes, setCloudAiStyleNotes] = useState(false)

  const loadTrips = async () => {
    if (PREVIEW_ONLY) return
    const response = await apiFetch(`${API_BASE}/api/trips`)
    if (!response.ok) throw new Error('Saved trips could not be loaded.')
    const data = await response.json() as { trips: SavedTrip[] }
    setTrips(data.trips)
  }

  useEffect(() => {
    if (PREVIEW_ONLY) return
    let active = true
    apiFetch(`${API_BASE}/api/trips`)
      .then((response) => {
        if (!response.ok) throw new Error('Saved trips could not be loaded.')
        return response.json() as Promise<{ trips: SavedTrip[] }>
      })
      .then(({ trips: loaded }) => { if (active) setTrips(loaded) })
      .catch((caught: unknown) => { if (active) setError(caught instanceof Error ? caught.message : 'Saved trips could not be loaded.') })
    return () => { active = false }
  }, [])

  const createPlan = async (tripId: string) => {
    if (PREVIEW_ONLY) return
    setBusy(true)
    setError('')
    setPlan(null)
    setActiveTripId(tripId)
    setPhase('Finding current destination information and organizing your trip…')
    try {
      const response = await apiFetch(`${API_BASE}/api/trips/${tripId}/plan`, { method: 'POST' })
      const data = await response.json() as { plan?: TripPlan; detail?: string }
      if (!response.ok || !data.plan) throw new Error(data.detail ?? 'Your trip could not be planned.')
      setPlan(data.plan)
      setPhase('Your trip plan is ready')
      await loadTrips()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Your trip could not be planned.')
      setPhase('')
    } finally {
      setBusy(false)
    }
  }

  const submitTrip = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (PREVIEW_ONLY) return
    setBusy(true)
    setPlan(null)
    setError('')
    setPhase('Saving your trip details…')
    try {
      const childAges = form.child_ages.split(',').map((age) => age.trim()).filter(Boolean).map(Number)
      const response = await apiFetch(`${API_BASE}/api/trips`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          origin: form.origin.trim(),
          destination: form.destination.trim(),
          start_date: form.start_date,
          end_date: form.end_date,
          adults: Number(form.adults),
          children: Number(form.children),
          child_ages: childAges,
          travel_mode: form.travel_mode,
          hotel_category: form.hotel_category,
          food_preference: form.food_preference || null,
          cloud_ai_style_notes: cloudAiStyleNotes,
          cancellation_required: true,
        }),
      })
      const trip = await response.json() as { id?: string; detail?: string }
      if (!response.ok || !trip.id) throw new Error(formatApiError(trip.detail, 'Trip could not be saved.'))
      setActiveTripId(trip.id)
      setPhase('Checking live destination information and preparing your plan…')
      const planResponse = await apiFetch(`${API_BASE}/api/trips/${trip.id}/plan`, { method: 'POST' })
      const result = await planResponse.json() as { plan?: TripPlan; detail?: string }
      if (!planResponse.ok || !result.plan) throw new Error(result.detail ?? 'Your trip was saved, but the plan could not be generated.')
      setPlan(result.plan)
      setPhase('Your trip plan is ready')
      await loadTrips()
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'Your trip could not be planned.')
      setPhase('')
      try { await loadTrips() } catch { /* Keep the original planning error visible. */ }
    } finally {
      setBusy(false)
    }
  }

  const openSavedTrip = async (trip: SavedTrip) => {
    if (PREVIEW_ONLY) return
    setActiveTripId(trip.id)
    setError('')
    setPlan(null)
    setBusy(true)
    setPhase('Opening your saved trip…')
    try {
      const response = await apiFetch(`${API_BASE}/api/trips/${trip.id}/plan`)
      if (response.ok) {
        const result = await response.json() as { plan: TripPlan }
        setPlan(result.plan)
        setPhase('')
      } else if (response.status === 404) {
        await createPlan(trip.id)
      } else {
        const result = await response.json() as { detail?: string }
        throw new Error(result.detail ?? 'The saved trip could not be opened.')
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : 'The saved trip could not be opened.')
      setPhase('')
    } finally {
      setBusy(false)
    }
  }

  const change = (key: keyof TripForm, value: string) => setForm((current) => ({ ...current, [key]: value }))
  const travelers = Number(form.adults || 0) + Number(form.children || 0)

  return <div className="page-content planner-page">
    <div className="welcome-row">
      <div><div className="eyebrow"><i className="eyebrow-rule" />YOUR NEXT JOURNEY</div><h1>Plan a trip, <em>your way.</em></h1><p className="page-intro">Tell us what you need. We’ll bring your travel details together in one clear plan.</p></div>
      <span className="traveler-count"><BriefcaseBusiness size={16} />{travelers} {travelers === 1 ? 'traveler' : 'travelers'}</span>
    </div>

    <div className="trip-workspace planner-workspace">
      <section className="form-panel trip-input-panel">
        <div className="panel-topline"><div><h3>Your trip details</h3><p>Share the basics to get a plan tailored to your trip.</p></div><span className="panel-counter">TRIP DETAILS</span></div>
        <form className="dynamic-form trip-input-form" onSubmit={(event) => void submitTrip(event)}>
          <label className="field-label"><span>From <b>*</b></span><input required value={form.origin} onChange={(event) => change('origin', event.target.value)} placeholder="City or airport" /></label>
          <label className="field-label"><span>To <b>*</b></span><input required value={form.destination} onChange={(event) => change('destination', event.target.value)} placeholder="Where would you like to go?" /></label>
          <label className="field-label"><span>Start date <b>*</b></span><input required type="date" min={dateAfter(0)} value={form.start_date} onChange={(event) => change('start_date', event.target.value)} /></label>
          <label className="field-label"><span>End date <b>*</b></span><input required type="date" min={form.start_date || dateAfter(0)} value={form.end_date} onChange={(event) => change('end_date', event.target.value)} /></label>
          <label className="field-label"><span>Adults <b>*</b></span><input required type="number" min="1" value={form.adults} onChange={(event) => change('adults', event.target.value)} /></label>
          <label className="field-label"><span>Children</span><input type="number" min="0" value={form.children} onChange={(event) => change('children', event.target.value)} /></label>
          {Number(form.children) > 0 && <label className="field-label"><span>Children’s ages</span><input value={form.child_ages} onChange={(event) => change('child_ages', event.target.value)} placeholder="For example: 6, 10" /><small>Enter one age per child, separated by commas.</small></label>}
          <label className="field-label"><span>Travel mode</span><select value={form.travel_mode} onChange={(event) => change('travel_mode', event.target.value)}>{['Flight', 'Train', 'Bus', 'By roads'].map((mode) => <option key={mode}>{mode}</option>)}</select></label>
          <label className="field-label"><span>Stay preference</span><select value={form.hotel_category} onChange={(event) => change('hotel_category', event.target.value)}>{['Hotel / Guest house', '5 Star', '4 Star', '3 Star', 'Resorts'].map((category) => <option key={category}>{category}</option>)}</select></label>
          <label className="field-label"><span>Food preference</span><select value={form.food_preference} onChange={(event) => change('food_preference', event.target.value)}><option value="">No preference</option>{['Vegetarian', 'Vegan', 'Jain', 'Halal'].map((preference) => <option key={preference}>{preference}</option>)}</select></label>
          {CLOUD_AI_ENABLED && <label className="checkbox-field"><input type="checkbox" checked={cloudAiStyleNotes} onChange={(event) => setCloudAiStyleNotes(event.target.checked)} /><span>Allow optional cloud AI clothing tips</span><small>Only coarse weather, suggested clothing and generic activity types are sent; not your destination, travel dates, names or uploaded documents.</small></label>}
          {error && <div className="form-error planner-error" role="alert"><AlertTriangle size={16} />{error}</div>}
          <button className="primary-button execute-button plan-submit" disabled={busy || PREVIEW_ONLY} type="submit">{PREVIEW_ONLY ? 'Planning unavailable in static preview' : busy ? <><span className="spinner" />Planning your trip…</> : <><Sparkles size={16} />Create my trip plan</>}</button>
        </form>
        {phase && <p className="trip-message planner-phase" role="status">{busy && <span className="spinner" />} {!busy && <Check size={14} />}{phase}</p>}
      </section>

      <aside className="trip-list-panel saved-trip-panel">
        <div className="panel-topline"><div><h3>Saved trips</h3><p>Pick up where you left off.</p></div><span className="panel-counter">{trips.length}</span></div>
        {trips.length ? trips.slice(0, 8).map((trip) => <button className={`saved-trip ${activeTripId === trip.id ? 'selected' : ''}`} key={trip.id} disabled={busy} onClick={() => void openSavedTrip(trip)}>
          <span className="trip-route"><strong>{trip.origin}</strong><i /><strong>{trip.destination}</strong></span><small>{String(trip.request_data.start_date ?? '')} · {trip.status.replaceAll('_', ' ')}</small>
        </button>) : <EmptyState title={PREVIEW_ONLY ? 'Trip planning is not connected' : 'Your trips will appear here'} detail={PREVIEW_ONLY ? 'The GitHub Pages preview cannot create or save trips.' : 'Create a trip to save its details and plan.'} />}
        <div className="data-note"><span className="note-tag">SOURCED DETAILS</span><p>Forecasts and map listings are linked to their sources. Booking prices and availability are only shown when confirmed by a provider.</p></div>
      </aside>
    </div>

    {plan && <TripPlanView plan={plan} onRegenerate={() => activeTripId && void createPlan(activeTripId)} />}
  </div>
}

function formatApiError(detail: string | undefined, fallback: string): string {
  if (!detail) return fallback
  try {
    const errors = JSON.parse(detail) as Array<{ msg?: string; loc?: Array<string | number> }>
    if (Array.isArray(errors)) return errors.map((error) => `${error.loc?.slice(-1)[0] ?? 'Input'}: ${error.msg ?? 'invalid value'}`).join('. ')
  } catch { return detail }
  return detail
}

function TripPlanView({ plan, onRegenerate }: { plan: TripPlan; onRegenerate: () => void }) {
  const [activeTab, setActiveTab] = useState<PlanTabId>('overview')
  const tabRefs = useRef<Array<HTMLButtonElement | null>>([])
  const selectedTab = PLAN_TABS.find((tab) => tab.id === activeTab) ?? PLAN_TABS[0]
  const activeSections = plan.sections.filter((section) => selectedTab.sectionIds.includes(section.id))

  const selectTab = (tabId: PlanTabId) => {
    setActiveTab(tabId)
    const tabIndex = PLAN_TABS.findIndex((tab) => tab.id === tabId)
    tabRefs.current[tabIndex]?.focus()
  }

  const handleTabKeyDown = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    let nextIndex: number
    if (event.key === 'ArrowRight') nextIndex = (index + 1) % PLAN_TABS.length
    else if (event.key === 'ArrowLeft') nextIndex = (index - 1 + PLAN_TABS.length) % PLAN_TABS.length
    else if (event.key === 'Home') nextIndex = 0
    else if (event.key === 'End') nextIndex = PLAN_TABS.length - 1
    else return
    event.preventDefault()
    selectTab(PLAN_TABS[nextIndex].id)
  }

  return <section className="trip-results" aria-live="polite">
    <div className="trip-result-heading"><div><div className="eyebrow"><i className="eyebrow-rule" />YOUR PERSONAL TRIP PLAN</div><h2>{plan.title}</h2><p className="page-intro">{plan.origin} to {plan.destination} · {formatDate(plan.start_date)} – {formatDate(plan.end_date)} · {plan.traveler_count} {plan.traveler_count === 1 ? 'traveler' : 'travelers'}</p></div><span className="result-ready"><Check size={15} />Plan ready</span></div>
    <div className="plan-tabs" role="tablist" aria-label="Trip plan sections">
      {PLAN_TABS.map((tab, index) => <button
        key={tab.id}
        ref={(element) => { tabRefs.current[index] = element }}
        id={`trip-tab-${tab.id}`}
        className={`plan-tab ${activeTab === tab.id ? 'active' : ''}`}
        type="button"
        role="tab"
        aria-selected={activeTab === tab.id}
        aria-controls="trip-plan-panel"
        tabIndex={activeTab === tab.id ? 0 : -1}
        onClick={() => selectTab(tab.id)}
        onKeyDown={(event) => handleTabKeyDown(event, index)}
      >{tab.label}</button>)}
    </div>
    <div id="trip-plan-panel" className="plan-tab-panel" role="tabpanel" aria-labelledby={`trip-tab-${activeTab}`} tabIndex={0}>
      {activeTab === 'overview'
        ? <PlanOverview plan={plan} onNavigate={selectTab} />
        : activeSections.length
          ? <div className={`plan-section-grid ${activeSections.length === 1 ? 'single-card' : ''}`}>{activeSections.map((section) => <PlanSectionCard key={section.id} section={section} />)}</div>
          : <div className="plan-tab-empty"><p>This saved plan does not have this section yet.</p><button className="primary-button" type="button" onClick={onRegenerate}>Refresh this plan</button></div>}
    </div>
    <p className="plan-disclaimer">Recommendations use the linked data sources where available. Map listings are not confirmed bookings; rates, room availability, schedules, opening hours and policy terms require confirmation from the relevant provider.</p>
  </section>
}

function PlanOverview({ plan, onNavigate }: { plan: TripPlan; onNavigate: (tab: PlanTabId) => void }) {
  const sections = new Map(plan.sections.map((section) => [section.id, section]))
  const weather = sections.get('weather')
  const stays = sections.get('hotels')
  const itinerary = sections.get('itinerary')
  const clothing = sections.get('clothing')
  const forecastDays = weather?.items.filter((item) => item.forecast_available !== false).length ?? 0
  const essentialsCount = plan.sections.filter((section) => PLAN_TABS.find((tab) => tab.id === 'essentials')?.sectionIds.includes(section.id)).length
  const summaries: Array<{ tab: PlanTabId; title: string; value: string; description: string }> = [
    { tab: 'weather', title: 'Weather', value: `${forecastDays} / ${weather?.items.length ?? 0} days`, description: weather?.summary ?? 'No forecast details saved.' },
    { tab: 'stays', title: 'Stays', value: `${stays?.items.length ?? 0} nearby listings`, description: stays?.summary ?? 'No stay suggestions saved.' },
    { tab: 'itinerary', title: 'Itinerary', value: `${itinerary?.items.length ?? 0} planned days`, description: itinerary?.summary ?? 'No itinerary saved.' },
    { tab: 'clothing', title: 'Clothing', value: `${clothing?.items.length ?? 0} daily suggestions`, description: clothing?.summary ?? 'No clothing suggestions saved.' },
    { tab: 'essentials', title: 'Essentials', value: `${essentialsCount} categories`, description: 'Documents, travel cover, finance, transport and other trip details.' },
  ]

  return <div className="plan-overview-grid">
    {summaries.map((summary) => <button className="plan-overview-card" key={summary.tab} type="button" onClick={() => onNavigate(summary.tab)}>
      <span>{summary.title}<ArrowRight size={13} /></span>
      <strong>{summary.value}</strong>
      <small>{summary.description}</small>
    </button>)}
  </div>
}

function formatDate(value: string): string {
  if (!value) return ''
  return new Date(`${value}T12:00:00`).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
}

function PlanSectionCard({ section }: { section: PlanSection }) {
  return <article className={`plan-section-card plan-${section.id}`}>
    <div className="plan-card-topline"><h3>{section.title}</h3><span className={`plan-source-status ${sectionStatusClass(section)}`}>{sectionStatusLabel(section)}</span></div>
    <p className="plan-summary">{section.summary}</p>
    {section.items?.length > 0 ? <PlanItems section={section} /> : null}
    {section.details && Object.keys(section.details).length > 0 && <InfoDetails details={section.details} />}
    {!!section.sources?.length && <div className="plan-sources">{section.sources.map((source) => <a key={source} href={source} target="_blank" rel="noreferrer">View source <ArrowRight size={12} /></a>)}</div>}
    {section.updated_at && <small className="plan-updated">Retrieved {new Date(section.updated_at).toLocaleString()}</small>}
  </article>
}

function sectionStatusClass(section: PlanSection): string {
  if (section.id === 'weather' && ['AVAILABLE', 'PARTIAL'].includes(section.status)) return 'live'
  if (section.id === 'hotels' && section.status === 'available') return 'live'
  if (section.id === 'activities' && section.status === 'available') return 'live'
  if (section.id === 'itinerary' && section.status === 'available') return 'live'
  if (section.id === 'clothing' && section.status === 'available') return 'live'
  return 'limited'
}

function sectionStatusLabel(section: PlanSection): string {
  if (section.id === 'weather' && section.status === 'AVAILABLE') return 'Live forecast'
  if (section.id === 'weather' && section.status === 'PARTIAL') return 'Partial forecast'
  if (section.id === 'hotels' && section.status === 'available') return 'Nearby listings'
  if (section.id === 'activities' && section.status === 'available') return 'Nearby places'
  if (section.id === 'itinerary' && section.status === 'available') return 'Suggested plan'
  if (section.id === 'clothing' && section.status === 'available') return 'Weather matched'
  if (section.id === 'clothing') return 'General guidance'
  if (section.id === 'packing') return 'General guidance'
  if (section.id === 'food' && section.status === 'needs_input') return 'Needs confirmation'
  if (section.id === 'documents') return section.status === 'needs_review' ? 'Review documents' : 'Checklist'
  if (section.id === 'insurance' && section.status === 'needs_review') return 'Policy review needed'
  if (section.id === 'budget') return 'Verified costs only'
  return 'Limited data'
}

function PlanItems({ section }: { section: PlanSection }) {
  if (section.id === 'weather') return <div className="weather-day-list">{section.items.map((item) => <div className={`weather-day ${item.forecast_available === false ? 'forecast-pending' : ''}`} key={String(item.date)}><strong>{formatDate(String(item.date))}</strong>{item.forecast_available === false ? <span>Forecast pending</span> : <><span>{String(item.condition ?? 'Forecast')}</span><span>{item.high_c != null && item.low_c != null ? `${String(item.high_c)}° / ${String(item.low_c)}°C` : 'Temperatures unavailable'}</span>{item.precipitation_probability_percent != null && <small>{String(item.precipitation_probability_percent)}% rain</small>}</>}</div>)}</div>
  if (section.id === 'itinerary') return <div className="itinerary-list">{section.items.map((day) => {
    const activities = Array.isArray(day.activities) ? day.activities as Array<Record<string, unknown>> : []
    return <article className="itinerary-day" key={String(day.date)}><div className="itinerary-day-heading"><strong>{formatDate(String(day.date))}</strong><span>{String(day.weather_summary ?? '')}</span></div>{activities.length ? <ul>{activities.map((activity, index) => <li key={`${String(activity.name ?? index)}-${index}`}><span>{String(activity.time_of_day ?? 'Suggested stop')}</span><div><strong>{String(activity.name ?? 'Suggested place')}</strong><small>{String(activity.type ?? 'Place')}</small></div>{typeof activity.source === 'string' && <a href={activity.source} target="_blank" rel="noreferrer" aria-label={`View ${String(activity.name ?? 'place')} source`}><ArrowRight size={13} /></a>}</li>)}</ul> : <p>No sourced places were available for this date. Keep the day flexible.</p>}</article>
  })}</div>
  if (section.id === 'clothing') return <div className="outfit-list">{section.items.map((day) => {
    const outfitItems = Array.isArray(day.outfit_items) ? day.outfit_items.map(String) : []
    const activities = Array.isArray(day.activities) ? day.activities.map(String) : []
    return <article className="outfit-day" key={String(day.date)}><div><strong>{formatDate(String(day.date))}</strong><small>{String(day.weather_summary ?? '')}</small></div>{activities.length > 0 && <p>Plan: {activities.join(', ')}</p>}{typeof day.style_note === 'string' && <p className="outfit-style-note">{day.style_note}</p>}<ul>{outfitItems.map((item) => <li key={item}>{item}</li>)}</ul></article>
  })}</div>
  if (section.id === 'hotels' || section.id === 'activities') return <div className="place-list">{section.items.map((item, index) => <article className="place-item" key={String(item.source ?? item.name ?? index)}><span className="place-index">{String(index + 1).padStart(2, '0')}</span><div><strong>{String(item.name ?? item.type ?? 'Travel option')}</strong><small>{[item.type, item.star_rating ? `${String(item.star_rating)} star listing` : section.id === 'hotels' ? 'Rating not listed' : null, item.address].filter(Boolean).join(' · ') || 'Address not listed'}</small></div>{typeof item.source === 'string' && <a href={item.source} target="_blank" rel="noreferrer" aria-label={`View ${String(item.name ?? 'place')} source`}><ArrowRight size={14} /></a>}</article>)}</div>
  return <ul className="plan-detail-list">{section.items.map((item, index) => <li key={String(item.name ?? item.category ?? index)}><strong>{String(item.item ?? item.name ?? item.category ?? 'Trip detail')}</strong>{item.status != null && <span>{String(item.status).replaceAll('_', ' ')}</span>}{item.purpose != null && <span>{String(item.purpose)}</span>}{item.note != null && <small>{String(item.note)}</small>}{item.notes != null && <small>{String(item.notes)}</small>}{item.total != null && <span>{String(item.total)} {String(item.currency ?? '')}</span>}</li>)}</ul>
}

function InfoDetails({ details }: { details: Record<string, unknown> }) {
  const entries = Object.entries(details).flatMap(([key, value]) => Array.isArray(value) ? value.map((item) => `${formatLabel(key)}: ${typeof item === 'object' && item !== null ? String((item as Record<string, unknown>).item ?? (item as Record<string, unknown>).name ?? (item as Record<string, unknown>).original_name ?? 'Suggested item') : String(item)}`) : [])
  return entries.length ? <div className="packing-chips">{entries.map((entry, index) => <span key={`${entry}-${index}`}>{entry}</span>)}</div> : null
}

function formatLabel(value: string): string {
  return value.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
}

function DocumentsPage() {
  const [documents, setDocuments] = useState<Array<{ id: string; trip_id: string | null; original_name: string; media_type: string; size_bytes: number; status: string; created_at: string }>>([])
  const [trips, setTrips] = useState<SavedTrip[]>([])
  const [selectedTripId, setSelectedTripId] = useState(() => new URLSearchParams(window.location.search).get('trip_id') ?? '')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (PREVIEW_ONLY) return
    Promise.all([
      apiFetch(`${API_BASE}/api/documents`).then((response) => {
        if (!response.ok) throw new Error('Saved documents could not be loaded.')
        return response.json() as Promise<{ documents: typeof documents }>
      }),
      apiFetch(`${API_BASE}/api/trips`).then((response) => {
        if (!response.ok) throw new Error('Saved trips could not be loaded.')
        return response.json() as Promise<{ trips: SavedTrip[] }>
      }),
    ])
      .then(([documentData, tripData]) => {
        setDocuments(documentData.documents)
        setTrips(tripData.trips)
      })
      .catch((caught: unknown) => setMessage(caught instanceof Error ? caught.message : 'Saved documents could not be loaded.'))
  }, [])

  const upload = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (PREVIEW_ONLY) return
    const input = event.currentTarget.elements.namedItem('document') as HTMLInputElement
    const file = input.files?.[0]
    if (!file) return
    setBusy(true)
    setMessage('')
    try {
      const form = new FormData()
      form.append('file', file)
      const tripQuery = selectedTripId ? `?trip_id=${encodeURIComponent(selectedTripId)}` : ''
      const response = await apiFetch(`${API_BASE}/api/documents${tripQuery}`, { method: 'POST', body: form })
      const data = await response.json() as { detail?: string; status?: string; message?: string }
      if (!response.ok) throw new Error(data.detail ?? 'Upload failed.')
      setMessage(`Uploaded · ${data.status?.replaceAll('_', ' ')}. ${data.message ?? ''}`)
      input.value = ''
      const refreshed = await apiFetch(`${API_BASE}/api/documents`)
      if (!refreshed.ok) throw new Error('The upload succeeded, but the document list could not be refreshed.')
      setDocuments((await refreshed.json() as { documents: typeof documents }).documents)
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : 'Upload failed.')
    } finally {
      setBusy(false)
    }
  }

  const download = async (document: (typeof documents)[number]) => {
    try {
      const response = await apiFetch(`${API_BASE}/api/documents/${document.id}/file`)
      if (!response.ok) throw new Error('The document could not be downloaded.')
      const url = URL.createObjectURL(await response.blob())
      const link = window.document.createElement('a')
      link.href = url
      link.download = document.original_name
      link.click()
      URL.revokeObjectURL(url)
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : 'The document could not be downloaded.')
    }
  }

  return <div className="page-content">
    <div className="eyebrow"><i className="eyebrow-rule" />TRAVEL RECORDS</div>
    <div className="page-title-row"><div><h1>Travel documents</h1><p className="page-intro">Keep your trip files together and review extracted information against the source.</p></div><span className="registered-count">{documents.length} STORED</span></div>
    <section className="form-panel upload-panel">
      <div className="panel-topline"><div><h3>Add a travel document</h3><p>PDF, DOCX, TXT, CSV, JSON, PNG, JPEG and WebP · 10 MB limit</p></div><FileText size={20} color="#4b8a71" /></div>
      <form className="upload-form" onSubmit={(event) => void upload(event)}><label className="field-label"><span>Link to trip</span><select disabled={PREVIEW_ONLY} value={selectedTripId} onChange={(event) => setSelectedTripId(event.target.value)}><option value="">Do not link to a trip</option>{trips.map((trip) => <option key={trip.id} value={trip.id}>{trip.origin} to {trip.destination}</option>)}</select><small>Linked documents appear in that trip’s final plan.</small></label><label className="field-label"><span>Choose document</span><input disabled={PREVIEW_ONLY} name="document" type="file" required accept=".pdf,.docx,.txt,.csv,.json,.png,.jpg,.jpeg,.webp" /></label><button className="primary-button" disabled={busy || PREVIEW_ONLY} type="submit"><Plus size={16} />{PREVIEW_ONLY ? 'Upload unavailable in static preview' : busy ? 'Uploading…' : 'Upload document'}</button></form>
      {message && <p className="trip-message" role="status">{message}</p>}
    </section>
    <section className="stored-documents"><div className="panel-topline"><div><h3>Stored documents</h3><p>Extracted details should be checked against the source file.</p></div></div>{documents.length ? documents.map((document) => <article className="document-row" key={document.id}><span className="document-icon"><FileText size={17} /></span><div className="document-name"><strong>{document.original_name}</strong><small>{document.media_type} · {(document.size_bytes / 1024).toFixed(1)} KB · {document.trip_id ? trips.find((trip) => trip.id === document.trip_id)?.destination ?? 'Linked to trip' : 'Not linked to a trip'}</small></div><button className="text-button" type="button" onClick={() => void download(document)}>Download</button><span className="document-date">{new Date(document.created_at).toLocaleDateString()}</span></article>) : <EmptyState title="No documents stored" detail="Uploaded itinerary, receipt or policy files will be listed here." />}</section>
  </div>
}

function EmptyState({ title, detail }: { title: string; detail: string }) {
  return <div className="empty-state"><span><BriefcaseBusiness size={20} /></span><strong>{title}</strong><p>{detail}</p></div>
}
