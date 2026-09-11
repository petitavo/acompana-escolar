import React, { useState, useEffect, useCallback } from "react";
import { createRoot } from "react-dom/client";
import {
  BrowserRouter,
  Link,
  NavLink,
  useLocation,
  useNavigate,
  useParams,
} from "react-router-dom";
import {
  HeartHandshake,
  LayoutList,
  History,
  MonitorSmartphone,
  FlaskConical,
  Activity,
  Download,
  LogOut,
  ChevronRight,
  ArrowUpRight,
  RefreshCw,
  Check,
  MessageCircle,
  ShieldCheck,
  Search,
  Clock,
  Database,
  FileText,
  Users,
  Menu,
  X,
} from "lucide-react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceArea,
  Legend,
} from "recharts";
import {
  api,
  setCsrf,
  stamp,
  stateLabel,
  reasonLabel,
  featureLabel,
} from "./api";
import "./style.css";
import ProductApp from "./Product";
type Row = Record<string, any>;
function useData(path: string | null) {
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const reload = useCallback(() => {
    if (!path) return;
    setLoading(true);
    api(path)
      .then((d) => {
        setData(d);
        setError("");
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [path]);
  useEffect(() => {
    setData(null);
    reload();
    const t = setInterval(reload, 15000);
    return () => clearInterval(t);
  }, [reload]);
  return { data, error, loading, reload };
}
function Badge({
  children,
  tone = "neutral",
}: {
  children: React.ReactNode;
  tone?: string;
}) {
  return <span className={"badge " + tone}>{children}</span>;
}
function Empty({ children }: { children: React.ReactNode }) {
  return (
    <div className="empty">
      <Database size={30} />
      <p>{children}</p>
    </div>
  );
}
function ErrorBox({ text }: { text: string }) {
  return text ? (
    <div role="alert" className="error">
      {text}
    </div>
  ) : null;
}
function Title({
  eyebrow,
  title,
  children,
}: {
  eyebrow: string;
  title: string;
  children?: React.ReactNode;
}) {
  return (
    <header className="page-title">
      <div>
        <div className="eyebrow">{eyebrow}</div>
        <h1>{title}</h1>
      </div>
      {children}
    </header>
  );
}
function App() {
  const [me, setMe] = useState<Row | null>(null);
  const [ready, setReady] = useState(false);
  const [mobile, setMobile] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();
  useEffect(() => {
    const expire = () => {
      setMe(null);
      setCsrf("");
    };
    window.addEventListener("session-expired", expire);
    return () => window.removeEventListener("session-expired", expire);
  }, []);
  useEffect(() => {
    api("/me")
      .then((d) => {
        setMe(d);
        setCsrf(d.csrf_token);
      })
      .catch(() => {})
      .finally(() => setReady(true));
  }, []);
  if (!ready) return <Empty>Comprobando sesión…</Empty>;
  if (location.pathname === "/participant") return <Participant />;
  if (!me)
    return (
      <Login
        onLogin={(d) => {
          setMe(d);
          setCsrf(d.csrf_token);
          navigate(
            d.role === "psychologist" ? "/psych/queue" : "/lab/overview",
          );
        }}
      />
    );
  const psych = me.role === "psychologist";
  const admin = me.role === "admin";
  const links = psych
    ? [
        [LayoutList, "Cola de revisión", "/psych/queue"],
        [History, "Historial de casos", "/psych/history"],
      ]
    : [
        [Activity, "Vista general", "/lab/overview"],
        [MonitorSmartphone, "Dispositivos", "/lab/devices"],
        [Database, "Eventos captados", "/lab/events"],
        [Activity, "Variables y trazabilidad", "/lab/features"],
        [FlaskConical, "Experimentos", "/lab/experiments"],
        [Download, "Exportaciones", "/lab/exports"],
      ];
  let content: React.ReactNode;
  if (admin)
    content = (
      <>
        <Title eyebrow="ADMINISTRACIÓN" title="Cuentas y asignaciones" />
        <section className="card">
          <ShieldCheck />
          <h2>Administración por CLI</h2>
          <p>
            Este rol no tiene acceso implícito a cuestionarios o casos. Cree
            cuentas, invitaciones y asignaciones con los comandos documentados
            en el README.
          </p>
        </section>
      </>
    );
  else if (
    location.pathname.startsWith("/psych/cases/") ||
    location.pathname.startsWith("/psych/participants/")
  )
    content = <CaseDetail />;
  else if (location.pathname.startsWith("/psych"))
    content = <Queue history={location.pathname.includes("history")} />;
  else if (location.pathname.startsWith("/lab/devices/"))
    content = <DeviceDetail />;
  else if (location.pathname === "/lab/devices") content = <Devices />;
  else if (location.pathname === "/lab/events") content = <Events />;
  else if (location.pathname === "/lab/features") content = <Features />;
  else if (location.pathname === "/lab/experiments") content = <Experiments />;
  else if (location.pathname === "/lab/exports") content = <Exports />;
  else content = <Overview />;
  return (
    <div className="shell">
      <div className={"mode-banner " + (me.mode === "LAB" ? "lab" : "")}>
        <FlaskConical size={15} />
        {me.mode === "DEMO"
          ? "Demostración · datos ficticios"
          : "LAB · pruebas autorizadas con adultos"}
        <span>Uso interno · sin interpretación clínica</span>
      </div>
      <aside className={mobile ? "sidebar open" : "sidebar"}>
        <Link className="brand" to={psych ? "/psych/queue" : "/lab/overview"}>
          <span className="brand-icon">
            <HeartHandshake size={27} />
          </span>
          <span>
            Acompaña<span className="brand-small">ESCOLAR · LABORATORIO</span>
          </span>
        </Link>
        <div className="workspace-label">
          {psych
            ? "ESPACIO DEL PSICÓLOGO"
            : admin
              ? "ADMINISTRACIÓN"
              : "ESPACIO DE INVESTIGACIÓN"}
        </div>
        <nav>
          {!admin &&
            links.map(([Icon, label, path]) => {
              const I = Icon as typeof Activity;
              return (
                <NavLink
                  key={String(path)}
                  to={String(path)}
                  onClick={() => setMobile(false)}
                >
                  <I size={20} />
                  {String(label)}
                </NavLink>
              );
            })}
        </nav>
        <div className="sidebar-note">
          <ShieldCheck size={22} />
          <p>Personas primero</p>
          <small>
            Los cambios observados orientan la revisión. No son un diagnóstico.
          </small>
        </div>
        <div className="account">
          <span className="avatar">{psych ? "PS" : "IN"}</span>
          <div>
            <strong>{me.username}</strong>
            <small>
              {psych ? "Psicólogo" : admin ? "Administrador" : "Investigador"}
            </small>
          </div>
          <button
            className="icon-button"
            aria-label="Cerrar sesión"
            onClick={async () => {
              await api("/auth/logout", "POST", {});
              setMe(null);
            }}
          >
            <LogOut size={19} />
          </button>
        </div>
      </aside>
      <main>
        <div className="topbar">
          <button
            className="icon-button menu"
            aria-label="Abrir navegación"
            onClick={() => setMobile(!mobile)}
          >
            {mobile ? <X /> : <Menu />}
          </button>
          <span>
            Santa María del Camino <ChevronRight size={14} /> Laboratorio
          </span>
          <Badge tone="teal">{me.mode}</Badge>
        </div>
        <div className="page" key={location.pathname}>
          {content}
        </div>
        <footer>
          Laboratorio de ingeniería de software · UPC{" "}
          <span>Entorno de prueba, sin atención de emergencia garantizada</span>
        </footer>
      </main>
    </div>
  );
}
function Login({ onLogin }: { onLogin: (v: Row) => void }) {
  const [user, setUser] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  return (
    <div className="login-page">
      <div className="login-story">
        <div className="brand light">
          <HeartHandshake size={34} /> Acompaña Escolar
        </div>
        <div>
          <span className="eyebrow">LABORATORIO DE SEGUIMIENTO</span>
          <h1>
            Un espacio para
            <br />
            observar y acompañar.
          </h1>
          <p>
            Cuestionarios, cambios personales y seguimiento humano, en un mismo
            lugar.
          </p>
          <div className="login-principles">
            <span>
              <ShieldCheck /> Datos de prueba
            </span>
            <span>
              <Users /> Revisión humana
            </span>
          </div>
        </div>
        <small>Ingeniería de Software · UPC</small>
      </div>
      <section className="login-form">
        <FlaskConical className="login-mark" size={36} />
        <h2>Ingresa al laboratorio</h2>
        <p>Usa la cuenta de prueba que generó el administrador.</p>
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            try {
              onLogin(
                await api("/auth/login", "POST", { username: user, password }),
              );
            } catch (e) {
              setError((e as Error).message);
            } finally {
              setBusy(false);
            }
          }}
        >
          <label>
            Usuario
            <input
              autoComplete="username"
              value={user}
              onChange={(e) => setUser(e.target.value)}
              required
            />
          </label>
          <label>
            Contraseña
            <input
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </label>
          <ErrorBox text={error} />
          <button className="primary wide" disabled={busy}>
            {busy ? "Ingresando…" : "Entrar al laboratorio"}
            <ArrowUpRight size={18} />
          </button>
        </form>
        <Link to="/participant">
          Probar el formulario como participante <ChevronRight size={15} />
        </Link>
        <p className="fine">
          Las cuentas DEMO se generan localmente. No hay registro público ni
          credenciales permanentes.
        </p>
      </section>
    </div>
  );
}
function Queue({ history }: { history: boolean }) {
  const { data, error, reload } = useData("/psych/cases");
  const [filter, setFilter] = useState("");
  const [kind, setKind] = useState("");
  const [state, setState] = useState("");
  const rows = (data || []).filter(
    (r: Row) =>
      (history || r.state !== "closed") &&
      r.pseudonym.toLowerCase().includes(filter.toLowerCase()) &&
      (!kind || r.reasons.some((x: Row) => x.kind === kind)) &&
      (!state || r.state === state),
  );
  const active = (data || []).filter((r: Row) => r.state !== "closed");
  return (
    <>
      <Title
        eyebrow="SEGUIMIENTO HUMANO"
        title={history ? "Historial de casos" : "Cola de revisión"}
      >
        <button onClick={reload} className="secondary">
          <RefreshCw size={17} />
          Actualizar
        </button>
      </Title>
      <p className="lead">
        Cada señal abre una conversación. Revisa el contexto y registra el
        siguiente paso.
      </p>
      <div className="stats">
        <Stat
          label="Por revisar"
          value={active.filter((r: Row) => r.state === "new").length}
          icon={<LayoutList />}
          tone="blue"
        />
        <Stat
          label="Solicitan contacto"
          value={
            active.filter((r: Row) =>
              r.reasons.some((x: Row) => x.kind === "contact_request"),
            ).length
          }
          icon={<MessageCircle />}
          tone="amber"
        />
        <Stat
          label="En seguimiento"
          value={active.filter((r: Row) => r.state === "in_followup").length}
          icon={<HeartHandshake />}
          tone="teal"
        />
        <Stat
          label="Casos registrados"
          value={(data || []).length}
          icon={<Users />}
        />
      </div>
      <section className="card no-pad">
        <div className="section-heading">
          <h2>
            {history
              ? "Registro de revisiones"
              : "Casos que necesitan una revisión"}{" "}
            <span className="count">{rows.length}</span>
          </h2>
          <Badge>Prioridad de trabajo</Badge>
        </div>
        <div className="filters">
          <div className="search">
            <Search size={18} />
            <input
              aria-label="Buscar participante"
              placeholder="Buscar seudónimo…"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
            />
          </div>
          <select
            aria-label="Filtrar motivo"
            value={kind}
            onChange={(e) => setKind(e.target.value)}
          >
            <option value="">Todos los motivos</option>
            {Object.entries(reasonLabel).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
          <select
            aria-label="Filtrar estado"
            value={state}
            onChange={(e) => setState(e.target.value)}
          >
            <option value="">Todos los estados</option>
            {[
              "new",
              "acknowledged",
              "contact_planned",
              "in_followup",
              "closed",
            ].map((s) => (
              <option key={s} value={s}>
                {stateLabel[s]}
              </option>
            ))}
          </select>
        </div>
        <ErrorBox text={error} />
        {data === null && !error ? (
          <Empty>Cargando casos…</Empty>
        ) : rows.length ? (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Participante</th>
                  <th>Motivo de revisión</th>
                  <th>Estado</th>
                  <th>Último cuestionario</th>
                  <th>Datos</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {rows.map((c: Row) => (
                  <tr key={c.id}>
                    <td>
                      <Link
                        className="participant-link"
                        to={"/psych/cases/" + c.id}
                      >
                        <span className="avatar">{c.pseudonym.slice(-2)}</span>
                        <span>
                          <strong>{c.pseudonym}</strong>
                          <small>{c.group}</small>
                        </span>
                      </Link>
                    </td>
                    <td>
                      <div className="reason-stack">
                        {c.reasons.map((r: Row) => (
                          <span key={r.id}>
                            <span
                              className={
                                "dot " +
                                (r.kind === "contact_request"
                                  ? "amber"
                                  : "blue")
                              }
                            />
                            {reasonLabel[r.kind] || r.kind}
                            {!r.active ? " · resuelto" : ""}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td>
                      <Badge tone={c.state === "new" ? "amber" : "teal"}>
                        {stateLabel[c.state]}
                      </Badge>
                      <small className="cell-sub">{stamp(c.created_at)}</small>
                    </td>
                    <td>{stamp(c.last_questionnaire)}</td>
                    <td>
                      <Badge
                        tone={c.quality === "sufficient" ? "teal" : "neutral"}
                      >
                        {stateLabel[c.quality]}
                      </Badge>
                    </td>
                    <td>
                      <Link
                        className="row-action"
                        aria-label={"Revisar " + c.pseudonym}
                        to={"/psych/cases/" + c.id}
                      >
                        <ChevronRight size={20} />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Empty>No hay casos que coincidan con estos filtros.</Empty>
        )}
        <div className="table-footer">
          <Clock size={16} />
          <span>
            Primero solicitudes de contacto, luego cuestionarios y cambios
            persistentes. Dentro de cada categoría, el caso más antiguo.
          </span>
        </div>
      </section>
      <div className="info-strip">
        <ShieldCheck size={23} />
        <div>
          <strong>Una prioridad de trabajo, sin etiquetas clínicas</strong>
          <p>
            La cola ayuda a organizar revisiones. No mide gravedad diagnóstica
            ni reemplaza el criterio profesional.
          </p>
        </div>
      </div>
      {history && <Usability />}
    </>
  );
}
function Usability() {
  const [start, setStart] = useState<number | null>(null);
  const [clarity, setClarity] = useState("4");
  const [usefulness, setUsefulness] = useState("4");
  const [comment, setComment] = useState("");
  const [message, setMessage] = useState("");
  return (
    <section className="card">
      <h2>Prueba de claridad y utilidad</h2>
      <p>
        Revisa tres casos ficticios. Registra el tiempo de la tarea y tus
        comentarios; esto no evalúa exactitud clínica.
      </p>
      <button className="secondary" onClick={() => setStart(Date.now())}>
        Iniciar medición de la tarea
      </button>
      <form
        className="export-form"
        onSubmit={async (e) => {
          e.preventDefault();
          try {
            await api("/psych/usability-feedback", "POST", {
              duration_seconds: Math.round(
                (Date.now() - (start || Date.now())) / 1000,
              ),
              clarity: Number(clarity),
              usefulness: Number(usefulness),
              comment,
            });
            setMessage("Comentario de usabilidad guardado");
            setStart(null);
          } catch (e) {
            setMessage((e as Error).message);
          }
        }}
      >
        <label>
          Claridad (1–5)
          <select value={clarity} onChange={(e) => setClarity(e.target.value)}>
            {[1, 2, 3, 4, 5].map((v) => (
              <option key={v}>{v}</option>
            ))}
          </select>
        </label>
        <label>
          Utilidad (1–5)
          <select
            value={usefulness}
            onChange={(e) => setUsefulness(e.target.value)}
          >
            {[1, 2, 3, 4, 5].map((v) => (
              <option key={v}>{v}</option>
            ))}
          </select>
        </label>
        <label>
          Comentario de la prueba
          <input
            value={comment}
            maxLength={2000}
            onChange={(e) => setComment(e.target.value)}
          />
        </label>
        <button className="primary" disabled={start === null}>
          Guardar evaluación
        </button>
      </form>
      <p role="status">{message}</p>
    </section>
  );
}
function Stat({
  label,
  value,
  icon,
  tone = "neutral",
}: {
  label: string;
  value: any;
  icon: React.ReactNode;
  tone?: string;
}) {
  return (
    <div className="stat">
      <div>
        <span>{label}</span>
        <strong>{value ?? "—"}</strong>
      </div>
      <span className={"stat-icon " + tone}>{icon}</span>
    </div>
  );
}
function CaseDetail() {
  const path = useLocation().pathname;
  const caseId = path.includes("/cases/") ? path.split("/").pop() : null;
  const c = useData(caseId ? "/psych/cases/" + caseId : null);
  const pid = caseId ? c.data?.participant_id : path.split("/").pop();
  const summary = useData(
    pid ? "/psych/participants/" + pid + "/summary" : null,
  );
  const [note, setNote] = useState("");
  const [reason, setReason] = useState("");
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  if (!summary.data)
    return (
      <>
        <ErrorBox text={summary.error || c.error} />
        <Empty>Cargando detalle autorizado…</Empty>
      </>
    );
  const s = summary.data;
  const current = s.evaluations[0]?.detail;
  const chart = s.features.map((f: Row) => ({
    day: f.day.slice(5),
    min: f.features.night_interactive_minutes.value,
    reference: current?.features.night_interactive_minutes.baseline,
  }));
  const transitions: Record<string, string[]> = {
    new: ["acknowledged", "closed"],
    acknowledged: ["contact_planned", "in_followup", "closed"],
    contact_planned: ["in_followup", "closed"],
    in_followup: ["closed"],
    closed: ["new"],
  };
  return (
    <>
      <Link className="back" to="/psych/queue">
        ← Volver a la cola
      </Link>
      <Title eyebrow={s.participant.group} title={s.participant.pseudonym}>
        {c.data && <Badge tone="amber">{stateLabel[c.data.state]}</Badge>}
      </Title>
      <div className="detail-grid">
        <div>
          <section className="card">
            <div className="section-heading plain">
              <h2>Uso nocturno del teléfono</h2>
              <Badge>Minutos · 22:00–06:00</Badge>
            </div>
            <p>
              Observación frente a su referencia personal. Un día sin captura
              permanece sin valor.
            </p>
            {current?.features.night_interactive_minutes.state ===
            "available" ? (
              <div className="comparison">
                {[
                  [
                    "Observado",
                    current.features.night_interactive_minutes.current,
                  ],
                  [
                    "Referencia",
                    current.features.night_interactive_minutes.baseline,
                  ],
                  ["Cambio", current.features.night_interactive_minutes.delta],
                ].map(([k, v]) => (
                  <div key={k}>
                    <span>{k}</span>
                    <strong>
                      {Number(v).toFixed(0)} <small>min</small>
                    </strong>
                  </div>
                ))}
              </div>
            ) : (
              <p>
                Referencia personal todavía no disponible: faltan días
                elegibles.
              </p>
            )}
            <div className="chart">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chart}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  {chart.length >= 35 && (
                    <ReferenceArea
                      x1={chart[chart.length - 35].day}
                      x2={chart[chart.length - 8].day}
                      fill="#d1fae5"
                      fillOpacity={0.3}
                    />
                  )}
                  <XAxis dataKey="day" minTickGap={25} />
                  <YAxis unit=" m" width={50} />
                  <Tooltip />
                  <Legend />
                  {chart.length > 7 && (
                    <ReferenceArea
                      x1={chart[chart.length - 7].day}
                      x2={chart[chart.length - 1].day}
                      fill="#dbeafe"
                      fillOpacity={0.5}
                    />
                  )}
                  <Line
                    isAnimationActive={false}
                    type="monotone"
                    dataKey="min"
                    name="Observado"
                    stroke="#1D4ED8"
                    strokeWidth={2.5}
                    dot={false}
                    connectNulls={false}
                  />
                  <Line
                    isAnimationActive={false}
                    dataKey="reference"
                    name="Referencia"
                    stroke="#0F766E"
                    strokeDasharray="5 5"
                    dot={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
            {s.academic_events.map((e: Row) => (
              <p className="annotation" key={e.id}>
                {e.detail.description} · {e.detail.start} a {e.detail.end}
              </p>
            ))}
          </section>
          <section className="card">
            <h2>Cuestionarios de prueba</h2>
            <p>
              CHECKIN_DEMO_V1 · formulario inventado; suma y umbral sin
              significado clínico.
            </p>
            <div className="response-list">
              {s.questionnaires.slice(0, 5).map((r: Row) => (
                <div key={r.id}>
                  <FileText size={20} />
                  <span>
                    {stamp(r.detail.applied_at)}
                    <small>
                      Completo · versión {r.detail.instrument_version}
                    </small>
                  </span>
                  <strong>{r.detail.total} / 9</strong>
                  <details>
                    <summary>Respuestas</summary>
                    {Object.entries(r.detail.answers || {}).map(([k, v]) => (
                      <p key={k}>
                        {(
                          {
                            energy: "Energía",
                            focus: "Concentración",
                            rest: "Descanso",
                          } as Record<string, string>
                        )[k] || k}
                        : {["Muy bien", "Bien", "Regular", "Mal"][Number(v)]}
                      </p>
                    ))}
                  </details>
                </div>
              ))}
            </div>
          </section>
          <section className="card">
            <h2>Calidad y cambios observados</h2>
            {Object.entries(current?.features || {}).map(([key, v]) => {
              const x = v as Row;
              return (
                <div className="quality-row" key={key}>
                  <span>{featureLabel[key]}</span>
                  <span>
                    {x.reference_days} días de referencia · {x.current_days}{" "}
                    actuales
                  </span>
                  <Badge tone={x.state === "available" ? "teal" : "neutral"}>
                    {x.state === "available"
                      ? "Disponible"
                      : "Datos insuficientes"}
                  </Badge>
                </div>
              );
            })}
          </section>
        </div>
        <div>
          {c.data && (
            <>
              <section className="card action-card">
                <h2>Registrar siguiente paso</h2>
                <form
                  onSubmit={async (e) => {
                    e.preventDefault();
                    try {
                      await api(
                        "/psych/cases/" + caseId + "/transitions",
                        "POST",
                        { state: status, version: c.data.version, reason },
                      );
                      setNotice("Cambio registrado");
                      setError("");
                      setReason("");
                      setStatus("");
                      c.reload();
                    } catch (e) {
                      setError((e as Error).message);
                    }
                  }}
                >
                  <label>
                    Acción
                    <select
                      value={status}
                      onChange={(e) => setStatus(e.target.value)}
                      required
                    >
                      <option value="">Selecciona una acción</option>
                      {transitions[c.data.state].map((x) => (
                        <option key={x} value={x}>
                          {stateLabel[x]}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Motivo o plan
                    <textarea
                      required
                      minLength={3}
                      value={reason}
                      onChange={(e) => setReason(e.target.value)}
                      placeholder="Registra el motivo de esta decisión…"
                    />
                  </label>
                  <button className="primary wide">
                    Guardar revisión <Check size={17} />
                  </button>
                </form>
                <hr />
                <form
                  onSubmit={async (e) => {
                    e.preventDefault();
                    try {
                      await api("/psych/cases/" + caseId + "/notes", "POST", {
                        text: note,
                      });
                      setNote("");
                      setNotice("Nota guardada");
                      c.reload();
                    } catch (e) {
                      setError((e as Error).message);
                    }
                  }}
                >
                  <label>
                    Nota de prueba
                    <textarea
                      required
                      value={note}
                      onChange={(e) => setNote(e.target.value)}
                      placeholder="Solo información ficticia para esta prueba"
                    />
                  </label>
                  <button className="secondary wide">Añadir nota</button>
                </form>
                <ErrorBox text={error} />
                {notice && (
                  <p role="status" className="success">
                    {notice}
                  </p>
                )}
              </section>
              <section className="card">
                <h2>Actividad del caso</h2>
                <ol className="timeline">
                  {c.data.events
                    .slice()
                    .reverse()
                    .map((e: Row) => (
                      <li key={e.id}>
                        <strong>
                          {e.kind === "review_note"
                            ? "Nota registrada"
                            : e.kind === "transition"
                              ? stateLabel[e.detail.state]
                              : e.kind === "notification_created"
                                ? "Aviso creado"
                                : e.kind === "simulated_escalation"
                                  ? "Reconocimiento pendiente"
                                  : "Evidencia registrada"}
                        </strong>
                        <small>{stamp(e.created_at)}</small>
                        <p>
                          {e.detail.text ||
                            reasonLabel[e.detail.reason] ||
                            e.detail.reason ||
                            ""}
                        </p>
                      </li>
                    ))}
                </ol>
              </section>
            </>
          )}
        </div>
      </div>
    </>
  );
}
function Overview() {
  const { data, error } = useData("/lab/overview");
  const devices = useData("/lab/devices");
  return (
    <>
      <Title
        eyebrow="INVESTIGACIÓN"
        title="Así está funcionando el laboratorio"
      >
        <Link className="primary" to="/lab/devices">
          Ver dispositivos
          <ChevronRight size={18} />
        </Link>
      </Title>
      <p className="lead">
        Verifica qué se captó, cómo se transformó y qué datos faltan.
      </p>
      <ErrorBox text={error} />
      <div className="stats">
        <Stat
          label="Participantes"
          value={data?.participants}
          icon={<Users />}
        />
        <Stat
          label="Dispositivos"
          value={data?.devices}
          icon={<MonitorSmartphone />}
          tone="blue"
        />
        <Stat
          label="Eventos registrados"
          value={data?.events?.toLocaleString("es-PE")}
          icon={<Database />}
          tone="teal"
        />
        <Stat
          label="Trabajos pendientes"
          value={data?.jobs_pending}
          icon={<Clock />}
          tone="amber"
        />
      </div>
      <div className="overview-grid">
        <section className="card">
          <h2>Del registro a la revisión</h2>
          <div className="pipeline">
            {[
              ["01", "Captura", "Pantalla, bloqueo y consultas"],
              ["02", "Calidad", "Ventanas, permisos y ausencias"],
              ["03", "Cambios", "Comparación con historial propio"],
              ["04", "Revisión", "Decisiones registradas por una persona"],
            ].map(([n, t, s]) => (
              <div key={n}>
                <span>{n}</span>
                <div>
                  <h3>{t}</h3>
                  <p>{s}</p>
                </div>
                <Check size={20} />
              </div>
            ))}
          </div>
          <Link to="/lab/features" className="text-link">
            Explorar trazabilidad <ArrowUpRight size={17} />
          </Link>
        </section>
        <section className="card">
          <h2>Capacidades del MVP</h2>
          <div className="quality-row">
            <span>Eventos de pantalla y bloqueo</span>
            <Badge tone="teal">Implementado</Badge>
          </div>
          <div className="quality-row">
            <span>Cuestionario de prueba</span>
            <Badge tone="teal">Disponible</Badge>
          </div>
          {["GPS / movilidad", "Pasos", "Estimación de sueño"].map((x) => (
            <div className="quality-row" key={x}>
              <span>{x}</span>
              <Badge>No implementado</Badge>
            </div>
          ))}
          <p className="fine">
            El detalle del dispositivo indica los permisos y consultas
            observados. Una API implementada no prueba captura en un teléfono
            concreto.
          </p>
        </section>
      </div>
      <section className="card">
        <h2>Dispositivos que requieren comprobación</h2>
        {devices.data
          ?.filter(
            (d: Row) =>
              d.detail.usage_access !== "available" ||
              d.detail.outbox_pending > 0,
          )
          .map((d: Row) => (
            <Link className="device-row" key={d.id} to={"/lab/devices/" + d.id}>
              <MonitorSmartphone />
              <strong>{d.pseudonym}</strong>
              <span>
                {d.detail.usage_access === "permission_missing"
                  ? "Falta acceso de uso"
                  : `${d.detail.outbox_pending} registros pendientes`}
              </span>
              <ChevronRight />
            </Link>
          ))}
      </section>
      <div className="info-strip">
        <FlaskConical />
        <div>
          <strong>Los experimentos se ejecutan fuera de la API</strong>
          <p>
            Los modelos DEMO prueban el circuito técnico. Sus resultados nunca
            se usan para atender participantes LAB.
          </p>
        </div>
      </div>
    </>
  );
}
function Devices() {
  const { data, error } = useData("/lab/devices");
  return (
    <>
      <Title eyebrow="CAPTURA Y SINCRONIZACIÓN" title="Dispositivos" />
      <ErrorBox text={error} />
      <div className="device-grid">
        {data?.map((d: Row) => (
          <Link
            className="card device-card"
            key={d.id}
            to={"/lab/devices/" + d.id}
          >
            <div className="section-heading plain">
              <span className="stat-icon blue">
                <MonitorSmartphone />
              </span>
              <Badge tone={d.status === "active" ? "teal" : "neutral"}>
                {stateLabel[d.status]}
              </Badge>
            </div>
            <h2>{d.pseudonym}</h2>
            <p>
              {d.detail.manufacturer} · {d.detail.model}
            </p>
            <div className="device-meta">
              <span>Android API {d.detail.android_api}</span>
              <span>
                Acceso de uso: {d.detail.usage_access || "sin comprobar"}
              </span>
              <span>Última sincronización: {stamp(d.detail.last_sync)}</span>
              <span>
                Cola pendiente: {d.detail.outbox_pending ?? "sin reporte"}
              </span>
            </div>
            <span className="text-link">
              Inspeccionar dispositivo
              <ChevronRight size={17} />
            </span>
          </Link>
        ))}
      </div>
      {data?.length === 0 && (
        <Empty>
          No hay dispositivos. Cree una invitación por CLI e instale la app en
          un teléfono adulto.
        </Empty>
      )}
    </>
  );
}
function DeviceDetail() {
  const id = useLocation().pathname.split("/").pop();
  const { data, error } = useData("/lab/devices/" + id);
  if (!data) return <ErrorBox text={error} />;
  return (
    <>
      <Link className="back" to="/lab/devices">
        ← Dispositivos
      </Link>
      <Title eyebrow="DIAGNÓSTICO TÉCNICO" title={data.pseudonym}>
        <Link className="primary" to={"/lab/events?device=" + id}>
          Ver eventos
        </Link>
      </Title>
      <div className="stats">
        <Stat
          label="Android API"
          value={data.detail.android_api}
          icon={<MonitorSmartphone />}
        />
        <Stat
          label="Batería"
          value={
            data.detail.battery !== undefined
              ? data.detail.battery + "%"
              : "Sin reporte"
          }
          icon={<Activity />}
        />
        <Stat
          label="Outbox"
          value={data.detail.outbox_pending}
          icon={<Database />}
        />
        <Stat
          label="Participación"
          value={stateLabel[data.status]}
          icon={<ShieldCheck />}
        />
      </div>
      <section className="card">
        <h2>Estado y capacidades</h2>
        <pre>{JSON.stringify(data.detail, null, 2)}</pre>
        <p>
          GPS y pasos: not_implemented. WorkManager es best effort; un permiso
          no garantiza eventos.
        </p>
      </section>
      <section className="card">
        <h2>Consultas del colector</h2>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Inicio</th>
                <th>Fin</th>
                <th>Resultado</th>
                <th>Permiso antes / después</th>
                <th>Eventos</th>
              </tr>
            </thead>
            <tbody>
              {data.captures.map((c: Row) => (
                <tr key={c.id}>
                  <td>{stamp(c.start_at)}</td>
                  <td>{stamp(c.end_at)}</td>
                  <td>{c.detail.success ? "Correcto" : c.detail.error}</td>
                  <td>
                    {String(c.detail.permission_before)} /{" "}
                    {String(c.detail.permission_after)}
                  </td>
                  <td>{c.detail.count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}
function Events() {
  const initial = new URLSearchParams(useLocation().search).get("device") || "";
  const [device, setDevice] = useState(initial);
  const [type, setType] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [source, setSource] = useState("");
  const [cursor, setCursor] = useState("");
  const [chosen, setChosen] = useState<Row | null>(null);
  const devices = useData("/lab/devices");
  const { data, error } = useData(
    "/lab/events?limit=50" +
      (device ? "&device_id=" + device : "") +
      (type ? "&event_type=" + type : "") +
      (cursor ? "&cursor=" + cursor : "") +
      (from ? "&start=" + from + "T00:00:00Z" : "") +
      (to ? "&end=" + to + "T00:00:00Z" : "") +
      (source ? "&source=" + source : ""),
  );
  return (
    <>
      <Title eyebrow="EVIDENCIA DE CAPTURA" title="Eventos captados" />
      <p className="lead">
        Registros permitidos, con origen y fecha del dispositivo. Se muestran 50
        por página.
      </p>
      <section className="card no-pad">
        <div className="filters">
          <select
            aria-label="Dispositivo"
            value={device}
            onChange={(e) => {
              setDevice(e.target.value);
              setCursor("");
            }}
          >
            <option value="">Todos los dispositivos</option>
            {devices.data?.map((d: Row) => (
              <option key={d.id} value={d.id}>
                {d.pseudonym}
              </option>
            ))}
          </select>
          <select
            aria-label="Tipo de evento"
            value={type}
            onChange={(e) => {
              setType(e.target.value);
              setCursor("");
            }}
          >
            <option value="">Todos los eventos</option>
            {[
              "SCREEN_INTERACTIVE",
              "SCREEN_NON_INTERACTIVE",
              "KEYGUARD_HIDDEN",
              "KEYGUARD_SHOWN",
              "ACTIVITY_RESUMED",
              "ACTIVITY_PAUSED",
              "DEVICE_STARTUP",
              "DEVICE_SHUTDOWN",
            ].map((t) => (
              <option key={t}>{t}</option>
            ))}
          </select>
          <input
            aria-label="Desde (UTC)"
            type="date"
            value={from}
            onChange={(e) => {
              setFrom(e.target.value);
              setCursor("");
            }}
          />
          <input
            aria-label="Hasta (UTC, exclusivo)"
            type="date"
            value={to}
            onChange={(e) => {
              setTo(e.target.value);
              setCursor("");
            }}
          />
          <select
            aria-label="Origen"
            value={source}
            onChange={(e) => {
              setSource(e.target.value);
              setCursor("");
            }}
          >
            <option value="">Todos los orígenes</option>
            <option value="synthetic_generator">Sintético</option>
            <option value="android_usage_events">Android real</option>
          </select>
        </div>
        <ErrorBox text={error} />
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Fecha del evento</th>
                <th>Tipo</th>
                <th>Origen</th>
                <th>Zona horaria</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {data?.items.map((e: Row) => (
                <tr key={e.id}>
                  <td>{stamp(e.occurred_at)}</td>
                  <td>
                    <code>{e.event_type}</code>
                    {e.clock_flag && <Badge tone="amber">Revisar reloj</Badge>}
                  </td>
                  <td>
                    <Badge
                      tone={
                        e.source === "synthetic_generator" ? "amber" : "teal"
                      }
                    >
                      {e.source === "synthetic_generator"
                        ? "Sintético"
                        : "Android real"}
                    </Badge>
                  </td>
                  <td>{e.timezone}</td>
                  <td>
                    <button className="secondary" onClick={() => setChosen(e)}>
                      JSON
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {data?.items.length === 0 && (
          <Empty>No hay eventos para estos filtros.</Empty>
        )}
        <div className="table-footer">
          <button
            className="secondary"
            disabled={!cursor}
            onClick={() => setCursor("")}
          >
            Primera página
          </button>
          <button
            className="secondary"
            disabled={!data?.next_cursor}
            onClick={() => setCursor(data.next_cursor)}
          >
            Siguiente página <ChevronRight size={16} />
          </button>
        </div>
      </section>
      {chosen && (
        <section className="card">
          <div className="section-heading plain">
            <h2>Registro permitido</h2>
            <button
              className="icon-button"
              aria-label="Cerrar registro"
              onClick={() => setChosen(null)}
            >
              <X />
            </button>
          </div>
          <pre>{JSON.stringify(chosen, null, 2)}</pre>
        </section>
      )}
    </>
  );
}
function Features() {
  const [device, setDevice] = useState("");
  const [chosen, setChosen] = useState<Row | null>(null);
  const [message, setMessage] = useState("");
  const devices = useData("/lab/devices");
  const features = useData(
    "/lab/features?limit=60" + (device ? "&device_id=" + device : ""),
  );
  return (
    <>
      <Title
        eyebrow="TRANSFORMACIONES VERSIONADAS"
        title="Variables y trazabilidad"
      />
      <p className="lead">
        Selecciona una variable diaria para recorrer sus intervalos y registros
        fuente.
      </p>
      <section className="card">
        <div className="filters">
          <select
            aria-label="Filtrar dispositivo"
            value={device}
            onChange={(e) => setDevice(e.target.value)}
          >
            <option value="">Todos los dispositivos</option>
            {devices.data?.map((d: Row) => (
              <option value={d.id} key={d.id}>
                {d.pseudonym}
              </option>
            ))}
          </select>
          <button
            className="secondary"
            disabled={!device}
            onClick={async () => {
              try {
                const d = features.data?.[0]?.day;
                if (!d) return;
                const j = await api("/lab/reprocessing-jobs", "POST", {
                  device_id: device,
                  start: d,
                  end: d,
                });
                setMessage("Reproceso encolado: " + j.id);
              } catch (e) {
                setMessage((e as Error).message);
              }
            }}
          >
            Reprocesar último día
          </button>
        </div>
        <p role="status">{message}</p>
        <ErrorBox text={features.error} />
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Día</th>
                <th>Pantalla</th>
                <th>Uso nocturno</th>
                <th>Calidad nocturna</th>
                <th>Versión</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {features.data?.map((f: Row) => (
                <tr key={f.id}>
                  <td>{f.day}</td>
                  <td>
                    {f.detail.features.interactive_minutes.value ?? "—"} min
                  </td>
                  <td>
                    {f.detail.features.night_interactive_minutes.value ?? "—"}{" "}
                    min
                  </td>
                  <td>
                    <Badge>
                      {
                        stateLabel[
                          f.detail.features.night_interactive_minutes.state
                        ]
                      }
                    </Badge>
                  </td>
                  <td>
                    <code>{f.version}</code>
                  </td>
                  <td>
                    <button
                      className="secondary"
                      onClick={async () =>
                        setChosen(
                          await api("/lab/features/" + f.id + "/lineage"),
                        )
                      }
                    >
                      Ver origen
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      {chosen && (
        <section className="card">
          <h2>Del intervalo a la variable · {chosen.feature.day}</h2>
          {chosen.raw_expired && (
            <p className="error">
              Parte del crudo expiró; el linaje conservado ya no permite
              reproducirlo completamente.
            </p>
          )}
          <h3>Intervalos confirmados</h3>
          {chosen.feature.detail.lineage.intervals.map((i: Row, n: number) => (
            <div className="quality-row" key={n}>
              <span>
                {stamp(i.start)} → {stamp(i.end)}
              </span>
              <strong>
                {(
                  (new Date(i.end).getTime() - new Date(i.start).getTime()) /
                  60000
                ).toFixed(1)}{" "}
                min
              </strong>
            </div>
          ))}
          <details>
            <summary>Eventos usados, descartes y cobertura</summary>
            <pre>{JSON.stringify(chosen, null, 2)}</pre>
          </details>
        </section>
      )}
    </>
  );
}
function Experiments() {
  const { data, error, reload } = useData("/lab/training-runs");
  const [task, setTask] = useState("concurrent");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const runs = (data || []).filter((r: Row) => r.kind === "training");
  const selected = runs.find((r: Row) => r.result.metrics);
  return (
    <>
      <Title
        eyebrow="MACHINE LEARNING EXPERIMENTAL"
        title="Experimentos DEMO"
      />
      <div className="info-strip">
        <FlaskConical />
        <div>
          <strong>Estimación experimental del cuestionario</strong>
          <p>
            Entrenamiento sintético de CHECKIN_DEMO_V1. No predice diagnósticos
            y no genera decisiones de atención.
          </p>
        </div>
      </div>
      <section className="card">
        <div className="run-controls">
          <label>
            Tarea
            <select value={task} onChange={(e) => setTask(e.target.value)}>
              <option value="concurrent">Concurrente · mismo período</option>
              <option value="prospective">
                Prospectiva · antes del período
              </option>
            </select>
          </label>
          <button
            className="primary"
            disabled={busy}
            onClick={async () => {
              setBusy(true);
              try {
                await api("/lab/training-runs", "POST", {
                  seed: 20260906,
                  task,
                });
                setMessage(
                  "Experimento encolado. El worker mostrará aquí el resultado.",
                );
                reload();
              } catch (e) {
                setMessage((e as Error).message);
              } finally {
                setBusy(false);
              }
            }}
          >
            <FlaskConical size={18} />
            Ejecutar experimento
          </button>
        </div>
        <p role="status">{message}</p>
        <ErrorBox text={error} />
        {runs.map((r: Row) => (
          <div className="job-row" key={r.id}>
            <span>
              <strong>Experimento DEMO · semilla {r.payload.seed}</strong>
              <small>
                {stamp(r.created_at)} · {r.payload.task}
              </small>
            </span>
            <Badge tone={r.state === "completed" ? "teal" : "amber"}>
              {stateLabel[r.state]}
            </Badge>
          </div>
        ))}
      </section>
      {selected && (
        <>
          <div className="stats">
            <Stat
              label="Participantes únicos"
              value={selected.result.participants}
              icon={<Users />}
            />
            <Stat
              label="Etiquetas sintéticas"
              value={selected.result.labels}
              icon={<FileText />}
            />
            <Stat
              label="Estado del modelo"
              value="DEMO"
              icon={<FlaskConical />}
            />
          </div>
          <section className="card">
            <h2>Comparación en participantes apartados</h2>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Modelo</th>
                    <th>MAE · puntos</th>
                    <th>RMSE · puntos</th>
                    <th>IC 95% MAE por participante</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(selected.result.metrics).map(([k, v]) => {
                    const m = v as Row;
                    return (
                      <tr key={k}>
                        <td>{k}</td>
                        <td>{m.mae.toFixed(3)}</td>
                        <td>{m.rmse.toFixed(3)}</td>
                        <td>
                          {m.participant_bootstrap_mae_ci95
                            .map((x: number) => x.toFixed(3))
                            .join(" – ")}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <p className="fine">
              Estos intervalos describen solo la muestra sintética, no
              generalización clínica.
            </p>
            <details>
              <summary>Particiones, evaluación temporal y model card</summary>
              <pre>{JSON.stringify(selected.result, null, 2)}</pre>
            </details>
          </section>
          <section className="card">
            <h2>Variables que influyeron en la estimación del modelo</h2>
            <p>SHAP en puntos del cuestionario; no porcentajes causales.</p>
            <div className="comparison">
              <div>
                <span>Base</span>
                <strong>{selected.result.shap.baseline.toFixed(3)}</strong>
              </div>
              <div>
                <span>Predicción DEMO</span>
                <strong>{selected.result.shap.prediction.toFixed(3)}</strong>
              </div>
            </div>
            {Object.entries(selected.result.shap.contributions)
              .sort((a, b) => Math.abs(Number(b[1])) - Math.abs(Number(a[1])))
              .slice(0, 6)
              .map(([k, v]) => (
                <div className="quality-row" key={k}>
                  <code>{k}</code>
                  <strong>
                    {Number(v) > 0 ? "+" : ""}
                    {Number(v).toFixed(3)} puntos
                  </strong>
                </div>
              ))}
          </section>
        </>
      )}
      {!runs.length && (
        <Empty>
          Todavía no hay modelos. Ejecuta un experimento DEMO; en LAB se informa
          que no está disponible.
        </Empty>
      )}
    </>
  );
}
function Exports() {
  const { data, error, reload } = useData("/lab/jobs");
  const [kind, setKind] = useState("features");
  const [start, setStart] = useState("2026-07-01");
  const [end, setEnd] = useState("2026-09-06");
  const [format, setFormat] = useState("csv");
  const [message, setMessage] = useState("");
  return (
    <>
      <Title eyebrow="SALIDAS AUTORIZADAS" title="Exportaciones" />
      <p className="lead">
        Descargas autenticadas, auditadas y con caducidad de 24 horas.
      </p>
      <section className="card">
        <form
          className="export-form"
          onSubmit={async (e) => {
            e.preventDefault();
            try {
              await api("/lab/exports", "POST", {
                kind,
                format,
                start: start + "T00:00:00Z",
                end: end + "T00:00:00Z",
              });
              setMessage("Exportación encolada");
              reload();
            } catch (e) {
              setMessage((e as Error).message);
            }
          }}
        >
          <label>
            Contenido
            <select value={kind} onChange={(e) => setKind(e.target.value)}>
              <option value="features">Variables calculadas</option>
              <option value="raw">Eventos crudos permitidos</option>
              <option value="labeled">Dataset etiquetado DEMO</option>
            </select>
          </label>
          <label>
            Desde
            <input
              type="date"
              required
              value={start}
              onChange={(e) => setStart(e.target.value)}
            />
          </label>
          <label>
            Hasta (exclusivo)
            <input
              type="date"
              required
              value={end}
              onChange={(e) => setEnd(e.target.value)}
            />
          </label>
          <label>
            Formato
            <select value={format} onChange={(e) => setFormat(e.target.value)}>
              <option>csv</option>
              <option>jsonl</option>
            </select>
          </label>
          <button className="primary">Crear exportación</button>
        </form>
        <p role="status">{message}</p>
      </section>
      <ErrorBox text={error} />
      <section className="card">
        <h2>Mis exportaciones</h2>
        {data
          ?.filter((j: Row) => j.kind === "export")
          .map((j: Row) => (
            <div className="job-row" key={j.id}>
              <span>
                <strong>
                  {j.payload.kind} · {j.payload.format.toUpperCase()}
                </strong>
                <small>
                  {stamp(j.created_at)} · {j.result.rows ?? "—"} filas ·{" "}
                  {j.result.participants ?? "—"} participantes
                </small>
              </span>
              <Badge>{stateLabel[j.state]}</Badge>
              {j.state === "completed" && (
                <a
                  className="secondary"
                  href={"/api/v1/lab/exports/" + j.id + "/download"}
                >
                  Descargar
                  <Download size={17} />
                </a>
              )}
            </div>
          ))}
      </section>
    </>
  );
}
function Participant() {
  const [token, setToken] = useState("");
  const [invite, setInvite] = useState("");
  const [me, setMe] = useState<Row | null>(null);
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const [message, setMessage] = useState("");
  const [adult, setAdult] = useState(false);
  const [form, setForm] = useState<Row | null>(null);
  const [key, setKey] = useState(crypto.randomUUID());
  const [submission, setSubmission] = useState<Row | null>(null);
  const [mode, setMode] = useState("");
  useEffect(() => {
    api("/health")
      .then((r) => setMode(r.mode))
      .catch(() => {});
  }, []);
  async function load(t: string) {
    setMe(await api("/me", "GET", undefined, t));
    setForm((await api("/questionnaires/due", "GET", undefined, t))[0]);
  }
  return (
    <div className="participant-page">
      <Link className="brand" to="/">
        <HeartHandshake /> Acompaña Escolar
      </Link>
      <div className="mode-banner">
        {mode === "DEMO"
          ? "Demostración · datos ficticios"
          : "Laboratorio · formulario de prueba"}
      </div>
      <section className="card">
        <h1>{me ? me.pseudonym : "Prueba del formulario"}</h1>
        <p>
          Esta pantalla permite comprobar el circuito del cuestionario. La
          captura real de uso requiere instalar la app Android.
        </p>
        {!token ? (
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              try {
                const r = await api("/enrollments/redeem", "POST", {
                  invitation: invite,
                  device: {
                    android_api: 29,
                    manufacturer: "Formulario web de prueba",
                    model: "Sin sensores",
                    app_version: "0.1.0-web",
                    timezone: "America/Lima",
                  },
                });
                setToken(r.token);
                await load(r.token);
                setMessage("Dispositivo de formulario vinculado");
              } catch (e) {
                setMessage((e as Error).message);
              }
            }}
          >
            <label>
              Invitación de un uso
              <input
                value={invite}
                onChange={(e) => setInvite(e.target.value)}
                required
              />
            </label>
            <button className="primary">Vincular formulario</button>
          </form>
        ) : me?.status !== "active" ? (
          <>
            <label className="check-label">
              <input
                type="checkbox"
                checked={adult}
                onChange={(e) => setAdult(e.target.checked)}
              />
              Soy adulto y acepto participar en esta prueba interna de
              formularios. Puedo retirarme.
            </label>
            <button
              className="primary"
              disabled={!adult}
              onClick={async () => {
                try {
                  await api(
                    "/me/participation-events",
                    "POST",
                    {
                      action: me?.status === "paused" ? "resume" : "consent",
                      occurred_at: new Date().toISOString(),
                      adult: true,
                    },
                    token,
                  );
                  await load(token);
                } catch (e) {
                  setMessage((e as Error).message);
                }
              }}
            >
              Aceptar y continuar
            </button>
          </>
        ) : (
          <>
            <Badge tone="teal">Participación activa</Badge>
            <h2>Cuestionario de prueba</h2>
            <p>{form?.notice}</p>
            <form
              onSubmit={async (e) => {
                e.preventDefault();
                const body = submission || {
                  instrument_code: form?.instrument_id,
                  answers,
                  applied_at: new Date().toISOString(),
                  recall_start: new Date(
                    new Date().setHours(0, 0, 0, 0),
                  ).toISOString(),
                  recall_end: new Date().toISOString(),
                };
                setSubmission(body);
                try {
                  await api(
                    "/questionnaire-responses",
                    "POST",
                    body,
                    token,
                    key,
                  );
                  setMessage("Respuesta guardada en el servidor");
                  setAnswers({});
                  setKey(crypto.randomUUID());
                  setSubmission(null);
                } catch (e) {
                  setMessage("Pendiente de envío: " + (e as Error).message);
                }
              }}
            >
              {form?.questions.map((q: Row) => (
                <fieldset key={q.id}>
                  <legend>{q.text}</legend>
                  <div className="answer-options">
                    {form.options.map((o: Row) => (
                      <label key={o.value}>
                        <input
                          type="radio"
                          name={q.id}
                          required
                          checked={answers[q.id] === o.value}
                          onChange={() => {
                            setAnswers({ ...answers, [q.id]: o.value });
                            setSubmission(null);
                          }}
                        />
                        {o.label}
                      </label>
                    ))}
                  </div>
                </fieldset>
              ))}
              <button className="primary wide">Enviar cuestionario</button>
            </form>
            <hr />
            <button
              className="secondary wide"
              onClick={async () => {
                try {
                  await api(
                    "/contact-requests",
                    "POST",
                    { requested_at: new Date().toISOString() },
                    token,
                  );
                  setMessage(
                    "Solicitud recibida por el servidor. Pendiente de reconocimiento.",
                  );
                } catch (e) {
                  setMessage("No enviada: " + (e as Error).message);
                }
              }}
            >
              <MessageCircle size={18} />
              Quiero que me contacten
            </button>
            <p className="fine">
              Se prueba el flujo. No existe atención de emergencia garantizada.
            </p>
            <button
              className="text-button"
              onClick={async () => {
                await api(
                  "/me/participation-events",
                  "POST",
                  { action: "pause", occurred_at: new Date().toISOString() },
                  token,
                );
                await load(token);
              }}
            >
              Pausar participación
            </button>
          </>
        )}
        <p role="status" className="status-message">
          {message}
        </p>
      </section>
    </div>
  );
}
function Entry() {
  const [mode, setMode] = useState("");
  const [error, setError] = useState("");
  useEffect(() => {
    fetch("/api/v1/health")
      .then((r) => {
        if (!r.ok) throw new Error("Servidor no disponible");
        return r.json();
      })
      .then((d) => setMode(d.mode))
      .catch((e) => setError(e.message));
  }, []);
  if (error) return <ErrorBox text={error} />;
  if (!mode) return <Empty>Conectando…</Empty>;
  return mode === "REAL" ? <ProductApp /> : <App />;
}
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <Entry />
    </BrowserRouter>
  </React.StrictMode>,
);
