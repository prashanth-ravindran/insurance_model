import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Activity,
  BadgeCheck,
  BarChart3,
  BookOpen,
  CheckCircle2,
  ClipboardCheck,
  Download,
  Eye,
  FileText,
  Gauge,
  Database,
  Inbox,
  Layers,
  LineChart,
  Loader2,
  LockKeyhole,
  PanelLeftClose,
  PanelLeftOpen,
  RefreshCw,
  Route,
  SearchCheck,
  Sparkles,
  ShieldAlert,
  SlidersHorizontal,
  UploadCloud,
  UserCheck,
  XCircle
} from 'lucide-react';
import {
  assignReview,
  bindQuote,
  createApplication,
  decideReview,
  enrichApplication,
  extractUnstructuredRecord,
  generateQuote,
  getConfig,
  listApplications,
  listReviews,
  listUnstructuredRecords,
  quotePdfUrl,
  reviewUnstructuredRecord,
  underwriteApplication,
  unstructuredRawUrl,
  getModelSummary,
  uploadUnstructuredFiles
} from './api';
import type { Applicant, ApplicationCreate, ConfigPayload, FieldConfidence, ModelSummary, ModelTableRow, PolicyPayload, Role, UnderwritingCase, UnstructuredRecord } from './types';

type Section = 'flow' | 'unstructured' | 'intake' | 'triage' | 'reviews' | 'quote' | 'model' | 'config';
type ModelTab = 'underwriting' | 'data' | 'actuarial' | 'diagnostics' | 'reserving' | 'capital' | 'scenarios' | 'rules' | 'proxy';

type BusyAction =
  | 'submit'
  | 'upload'
  | 'extract'
  | 'approveExtraction'
  | 'rejectExtraction'
  | 'enrich'
  | 'underwrite'
  | 'assign'
  | 'approve'
  | 'decline'
  | 'quote'
  | 'bind'
  | 'refresh'
  | 'model'
  | null;

const navItems: Array<{ id: Section; label: string; icon: typeof FileText; kind?: 'utility' }> = [
  { id: 'flow', label: 'Process Flow', icon: Route },
  { id: 'unstructured', label: 'Unstructured Intake', icon: Inbox },
  { id: 'intake', label: 'Record Creation', icon: FileText },
  { id: 'triage', label: 'Enrichment & Underwriting', icon: SearchCheck },
  { id: 'reviews', label: 'Review Queue', icon: UserCheck },
  { id: 'quote', label: 'Quote & Bind', icon: BadgeCheck },
  { id: 'model', label: 'Model', icon: BarChart3, kind: 'utility' },
  { id: 'config', label: 'Config', icon: SlidersHorizontal, kind: 'utility' }
];

const lobs = ['Motor', 'Property & Fire', 'Engineering & Construction', 'Marine & Cargo', 'Casualty/Liability'];
const regions = ['Riyadh', 'Jeddah', 'Dammam/Khobar', 'Jubail/Yanbu', 'Makkah/Madinah', 'NEOM/Red Sea', 'Rest of KSA'];
const ratings = ['AAA', 'AA', 'A', 'BBB', 'BB', 'Unrated'];

const modelTabs: Array<{ id: ModelTab; label: string }> = [
  { id: 'underwriting', label: 'Underwriting' },
  { id: 'data', label: 'Data' },
  { id: 'actuarial', label: 'Actuarial' },
  { id: 'diagnostics', label: 'Diagnostics' },
  { id: 'reserving', label: 'Reserving' },
  { id: 'capital', label: 'Capital' },
  { id: 'scenarios', label: 'Scenarios' },
  { id: 'rules', label: 'Rules' },
  { id: 'proxy', label: 'Proxy Factors' }
];

type FlowHotspot = {
  label: string;
  target?: Section;
  x: number;
  y: number;
  w: number;
  h: number;
};

const sectionIds: Section[] = ['flow', 'unstructured', 'intake', 'triage', 'reviews', 'quote', 'model', 'config'];

const processFlowHotspots: FlowHotspot[] = [
  { label: 'Broker / Agent', target: 'intake', x: 3.1, y: 7.4, w: 13.6, h: 4.6 },
  { label: 'Customer', target: 'intake', x: 3.1, y: 12.2, w: 13.6, h: 4.6 },
  { label: 'Sales Team', target: 'intake', x: 3.1, y: 17.3, w: 13.6, h: 4.6 },
  { label: 'Unstructured source files', target: 'unstructured', x: 3.1, y: 24.2, w: 9.0, h: 16.7 },
  { label: 'Web / Portal Intake', target: 'intake', x: 3.1, y: 41.1, w: 9.0, h: 4.5 },
  { label: 'Upload, preview, and extract', target: 'unstructured', x: 13.4, y: 19.0, w: 5.8, h: 24.0 },
  { label: 'Data Prep Stage', x: 21.0, y: 5.6, w: 26.5, h: 44.0 },
  { label: 'Data Intelligence and HITL extraction', target: 'unstructured', x: 48.0, y: 5.8, w: 18.7, h: 68.7 },
  { label: 'Enrichment', target: 'triage', x: 70.2, y: 9.5, w: 26.2, h: 24.5 },
  { label: 'Underwriting Engine', target: 'triage', x: 70.2, y: 35.1, w: 26.2, h: 14.4 },
  { label: 'Premium and Rate Calculation', target: 'triage', x: 70.2, y: 49.3, w: 26.2, h: 23.2 },
  { label: 'Straight-through processing', target: 'triage', x: 13.2, y: 78.2, w: 11.8, h: 5.2 },
  { label: 'Review Queue', target: 'reviews', x: 13.2, y: 85.1, w: 11.8, h: 5.2 },
  { label: 'Decline', target: 'triage', x: 13.2, y: 92.1, w: 11.8, h: 5.2 },
  { label: 'Quotation Automation', target: 'quote', x: 28.0, y: 77.7, w: 45.4, h: 18.8 },
  { label: 'Bind and Delivery', target: 'quote', x: 76.0, y: 77.7, w: 21.0, h: 18.8 }
];

const defaultHotspotLayerStyle = { left: '0%', top: '0%', width: '100%', height: '100%' };

function sectionFromHash(hash: string): Section | null {
  const id = hash.replace(/^#/, '') as Section;
  return sectionIds.includes(id) ? id : null;
}

const lobDefaults: Record<string, Partial<PolicyPayload>> = {
  Motor: {
    exposure_value_sar: 120000,
    limit_sar: 1000000,
    deductible_sar: 2500,
    policy_type: 'Comprehensive',
    vehicle_class: 'Private car',
    driver_age: 42,
    vehicle_age: 2,
    fleet_size: 1
  },
  'Property & Fire': {
    exposure_value_sar: 120000000,
    limit_sar: 90000000,
    deductible_sar: 150000,
    policy_type: 'Commercial property',
    occupancy_type: 'Warehouse',
    occupancy_hazard_score: 0.52,
    construction_quality_score: 0.72,
    fire_protection_score: 0.74
  },
  'Engineering & Construction': {
    exposure_value_sar: 900000000,
    limit_sar: 650000000,
    deductible_sar: 1500000,
    policy_type: 'CAR/EAR',
    project_type: 'Giga-project package',
    project_complexity_score: 0.84,
    project_duration_months: 36,
    contractor_experience_years: 10
  },
  'Marine & Cargo': {
    exposure_value_sar: 25000000,
    limit_sar: 20000000,
    deductible_sar: 50000,
    policy_type: 'Single transit/open cover',
    cargo_type: 'General cargo',
    cargo_type_risk_score: 0.3,
    transit_distance_km: 800,
    storage_days: 4
  },
  'Casualty/Liability': {
    exposure_value_sar: 90000000,
    limit_sar: 25000000,
    deductible_sar: 75000,
    policy_type: 'Liability',
    liability_type: 'General liability',
    annual_revenue_sar: 90000000,
    liability_limit_factor: 0.45,
    professional_risk_score: 0.34
  }
};

function defaultPolicy(lob = 'Motor'): PolicyPayload {
  return {
    lob,
    region: 'Riyadh',
    counterparty_rating: 'A',
    exposure_value_sar: 120000,
    limit_sar: 1000000,
    deductible_sar: 2500,
    term_months: 12,
    prior_claims_3y: 0,
    risk_control_score: 88,
    reinsurance_ceded_pct: 0.1,
    event_accumulation_score: 0.08,
    ...lobDefaults[lob]
  } as PolicyPayload;
}

function formatSar(value: number | null | undefined): string {
  if (value === null || value === undefined) return 'Not offered';
  if (Math.abs(value) >= 1_000_000_000) return `SAR ${(value / 1_000_000_000).toFixed(2)}B`;
  if (Math.abs(value) >= 1_000_000) return `SAR ${(value / 1_000_000).toFixed(2)}M`;
  if (Math.abs(value) >= 1_000) return `SAR ${(value / 1_000).toFixed(1)}K`;
  return `SAR ${value.toFixed(0)}`;
}

function statusLabel(status: string): string {
  return status.replaceAll('_', ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

function draftFromUnstructured(record: UnstructuredRecord): ApplicationCreate {
  const extracted = record.extraction.application;
  const lob = extracted?.policy?.lob && lobs.includes(String(extracted.policy.lob)) ? String(extracted.policy.lob) : 'Motor';
  const basePolicy = defaultPolicy(lob);
  const extractedPolicy = (extracted?.policy ?? {}) as Partial<PolicyPayload>;
  const extractedLimit = positiveNumber(extractedPolicy.limit_sar);
  const extractedExposure = positiveNumber(extractedPolicy.exposure_value_sar);
  const sourceDocumentId = findSourceDocumentId(record);
  const nationalId = cleanString(extracted?.applicant?.national_id_or_cr);
  const applicantName = cleanString(extracted?.applicant?.name) || record.original_filename.replace(/\.[^.]+$/, '') || 'Uploaded record';
  return {
    channel: extracted?.channel ?? 'manual',
    submitted_by: extracted?.submitted_by ?? 'unstructured.intake',
    role: extracted?.role ?? 'agent',
    applicant: {
      name: applicantName,
      applicant_type: extracted?.applicant?.applicant_type ?? 'company',
      national_id_or_cr: nationalId.length >= 4 ? nationalId : sourceDocumentId,
      email: extracted?.applicant?.email ?? '',
      phone: extracted?.applicant?.phone ?? ''
    },
    policy: {
      ...basePolicy,
      ...extractedPolicy,
      lob,
      exposure_value_sar: extractedExposure > 0 ? extractedExposure : extractedLimit > 0 ? extractedLimit : basePolicy.exposure_value_sar,
      limit_sar: extractedLimit > 0 ? extractedLimit : extractedExposure > 0 ? extractedExposure : basePolicy.limit_sar,
      deductible_sar: Number(extractedPolicy.deductible_sar ?? basePolicy.deductible_sar)
    } as PolicyPayload,
    requested_coverages: extracted?.requested_coverages ?? { source: 'unstructured_intake' }
  };
}

function cleanString(value: unknown): string {
  return typeof value === 'string' ? value.trim() : value === null || value === undefined ? '' : String(value).trim();
}

function positiveNumber(value: unknown): number {
  const number = Number(value);
  return Number.isFinite(number) && number > 0 ? number : 0;
}

function findSourceDocumentId(record: UnstructuredRecord): string {
  const match = record.raw_text.match(/\bAPP-[A-Z0-9]+\b/i);
  if (match) return match[0].toUpperCase();
  return `DOC-${record.id.replace(/^URI-/, '').slice(0, 12) || 'UNSTRUCT'}`;
}

function confidenceFor(record: UnstructuredRecord | null, path: string): FieldConfidence | undefined {
  return record?.field_confidence?.[path];
}

function decisionClass(status?: string | null): string {
  if (status === 'declined' || status === 'underwriter_declined') return 'danger';
  if (status === 'requires_review') return 'warning';
  if (status === 'bound' || status === 'quoted' || status === 'stp_quoted' || status === 'underwriter_approved') return 'success';
  return 'neutral';
}

function App() {
  const [section, setSection] = useState<Section>(() => typeof window === 'undefined' ? 'flow' : sectionFromHash(window.location.hash) ?? 'flow');
  const [sidebarCollapsed, setSidebarCollapsed] = useState(true);
  const [role, setRole] = useState<Role>('agent');
  const [config, setConfig] = useState<ConfigPayload | null>(null);
  const [cases, setCases] = useState<UnderwritingCase[]>([]);
  const [reviews, setReviews] = useState<UnderwritingCase[]>([]);
  const [unstructuredRecords, setUnstructuredRecords] = useState<UnstructuredRecord[]>([]);
  const [currentUnstructured, setCurrentUnstructured] = useState<UnstructuredRecord | null>(null);
  const [unstructuredDraft, setUnstructuredDraft] = useState<ApplicationCreate | null>(null);
  const [currentCase, setCurrentCase] = useState<UnderwritingCase | null>(null);
  const [busy, setBusy] = useState<BusyAction>(null);
  const [error, setError] = useState<string | null>(null);
  const [channel, setChannel] = useState<'manual' | 'api'>('manual');
  const [applicant, setApplicant] = useState<Applicant>({
    name: 'Acme Logistics Co.',
    applicant_type: 'company',
    national_id_or_cr: 'CR12345',
    email: 'ops@acme.example',
    phone: '+966500000000'
  });
  const [policy, setPolicy] = useState<PolicyPayload>(defaultPolicy('Motor'));
  const [modelPolicy, setModelPolicy] = useState<PolicyPayload>(defaultPolicy('Motor'));
  const [modelSummary, setModelSummary] = useState<ModelSummary | null>(null);
  const [modelSettings, setModelSettings] = useState({ rows: 2500, seed: 42, scenario: 'Base' });
  const [modelTab, setModelTab] = useState<ModelTab>('underwriting');
  const [reviewNotes, setReviewNotes] = useState('Risk controls verified and terms adjusted for current appetite.');
  const [premiumDelta, setPremiumDelta] = useState(0.05);
  const [reviewExclusion, setReviewExclusion] = useState('Flood and sandstorm sublimits apply where scheduled.');

  const selectedDecision = currentCase?.latest_decision;
  const selectedRating = currentCase?.latest_rating;
  const selectedQuote = currentCase?.latest_quote;
  const pageTitle = section === 'flow'
    ? 'Underwriting process flow'
    : section === 'model'
      ? 'Portfolio risk model'
      : section === 'unstructured'
        ? currentUnstructured?.original_filename ?? 'Unstructured intake'
        : currentCase ? currentCase.applicant.name : 'New application';

  const visibleCases = useMemo(() => cases.slice(0, 12), [cases]);
  const visibleUnstructured = useMemo(() => unstructuredRecords.slice(0, 18), [unstructuredRecords]);

  useEffect(() => {
    void bootstrap();
  }, []);

  useEffect(() => {
    const handleLocationChange = () => {
      const next = sectionFromHash(window.location.hash);
      if (next) setSection(next);
    };
    window.addEventListener('hashchange', handleLocationChange);
    window.addEventListener('popstate', handleLocationChange);
    return () => {
      window.removeEventListener('hashchange', handleLocationChange);
      window.removeEventListener('popstate', handleLocationChange);
    };
  }, []);

  useEffect(() => {
    if (section === 'model' && !modelSummary && busy !== 'model') {
      void runModelSummary();
    }
  }, [section]);

  async function bootstrap() {
    setBusy('refresh');
    setError(null);
    try {
      const [cfg, allCases, reviewCases, rawRecords] = await Promise.all([getConfig(), listApplications(), listReviews(), listUnstructuredRecords()]);
      setConfig(cfg);
      setCases(allCases);
      setReviews(reviewCases);
      setUnstructuredRecords(rawRecords);
      if (!currentCase && allCases.length) setCurrentCase(allCases[0]);
      if (!currentUnstructured && rawRecords.length) {
        setCurrentUnstructured(rawRecords[0]);
        setUnstructuredDraft(draftFromUnstructured(rawRecords[0]));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  }

  async function refreshQueues(nextCase?: UnderwritingCase) {
    const [allCases, reviewCases] = await Promise.all([listApplications(), listReviews()]);
    setCases(allCases);
    setReviews(reviewCases);
    if (nextCase) setCurrentCase(nextCase);
  }

  async function refreshUnstructured(nextRecord?: UnstructuredRecord | null) {
    const rawRecords = await listUnstructuredRecords();
    setUnstructuredRecords(rawRecords);
    if (nextRecord) {
      const refreshed = rawRecords.find((record) => record.id === nextRecord.id) ?? nextRecord;
      setCurrentUnstructured(refreshed);
      setUnstructuredDraft(draftFromUnstructured(refreshed));
    } else if (!currentUnstructured && rawRecords.length) {
      setCurrentUnstructured(rawRecords[0]);
      setUnstructuredDraft(draftFromUnstructured(rawRecords[0]));
    }
  }

  function navigateToSection(next: Section) {
    setSection(next);
    if (typeof window !== 'undefined') {
      const hash = `#${next}`;
      if (window.location.hash !== hash) window.history.pushState(null, '', hash);
    }
  }

  async function runAction(action: BusyAction, fn: () => Promise<UnderwritingCase>) {
    if (!action) return;
    setBusy(action);
    setError(null);
    try {
      const next = await fn();
      await refreshQueues(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  }

  function updatePolicy(key: string, value: string | number) {
    setPolicy((prev) => ({ ...prev, [key]: value }));
  }

  function changeLob(lob: string) {
    setPolicy(defaultPolicy(lob));
  }

  function updateModelPolicy(key: string, value: string | number) {
    setModelPolicy((prev) => ({ ...prev, [key]: value }));
  }

  function changeModelLob(lob: string) {
    setModelPolicy(defaultPolicy(lob));
  }

  function updateModelSettings(key: 'rows' | 'seed' | 'scenario', value: string | number) {
    setModelSettings((prev) => ({ ...prev, [key]: value }));
  }

  async function runModelSummary() {
    setBusy('model');
    setError(null);
    try {
      const summary = await getModelSummary({
        rows: Number(modelSettings.rows),
        seed: Number(modelSettings.seed),
        scenario: String(modelSettings.scenario),
        policy: modelPolicy
      });
      setModelSummary(summary);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  }

  function selectUnstructured(record: UnstructuredRecord) {
    setCurrentUnstructured(record);
    setUnstructuredDraft(draftFromUnstructured(record));
  }

  async function handleUnstructuredUpload(files: FileList | null) {
    if (!files?.length) return;
    setBusy('upload');
    setError(null);
    try {
      const uploaded = await uploadUnstructuredFiles(Array.from(files));
      const [rawRecords] = await Promise.all([listUnstructuredRecords()]);
      setUnstructuredRecords(rawRecords);
      const selected = uploaded[0] ?? rawRecords[0] ?? null;
      if (selected) selectUnstructured(selected);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  }

  async function runUnstructuredExtraction() {
    if (!currentUnstructured) return;
    setBusy('extract');
    setError(null);
    try {
      const next = await extractUnstructuredRecord(currentUnstructured.id);
      await refreshUnstructured(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  }

  async function approveUnstructuredExtraction() {
    if (!currentUnstructured || !unstructuredDraft) return;
    setBusy('approveExtraction');
    setError(null);
    try {
      const result = await reviewUnstructuredRecord(currentUnstructured.id, {
        action: 'approve',
        reviewer: `demo.${role}`,
        notes: 'Extraction reviewed and approved for structured intake.',
        application: unstructuredDraft
      });
      await refreshUnstructured(result.record);
      if (result.application) {
        await refreshQueues(result.application);
        navigateToSection('triage');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  }

  async function rejectUnstructuredExtraction() {
    if (!currentUnstructured) return;
    setBusy('rejectExtraction');
    setError(null);
    try {
      const result = await reviewUnstructuredRecord(currentUnstructured.id, {
        action: 'reject',
        reviewer: `demo.${role}`,
        notes: 'Extraction rejected during HITL review.'
      });
      await refreshUnstructured(result.record);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  }

  function updateDraftApplicant(key: keyof Applicant, value: string) {
    setUnstructuredDraft((prev) => prev ? { ...prev, applicant: { ...prev.applicant, [key]: value } } : prev);
  }

  function updateDraftPolicy(key: string, value: string | number) {
    setUnstructuredDraft((prev) => prev ? { ...prev, policy: { ...prev.policy, [key]: value } } : prev);
  }

  function changeDraftLob(lob: string) {
    setUnstructuredDraft((prev) => prev ? { ...prev, policy: { ...defaultPolicy(lob), ...prev.policy, lob } } : prev);
  }

  async function submitApplication() {
    const payload: ApplicationCreate = {
      channel,
      submitted_by: role === 'agent' ? 'demo.agent' : `demo.${role}`,
      role,
      applicant,
      policy,
      requested_coverages: { source: 'workbench', requested_at: new Date().toISOString() }
    };
    await runAction('submit', async () => createApplication(payload));
  }

  async function runEnrichment() {
    if (!currentCase) return;
    await runAction('enrich', async () => enrichApplication(currentCase.id));
  }

  async function runUnderwriting() {
    if (!currentCase) return;
    await runAction('underwrite', async () => underwriteApplication(currentCase.id));
  }

  async function assignCurrentCase() {
    if (!currentCase) return;
    await runAction('assign', async () => assignReview(currentCase.id, { assignee: 'demo.underwriter' }));
  }

  async function approveCurrentCase() {
    if (!currentCase) return;
    await runAction('approve', async () =>
      decideReview(currentCase.id, {
        action: 'approve',
        underwriter: 'demo.underwriter',
        notes: reviewNotes,
        premium_delta_pct: premiumDelta,
        deductible_sar: Number(policy.deductible_sar),
        sublimits: { flood_sar: Math.round(Number(currentCase.policy.limit_sar) * 0.25) },
        exclusions: [reviewExclusion]
      })
    );
  }

  async function declineCurrentCase() {
    if (!currentCase) return;
    await runAction('decline', async () =>
      decideReview(currentCase.id, {
        action: 'decline',
        underwriter: 'demo.underwriter',
        notes: reviewNotes || 'Outside current appetite.',
        premium_delta_pct: 0,
        sublimits: {},
        exclusions: []
      })
    );
  }

  async function generateCurrentQuote() {
    if (!currentCase) return;
    await runAction('quote', async () => generateQuote(currentCase.id, { generated_by: `demo.${role}`, expiry_days: 30 }));
  }

  async function bindCurrentQuote() {
    if (!selectedQuote) return;
    await runAction('bind', async () => bindQuote(selectedQuote.id, { bound_by: `demo.${role}`, accepted_terms: true }));
  }

  return (
    <div className={`app-shell ${sidebarCollapsed ? 'sidebar-collapsed' : ''}`}>
      <aside className="sidebar">
        <div className="brand-block">
          <div className="brand-lockup xtract-brand">
            <div className="brand-logo-card">
              <img className="brand-logo" src="/xtract-logo.png" alt="Xtract.io" />
            </div>
            <div className="brand-subtitle">for Chubb Arabia</div>
          </div>
          <button
            className="sidebar-toggle"
            onClick={() => setSidebarCollapsed((value) => !value)}
            title={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            {sidebarCollapsed ? <PanelLeftOpen size={17} /> : <PanelLeftClose size={17} />}
          </button>
        </div>
        <nav className="nav-list">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <button key={item.id} className={`nav-item ${item.kind === 'utility' ? 'utility' : ''} ${section === item.id ? 'active' : ''}`} onClick={() => navigateToSection(item.id)} title={item.label} aria-label={item.label}>
                <Icon size={18} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>
        <div className="sidebar-footer">
          <label className="field-label">Role</label>
          <select value={role} onChange={(event) => setRole(event.target.value as Role)}>
            <option value="agent">Agent</option>
            <option value="underwriter">Underwriter</option>
            <option value="manager">Manager</option>
          </select>
        </div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <div className="topbar-title">
            <div>
              <div className="eyebrow">Xtract.io for Chubb Arabia</div>
              <h1>{pageTitle}</h1>
            </div>
          </div>
          <div className="topbar-actions">
            {section !== 'flow' && section !== 'unstructured' && section !== 'model' && currentCase && <span className={`status-pill ${decisionClass(currentCase.status)}`}>{statusLabel(currentCase.status)}</span>}
            <button className="icon-button" onClick={() => void bootstrap()} disabled={busy !== null} title="Refresh">
              {busy === 'refresh' ? <Loader2 className="spin" size={18} /> : <RefreshCw size={18} />}
            </button>
          </div>
        </header>

        {error && <div className="error-banner"><XCircle size={18} /> {error}</div>}

        {section !== 'flow' && section !== 'unstructured' && section !== 'model' && (
          <section className="case-strip">
            {visibleCases.map((item) => (
              <button key={item.id} className={`case-chip ${currentCase?.id === item.id ? 'selected' : ''}`} onClick={() => setCurrentCase(item)}>
                <span>{item.applicant.name}</span>
                <strong>{statusLabel(item.status)}</strong>
              </button>
            ))}
          </section>
        )}

        {section === 'flow' && (
          <ProcessFlowView onNavigate={navigateToSection} />
        )}

        {section === 'unstructured' && (
          <UnstructuredIntakeView
            records={visibleUnstructured}
            currentRecord={currentUnstructured}
            draft={unstructuredDraft}
            config={config}
            busy={busy}
            onUpload={(files) => void handleUnstructuredUpload(files)}
            onSelect={selectUnstructured}
            onExtract={() => void runUnstructuredExtraction()}
            onApprove={() => void approveUnstructuredExtraction()}
            onReject={() => void rejectUnstructuredExtraction()}
            updateApplicant={updateDraftApplicant}
            updatePolicy={updateDraftPolicy}
            changeLob={changeDraftLob}
          />
        )}

        {section === 'intake' && (
          <div className="layout-grid two-col">
            <Panel title="Application Intake" icon={FileText}>
              <div className="form-grid two">
                <Field label="Channel">
                  <select value={channel} onChange={(event) => setChannel(event.target.value as 'manual' | 'api')}>
                    <option value="manual">Manual</option>
                    <option value="api">API</option>
                  </select>
                </Field>
                <Field label="Applicant type">
                  <select value={applicant.applicant_type} onChange={(event) => setApplicant({ ...applicant, applicant_type: event.target.value as 'individual' | 'company' })}>
                    <option value="company">Company</option>
                    <option value="individual">Individual</option>
                  </select>
                </Field>
                <Field label="Applicant name"><input value={applicant.name} onChange={(event) => setApplicant({ ...applicant, name: event.target.value })} /></Field>
                <Field label="National ID / CR"><input value={applicant.national_id_or_cr} onChange={(event) => setApplicant({ ...applicant, national_id_or_cr: event.target.value })} /></Field>
                <Field label="Email"><input value={applicant.email ?? ''} onChange={(event) => setApplicant({ ...applicant, email: event.target.value })} /></Field>
                <Field label="Phone"><input value={applicant.phone ?? ''} onChange={(event) => setApplicant({ ...applicant, phone: event.target.value })} /></Field>
              </div>
            </Panel>

            <Panel title="Risk Details" icon={Layers}>
              <div className="form-grid two">
                <Field label="LOB">
                  <select value={policy.lob} onChange={(event) => changeLob(event.target.value)}>
                    {(config?.lobs ?? lobs).map((lob) => <option key={lob}>{lob}</option>)}
                  </select>
                </Field>
                <Field label="Region">
                  <select value={policy.region} onChange={(event) => updatePolicy('region', event.target.value)}>
                    {(config ? Object.keys(config.regions) : regions).map((region) => <option key={region}>{region}</option>)}
                  </select>
                </Field>
                <Field label="Reinsurer rating">
                  <select value={policy.counterparty_rating} onChange={(event) => updatePolicy('counterparty_rating', event.target.value)}>
                    {(config?.counterparty_ratings ?? ratings).map((rating) => <option key={rating}>{rating}</option>)}
                  </select>
                </Field>
                <Field label="Term months"><NumberInput value={policy.term_months} onChange={(value) => updatePolicy('term_months', value)} /></Field>
                <Field label="Exposure value"><NumberInput value={policy.exposure_value_sar} onChange={(value) => updatePolicy('exposure_value_sar', value)} /></Field>
                <Field label="Coverage limit"><NumberInput value={policy.limit_sar} onChange={(value) => updatePolicy('limit_sar', value)} /></Field>
                <Field label="Deductible"><NumberInput value={policy.deductible_sar} onChange={(value) => updatePolicy('deductible_sar', value)} /></Field>
                <Field label="Prior claims"><NumberInput value={policy.prior_claims_3y} onChange={(value) => updatePolicy('prior_claims_3y', value)} /></Field>
                <Field label="Risk controls"><NumberInput value={policy.risk_control_score} onChange={(value) => updatePolicy('risk_control_score', value)} /></Field>
                <Field label="Reinsurance ceded"><NumberInput value={policy.reinsurance_ceded_pct} step={0.01} onChange={(value) => updatePolicy('reinsurance_ceded_pct', value)} /></Field>
                <Field label="Event accumulation"><NumberInput value={policy.event_accumulation_score} step={0.01} onChange={(value) => updatePolicy('event_accumulation_score', value)} /></Field>
              </div>
              <LobSpecificFields policy={policy} updatePolicy={updatePolicy} />
              <div className="button-row">
                <button className="primary-button" onClick={() => void submitApplication()} disabled={busy !== null}>{busy === 'submit' ? <Loader2 className="spin" size={17} /> : <ClipboardCheck size={17} />} Submit</button>
              </div>
            </Panel>
          </div>
        )}

        {section === 'triage' && (
          <div className="layout-grid two-col">
            <Panel title="Enrichment Timeline" icon={Route}>
              <div className="button-row compact">
                <button onClick={() => void runEnrichment()} disabled={!currentCase || busy !== null}>{busy === 'enrich' ? <Loader2 className="spin" size={16} /> : <Activity size={16} />} Enrich</button>
                <button onClick={() => void runUnderwriting()} disabled={!currentCase || busy !== null}>{busy === 'underwrite' ? <Loader2 className="spin" size={16} /> : <Gauge size={16} />} Underwrite</button>
              </div>
              <EnrichmentList item={currentCase} />
            </Panel>

            <Panel title="Triage & Rating" icon={Gauge}>
              {selectedDecision ? <DecisionSummary item={currentCase!} /> : <EmptyState label="No underwriting decision" />}
              {selectedRating && <RatingSummary rating={selectedRating} />}
            </Panel>
          </div>
        )}

        {section === 'reviews' && (
          <div className="layout-grid two-col queue-grid">
            <Panel title="Review Queue" icon={UserCheck}>
              <div className="queue-list">
                {reviews.length === 0 && <EmptyState label="No cases in review" />}
                {reviews.map((item) => (
                  <button key={item.id} className={`queue-row ${currentCase?.id === item.id ? 'selected' : ''}`} onClick={() => setCurrentCase(item)}>
                    <span><strong>{item.applicant.name}</strong><em>{item.policy.lob}</em></span>
                    <span>{formatSar(item.latest_rating?.adjusted_premium_sar)}</span>
                  </button>
                ))}
              </div>
            </Panel>
            <Panel title="Underwriter Action" icon={CheckCircle2}>
              {currentCase?.status === 'requires_review' ? (
                <>
                  <DecisionSummary item={currentCase} />
                  <div className="form-grid two">
                    <Field label="Assignee"><input value={currentCase.assigned_to ?? 'demo.underwriter'} readOnly /></Field>
                    <Field label="Schedule adjustment"><NumberInput value={premiumDelta} step={0.01} onChange={setPremiumDelta} /></Field>
                  </div>
                  <Field label="Notes"><textarea value={reviewNotes} onChange={(event) => setReviewNotes(event.target.value)} /></Field>
                  <Field label="Exclusion"><input value={reviewExclusion} onChange={(event) => setReviewExclusion(event.target.value)} /></Field>
                  <div className="button-row">
                    <button onClick={() => void assignCurrentCase()} disabled={busy !== null}>{busy === 'assign' ? <Loader2 className="spin" size={16} /> : <UserCheck size={16} />} Assign</button>
                    <button className="primary-button" onClick={() => void approveCurrentCase()} disabled={busy !== null}>{busy === 'approve' ? <Loader2 className="spin" size={16} /> : <CheckCircle2 size={16} />} Approve</button>
                    <button className="danger-button" onClick={() => void declineCurrentCase()} disabled={busy !== null}>{busy === 'decline' ? <Loader2 className="spin" size={16} /> : <XCircle size={16} />} Decline</button>
                  </div>
                </>
              ) : <EmptyState label="Select a requires-review case" />}
            </Panel>
          </div>
        )}

        {section === 'quote' && (
          <div className="layout-grid two-col">
            <Panel title="Quote Package" icon={FileText}>
              {currentCase ? (
                <>
                  <MetricRow values={[
                    ['Status', statusLabel(currentCase.status)],
                    ['Premium', formatSar(selectedQuote?.premium_sar ?? selectedRating?.adjusted_premium_sar)],
                    ['Risk score', selectedRating ? `${selectedRating.risk_score.toFixed(1)}/100` : '-'],
                    ['SCR impact', formatSar(selectedRating?.scr_impact_sar)]
                  ]} />
                  <div className="button-row">
                    <button className="primary-button" onClick={() => void generateCurrentQuote()} disabled={!['stp_quoted', 'underwriter_approved', 'quoted'].includes(currentCase.status) || busy !== null}>{busy === 'quote' ? <Loader2 className="spin" size={16} /> : <FileText size={16} />} Generate Quote</button>
                    {selectedQuote && <a className="secondary-link" href={quotePdfUrl(selectedQuote.id)} target="_blank" rel="noreferrer"><Download size={16} /> PDF</a>}
                    <button onClick={() => void bindCurrentQuote()} disabled={!selectedQuote || currentCase.status === 'bound' || busy !== null}>{busy === 'bind' ? <Loader2 className="spin" size={16} /> : <LockKeyhole size={16} />} Bind</button>
                  </div>
                  {selectedQuote && (
                    <>
                      <QuoteDetails item={currentCase} />
                      <QuotePreview quoteId={selectedQuote.id} quoteNumber={selectedQuote.quote_number} />
                    </>
                  )}
                </>
              ) : <EmptyState label="No application selected" />}
            </Panel>
            <Panel title="Audit Trail" icon={BookOpen}>
              <AuditTrail item={currentCase} />
            </Panel>
          </div>
        )}

        {section === 'model' && (
          <ModelView
            summary={modelSummary}
            settings={modelSettings}
            policy={modelPolicy}
            activeTab={modelTab}
            config={config}
            busy={busy}
            onSettingsChange={updateModelSettings}
            onPolicyChange={updateModelPolicy}
            onLobChange={changeModelLob}
            onTabChange={setModelTab}
            onRun={() => void runModelSummary()}
          />
        )}

        {section === 'config' && (
          <div className="layout-grid two-col">
            <Panel title="LOB Appetite" icon={SlidersHorizontal}>
              <DataTable rows={Object.entries(config?.lob_config ?? {}).map(([lob, cfg]) => ({ LOB: lob, MaxLimit: formatSar(cfg.max_limit), MinPremium: formatSar(cfg.min_premium), BaseRate: cfg.base_rate }))} />
            </Panel>
            <Panel title="Decision Thresholds" icon={ShieldAlert}>
              <DataTable rows={Object.entries(config?.decision_thresholds ?? {}).map(([key, value]) => ({ Threshold: key, Value: value }))} />
            </Panel>
          </div>
        )}
      </main>
    </div>
  );
}

function ProcessFlowView({ onNavigate }: { onNavigate: (section: Section) => void }) {
  const frameRef = useRef<HTMLIFrameElement | null>(null);
  const [hotspotLayerStyle, setHotspotLayerStyle] = useState(defaultHotspotLayerStyle);

  function syncHotspotLayer() {
    const frame = frameRef.current;
    const stage = frame?.parentElement;
    const graph = frame?.contentDocument?.querySelector('.mxgraph') as HTMLElement | null;
    if (!frame || !stage || !graph) return;
    const stageRect = stage.getBoundingClientRect();
    const graphRect = graph.getBoundingClientRect();
    if (!stageRect.width || !stageRect.height || !graphRect.width || !graphRect.height) return;
    setHotspotLayerStyle({
      left: (graphRect.left / stageRect.width * 100) + '%',
      top: (graphRect.top / stageRect.height * 100) + '%',
      width: (graphRect.width / stageRect.width * 100) + '%',
      height: (graphRect.height / stageRect.height * 100) + '%'
    });
  }

  function scheduleHotspotSync() {
    window.setTimeout(syncHotspotLayer, 0);
    window.setTimeout(syncHotspotLayer, 250);
  }

  useEffect(() => {
    scheduleHotspotSync();
    window.addEventListener('resize', scheduleHotspotSync);
    return () => window.removeEventListener('resize', scheduleHotspotSync);
  }, []);

  return (
    <div className="flow-page">
      <section className="flow-hero">
        <div>
          <div className="eyebrow">Demo control map</div>
          <h2>Insurance underwriting and quotation automation</h2>
          <p>The demo flow keeps the original Draw.io diagram intact. Click the active regions to jump into the matching workbench screen.</p>
        </div>
        <div className="flow-legend" aria-label="Flow legend">
          <span><i className="legend-clickable" /> Clickable app region</span>
          <span><i className="legend-background" /> Background process</span>
        </div>
      </section>

      <section className="flow-image-shell">
        <div className="flow-image-scroller" aria-label="Underwriting flow diagram">
          <div className="flow-diagram-stage">
            <iframe
              ref={frameRef}
              className="flow-diagram-frame"
              src="/process-flow.html"
              title="Insurance underwriting and quotation automation process flow"
              onLoad={scheduleHotspotSync}
            />
            <div className="flow-hotspot-layer" style={hotspotLayerStyle}>
              {processFlowHotspots.map((hotspot) => (
                <FlowHotspotButton key={hotspot.label} hotspot={hotspot} onNavigate={onNavigate} />
              ))}
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

function FlowHotspotButton({ hotspot, onNavigate }: { hotspot: FlowHotspot; onNavigate: (section: Section) => void }) {
  const style = { left: hotspot.x + '%', top: hotspot.y + '%', width: hotspot.w + '%', height: hotspot.h + '%' };
  if (!hotspot.target) {
    return <div className="flow-hotspot background" style={style} aria-label={hotspot.label + ': background process'} title={hotspot.label + ' runs as a background process'} />;
  }
  const targetLabel = flowTargetLabel(hotspot.target);
  return (
    <button
      type="button"
      className="flow-hotspot"
      style={style}
      onClick={() => onNavigate(hotspot.target!)}
      aria-label={'Open ' + targetLabel + ': ' + hotspot.label}
      title={'Open ' + targetLabel + ': ' + hotspot.label}
    >
      <span>{'Open ' + targetLabel + ': ' + hotspot.label}</span>
    </button>
  );
}

function flowTargetLabel(target?: Section): string {
  if (!target) return 'screen';
  return navItems.find((item) => item.id === target)?.label ?? 'Open screen';
}

function ModelView({
  summary,
  settings,
  policy,
  activeTab,
  config,
  busy,
  onSettingsChange,
  onPolicyChange,
  onLobChange,
  onTabChange,
  onRun
}: {
  summary: ModelSummary | null;
  settings: { rows: number; seed: number; scenario: string };
  policy: PolicyPayload;
  activeTab: ModelTab;
  config: ConfigPayload | null;
  busy: BusyAction;
  onSettingsChange: (key: 'rows' | 'seed' | 'scenario', value: string | number) => void;
  onPolicyChange: (key: string, value: string | number) => void;
  onLobChange: (lob: string) => void;
  onTabChange: (tab: ModelTab) => void;
  onRun: () => void;
}) {
  const feedNames = Object.keys(summary?.data.table_previews ?? {});
  const [selectedFeed, setSelectedFeed] = useState('policies');
  const activeFeed = feedNames.includes(selectedFeed) ? selectedFeed : feedNames[0] ?? 'policies';
  const capitalDetailNames = Object.keys(summary?.capital.details ?? {});
  const [selectedCapitalDetail, setSelectedCapitalDetail] = useState('premium_risk');
  const activeCapitalDetail = capitalDetailNames.includes(selectedCapitalDetail) ? selectedCapitalDetail : capitalDetailNames[0] ?? 'premium_risk';
  const scenarioNames = Object.keys(config?.scenarios ?? { Base: {} });

  return (
    <div className="model-page">
      <div className="layout-grid model-control-grid">
        <Panel title="Model Run" icon={SlidersHorizontal}>
          <div className="form-grid three">
            <Field label="Data rows"><NumberInput value={settings.rows} onChange={(value) => onSettingsChange('rows', value)} /></Field>
            <Field label="Random seed"><NumberInput value={settings.seed} onChange={(value) => onSettingsChange('seed', value)} /></Field>
            <Field label="Scenario">
              <select value={settings.scenario} onChange={(event) => onSettingsChange('scenario', event.target.value)}>
                {scenarioNames.map((scenario) => <option key={scenario}>{scenario}</option>)}
              </select>
            </Field>
          </div>
          <div className="button-row">
            <button className="primary-button" onClick={onRun} disabled={busy !== null}>
              {busy === 'model' ? <Loader2 className="spin" size={17} /> : <RefreshCw size={17} />} Recalculate Model
            </button>
            {summary && <span className="model-run-note">{summary.run.scenario_description}</span>}
          </div>
        </Panel>

        <Panel title="Policy Input" icon={Layers}>
          <div className="form-grid three">
            <Field label="LOB">
              <select value={policy.lob} onChange={(event) => onLobChange(event.target.value)}>
                {(config?.lobs ?? lobs).map((lob) => <option key={lob}>{lob}</option>)}
              </select>
            </Field>
            <Field label="Region">
              <select value={policy.region} onChange={(event) => onPolicyChange('region', event.target.value)}>
                {(config ? Object.keys(config.regions) : regions).map((region) => <option key={region}>{region}</option>)}
              </select>
            </Field>
            <Field label="Reinsurer rating">
              <select value={policy.counterparty_rating} onChange={(event) => onPolicyChange('counterparty_rating', event.target.value)}>
                {(config?.counterparty_ratings ?? ratings).map((rating) => <option key={rating}>{rating}</option>)}
              </select>
            </Field>
            <Field label="Exposure value"><NumberInput value={policy.exposure_value_sar} onChange={(value) => onPolicyChange('exposure_value_sar', value)} /></Field>
            <Field label="Coverage limit"><NumberInput value={policy.limit_sar} onChange={(value) => onPolicyChange('limit_sar', value)} /></Field>
            <Field label="Deductible"><NumberInput value={policy.deductible_sar} onChange={(value) => onPolicyChange('deductible_sar', value)} /></Field>
            <Field label="Term months"><NumberInput value={policy.term_months} onChange={(value) => onPolicyChange('term_months', value)} /></Field>
            <Field label="Prior claims"><NumberInput value={policy.prior_claims_3y} onChange={(value) => onPolicyChange('prior_claims_3y', value)} /></Field>
            <Field label="Risk controls"><NumberInput value={policy.risk_control_score} onChange={(value) => onPolicyChange('risk_control_score', value)} /></Field>
            <Field label="Reinsurance ceded"><NumberInput value={policy.reinsurance_ceded_pct} step={0.01} onChange={(value) => onPolicyChange('reinsurance_ceded_pct', value)} /></Field>
            <Field label="Event accumulation"><NumberInput value={policy.event_accumulation_score} step={0.01} onChange={(value) => onPolicyChange('event_accumulation_score', value)} /></Field>
          </div>
          <LobSpecificFields policy={policy} updatePolicy={onPolicyChange} />
        </Panel>
      </div>

      <div className="model-tab-strip">
        {modelTabs.map((tab) => (
          <button key={tab.id} className={`model-tab ${activeTab === tab.id ? 'active' : ''}`} onClick={() => onTabChange(tab.id)}>
            {tab.label}
          </button>
        ))}
      </div>

      {!summary ? (
        <Panel title="Model Output" icon={BarChart3}>
          <EmptyState label={busy === 'model' ? 'Training and calculating model output' : 'Run the model to load this view'} />
        </Panel>
      ) : (
        <>
          {activeTab === 'underwriting' && (
            <div className="layout-grid two-col">
              <Panel title="Underwriting Decision" icon={Gauge}>
                <MetricRow values={[
                  ['Decision', statusLabel(summary.underwriting.decision === 'refer' ? 'requires_review' : summary.underwriting.decision)],
                  ['Offered premium', formatSar(summary.underwriting.recommended_premium_sar)],
                  ['Risk score', `${summary.underwriting.risk_score.toFixed(1)}/100`],
                  ['Expected loss', formatSar(summary.underwriting.expected_loss_sar)]
                ]} />
                <TextList title="Decision reasons" items={summary.underwriting.decision_reasons} />
                <TextList title="Detailed explanation" items={summary.underwriting.decision_explanation.drivers} />
                <TextList title="What can make it acceptable" items={summary.underwriting.decision_explanation.recommended_actions} />
              </Panel>
              <Panel title="Premium & Capital" icon={BarChart3}>
                <MiniBarChart rows={summary.underwriting.premium_breakdown.filter((row) => row.Component !== 'Technical premium')} labelKey="Component" valueKey="Amount SAR" valueFormatter={formatSar} />
                <DataTable rows={summary.underwriting.premium_breakdown} />
                <div className="model-section-gap" />
                <MiniBarChart rows={summary.underwriting.rbc_modules} labelKey="module" valueKey="capital_sar" valueFormatter={formatSar} />
                <MetricRow values={[
                  ['SCR impact', formatSar(summary.underwriting.scr_impact_sar)],
                  ['SCR / premium', summary.underwriting.scr_to_premium.toFixed(2)],
                  ['Claim probability', formatPercent(summary.underwriting.claim_probability)],
                  ['RBC benefit', formatSar(summary.underwriting.rbc_diversification_benefit_sar)]
                ]} />
                <DataTable rows={summary.underwriting.pricing_reconciliation} />
                <p className="model-footnote">{summary.underwriting.model_basis} {summary.underwriting.proxy_basis}</p>
              </Panel>
              <Panel title="Rule Checks" icon={ShieldAlert}>
                <DataTable rows={summary.underwriting.decision_explanation.rule_evaluations} />
              </Panel>
            </div>
          )}

          {activeTab === 'data' && (
            <div className="layout-grid two-col">
              <Panel title="Portfolio Data" icon={Database}>
                <MetricRow values={[
                  ['Policies', summary.data.metrics.policies.toLocaleString()],
                  ['Claim rate', formatPercent(summary.data.metrics.claim_rate)],
                  ['Mean premium', formatSar(summary.data.metrics.mean_technical_premium_sar)],
                  ['Mean expected loss', formatSar(summary.data.metrics.mean_expected_loss_sar)]
                ]} />
                <MiniBarChart rows={summary.data.lob_counts} labelKey="LOB" valueKey="Policies" />
                <DataTable rows={summary.data.loss_ratio_by_lob} />
              </Panel>
              <Panel title="Data Feeds" icon={FileText}>
                <div className="form-grid two compact-fields">
                  <Field label="Feed">
                    <select value={activeFeed} onChange={(event) => setSelectedFeed(event.target.value)}>
                      {feedNames.map((name) => <option key={name}>{name}</option>)}
                    </select>
                  </Field>
                </div>
                <DataTable rows={summary.data.metadata_coverage} />
                <div className="model-section-gap" />
                <DataTable rows={summary.data.table_previews[activeFeed] ?? []} />
              </Panel>
            </div>
          )}

          {activeTab === 'actuarial' && (
            <div className="layout-grid two-col">
              <Panel title="GLM Baseline" icon={LineChart}>
                <p className="model-footnote">{summary.actuarial.basis}</p>
                <DataTable rows={summary.actuarial.diagnostics} />
              </Panel>
              <Panel title="Indications" icon={BarChart3}>
                <MiniBarChart rows={summary.actuarial.indication_summary} labelKey="lob" valueKey="avg_expected_loss_sar" valueFormatter={formatSar} />
                <DataTable rows={summary.actuarial.indication_summary} />
              </Panel>
              <Panel title="Sample GLM Output" icon={Database}>
                <DataTable rows={summary.actuarial.sample_indications} />
              </Panel>
            </div>
          )}

          {activeTab === 'diagnostics' && (
            <div className="layout-grid two-col">
              <Panel title="Predictive ML Diagnostics" icon={Gauge}>
                <DataTable rows={summary.diagnostics.model_diagnostics} />
              </Panel>
              <Panel title="SHAP Explanation" icon={Sparkles}>
                <p className="model-footnote">{summary.diagnostics.shap_error ? `${summary.diagnostics.shap_method}: ${summary.diagnostics.shap_error}` : summary.diagnostics.shap_method}</p>
                <MiniBarChart rows={summary.diagnostics.shap_features} labelKey="feature" valueKey="absolute_contribution" />
                <DataTable rows={summary.diagnostics.shap_features} />
              </Panel>
              <Panel title="Frequency Importance" icon={BarChart3}>
                <DataTable rows={summary.diagnostics.frequency_importance} />
              </Panel>
              <Panel title="Severity Importance" icon={BarChart3}>
                <DataTable rows={summary.diagnostics.severity_importance} />
              </Panel>
            </div>
          )}

          {activeTab === 'reserving' && (
            <div className="layout-grid two-col">
              <Panel title="Reserve Summary" icon={BookOpen}>
                <p className="model-footnote">{summary.reserving.basis}</p>
                <DataTable rows={summary.reserving.reserve_summary} />
              </Panel>
              <Panel title="Link Ratios" icon={LineChart}>
                <DataTable rows={summary.reserving.link_ratios} />
              </Panel>
              <Panel title="Paid Triangle" icon={Database}>
                <DataTable rows={summary.reserving.paid_triangle} />
              </Panel>
              <Panel title="Incurred Triangle" icon={Database}>
                <DataTable rows={summary.reserving.incurred_triangle} />
              </Panel>
            </div>
          )}

          {activeTab === 'capital' && (
            <div className="layout-grid two-col">
              <Panel title="Expanded SCR" icon={ShieldAlert}>
                <MetricRow values={[
                  ['Standalone capital', formatSar(summary.capital.standalone_sum_sar)],
                  ['Diversified SCR', formatSar(summary.capital.diversified_scr_sar)],
                  ['Diversification benefit', formatSar(summary.capital.diversification_benefit_sar)],
                  ['Legacy sample SCR', formatSar(summary.capital.legacy_diversified_scr_sar)]
                ]} />
                <MiniBarChart rows={summary.capital.module_table} labelKey="module_label" valueKey="capital_sar" valueFormatter={formatSar} />
                <DataTable rows={summary.capital.module_table} />
              </Panel>
              <Panel title="Capital Detail" icon={Database}>
                <div className="form-grid two compact-fields">
                  <Field label="Detail">
                    <select value={activeCapitalDetail} onChange={(event) => setSelectedCapitalDetail(event.target.value)}>
                      {capitalDetailNames.map((name) => <option key={name}>{name.replaceAll('_', ' ')}</option>)}
                    </select>
                  </Field>
                </div>
                <DataTable rows={summary.capital.details[activeCapitalDetail] ?? []} />
              </Panel>
              <Panel title="Expanded Module Correlations" icon={LineChart}>
                <DataTable rows={summary.capital.correlation_matrix} />
              </Panel>
              <Panel title="Legacy Three-Module Sample" icon={BarChart3}>
                <DataTable rows={summary.capital.legacy_lob_capital} />
              </Panel>
            </div>
          )}

          {activeTab === 'scenarios' && (
            <Panel title="Scenario Comparison" icon={LineChart}>
              <MiniBarChart rows={summary.scenarios.comparison} labelKey="scenario" valueKey="diversified_scr_sar" valueFormatter={formatSar} />
              <DataTable rows={summary.scenarios.comparison} />
            </Panel>
          )}

          {activeTab === 'rules' && (
            <div className="layout-grid two-col">
              <Panel title="Business Rules" icon={ShieldAlert}>
                <DataTable rows={summary.rules.business_rules} />
              </Panel>
              <Panel title="Decision Thresholds" icon={Gauge}>
                <DataTable rows={summary.rules.thresholds} />
              </Panel>
              <Panel title="LOB Appetite Limits" icon={Database}>
                <DataTable rows={summary.rules.appetite} />
              </Panel>
            </div>
          )}

          {activeTab === 'proxy' && (
            <div className="layout-grid two-col">
              <Panel title="LOB Factors" icon={SlidersHorizontal}>
                <DataTable rows={summary.proxy_factors.lob_factors} />
              </Panel>
              <Panel title="Three-Module Correlations" icon={LineChart}>
                <DataTable rows={summary.proxy_factors.three_module_correlations} />
              </Panel>
              <Panel title="Expanded SCR Correlations" icon={LineChart}>
                <DataTable rows={summary.proxy_factors.expanded_correlations} />
              </Panel>
              <Panel title="Scenario Assumptions" icon={Database}>
                <DataTable rows={summary.proxy_factors.scenario_assumptions} />
              </Panel>
              <Panel title="Generated RBC Factor Feed" icon={FileText}>
                <DataTable rows={summary.proxy_factors.rbc_factors} />
                <p className="model-footnote">{summary.run.data_notice}</p>
              </Panel>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function TextList({ title, items }: { title: string; items: string[] }) {
  return <div className="model-text-list"><h3>{title}</h3>{items.map((item) => <p key={item}>{item}</p>)}</div>;
}

function MiniBarChart({ rows, labelKey, valueKey, valueFormatter }: { rows: ModelTableRow[]; labelKey: string; valueKey: string; valueFormatter?: (value: number) => string }) {
  if (!rows.length) return <EmptyState label="No chart data" />;
  const values = rows.map((row) => Math.abs(Number(row[valueKey] ?? 0))).filter((value) => Number.isFinite(value));
  const max = Math.max(...values, 1);
  return (
    <div className="mini-bar-chart">
      {rows.slice(0, 12).map((row, index) => {
        const value = Number(row[valueKey] ?? 0);
        const width = `${Math.max(2, Math.abs(value) / max * 100)}%`;
        return (
          <div className="mini-bar-row" key={`${String(row[labelKey])}-${index}`}>
            <span>{String(row[labelKey] ?? '-')}</span>
            <div><i style={{ width }} /></div>
            <strong>{valueFormatter ? valueFormatter(value) : formatCellValue(value)}</strong>
          </div>
        );
      })}
    </div>
  );
}

function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return '-';
  return `${(value * 100).toFixed(1)}%`;
}

function formatCellValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return '-';
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  if (typeof value === 'number') {
    if (!Number.isFinite(value)) return '-';
    if (Math.abs(value) >= 100000) return value.toLocaleString(undefined, { maximumFractionDigits: 0 });
    if (Math.abs(value) >= 1000) return value.toLocaleString(undefined, { maximumFractionDigits: 1 });
    if (Math.abs(value) > 0 && Math.abs(value) < 1) return value.toLocaleString(undefined, { maximumFractionDigits: 4 });
    return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
  }
  return String(value);
}

function UnstructuredIntakeView({
  records,
  currentRecord,
  draft,
  config,
  busy,
  onUpload,
  onSelect,
  onExtract,
  onApprove,
  onReject,
  updateApplicant,
  updatePolicy,
  changeLob
}: {
  records: UnstructuredRecord[];
  currentRecord: UnstructuredRecord | null;
  draft: ApplicationCreate | null;
  config: ConfigPayload | null;
  busy: BusyAction;
  onUpload: (files: FileList | null) => void;
  onSelect: (record: UnstructuredRecord) => void;
  onExtract: () => void;
  onApprove: () => void;
  onReject: () => void;
  updateApplicant: (key: keyof Applicant, value: string) => void;
  updatePolicy: (key: string, value: string | number) => void;
  changeLob: (lob: string) => void;
}) {
  const isReviewable = currentRecord?.status === 'needs_review';
  const isConverted = currentRecord?.status === 'application_created';
  return (
    <div className="layout-grid unstructured-layout">
      <section className="intake-rail">
        <div className="intake-rail-primary">
          <label className="upload-compact">
            <input type="file" multiple accept=".eml,.pdf,.csv,.xlsx,.xls" onChange={(event) => onUpload(event.target.files)} />
            <UploadCloud size={17} />
            <span>Upload</span>
            <small>.eml .pdf .csv .xlsx .xls</small>
          </label>
          <button onClick={onExtract} disabled={!currentRecord || busy !== null || isConverted}>
            {busy === 'extract' ? <Loader2 className="spin" size={16} /> : <Sparkles size={16} />} Extract
          </button>
          <button className="primary-button" onClick={onApprove} disabled={!draft || !isReviewable || busy !== null}>
            {busy === 'approveExtraction' ? <Loader2 className="spin" size={16} /> : <ClipboardCheck size={16} />} Approve
          </button>
          <button className="danger-button" onClick={onReject} disabled={!currentRecord || !isReviewable || busy !== null}>
            {busy === 'rejectExtraction' ? <Loader2 className="spin" size={16} /> : <XCircle size={16} />} Reject
          </button>
        </div>
        <div className="intake-record-strip">
          {records.length === 0 && <span className="record-empty">No uploaded records</span>}
          {records.map((record) => (
            <button key={record.id} className={`record-chip ${currentRecord?.id === record.id ? 'selected' : ''}`} onClick={() => onSelect(record)}>
              <span>{record.original_filename}</span>
              <em>{record.file_extension.toUpperCase()} {record.batch_index > 0 ? `row ${record.batch_index + 1}` : ''}</em>
              <strong className={`status-pill ${unstructuredStatusClass(record.status)}`}>{statusLabel(record.status)}</strong>
            </button>
          ))}
        </div>
      </section>

      <div className="hitl-grid">
        <Panel title="Raw Record" icon={Eye}>
          <RawRecordPreview record={currentRecord} />
        </Panel>

        <Panel title="Extracted Values" icon={Sparkles}>
          {!currentRecord || !draft ? (
            <EmptyState label="No extraction selected" />
          ) : (
            <>
              {currentRecord.error_message && <div className="error-banner compact-error"><XCircle size={16} /> {currentRecord.error_message}</div>}
              <ExtractionSignals record={currentRecord} />
              <div className="form-grid two">
                <ConfidenceField label="Applicant type" confidence={confidenceFor(currentRecord, 'applicant.applicant_type')}>
                  <select value={draft.applicant.applicant_type} onChange={(event) => updateApplicant('applicant_type', event.target.value)}>
                    <option value="company">Company</option>
                    <option value="individual">Individual</option>
                  </select>
                </ConfidenceField>
                <ConfidenceField label="Applicant name" confidence={confidenceFor(currentRecord, 'applicant.name')}>
                  <input value={draft.applicant.name} onChange={(event) => updateApplicant('name', event.target.value)} />
                </ConfidenceField>
                <ConfidenceField label="National ID / CR" confidence={confidenceFor(currentRecord, 'applicant.national_id_or_cr')}>
                  <input value={draft.applicant.national_id_or_cr} onChange={(event) => updateApplicant('national_id_or_cr', event.target.value)} />
                </ConfidenceField>
                <ConfidenceField label="Email" confidence={confidenceFor(currentRecord, 'applicant.email')}>
                  <input value={draft.applicant.email ?? ''} onChange={(event) => updateApplicant('email', event.target.value)} />
                </ConfidenceField>
                <ConfidenceField label="Phone" confidence={confidenceFor(currentRecord, 'applicant.phone')}>
                  <input value={draft.applicant.phone ?? ''} onChange={(event) => updateApplicant('phone', event.target.value)} />
                </ConfidenceField>
                <ConfidenceField label="LOB" confidence={confidenceFor(currentRecord, 'policy.lob')}>
                  <select value={draft.policy.lob} onChange={(event) => changeLob(event.target.value)}>
                    {(config?.lobs ?? lobs).map((lob) => <option key={lob}>{lob}</option>)}
                  </select>
                </ConfidenceField>
                <ConfidenceField label="Region" confidence={confidenceFor(currentRecord, 'policy.region')}>
                  <select value={draft.policy.region} onChange={(event) => updatePolicy('region', event.target.value)}>
                    {(config ? Object.keys(config.regions) : regions).map((region) => <option key={region}>{region}</option>)}
                  </select>
                </ConfidenceField>
                <ConfidenceField label="Reinsurer rating" confidence={confidenceFor(currentRecord, 'policy.counterparty_rating')}>
                  <select value={draft.policy.counterparty_rating} onChange={(event) => updatePolicy('counterparty_rating', event.target.value)}>
                    {(config?.counterparty_ratings ?? ratings).map((rating) => <option key={rating}>{rating}</option>)}
                  </select>
                </ConfidenceField>
                <ConfidenceField label="Term months" confidence={confidenceFor(currentRecord, 'policy.term_months')}>
                  <NumberInput value={draft.policy.term_months} onChange={(value) => updatePolicy('term_months', value)} />
                </ConfidenceField>
                <ConfidenceField label="Exposure value" confidence={confidenceFor(currentRecord, 'policy.exposure_value_sar')}>
                  <NumberInput value={draft.policy.exposure_value_sar} onChange={(value) => updatePolicy('exposure_value_sar', value)} />
                </ConfidenceField>
                <ConfidenceField label="Coverage limit" confidence={confidenceFor(currentRecord, 'policy.limit_sar')}>
                  <NumberInput value={draft.policy.limit_sar} onChange={(value) => updatePolicy('limit_sar', value)} />
                </ConfidenceField>
                <ConfidenceField label="Deductible" confidence={confidenceFor(currentRecord, 'policy.deductible_sar')}>
                  <NumberInput value={draft.policy.deductible_sar} onChange={(value) => updatePolicy('deductible_sar', value)} />
                </ConfidenceField>
                <ConfidenceField label="Prior claims" confidence={confidenceFor(currentRecord, 'policy.prior_claims_3y')}>
                  <NumberInput value={draft.policy.prior_claims_3y} onChange={(value) => updatePolicy('prior_claims_3y', value)} />
                </ConfidenceField>
                <ConfidenceField label="Risk controls" confidence={confidenceFor(currentRecord, 'policy.risk_control_score')}>
                  <NumberInput value={draft.policy.risk_control_score} onChange={(value) => updatePolicy('risk_control_score', value)} />
                </ConfidenceField>
                <ConfidenceField label="Reinsurance ceded" confidence={confidenceFor(currentRecord, 'policy.reinsurance_ceded_pct')}>
                  <NumberInput value={draft.policy.reinsurance_ceded_pct} step={0.01} onChange={(value) => updatePolicy('reinsurance_ceded_pct', value)} />
                </ConfidenceField>
                <ConfidenceField label="Event accumulation" confidence={confidenceFor(currentRecord, 'policy.event_accumulation_score')}>
                  <NumberInput value={draft.policy.event_accumulation_score} step={0.01} onChange={(value) => updatePolicy('event_accumulation_score', value)} />
                </ConfidenceField>
              </div>
              <LobSpecificFields policy={draft.policy} updatePolicy={updatePolicy} />
              {isConverted && currentRecord.application_id && <div className="success-note"><CheckCircle2 size={16} /> Application {currentRecord.application_id} created.</div>}
            </>
          )}
        </Panel>
      </div>
    </div>
  );
}

function RawRecordPreview({ record }: { record: UnstructuredRecord | null }) {
  if (!record) return <EmptyState label="No raw record selected" />;
  const previewText = record.raw_preview.text || record.raw_text;
  return (
    <div className="raw-preview">
      {record.file_extension === '.pdf' && (
        <iframe title="Raw PDF preview" src={unstructuredRawUrl(record.id, `${record.updated_at}-${record.raw_text.length}-${record.raw_text.slice(0, 32)}`)} />
      )}
      <pre>{previewText}</pre>
    </div>
  );
}

function ExtractionSignals({ record }: { record: UnstructuredRecord }) {
  const signals = [...record.missing_fields.map((field) => `Missing: ${field}`), ...record.warnings];
  if (!signals.length) return null;
  return <div className="signal-list">{signals.slice(0, 8).map((signal) => <span key={signal}>{signal}</span>)}</div>;
}

function ConfidenceField({ label, confidence, children }: { label: string; confidence?: FieldConfidence; children: React.ReactNode }) {
  return (
    <Field label={<span className="field-heading"><span>{label}</span><ConfidenceBadge confidence={confidence} /></span>}>
      {children}
    </Field>
  );
}

function ConfidenceBadge({ confidence }: { confidence?: FieldConfidence }) {
  const level = confidence?.confidence ?? 'low';
  const title = [confidence?.evidence, confidence?.rationale].filter(Boolean).join(' | ');
  return <span className={`confidence-badge ${level}`} title={title}>{level}</span>;
}

function unstructuredStatusClass(status: string): string {
  if (status === 'failed' || status === 'rejected') return 'danger';
  if (status === 'needs_review' || status === 'extracting') return 'warning';
  if (status === 'application_created' || status === 'approved') return 'success';
  return 'neutral';
}

function Panel({ title, icon: Icon, children }: { title: string; icon: typeof FileText; children: React.ReactNode }) {
  return (
    <section className="panel">
      <div className="panel-header"><Icon size={18} /><h2>{title}</h2></div>
      {children}
    </section>
  );
}

function Field({ label, children }: { label: React.ReactNode; children: React.ReactNode }) {
  return <label className="field">{typeof label === 'string' ? <span>{label}</span> : label}{children}</label>;
}

function NumberInput({ value, onChange, step = 1 }: { value: string | number | undefined; onChange: (value: number) => void; step?: number }) {
  return <input type="number" value={Number(value ?? 0)} step={step} onChange={(event) => onChange(Number(event.target.value))} />;
}

function LobSpecificFields({ policy, updatePolicy }: { policy: PolicyPayload; updatePolicy: (key: string, value: string | number) => void }) {
  if (policy.lob === 'Motor') {
    return <div className="form-grid three compact-fields"><Field label="Policy type"><select value={String(policy.policy_type)} onChange={(e) => updatePolicy('policy_type', e.target.value)}><option>Comprehensive</option><option>Compulsory</option></select></Field><Field label="Vehicle class"><select value={String(policy.vehicle_class)} onChange={(e) => updatePolicy('vehicle_class', e.target.value)}><option>Private car</option><option>SUV</option><option>Taxi/ride-hailing</option><option>Light commercial</option><option>Heavy truck</option></select></Field><Field label="Driver age"><NumberInput value={policy.driver_age} onChange={(v) => updatePolicy('driver_age', v)} /></Field><Field label="Vehicle age"><NumberInput value={policy.vehicle_age} onChange={(v) => updatePolicy('vehicle_age', v)} /></Field><Field label="Fleet size"><NumberInput value={policy.fleet_size} onChange={(v) => updatePolicy('fleet_size', v)} /></Field></div>;
  }
  if (policy.lob === 'Property & Fire') {
    return <div className="form-grid three compact-fields"><Field label="Occupancy"><select value={String(policy.occupancy_type)} onChange={(e) => updatePolicy('occupancy_type', e.target.value)}><option>Residential</option><option>Retail</option><option>Warehouse</option><option>Manufacturing</option><option>Petrochemical support</option></select></Field><Field label="Hazard score"><NumberInput value={policy.occupancy_hazard_score} step={0.01} onChange={(v) => updatePolicy('occupancy_hazard_score', v)} /></Field><Field label="Fire protection"><NumberInput value={policy.fire_protection_score} step={0.01} onChange={(v) => updatePolicy('fire_protection_score', v)} /></Field><Field label="Construction quality"><NumberInput value={policy.construction_quality_score} step={0.01} onChange={(v) => updatePolicy('construction_quality_score', v)} /></Field></div>;
  }
  if (policy.lob === 'Engineering & Construction') {
    return <div className="form-grid three compact-fields"><Field label="Project type"><select value={String(policy.project_type)} onChange={(e) => updatePolicy('project_type', e.target.value)}><option>Civil works</option><option>Power/renewables</option><option>Metro/rail</option><option>Industrial plant</option><option>Giga-project package</option></select></Field><Field label="Complexity"><NumberInput value={policy.project_complexity_score} step={0.01} onChange={(v) => updatePolicy('project_complexity_score', v)} /></Field><Field label="Duration months"><NumberInput value={policy.project_duration_months} onChange={(v) => updatePolicy('project_duration_months', v)} /></Field><Field label="Contractor years"><NumberInput value={policy.contractor_experience_years} onChange={(v) => updatePolicy('contractor_experience_years', v)} /></Field></div>;
  }
  if (policy.lob === 'Marine & Cargo') {
    return <div className="form-grid three compact-fields"><Field label="Cargo type"><select value={String(policy.cargo_type)} onChange={(e) => updatePolicy('cargo_type', e.target.value)}><option>General cargo</option><option>Electronics</option><option>Pharma/cold chain</option><option>Project cargo</option><option>Hazardous cargo</option></select></Field><Field label="Cargo risk"><NumberInput value={policy.cargo_type_risk_score} step={0.01} onChange={(v) => updatePolicy('cargo_type_risk_score', v)} /></Field><Field label="Transit km"><NumberInput value={policy.transit_distance_km} onChange={(v) => updatePolicy('transit_distance_km', v)} /></Field><Field label="Storage days"><NumberInput value={policy.storage_days} onChange={(v) => updatePolicy('storage_days', v)} /></Field></div>;
  }
  return <div className="form-grid three compact-fields"><Field label="Liability type"><select value={String(policy.liability_type)} onChange={(e) => updatePolicy('liability_type', e.target.value)}><option>General liability</option><option>Professional indemnity</option><option>D&O</option><option>Product liability</option></select></Field><Field label="Revenue"><NumberInput value={policy.annual_revenue_sar} onChange={(v) => updatePolicy('annual_revenue_sar', v)} /></Field><Field label="Limit intensity"><NumberInput value={policy.liability_limit_factor} step={0.01} onChange={(v) => updatePolicy('liability_limit_factor', v)} /></Field><Field label="Professional risk"><NumberInput value={policy.professional_risk_score} step={0.01} onChange={(v) => updatePolicy('professional_risk_score', v)} /></Field></div>;
}

function EnrichmentList({ item }: { item: UnderwritingCase | null }) {
  if (!item?.enrichments.length) return <EmptyState label="No enrichment results" />;
  return (
    <div className="timeline">
      {item.enrichments.map((result) => (
        <div className="timeline-card enrichment-card" key={result.provider}>
          <div className="enrichment-heading">
            <strong>{result.provider.replaceAll('_', ' ')}</strong>
            <span className="enrichment-confidence">{Math.round(result.confidence * 100)}% confidence</span>
          </div>
          <div className="flag-row">
            {result.flags.length
              ? result.flags.map((flag) => <span key={flag.code} className={'flag ' + flag.severity}>{flag.label}</span>)
              : <span className="flag low">Clear</span>}
          </div>
        </div>
      ))}
    </div>
  );
}

function DecisionSummary({ item }: { item: UnderwritingCase }) {
  const decision = item.latest_decision;
  if (!decision) return null;
  return <div className="decision-block"><span className={`status-pill ${decision.decision_bucket === 'declined' ? 'danger' : decision.decision_bucket === 'requires_review' ? 'warning' : 'success'}`}>{decision.decision_bucket === 'stp' ? 'STP' : statusLabel(decision.decision_bucket)}</span><div className="reason-list">{decision.reasons.slice(0, 6).map((reason) => <p key={reason}>{reason}</p>)}</div></div>;
}

function RatingSummary({ rating }: { rating: NonNullable<UnderwritingCase['latest_rating']> }) {
  return <div className="rating-block"><MetricRow values={[["Adjusted premium", formatSar(rating.adjusted_premium_sar)], ["Expected loss", formatSar(rating.expected_loss_sar)], ["Risk score", `${rating.risk_score.toFixed(1)}/100`], ["SCR", formatSar(rating.scr_impact_sar)]]} /><div className="adjustments">{rating.adjustments.map((adj) => <div key={adj.code}><span>{adj.label}</span><strong>{(adj.pct * 100).toFixed(1)}%</strong></div>)}</div></div>;
}

function QuoteDetails({ item }: { item: UnderwritingCase }) {
  const quote = item.latest_quote;
  if (!quote) return null;
  return <div className="quote-box"><h3>{quote.quote_number}</h3><MetricRow values={[["Premium", formatSar(quote.premium_sar)], ["Expires", quote.expires_at], ["Deductible", formatSar(quote.deductible_sar)], ["Policy", item.bound_policies.at(-1)?.policy_number ?? '-']]} /></div>;
}

function QuotePreview({ quoteId, quoteNumber }: { quoteId: string; quoteNumber: string }) {
  return (
    <div className="quote-preview">
      <div className="quote-preview-header">
        <div>
          <h3>Quote preview</h3>
          <span>{quoteNumber}</span>
        </div>
        <a className="secondary-link" href={quotePdfUrl(quoteId)} target="_blank" rel="noreferrer"><Download size={16} /> Open PDF</a>
      </div>
      <iframe title={'Quote preview ' + quoteNumber} src={quotePdfUrl(quoteId)} />
    </div>
  );
}

function AuditTrail({ item }: { item: UnderwritingCase | null }) {
  if (!item?.audit_events.length) return <EmptyState label="No audit events" />;
  return <div className="audit-list">{item.audit_events.slice().reverse().map((event) => <div className="audit-row" key={event.id}><span>{event.event_type}</span><strong>{event.actor}</strong><em>{new Date(event.created_at).toLocaleString()}</em></div>)}</div>;
}

function MetricRow({ values }: { values: Array<[string, string]> }) {
  return <div className="metric-row">{values.map(([label, value]) => <div className="metric" key={label}><span>{label}</span><strong>{value}</strong></div>)}</div>;
}

function DataTable({ rows }: { rows: Array<Record<string, unknown>> }) {
  if (!rows.length) return <EmptyState label="No records" />;
  const columns = Object.keys(rows[0]);
  return <div className="table-wrap"><table><thead><tr>{columns.map((column) => <th key={column}>{column}</th>)}</tr></thead><tbody>{rows.map((row, index) => <tr key={index}>{columns.map((column) => <td key={column}>{formatCellValue(row[column])}</td>)}</tr>)}</tbody></table></div>;
}

function EmptyState({ label }: { label: string }) {
  return <div className="empty-state">{label}</div>;
}

export default App;
