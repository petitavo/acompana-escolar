import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { resolve } from "node:path";
const credentials = JSON.parse(
  readFileSync("../../.runtime/credentials-demo.json", "utf8"),
).credentials;
async function login(page: any, user: string) {
  await page.goto("/");
  await page.getByLabel("Usuario", { exact: true }).fill(user);
  await page.getByLabel("Contraseña", { exact: true }).fill(credentials[user]);
  await page.getByRole("button", { name: "Entrar al laboratorio" }).click();
}
test("psicólogo revisa caso, registra nota y cierra con persistencia", async ({
  page,
}) => {
  const scenario = JSON.parse(
    execFileSync(
      resolve("../../.venv/bin/python"),
      ["scripts/prepare_e2e.py"],
      {
        cwd: resolve("../.."),
        env: {
          ...process.env,
          APP_MODE: "DEMO",
          PYTHONPATH: "services/backend:.",
        },
      },
    ).toString(),
  );
  await login(page, "psicologo.demo");
  await expect(
    page.getByRole("heading", { name: "Cola de revisión", exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: "../../.runtime/psych-queue.png",
    fullPage: true,
    animations: "disabled",
  });
  await page.goto("/psych/cases/" + scenario.case_id);
  await expect(
    page.getByRole("heading", { name: "Registrar siguiente paso" }),
  ).toBeVisible();
  const action = page.getByRole("combobox", { name: "Acción", exact: true });
  await expect(action).toBeVisible();
  if (await action.locator('option[value="acknowledged"]').count()) {
    await action.selectOption("acknowledged");
    await page
      .getByLabel("Motivo o plan")
      .fill("Reconocimiento de caso ficticio para prueba E2E");
    await page.getByRole("button", { name: "Guardar revisión" }).click();
    await expect(page.getByRole("status")).toContainText("Cambio registrado");
  }
  await page
    .getByLabel("Nota de prueba", { exact: true })
    .fill("Nota ficticia de verificación Playwright");
  await page.getByRole("button", { name: "Añadir nota" }).click();
  await expect(page.getByRole("status")).toContainText("Nota guardada");
  await action.selectOption("closed");
  await page
    .getByLabel("Motivo o plan")
    .fill("Circuito ficticio revisado, prueba completada");
  await page.getByRole("button", { name: "Guardar revisión" }).click();
  await expect(page.locator(".page-title").getByText("Cerrado")).toBeVisible();
  await page.reload();
  await expect(
    page.getByText("Nota ficticia de verificación Playwright").first(),
  ).toBeVisible();
  await expect(page.locator(".recharts-line-curve").first()).toHaveAttribute("d", /M/);
  await page.screenshot({
    path: "../../.runtime/case-detail.png",
    fullPage: true,
    animations: "disabled",
  });
});
test("investigador navega dispositivos, linaje, experimentos y exporta", async ({
  page,
}) => {
  await login(page, "investigador.demo");
  await expect(
    page.getByRole("heading", { name: "Así está funcionando el laboratorio" }),
  ).toBeVisible();
  await page
    .getByRole("link", { name: "Eventos captados", exact: true })
    .click();
  await expect(page.locator("tbody tr").first()).toBeVisible();
  await page.getByRole("button", { name: "JSON", exact: true }).first().click();
  await expect(
    page.getByRole("heading", { name: "Registro permitido" }),
  ).toBeVisible();
  await page
    .getByRole("link", { name: "Variables y trazabilidad", exact: true })
    .click();
  await page.getByRole("button", { name: "Ver origen" }).first().click();
  await expect(
    page.getByRole("heading", { name: /Del intervalo a la variable/ }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Experimentos", exact: true }).click();
  await expect(
    page.getByRole("heading", {
      name: "Comparación en participantes apartados",
    }),
  ).toBeVisible();
  await page.screenshot({
    path: "../../.runtime/experiments.png",
    fullPage: true,
    animations: "disabled",
  });
  await page.getByRole("link", { name: "Exportaciones", exact: true }).click();
  await page.getByRole("button", { name: "Crear exportación" }).click();
  await expect(page.getByRole("status")).toContainText("Exportación encolada");
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({
    path: "../../.runtime/mobile-web.png",
    fullPage: true,
    animations: "disabled",
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
});
test("formulario de participante crea motivo y solicitud visibles al psicólogo", async ({
  page,
}) => {
  const output = execFileSync(
    resolve("../../.venv/bin/python"),
    ["-m", "app.cli", "invite", "DEMO-001"],
    {
      cwd: resolve("../.."),
      env: {
        ...process.env,
        APP_MODE: "DEMO",
        PYTHONPATH: "services/backend:.",
      },
    },
  ).toString();
  const invitation = output.trim().split(": ").pop()!;
  await page.goto("/participant");
  await page
    .getByLabel("Invitación de un uso", { exact: true })
    .fill(invitation);
  await page.getByRole("button", { name: "Vincular formulario" }).click();
  await page.getByRole("checkbox", { name: /Soy adulto y acepto/ }).check();
  await page.getByRole("button", { name: "Aceptar y continuar" }).click();
  for (const name of [
    "¿Cómo sentiste tu energía hoy?",
    "¿Qué tan fácil te resultó concentrarte hoy?",
    "¿Cómo sentiste tu descanso hoy?",
  ])
    await page
      .getByRole("group", { name, exact: true })
      .getByRole("radio", { name: "Mal", exact: true })
      .check();
  await page.getByRole("button", { name: "Enviar cuestionario" }).click();
  await expect(page.getByRole("status")).toContainText(
    "Respuesta guardada en el servidor",
  );
  await page.getByRole("button", { name: "Quiero que me contacten" }).click();
  await expect(page.getByRole("status")).toContainText(
    "Solicitud recibida por el servidor",
  );
  await page.screenshot({
    path: "../../.runtime/participant-form.png",
    fullPage: true,
    animations: "disabled",
  });
  await login(page, "psicologo.demo");
  await page
    .getByRole("link", { name: "Revisar DEMO-001", exact: true })
    .first()
    .click();
  await expect(page.getByText("9 / 9", { exact: true }).first()).toBeVisible();
});
