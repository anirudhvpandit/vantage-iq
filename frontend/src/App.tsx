import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import AuthPage from "./AuthPage";
import { useAuth, type AuthSession } from "./auth";
import { request } from "./api";
import {
  Activity,
  ArrowDownRight,
  ArrowRight,
  ArrowUpRight,
  Bell,
  BriefcaseBusiness,
  Building2,
  CalendarDays,
  Check,
  CircleHelp,
  CloudUpload,
  Command,
  Database,
  Download,
  FileBarChart2,
  FileDown,
  Gauge,
  LayoutDashboard,
  LogOut,
  Menu,
  Moon,
  Search,
  Settings,
  ShieldAlert,
  Sun,
  Users,
  UsersRound,
  Wallet,
  Target,
  X,
} from "lucide-react";
import {
  ArcElement,
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  Filler,
  Legend,
  LinearScale,
  LineElement,
  PointElement,
  Tooltip,
} from "chart.js";
import { Bar, Doughnut, Line } from "react-chartjs-2";

ChartJS.register(
  ArcElement,
  BarElement,
  CategoryScale,
  Filler,
  Legend,
  LinearScale,
  LineElement,
  PointElement,
  Tooltip,
);

const API = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
const navItems = [
  { label: "Overview", icon: LayoutDashboard, group: "Workspace" },
  { label: "Financial performance", icon: Wallet, group: "Workspace" },
  { label: "Revenue & sales", icon: Activity, group: "Workspace" },
  { label: "Projects & delivery", icon: BriefcaseBusiness, group: "Workspace" },
  { label: "Customers", icon: Users, group: "Workspace" },
  { label: "Departments", icon: Building2, group: "Workspace" },
  { label: "Budgets & goals", icon: Target, group: "Workspace" },
  { label: "Data imports", icon: CloudUpload, group: "Manage" },
  { label: "KPI dictionary", icon: FileBarChart2, group: "Manage" },
  { label: "Alerts", icon: ShieldAlert, group: "Manage" },
  { label: "Team & access", icon: UsersRound, group: "Manage" },
  { label: "Reports", icon: FileDown, group: "Manage" },
  { label: "Settings", icon: Settings, group: "Manage" },
  { label: "Business records", icon: Database, group: "Manage" },
];

type Metric = { value: number | null; change_percent?: number | null; change_points?: number | null; previous?: number | null };
type Overview = {
  organization: { name: string; currency: string; synthetic_data: boolean };
  period: { start: string; end: string; comparison_start: string; comparison_end: string; comparison_available: boolean };
  metrics: {
    revenue: Metric;
    operating_costs: Metric;
    operating_profit: Metric;
    operating_margin: Metric;
    budget_achievement: Metric;
    on_time_delivery: Metric & { eligible_completed_projects: number };
    customer_activity: Metric & { definition: string };
  };
  trend: { labels: string[]; revenue: number[]; operating_costs: number[] };
  revenue_by_department: { name: string; value: number }[];
  cost_by_category: { name: string; value: number }[];
  freshness: string;
};

function useOverview(organizationId: number | null, start: string, end: string) {
  return useQuery({
    queryKey: ["overview", organizationId, start, end],
    queryFn: () => request<Overview>(`/api/v1/overview?start_date=${start}&end_date=${end}`),
  });
}

function currency(value: number | null | undefined, code = "USD", compact = false) {
  if (value == null || !Number.isFinite(value)) return "—";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: code,
    maximumFractionDigits: compact ? 1 : 0,
    notation: compact ? "compact" : "standard",
  }).format(value);
}

function percent(value: number | null | undefined, digits = 1) {
  return value == null || !Number.isFinite(value) ? "—" : `${value.toFixed(digits)}%`;
}

function dateInput(value: Date) {
  const local = new Date(value.getTime() - value.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 10);
}

export default function App() {
  const { session, isLoading, error } = useAuth();
  const location = useLocation();
  if (isLoading) return <div className="auth-loading"><span className="loading-spinner" />Loading your workspace…</div>;
  if (error) return <div className="auth-loading" role="alert">Your session could not be verified: {error}</div>;
  if (!session) {
    if (["/login", "/register", "/verify-email", "/reset-password", "/forgot-password", "/resend-verification"].includes(location.pathname)) return <AuthPage />;
    return <Navigate to="/login" replace />;
  }
  if (location.pathname === "/login" || location.pathname === "/register" || location.pathname === "/") {
    return <Navigate to="/app/overview" replace />;
  }
  return <WorkspaceApp session={session} />;
}

function WorkspaceApp({ session }: { session: AuthSession }) {
  const location = useLocation();
  const navigate = useNavigate();
  const routeSegment = location.pathname.split("/").pop();
  const page = navItems.find((item) => pagePath(item.label) === routeSegment)?.label || "Overview";
  const setPage = (target: string) => navigate(`/app/${pagePath(target)}`);
  const activeMembership = session.memberships.find((item) => item.organization_id === session.active_organization_id);
  const [start, setStart] = useState(() => {
    if (activeMembership?.is_demo) return "2025-11-01";
    const previousYear = new Date();
    previousYear.setFullYear(previousYear.getFullYear() - 1);
    return dateInput(previousYear);
  });
  const [end, setEnd] = useState(() => activeMembership?.is_demo ? "2026-10-31" : dateInput(new Date()));
  const [dark, setDark] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const overview = useOverview(session.active_organization_id, start, end);
  const { logout, selectOrganization } = useAuth();
  const maxDate = activeMembership?.is_demo ? "2026-10-31" : dateInput(new Date());
  const minDate = activeMembership?.is_demo ? "2024-11-01" : "1970-01-01";
  const alertCount = useQuery({
    queryKey: ["alerts-count", session.active_organization_id],
    queryFn: () => request<{ items: { acknowledged: boolean }[] }>("/api/v1/alerts"),
  }).data?.items.filter((alert) => !alert.acknowledged).length || 0;

  const title = page === "Overview" ? "Executive overview" : page;

  useEffect(() => {
    const navigate = (event: Event) => {
      const target = (event as CustomEvent<string>).detail;
      if (target) setPage(target);
    };
    const handleShortcut = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setSearchOpen(true);
        window.setTimeout(() => document.getElementById("global-search")?.focus(), 0);
      }
      if (event.key === "Escape") setSearchOpen(false);
    };
    window.addEventListener("navigate-vantage", navigate);
    window.addEventListener("keydown", handleShortcut);
    return () => {
      window.removeEventListener("navigate-vantage", navigate);
      window.removeEventListener("keydown", handleShortcut);
    };
  }, []);

  return (
    <div className={`app ${dark ? "theme-dark" : ""}`}>
      <aside className={`sidebar ${mobileOpen ? "sidebar-open" : ""}`}>
        <div className="brand">
          <div className="brand-mark"><Gauge size={21} strokeWidth={2.2} /></div>
          <div className="brand-wordmark">vantage<span>iq</span><small>BUSINESS INTELLIGENCE</small></div>
          <button className="icon-button mobile-close" aria-label="Close navigation" onClick={() => setMobileOpen(false)}><X size={18} /></button>
        </div>
        <div className="org-switcher">
          <span className="org-monogram">{activeMembership?.organization_name.slice(0, 1).toUpperCase() || "O"}</span>
          <span className="org-info"><strong>{activeMembership?.organization_name || "Organization"}</strong><small>{activeMembership?.is_demo ? "Synthetic demo workspace" : "Organization workspace"}</small></span>
        </div>
        <div className="side-nav">
          <div className="organization-selector"><Building2 size={15} /><select aria-label="Select organization" value={session.active_organization_id ?? ""} onChange={(event) => selectOrganization(Number(event.target.value))}>{session.memberships.map((membership) => <option key={membership.organization_id} value={membership.organization_id}>{membership.organization_name} · {membership.role}</option>)}</select></div>
          {["Workspace", "Manage"].map((group) => (
            <div className="nav-group" key={group}>
              <div className="nav-label">{group}</div>
              {navItems.filter((item) => item.group === group && (item.label !== "Team & access" || activeMembership?.role === "owner" || activeMembership?.role === "admin")).map(({ label, icon: Icon }) => (
                <Link
                  key={label}
                  className={`nav-item ${page === label ? "active" : ""}`}
                  to={`/app/${pagePath(label)}`}
                  onClick={() => setMobileOpen(false)}
                >
                  <Icon size={17} strokeWidth={1.8} /><span>{label}</span>
                  {label === "Alerts" && alertCount > 0 && <span className="nav-count">{alertCount}</span>}
                </Link>
              ))}
            </div>
          ))}
        </div>
        <div className="sidebar-bottom">
          <div className="help-card">
            <div className="help-icon"><CircleHelp size={17} /></div>
            <div><strong>{activeMembership?.is_demo ? "Synthetic sample" : "Organization workspace"}</strong><small>{activeMembership?.is_demo ? "24 months · 4 departments" : "Tenant-scoped records"}</small></div>
          </div>
          <div className="profile-row">
            <div className="avatar">{initials(session.user?.email || "Demo")}</div>
            <div className="profile-info"><strong>{session.user?.email || "Demo workspace"}</strong><small>{activeMembership?.role || "Member"}</small></div>
            {session.user && <button className="icon-button" aria-label="Sign out" title="Sign out" onClick={() => logout()}><LogOut size={15} /></button>}
          </div>
        </div>
      </aside>
      {mobileOpen && <button className="mobile-backdrop" aria-label="Close navigation overlay" onClick={() => setMobileOpen(false)} />}
      <main className="main">
        <header className="topbar">
          <div className="topbar-left">
            <button className="icon-button mobile-menu" aria-label="Open navigation" onClick={() => setMobileOpen(true)}><Menu size={19} /></button>
            <div className="breadcrumbs"><span>Workspace</span><span className="crumb-slash">/</span><strong>{title}</strong></div>
          </div>
          <div className="topbar-actions">
            <button className="search-trigger" onClick={() => { setSearchOpen(true); window.setTimeout(() => document.getElementById("global-search")?.focus(), 0); }}><Search size={16} /><span>Search pages</span><kbd><Command size={11} /> K</kbd></button>
            <button className="icon-button topbar-icon" aria-label="Toggle color theme" title="Toggle color theme" onClick={() => setDark(!dark)}>{dark ? <Sun size={18} /> : <Moon size={18} />}</button>
            <button className="icon-button topbar-icon notification-button" aria-label="Notifications" onClick={() => setPage("Alerts")}><Bell size={18} /><i /></button>
          </div>
        </header>
        <div className="page-scroll">
          <section className="page-heading">
            <div className="heading-copy">
              <div className="eyebrow"><span className="live-dot" /> {overview.data?.organization.synthetic_data ? "SYNTHETIC DEMO DATA" : "ORGANIZATION DATA"}</div>
              <h1>{title}</h1>
              <p>{pageDescription(page)}</p>
            </div>
            <div className="heading-actions">
              {(page === "Overview" || page === "Financial performance" || page === "Revenue & sales") && (
                <DateRange start={start} end={end} onStart={setStart} onEnd={setEnd} minDate={minDate} maxDate={maxDate} />
              )}
              {page === "Overview" && <a className="button button-primary" href={`${API}/api/v1/reports/executive.csv?start_date=${start}&end_date=${end}`}><Download size={15} /> Export report</a>}
            </div>
          </section>
          {overview.isError && <ErrorBanner message={overview.error.message} />}
          {page === "Overview" && <OverviewPage query={overview} start={start} end={end} />}
          {page === "Financial performance" && <FinancialPage start={start} end={end} />}
          {page === "Revenue & sales" && <RevenuePage start={start} end={end} />}
          {page === "Projects & delivery" && <ProjectsPage />}
          {page === "Customers" && <CustomersPage />}
          {page === "Departments" && <CrudPage resource="departments" title="Departments" fields={[
            { name: "name", label: "Department name", type: "text" },
          ]} />}
          {page === "Budgets & goals" && <CrudPage resource="budgets" title="Budgets & goals" fields={[
            { name: "department_id", label: "Department ID", type: "number" },
            { name: "period_start", label: "Month", type: "date" },
            { name: "revenue_target", label: "Revenue target", type: "number" },
            { name: "expense_budget", label: "Expense budget", type: "number" },
          ]} />}
          {page === "Data imports" && <ImportsPage />}
          {page === "KPI dictionary" && <KpiPage />}
          {page === "Alerts" && <AlertsPage />}
          {page === "Team & access" && <TeamPage session={session} />}
          {page === "Reports" && <ReportsPage start={start} end={end} />}
          {page === "Settings" && <SettingsPage session={session} />}
          {page === "Business records" && <BusinessRecordsPage />}
          <footer className="page-footer"><span>Vantage IQ <b>·</b> {overview.data?.organization.synthetic_data ? "Synthetic demonstration workspace" : activeMembership?.organization_name || "Organization workspace"}</span><span>{overview.data?.freshness || "Data freshness unavailable"}</span></footer>
        </div>
      </main>
      {searchOpen && <div className="search-popover"><div className="search-box"><Search size={16} /><input id="global-search" aria-label="Search" placeholder="Search pages and data" onKeyDown={(event) => {
        const found = navItems.find((item) => item.label.toLowerCase().includes((event.currentTarget.value || "").toLowerCase()));
        if (event.key === "Enter" && found) { setPage(found.label); setSearchOpen(false); }
        if (event.key === "Escape") setSearchOpen(false);
      }} /><button className="icon-button" aria-label="Close search" onClick={() => setSearchOpen(false)}><X size={15} /></button></div><div className="search-hint">Type a workspace page name and press Enter</div></div>}
    </div>
  );
}

function pageDescription(page: string) {
  const descriptions: Record<string, string> = {
    Overview: "A clear, current view of the signals shaping your business.",
    "Financial performance": "Understand recognized revenue, operating costs, and profitability.",
    "Revenue & sales": "Explore customer revenue and keep pipeline value distinct from recognized sales.",
    "Projects & delivery": "Monitor project progress, delivery dates, and budget exposure.",
    Customers: "Review customer contribution, segments, and account ownership.",
    Departments: "Manage the reporting units used to group customers, projects, and budgets.",
    "Budgets & goals": "Set monthly departmental revenue and expense targets.",
    "Data imports": "Validate and safely add recognized revenue records to an authorized organization.",
    "KPI dictionary": "Definitions and calculation notes for the metrics shown in this workspace.",
    Alerts: "Organization-scoped operational exceptions and suggested review actions.",
    "Team & access": "Review organization membership and each member’s assigned role.",
    Reports: "Generate a period-aware executive report for your organization.",
    Settings: "Workspace configuration and implementation details.",
    "Business records": "Create, update, and remove organization-scoped business records.",
  };
  return descriptions[page] || "";
}

function pagePath(label: string) {
  return label.toLowerCase().replace(/&/g, "and").replace(/\s+/g, "-");
}

function DateRange({ start, end, onStart, onEnd, minDate, maxDate }: { start: string; end: string; onStart: (value: string) => void; onEnd: (value: string) => void; minDate: string; maxDate: string }) {
  return (
    <div className="date-range">
      <CalendarDays size={15} />
      <label><span>From</span><input aria-label="Start date" type="date" value={start} min={minDate} max={end} onChange={(event) => onStart(event.target.value)} /></label>
      <span className="date-divider" />
      <label><span>To</span><input aria-label="End date" type="date" value={end} min={start} max={maxDate} onChange={(event) => onEnd(event.target.value)} /></label>
    </div>
  );
}

function ErrorBanner({ message }: { message: string }) {
  return <div className="error-banner" role="alert"><ShieldAlert size={18} /><div><strong>We couldn’t load this data</strong><span>{message}. Check that the API is running, then try again.</span></div></div>;
}

function LoadingPanel() {
  return <div className="loading-panel"><div className="loading-spinner" /><span>Loading workspace data…</span></div>;
}

function OverviewPage({ query, start, end }: { query: ReturnType<typeof useOverview>; start: string; end: string }) {
  if (query.isPending) return <LoadingPanel />;
  if (!query.data) return <div className="empty-panel">No data is available for this reporting period.</div>;
  const data = query.data;
  const metrics = data.metrics;
  const cards = [
    { title: "Recognized revenue", value: currency(metrics.revenue.value, data.organization.currency, true), change: metrics.revenue.change_percent, icon: Wallet, tone: "blue", help: "Sum of recorded recognized revenue in the selected period." },
    { title: "Operating costs", value: currency(metrics.operating_costs.value, data.organization.currency, true), change: metrics.operating_costs.change_percent, icon: Activity, tone: "amber", inverse: true, help: "Sum of recorded operating expenses; no company-wide allocation is made." },
    { title: "Operating profit", value: currency(metrics.operating_profit.value, data.organization.currency, true), change: metrics.operating_profit.change_percent, icon: FileBarChart2, tone: "green", help: "Recognized revenue minus recorded operating costs. Not net profit or EBITDA." },
    { title: "Operating margin", value: percent(metrics.operating_margin.value), change: metrics.operating_margin.change_points, suffix: "pp", icon: Gauge, tone: "violet", help: "Operating profit divided by recognized revenue. Not available when revenue is zero." },
  ];
  return (
    <>
      <div className="context-strip"><div className="context-period"><CalendarDays size={15} /><span><strong>{formatPeriod(start, end)}</strong><small>{data.period.comparison_available ? `Compared with ${formatPeriod(data.period.comparison_start, data.period.comparison_end)}` : `No earlier ${data.organization.synthetic_data ? "synthetic " : ""}history is available for comparison`}</small></span></div><div className="freshness"><span className="freshness-dot" /> {data.freshness}</div></div>
      <section className="kpi-grid">
        {cards.map((card) => <MetricCard key={card.title} {...card} currencyCode={data.organization.currency} />)}
      </section>
      <section className="secondary-kpi-grid">
        <div className="secondary-kpi"><div className="secondary-icon blue-soft"><TargetIcon /></div><div><span>Revenue target achievement</span><strong>{percent(metrics.budget_achievement.value)}</strong><small>Monthly department targets, prorated for selected dates</small></div><span className="secondary-note">Target</span></div>
        <div className="secondary-kpi"><div className="secondary-icon green-soft"><Check size={17} /></div><div><span>On-time delivery</span><strong>{percent(metrics.on_time_delivery.value, 0)}</strong><small>{metrics.on_time_delivery.eligible_completed_projects} completed projects eligible</small></div><span className="secondary-note">Projects</span></div>
        <div className="secondary-kpi"><div className="secondary-icon violet-soft"><Users size={17} /></div><div><span>Customer activity</span><strong>{percent(metrics.customer_activity.value, 0)}</strong><small>Active customers / total organization customers</small></div><span className="secondary-note">Customers</span></div>
      </section>
      <div className="content-grid charts-grid">
        <article className="panel trend-panel">
          <PanelHeading title="Revenue & operating costs" subtitle="Monthly recognized revenue and recorded operating expenses" />
          <div className="chart-wrap trend-chart"><Line data={{
            labels: data.trend.labels,
            datasets: [
              { label: "Recognized revenue", data: data.trend.revenue, borderColor: "#3d7cf6", backgroundColor: "rgba(61,124,246,.10)", fill: true, borderWidth: 2.5, pointRadius: 2.5, pointHoverRadius: 5, tension: .35 },
              { label: "Operating costs", data: data.trend.operating_costs, borderColor: "#9cb0c8", backgroundColor: "transparent", borderWidth: 2, pointRadius: 1.5, pointHoverRadius: 4, tension: .35 },
            ],
          }} options={lineOptions(data.organization.currency)} /></div>
        </article>
        <article className="panel cost-panel">
          <PanelHeading title="Operating cost mix" subtitle="Recorded expense by category" />
          <div className="doughnut-wrap"><Doughnut data={{
            labels: data.cost_by_category.map((item) => item.name),
            datasets: [{ data: data.cost_by_category.map((item) => item.value), backgroundColor: ["#3d7cf6", "#33b6a1", "#f0ac48", "#8b77e8"], borderWidth: 0, hoverOffset: 4 }],
          }} options={{ responsive: true, maintainAspectRatio: false, cutout: "74%", plugins: { legend: { display: false }, tooltip: { callbacks: { label: (ctx) => ` ${ctx.label}: ${currency(Number(ctx.raw), data.organization.currency)}` } } } }} />
            <div className="doughnut-center"><strong>{currency(metrics.operating_costs.value, data.organization.currency, true)}</strong><span>total costs</span></div>
          </div>
          <div className="legend-list">{data.cost_by_category.map((item, index) => <div className="legend-row" key={item.name}><span className={`legend-dot legend-${index}`} /><span>{item.name}</span><strong>{currency(item.value, data.organization.currency, true)}</strong></div>)}</div>
        </article>
      </div>
      <div className="content-grid lower-grid">
        <article className="panel department-panel">
          <PanelHeading title="Revenue by department" subtitle="Contribution to recognized revenue in this period" />
          <div className="chart-wrap department-chart"><Bar data={{
            labels: data.revenue_by_department.map((item) => item.name),
            datasets: [{ label: "Recognized revenue", data: data.revenue_by_department.map((item) => item.value), backgroundColor: ["#3d7cf6", "#5a91fb", "#83aafc", "#b2cbff"], borderRadius: 5, maxBarThickness: 34 }],
          }} options={barOptions(data.organization.currency)} /></div>
        </article>
        <article className="panel insight-panel">
          <PanelHeading title="Management signals" subtitle={data.organization.synthetic_data ? "Observations from the synthetic demo dataset" : "Organization-specific review prompts"} />
          {data.organization.synthetic_data ? <>
            <div className="signal-item"><div className="signal-mark signal-amber"><ShieldAlert size={16} /></div><div><strong>Project delivery needs attention</strong><p>Bluepeak controls upgrade is 20 points behind planned progress.</p><button className="text-button" onClick={() => window.dispatchEvent(new CustomEvent("navigate-vantage", { detail: "Projects & delivery" }))}>Review project <ArrowRight size={13} /></button></div></div>
            <div className="signal-item"><div className="signal-mark signal-blue"><Activity size={16} /></div><div><strong>Customer revenue is changing</strong><p>Lumen Field Partners is flagged for a synthetic revenue decline.</p><button className="text-button" onClick={() => window.dispatchEvent(new CustomEvent("navigate-vantage", { detail: "Customers" }))}>Review account <ArrowRight size={13} /></button></div></div>
          </> : <div className="empty-panel">Organization-specific automated signals are not configured. Review the Alerts page for available records.</div>}
          <div className="insight-disclaimer">Rule-based observations only. They describe measured values and do not infer causes.</div>
        </article>
      </div>
      <div className="dashboard-note"><CircleHelp size={15} /><span>{data.organization.synthetic_data ? "All figures shown are synthetic demo data. " : ""}Revenue means recognized revenue; pipeline value is reported separately.</span></div>
    </>
  );
}

function TargetIcon() {
  return <span className="target-glyph">◎</span>;
}

function MetricCard({ title, value, change, change_points, suffix, icon: Icon, tone, inverse, help, currencyCode }: {
  title: string; value: string; change?: number | null; change_points?: number | null; suffix?: string;
  icon: typeof Wallet; tone: string; inverse?: boolean; help: string; currencyCode: string;
}) {
  const delta = change_points !== undefined ? change_points : change;
  const favorable = delta == null ? null : (inverse ? delta <= 0 : delta >= 0);
  return (
    <article className="metric-card">
      <div className="metric-top"><span className="metric-title">{title}<span className="tooltip-trigger" tabIndex={0} aria-label={help} title={help}>i</span></span><span className={`metric-icon ${tone}`}><Icon size={17} /></span></div>
      <div className="metric-value">{value}</div>
      <div className="metric-foot">
        <span className={`change-pill ${favorable === null ? "neutral" : favorable ? "positive" : "negative"}`}>
          {favorable === null ? <span>—</span> : favorable ? <ArrowUpRight size={13} /> : <ArrowDownRight size={13} />}
          {delta == null ? "No prior baseline" : `${Math.abs(delta).toFixed(1)}${suffix || "%"} ${delta >= 0 ? "up" : "down"}`}
        </span>
        <span className="metric-compare">{change_points !== undefined ? "vs prior margin" : "vs prior period"}</span>
      </div>
      <span className="sr-only">Currency shown in {currencyCode}</span>
    </article>
  );
}

function PanelHeading({ title, subtitle, action }: { title: string; subtitle: string; action?: ReactNode }) {
  return <div className="panel-heading"><div><h2>{title}</h2><p>{subtitle}</p></div>{action}</div>;
}

const lineOptions = (currencyCode: string) => ({
  responsive: true, maintainAspectRatio: false,
  interaction: { intersect: false, mode: "index" as const },
  plugins: {
    legend: { position: "bottom" as const, align: "start" as const, labels: { usePointStyle: true, boxWidth: 7, boxHeight: 7, padding: 18, color: "#77859a", font: { size: 11 } } },
    tooltip: { callbacks: { label: (ctx: { dataset: { label?: string }; parsed: { y: number } }) => ` ${ctx.dataset.label}: ${currency(ctx.parsed.y, currencyCode)}` } },
  },
  scales: {
    x: { grid: { display: false }, border: { display: false }, ticks: { color: "#8996a9", maxRotation: 0, autoSkip: true, maxTicksLimit: 8, font: { size: 10 } } },
    y: { border: { display: false }, grid: { color: "rgba(134,151,173,.14)" }, ticks: { color: "#8996a9", callback: (value: string | number) => currency(Number(value), currencyCode, true), maxTicksLimit: 5, font: { size: 10 } } },
  },
});

const barOptions = (currencyCode: string) => ({
  responsive: true, maintainAspectRatio: false,
  plugins: {
    legend: { display: false },
    tooltip: { callbacks: { label: (ctx: { parsed: { y: number } }) => ` ${currency(ctx.parsed.y, currencyCode)}` } },
  },
  scales: {
    x: { grid: { display: false }, border: { display: false }, ticks: { color: "#8996a9", font: { size: 11 } } },
    y: { border: { display: false }, grid: { color: "rgba(134,151,173,.14)" }, ticks: { color: "#8996a9", callback: (value: string | number) => currency(Number(value), currencyCode, true), maxTicksLimit: 5, font: { size: 10 } } },
  },
});

function FinancialPage({ start, end }: { start: string; end: string }) {
  const { session } = useAuth();
  const { data, isPending, error } = useQuery({ queryKey: ["financial", session?.active_organization_id, start, end], queryFn: () => request<{ currency: string; metrics: Overview["metrics"]; cost_by_category: Overview["cost_by_category"]; limitations: string[] }>(`/api/v1/financial?start_date=${start}&end_date=${end}`) });
  if (isPending) return <LoadingPanel />;
  if (error || !data) return <ErrorBanner message={error?.message || "Financial data unavailable"} />;
  return <div className="content-grid single-column">
    <div className="kpi-grid financial-kpis">
      <SimpleMetric title="Recognized revenue" value={currency(data.metrics.revenue.value, data.currency)} change={data.metrics.revenue.change_percent} />
      <SimpleMetric title="Operating costs" value={currency(data.metrics.operating_costs.value, data.currency)} change={data.metrics.operating_costs.change_percent} inverse />
      <SimpleMetric title="Operating profit" value={currency(data.metrics.operating_profit.value, data.currency)} change={data.metrics.operating_profit.change_percent} />
      <SimpleMetric title="Operating margin" value={percent(data.metrics.operating_margin.value)} change={data.metrics.operating_margin.change_points} suffix=" pp" />
    </div>
    <article className="panel"><PanelHeading title="Expense composition" subtitle="Recorded operating costs by category" /><div className="expense-table">
      {data.cost_by_category.map((item) => <div className="expense-row" key={item.name}><span>{item.name}</span><div className="expense-track"><i style={{ width: `${Math.min(100, item.value / Math.max(...data.cost_by_category.map((entry) => entry.value)) * 100)}%` }} /></div><strong>{currency(item.value, data.currency)}</strong></div>)}
    </div></article>
    <article className="panel limitation-panel"><div className="limitation-title"><CircleHelp size={17} /><strong>Calculation scope</strong></div>{data.limitations.map((item) => <p key={item}>{item}</p>)}</article>
  </div>;
}

function SimpleMetric({ title, value, change, suffix = "%", inverse = false }: { title: string; value: string; change?: number | null; suffix?: string; inverse?: boolean }) {
  const good = change == null ? null : inverse ? change <= 0 : change >= 0;
  return <article className="metric-card simple-metric"><span className="metric-title">{title}</span><strong className="metric-value">{value}</strong><span className={`change-pill ${good === null ? "neutral" : good ? "positive" : "negative"}`}>{change == null ? "No prior baseline" : `${change > 0 ? "+" : ""}${change.toFixed(1)}${suffix} vs prior period`}</span></article>;
}

function RevenuePage({ start, end }: { start: string; end: string }) {
  const { session } = useAuth();
  const { data, isPending, error } = useQuery({
    queryKey: ["revenue", session?.active_organization_id, start, end],
    queryFn: () => request<{ recognized_revenue_by_customer: { customer: string; segment: string; value: number }[]; pipeline: { stage: string; count: number; pipeline_value: number }[]; pipeline_note: string }>(`/api/v1/revenue/analytics?start_date=${start}&end_date=${end}`),
  });
  if (isPending) return <LoadingPanel />;
  if (error || !data) return <ErrorBanner message={error?.message || "Revenue data unavailable"} />;
  return <div className="content-grid single-column"><article className="panel"><PanelHeading title="Recognized revenue by customer" subtitle="Sorted by recognized revenue for the selected period" /><DataTable headers={["Customer", "Segment", "Recognized revenue"]} rows={data.recognized_revenue_by_customer.map((item) => [item.customer, item.segment, currency(item.value)])} /></article>
    <article className="panel"><PanelHeading title="Sales pipeline" subtitle="Open opportunity values are estimates and are not recognized revenue" /><div className="pipeline-grid">{data.pipeline.map((item) => <div className="pipeline-card" key={item.stage}><span>{item.stage}</span><strong>{currency(item.pipeline_value)}</strong><small>{item.count} synthetic opportunities</small></div>)}</div><div className="dashboard-note inline-note"><CircleHelp size={15} />{data.pipeline_note}</div></article></div>;
}

function ProjectsPage() {
  const { session } = useAuth();
  const { data, isPending, error } = useQuery({ queryKey: ["projects-health", session?.active_organization_id], queryFn: () => request<{ items: { id: number; name: string; customer: string; department: string; manager: string; status: string; planned_end_date: string; actual_end_date: string | null; budget: number; actual_cost: number; planned_progress: number; actual_progress: number; budget_variance: number }[]; on_time_definition: string }>("/api/v1/projects/health") });
  if (isPending) return <LoadingPanel />;
  if (error || !data) return <ErrorBanner message={error?.message || "Projects unavailable"} />;
  const overBudget = data.items.filter((item) => item.budget_variance > 0).length;
  const atRisk = data.items.filter((item) => item.status === "At risk").length;
  const completed = data.items.filter((item) => item.status === "Completed" && item.actual_end_date);
  const onTime = completed.length ? completed.filter((item) => item.actual_end_date! <= item.planned_end_date).length / completed.length * 100 : null;
  return <div className="content-grid single-column"><div className="kpi-grid compact-kpis"><SimpleMetric title="Active projects" value={String(data.items.filter((item) => item.status === "In progress" || item.status === "At risk").length)} /><SimpleMetric title="At risk" value={String(atRisk)} /><SimpleMetric title="Over budget" value={String(overBudget)} /><SimpleMetric title="Eligible on-time delivery" value={percent(onTime, 0)} /></div>
    <article className="panel"><PanelHeading title="Project health" subtitle="Status, delivery progress, and budget position" /><div className="table-scroll"><table><thead><tr>{["Project", "Customer", "Status", "Progress", "Planned end", "Budget variance"].map((head) => <th key={head}>{head}</th>)}</tr></thead><tbody>{data.items.map((item) => <tr key={item.id}><td><strong>{item.name}</strong><small className="table-subtext">{item.department} · {item.manager}</small></td><td>{item.customer}</td><td><StatusBadge value={item.status} /></td><td><Progress value={item.actual_progress} planned={item.planned_progress} /></td><td>{formatDate(item.planned_end_date)}</td><td className={item.budget_variance > 0 ? "negative-text" : "positive-text"}>{currency(item.budget_variance)}</td></tr>)}</tbody></table></div><div className="table-footnote">{data.on_time_definition} Incomplete projects are not counted as late.</div></article></div>;
}

function CustomersPage() {
  const { session } = useAuth();
  const [search, setSearch] = useState("");
  const { data, isPending, error } = useQuery({ queryKey: ["customers-analytics", session?.active_organization_id, search], queryFn: () => request<{ items: { id: number; name: string; segment: string; status: string; account_owner: string; recognized_revenue: number; last_revenue_date: string | null }[] }>(`/api/v1/customers/analytics?search=${encodeURIComponent(search)}`) });
  if (isPending) return <LoadingPanel />;
  if (error || !data) return <ErrorBanner message={error?.message || "Customers unavailable"} />;
  return <div className="content-grid single-column"><article className="panel"><PanelHeading title="Customer directory" subtitle={`${data.items.length} accounts`} action={<div className="table-search"><Search size={15} /><input placeholder="Filter customers" value={search} onChange={(event) => setSearch(event.target.value)} aria-label="Filter customers" /></div>} /><div className="table-scroll"><table><thead><tr>{["Customer", "Segment", "Account owner", "Status", "Recognized revenue", "Last activity"].map((head) => <th key={head}>{head}</th>)}</tr></thead><tbody>{data.items.length ? data.items.map((item) => <tr key={item.id}><td><strong>{item.name}</strong></td><td>{item.segment}</td><td>{item.account_owner}</td><td><StatusBadge value={item.status} /></td><td className="numeric">{currency(item.recognized_revenue)}</td><td>{item.last_revenue_date ? formatDate(item.last_revenue_date) : "—"}</td></tr>) : <tr><td colSpan={6} className="empty-table-cell">No customers match this filter.</td></tr>}</tbody></table></div><div className="table-footnote">Recognized revenue is historical. Customer lifetime value and cohort retention are not calculated.</div></article></div>;
}

type CrudField = { name: string; label: string; type: "text" | "number" | "date"; required?: boolean };
type CrudRecord = Record<string, string | number | boolean | null | undefined> & { id: number };
type CrudResponse = { items: CrudRecord[]; limit: number; offset: number };

function CrudPage({ resource, title, fields }: { resource: string; title: string; fields: CrudField[] }) {
  const { session } = useAuth();
  const queryClient = useQueryClient();
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<CrudRecord | null>(null);
  const [formValues, setFormValues] = useState<Record<string, string>>({});
  const [errorText, setErrorText] = useState("");
  const [offset, setOffset] = useState(0);
  const queryKey = [resource, session?.active_organization_id, offset];
  const query = useQuery({
    queryKey,
    queryFn: () => request<CrudResponse>(`/api/v1/${resource}?limit=100&offset=${offset}`),
  });
  const activeRole = session?.memberships.find((item) => item.organization_id === session.active_organization_id)?.role;
  const canWrite = activeRole === "owner" || activeRole === "admin" || activeRole === "analyst";
  const canDelete = activeRole === "owner" || activeRole === "admin";
  const save = useMutation({
    mutationFn: (payload: Record<string, string | number>) => request<CrudRecord>(
      editing ? `/api/v1/${resource}/${editing.id}` : `/api/v1/${resource}`,
      { method: editing ? "PATCH" : "POST", body: JSON.stringify(payload) },
    ),
    onSuccess: async () => {
      setFormOpen(false);
      setEditing(null);
      setFormValues({});
      setErrorText("");
      await queryClient.invalidateQueries({ queryKey });
    },
    onError: (error: Error) => setErrorText(error.message),
  });
  const remove = useMutation({
    mutationFn: (id: number) => request(`/api/v1/${resource}/${id}`, { method: "DELETE" }),
    onSuccess: async () => {
      if ((query.data?.items.length || 0) <= 1 && offset > 0) setOffset(Math.max(0, offset - 100));
      await queryClient.invalidateQueries({ queryKey });
    },
    onError: (error: Error) => setErrorText(error.message),
  });

  function beginEdit(record?: CrudRecord) {
    setEditing(record || null);
    setErrorText("");
    setFormValues(Object.fromEntries(fields.map((field) => [field.name, record?.[field.name] == null ? "" : String(record[field.name])])));
    setFormOpen(true);
  }
  function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const payload: Record<string, string | number> = {};
    for (const field of fields) {
      const value = formValues[field.name]?.trim();
      if (value) payload[field.name] = field.type === "number" ? Number(value) : value;
    }
    if (Object.values(payload).some((value) => typeof value === "number" && !Number.isFinite(value))) {
      setErrorText("Enter valid numeric values.");
      return;
    }
    setErrorText("");
    save.mutate(payload);
  }

  if (query.isPending) return <LoadingPanel />;
  if (query.error) return <ErrorBanner message={query.error.message} />;
  const records = query.data?.items || [];
  return <div className="content-grid single-column">
    <article className="panel">
      <PanelHeading title={title} subtitle="Organization-scoped records; the API enforces access permissions." action={canWrite ? <button className="button button-primary" onClick={() => beginEdit()}><span>+</span> Add {title.toLowerCase().replace(/&/g, "and").replace(/s$/, "")}</button> : undefined} />
      {errorText && <div className="inline-error" role="alert">{errorText}</div>}
      <div className="table-scroll"><table><thead><tr>{[...fields.map((field) => field.label), "Actions"].map((item) => <th key={item}>{item}</th>)}</tr></thead><tbody>
          {records.length ? records.map((record) => <tr key={record.id}>{fields.map((field) => <td key={field.name}>{field.type === "number" && !field.name.endsWith("_id") ? currency(Number(record[field.name] || 0)) : String(record[field.name] ?? "—")}</td>)}<td className="record-actions">{canWrite && <button className="text-button" onClick={() => beginEdit(record)}>Edit</button>}{canDelete && <button className="text-button danger-button" onClick={() => window.confirm(`Delete this ${title.toLowerCase()} record?`) && remove.mutate(record.id)}>Delete</button>}</td></tr>) : <tr><td className="empty-table-cell" colSpan={fields.length + 1}>No records found.</td></tr>}
      </tbody></table></div>
      <div className="table-pagination"><span>Showing {records.length ? offset + 1 : 0}–{offset + records.length}</span><div><button className="button button-secondary" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 100))}>Previous</button><button className="button button-secondary" disabled={records.length < 100} onClick={() => setOffset(offset + 100)}>Next</button></div></div>
      {formOpen && <form className="record-form" onSubmit={submit}><div className="record-form-heading"><strong>{editing ? "Update" : "Create"} {title.toLowerCase().replace(/&/g, "and").replace(/s$/, "")}</strong><button type="button" className="icon-button" aria-label="Close form" onClick={() => setFormOpen(false)}><X size={15} /></button></div><div className="record-form-grid">{fields.map((field) => <label className="auth-field" key={field.name}><span>{field.label}</span><input required={field.required !== false} type={field.type} step={field.type === "number" ? field.name.endsWith("_id") ? "1" : "0.01" : undefined} value={formValues[field.name] || ""} onChange={(event) => setFormValues({ ...formValues, [field.name]: event.target.value })} /></label>)}</div><button className="button button-primary" disabled={save.isPending}>{save.isPending ? "Saving…" : "Save changes"}</button></form>}
    </article>
  </div>;
}

function BusinessRecordsPage() {
  const [resource, setResource] = useState("customers");
  const configurations: Record<string, { title: string; fields: CrudField[] }> = {
    customers: { title: "Customers", fields: [
      { name: "name", label: "Customer name", type: "text" },
      { name: "segment", label: "Segment", type: "text" },
      { name: "status", label: "Status", type: "text" },
      { name: "account_owner", label: "Account owner", type: "text" },
    ] },
    projects: { title: "Projects", fields: [
      { name: "customer_id", label: "Customer ID", type: "number" },
      { name: "department_id", label: "Department ID", type: "number" },
      { name: "name", label: "Project name", type: "text" },
      { name: "manager", label: "Project manager", type: "text" },
      { name: "status", label: "Status", type: "text" },
      { name: "start_date", label: "Start date", type: "date" },
      { name: "planned_end_date", label: "Planned end date", type: "date" },
      { name: "actual_end_date", label: "Actual end date", type: "date", required: false },
      { name: "budget", label: "Budget", type: "number" },
      { name: "actual_cost", label: "Actual cost", type: "number" },
      { name: "planned_progress", label: "Planned progress (%)", type: "number" },
      { name: "actual_progress", label: "Actual progress (%)", type: "number" },
    ] },
    departments: { title: "Departments", fields: [{ name: "name", label: "Department name", type: "text" }] },
    budgets: { title: "Budgets", fields: [
      { name: "department_id", label: "Department ID", type: "number" },
      { name: "period_start", label: "Month", type: "date" },
      { name: "revenue_target", label: "Revenue target", type: "number" },
      { name: "expense_budget", label: "Expense budget", type: "number" },
    ] },
    revenue: { title: "Revenue transactions", fields: [
      { name: "customer_id", label: "Customer ID", type: "number" },
      { name: "department_id", label: "Department ID", type: "number" },
      { name: "external_id", label: "External ID", type: "text" },
      { name: "transaction_date", label: "Date", type: "date" },
      { name: "amount", label: "Amount", type: "number" },
      { name: "currency", label: "Currency", type: "text" },
      { name: "description", label: "Description", type: "text" },
      { name: "revenue_type", label: "Revenue type", type: "text" },
    ] },
    expenses: { title: "Expense transactions", fields: [
      { name: "department_id", label: "Department ID", type: "number" },
      { name: "transaction_date", label: "Date", type: "date" },
      { name: "amount", label: "Amount", type: "number" },
      { name: "category", label: "Category", type: "text" },
      { name: "description", label: "Description", type: "text" },
    ] },
  };
  const selected = configurations[resource];
  return <div className="content-grid single-column">
    <article className="panel"><div className="record-form-grid"><label className="auth-field"><span>Record type</span><select value={resource} onChange={(event) => setResource(event.target.value)}>{Object.entries(configurations).map(([key, config]) => <option key={key} value={key}>{config.title}</option>)}</select></label></div></article>
    <CrudPage key={resource} resource={resource} title={selected.title} fields={selected.fields} />
  </div>;
}

function TeamPage({ session }: { session: AuthSession }) {
  const queryClient = useQueryClient();
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("viewer");
  const [errorText, setErrorText] = useState("");
  const activeRole = session.memberships.find((item) => item.organization_id === session.active_organization_id)?.role;
  const canManage = activeRole === "owner" || activeRole === "admin";
  const membersKey = ["organization-members", session.active_organization_id];
  const { data, isPending, error } = useQuery({
    queryKey: membersKey,
    enabled: canManage && session.active_organization_id !== null,
    queryFn: () => request<{ items: { user_id: number; email: string; role: string }[] }>(`/api/v1/organizations/${session.active_organization_id}/members`),
  });
  const addMember = useMutation({
    mutationFn: () => request(`/api/v1/organizations/${session.active_organization_id}/members`, {
      method: "POST",
      body: JSON.stringify({ email, role }),
    }),
    onSuccess: async () => {
      setEmail("");
      setErrorText("");
      await queryClient.invalidateQueries({ queryKey: membersKey });
    },
    onError: (cause: Error) => setErrorText(cause.message),
  });
  const updateRole = useMutation({
    mutationFn: ({ userId, nextRole }: { userId: number; nextRole: string }) => request(
      `/api/v1/organizations/${session.active_organization_id}/members/${userId}`,
      { method: "PATCH", body: JSON.stringify({ role: nextRole }) },
    ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: membersKey }),
    onError: (cause: Error) => setErrorText(cause.message),
  });
  const removeMember = useMutation({
    mutationFn: (userId: number) => request(
      `/api/v1/organizations/${session.active_organization_id}/members/${userId}`,
      { method: "DELETE" },
    ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: membersKey }),
    onError: (cause: Error) => setErrorText(cause.message),
  });
  if (!canManage) return <div className="empty-panel">Team management is available to organization owners and administrators.</div>;
  if (isPending) return <LoadingPanel />;
  if (error || !data) return <ErrorBanner message={error?.message || "Could not load organization membership"} />;
  const roles = activeRole === "owner" ? ["owner", "admin", "analyst", "viewer"] : ["analyst", "viewer"];
  return <div className="content-grid single-column"><article className="panel">
    <PanelHeading title="Team & access" subtitle="Manage existing Vantage IQ accounts and their organization roles" />
    {errorText && <div className="inline-error" role="alert">{errorText}</div>}
    <form className="record-form" onSubmit={(event) => { event.preventDefault(); addMember.mutate(); }}>
      <div className="record-form-grid">
        <label className="auth-field"><span>Account email</span><input type="email" required value={email} onChange={(event) => setEmail(event.target.value)} placeholder="teammate@company.com" /></label>
        <label className="auth-field"><span>Organization role</span><select value={role} onChange={(event) => setRole(event.target.value)}>{roles.map((item) => <option key={item} value={item}>{item}</option>)}</select></label>
      </div>
      <button className="button button-primary" disabled={addMember.isPending}>{addMember.isPending ? "Adding…" : "Add existing account"}</button>
      <div className="table-footnote">The member must already have an account. Owners can grant any role; administrators can grant analyst or viewer access.</div>
    </form>
    <div className="table-scroll"><table><thead><tr>{["Member ID", "Email", "Role", "Actions"].map((item) => <th key={item}>{item}</th>)}</tr></thead><tbody>{data.items.map((member) => {
      const memberRoles = [...new Set([member.role, ...roles])];
      const restricted = activeRole !== "owner" && ["owner", "admin"].includes(member.role);
      return <tr key={member.user_id}><td>{member.user_id}</td><td><strong>{member.email}</strong></td><td><StatusBadge value={member.role} /></td><td className="record-actions"><select aria-label={`Role for ${member.email}`} value={member.role} disabled={restricted} onChange={(event) => updateRole.mutate({ userId: member.user_id, nextRole: event.target.value })}>{memberRoles.map((item) => <option key={item} value={item}>{item}</option>)}</select><button className="text-button danger-button" disabled={restricted} onClick={() => window.confirm(`Remove ${member.email} from this organization?`) && removeMember.mutate(member.user_id)}>Remove</button></td></tr>;
    })}</tbody></table></div>
    <div className="table-footnote">The API validates every operation against the selected organization’s membership and role.</div>
  </article></div>;
}

function ReportsPage({ start, end }: { start: string; end: string }) {
  return <div className="content-grid single-column"><article className="panel"><PanelHeading title="Executive report" subtitle={`Report period ${formatPeriod(start, end)}`} /><div className="report-actions"><div><FileBarChart2 size={20} /><div><strong>Executive performance report</strong><span>PDF overview with financial, delivery, customer, and data limitation sections.</span></div></div><div className="report-downloads"><a className="button button-secondary" href={`${API}/api/v1/reports/executive.csv?start_date=${start}&end_date=${end}`}><Download size={15} /> Download CSV</a><a className="button button-primary" href={`${API}/api/v1/reports/executive.pdf?start_date=${start}&end_date=${end}`} target="_blank" rel="noreferrer"><Download size={15} /> Generate PDF</a></div></div></article></div>;
}

type ImportPreview = {
  total_rows: number;
  valid_rows: number;
  invalid_rows: number;
  errors: { row: number; errors: string[] }[];
  preview: { external_id: string; date: string; customer: string; department: string; amount: string; currency: string; description: string }[];
  can_commit: boolean;
};

type ImportConfig = { upload_max_bytes: number; upload_max_rows: number };

function ImportsPage() {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [message, setMessage] = useState("");
  const [errorText, setErrorText] = useState("");
  const queryClient = useQueryClient();
  const { session } = useAuth();
  const activeRole = session?.memberships.find((item) => item.organization_id === session.active_organization_id)?.role;
  const canImport = Boolean(session?.user && ["owner", "admin", "analyst"].includes(activeRole || ""));
  const isDemo = session?.user === null;
  const { data: config } = useQuery({ queryKey: ["public-config"], queryFn: () => request<ImportConfig>("/api/v1/config") });
  const previewMutation = useMutation({
    mutationFn: (selected: File) => { const body = new FormData(); body.append("file", selected); return request<ImportPreview>("/api/v1/imports/revenue/preview", { method: "POST", body }); },
    onSuccess: (result) => { setPreview(result); setErrorText(""); setMessage(""); },
    onError: (error: Error) => setErrorText(error.message),
  });
  const commitMutation = useMutation({
    mutationFn: (selected: File) => { const body = new FormData(); body.append("file", selected); body.append("confirm", "true"); return request<{ status: string; imported_rows: number }>("/api/v1/imports/revenue/commit", { method: "POST", body }); },
    onSuccess: async (result) => { setMessage(`${result.imported_rows} revenue records imported successfully.`); setPreview(null); setFile(null); await queryClient.invalidateQueries(); },
    onError: (error: Error) => setErrorText(error.message),
  });
  return <div className="content-grid import-layout"><article className="panel import-panel"><PanelHeading title="Import recognized revenue" subtitle={canImport ? "Validate the entire file before writing any records" : "Imports require an analyst, admin, or owner account"} />
    {!canImport && <div className="dashboard-note inline-note"><ShieldAlert size={15} />{isDemo ? "The synthetic demo workspace is read-only." : "Your current role does not have permission to import records."}</div>}
    <div className="import-drop"><div className="upload-icon"><CloudUpload size={23} /></div><strong>{file ? file.name : "Choose a CSV or Excel file"}</strong><p>UTF-8 CSV or XLSX · up to {config ? `${(config.upload_max_bytes / (1024 * 1024)).toFixed(1)} MB` : "configured limit"} · {config?.upload_max_rows.toLocaleString() || "10,000"} rows</p><div className="import-file-actions"><label className="button button-secondary file-picker">Browse files<input type="file" accept=".csv,.xlsx" disabled={!canImport} onChange={(event) => { setFile(event.target.files?.[0] || null); setPreview(null); setMessage(""); setErrorText(""); }} /></label><a className="template-link" href={`${API}/api/v1/imports/revenue/template.csv`}><Download size={13} /> CSV template</a><a className="template-link" href={`${API}/api/v1/imports/revenue/template.xlsx`}><Download size={13} /> XLSX template</a></div></div>
    <div className="import-actions"><button className="button button-primary" disabled={!file || previewMutation.isPending} onClick={() => file && previewMutation.mutate(file)}>{previewMutation.isPending ? "Validating…" : "Preview & validate"}</button></div>
    {errorText && <div className="inline-error" role="alert">{errorText}</div>}
    {message && <div className="inline-success" role="status"><Check size={16} />{message}</div>}
    {preview && <div className="validation-result"><div className="validation-summary"><span><strong>{preview.total_rows}</strong> rows</span><span className="positive-text"><strong>{preview.valid_rows}</strong> valid</span><span className={preview.invalid_rows ? "negative-text" : "positive-text"}><strong>{preview.invalid_rows}</strong> invalid</span></div>
      {preview.preview.length > 0 && <div className="table-scroll preview-table"><table><thead><tr>{["ID", "Date", "Customer", "Department", "Amount"].map((head) => <th key={head}>{head}</th>)}</tr></thead><tbody>{preview.preview.map((row) => <tr key={row.external_id}><td>{row.external_id}</td><td>{row.date}</td><td>{row.customer}</td><td>{row.department}</td><td>{row.currency} {row.amount}</td></tr>)}</tbody></table></div>}
      {preview.errors.length > 0 && <div className="validation-errors"><strong>Fix these row errors before importing</strong>{preview.errors.slice(0, 8).map((item) => <p key={item.row}>Row {item.row}: {item.errors.join("; ")}</p>)}</div>}
      <button className="button button-primary commit-button" disabled={!canImport || !preview.can_commit || commitMutation.isPending} onClick={() => file && commitMutation.mutate(file)}>{commitMutation.isPending ? "Importing…" : "Confirm and import records"}</button>
    </div>}
  </article>
    <article className="panel import-guide"><PanelHeading title="Required columns" subtitle="Column names are case-insensitive" /><div className="field-list">{[["external_id", "Stable unique ID per transaction"], ["date", "Transaction date (YYYY-MM-DD)"], ["customer", "Exact existing customer name"], ["department", "Exact existing department name"], ["amount", "Decimal amount; negative values represent refunds"], ["currency", "Three-letter ISO currency"], ["description", "Short transaction description"]].map(([key, description]) => <div key={key}><code>{key}</code><span>{description}</span></div>)}</div><div className="import-safety"><ShieldAlert size={16} /><p>Imports are all-or-nothing. Duplicate IDs and invalid rows block the full commit. Spreadsheets are read as values only; macros are not executed.</p></div></article>
  </div>;
}

const kpis = [
  ["Recognized revenue", "Financial", "Sum of recognized revenue transaction amounts in the selected accounting period.", "USD", "Monthly", "Revenue transactions", "No target configured", "Higher", "Refunds are represented by negative transactions."],
  ["Operating costs", "Financial", "Sum of recorded operating expense transaction amounts in the selected period.", "USD", "Monthly", "Expense transactions", "Budget records", "Lower", "Company-wide expenses are not allocated to departments."],
  ["Operating profit", "Financial", "Recognized revenue less recorded operating costs; excludes non-operating items and taxes.", "USD", "Monthly", "Revenue and expense transactions", "Revenue less operating costs", "Higher", "Not net profit or EBITDA."],
  ["Operating margin", "Financial", "Operating profit divided by recognized revenue, multiplied by 100.", "%", "Monthly", "Revenue and expense transactions", "No target configured", "Higher", "Not available when recognized revenue is zero or negative."],
  ["Budget achievement", "Financial", "Recognized revenue divided by the sum of configured revenue targets, multiplied by 100.", "%", "Monthly", "Revenue transactions and budgets", "Department revenue targets", "Higher", "Not available if the target denominator is zero."],
  ["On-time delivery", "Projects", "Completed projects delivered on or before planned end date divided by eligible completed projects.", "%", "Monthly", "Projects", "No target configured", "Higher", "Incomplete projects are excluded; not available with no eligible projects."],
  ["Customer activity", "Customers", "Distinct customers with recognized revenue in period divided by organization customer count.", "%", "Monthly", "Revenue transactions and customers", "No target configured", "Higher", "Activity proxy only; not a cohort retention or churn measure."],
];

function KpiPage() {
  return <div className="content-grid single-column"><article className="panel"><PanelHeading title="KPI dictionary" subtitle="Definitions, formulas, data sources, and limitations" /><div className="table-scroll"><table className="kpi-table"><thead><tr>{["KPI", "Area", "Definition & formula", "Unit", "Frequency", "Source", "Target", "Direction", "Data note"].map((head) => <th key={head}>{head}</th>)}</tr></thead><tbody>{kpis.map((item) => <tr key={item[0]}><td><strong>{item[0]}</strong></td><td>{item[1]}</td><td className="definition-cell">{item[2]}</td><td>{item[3]}</td><td>{item[4]}</td><td>{item[5]}</td><td>{item[6]}</td><td>{item[7]}</td><td className="definition-cell">{item[8]}</td></tr>)}</tbody></table></div></article></div>;
}

function AlertsPage() {
  const { session } = useAuth();
  const { data, isPending, error } = useQuery({ queryKey: ["alerts", session?.active_organization_id], queryFn: () => request<{ items: { id: number; title: string; severity: string; explanation: string; suggested_action: string; detected_at: string; acknowledged: boolean }[] }>("/api/v1/alerts") });
  if (isPending) return <LoadingPanel />;
  if (error || !data) return <ErrorBanner message={error?.message || "Alerts unavailable"} />;
  return <div className="alerts-list">{data.items.map((alert) => <article className="panel alert-card" key={alert.id}><div className={`alert-severity ${alert.severity.toLowerCase()}`}><ShieldAlert size={17} />{alert.severity}</div><div className="alert-content"><div className="alert-title-row"><h2>{alert.title}</h2><span>{new Date(alert.detected_at).toLocaleDateString()}</span></div><p>{alert.explanation}</p><div className="suggested-action"><strong>Suggested next action</strong><span>{alert.suggested_action}</span></div></div></article>)}</div>;
}

function SettingsPage({ session }: { session: AuthSession }) {
  const membership = session.memberships.find((item) => item.organization_id === session.active_organization_id);
  const demo = membership?.is_demo === true;
  return <div className="content-grid settings-grid">
    <article className="panel"><PanelHeading title="Workspace profile" subtitle="Current organization and access level" /><div className="settings-detail">
      <div><span>Organization</span><strong>{membership?.organization_name || "Organization"}</strong></div>
      <div><span>Workspace mode</span><strong><span className="status-dot" /> {demo ? "Synthetic demo" : "Organization data"}</strong></div>
      <div><span>Your role</span><strong>{membership?.role || "Member"}</strong></div>
      <div><span>Account</span><strong>{session.user?.email || "Read-only demo"}</strong></div>
    </div></article>
    <article className="panel"><PanelHeading title="Workspace capabilities" subtitle="Available in this application" /><ul className="feature-list">
      <li><Check size={15} /> Server-backed analytics, tenant authorization, and role checks</li>
      <li><Check size={15} /> Organization-scoped business-record CRUD</li>
      <li><Check size={15} /> Alembic migrations and executive CSV/PDF reports</li>
      <li><Check size={15} /> Cookie sessions and CSRF-protected mutations</li>
      <li><X size={15} /> Email verification, password recovery, and login rate limits</li>
      <li><X size={15} /> Invitations and persistent audit-event history</li>
    </ul></article>
  </div>;
}

function DataTable({ headers, rows }: { headers: string[]; rows: string[][] }) {
  return <div className="table-scroll"><table><thead><tr>{headers.map((header) => <th key={header}>{header}</th>)}</tr></thead><tbody>{rows.length ? rows.map((row) => <tr key={row[0]}>{row.map((cell, index) => <td className={index === row.length - 1 ? "numeric" : ""} key={`${row[0]}-${index}`}>{index === 0 ? <strong>{cell}</strong> : cell}</td>)}</tr>) : <tr><td colSpan={headers.length} className="empty-table-cell">No records found for this period.</td></tr>}</tbody></table></div>;
}

function StatusBadge({ value }: { value: string }) {
  const status = value.toLowerCase().replace(" ", "-");
  return <span className={`status-badge status-${status}`}><i />{value}</span>;
}

function Progress({ value, planned }: { value: number; planned: number }) {
  const behind = value < planned - 10;
  return <div className="progress-cell"><div className="progress-track"><span className={behind ? "behind" : ""} style={{ width: `${Math.min(value, 100)}%` }} /></div><span>{value}%</span></div>;
}

function formatPeriod(start: string, end: string) {
  const a = new Date(`${start}T00:00:00`);
  const b = new Date(`${end}T00:00:00`);
  return `${a.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })} – ${b.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}`;
}

function formatDate(value: string) {
  return new Date(`${value}T00:00:00`).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

function initials(name: string) {
  return name.trim().split(/\s+/).slice(0, 2).map((part) => part.charAt(0).toUpperCase()).join("") || "U";
}
