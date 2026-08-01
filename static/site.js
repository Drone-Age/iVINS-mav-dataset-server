"use strict";

let siteApiKey = "";
let siteRole = "guest";
let catalog = [];

const byId = (id) => document.getElementById(id);

function toast(message, isError = false) {
  const node = byId("toast");
  node.textContent = message;
  node.classList.toggle("error", isError);
  node.hidden = false;
  window.setTimeout(() => { node.hidden = true; }, 4200);
}

function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined && text !== null) node.textContent = text;
  if (className) node.className = className;
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
  role.textContent = siteRole === "admin" ? "Адмін" : siteRole === "user" ? "Користувач" : "Гість";
  role.classList.toggle("guest", siteRole === "guest");
  byId("loginButton").hidden = siteRole !== "guest";
  byId("logoutButton").hidden = siteRole === "guest";
  byId("adminLink").hidden = siteRole !== "admin";
}

async function login(event) {
  event.preventDefault();
  const candidate = byId("apiKeyInput").value.trim();
  if (!candidate) return;
  siteApiKey = candidate;
  try {
    const session = await request("/auth/session");
    siteRole = session.role;
    byId("loginDialog").close();
    byId("apiKeyInput").value = "";
    updateIdentity();
    renderCatalog();
    toast(`Вхід виконано: ${session.user_type}`);
  } catch (error) {
    siteApiKey = "";
    siteRole = "guest";
    byId("loginMessage").textContent = error.status === 401 ? "API-ключ недійсний або відкликаний." : error.message;
  }
}

function logout() {
  siteApiKey = "";
  siteRole = "guest";
  updateIdentity();
  renderCatalog();
  toast("Ви працюєте як Гість");
}

function externalLink(mirror) {
  const link = element("a", `${mirror.label} ↗`, "download-link external");
  link.href = mirror.url;
  link.target = "_blank";
  link.rel = "noopener noreferrer";
  link.title = `Зовнішнє дзеркало · ${mirror.format}`;
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
    toast("Захищене завантаження розпочато");
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
    const label = siteRole === "guest" ? "Server · потрібен ключ" : `Server · v${artifact.version}`;
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
    const link = element("a", "Trajectory ↗", "reference-link");
    link.href = item.ground_truth_url; link.target = "_blank"; link.rel = "noopener noreferrer"; stack.append(link);
  }
  if (item.config_url) {
    const link = element("a", "Config ↗", "reference-link");
    link.href = item.config_url; link.target = "_blank"; link.rel = "noopener noreferrer"; stack.append(link);
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
    const link = document.createElement("a"); link.href = item.homepage_url; link.target = "_blank"; link.rel = "noopener noreferrer"; link.append(title); name.append(link);
  } else name.append(title);
  if (item.description) name.append(element("small", item.description));
  row.append(name, element("td", item.profile, "profile-badge"), element("td", item.measurement || "—"), formatCell(item, "rosbag"), formatCell(item, "rosbag2"), referenceCell(item));
  return row;
}

function familyBlock(family, items) {
  const section = element("section", null, "family-block");
  const heading = element("div", null, "family-title");
  heading.append(element("h3", family), element("span", `${items.length} datasets`));
  const scroll = element("div", null, "table-scroll");
  const table = document.createElement("table");
  const head = document.createElement("thead");
  const headRow = document.createElement("tr");
  ["ID", "Dataset Name", "Profile", "Length / Size", "ROS Bag", "ROS Bag2", "Ground Truth / Config"].forEach((label) => headRow.append(element("th", label)));
  head.append(headRow);
  const body = document.createElement("tbody");
  body.replaceChildren(...items.map(datasetRow));
  table.append(head, body); scroll.append(table); section.append(heading, scroll);
  return section;
}

function renderCatalog() {
  const query = byId("searchInput").value.trim().toLowerCase();
  const family = byId("familyFilter").value;
  const profile = byId("profileFilter").value;
  const filtered = catalog.filter((item) => (!family || item.family === family) && (!profile || item.profile === profile) && (!query || `${item.id} ${item.name} ${item.profile} ${item.description}`.toLowerCase().includes(query)));
  const grouped = new Map();
  filtered.forEach((item) => { if (!grouped.has(item.family)) grouped.set(item.family, []); grouped.get(item.family).push(item); });
  const list = byId("familyList");
  list.replaceChildren(...[...grouped.entries()].map(([name, items]) => familyBlock(name, items)));
  byId("catalogStatus").textContent = filtered.length ? `Показано ${filtered.length} із ${catalog.length}` : "Нічого не знайдено";
}

async function loadCatalog() {
  byId("catalogStatus").textContent = "Завантаження каталогу…";
  try {
    const data = await request("/public/api/datasets");
    catalog = data.datasets;
    byId("datasetCount").textContent = data.total;
    byId("familyCount").textContent = data.families.length;
    byId("mirrorCount").textContent = catalog.reduce((count, item) => count + item.mirrors.length, 0);
    const select = byId("familyFilter");
    const selected = select.value;
    const defaultOption = element("option", "Усі сімейства"); defaultOption.value = "";
    select.replaceChildren(defaultOption, ...data.families.map((family) => { const option = element("option", family); option.value = family; return option; }));
    select.value = data.families.includes(selected) ? selected : "";
    const profileSelect = byId("profileFilter");
    const selectedProfile = profileSelect.value;
    const allProfiles = element("option", "Усі профілі"); allProfiles.value = "";
    profileSelect.replaceChildren(allProfiles, ...data.profiles.map((profile) => { const option = element("option", profile); option.value = profile; return option; }));
    profileSelect.value = data.profiles.includes(selectedProfile) ? selectedProfile : "";
    renderCatalog();
  } catch (error) {
    byId("catalogStatus").textContent = "Каталог тимчасово недоступний.";
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
  byId("familyFilter").addEventListener("change", renderCatalog);
  byId("profileFilter").addEventListener("change", renderCatalog);
  updateIdentity();
  loadCatalog();
});
