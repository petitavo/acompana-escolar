import React, { useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import {
  Activity,
  ArrowRight,
  Bell,
  CalendarDays,
  Check,
  CheckCircle2,
  ChevronRight,
  ClipboardList,
  Download,
  HeartHandshake,
  Home,
  LogOut,
  MapPin,
  Menu,
  Plus,
  Search,
  Settings,
  ShieldCheck,
  SlidersHorizontal,
  Smartphone,
  Users,
  X,
  FlaskConical,
  Clock3,
  GraduationCap,
} from "lucide-react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
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
import "./product.css";
type R = Record<string, any>;
const S = "/school";
const labels: R = {
  ...stateLabel,
  pending: "Pendiente",
  confirmed: "Confirmada",
  cancelled: "Cancelada",
  registered: "Registrado",
  shadow: "En sombra",
  active: "Activo",
  retired: "Retirado",
  created: "En bandeja",
  sent: "Aceptado por el canal",
  delivered: "Recibido en dispositivo",
  acknowledged: "Reconocido",
};
const reasons: R = {
  ...reasonLabel,
  safety_review: "Revisión de seguridad",
  model_estimate: "Estimación del modelo",
};
const fields: R = {
  ...featureLabel,
  observed_distance_m: "Distancia observada",
  radius_gyration_m: "Radio de movimiento",
  home_minutes: "Tiempo en zona habitual",
  place_entropy: "Diversidad de lugares",
  observed_steps: "Pasos con el teléfono",
};
const roleNames: R = {
  admin: "Administración",
  director: "Dirección",
  psychologist: "Psicología",
  practitioner: "Prácticas supervisadas",
  researcher: "Investigación",
};
function useData(path: string | null, interval = 0) {
  const [data, setData] = useState<any>(null),
    [error, setError] = useState(""),
    [revision, setRevision] = useState(0);
  useEffect(() => { setData(null); setError(""); }, [path]);
  useEffect(() => {
    if (!path) return;
    let alive = true;
    const load = () =>
      api(path)
        .then((v) => {
          if (alive) {
            setData(v);
            setError("");
          }
        })
        .catch((e) => alive && setError(e.message));
    load();
    const id = interval ? setInterval(load, interval) : undefined;
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [path, revision, interval]);
  return { data, error, refresh: () => setRevision((v) => v + 1) };
}
function Empty({
  title,
  children,
}: {
  title: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="p-empty">
      <HeartHandshake size={30} />
      <h3>{title}</h3>
      <p>{children}</p>
    </div>
  );
}
function ErrorMessage({ value }: { value?: string }) {
  return value ? (
    <div className="p-error" role="alert">
      {value}
    </div>
  ) : null;
}
function Tag({
  children,
  tone = "",
}: {
  children: React.ReactNode;
  tone?: string;
}) {
  return <span className={"p-tag " + tone}>{children}</span>;
}
function PageTitle({
  eyebrow,
  title,
  children,
}: {
  eyebrow: string;
  title: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="p-page-title">
      <div>
        <span className="p-eyebrow">{eyebrow}</span>
        <h1>{title}</h1>
      </div>
      <div>{children}</div>
    </div>
  );
}
function Modal({
  title,
  close,
  children,
}: {
  title: string;
  close: () => void;
  children: React.ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    ref.current?.showModal();
    return () => ref.current?.close();
  }, []);
  return (
    <dialog ref={ref} className="p-modal" onCancel={close}>
      <header>
        <h2>{title}</h2>
        <button className="p-icon" onClick={close} aria-label="Cerrar">
          <X />
        </button>
      </header>
      {children}
    </dialog>
  );
}
function Form({
  children,
  task,
  done,
  submit = "Guardar cambios",
}: {
  children: React.ReactNode;
  task: (data: FormData) => Promise<any>;
  done?: (v: any) => void;
  submit?: string;
}) {
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [saved, setSaved] = useState(false);
  return (
    <form
      className="p-form"
      onSubmit={async (e) => {
        e.preventDefault();
        const f = new FormData(e.currentTarget);
        setBusy(true);
        setError("");
        setSaved(false);
        try {
          const r = await task(f);
          setSaved(true);
          done?.(r);
        } catch (e) {
          setError((e as Error).message);
        } finally {
          setBusy(false);
        }
      }}
    >
      <fieldset disabled={busy}>{children}</fieldset>
      <ErrorMessage value={error} />
      <div className="p-form-end">
        <button className="p-primary" disabled={busy}>
          {busy ? "Guardando…" : submit}
        </button>
        {saved && (
          <span role="status">
            <Check size={16} /> Guardado
          </span>
        )}
      </div>
    </form>
  );
}
function Input({
  label,
  name,
  value,
  type = "text",
  required = true,
  ...rest
}: any) {
  return (
    <label>
      {label}
      <input
        name={name}
        type={type}
        defaultValue={value}
        required={required}
        {...rest}
      />
    </label>
  );
}
function Select({ label, name, options, value, required = true }: any) {
  return (
    <label>
      {label}
      <select name={name} defaultValue={value || ""} required={required}>
        <option value="">Seleccionar…</option>
        {options.map((o: R) => (
          <option key={o.id} value={o.id}>
            {o.name || o.username || o.label}
          </option>
        ))}
      </select>
    </label>
  );
}
function Note({ children }: { children: React.ReactNode }) {
  return (
    <div className="p-note">
      <ShieldCheck size={20} />
      <div>{children}</div>
    </div>
  );
}
function downloadJson(value: any, name: string) {
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(value, null, 2)], { type: "application/json" }),
  );
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}

export default function ProductApp() {
  const [me, setMe] = useState<R | null>(null),
    [ready, setReady] = useState(false),
    [open, setOpen] = useState(false),
    [boot, setBoot] = useState<R | null>(null),
    [bootError, setBootError] = useState("");
  const location = useLocation(),
    navigate = useNavigate();
  useEffect(() => {
    const expire = () => {
      setMe(null);
      setCsrf("");
    };
    window.addEventListener("session-expired", expire);
    api("/me")
      .then((d) => {
        setMe(d);
        setCsrf(d.csrf_token);
      })
      .catch(() => {})
      .finally(() => setReady(true));
    return () => window.removeEventListener("session-expired", expire);
  }, []);
  useEffect(() => {
    if (me) {
      setBootError("");
      api(S + "/bootstrap")
        .then(setBoot)
        .catch(() => setBootError("No se pudo cargar la institución. Comprueba tu conexión y vuelve a intentar."));
    }
  }, [me]);
  const notifications = useData(me ? S + "/notifications" : null, 15000);
  if (location.pathname === "/guardian")
    return (
      <div className="product">
        <Guardian />
      </div>
    );
  if (location.pathname === "/student")
    return (
      <div className="product">
        <StudentPortal />
      </div>
    );
  if (!ready)
    return (
      <div className="product">
        <Empty title="Preparando tu espacio…" />
      </div>
    );
  if (!me)
    return (
      <div className="product">
        <ProductLogin
          onLogin={(d) => {
            setMe(d);
            setCsrf(d.csrf_token);
            navigate("/school/overview");
          }}
        />
      </div>
    );
  if (!boot)
    return (
      <div className="product">
        <Empty title={bootError || "Cargando tu institución…"} />
        {bootError && <button onClick={() => window.location.reload()}>Volver a intentar</button>}
      </div>
    );
  if (!boot.configured)
    return (
      <div className="product">
        <Setup onDone={() => api(S + "/bootstrap").then(setBoot)} />
      </div>
    );
  const clinical = ["psychologist", "practitioner"].includes(me.role);
  const technical = me.scopes?.includes("diagnostics");
  const modelAccess =
    me.scopes?.includes("models") ||
    (me.role === "psychologist" &&
      boot.institution?.settings?.primary_id === me.id);
  const links: any[] = [
    [Home, "Resumen", "/school/overview"],
    ...(clinical
      ? [
          [ClipboardList, "Casos por revisar", "/school/cases"],
          [Users, "Estudiantes", "/school/students"],
          [CheckCircle2, "Seguimientos", "/school/followups"],
        ]
      : [[GraduationCap, "Estudiantes", "/school/students"]]),
    [CalendarDays, "Calendario", "/school/calendar"],
    [Bell, "Bandeja", "/school/inbox"],
    ...(["admin", "director"].includes(me.role)
      ? [[Settings, "Administración", "/school/administration"]]
      : []),
    ...(["admin", "psychologist"].includes(me.role)
      ? [[ShieldCheck, "Configuración escolar", "/school/settings"]]
      : []),
    ...(modelAccess
      ? [[FlaskConical, "Modelos y evaluación", "/school/models"]]
      : []),
    ...(technical
      ? [[Activity, "Diagnóstico de datos", "/school/diagnostics"]]
      : []),
    [SlidersHorizontal, "Configuración personal", "/school/preferences"],
  ];
  const path = location.pathname;
  let content: React.ReactNode;
  if (/^\/school\/cases\/.+/.test(path))
    content = <CasePage id={path.split("/")[3]} />;
  else if (/^\/school\/students\/.+/.test(path))
    content = <StudentProfilePage id={path.split("/")[3]} />;
  else if (path === "/school/cases") content = <Cases />;
  else if (path === "/school/students") content = <Students me={me} />;
  else if (path === "/school/followups") content = <Followups />;
  else if (path === "/school/calendar") content = <Calendar me={me} />;
  else if (path === "/school/administration")
    content = <Administration me={me} />;
  else if (path === "/school/settings")
    content = (
      <SchoolSettings onSaved={() => api(S + "/bootstrap").then(setBoot)} />
    );
  else if (path === "/school/diagnostics") content = <Diagnostics me={me} />;
  else if (path === "/school/models") content = <Models me={me} />;
  else if (path === "/school/inbox") content = <Inbox data={notifications} />;
  else if (path === "/school/preferences") content = <Preferences />;
  else content = <Overview me={me} />;
  return (
    <div className="product p-shell">
      <aside className={"p-sidebar " + (open ? "is-open" : "")}>
        <Link className="p-brand" to="/school/overview">
          <span>
            <HeartHandshake size={27} />
          </span>
          <div>
            Acompaña<small>ESCOLAR</small>
          </div>
        </Link>
        <div className="p-institution">
          <GraduationCap size={19} />
          <span>{boot.institution?.name}</span>
        </div>
        <nav aria-label="Navegación principal">
          {links.map(([Icon, label, url]) => (
            <Link
              className={path.startsWith(url) ? "active" : ""}
              key={url}
              to={url}
              onClick={() => setOpen(false)}
            >
              <Icon size={20} />
              <span>{label}</span>
            </Link>
          ))}
        </nav>
        <div className="p-sidebar-bottom">
          <div className="p-avatar">{me.username?.[0]?.toUpperCase()}</div>
          <div>
            <strong>{me.username}</strong>
            <small>{roleNames[me.role]}</small>
          </div>
          <button
            className="p-icon"
            aria-label="Cerrar sesión"
            onClick={async () => {
              await api("/auth/logout", "POST", {});
              setMe(null);
              setBoot(null);
            }}
          >
            <LogOut size={18} />
          </button>
        </div>
      </aside>
      {open && (
        <button
          className="p-menu-shade"
          aria-label="Cerrar navegación"
          onClick={() => setOpen(false)}
        />
      )}
      <div className="p-main">
        <header className="p-topbar">
          <button
            className="p-mobile-menu p-icon"
            aria-label="Abrir navegación"
            onClick={() => setOpen(!open)}
          >
            <Menu />
          </button>
          <span>
            {roleNames[me.role]} <ChevronRight size={14} />{" "}
            <strong>Tu espacio de trabajo</strong>
          </span>
          <Link
            to="/school/inbox"
            className="p-notification-link"
            aria-label="Abrir bandeja"
          >
            <Bell size={20} />
            {notifications.data?.filter((n: R) => !n.acknowledged_at).length >
              0 && <i />}
          </Link>
        </header>
        <main className="p-content">{content}</main>
        <footer className="p-footer">
          Acompaña Escolar · Información para acompañar, decisiones a cargo de
          profesionales.
        </footer>
      </div>
    </div>
  );
}
function ProductLogin({ onLogin }: { onLogin: (v: R) => void }) {
  return (
    <div className="p-login">
      <section className="p-login-story">
        <div className="p-brand">
          <span>
            <HeartHandshake size={29} />
          </span>
          <div>
            Acompaña<small>ESCOLAR</small>
          </div>
        </div>
        <div className="p-story-copy">
          <span className="p-eyebrow">CERCA, CUANDO HACE FALTA</span>
          <h1>
            Acompañar empieza
            <br />
            por escuchar.
          </h1>
          <p>
            Un espacio para conocer el contexto de cada estudiante y dar
            continuidad al acompañamiento del equipo.
          </p>
          <div className="p-hero-art" aria-hidden="true">
            <div className="p-orbit" />
            <div className="p-orbit second" />
            <span className="p-art-card">
              <HeartHandshake size={48} />
              <b>
                Con tiempo.
                <br />
                Con contexto.
                <br />
                Con cuidado.
              </b>
            </span>
            <span className="p-art-dot one">
              <Users />
            </span>
            <span className="p-art-dot two">
              <CheckCircle2 />
            </span>
          </div>
        </div>
        <p className="p-story-foot">
          <ShieldCheck size={17} /> Privacidad y participación informada
        </p>
      </section>
      <section className="p-login-form">
        <span className="p-eyebrow">BIENVENIDO A TU ESPACIO</span>
        <h2>Iniciar sesión</h2>
        <p>Ingresa con la cuenta que te asignó tu institución.</p>
        <Form
          submit="Entrar a mi espacio"
          task={(f) =>
            api("/auth/login", "POST", {
              username: f.get("username"),
              password: f.get("password"),
            })
          }
          done={onLogin}
        >
          <Input label="Usuario" name="username" autoComplete="username" />
          <Input
            label="Contraseña"
            name="password"
            type="password"
            autoComplete="current-password"
          />
        </Form>
        <div className="p-login-divider" />
        <Link className="p-invitation-link" to="/student">
          Tengo una invitación de estudiante <ArrowRight size={17} />
        </Link>
        <p className="p-muted">
          ¿Necesitas recuperar tu acceso? Contacta al administrador de tu
          institución.
        </p>
      </section>
    </div>
  );
}
function Setup({ onDone }: { onDone: () => void }) {
  return (
    <div className="p-setup">
      <div className="p-brand">
        <HeartHandshake /> Acompaña Escolar
      </div>
      <PageTitle
        eyebrow="CONFIGURACIÓN INICIAL · PASO 1"
        title="Demos forma a tu institución"
      />
      <p>
        Después podrás crear el equipo, registrar el horario de atención y
        preparar las invitaciones. La captación del piloto permanece apagada.
      </p>
      <section className="p-card">
        <Form
          task={(f) =>
            api(S + "/setup", "POST", {
              name: f.get("name"),
              timezone: f.get("timezone"),
            })
          }
          done={onDone}
          submit="Crear institución y continuar"
        >
          <Input
            label="Nombre de la institución"
            name="name"
            placeholder="Nombre de tu colegio"
            minLength={3}
          />
          <Input label="Zona horaria" name="timezone" value="America/Lima" />
        </Form>
      </section>
    </div>
  );
}
function Overview({ me }: { me: R }) {
  const overview = useData(S + "/overview", 15000),
    calendar = useData(S + "/calendar");
  const d = overview.data;
  const clinical = ["psychologist", "practitioner"].includes(me.role);
  return (
    <>
      <PageTitle
        eyebrow="UNA MIRADA AL DÍA"
        title={
          clinical ? "Cada seguimiento cuenta" : "Tu comunidad, bien organizada"
        }
      >
        <span className="p-today">
          {new Date().toLocaleDateString("es-PE", {
            weekday: "long",
            day: "numeric",
            month: "long",
          })}
        </span>
      </PageTitle>
      <ErrorMessage value={overview.error} />
      <div className="p-welcome">
        <div>
          <Tag tone="teal">
            {clinical
              ? "ACOMPAÑAMIENTO CON CONTINUIDAD"
              : "CONFIGURACIÓN DE TU INSTITUCIÓN"}
          </Tag>
          <h2>
            {clinical
              ? "Lo importante tiene un próximo paso."
              : "Prepara el espacio antes de invitar."}
          </h2>
          <p>
            {clinical
              ? "Revisa las solicitudes, reconoce lo pendiente y acuerda el siguiente contacto con cada estudiante."
              : "Define quién acompaña, cuándo está disponible y qué información se comparte."}
          </p>
          <Link
            className="p-primary"
            to={clinical ? "/school/cases" : "/school/administration"}
          >
            {clinical ? "Ver casos por revisar" : "Organizar mi institución"}{" "}
            <ArrowRight size={17} />
          </Link>
        </div>
        <div className="p-welcome-symbol">
          <HeartHandshake size={76} />
        </div>
      </div>
      <div className="p-stats">
        {(clinical
          ? [
              ["Por reconocer", d?.pending, ClipboardList],
              ["Solicitudes de apoyo", d?.support, HeartHandshake],
              ["Seguimientos vencidos", d?.overdue, Clock3],
              ["Estudiantes asignados", d?.students, Users],
            ]
          : [
              ["Estudiantes", d?.students, Users],
              ["Aulas registradas", d?.classrooms, GraduationCap],
              [
                "Autorizaciones pendientes",
                d?.pending_authorizations,
                ShieldCheck,
              ],
              [
                "Cuestionario",
                d
                  ? d.instrument_enabled
                    ? "Configurado"
                    : "Por configurar"
                  : "—",
                ClipboardList,
              ],
            ]
        ).map(([label, value, Icon]: any) => (
          <section className="p-stat" key={label}>
            <span>
              {label}
              <Icon size={20} />
            </span>
            <strong>{value ?? "—"}</strong>
            <small>
              {clinical
                ? "Dentro de tu ámbito de atención"
                : "Información administrativa"}
            </small>
          </section>
        ))}
      </div>
      <div className="p-columns">
        <section className="p-card">
          <header>
            <h2>
              {clinical ? "Para revisar hoy" : "Tu ruta de configuración"}
            </h2>
            <Link to={clinical ? "/school/cases" : "/school/settings"}>
              Ver todo <ArrowRight size={15} />
            </Link>
          </header>
          {clinical ? (
            d?.recent?.length ? (
              <CaseRows rows={d.recent} />
            ) : (
              <Empty title="Tu bandeja está al día">
                Las solicitudes y motivos de revisión aparecerán aquí cuando se
                reciban.
              </Empty>
            )
          ) : (
            <div className="p-setup-steps">
              {[
                ["1", "Crea las cuentas del equipo", "/school/administration"],
                [
                  "2",
                  "Registra horarios, recursos e instrumento",
                  "/school/settings",
                ],
                [
                  "3",
                  "Organiza las aulas y las invitaciones",
                  "/school/students",
                ],
              ].map(([n, title, to]) => (
                <Link to={to} key={n}>
                  <span>{n}</span>
                  <strong>{title}</strong>
                  <ArrowRight size={18} />
                </Link>
              ))}
            </div>
          )}
        </section>
        <section className="p-card">
          <header>
            <h2>En el calendario</h2>
            <CalendarDays size={19} />
          </header>
          {calendar.data?.length ? (
            calendar.data.slice(0, 4).map((e: R) => (
              <div className="p-event" key={e.id}>
                <div className="p-event-date">
                  {new Date(e.start_at).getDate()}
                  <small>
                    {new Date(e.start_at).toLocaleString("es-PE", {
                      month: "short",
                    })}
                  </small>
                </div>
                <div>
                  <strong>{e.title}</strong>
                  <p>{stamp(e.start_at)}</p>
                </div>
              </div>
            ))
          ) : (
            <Empty title="Un calendario con contexto">
              Agrega exámenes, vacaciones y actividades escolares.
            </Empty>
          )}
        </section>
      </div>
    </>
  );
}
function CaseRows({ rows }: { rows: R[] }) {
  return (
    <div className="p-table-wrap">
      <table className="p-table">
        <thead>
          <tr>
            <th>Estudiante</th>
            <th>Motivo de revisión</th>
            <th>Estado</th>
            <th>Recibido</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {rows.map((c) => (
            <tr key={c.id}>
              <td>
                <Link className="p-person" to={"/school/cases/" + c.id}>
                  <span className="p-avatar">
                    {(c.student?.display_name || c.pseudonym)?.[0]}
                  </span>
                  <span>
                    <strong>{c.student?.display_name || c.pseudonym}</strong>
                    <small>
                      {c.group}
                      {c.student?.is_test ? " · Cuenta de prueba" : ""}
                    </small>
                  </span>
                </Link>
              </td>
              <td>
                <div className="p-tags">
                  {c.reasons
                    .filter((r: R) => r.active)
                    .map((r: R) => (
                      <Tag
                        key={r.id}
                        tone={r.kind === "safety_review" ? "amber" : ""}
                      >
                        {reasons[r.kind] || r.kind}
                      </Tag>
                    ))}
                </div>
              </td>
              <td>{labels[c.state] || c.state}</td>
              <td>{stamp(c.created_at)}</td>
              <td>
                <Link
                  to={"/school/cases/" + c.id}
                  aria-label={
                    "Abrir caso de " + (c.student?.display_name || c.pseudonym)
                  }
                >
                  <ChevronRight size={19} />
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
function Cases() {
  const { data, error } = useData(S + "/cases", 15000),
    [filter, setFilter] = useState("open"),
    [search, setSearch] = useState("");
  const rows = (data || []).filter(
    (r: R) =>
      (filter === "all" ||
        (filter === "closed" ? r.state === "closed" : r.state !== "closed")) &&
      (r.student.display_name + r.group)
        .toLowerCase()
        .includes(search.toLowerCase()),
  );
  return (
    <>
      <PageTitle
        eyebrow="ESCUCHAR · RECONOCER · DAR CONTINUIDAD"
        title="Casos por revisar"
      />
      <Note>
        Los motivos orientan el trabajo del equipo. Una revisión de seguridad
        requiere valoración profesional; el sistema no determina por sí solo
        peligro inminente.
      </Note>
      <section className="p-card">
        <div className="p-toolbar">
          <div className="p-tabs">
            {[
              ["open", "Abiertos"],
              ["closed", "Cerrados"],
              ["all", "Todos"],
            ].map(([k, l]) => (
              <button
                key={k}
                className={filter === k ? "active" : ""}
                onClick={() => setFilter(k)}
              >
                {l}
              </button>
            ))}
          </div>
          <label className="p-search">
            <Search size={17} />
            <input
              aria-label="Buscar estudiante"
              placeholder="Buscar por estudiante o aula"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </label>
        </div>
        <ErrorMessage value={error} />
        {rows.length ? (
          <CaseRows rows={rows} />
        ) : (
          <Empty title="No hay casos en esta vista">
            Las solicitudes de apoyo y la evidencia recibida se guardarán aquí.
          </Empty>
        )}
      </section>
    </>
  );
}
function InvitationResult({ value }: { value: R }) {
  const invite = value.invitation;
  const guardian = value.guardian;
  return (
    <div className="p-invitation-result">
      <Tag tone="teal">Invitación preparada</Tag>
      <h3>{value.student.display_name}</h3>
      <p>
        Entrega cada enlace a su destinatario y el código de verificación por un
        canal separado. No se envió ningún mensaje externo.
      </p>
      <label>
        Invitación del estudiante
        <textarea readOnly value={invite.token} />
      </label>
      <label>
        Código del estudiante
        <input readOnly value={invite.verification_code} />
      </label>
      {guardian && (
        <>
          <label>
            Enlace del responsable
            <textarea
              readOnly
              value={location.origin + "/guardian?token=" + guardian.token}
            />
          </label>
          <label>
            Código del responsable
            <input readOnly value={guardian.verification_code} />
          </label>
        </>
      )}
      <button
        type="button"
        className="p-secondary"
        onClick={() => downloadJson(value, "invitacion-individual.json")}
      >
        <Download size={16} /> Guardar comprobante privado
      </button>
    </div>
  );
}
function Students({ me }: { me: R }) {
  const list = useData(S + "/students"),
    classes = useData(S + "/classrooms"),
    accounts = useData(S + "/accounts");
  const [modal, setModal] = useState(""),
    [result, setResult] = useState<R | null>(null),
    [search, setSearch] = useState(""),
    [selected, setSelected] = useState<R | null>(null);
  const admin = ["admin", "director"].includes(me.role);
  const rows = (list.data || []).filter((r: R) =>
    r.display_name.toLowerCase().includes(search.toLowerCase()),
  );
  return (
    <>
      <PageTitle
        eyebrow={
          admin ? "COMUNIDAD E INCORPORACIÓN" : "CONTEXTO PARA ACOMPAÑAR"
        }
        title="Estudiantes"
      >
        {admin && (
          <div className="p-inline">
            <button className="p-secondary" onClick={() => setModal("csv")}>
              Importar CSV
            </button>
            <button
              className="p-primary"
              onClick={() => {
                setResult(null);
                setModal("invite");
              }}
            >
              <Plus size={17} /> Invitar estudiante
            </button>
          </div>
        )}
      </PageTitle>
      <section className="p-card">
        <div className="p-toolbar">
          <h2>{admin ? "Tu institución" : "Estudiantes asignados"}</h2>
          <label className="p-search">
            <Search size={17} />
            <input
              aria-label="Buscar estudiante"
              placeholder="Buscar por nombre"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </label>
        </div>
        <ErrorMessage value={list.error} />
        {rows.length ? (
          <div className="p-table-wrap">
            <table className="p-table">
              <thead>
                <tr>
                  <th>Estudiante</th>
                  <th>Aula</th>
                  <th>Participación</th>
                  <th>Autorización</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {rows.map((r: R) => (
                  <tr key={r.id}>
                    <td>
                      <strong>{r.display_name}</strong>
                      {r.is_test && <small>Cuenta de prueba</small>}
                    </td>
                    <td>
                      {
                        classes.data?.find((c: R) => c.id === r.classroom_id)
                          ?.name
                      }
                    </td>
                    <td>{labels[r.status] || r.status}</td>
                    <td>
                      <Tag tone={r.authorization.ready ? "teal" : "amber"}>
                        {r.authorization.ready ? "Completa" : "Pendiente"}
                      </Tag>
                    </td>
                    <td>
                      {admin ? (
                        <button
                          className="p-link"
                          onClick={() => {
                            setSelected(r);
                            setModal("manage");
                          }}
                        >
                          Gestionar <ChevronRight size={14} />
                        </button>
                      ) : ["psychologist", "practitioner"].includes(me.role) ? (
                        <Link to={"/school/students/" + r.participant_id}>
                          Ver perfil <ChevronRight size={14} />
                        </Link>
                      ) : (
                        <span className="p-muted">Diagnóstico autorizado</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Empty title="Aquí comienza cada acompañamiento">
            {admin
              ? "Crea primero un aula y una cuenta de psicología; después prepara invitaciones individuales."
              : "Los estudiantes aparecerán cuando te los asigne la institución."}
          </Empty>
        )}
      </section>
      {modal === "invite" && (
        <Modal title="Invitar a un estudiante" close={() => setModal("")}>
          {result ? (
            <InvitationResult value={result} />
          ) : (
            <Form
              submit="Crear invitación individual"
              task={(f) =>
                api(S + "/students", "POST", {
                  display_name: f.get("display_name"),
                  classroom_id: f.get("classroom_id"),
                  psychologist_id: f.get("psychologist_id"),
                  minor: f.has("minor"),
                  is_test: f.has("is_test"),
                  guardian_channel: f.get("guardian_channel"),
                })
              }
              done={(v) => {
                setResult(v);
                list.refresh();
              }}
            >
              <Input label="Nombre autorizado" name="display_name" />
              <Select
                label="Aula"
                name="classroom_id"
                options={classes.data || []}
              />
              <Select
                label="Psicólogo asignado"
                name="psychologist_id"
                options={
                  accounts.data?.filter(
                    (u: R) => u.role === "psychologist" && u.active,
                  ) || []
                }
              />
              <Input
                label="Canal de contacto del responsable"
                name="guardian_channel"
                required={false}
                placeholder="Correo o referencia de entrega institucional"
              />
              <label className="p-check">
                <input type="checkbox" name="minor" defaultChecked /> Requiere
                autorización de responsable y asentimiento
              </label>
              <label className="p-check">
                <input type="checkbox" name="is_test" defaultChecked />{" "}
                Identidad ficticia para evaluar el producto
              </label>
              <Note>
                Crear una cuenta real no habilita la captación del piloto.
              </Note>
            </Form>
          )}
        </Modal>
      )}
      {modal === "csv" && (
        <Modal title="Importar invitaciones por CSV" close={() => setModal("")}>
          <Form
            submit="Validar y crear invitaciones"
            task={(f) =>
              api(S + "/students/import", "POST", {
                csv: f.get("csv"),
                classroom_id: f.get("classroom_id"),
                psychologist_id: f.get("psychologist_id"),
                is_test: f.has("is_test"),
              })
            }
            done={(v) => {
              downloadJson(v, "invitaciones-privadas.json");
              list.refresh();
              setModal("");
            }}
          >
            <p>Hasta 100 filas. Se valida el lote completo antes de guardar.</p>
            <Select
              label="Aula"
              name="classroom_id"
              options={classes.data || []}
            />
            <Select
              label="Psicólogo"
              name="psychologist_id"
              options={
                accounts.data?.filter((u: R) => u.role === "psychologist") || []
              }
            />
            <label>
              Contenido CSV
              <textarea
                name="csv"
                required
                rows={8}
                placeholder={
                  "name,minor,guardian_channel\nEstudiante de prueba,true,Entrega presencial"
                }
              />
            </label>
            <label className="p-check">
              <input type="checkbox" name="is_test" defaultChecked /> Todas son
              cuentas ficticias de prueba
            </label>
          </Form>
        </Modal>
      )}
      {modal === "manage" && selected && (
        <Modal title={selected.display_name} close={() => setModal("")}>
          <StudentManagement
            student={selected}
            accounts={accounts.data || []}
            done={() => {
              list.refresh();
              setModal("");
            }}
          />
        </Modal>
      )}
    </>
  );
}
function StudentManagement({
  student,
  accounts,
  done,
}: {
  student: R;
  accounts: R[];
  done: () => void;
}) {
  const history = useData(
    S + "/students/" + student.participant_id + "/authorizations",
  );
  const [link, setLink] = useState<R | null>(null),
    [error, setError] = useState(""),
    [renewed, setRenewed] = useState<R | null>(null);
  return (
    <>
      <details><summary>Renovar acceso del estudiante</summary><p>Invalida los accesos anteriores y prepara una invitación nueva para la misma participación.</p><button className="p-secondary" onClick={async () => {try {setRenewed(await api(S+"/students/"+student.participant_id+"/access-link","POST",{}));} catch(e) {setError((e as Error).message);}}}>Generar nueva invitación</button>{renewed && <InvitationResult value={renewed} />}</details>
      <Form
        submit="Agregar profesional asignado"
        task={(f) =>
          api(
            S +
              "/students/" +
              student.participant_id +
              "/assign/" +
              f.get("user_id"),
            "POST",
            {},
          )
        }
        done={done}
      >
        <Select
          label="Profesional"
          name="user_id"
          options={accounts.filter((a) =>
            ["psychologist", "practitioner"].includes(a.role),
          )}
        />
      </Form>
      <h3>Historial de autorizaciones</h3>
      {history.data?.length ? (
        history.data.map((a: R) => (
          <div className="p-timeline-item" key={a.id}>
            <strong>
              {a.kind} · {a.version}
            </strong>
            <small>{stamp(a.created_at)}</small>
            <p>
              {a.detail.accepted === false
                ? "No aceptado"
                : a.detail.accepted
                  ? "Registrado"
                  : a.detail.action}
            </p>
          </div>
        ))
      ) : (
        <p>Aún no se registraron decisiones.</p>
      )}
      {student.minor && (
        <button
          className="p-secondary"
          onClick={async () => {
            try {
              setLink(
                await api(
                  S + "/students/" + student.participant_id + "/guardian-link",
                  "POST",
                  {},
                ),
              );
            } catch (e) {
              setError((e as Error).message);
            }
          }}
        >
          Generar nuevo enlace del responsable
        </button>
      )}
      {link && (
        <div className="p-note">
          <div>
            <p>Enlace: {location.origin + "/guardian?token=" + link.token}</p>
            <p>Código separado: {link.verification_code}</p>
          </div>
        </div>
      )}
      <ErrorMessage value={error} />
      <details className="p-danger-zone">
        <summary>Retirar participación y solicitar borrado</summary>
        <p>
          Detiene la captura, revoca los accesos del estudiante y encola el
          borrado. No elimina registros de otros estudiantes.
        </p>
        <button
          className="p-danger"
          onClick={async () => {
            try {
              await api(
                S + "/students/" + student.participant_id + "/withdraw",
                "POST",
                {},
              );
              done();
            } catch (e) {
              setError((e as Error).message);
            }
          }}
        >
          Confirmar retirada
        </button>
      </details>
    </>
  );
}
function Administration({ me }: { me: R }) {
  const classes = useData(S + "/classrooms"),
    accounts = useData(S + "/accounts"),
    channels = useData(me.role === "admin" ? S + "/channels" : null);
  const [tab, setTab] = useState("classrooms"),
    [modal, setModal] = useState(false),
    [manageAccount, setManageAccount] = useState<R | null>(null),
    [accountError, setAccountError] = useState("");
  return (
    <>
      <PageTitle eyebrow="ORGANIZACIÓN ESCOLAR" title="Administración">
        <button className="p-primary" onClick={() => setModal(true)}>
          <Plus size={17} />{" "}
          {tab === "accounts" ? "Crear cuenta" : "Crear aula"}
        </button>
      </PageTitle>
      <div className="p-tabs p-tabs-outside">
        <button
          className={tab === "classrooms" ? "active" : ""}
          onClick={() => setTab("classrooms")}
        >
          Aulas y períodos
        </button>
        {me.role === "admin" && (
          <button
            className={tab === "accounts" ? "active" : ""}
            onClick={() => setTab("accounts")}
          >
            Equipo y permisos
          </button>
        )}
      </div>
      <section className="p-card">
        {tab === "classrooms" ? (
          classes.data?.length ? (
            <div className="p-class-grid">
              {classes.data.map((c: R) => (
                <article className="p-class-card" key={c.id}>
                  <GraduationCap size={29} />
                  <h3>{c.name}</h3>
                  <p>
                    {c.grade} · {c.period}
                  </p>
                  <Link to="/school/students">
                    Gestionar estudiantes <ArrowRight size={16} />
                  </Link>
                </article>
              ))}
            </div>
          ) : (
            <Empty title="Organiza el primer grupo">
              Registra el grado, sección y período académico para comenzar las
              invitaciones.
            </Empty>
          )
        ) : (
          <div className="p-table-wrap">
            <table className="p-table">
              <thead>
                <tr>
                  <th>Cuenta</th>
                  <th>Rol</th>
                  <th>Permisos específicos</th>
                  <th>Estado</th>
                </tr>
              </thead>
              <tbody>
                {accounts.data?.map((u: R) => (
                  <tr key={u.id}>
                    <td>{u.username}</td>
                    <td>{roleNames[u.role]}</td>
                    <td>{u.scopes.join(", ") || "Según rol y asignación"}</td>
                    <td>{u.active ? "Activa" : "Desactivada"}{me.role === "admin" && u.active && <button className="p-link" onClick={() => setManageAccount(u)}>Gestionar cuenta</button>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <ErrorMessage value={classes.error || accounts.error} />
      </section>
      <ErrorMessage value={accountError} />
      {manageAccount && <Modal title={"Cuenta: " + manageAccount.username} close={() => setManageAccount(null)}><Form submit="Cambiar contraseña y revocar sesiones" task={f => api(S+"/accounts/"+manageAccount.id+"/password","POST",{password:f.get("password")})} done={() => {accounts.refresh();setManageAccount(null);}}><Input label="Nueva contraseña" name="password" type="password" minLength={12} autoComplete="new-password" /><p>Entregar individualmente por un canal institucional verificado.</p></Form>{manageAccount.id !== me.id && <details className="p-danger-zone"><summary>Desactivar cuenta</summary><button className="p-danger" onClick={async () => {try {await api(S+"/accounts/"+manageAccount.id+"/disable","POST",{});accounts.refresh();setManageAccount(null);} catch(e){setAccountError((e as Error).message);}}}>Confirmar desactivación</button></details>}</Modal>}
      {me.role === "admin" && (
        <section className="p-card">
          <header>
            <h2>Canales de comunicación</h2>
            <Bell size={20} />
          </header>
          <div className="p-channel-grid">
            <div>
              <strong>Bandeja del producto</strong>
              <Tag tone="teal">Disponible</Tag>
              <p>Los avisos se guardan con cada caso.</p>
            </div>
            <div>
              <strong>Push al dispositivo</strong>
              <Tag>
                {channels.data?.push === "configured"
                  ? "Configurado"
                  : "Requiere credenciales FCM"}
              </Tag>
              <p>
                Los mensajes externos permanecen apagados hasta registrar
                configuración y autorización.
              </p>
            </div>
            <div>
              <strong>Invitaciones individuales</strong>
              <Tag>Entrega por operador</Tag>
              <p>
                Enlace y código separados; sin afirmar que un correo fue
                entregado.
              </p>
            </div>
          </div>
        </section>
      )}
      {modal && (
        <Modal
          title={
            tab === "accounts" ? "Crear una cuenta del equipo" : "Crear aula"
          }
          close={() => setModal(false)}
        >
          {tab === "classrooms" ? (
            <Form
              task={(f) =>
                api(S + "/classrooms", "POST", Object.fromEntries(f))
              }
              done={() => {
                classes.refresh();
                setModal(false);
              }}
              submit="Crear aula"
            >
              <Input
                label="Nombre de sección"
                name="name"
                placeholder="3.° A"
              />
              <Input
                label="Grado o nivel"
                name="grade"
                placeholder="Tercero de secundaria"
              />
              <Input label="Período académico" name="period" value="2026" />
            </Form>
          ) : (
            <Form
              task={(f) =>
                api(S + "/accounts", "POST", {
                  username: f.get("username"),
                  password: f.get("password"),
                  role: f.get("role"),
                  supervisor_id: f.get("supervisor_id") || null,
                  scopes: f.getAll("scopes"),
                })
              }
              done={() => {
                accounts.refresh();
                setModal(false);
              }}
              submit="Crear cuenta"
            >
              <Input label="Usuario" name="username" />
              <Input
                label="Contraseña inicial (mínimo 12 caracteres)"
                name="password"
                type="password"
                minLength={12}
                autoComplete="new-password"
              />
              <Select
                label="Rol"
                name="role"
                options={Object.entries(roleNames).map(([id, name]) => ({
                  id,
                  name,
                }))}
              />
              <Select
                label="Supervisor (para practicantes)"
                name="supervisor_id"
                required={false}
                options={
                  accounts.data?.filter((u: R) => u.role === "psychologist") ||
                  []
                }
              />
              <div>
                <strong>
                  Permisos técnicos para administración/investigación
                </strong>
                {[
                  ["diagnostics", "Diagnóstico de datos"],
                  ["raw_location", "Ubicación cruda autorizada"],
                  ["models", "Administración de modelos"],
                  ["raw_export", "Exportaciones técnicas"],
                ].map(([value, label]) => (
                  <label className="p-check" key={value}>
                    <input name="scopes" type="checkbox" value={value} />
                    {label}
                  </label>
                ))}
              </div>
            </Form>
          )}
        </Modal>
      )}
    </>
  );
}
function Trend({
  title,
  rows,
  selected,
}: {
  title: string;
  rows: R[];
  selected: string;
}) {
  const values = rows.map((r) => ({
    day: r.day,
    value: (r.features || r.detail?.features)?.[selected]?.value ?? null,
  }));
  const any = values.some((r) => r.value !== null);
  return (
    <section className="p-card p-chart">
      <header>
        <h2>{title}</h2>
        <Tag>{fields[selected]}</Tag>
      </header>
      {any ? (
        <>
          <div style={{ height: 230 }} role="img" aria-label={title}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={values}>
                <CartesianGrid
                  strokeDasharray="3 4"
                  vertical={false}
                  stroke="#e1eaee"
                />
                <XAxis
                  dataKey="day"
                  tickFormatter={(v) => v.slice(5)}
                  tick={{ fontSize: 11 }}
                />
                <YAxis tick={{ fontSize: 11 }} width={40} />
                <Tooltip />
                <Line
                  type="monotone"
                  dataKey="value"
                  name={fields[selected]}
                  stroke="#0b8f8d"
                  strokeWidth={2.5}
                  dot={false}
                  isAnimationActive={false}
                  connectNulls={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <details>
            <summary>Ver valores y calidad</summary>
            <div className="p-table-wrap">
              <table className="p-table">
                <thead>
                  <tr>
                    <th>Día</th>
                    <th>Valor</th>
                    <th>Calidad</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.slice(-60).map((r, i) => {
                    const f = (r.features || r.detail?.features)?.[selected];
                    return (
                      <tr key={i}>
                        <td>{r.day}</td>
                        <td>
                          {f?.value ?? "Sin datos"} {f?.unit}
                        </td>
                        <td>
                          {labels[f?.state] || f?.state || "No disponible"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </details>
        </>
      ) : (
        <Empty title="Estamos construyendo tu referencia">
          Se necesitan días observados para mostrar una evolución. Los datos
          ausentes no se convierten en cero.
        </Empty>
      )}
    </section>
  );
}
function ProfileContent({ data }: { data: R }) {
  const [variable, setVariable] = useState("observed_distance_m");
  return (
    <>
      <div className="p-columns">
        <Trend
          title="Uso nocturno del teléfono"
          rows={data.features || []}
          selected="night_interactive_minutes"
        />
        <section className="p-card">
          <header>
            <h2>Cuestionarios recibidos</h2>
            <ClipboardList size={20} />
          </header>
          {data.questionnaires?.length ? (
            <div className="p-table-wrap">
              <table className="p-table">
                <thead>
                  <tr>
                    <th>Fecha</th>
                    <th>Instrumento</th>
                    <th>Puntaje</th>
                  </tr>
                </thead>
                <tbody>
                  {data.questionnaires.map((r: R) => (
                    <tr key={r.id}>
                      <td>{stamp(r.detail.applied_at)}</td>
                      <td>
                        {r.detail.instrument_code?.startsWith("PHQ")
                          ? "PHQ-9"
                          : r.detail.instrument_code}
                        <small>{r.detail.instrument_version}</small>
                      </td>
                      <td>
                        <strong>{r.detail.total}</strong> / 27
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <Empty title="Todavía no hay respuestas">
              El cuestionario aparecerá cuando se complete la incorporación y el
              equipo lo habilite.
            </Empty>
          )}
          <p className="p-muted">
            El PHQ-9 orienta la revisión profesional; no establece un
            diagnóstico automático.
          </p>
        </section>
      </div>
      <div className="p-toolbar p-mobility-select">
        <h2>Movilidad y actividad observadas</h2>
        <label>
          Variable
          <select
            value={variable}
            onChange={(e) => setVariable(e.target.value)}
          >
            {[
              "observed_distance_m",
              "radius_gyration_m",
              "home_minutes",
              "place_entropy",
              "observed_steps",
            ].map((v) => (
              <option value={v} key={v}>
                {fields[v]}
              </option>
            ))}
          </select>
        </label>
      </div>
      <Trend
        title="Evolución personal"
        rows={data.mobility || []}
        selected={variable}
      />
      <section className="p-card">
        <header>
          <h2>Referencia personal y cambios</h2>
          <Activity size={20} />
        </header>
        {data.evaluations?.some((e: R) => e.detail.eligible) ? (
          data.evaluations
            .filter((e: R) => e.detail.eligible)
            .slice(0, 2)
            .map((e: R) => (
              <div key={e.id}>
                <p>
                  Datos hasta {e.cutoff} · {e.detail.current_start} a{" "}
                  {e.detail.current_end}
                </p>
                <div className="p-table-wrap">
                  <table className="p-table">
                    <thead>
                      <tr>
                        <th>Variable</th>
                        <th>Referencia</th>
                        <th>Actual</th>
                        <th>Cambio</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(e.detail.features).map(
                        ([k, v]: any) =>
                          v.state === "available" && (
                            <tr key={k}>
                              <td>{fields[k] || k}</td>
                              <td>{Number(v.baseline).toFixed(1)}</td>
                              <td>{Number(v.current).toFixed(1)}</td>
                              <td>
                                {v.delta > 0 ? "+" : ""}
                                {Number(v.delta).toFixed(1)}
                              </td>
                            </tr>
                          ),
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            ))
        ) : (
          <Empty title="Estamos construyendo tu referencia">
            La comparación usa el historial de esta persona, nunca un ranking
            entre compañeros.
          </Empty>
        )}
      </section>
      {data.predictions?.length > 0 && (
        <section className="p-card">
          <header>
            <h2>Estimaciones para revisión</h2>
            <Tag>Versión autorizada por el responsable</Tag>
          </header>
          {data.predictions.slice(0, 3).map((p: R) => (
            <details key={p.id}>
              <summary>
                {p.cutoff} · {Number(p.detail.estimate).toFixed(1)} puntos PHQ-9
                estimados
              </summary>
              <p>Contribuciones al resultado del modelo, no causas.</p>
              <ul>
                {Object.entries(p.detail.shap.contributions)
                  .sort((a: any, b: any) => Math.abs(b[1]) - Math.abs(a[1]))
                  .slice(0, 8)
                  .map(([k, v]: any) => (
                    <li key={k}>
                      {k}: {Number(v).toFixed(3)} puntos
                    </li>
                  ))}
              </ul>
            </details>
          ))}
        </section>
      )}
    </>
  );
}
function StudentProfilePage({ id }: { id: string }) {
  const d = useData(S + "/students/" + id + "/profile");
  return (
    <>
      <Link className="p-back" to="/school/students">
        ← Estudiantes
      </Link>
      <PageTitle
        eyebrow="HISTORIA Y CONTEXTO PERSONAL"
        title={d.data?.student.display_name || "Perfil del estudiante"}
      />
      {d.data?.student.is_test && <Tag tone="amber">Cuenta de prueba</Tag>}
      <ErrorMessage value={d.error} />
      {d.data && <ProfileContent data={d.data} />}
    </>
  );
}
function FollowupForm({ caseId, done }: { caseId: string; done: () => void }) {
  return (
    <Form
      submit="Guardar próximo paso"
      task={(f) =>
        api(S + "/followups", "POST", {
          case_id: caseId,
          title: f.get("title"),
          kind: f.get("kind"),
          due_at: new Date(String(f.get("due_at"))).toISOString(),
          location: f.get("location"),
        })
      }
      done={done}
    >
      <Select
        label="Tipo de seguimiento"
        name="kind"
        options={[
          { id: "task", name: "Tarea del equipo" },
          { id: "appointment", name: "Cita con el estudiante" },
        ]}
        value="appointment"
      />
      <Input
        label="Próxima acción (privada para el equipo)"
        name="title"
        placeholder="Acordar un primer encuentro"
      />
      <Input label="Fecha y hora" name="due_at" type="datetime-local" />
      <Input
        label="Lugar de la cita (visible al estudiante)"
        name="location"
        required={false}
        placeholder="Área de psicología"
      />
      <Note>
        El estudiante recibe una invitación genérica a la cita. Las notas del
        equipo permanecen privadas.
      </Note>
    </Form>
  );
}
function CasePage({ id }: { id: string }) {
  const d = useData("/psych/cases/" + id),
    p = useData(
      d.data && d.data.access_scope !== "escalation"
        ? S + "/students/" + d.data.participant_id + "/profile"
        : null,
    ),
    follow = useData(S + "/followups");
  const [modal, setModal] = useState(""),
    [tab, setTab] = useState("review"),
    [state, setState] = useState("");
  const refresh = () => {
    d.refresh();
    p.refresh();
    follow.refresh();
    setModal("");
  };
  const c = d.data;
  const next: R = {
    new: ["acknowledged", "closed"],
    acknowledged: ["contact_planned", "in_followup", "closed"],
    contact_planned: ["in_followup", "closed"],
    in_followup: ["closed"],
    closed: ["new"],
  };
  return (
    <>
      <Link className="p-back" to="/school/cases">
        ← Casos por revisar
      </Link>
      <PageTitle
        eyebrow="ACOMPAÑAMIENTO INDIVIDUAL"
        title={
          p.data?.student.display_name || c?.pseudonym || "Revisión del caso"
        }
      >
        <Tag tone="teal">{labels[c?.state] || "Cargando"}</Tag>
      </PageTitle>
      <ErrorMessage value={d.error} />
      {c?.access_scope === "escalation" && (
        <Note>
          {c.access_notice ||
            "Acceso de suplencia acotado a este caso. No incluye el perfil clínico completo ni otros casos del estudiante."}
        </Note>
      )}
      {c && (
        <>
          <div className="p-case-summary">
            <div className="p-tags">
              {c.reasons
                .filter((r: R) => r.active)
                .map((r: R) => (
                  <Tag
                    key={r.id}
                    tone={r.kind === "safety_review" ? "amber" : ""}
                  >
                    {reasons[r.kind] || r.kind}
                  </Tag>
                ))}
            </div>
            <p>
              {c.group} · Recibido {stamp(c.created_at)}
              {p.data?.student.is_test ? " · Cuenta de prueba" : ""}
            </p>
            <div className="p-inline">
              {(next[c.state] || []).map((s: string) => (
                <button
                  key={s}
                  className={s === "acknowledged" ? "p-primary" : "p-secondary"}
                  onClick={() => {
                    setState(s);
                    setModal("transition");
                  }}
                >
                  {s === "acknowledged"
                    ? "Reconocer revisión"
                    : s === "closed"
                      ? "Cerrar caso"
                      : s === "new"
                        ? "Reabrir caso"
                        : labels[s]}
                </button>
              ))}
              <button
                className="p-secondary"
                onClick={() => setModal("followup")}
              >
                <CalendarDays size={16} /> Próximo paso
              </button>
              {c.access_scope !== "escalation" && (
                <button
                  className="p-secondary"
                  onClick={() => setModal("report")}
                >
                  <Download size={16} /> Informe
                </button>
              )}
            </div>
          </div>
          <div className="p-tabs p-tabs-outside">
            <button
              className={tab === "review" ? "active" : ""}
              onClick={() => setTab("review")}
            >
              Revisión y contexto
            </button>
            <button
              className={tab === "history" ? "active" : ""}
              onClick={() => setTab("history")}
            >
              Notas e historial
            </button>
            <button
              className={tab === "followups" ? "active" : ""}
              onClick={() => setTab("followups")}
            >
              Seguimientos
            </button>
          </div>
          {tab === "review" && (
            <>
              <section className="p-card">
                <header>
                  <h2>Por qué se propone esta revisión</h2>
                  <HeartHandshake size={20} />
                </header>
                {c.reasons.map((r: R) => (
                  <article className="p-evidence" key={r.id}>
                    <span className="p-evidence-dot" />
                    <div>
                      <h3>{reasons[r.kind] || r.kind}</h3>
                      <p>
                        {r.kind === "safety_review"
                          ? "Se recibió una respuesta relevante al ítem 9. Corresponde realizar una valoración profesional, independientemente del total y del modelo."
                          : r.kind === "contact_request"
                            ? "El estudiante solicitó apoyo. No necesita un puntaje alto para recibir acompañamiento."
                            : r.kind === "questionnaire_review"
                              ? `El cuestionario recibido propone revisión profesional. Puntaje registrado: ${r.detail.total}.`
                              : r.kind === "behavior_change"
                                ? "Se observaron cambios persistentes respecto a su propio historial. Revisa las unidades y la calidad antes de interpretarlos."
                                : "Una versión autorizada del modelo propone revisión; contrasta la estimación con la información disponible."}
                      </p>
                      <small>{stamp(r.created_at)}</small>
                    </div>
                  </article>
                ))}
              </section>
              {p.data && <ProfileContent data={p.data} />}
            </>
          )}
          {tab === "history" && (
            <div className="p-columns">
              <section className="p-card">
                <h2>Nota privada del equipo</h2>
                <Form
                  submit="Guardar nota"
                  task={(f) =>
                    api("/psych/cases/" + id + "/notes", "POST", {
                      text: f.get("text"),
                    })
                  }
                  done={d.refresh}
                >
                  <label>
                    Registro del seguimiento
                    <textarea
                      name="text"
                      required
                      minLength={1}
                      maxLength={2000}
                      rows={6}
                      placeholder="Registra el contexto y los acuerdos del contacto."
                    />
                  </label>
                  <p className="p-muted">
                    No es visible para estudiantes, dirección ni investigadores.
                  </p>
                </Form>
              </section>
              <section className="p-card">
                <h2>Historial del caso</h2>
                {c.events
                  .slice()
                  .reverse()
                  .map((e: R) => (
                    <div className="p-timeline-item" key={e.id}>
                      <strong>
                        {(
                          {
                            review_note: "Nota privada",
                            transition: "Cambio de estado",
                            evidence_added: "Evidencia recibida",
                            followup_created: "Próximo paso acordado",
                            followup_updated: "Seguimiento actualizado",
                            escalated_to_backup: "Aviso al suplente",
                            notification_created: "Aviso creado",
                          } as R
                        )[e.kind] || e.kind}
                      </strong>
                      <small>{stamp(e.created_at)}</small>
                      <p>
                        {e.detail.text ||
                          e.detail.reason ||
                          e.detail.outcome ||
                          (e.detail.state ? labels[e.detail.state] : "")}
                      </p>
                    </div>
                  ))}
              </section>
            </div>
          )}
          {tab === "followups" && (
            <section className="p-card">
              <h2>Próximos pasos</h2>
              <FollowupRows
                rows={(follow.data || []).filter((f: R) => f.case_id === id)}
                refresh={follow.refresh}
              />
            </section>
          )}
        </>
      )}
      {modal === "transition" && (
        <Modal
          title={
            state === "closed" ? "Cerrar el caso" : "Registrar cambio de estado"
          }
          close={() => setModal("")}
        >
          <Form
            task={(f) =>
              api("/psych/cases/" + id + "/transitions", "POST", {
                state,
                version: c.version,
                reason: f.get("reason"),
              })
            }
            done={refresh}
            submit="Confirmar y registrar"
          >
            <label>
              Motivo y siguiente acción
              <textarea
                name="reason"
                required
                minLength={3}
                maxLength={1000}
                rows={4}
              />
            </label>
          </Form>
        </Modal>
      )}
      {modal === "followup" && (
        <Modal title="Acordar un próximo paso" close={() => setModal("")}>
          <FollowupForm caseId={id} done={refresh} />
        </Modal>
      )}
      {modal === "report" && (
        <Modal title="Informe individual autorizado" close={() => setModal("")}>
          <ReportDownload id={c.participant_id} />
        </Modal>
      )}
    </>
  );
}
function ReportDownload({ id }: { id: string }) {
  const [start, setStart] = useState(
      new Date(Date.now() - 60 * 86400000).toISOString().slice(0, 10),
    ),
    [end, setEnd] = useState(new Date().toISOString().slice(0, 10));
  return (
    <>
      <p>
        Incluye cuestionarios, resúmenes y acciones del período. Excluye
        coordenadas crudas. Se descarga un documento imprimible que puedes
        guardar como PDF.
      </p>
      <div className="p-form">
        <label>
          Desde
          <input
            type="date"
            value={start}
            onChange={(e) => setStart(e.target.value)}
          />
        </label>
        <label>
          Hasta
          <input
            type="date"
            value={end}
            onChange={(e) => setEnd(e.target.value)}
          />
        </label>
      </div>
      <a
        className="p-primary"
        href={
          "/api/v1/school/students/" +
          id +
          "/report?start=" +
          encodeURIComponent(start + "T00:00:00-05:00") +
          "&end=" +
          encodeURIComponent(end + "T23:59:59-05:00")
        }
      >
        <Download size={17} /> Descargar informe privado
      </a>
    </>
  );
}
function FollowupRows({ rows, refresh }: { rows: R[]; refresh: () => void }) {
  const [selected, setSelected] = useState<R | null>(null);
  return (
    <>
      {rows.length ? (
        <div className="p-table-wrap">
          <table className="p-table">
            <thead>
              <tr>
                <th>Próxima acción</th>
                <th>Fecha</th>
                <th>Tipo</th>
                <th>Estado</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {rows.map((f) => (
                <tr key={f.id}>
                  <td>
                    <strong>{f.title}</strong>
                    <Link to={"/school/cases/" + f.case_id}>Abrir caso</Link>
                  </td>
                  <td>
                    {stamp(f.due_at)}
                    {new Date(f.due_at) < new Date() &&
                      ["pending", "confirmed"].includes(f.state) && (
                        <small className="p-overdue">Vencido</small>
                      )}
                  </td>
                  <td>{f.kind === "appointment" ? "Cita" : "Tarea"}</td>
                  <td>
                    <Tag>{labels[f.state]}</Tag>
                  </td>
                  <td>
                    <button className="p-link" onClick={() => setSelected(f)}>
                      Actualizar
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <Empty title="Cada caso puede tener un próximo paso">
          Desde el caso, crea una tarea del equipo o acuerda una cita.
        </Empty>
      )}
      {selected && (
        <Modal title="Actualizar seguimiento" close={() => setSelected(null)}>
          <Form
            task={(f) =>
              api(S + "/followups/" + selected.id, "PUT", {
                state: f.get("state"),
                version: selected.version,
                contact_confirmed: f.has("contact_confirmed"),
                outcome: f.get("outcome"),
              })
            }
            done={() => {
              refresh();
              setSelected(null);
            }}
          >
            <Select
              label="Estado"
              name="state"
              value={selected.state}
              options={["pending", "confirmed", "completed", "cancelled"].map(
                (id) => ({ id, name: labels[id] }),
              )}
            />
            <label className="p-check">
              <input
                name="contact_confirmed"
                type="checkbox"
                defaultChecked={selected.detail.contact_confirmed}
              />{" "}
              Se confirmó contacto con el estudiante
            </label>
            <label>
              Resultado o acuerdo (privado)
              <textarea
                name="outcome"
                defaultValue={selected.detail.outcome || ""}
                rows={4}
              />
            </label>
          </Form>
        </Modal>
      )}
    </>
  );
}
function Followups() {
  const d = useData(S + "/followups", 15000);
  return (
    <>
      <PageTitle
        eyebrow="ACUERDOS QUE SE CONVIERTEN EN ACCIONES"
        title="Seguimientos"
      />
      <ErrorMessage value={d.error} />
      <section className="p-card">
        <FollowupRows rows={d.data || []} refresh={d.refresh} />
      </section>
    </>
  );
}
function Calendar({ me }: { me: R }) {
  const d = useData(S + "/calendar"),
    classes = useData(S + "/classrooms"),
    follow = useData(
      ["psychologist", "practitioner"].includes(me.role)
        ? S + "/followups"
        : null,
    );
  const [modal, setModal] = useState(false),
    [eventError, setEventError] = useState(""),
    [selectedClass, setSelectedClass] = useState("");
  const cohort = useData(
    selectedClass ? S + "/cohort-summary/" + selectedClass : null,
  );
  const canEdit = ["admin", "director", "psychologist"].includes(me.role);
  return (
    <>
      <PageTitle eyebrow="EL CONTEXTO TAMBIÉN IMPORTA" title="Calendario">
        {canEdit && (
          <button className="p-primary" onClick={() => setModal(true)}>
            <Plus size={17} /> Agregar evento
          </button>
        )}
      </PageTitle>
      <div className="p-columns">
        <section className="p-card">
          <header>
            <h2>Actividades escolares</h2>
            <CalendarDays size={22} />
          </header>
          <ErrorMessage value={d.error || eventError} />
          {d.data?.length ? (
            d.data.map((e: R) => (
              <div key={e.id} className="p-event">
                <div className="p-event-date">
                  {new Date(e.start_at).getDate()}
                  <small>
                    {new Date(e.start_at).toLocaleString("es-PE", {
                      month: "short",
                    })}
                  </small>
                </div>
                <div>
                  <strong>{e.title}</strong>
                  <p>
                    {stamp(e.start_at)} — {stamp(e.end_at)}
                  </p>
                  <Tag>
                    {
                      (
                        {
                          exam: "Exámenes",
                          vacation: "Vacaciones",
                          school: "Actividad escolar",
                          schedule: "Horario",
                        } as R
                      )[e.kind]
                    }
                  </Tag>
                  {canEdit && <details><summary>Modificar calendario</summary><button className="p-link" onClick={async()=>{try{await api(S+"/calendar/"+e.id,"DELETE");d.refresh();}catch(error){setEventError((error as Error).message);}}}>Eliminar evento</button></details>}
                </div>
              </div>
            ))
          ) : (
            <Empty title="Agrega contexto al calendario">
              Exámenes, vacaciones y horarios ayudan a interpretar el período
              sin descartar casos automáticamente.
            </Empty>
          )}
        </section>
        <section className="p-card">
          <header>
            <h2>Citas y próximas acciones</h2>
            <Clock3 size={20} />
          </header>
          {follow.data?.length ? (
            follow.data
              .filter((f: R) => ["pending", "confirmed"].includes(f.state))
              .slice(0, 8)
              .map((f: R) => (
                <Link
                  key={f.id}
                  className="p-calendar-task"
                  to={"/school/cases/" + f.case_id}
                >
                  <strong>{f.title}</strong>
                  <span>{stamp(f.due_at)}</span>
                  <Tag>{labels[f.state]}</Tag>
                </Link>
              ))
          ) : (
            <Empty title="Aquí aparecerán los acuerdos">
              Las citas se crean desde el caso del estudiante y conservan su
              estado de confirmación.
            </Empty>
          )}
        </section>
      </div>
      {canEdit && (
        <section className="p-card">
          <h2>Disponibilidad agregada por aula</h2>
          <label className="p-form">
            Aula
            <select
              value={selectedClass}
              onChange={(e) => setSelectedClass(e.target.value)}
            >
              <option value="">Seleccionar…</option>
              {classes.data?.map((c: R) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
          {cohort.data && (
            <Note>
              {cohort.data.available
                ? `${cohort.data.participants_with_data} participantes con datos en los últimos ${cohort.data.period_days} días. ${cohort.data.notice}`
                : cohort.data.message}
            </Note>
          )}
          <ErrorMessage value={cohort.error} />
        </section>
      )}
      {modal && (
        <Modal title="Nuevo evento escolar" close={() => setModal(false)}>
          <Form
            task={(f) =>
              api(S + "/calendar", "POST", {
                title: f.get("title"),
                kind: f.get("kind"),
                classroom_id: f.get("classroom_id") || null,
                start_at: new Date(String(f.get("start_at"))).toISOString(),
                end_at: new Date(String(f.get("end_at"))).toISOString(),
              })
            }
            done={() => {
              d.refresh();
              setModal(false);
            }}
            submit="Guardar evento"
          >
            <Input label="Nombre del evento" name="title" />
            <Select
              label="Tipo"
              name="kind"
              options={[
                { id: "exam", name: "Exámenes" },
                { id: "vacation", name: "Vacaciones" },
                { id: "school", name: "Actividad escolar" },
                { id: "schedule", name: "Horario general" },
              ]}
            />
            <Select
              label="Aula (vacío para toda la institución)"
              name="classroom_id"
              options={classes.data || []}
              required={false}
            />
            <Input label="Inicio" name="start_at" type="datetime-local" />
            <Input label="Fin" name="end_at" type="datetime-local" />
          </Form>
        </Modal>
      )}
    </>
  );
}
function SchoolSettings({ onSaved }: { onSaved: () => void }) {
  const d = useData(S + "/settings"),
    accounts = useData(S + "/accounts");
  const [resources, setResources] = useState<R[]>([]);
  useEffect(() => {
    if (d.data) setResources(d.data.resources || []);
  }, [d.data]);
  if (!d.data)
    return (
      <>
        <ErrorMessage value={d.error} />
        <Empty title="Cargando configuración…" />
      </>
    );
  const cfg = d.data;
  return (
    <>
      <PageTitle
        eyebrow="RESPONSABILIDADES, INFORMACIÓN Y COBERTURA"
        title="Configuración escolar"
      />
      <Note>
        El piloto real permanece{" "}
        {cfg.pilot_enabled
          ? "habilitado según la configuración del servidor"
          : "apagado"}
        . Registrar estas decisiones prepara el producto; no sustituye las
        autorizaciones individuales.
      </Note>
      <Form
        submit="Guardar configuración escolar"
        task={(f) =>
          api(S + "/settings", "PUT", {
            document_version: f.get("document_version"),
            participation_document: f.get("participation_document"),
            purpose: f.get("purpose"),
            primary_id: f.get("primary_id") || null,
            backup_id: f.get("backup_id") || null,
            coverage: f.get("coverage"),
            days: f.getAll("days").map(Number),
            opens: f.get("opens"),
            closes: f.get("closes"),
            acknowledgement_minutes: Number(f.get("acknowledgement_minutes")),
            safety_minutes: Number(f.get("safety_minutes")),
            escalation_minutes: Number(f.get("escalation_minutes")),
            resources: resources.map((r) => ({
              ...r,
              verified_at: new Date(r.verified_at).toISOString(),
            })),
            instrument_enabled: f.has("instrument_enabled"),
            professional_decision: f.get("professional_decision"),
            cadence_days: Number(f.get("cadence_days")),
            minimum_group: Number(f.get("minimum_group")),
            external_notifications_authorized: f.has(
              "external_notifications_authorized",
            ),
            raw_location_retention_days: Number(
              f.get("raw_location_retention_days"),
            ),
            location_interval_minutes: Number(
              f.get("location_interval_minutes"),
            ),
            location_distance_meters: Number(f.get("location_distance_meters")),
          })
        }
        done={() => {
          d.refresh();
          onSaved();
        }}
      >
        <section className="p-card">
          <header>
            <h2>
              <span className="p-step">1</span> Equipo responsable y horarios
            </h2>
          </header>
          <div className="p-form-grid">
            <Select
              label="Psicólogo responsable"
              name="primary_id"
              value={cfg.primary_id}
              options={
                accounts.data?.filter(
                  (u: R) => u.role === "psychologist" && u.active,
                ) || []
              }
              required={false}
            />
            <Select
              label="Psicólogo suplente"
              name="backup_id"
              value={cfg.backup_id}
              options={
                accounts.data?.filter(
                  (u: R) => u.role === "psychologist" && u.active,
                ) || []
              }
              required={false}
            />
          </div>
          <label>
            Información de cobertura que verá el estudiante
            <textarea
              name="coverage"
              defaultValue={cfg.coverage}
              required
              minLength={5}
              rows={3}
            />
          </label>
          <div className="p-weekdays">
            {["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"].map((v, n) => (
              <label key={v}>
                <input
                  type="checkbox"
                  name="days"
                  value={n}
                  defaultChecked={cfg.days.includes(n)}
                />
                {v}
              </label>
            ))}
          </div>
          <div className="p-form-grid">
            <Input
              label="Inicio de atención"
              name="opens"
              type="time"
              value={cfg.opens}
            />
            <Input
              label="Fin de atención"
              name="closes"
              type="time"
              value={cfg.closes}
            />
          </div>
          <div className="p-form-grid three">
            <Input
              label="Reconocimiento habitual (minutos)"
              name="acknowledgement_minutes"
              type="number"
              min={5}
              max={10080}
              value={cfg.acknowledgement_minutes}
            />
            <Input
              label="Revisión de seguridad (minutos)"
              name="safety_minutes"
              type="number"
              min={5}
              max={1440}
              value={cfg.safety_minutes}
            />
            <Input
              label="Escalamiento al responsable (minutos)"
              name="escalation_minutes"
              type="number"
              min={5}
              max={1440}
              value={cfg.escalation_minutes}
            />
          </div>
        </section>
        <section className="p-card">
          <header>
            <h2>
              <span className="p-step">2</span> Recursos de apoyo verificados
            </h2>
            <button
              type="button"
              className="p-secondary"
              onClick={() =>
                setResources([
                  ...resources,
                  {
                    title: "",
                    contact: "",
                    verified_by: "",
                    verified_at: new Date().toISOString(),
                  },
                ])
              }
            >
              <Plus size={16} /> Agregar recurso
            </button>
          </header>
          <p>
            Registra únicamente canales y horarios comprobados por el equipo. Se
            conservarán en el teléfono para consulta sin conexión.
          </p>
          {resources.map((r, n) => (
            <div className="p-resource-form" key={n}>
              <div className="p-form-grid">
                {[
                  ["title", "Nombre del recurso"],
                  ["contact", "Contacto e indicación de uso"],
                  ["verified_by", "Verificado por"],
                ].map(([k, l]) => (
                  <label key={k}>
                    {l}
                    <input
                      required
                      value={r[k]}
                      onChange={(e) =>
                        setResources(
                          resources.map((v, j) =>
                            j === n ? { ...v, [k]: e.target.value } : v,
                          ),
                        )
                      }
                    />
                  </label>
                ))}
                <label>
                  Fecha de verificación
                  <input
                    type="date"
                    required
                    value={r.verified_at.slice(0, 10)}
                    onChange={(e) =>
                      setResources(
                        resources.map((v, j) =>
                          j === n ? { ...v, verified_at: e.target.value } : v,
                        ),
                      )
                    }
                  />
                </label>
              </div>
              <button
                type="button"
                className="p-link"
                onClick={() =>
                  setResources(resources.filter((_, j) => j !== n))
                }
              >
                Quitar recurso
              </button>
            </div>
          ))}
        </section>
        <section className="p-card">
          <header>
            <h2>
              <span className="p-step">3</span> Instrumento y decisión
              profesional
            </h2>
            <Tag tone="teal">PHQ-9 estándar · español</Tag>
          </header>
          <p>
            Nueve preguntas, recuerdo de dos semanas y puntaje de 0 a 27. La
            pregunta de funcionamiento se registra aparte. Una respuesta al ítem
            9 mayor que cero genera revisión independiente.
          </p>
          <a
            href="https://aidsetc.org/sites/default/files/resources_files/PHQ-9_Spanish.pdf"
            target="_blank"
            rel="noreferrer"
          >
            Consultar versión institucional y puntuación
          </a>
          <details>
            <summary>Ver el contenido integrado</summary>
            <p>{cfg.instrument.recall}</p>
            <ol>
              {cfg.instrument.questions.map((q: R) => (
                <li key={q.id}>{q.text}</li>
              ))}
            </ol>
            <p>{cfg.instrument.notice}</p>
          </details>
          <label>
            Decisión del profesional sobre versión, población y organización
            <textarea
              name="professional_decision"
              rows={3}
              defaultValue={cfg.professional_decision}
              placeholder="Registre la revisión y decisión profesional; no presuponga validación para el colegio."
            />
          </label>
          <Input
            label="Cadencia del cuestionario (días, mínimo 14)"
            name="cadence_days"
            type="number"
            min={14}
            max={90}
            value={cfg.cadence_days}
          />
          <label className="p-check">
            <input
              type="checkbox"
              name="instrument_enabled"
              defaultChecked={cfg.instrument_enabled}
            />{" "}
            Habilitar el cuestionario para participantes autorizados
          </label>
        </section>
        <section className="p-card">
          <header>
            <h2>
              <span className="p-step">4</span> Información de participación y
              datos
            </h2>
          </header>
          <Input
            label="Versión del documento"
            name="document_version"
            value={cfg.document_version}
          />
          <label>
            Finalidad comunicada
            <textarea
              name="purpose"
              required
              minLength={10}
              defaultValue={cfg.purpose}
            />
          </label>
          <label>
            Documento de información y participación
            <textarea
              name="participation_document"
              rows={6}
              required
              minLength={30}
              defaultValue={cfg.participation_document}
            />
          </label>
          <p className="p-muted">
            Cambiar finalidad o documento requiere una versión nueva y renovar
            las autorizaciones. La captura se pausa hasta completarlas.
          </p>
          <div className="p-form-grid">
            <Input
              label="Mínimo de participantes para agregados"
              name="minimum_group"
              type="number"
              min={5}
              max={100}
              value={cfg.minimum_group}
            />
            <Input
              label="Retención de coordenadas autorizadas (días)"
              name="raw_location_retention_days"
              type="number"
              min={1}
              max={7}
              value={cfg.raw_location_retention_days}
            />
            <Input
              label="Intervalo solicitado de ubicación (minutos)"
              name="location_interval_minutes"
              type="number"
              min={5}
              max={120}
              value={cfg.location_interval_minutes}
            />
            <Input
              label="Desplazamiento solicitado (metros)"
              name="location_distance_meters"
              type="number"
              min={20}
              max={1000}
              value={cfg.location_distance_meters}
            />
          </div>
          <p className="p-muted">
            Android decide los intervalos reales según permisos, batería y
            estado del dispositivo.
          </p>
          <label className="p-check">
            <input
              type="checkbox"
              name="external_notifications_authorized"
              defaultChecked={cfg.external_notifications_authorized}
            />{" "}
            Autorizar canales externos configurados para avisos genéricos
          </label>
        </section>
      </Form>
    </>
  );
}
function Inbox({ data }: { data: ReturnType<typeof useData> }) {
  const [error, setError] = useState("");
  return (
    <>
      <PageTitle eyebrow="AVISOS CON ESTADO Y CONTINUIDAD" title="Tu bandeja" />
      <ErrorMessage value={data.error || error} />
      <section className="p-card">
        {data.data?.length ? (
          data.data.map((n: R) => (
            <article
              className={"p-inbox-item " + (n.acknowledged_at ? "" : "unread")}
              key={n.id}
            >
              <span className="p-inbox-icon">
                <Bell size={20} />
              </span>
              <div>
                <strong>{n.title}</strong>
                <p>
                  {stamp(n.created_at)} · {labels[n.state]}
                </p>
                {Object.entries(n.detail.channels || {}).map(([channel, raw]) => {
                  const state = raw as R;
                  const text = state.state === "accepted" ? "Aceptado por el proveedor; entrega no confirmada" : state.state === "retry_pending" ? "Reintento pendiente" : "No se confirmó envío";
                  return <small key={channel}>{channel === "email" ? "Correo" : "Push"}: {text} · {state.attempts} intento(s){state.state === "retry_pending" && state.next_attempt_at ? " · " + stamp(state.next_attempt_at) : ""}</small>;
                })}
                {n.detail.case_id && (
                  <Link to={"/school/cases/" + n.detail.case_id}>
                    Revisar caso <ArrowRight size={15} />
                  </Link>
                )}
              </div>
              {!n.acknowledged_at && (
                <button
                  className="p-secondary"
                  onClick={async () => {
                    try {
                      await api(
                        S + "/notifications/" + n.id + "/ack",
                        "POST",
                        {},
                      );
                      data.refresh();
                    } catch (e) {
                      setError((e as Error).message);
                    }
                  }}
                >
                  Reconocer
                </button>
              )}
            </article>
          ))
        ) : (
          <Empty title="No hay avisos pendientes">
            Los avisos del producto funcionan aunque no haya un canal push
            configurado.
          </Empty>
        )}
      </section>
    </>
  );
}
function Preferences() {
  const d = useData(S + "/preferences");
  return (
    <>
      <PageTitle
        eyebrow="TU MANERA DE ORGANIZAR EL DÍA"
        title="Configuración personal"
      />
      <section className="p-card">
        <ErrorMessage value={d.error} />
        {d.data && (
          <Form
            task={(f) =>
              api(S + "/preferences", "PUT", {
                display_name: f.get("display_name"),
                notification_email: f.get("notification_email"),
                reminder_time: f.get("reminder_time"),
                reminders: f.has("reminders"),
              })
            }
            done={d.refresh}
          >
            <Input
              label="Nombre para mostrar"
              name="display_name"
              value={d.data.display_name || ""}
              required={false}
            />
            <Input
              label="Correo para notificaciones (opcional)"
              name="notification_email"
              type="email"
              value={d.data.notification_email || ""}
              required={false}
            />
            <Input
              label="Hora preferida de recordatorio"
              name="reminder_time"
              type="time"
              value={d.data.reminder_time || "08:00"}
            />
            <label className="p-check">
              <input
                type="checkbox"
                name="reminders"
                defaultChecked={d.data.reminders !== false}
              />{" "}
              Recibir recordatorios del equipo
            </label>
          </Form>
        )}
      </section>
    </>
  );
}
function LocationPlot({ rows }: { rows: R[] }) {
  const [index, setIndex] = useState(0);
  const points = rows
    .map((r) => r.detail)
    .filter((r) => typeof r.latitude === "number");
  if (!points.length)
    return (
      <Empty title="No hay ubicaciones en este período">
        Solo se muestran coordenadas que la persona autorizó compartir.
      </Empty>
    );
  const anchor = points[0].longitude;
  const lon = (v: number) => anchor + ((v - anchor + 540) % 360) - 180;
  const xs = points.map((p) => lon(p.longitude)),
    ys = points.map((p) => p.latitude);
  const x0 = Math.min(...xs),
    x1 = Math.max(...xs),
    y0 = Math.min(...ys),
    y1 = Math.max(...ys);
  const x = (p: R) =>
      35 + ((lon(p.longitude) - x0) / Math.max(0.001, x1 - x0)) * 650,
    y = (p: R) => 275 - ((p.latitude - y0) / Math.max(0.001, y1 - y0)) * 240;
  const selected = points[Math.min(index, points.length - 1)];
  return (
    <div className="p-location-plot">
      <svg
        viewBox="0 0 720 320"
        role="img"
        aria-label="Mapa temporal de puntos geográficos autorizados"
      >
        <defs>
          <pattern
            id="geo-grid"
            width="40"
            height="40"
            patternUnits="userSpaceOnUse"
          >
            <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#dce9ec" />
          </pattern>
        </defs>
        <rect width="720" height="320" fill="url(#geo-grid)" />
        <polyline
          points={points.map((p) => `${x(p)},${y(p)}`).join(" ")}
          fill="none"
          stroke="#8bc3c2"
          strokeWidth="2"
          strokeDasharray="4 4"
        />
        {points.map((p, n) => (
          <circle
            key={n}
            cx={x(p)}
            cy={y(p)}
            r={n === index ? 8 : 3}
            fill={n === index ? "#ec9b34" : "#087f83"}
          >
            <title>
              {p.occurred_at} · ±{p.accuracy_m} m
            </title>
          </circle>
        ))}
        <text x="15" y="310" fill="#52717d" fontSize="11">
          Longitud {x0.toFixed(4)} a {x1.toFixed(4)} · Latitud {y0.toFixed(4)} a{" "}
          {y1.toFixed(4)}
        </text>
      </svg>
      <label>
        Recorrer en el tiempo
        <input
          type="range"
          min={0}
          max={points.length - 1}
          value={Math.min(index, points.length - 1)}
          onChange={(e) => setIndex(Number(e.target.value))}
        />
      </label>
      <p>
        {stamp(selected.occurred_at)} · {selected.latitude.toFixed(5)},{" "}
        {selected.longitude.toFixed(5)} · Precisión ±{selected.accuracy_m} m ·{" "}
        {selected.permission === "approximate" ? "Aproximada" : "Precisa"}
      </p>
      <p className="p-muted">
        Las líneas solo indican orden temporal, no un trayecto reconstruido. No
        se consultan mapas externos.{" "}
        {selected.mock
          ? "El sistema informó ubicación simulada; esto no implica fraude."
          : ""}
      </p>
    </div>
  );
}
function Diagnostics({me}: {me:R}) {
  const devices = useData(S + "/diagnostics/devices", 15000);
  const [selected, setSelected] = useState(""),
    [kind, setKind] = useState("usage"),
    [start, setStart] = useState(
      new Date(Date.now() - 7 * 86400000).toISOString().slice(0, 10),
    ),
    [end, setEnd] = useState(new Date().toISOString().slice(0, 10));
  const d = useData(
    selected
      ? S +
          "/diagnostics/" +
          selected +
          "?kind=" +
          kind +
          "&start=" +
          encodeURIComponent(start + "T00:00:00-05:00") +
          "&end=" +
          encodeURIComponent(end + "T23:59:59-05:00")
      : null,
  );
  const device = devices.data?.find((v: R) => v.id === selected);
  return (
    <>
      <PageTitle
        eyebrow="ADMINISTRACIÓN · ACCESO AUDITADO"
        title="Diagnóstico de datos"
      >{selected && kind !== "location" && me.scopes?.includes("raw_export") && <a className="p-secondary" href={"/api/v1/school/diagnostics/"+selected+"/export?kind="+kind+"&start="+encodeURIComponent(start+"T00:00:00-05:00")+"&end="+encodeURIComponent(end+"T23:59:59-05:00")}>Descargar extracto autorizado</a>}</PageTitle>
      <Note>
        Este espacio técnico está separado del seguimiento escolar. El mapa
        requiere permiso específico y autorización de acceso a coordenadas.
      </Note>
      <section className="p-card">
        <div className="p-form p-form-grid">
          <label>
            Dispositivo
            <select
              value={selected}
              onChange={(e) => {
                setSelected(e.target.value);
                setKind("usage");
              }}
            >
              <option value="">Seleccionar dispositivo…</option>
              {devices.data?.map((d: R) => (
                <option key={d.id} value={d.id}>
                  {d.display_name} · {d.detail.manufacturer} {d.detail.model}
                </option>
              ))}
            </select>
          </label>
          <label>
            Datos
            <select value={kind} onChange={(e) => setKind(e.target.value)}>
              <option value="usage">Eventos de uso</option>
              <option value="features">Resúmenes y trazabilidad</option>
              <option value="steps">Pasos</option>
              {device?.raw_location_available && (
                <option value="location">Ubicación cruda autorizada</option>
              )}
            </select>
          </label>
          <label>
            Desde
            <input
              type="date"
              value={start}
              onChange={(e) => setStart(e.target.value)}
            />
          </label>
          <label>
            Hasta
            <input
              type="date"
              value={end}
              onChange={(e) => setEnd(e.target.value)}
            />
          </label>
        </div>
        <ErrorMessage value={devices.error || d.error} />
        {device && (
          <div className="p-device-metadata">
            <Tag>
              {device.detail.manufacturer} {device.detail.model}
            </Tag>
            <Tag>Android API {device.detail.android_api}</Tag>
            <span>
              Última sincronización:{" "}
              {stamp(device.detail.last_sensor_sync || device.detail.last_sync)}
            </span>
            <span>
              Pendientes informados:{" "}
              {device.detail.outbox_pending ?? "Sin reporte"}
            </span>
          </div>
        )}
      </section>
      {selected && d.data && (
        <>
          <section className="p-card">
            <header>
              <h2>
                {kind === "location"
                  ? "Mapa temporal autorizado"
                  : "Registros del período"}
              </h2>
              <Tag>{d.data.rows.length} registros</Tag>
            </header>
            {kind === "location" ? (
              <LocationPlot rows={d.data.rows} />
            ) : d.data.rows.length ? (
              <div className="p-table-wrap">
                <table className="p-table">
                  <thead>
                    <tr>
                      <th>Fecha</th>
                      <th>Tipo / versión</th>
                      <th>Procedencia</th>
                      <th>Detalle</th>
                    </tr>
                  </thead>
                  <tbody>
                    {d.data.rows.map((r: R) => (
                      <tr key={r.id}>
                        <td>{r.day || stamp(r.occurred_at)}</td>
                        <td>{r.event_type || r.kind || r.version}</td>
                        <td>
                          {r.source ||
                            r.detail.source ||
                            "Contrato del dispositivo"}
                        </td>
                        <td>
                          <details>
                            <summary>Ver JSON</summary>
                            <pre>{JSON.stringify(r, null, 2)}</pre>
                          </details>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <Empty title="No hay registros en este período">
                Comprueba los permisos, la participación y la sincronización del
                dispositivo.
              </Empty>
            )}
          </section>
          <section className="p-card">
            <h2>Últimas consultas de uso</h2>
            {d.data.captures.length ? (
              d.data.captures.map((c: R) => (
                <details key={c.id}>
                  <summary>
                    {stamp(c.end_at)} ·{" "}
                    {c.detail.success
                      ? "Consulta completada"
                      : "Consulta incompleta"}
                  </summary>
                  <pre>{JSON.stringify(c, null, 2)}</pre>
                </details>
              ))
            ) : (
              <p>Todavía no se recibieron consultas del teléfono.</p>
            )}
          </section>
        </>
      )}
    </>
  );
}
const FEATURE_LABELS: R = {
  interactive_minutes: "Minutos interactivos",
  night_interactive_minutes: "Minutos interactivos nocturnos",
  interactive_session_count: "Sesiones interactivas",
  keyguard_hidden_count: "Desbloqueos",
  observed_distance_m: "Distancia observada (m)",
  radius_gyration_m: "Radio de giro (m)",
  home_minutes: "Minutos en casa",
  place_entropy: "Entropía de lugares",
  observed_steps: "Pasos observados",
};
function Models({ me }: { me: R }) {
  const d = useData(S + "/models", 5000);
  const schedule = useData(S + "/models/schedule", 15000);
  const [modal, setModal] = useState(""),
    [selected, setSelected] = useState<R | null>(null),
    [state, setState] = useState("shadow"),
    [error, setError] = useState(""),
    [preview, setPreview] = useState<R | null>(null),
    [buildSpec, setBuildSpec] = useState<R | null>(null),
    [predictions, setPredictions] = useState<R[]>([]);
  const technical = me.scopes?.includes("models") || me.role === "psychologist";
  return (
    <>
      {d.data?.analysis && !d.data.analysis.ready && <p role="status">Análisis esperando agregados: {d.data.analysis.pending_aggregates} pendientes y {d.data.analysis.failed_aggregates} fallidos.</p>}
      {d.data?.analysis?.failed_jobs?.map((j: R) => <Form key={j.id} task={() => api(S + "/models/aggregate-jobs/" + j.id + "/retry", "POST", {})} done={d.refresh}><p>Agregado fallido: {j.kind}</p><button type="submit">Reintentar agregado</button></Form>)}
      <PageTitle
        eyebrow="INVESTIGACIÓN Y DECISIONES REGISTRADAS"
        title="Modelos y evaluación"
      >
        {technical && (
          <div className="p-inline">
            <button className="p-secondary" onClick={() => setModal("weights")}>
              Importar versión
            </button>
            <button className="p-secondary" onClick={() => setModal("dataset")}>
              Importar dataset JSON
            </button>
            <button
              className="p-primary"
              onClick={() => {
                setPreview(null);
                setBuildSpec(null);
                setModal("build");
              }}
            >
              <Plus size={16} /> Construir dataset local
            </button>
          </div>
        )}
      </PageTitle>
      <ErrorMessage value={d.error || error} />
      {!d.data?.models.length && (
        <section className="p-card">
          <Empty title="Modelo pendiente de entrenamiento">
            El producto ya funciona con cuestionarios, solicitudes y resúmenes.
            Incorpora datos autorizados para entrenar y comparar una versión; no
            se generaron pesos ficticios.
          </Empty>
        </section>
      )}
      <section className="p-card">
        <header>
          <h2>Datasets y entrenamiento</h2>
          <Tag>PHQ-9 · ventanas verificadas</Tag>
        </header>
        {d.data?.datasets.length ? (
          d.data.datasets.map((r: R) => (
            <div className="p-model-row" key={r.id}>
              <div>
                <strong>{r.name}</strong>
                <p>
                  {r.manifest.task === "prospective"
                    ? "Prospectivo: sensores anteriores al período preguntado"
                    : "Contemporáneo: sensores del período preguntado"}
                </p>
                <div className="p-tags">
                  <Tag
                    tone={
                      r.manifest.provenance === "test_fixture" ? "amber" : "teal"
                    }
                  >
                    {r.manifest.provenance === "test_fixture"
                      ? "Solo pruebas · no activable"
                      : "Datos declarados autorizados"}
                  </Tag>
                  <Tag>
                    {r.manifest.source === "local_builder"
                      ? "Construido localmente"
                      : "Importado"}
                  </Tag>
                  {r.manifest.purpose && <Tag>{r.manifest.purpose}</Tag>}
                </div>
                {r.manifest.exclusions && (
                  <details>
                    <summary>
                      Procedencia y exclusiones (
                      {(r.manifest.exclusions.labels?.length || 0) +
                        (r.manifest.exclusions.participants?.length || 0) +
                        (r.manifest.exclusions.days?.length || 0)}
                      )
                    </summary>
                    <pre>
                      {JSON.stringify(
                        {
                          selection: r.manifest.selection,
                          exclusions: r.manifest.exclusions,
                          label_provenance_sample: Object.fromEntries(
                            Object.entries(
                              r.manifest.label_provenance || {},
                            ).slice(0, 3),
                          ),
                        },
                        null,
                        2,
                      )}
                    </pre>
                  </details>
                )}
              </div>
              {technical && (
                <button
                  className="p-secondary"
                  onClick={async () => {
                    try {
                      await api(
                        S + "/models/datasets/" + r.id + "/train",
                        "POST",
                        {},
                      );
                      d.refresh();
                    } catch (e) {
                      setError((e as Error).message);
                    }
                  }}
                >
                  Entrenar y evaluar
                </button>
              )}
            </div>
          ))
        ) : (
          <p>No se ha incorporado un dataset autorizado.</p>
        )}
      </section>
      {d.data?.models.map((r: R) => (
        <section className="p-card" key={r.id}>
          <header>
            <div>
              <h2>Versión {r.id.slice(0, 8)}</h2>
              <p>
                {stamp(r.created_at)} · {r.manifest.task} ·{" "}
                {r.manifest.labels ?? "—"} etiquetas
              </p>
            </div>
            <Tag>{labels[r.state]}</Tag>
          </header>
          <div className="p-table-wrap">
            <table className="p-table">
              <thead>
                <tr>
                  <th>Comparador</th>
                  <th>Error absoluto medio</th>
                  <th>RMSE</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(r.metrics).map(([name, v]: any) => (
                  <tr key={name}>
                    <td>
                      {(
                        {
                          constant: "Valor constante",
                          last_questionnaire: "Último cuestionario",
                          ridge: "Ridge",
                          xgboost: "XGBoost · niveles y cambios",
                          levels_only: "XGBoost · solo niveles",
                        } as R
                      )[name] || name}
                    </td>
                    <td>{Number(v.mae).toFixed(3)}</td>
                    <td>{Number(v.rmse).toFixed(3)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="p-muted">
            Errores en puntos PHQ-9; menor es mejor. La comparación funcional no
            demuestra validación clínica.
          </p>
          <details>
            <summary>Particiones, contrato y decisiones</summary>
            <pre>
              {JSON.stringify(
                { manifest: r.manifest, decisions: r.decisions },
                null,
                2,
              )}
            </pre>
          </details>
          <div className="p-inline">
            {["shadow", "active", "retired"].map((s) => (
              <button
                className="p-secondary"
                key={s}
                onClick={() => {
                  setSelected(r);
                  setState(s);
                  setModal("decision");
                }}
              >
                {s === "shadow"
                  ? "Ejecutar en sombra"
                  : s === "active"
                    ? "Activar / revertir a esta versión"
                    : "Retirar versión"}
              </button>
            ))}
            {["shadow", "active"].includes(r.state) && (
              <button
                className="p-secondary"
                onClick={async () => {
                  try {
                    await api(S + "/models/" + r.id + "/infer", "POST", {});
                    d.refresh();
                  } catch (e) {
                    setError((e as Error).message);
                  }
                }}
              >
                Procesar inferencia
              </button>
            )}
            <button
              className="p-link"
              onClick={async () => {
                try {
                  setPredictions(
                    await api(S + "/models/" + r.id + "/predictions"),
                  );
                  setSelected(r);
                  setModal("predictions");
                } catch (e) {
                  setError((e as Error).message);
                }
              }}
            >
              Ver estimaciones
            </button>
          </div>
        </section>
      ))}
      {technical && (
        <section className="p-card">
          <header>
            <h2>Programación controlada</h2>
            <Tag>{schedule.data?.enabled ? "Activa" : "Sin programar"}</Tag>
          </header>
          <p className="p-muted">
            {schedule.data?.note ||
              "La construcción y el reentrenamiento programados nunca activan un modelo."}
          </p>
          {schedule.data?.configured && (
            <p>
              Cada {schedule.data.cadence_days} días ·{" "}
              {schedule.data.auto_retrain
                ? "reentrena tras construir"
                : "solo construye el dataset"}{" "}
              · próxima: {stamp(schedule.data.next_run_at)}
              {schedule.data.last_run_at
                ? ` · última: ${stamp(schedule.data.last_run_at)}`
                : ""}
            </p>
          )}
          <button className="p-secondary" onClick={() => setModal("schedule")}>
            {schedule.data?.configured
              ? "Editar programación"
              : "Programar construcción y reentrenamiento"}
          </button>
        </section>
      )}
      <section className="p-card">
        <h2>Procesos reproducibles</h2>
        {d.data?.jobs.length ? (
          d.data.jobs.map((j: R) => (
            <div className="p-job" key={j.id}>
              <span>
                <strong>
                  {j.kind === "school_training"
                    ? "Entrenamiento y evaluación"
                    : j.kind === "school_dataset_build"
                      ? "Construcción de dataset local"
                      : "Inferencia de versión"}
                </strong>
                <small>{stamp(j.created_at)}</small>
              </span>
              <Tag>{labels[j.state]}</Tag>
              {j.result.message && <p>{j.result.message}</p>}
            </div>
          ))
        ) : (
          <p>Los procesos aparecerán al entrenar o ejecutar una versión.</p>
        )}
      </section>
      {modal === "dataset" && (
        <Modal title="Importar datos autorizados" close={() => setModal("")}>
          <p>
            Selecciona un JSON con manifest, días observados y etiquetas. Se
            verifican instrumento, unidades, períodos y procedencia. No admite
            coordenadas.
          </p>
          <Form
            submit="Validar e importar"
            task={async (f) => {
              const file = f.get("file") as File;
              return api(
                S + "/models/datasets",
                "POST",
                JSON.parse(await file.text()),
              );
            }}
            done={() => {
              d.refresh();
              setModal("");
            }}
          >
            <label>
              Dataset JSON
              <input
                type="file"
                name="file"
                accept="application/json,.json"
                required
              />
            </label>
            <Note>
              Contrato y ejemplo estructural en la guía de modelos del proyecto.
              No se inventan datos ni se descargan datasets restringidos.
            </Note>
          </Form>
        </Modal>
      )}
      {modal === "weights" && (
        <Modal title="Importar una versión evaluada" close={() => setModal("")}>
          <Form
            submit="Verificar y registrar"
            task={async (f) =>
              api(
                S + "/models/import",
                "POST",
                JSON.parse(await (f.get("file") as File).text()),
              )
            }
            done={() => {
              d.refresh();
              setModal("");
            }}
          >
            <p>
              Archivo con dataset_id, artifact_base64, manifest y metrics. Solo
              se acepta el formato nativo JSON de XGBoost; nunca archivos
              ejecutables o pickle.
            </p>
            <label>
              Paquete de versión JSON
              <input
                type="file"
                name="file"
                accept="application/json,.json"
                required
              />
            </label>
          </Form>
        </Modal>
      )}
      {modal === "decision" && selected && (
        <Modal title="Registrar decisión de versión" close={() => setModal("")}>
          <Form
            task={(f) =>
              api(S + "/models/" + selected.id + "/decision", "POST", {
                state,
                rationale: f.get("rationale"),
              })
            }
            done={() => {
              d.refresh();
              setModal("");
            }}
            submit="Registrar decisión"
          >
            <Note>
              {state === "active"
                ? "La activación solo puede registrarla el psicólogo responsable, con datos reales autorizados y evaluación. Reemplaza explícitamente la versión activa anterior."
                : state === "shadow"
                  ? "Las estimaciones en sombra son para evaluación; no alteran la prioridad de casos."
                  : "La versión dejará de generar nuevas estimaciones."}
            </Note>
            <label>
              Motivo y evaluación revisada
              <textarea name="rationale" required minLength={15} rows={4} />
            </label>
          </Form>
        </Modal>
      )}
      {modal === "predictions" && (
        <Modal title="Estimaciones registradas" close={() => setModal("")}>
          {predictions.length ? (
            predictions.map((p) => (
              <details key={p.id}>
                <summary>
                  {p.cutoff} · {Number(p.detail.estimate).toFixed(2)} puntos
                  PHQ-9
                </summary>
                <pre>{JSON.stringify(p.detail, null, 2)}</pre>
              </details>
            ))
          ) : (
            <Empty title="Sin estimaciones visibles">
              Administrar modelos no da acceso a estimaciones individuales: solo se
              muestran las de participantes sobre los que tienes autorización
              clínica asignada o de investigación. También puede faltar ejecutar
              la inferencia o días elegibles compatibles.
            </Empty>
          )}
        </Modal>
      )}
    </>
  );
}
function Guardian() {
  const token = new URLSearchParams(useLocation().search).get("token") || "";
  const d = useData(
    token ? S + "/guardian/info?token=" + encodeURIComponent(token) : null,
  );
  const [result, setResult] = useState<R | null>(null),
    [withdrawn, setWithdrawn] = useState(false),
    [error, setError] = useState("");
  return (
    <div className="p-public">
      <Link className="p-brand" to="/">
        <HeartHandshake /> Acompaña Escolar
      </Link>
      <PageTitle
        eyebrow="INFORMACIÓN Y DECISIÓN DEL RESPONSABLE"
        title="Una participación informada"
      />
      <ErrorMessage value={d.error || error} />
      {!token && (
        <Empty title="Abre tu enlace individual">
          La institución debe entregarte un enlace y un código de verificación
          por separado.
        </Empty>
      )}
      {d.data && !result && (
        <>
          <section className="p-card">
            <h2>Participación de {d.data.student_name}</h2>
            {d.data.is_test && (
              <Tag tone="amber">Cuenta ficticia para evaluar el flujo</Tag>
            )}
            <p className="p-document">{d.data.document}</p>
            <p>
              <strong>Finalidad:</strong> {d.data.purpose}
            </p>
            <Tag>Documento {d.data.document_version}</Tag>
          </section>
          <section className="p-card">
            <Form
              submit="Registrar mi decisión"
              task={(f) =>
                api(S + "/guardian/approve", "POST", {
                  token,
                  verification_code: f.get("verification_code"),
                  full_name: f.get("full_name"),
                  relationship: f.get("relationship"),
                  identity_reference: f.get("identity_reference"),
                  document_version: d.data.document_version,
                  accepted: f.get("decision") === "accept",
                })
              }
              done={setResult}
            >
              <Input
                label="Código de verificación del responsable"
                name="verification_code"
                minLength={6}
                autoComplete="one-time-code"
              />
              <Input
                label="Nombre completo del responsable"
                name="full_name"
                minLength={3}
              />
              <Input
                label="Vínculo con el estudiante"
                name="relationship"
                placeholder="Madre, padre o responsable autorizado"
              />
              <Input
                label="Referencia de verificación institucional"
                name="identity_reference"
                placeholder="Referencia del registro o comprobación con la institución"
              />
              <Select
                label="Mi decisión"
                name="decision"
                options={[
                  { id: "accept", name: "Autorizo la participación descrita" },
                  { id: "decline", name: "No autorizo la participación" },
                ]}
              />
              <Note>
                Este enlace es exclusivo del responsable. El estudiante deberá
                registrar su asentimiento por separado. No se muestran puntajes
                ni notas privadas.
              </Note>
            </Form>
          </section>
        </>
      )}
      {result && (
        <section className="p-card">
          <CheckCircle2 size={40} color="#087f83" />
          <h2>
            {withdrawn
              ? "Participación retirada"
              : "Tu decisión fue registrada"}
          </h2>
          <p>
            {withdrawn
              ? "Se revocó la captura y se solicitó el borrado."
              : result.accepted
                ? "El estudiante puede continuar con su asentimiento. Guarda este comprobante para la institución."
                : "No se habilitará la captura del estudiante."}
          </p>
          <button
            className="p-secondary"
            onClick={() =>
              downloadJson(result, "comprobante-autorizacion.json")
            }
          >
            Guardar comprobante privado
          </button>
          {!withdrawn && (
            <details className="p-danger-zone">
              <summary>Retirar autorización</summary>
              <p>
                Detendrá la participación y solicitará el borrado de los datos.
              </p>
              <button
                className="p-danger"
                onClick={async () => {
                  try {
                    await api(S + "/guardian/withdraw", "POST", {
                      token: result.management_token,
                    });
                    setWithdrawn(true);
                  } catch (e) {
                    setError((e as Error).message);
                  }
                }}
              >
                Confirmar retirada
              </button>
            </details>
          )}
        </section>
      )}
    </div>
  );
}
function StudentHistory({token}: {token: string}) {
  const [rows, setRows] = useState<R[]>([]);
  const [error, setError] = useState("");
  const load = async () => { try { setRows(await api(S + "/me/questionnaires/history", "GET", undefined, token)); } catch(e) { setError((e as Error).message); } };
  useEffect(() => { load(); }, [token]);
  return <section className="p-card"><h2>Mis respuestas</h2>
    <p>Este historial muestra respuestas recibidas. Una corrección conserva la versión anterior y no cancela una revisión del equipo.</p>
    {error && <p role="alert">{error}</p>}{rows.length === 0 && <p>Todavía no hay respuestas recibidas.</p>}
    {rows.map(r => <details className="p-event" key={r.id}><summary>{stamp(r.applied_at)} · Versión {r.revision} · {r.current ? "Vigente" : "Anterior"}</summary>
      <p>Recibida: {stamp(r.received_at)}</p>
      {r.can_correct ? <Form submit="Enviar corrección" done={load} task={f => api(S + "/me/questionnaires/" + r.id + "/corrections", "POST", {
        answers: Object.fromEntries(r.definition.questions.map((q:R) => [q.id, Number(f.get(q.id))])),
        functioning: f.get("functioning") === "" ? null : Number(f.get("functioning")), reason: String(f.get("reason"))
      }, token, crypto.randomUUID())}>
        <p>Corrige lo que respondiste sobre el mismo período; no es un cuestionario nuevo.</p>
        {r.definition.questions.map((q:R) => <label key={q.id}>{q.text}<select name={q.id} defaultValue={r.answers[q.id]} required>{r.definition.options.map((o:R) => <option key={o.value} value={o.value}>{o.label}</option>)}</select></label>)}
        <label>{r.definition.functioning.text}<select name="functioning" defaultValue={r.functioning ?? ""}><option value="">Selecciona si corresponde</option>{r.definition.functioning.options.map((o:string,i:number) => <option value={i} key={i}>{o}</option>)}</select></label>
        <label>Motivo de la corrección<textarea name="reason" required minLength={3} maxLength={500}/></label>
      </Form> : <div>{r.definition.questions.map((q:R) => <p key={q.id}>{q.text}: {r.definition.options.find((o:R)=>o.value===r.answers[q.id])?.label}</p>)}</div>}
    </details>)}
  </section>;
}

function StudentPortal() {
  const [token, setToken] = useState(
      () => sessionStorage.getItem("acompana-student-token") || "",
    ),
    [home, setHome] = useState<R | null>(null),
    [form, setForm] = useState<R | null>(null),
    [requests, setRequests] = useState<R | null>(null),
    [page, setPage] = useState("home"),
    [answers, setAnswers] = useState<R>({}),
    [error, setError] = useState(""),
    [message, setMessage] = useState("");
  const key = useRef(crypto.randomUUID());
  const load = async () => {
    if (!token) return;
    try {
      setHome(await api(S + "/me", "GET", undefined, token));
      const forms = await api(
        S + "/me/questionnaires",
        "GET",
        undefined,
        token,
      );
      setForm(forms[0] || null);
      setRequests(await api(S + "/me/requests", "GET", undefined, token));
      setError("");
    } catch (e) {
      setError((e as Error).message);
    }
  };
  useEffect(() => {
    load();
  }, [token]);
  const post = (path: string, body: R, k?: string) =>
    api(S + path, "POST", body, token, k);
  const participation = (f: FormData, action: string) =>
    post("/me/participation", {
      action,
      document_version: home!.authorization.version,
      occurred_at: new Date().toISOString(),
      usage: f.has("usage"),
      location: f.has("location"),
      steps: f.has("steps"),
      raw_location_upload: f.has("raw_location_upload"),
      research_access: f.has("research_access"),
      reminder_time: f.get("reminder_time") || "17:00",
      reminders: f.has("reminders"),
    });
  return (
    <div className="p-student">
      <header className="p-student-header">
        <Link className="p-brand" to="/">
          <HeartHandshake /> Acompaña
        </Link>
        {token && (
          <button
            className="p-link"
            onClick={() => {
              sessionStorage.removeItem("acompana-student-token");
              setToken("");
              setHome(null);
            }}
          >
            Cerrar sesión
          </button>
        )}
      </header>
      {!token ? (
        <>
          <PageTitle
            eyebrow="TU ESPACIO, A TU RITMO"
            title="Qué bueno encontrarte aquí"
          />
          <section className="p-card">
            <h2>Activa tu invitación</h2>
            <p>
              Tu institución te entrega la invitación y un código individual.
              Desde la web puedes responder y solicitar apoyo; la captura del
              teléfono se configura en Android.
            </p>
            <Form
              submit="Verificar y continuar"
              task={(f) =>
                api(S + "/enroll", "POST", {
                  invitation: f.get("invitation"),
                  verification_code: f.get("verification_code"),
                  device: {
                    android_api: 29,
                    manufacturer: "Navegador",
                    model: "Formulario sin sensores",
                    app_version: "0.2.0-web",
                    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
                  },
                })
              }
              done={(v) => {
                sessionStorage.setItem("acompana-student-token", v.token);
                setToken(v.token);
              }}
            >
              <Input
                label="Invitación individual"
                name="invitation"
                minLength={16}
              />
              <Input
                label="Código de verificación"
                name="verification_code"
                minLength={6}
                autoComplete="one-time-code"
              />
            </Form>
          </section>
        </>
      ) : (
        home && (
          <>
            {home.is_test && (
              <div className="p-test-label">
                Cuenta ficticia para evaluar el producto
              </div>
            )}
            <ErrorMessage value={error} />
            {message && (
              <div className="p-success" role="status">
                {message}
              </div>
            )}
            {!home.authorization.ready ? (
              <>
                <PageTitle
                  eyebrow="ANTES DE COMENZAR"
                  title="Tú decides cómo participar"
                />
                <section className="p-card">
                  <p className="p-document">{home.document}</p>
                  <p>
                    <strong>Finalidad:</strong> {home.purpose}
                  </p>
                  <Tag>Versión {home.authorization.version}</Tag>
                  {home.authorization.minor && !home.authorization.guardian ? (
                    <Note>
                      Falta que tu responsable complete su autorización desde su
                      propio enlace. Puedes actualizar el estado cuando lo haya
                      hecho.
                    </Note>
                  ) : (
                    <Form
                      submit={
                        home.authorization.minor
                          ? "Registrar mi asentimiento"
                          : "Aceptar mi participación"
                      }
                      task={(f) =>
                        participation(
                          f,
                          home.authorization.minor ? "assent" : "consent",
                        )
                      }
                      done={load}
                    >
                      <label className="p-check">
                        <input type="checkbox" required /> Leí la información y
                        quiero participar voluntariamente
                      </label>
                      <p>
                        Después podrás elegir permisos por separado, pausarlos y
                        retirarte.
                      </p>
                    </Form>
                  )}
                  <button className="p-secondary" onClick={load}>
                    Actualizar autorización
                  </button>
                </section>
              </>
            ) : (
              <>
                <nav className="p-student-nav" aria-label="Mi espacio">
                  {[
                    ["home", "Inicio", Home],
                    ["form", "Cuestionario", ClipboardList],
                    ["requests", "Mis solicitudes", CalendarDays],
                    ["history", "Mis respuestas", ClipboardList],
                    ["privacy", "Mi participación", ShieldCheck],
                  ].map(([id, text, Icon]: any) => (
                    <button
                      key={id}
                      className={page === id ? "active" : ""}
                      onClick={() => setPage(id)}
                    >
                      <Icon size={19} />
                      {text}
                    </button>
                  ))}
                </nav>
                {page === "home" && (
                  <>
                    <PageTitle
                      eyebrow="UN ESPACIO PARA TI"
                      title={"Hola, " + home.name.split(" ")[0]}
                    />
                    <div className="p-student-welcome">
                      <HeartHandshake size={38} />
                      <h2>
                        No tienes que tener todo resuelto para pedir apoyo.
                      </h2>
                      <p>
                        Puedes escribirle al equipo cuando necesites conversar.
                        No hace falta completar un cuestionario primero.
                      </p>
                      <button
                        className="p-primary"
                        onClick={async () => {
                          try {
                            await post("/me/support", {}, key.current);
                            key.current = crypto.randomUUID();
                            setMessage("Tu solicitud fue recibida");
                            await load();
                          } catch (e) {
                            setError(
                              "El equipo todavía no recibió tu solicitud. Comprueba tu conexión.",
                            );
                          }
                        }}
                      >
                        Solicitar apoyo <ArrowRight size={16} />
                      </button>
                    </div>
                    <section className="p-card">
                      <header>
                        <h2>
                          {form
                            ? "Tu cuestionario está disponible"
                            : "Tu próximo cuestionario"}
                        </h2>
                        <ClipboardList size={22} />
                      </header>
                      <p>
                        {form
                          ? "Busca un momento tranquilo para responder. Puedes revisar tus respuestas antes de enviarlas."
                          : home.questionnaire_enabled
                            ? "Próxima fecha: " + stamp(home.next_questionnaire)
                            : "Tu equipo te avisará cuando esté disponible."}
                      </p>
                      {form && (
                        <button
                          className="p-secondary"
                          onClick={() => setPage("form")}
                        >
                          Comenzar cuestionario
                        </button>
                      )}
                    </section>
                  </>
                )}
                {page === "form" && (
                  <>
                    <PageTitle
                      eyebrow="UN MOMENTO PARA RESPONDER"
                      title="Tu cuestionario"
                    />
                    {form ? (
                      <section className="p-card">
                        <h2>{form.title}</h2>
                        <p>{form.recall}</p>
                        <Form
                          submit="Confirmar y enviar respuestas"
                          task={(f) => {
                            const at = new Date();
                            return post(
                              "/me/questionnaires",
                              {
                                instrument_code: form.instrument_id,
                                instrument_version: form.version,
                                answers,
                                functioning:
                                  f.get("functioning") === ""
                                    ? null
                                    : Number(f.get("functioning")),
                                applied_at: at.toISOString(),
                                recall_start: new Date(
                                  at.getTime() - 14 * 86400000,
                                ).toISOString(),
                                recall_end: at.toISOString(),
                              },
                              key.current,
                            );
                          }}
                          done={async () => {
                            key.current = crypto.randomUUID();
                            setAnswers({});
                            setMessage("Tu respuesta fue recibida");
                            await load();
                            setPage("home");
                          }}
                        >
                          {form.questions.map((q: R, n: number) => (
                            <div className="p-question" key={q.id}>
                              <h3>
                                {n + 1}. {q.text}
                              </h3>
                              <div className="p-answer-options">
                                {form.options.map((o: R) => (
                                  <label
                                    key={o.value}
                                    className={
                                      answers[q.id] === o.value
                                        ? "selected"
                                        : ""
                                    }
                                  >
                                    <input
                                      type="radio"
                                      name={q.id}
                                      required
                                      checked={answers[q.id] === o.value}
                                      onChange={() =>
                                        setAnswers({
                                          ...answers,
                                          [q.id]: o.value,
                                        })
                                      }
                                    />
                                    {o.label}
                                  </label>
                                ))}
                              </div>
                            </div>
                          ))}
                          <Select
                            label={form.functioning.text}
                            name="functioning"
                            required={Object.values(answers).some(
                              (v) => Number(v) > 0,
                            )}
                            options={form.functioning.options.map(
                              (name: string, id: number) => ({
                                id: String(id),
                                name,
                              }),
                            )}
                          />
                          <Note>
                            Revisa las nueve respuestas antes de confirmar. El
                            equipo recibe tu respuesta cuando se confirma el
                            envío.
                          </Note>
                        </Form>
                      </section>
                    ) : (
                      <Empty title="No hay un cuestionario pendiente">
                        Tu equipo te avisará cuando corresponda el próximo
                        período.
                      </Empty>
                    )}
                  </>
                )}
                {page === "history" && <StudentHistory token={token}/>}
                {page === "requests" && (
                  <>
                    <PageTitle
                      eyebrow="TUS CONTACTOS CON EL EQUIPO"
                      title="Mis solicitudes"
                    />
                    <section className="p-card">
                      <h2>Solicitudes de apoyo</h2>
                      {requests?.requests.length ? (
                        requests.requests.map((r: R) => (
                          <div className="p-event" key={r.id}>
                            <HeartHandshake />
                            <div>
                              <strong>Solicitud recibida</strong>
                              <p>
                                {stamp(r.created_at)} · {labels[r.state]}
                              </p>
                            </div>
                          </div>
                        ))
                      ) : (
                        <Empty title="Puedes pedir apoyo cuando lo necesites">
                          No necesitas un puntaje alto ni un cuestionario
                          previo.
                        </Empty>
                      )}
                    </section>
                    <section className="p-card">
                      <h2>Mis citas</h2>
                      {requests?.appointments.length ? (
                        requests.appointments.map((a: R) => (
                          <div className="p-event" key={a.id}>
                            <CalendarDays />
                            <div>
                              <strong>{a.title}</strong>
                              <p>
                                {stamp(a.date)} · {a.place}
                              </p>
                              <Tag>{labels[a.state]}</Tag>
                              {a.state === "pending" && (
                                <button
                                  className="p-secondary"
                                  onClick={async () => {
                                    try {
                                      await post(
                                        "/me/appointments/" + a.id + "/confirm",
                                        {},
                                      );
                                      await load();
                                    } catch (e) {
                                      setError((e as Error).message);
                                    }
                                  }}
                                >
                                  Confirmar cita
                                </button>
                              )}
                            </div>
                          </div>
                        ))
                      ) : (
                        <p>Todavía no tienes citas acordadas.</p>
                      )}
                    </section>
                  </>
                )}
                {page === "privacy" && (
                  <>
                    <PageTitle
                      eyebrow="TUS DECISIONES IMPORTAN"
                      title="Mi participación"
                    />
                    <section className="p-card">
                      <p>
                        El equipo de psicología ve cuestionarios y resúmenes de
                        las variables que eliges compartir. No se leen mensajes,
                        llamadas ni contenido de pantalla.
                      </p>
                      <Form
                        task={(f) => participation(f, "preferences")}
                        done={load}
                      >
                        <label className="p-check">
                          <input
                            name="usage"
                            type="checkbox"
                            defaultChecked={home.policy.usage}
                          />{" "}
                          Compartir uso de pantalla
                        </label>
                        <label className="p-check">
                          <input
                            name="location"
                            type="checkbox"
                            defaultChecked={home.policy.location}
                          />{" "}
                          Compartir resúmenes de ubicación
                        </label>
                        <label className="p-check">
                          <input
                            name="steps"
                            type="checkbox"
                            defaultChecked={home.policy.steps}
                          />{" "}
                          Compartir pasos observados con el teléfono
                        </label>
                        <label className="p-check">
                          <input
                            name="raw_location_upload"
                            type="checkbox"
                            defaultChecked={home.policy.raw_location_upload}
                          />{" "}
                          Compartir coordenadas para diagnóstico autorizado
                        </label>
                        <label className="p-check">
                          <input
                            name="research_access"
                            type="checkbox"
                            defaultChecked={home.policy.research_access}
                          />{" "}
                          Autorizar acceso de investigación a mis datos técnicos
                        </label>
                        <label className="p-check">
                          <input
                            name="reminders"
                            type="checkbox"
                            defaultChecked={home.policy.reminders !== false}
                          />{" "}
                          Recibir recordatorios respetuosos
                        </label>
                        <Input
                          label="Hora preferida"
                          name="reminder_time"
                          type="time"
                          value={home.policy.reminder_time || "17:00"}
                        />
                        <Note>
                          Los permisos del sistema y la captura se controlan en
                          la app Android. No aceptar GPS no impide responder ni
                          solicitar apoyo.
                        </Note>
                      </Form>
                      <details className="p-danger-zone">
                        <summary>Retirar mi participación</summary>
                        <p>
                          Se detendrá la captura y se solicitará el borrado de
                          tus datos.
                        </p>
                        <button
                          className="p-danger"
                          onClick={async () => {
                            try {
                              await participation(new FormData(), "withdraw");
                              sessionStorage.removeItem(
                                "acompana-student-token",
                              );
                              setToken("");
                              setHome(null);
                              setMessage("Tu participación fue retirada");
                            } catch (e) {
                              setError((e as Error).message);
                            }
                          }}
                        >
                          Confirmar retirada
                        </button>
                      </details>
                    </section>
                  </>
                )}
              </>
            )}
            <section className="p-card p-support-card">
              <h2>Tu equipo y recursos de apoyo</h2>
              {!home.authorization.ready && <button className="p-secondary" onClick={async () => {try {await post("/me/support",{},key.current);key.current=crypto.randomUUID();setMessage("Tu solicitud fue recibida");}catch(e){setError("El equipo todavía no recibió tu solicitud. Comprueba tu conexión.");}}}>Solicitar contacto con el equipo</button>}
              <p>{home.coverage.text}</p>
              <Tag tone={home.coverage.open ? "teal" : "amber"}>
                {home.coverage.open
                  ? "Dentro del horario configurado"
                  : "Fuera del horario configurado"}
              </Tag>
              <p>{home.coverage.notice}</p>
              {home.coverage.resources.map((r: R, i: number) => (
                <div className="p-resource" key={i}>
                  <strong>{r.title}</strong>
                  <p>{r.contact}</p>
                </div>
              ))}
            </section>
          </>
        )
      )}
      {token && !home && (
        <>
          <ErrorMessage value={error} />
          <button className="p-secondary" onClick={load}>
            Volver a intentar
          </button>
        </>
      )}
    </div>
  );
}
