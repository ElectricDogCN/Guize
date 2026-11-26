const region = (page, name) => page.getByRole("region", { name });
const exact = (node, text) => node.getByText(text, { exact: true });
const button = (node, name) => node.getByRole("button", { name, exact: true });
const status = (node) => node.getByRole("status").textContent();
const items = (node) => node.getByRole("listitem").allTextContents();

async function virtualList({ page, args, record }) {
  const list = page.getByLabel("Assets", { exact: true });
  const rows = list.locator("[data-asset]");
  await list.waitFor();

  for (const [index, offset] of args.offsets.entries()) {
    const action = ["scroll_begin", "scroll_middle", "scroll_end"][index];
    await record(action, "[data-input-rows] [data-asset]", async () => {
      const id = "asset-" + String(offset + 1).padStart(7, "0");
      await list.evaluate((element, row) => { element.scrollTop = row * 28; }, offset);
      await list.locator(`[data-asset="${id}"]`).waitFor();
      const visible = await rows.count();
      return {
        value: { first: await rows.first().getAttribute("data-asset"), visible },
        inputRowCount: Number(await list.getAttribute("data-input-rows")),
        renderedDomRows: visible,
      };
    });
  }

  await record("select_row", "[data-asset=asset-1000000]", async () => {
    await list.evaluate((element) => { element.scrollTop = element.scrollHeight; });
    const last = list.locator("[data-asset=asset-1000000]");
    await last.click();
    await exact(page, "Selected asset-1000000").waitFor();
    return {
      value: {
        asset: await last.getAttribute("data-asset"),
        pressed: (await last.getAttribute("aria-pressed")) === "true",
      },
      inputRowCount: Number(await list.getAttribute("data-input-rows")),
      renderedDomRows: await rows.count(),
    };
  });
}

async function form({ page, record }) {
  const panel = region(page, "Source form");
  const source = panel.getByLabel("Source", { exact: true });
  const endpoint = panel.getByLabel("Endpoint");
  const save = button(panel, "Save source");

  await record("conditional_fields", "label/source-type and input[name=endpoint]", async () => {
    await source.waitFor();
    const localEndpoint = await endpoint.isVisible();
    await source.selectOption("remote");
    await endpoint.waitFor();
    return { value: { localEndpoint, remoteEndpoint: await endpoint.isVisible() } };
  });
  await record("validation", "[role=alert] in Source form", async () => {
    await save.click();
    await exact(panel, "Endpoint is required.").waitFor();
    return { value: await panel.getByRole("alert").textContent() };
  });
  await record("schema_update", "[role=status] in Source form", async () => {
    await endpoint.fill("fixture-endpoint");
    await save.click();
    await exact(panel, "Saved remote source with retry limit 3.").waitFor();
    return { value: await status(panel) };
  });
}

async function graph({ page, record }) {
  const panel = region(page, "Workflow graph");
  const readPosition = async () => {
    await exact(panel, "Row 2, column 2").waitFor();
    return { label: await panel.getByLabel("Node label").inputValue(), position: await status(panel) };
  };

  await record("nodes", ".graph button", async () => {
    await panel.locator(".graph button").first().waitFor();
    return { value: await panel.locator(".graph button").allTextContents() };
  });
  await record("edges", "Connections list", async () => ({ value: await items(panel) }));
  await record("edit", "Node label and graph position", async () => {
    await button(panel, "verify").click();
    await button(panel, "Move selected node").click();
    await panel.getByLabel("Node label").fill("Verify input");
    return { value: await readPosition() };
  });
  await record("state_sync", "reloaded graph selected node", async () => {
    await page.reload();
    await button(panel, "Verify input").click();
    return { value: await readPosition() };
  });
}

async function rules({ page, record }) {
  const panel = region(page, "Decision table");
  const pending = panel.getByLabel("Rule 2 allow");
  const condition = panel.getByLabel("Rule 3 condition");
  const save = button(panel, "Save rules");

  await record("edit_rules", "Decision table tbody rows and Rule 2 allow", async () => {
    await pending.check();
    await button(panel, "Add rule").click();
    await condition.waitFor();
    return { value: { pendingAllows: await pending.isChecked(), ruleCount: await panel.locator("tbody tr").count() } };
  });
  await record("validate_rules", "Decision table alert and status", async () => {
    await condition.fill("ready");
    await save.click();
    const alert = exact(panel, "Rule conditions must be unique.");
    await alert.waitFor();
    const duplicate = await alert.textContent();
    await condition.fill("failed");
    await save.click();
    await exact(panel, "3 rules saved.").waitFor();
    return { value: { duplicate, saved: await status(panel) } };
  });
}

async function monitoring({ page, record }) {
  const panel = region(page, "Monitoring");
  const refresh = button(panel, "Refresh metrics");
  await record("metrics", "Monitoring Metric samples", async () => {
    await panel.getByRole("listitem").first().waitFor();
    return { value: await items(panel) };
  });
  await record("filter", "Monitoring Series and Metric samples", async () => {
    await panel.getByLabel("Series").selectOption("failed");
    await exact(panel, "10s · 1").waitFor();
    return { value: await items(panel) };
  });
  await record("refresh", "Refresh metrics control", async () => {
    await refresh.click();
    return { value: await refresh.evaluate((element) => element === document.activeElement) };
  });
  await record("failure_state", "Monitoring role=alert and retained samples", async () => {
    await exact(panel, "Refresh failed (unavailable).").waitFor();
    return { value: { message: await panel.getByRole("alert").textContent(), retained: await items(panel) } };
  });
}

async function streams({ page, record }) {
  const transports = [
    ["sse", region(page, "SSE stream")],
    ["websocket", region(page, "WebSocket stream")],
  ];
  for (const [name, panel] of transports) {
    await record(name + "_update", name + " ordered event list", async () => {
      await exact(panel, "2 · ready").waitFor();
      return { value: await items(panel) };
    });
  }
  await record("reconnect", "SSE and WebSocket reconnect counters", async () => ({
    value: Object.fromEntries(await Promise.all(transports.map(async ([name, panel]) =>
      [name, Number((await status(panel)).split(": ").at(-1))],
    ))),
  }));
  await record("error_state", "SSE and WebSocket status and replay observations", async () => {
    const states = await Promise.all(transports.map(([, panel]) => items(panel)));
    return { value: {
      recovered: states.every((sequence) => sequence.at(-1) === "2 · ready"),
      duplicateApplied: states.some((sequence) => new Set(sequence).size !== sequence.length),
    } };
  });
}

async function player({ page, args, record }) {
  const panel = region(page, "Playback component");
  const widget = panel.locator(args.component);
  await record("embed_player", args.component + " asset label", async () => {
    await exact(widget, args.assetId).waitFor();
    return { value: await exact(widget, args.assetId).textContent() };
  });
  await record("web_component_contract", args.component + " shadow root", async () => ({
    value: await widget.evaluate((element) => element.shadowRoot && element.localName),
  }));
  await record("player_events", "Playback component status", async () => {
    const states = [];
    for (const [index, control] of ["Signal ready", "Pause playback", "Signal unavailable"].entries()) {
      await button(widget, control).click();
      await exact(panel, "Playback: " + args.events[index]).waitFor();
      states.push(await status(panel));
    }
    await region(page, "Monitoring").waitFor();
    return { value: states };
  });
}

async function responsive({ browser, url, args, record }) {
  const pages = [];
  try {
    await record("responsive_breakpoints", ".responsive-actions grid and touch target dimensions", async () => {
      const value = {};
      for (const [index, viewport] of args.viewports.entries()) {
        const key = ["phone", "tablet"][index];
        const page = await browser.newPage({ viewport, hasTouch: true, isMobile: true });
        pages.push([key, page]);
        page.setDefaultTimeout(7_000);
        await page.goto(url);
        const panel = region(page, "Responsive actions");
        const layout = await panel.locator(".responsive-actions").evaluate((group) => {
          const columns = getComputedStyle(group).gridTemplateColumns.split(" ").length;
          const heights = Array.from(group.querySelectorAll("button"), (item) => item.getBoundingClientRect().height);
          return { columns, heights };
        });
        if (layout.heights.some((height) => height < 44)) throw new Error("Touch action below 44px: " + key);
        value[key + "Columns"] = layout.columns;
      }
      return { value };
    });
    await record("touch_interaction", "Responsive actions status after touch", async () => {
      const value = {};
      for (const [key, page] of pages) {
        const panel = region(page, "Responsive actions");
        await button(panel, "Open sample").tap();
        await exact(panel, "Sample details").waitFor();
        const opened = await status(panel);
        await button(panel, "Back to samples").tap();
        await exact(panel, "Sample list").waitFor();
        value[key] = [opened, await status(panel)];
      }
      return { value };
    });
  } finally {
    await Promise.all(pages.map(([, page]) => page.close()));
  }
}

async function permissions({ page, args, record }) {
  const panel = region(page, "Subject visibility");
  const select = panel.getByLabel("Sample subject");
  const edit = button(panel, "edit");
  const field = panel.getByLabel("Sample title");
  const choose = async (subject) => {
    await select.selectOption(subject);
    await exact(panel, "Current view: read").waitFor();
  };

  await record("route_visibility", "Current view label per sample subject", async () => {
    await choose("editor");
    await edit.click();
    await exact(panel, "Current view: edit").waitFor();
    const editor = await status(panel);
    await choose("reader");
    return { value: { editor, reader: await status(panel) } };
  });
  await record("field_visibility", "Sample title field per sample subject", async () => {
    const reader = await field.isVisible();
    await choose("editor");
    await edit.click();
    await field.waitFor();
    return { value: { editor: await field.isVisible(), reader } };
  });
  await record("action_visibility", "Rendered buttons per sample subject", async () => {
    const value = {};
    for (const { id } of args.subjects) {
      await choose(id);
      value[id] = [];
      for (const action of args.actions) {
        if (await button(panel, action).isVisible()) value[id].push(action);
      }
    }
    return { value };
  });
  await record("server_authorization", "Server edit status per sample subject", async () => {
    const value = {};
    for (const { id } of args.subjects) {
      await choose(id);
      const reply = page.waitForResponse((response) => new URL(response.url()).pathname === "/fixture-authorization");
      await button(panel, "Check sample edit capability").click();
      const code = (await reply).status();
      const verdict = exact(panel, "Server edit status " + code);
      await verdict.waitFor();
      value[id] = Number((await verdict.textContent()).split(" ").at(-1));
    }
    return { value };
  });
}

async function theme({ page, record }) {
  const panel = region(page, "Theme preview");
  const surface = exact(panel, "Sample surface");
  for (const [theme, action] of [["light", "apply_tokens"], ["dark", "switch_theme"]]) {
    await record(action, ".sample-surface computed style", async () => {
      await button(panel, theme).click();
      await panel.getByRole("button", { name: theme, exact: true, pressed: true }).waitFor();
      return { value: await surface.evaluate((element) => {
        const style = getComputedStyle(element);
        return { background: style.backgroundColor, text: style.color, padding: style.padding };
      }) };
    });
  }
}

export const browserActions = {
  million_row_virtual_list_equivalent: virtualList,
  dynamic_form_equivalent: form,
  flowchart_equivalent: graph,
  decision_table_equivalent: rules,
  monitoring_view_equivalent: monitoring,
  sse_websocket_equivalent: streams,
  player_integration_equivalent: player,
  mobile_experience_equivalent: responsive,
  permission_model_equivalent: permissions,
  design_token_equivalent: theme,
};

export async function observeScenario({ scenario, browser, page, url }) {
  const actions = [];
  const record = async (actionId, selector, interaction) => {
    const startedAt = new Date().toISOString();
    const { value, inputRowCount = null, renderedDomRows = null } = await interaction();
    const observedAt = new Date().toISOString();
    actions.push({
      actionId, startedAt, finishedAt: observedAt, status: "completed",
      domSamples: [{ observedAt, selector, observedValue: value, inputRowCount, renderedDomRows }],
    });
  };
  await browserActions[scenario.scenarioId]({ args: scenario.arguments, browser, page, url, record });
  return actions;
}
