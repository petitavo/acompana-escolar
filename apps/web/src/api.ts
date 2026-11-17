export let csrf = "";
export function setCsrf(value: string) {
  csrf = value;
}
export async function api(
  path: string,
  method = "GET",
  body?: unknown,
  token?: string,
  key?: string,
) {
  const response = await fetch("/api/v1" + path, {
    method,
    credentials: "same-origin",
    headers: {
      ...(body ? { "Content-Type": "application/json" } : {}),
      ...(token
        ? { Authorization: "Bearer " + token }
        : { "X-CSRF-Token": csrf }),
      ...(method === "POST"
        ? { "Idempotency-Key": key || crypto.randomUUID() }
        : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await response.json();
  if (response.status === 401 && !token && path !== "/auth/login")
    window.dispatchEvent(new Event("session-expired"));
  if (!response.ok)
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : JSON.stringify(data.detail),
    );
  return data;
}
// El servidor guarda en UTC; con SQLite algunas fechas llegan sin zona horaria y el
// navegador las tomaría como hora local (5 h de diferencia en Lima).
const asUtc = (v: string) =>
  /T\d{2}:\d{2}(:\d{2}(\.\d+)?)?$/.test(v) ? v + "Z" : v;
export const stamp = (v?: string) =>
  v
    ? new Date(asUtc(v)).toLocaleString("es-PE", {
        day: "2-digit",
        month: "short",
        hour: "2-digit",
        minute: "2-digit",
      })
    : "Todavía no disponible";
export const stateLabel: Record<string, string> = {
  new: "Sin revisar",
  acknowledged: "Reconocido",
  contact_planned: "Contacto planificado",
  in_followup: "En seguimiento",
  closed: "Cerrado",
  active: "Activa",
  paused: "Pausada",
  pending: "Sin consentimiento",
  revoked: "Revocada",
  queued: "En cola",
  running: "Procesando",
  completed: "Completado",
  failed: "Falló",
  expired: "Vencido",
  sufficient: "Datos suficientes",
  partial: "Datos parciales",
  missing: "Sin datos",
  observed: "Observado",
  unsupported: "No compatible",
};
export const reasonLabel: Record<string, string> = {
  contact_request: "Solicitud de contacto",
  questionnaire_review_demo: "Cuestionario de prueba",
  behavior_change: "Cambio persistente",
  questionnaire_review: "Cuestionario",
};
export const featureLabel: Record<string, string> = {
  interactive_minutes: "Pantalla interactiva",
  night_interactive_minutes: "Uso nocturno del teléfono",
  interactive_session_count: "Sesiones interactivas",
  keyguard_hidden_count: "Bloqueo ocultado",
};
