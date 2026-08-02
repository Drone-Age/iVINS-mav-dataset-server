"use strict";

let siteApiKey = "";
let siteRole = "guest";
let catalog = [];
let families = [];
let profilesByFamily = {};
let siteEditMode = false;
let editingDataset = null;

const byId = (id) => document.getElementById(id);
const t = (uk, en) => window.IVINS_I18N?.t(uk, en) || uk;

function toast(message, isError = false) {
  const node = byId("toast");
  node.textContent = message;
  node.classList.toggle("error", isError);
  node.hidden = false;
  window.setTimeout(() => { node.hidden = true; }, 4200);
}

function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined && text !== null) node.textContent = String(text);
  if (className) node.className = className;
  return node;
}

function actionButton(text, className, handler) {
  const node = element("button", text, `button compact ${className || ""}`.trim());
  node.type = "button";
  node.addEventListener("click", handler);
  return node;
}

async function request(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (siteApiKey) headers.Authorization = `Bearer ${siteApiKey}`;
  if (options.body !== undefined) headers["Content-Type"] = "application/json";
  const response = await fetch(path, {
    method: options.method || "GET",
    headers,
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
    cache: "no-store",
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const problem = new Error(payload.error?.message || `HTTP ${response.status}`);
    problem.status = response.status;
    throw problem;
  }
  return payload;
}

function showLogin() {
  byId("loginMessage").textContent = "";
  byId("apiKeyInput").value = "";
  byId("loginDialog").showModal();
  byId("apiKeyInput").focus();
}

function updateIdentity() {
  const role = byId("rolePill");
  role.textContent = siteRole === "admin"
    ? t("Адмін", "Admin")
    : siteRole === "user" ? t("Користувач", "User") : t("Гість", "Guest");
  role.classList.toggle("guest", siteRole === "guest");
  byId("loginButton").hidden = siteRole !== "guest";
  byId("logoutButton").hidden = siteRole === "guest";
  byId("adminCatalogControls").hidden = siteRole !== "admin";
  if (siteRole !== "admin") {
    siteEditMode = false;
    byId("siteEditMode").checked = false;
  }
  byId("siteNewDatasetButton").hidden = !siteEditMode || siteRole !== "admin";
}

async function login(event) {
  event.preventDefault();
  const candidate = byId("apiKeyInput").value.trim();
  if (!candidate) return;
  siteApiKey = candidate;
  try {
    const session = await request("/auth/session");
    siteRole = session.role;
    siteEditMode = false;
    byId("siteEditMode").checked = false;
    byId("loginDialog").close();
    byId("apiKeyInput").value = "";
    updateIdentity();
    renderCatalog();
    toast(t(`Вхід виконано: ${siteRole === "admin" ? "Адмін" : "Користувач"}`, `Signed in: ${siteRole === "admin" ? "Admin" : "User"}`));
    if (siteRole === "admin") byId("datasets").scrollIntoView({ behavior: "smooth" });
  } catch (error) {
    siteApiKey = "";
    siteRole = "guest";
    byId("loginMessage").textContent = error.status === 401
      ? t("API-ключ недійсний або відкликаний.", "The API key is invalid or revoked.")
      : error.message;
  }
}

function logout() {
  siteApiKey = "";
  siteRole = "guest";
  siteEditMode = false;
  updateIdentity();
  renderCatalog();
  toast(t("Ви працюєте як Гість", "You are browsing as a Guest"));
}

function externalLink(mirror) {
  const link = element("a", `${mirror.label} ↗`, "download-link external");
  link.href = mirror.url;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  link.title = `${t("Зовнішнє дзеркало", "External mirror")} · ${mirror.format}`;
  return link;
}

async function downloadLocal(item, artifact) {
  if (siteRole === "guest") {
    showLogin();
    return;
  }
  try {
    const base = `/v1/datasets/${encodeURIComponent(item.id)}/artifacts/${encodeURIComponent(artifact.format)}/${encodeURIComponent(artifact.version)}`;
    const ticket = await request(`${base}/download-ticket`, { method: "POST", body: {} });
    const link = document.createElement("a");
    link.href = ticket.download_url;
    link.hidden = true;
    document.body.append(link);
    link.click();
    link.remove();
    toast(t("Захищене завантаження розпочато", "Protected download started"));
  } catch (error) {
    if (error.status === 401) logout();
    toast(error.message, true);
  }
}

function formatCell(item, format) {
  const cell = document.createElement("td");
  const stack = element("div", null, "link-stack");
  item.mirrors.filter((mirror) => mirror.format === format).forEach((mirror) => stack.append(externalLink(mirror)));
  item.local_artifacts.filter((artifact) => artifact.format === format && artifact.available).forEach((artifact) => {
    const label = siteRole === "guest"
      ? t("Server · потрібен ключ", "Server · key required")
      : `Server · v${artifact.version}`;
    const button = element("button", label, siteRole === "guest" ? "locked-link" : "download-link");
    button.type = "button";
    button.addEventListener("click", () => downloadLocal(item, artifact));
    stack.append(button);
  });
  if (!stack.childNodes.length) stack.append(element("span", "—", "empty"));
  cell.append(stack);
  return cell;
}

function referenceCell(item) {
  const cell = document.createElement("td");
  const stack = element("div", null, "link-stack");
  if (item.ground_truth_url) {
    const link = element("a", `${t("Траєкторія", "Trajectory")} ↗`, "reference-link");
    link.href = item.ground_truth_url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    stack.append(link);
  }
  if (item.config_url) {
    const link = element("a", `${t("Конфігурація", "Config")} ↗`, "reference-link");
    link.href = item.config_url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    stack.append(link);
  }
  if (!stack.childNodes.length) stack.append(element("span", "—", "empty"));
  cell.append(stack);
  return cell;
}

function datasetRow(item) {
  const row = document.createElement("tr");
  row.append(element("td", item.id, "dataset-id"));
  const name = element("td", null, "dataset-name");
  const title = element("strong", item.name);
  if (item.homepage_url) {
    const link = document.createElement("a");
    link.href = item.homepage_url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.append(title);
    name.append(link);
  } else {
    name.append(title);
  }
  if (item.description) name.append(element("small", item.description));
  row.append(
    name,
    element("td", item.profile, "profile-badge"),
    element("td", item.measurement || "—"),
    formatCell(item, "rosbag"),
    formatCell(item, "rosbag2"),
    referenceCell(item),
  );
  if (siteRole === "admin" && siteEditMode) {
    const actions = element("td", null, "row-actions");
    actions.append(
      actionButton(t("Редагувати", "Edit"), "", () => openDataset(item)),
      actionButton(t("Видалити", "Delete"), "danger", () => deleteDataset(item)),
    );
    row.append(actions);
  }
  return row;
}

function familyBlock(family, items) {
  const section = element("section", null, "family-block");
  const heading = element("div", null, "family-title");
  heading.append(element("h3", family), element("span", `${items.length} ${t("наборів", "datasets")}`));
  const scroll = element("div", null, "table-scroll");
  const table = document.createElement("table");
  const head = document.createElement("thead");
  const headRow = document.createElement("tr");
  const labels = [
    "ID",
    t("Назва Dataset", "Dataset name"),
    t("Профіль", "Profile"),
    t("Довжина / Розмір", "Length / Size"),
    "ROS Bag",
    "ROS Bag2",
    t("Ground Truth / Конфігурація", "Ground Truth / Config"),
  ];
  if (siteRole === "admin" && siteEditMode) labels.push(t("Дії", "Actions"));
  labels.forEach((label) => headRow.append(element("th", label)));
  head.append(headRow);
  const body = document.createElement("tbody");
  body.replaceChildren(...items.map(datasetRow));
  table.append(head, body);
  scroll.append(table);
  section.append(heading, scroll);
  return section;
}

function renderCatalog() {
  const query = byId("searchInput").value.trim().toLowerCase();
  const family = byId("familyFilter").value;
  const profile = byId("profileFilter").value;
  const filtered = catalog.filter((item) => (
    (!family || item.family === family)
    && (!profile || item.profile === "all" || item.profile === profile)
    && (!query || `${item.id} ${item.name} ${item.profile} ${item.description}`.toLowerCase().includes(query))
  ));
  const grouped = new Map();
  filtered.forEach((item) => {
    if (!grouped.has(item.family)) grouped.set(item.family, []);
    grouped.get(item.family).push(item);
  });
  const list = byId("familyList");
  list.replaceChildren(...[...grouped.entries()].map(([name, items]) => familyBlock(name, items)));
  byId("catalogStatus").textContent = filtered.length
    ? t(`Показано ${filtered.length} із ${catalog.length}`, `Showing ${filtered.length} of ${catalog.length}`)
    : t("Нічого не знайдено", "No datasets found");
}

function populateFamilyFilter() {
  const select = byId("familyFilter");
  const selected = select.value;
  const defaultOption = element("option", t("Усі сімейства", "All families"));
  defaultOption.value = "";
  select.replaceChildren(defaultOption, ...families.map((family) => {
    const option = element("option", family);
    option.value = family;
    return option;
  }));
  select.value = families.includes(selected) ? selected : "";
}

function populateProfileFilter() {
  const select = byId("profileFilter");
  const family = byId("familyFilter").value;
  const selected = select.value;
  const available = family
    ? (profilesByFamily[family] || []).filter((profile) => profile !== "all")
    : [];
  const defaultOption = element(
    "option",
    family ? t("Усі профілі", "All profiles") : t("Оберіть сімейство", "Select a family"),
  );
  defaultOption.value = "";
  select.replaceChildren(defaultOption, ...available.map((profile) => {
    const option = element("option", profile);
    option.value = profile;
    return option;
  }));
  select.disabled = !family;
  select.value = available.includes(selected) ? selected : "";
}

async function loadCatalog() {
  byId("catalogStatus").textContent = t("Завантаження каталогу…", "Loading catalog…");
  try {
    const data = await request("/public/api/datasets");
    catalog = data.datasets;
    families = data.families;
    profilesByFamily = data.profiles_by_family || Object.fromEntries(families.map((family) => [
      family,
      [...new Set(catalog.filter((item) => item.family === family).map((item) => item.profile))].sort(),
    ]));
    byId("datasetCount").textContent = data.total;
    byId("familyCount").textContent = data.families.length;
    byId("mirrorCount").textContent = catalog.reduce((count, item) => count + item.mirrors.length, 0);
    populateFamilyFilter();
    populateProfileFilter();
    renderCatalog();
  } catch (error) {
    byId("catalogStatus").textContent = t("Каталог тимчасово недоступний.", "The catalog is temporarily unavailable.");
    toast(error.message, true);
  }
}

function openDataset(item = null) {
  editingDataset = item;
  byId("siteDatasetDialogTitle").textContent = item
    ? t(`Редагування ${item.id}`, `Editing ${item.id}`)
    : t("Новий Dataset", "New Dataset");
  byId("siteDatasetId").value = item?.id || "";
  byId("siteDatasetId").disabled = Boolean(item);
  byId("siteDatasetFamily").value = item?.family || byId("familyFilter").value || "";
  byId("siteDatasetProfile").value = item?.profile || "all";
  byId("siteDatasetName").value = item?.name || "";
  byId("siteDatasetMeasurement").value = item?.measurement || "";
  byId("siteDatasetDescription").value = item?.description || "";
  byId("siteDatasetHomepage").value = item?.homepage_url || "";
  byId("siteDatasetGroundTruth").value = item?.ground_truth_url || "";
  byId("siteDatasetConfig").value = item?.config_url || "";
  byId("siteDatasetVisible").checked = true;
  byId("siteDatasetDialog").showModal();
}

async function saveDataset(event) {
  event.preventDefault();
  if (siteRole !== "admin" || !siteEditMode) return;
  const body = {
    family: byId("siteDatasetFamily").value.trim(),
    profile: byId("siteDatasetProfile").value.trim(),
    name: byId("siteDatasetName").value.trim(),
    measurement: byId("siteDatasetMeasurement").value.trim(),
    description: byId("siteDatasetDescription").value.trim(),
    homepage_url: byId("siteDatasetHomepage").value.trim(),
    ground_truth_url: byId("siteDatasetGroundTruth").value.trim(),
    config_url: byId("siteDatasetConfig").value.trim(),
    visible: byId("siteDatasetVisible").checked,
  };
  try {
    if (editingDataset) {
      await request(`/admin/api/datasets/${encodeURIComponent(editingDataset.id)}`, { method: "PATCH", body });
    } else {
      body.id = byId("siteDatasetId").value.trim();
      await request("/admin/api/datasets", { method: "POST", body });
    }
    byId("siteDatasetDialog").close();
    editingDataset = null;
    await loadCatalog();
    toast(t("Dataset збережено", "Dataset saved"));
  } catch (error) {
    toast(error.message, true);
  }
}

async function deleteDataset(item) {
  if (siteRole !== "admin" || !siteEditMode) return;
  if (!window.confirm(t(`Видалити Dataset ${item.id}?`, `Delete Dataset ${item.id}?`))) return;
  try {
    await request(`/admin/api/datasets/${encodeURIComponent(item.id)}`, { method: "DELETE" });
    await loadCatalog();
    toast(t("Dataset видалено", "Dataset deleted"));
  } catch (error) {
    toast(error.message, true);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  byId("loginButton").addEventListener("click", showLogin);
  byId("closeLogin").addEventListener("click", () => byId("loginDialog").close());
  byId("loginForm").addEventListener("submit", login);
  byId("logoutButton").addEventListener("click", logout);
  byId("refreshButton").addEventListener("click", loadCatalog);
  byId("searchInput").addEventListener("input", renderCatalog);
  byId("familyFilter").addEventListener("change", () => {
    populateProfileFilter();
    renderCatalog();
  });
  byId("profileFilter").addEventListener("change", renderCatalog);
  byId("siteEditMode").addEventListener("change", (event) => {
    siteEditMode = siteRole === "admin" && event.target.checked;
    byId("siteNewDatasetButton").hidden = !siteEditMode;
    renderCatalog();
  });
  byId("siteNewDatasetButton").addEventListener("click", () => openDataset());
  byId("siteDatasetForm").addEventListener("submit", saveDataset);
  byId("siteCancelDataset").addEventListener("click", () => byId("siteDatasetDialog").close());
  byId("siteCancelDatasetTop").addEventListener("click", () => byId("siteDatasetDialog").close());
  window.addEventListener("ivins-languagechange", () => {
    updateIdentity();
    populateFamilyFilter();
    populateProfileFilter();
    renderCatalog();
  });
  updateIdentity();
  loadCatalog();
});
