"use strict";

let apiKey = "";
let activeView = "datasets";
let editingArtifact = null;
let editingDataset = null;
let mirrorDataset = null;
let adminDatasets = [];
let datasetEditMode = false;

const byId = (id) => document.getElementById(id);
const t = (uk, en) => window.IVINS_I18N?.t(uk, en) || uk;

function make(tag, text, className) {
  const element = document.createElement(tag);
  if (text !== undefined && text !== null) element.textContent = String(text);
  if (className) element.className = className;
  return element;
}

function button(text, className, handler) {
  const element = make("button", text, `button compact ${className || ""}`.trim());
  element.type = "button";
  element.addEventListener("click", handler);
  return element;
}

function formatBytes(value) {
  const size = Number(value || 0);
  if (size < 1024) return `${size} B`;
  const units = ["KB", "MB", "GB", "TB"];
  let amount = size;
  let index = -1;
  do { amount /= 1024; index += 1; } while (amount >= 1024 && index < units.length - 1);
  return `${amount.toFixed(amount >= 10 ? 1 : 2)} ${units[index]}`;
}

function formatDate(value, epoch = false) {
  if (!value) return "—";
  const date = epoch ? new Date(Number(value) * 1000) : new Date(`${value}Z`);
  const locale = window.IVINS_I18N?.getLanguage() === "en" ? "en-US" : "uk-UA";
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString(locale);
}

function badge(text, tone) { return make("span", text, `badge ${tone || ""}`); }

function stateLabel(value) {
  const labels = {
    created: ["створено", "created"],
    uploading: ["завантаження", "uploading"],
    verified: ["перевірено", "verified"],
    published: ["опубліковано", "published"],
    rejected: ["відхилено", "rejected"],
    registered: ["зареєстровано", "registered"],
    orphan: ["незареєстрований", "orphan"],
    missing: ["відсутній", "missing"],
    legacy: ["застарілий", "legacy"],
  };
  return labels[value] ? t(labels[value][0], labels[value][1]) : value;
}

function toast(message, isError = false) {
  const element = byId("toast");
  element.textContent = message;
  element.className = isError ? "toast error" : "toast";
  element.hidden = false;
  window.setTimeout(() => { element.hidden = true; }, 4500);
}

async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  headers.set("Authorization", `Bearer ${apiKey}`);
  headers.set("Accept", "application/json");
  const requestOptions = { ...options, headers };
  if (options.body && typeof options.body !== "string") {
    headers.set("Content-Type", "application/json");
    requestOptions.body = JSON.stringify(options.body);
  }
  const response = await fetch(path, requestOptions);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = payload.error?.message || `HTTP ${response.status}`;
    const error = new Error(message);
    error.status = response.status;
    throw error;
  }
  return payload;
}

function tableEmpty(body, columns, message) {
  const row = document.createElement("tr");
  const cell = make("td", message, "empty");
  cell.colSpan = columns;
  row.append(cell);
  body.replaceChildren(row);
}

async function login(event) {
  event.preventDefault();
  const input = byId("apiKeyInput");
  apiKey = input.value.trim();
  byId("loginMessage").textContent = "";
  try {
    const session = await api("/admin/api/session");
    input.value = "";
    byId("currentKey").textContent = `${session.key_id} · ${session.role}`;
    byId("loginShell").hidden = true;
    byId("appShell").hidden = false;
    datasetEditMode = false;
    byId("adminDatasetEditMode").checked = false;
    await loadView("datasets");
  } catch (error) {
    apiKey = "";
    byId("loginMessage").textContent = error.message;
    input.focus();
  }
}

function logout() {
  apiKey = "";
  byId("appShell").hidden = true;
  byId("loginShell").hidden = false;
  byId("apiKeyInput").focus();
}

async function loadOverview() {
  const data = await api("/admin/api/overview");
  byId("metricKeys").textContent = data.active_keys;
  byId("metricUploads").textContent = data.uploads;
  byId("metricArtifacts").textContent = data.artifacts;
  byId("metricDatasets").textContent = data.datasets;
  byId("metricMirrors").textContent = data.mirrors;
  byId("metricBags").textContent = data.bag_files;
  byId("metricBytes").textContent = formatBytes(data.bag_bytes);
  byId("metricMissing").textContent = data.missing_files;
  byId("metricLegacy").textContent = data.legacy_files;
  byId("bagRoot").textContent = data.bag_root;
  byId("backendVersion").textContent = data.backend_version;
  byId("frontendVersion").textContent = data.frontend_version;
  byId("processVersion").textContent = data.process_version;
  byId("serverStatus").textContent = `${t("Працює", "Healthy")} · Backend ${data.backend_version}`;
}

function populateAdminFamilyFilter() {
  const select = byId("adminFamilyFilter");
  const selected = select.value;
  const families = [...new Set(adminDatasets.map((item) => item.family))].sort((a, b) => a.localeCompare(b));
  const all = make("option", t("Усі сімейства", "All families"));
  all.value = "";
  select.replaceChildren(all, ...families.map((family) => {
    const option = make("option", family);
    option.value = family;
    return option;
  }));
  select.value = families.includes(selected) ? selected : "";
}

function populateAdminProfileFilter() {
  const select = byId("adminProfileFilter");
  const family = byId("adminFamilyFilter").value;
  const selected = select.value;
  const profiles = family
    ? [...new Set(adminDatasets.filter((item) => item.family === family).map((item) => item.profile))]
      .filter((profile) => profile !== "all")
      .sort((a, b) => a.localeCompare(b))
    : [];
  const all = make("option", family ? t("Усі профілі", "All profiles") : t("Оберіть сімейство", "Select a family"));
  all.value = "";
  select.replaceChildren(all, ...profiles.map((profile) => {
    const option = make("option", profile);
    option.value = profile;
    return option;
  }));
  select.disabled = !family;
  select.value = profiles.includes(selected) ? selected : "";
}

function renderAdminDatasets() {
  const body = byId("datasetsBody");
  byId("adminDatasetActionsHeader").hidden = !datasetEditMode;
  const query = byId("adminDatasetSearch").value.trim().toLowerCase();
  const family = byId("adminFamilyFilter").value;
  const profile = byId("adminProfileFilter").value;
  const filtered = adminDatasets.filter((item) => (
    (!family || item.family === family)
    && (!profile || item.profile === "all" || item.profile === profile)
    && (!query || `${item.id} ${item.name} ${item.profile} ${item.description}`.toLowerCase().includes(query))
  ));
  byId("adminCatalogStatus").textContent = filtered.length
    ? t(`Показано ${filtered.length} із ${adminDatasets.length}`, `Showing ${filtered.length} of ${adminDatasets.length}`)
    : t("Нічого не знайдено", "No datasets found");
  if (!filtered.length) return tableEmpty(body, datasetEditMode ? 9 : 8, t("Datasets відсутні", "No datasets"));
  const rows = filtered.map((item) => {
    const row = document.createElement("tr");
    row.append(
      make("td", item.id, "hash"),
      make("td", item.family),
      make("td", item.profile || "all", "hash"),
      make("td", item.name),
      make("td", item.measurement || "—"),
    );
    const mirrors = make("td", null, "row-actions");
    item.mirrors.forEach((mirror) => {
      mirrors.append(badge(`${mirror.format}: ${mirror.label}`, mirror.verified ? "good" : "warn"));
      if (datasetEditMode) mirrors.append(button("×", "danger", () => deleteMirror(mirror)));
    });
    if (!item.mirrors.length) mirrors.append(make("span", "—", "empty"));
    row.append(mirrors, make("td", item.local_artifacts));
    const visibility = document.createElement("td");
    visibility.append(badge(item.visible ? t("публічний", "public") : t("прихований", "hidden"), item.visible ? "good" : "warn"));
    row.append(visibility);
    if (datasetEditMode) {
      const actions = make("td", null, "row-actions");
      actions.append(
        button(t("Редагувати", "Edit"), "", () => openDataset(item)),
        button(t("Дзеркало", "Mirror"), "", () => openMirror(item)),
        button(t("Видалити", "Delete"), "danger", () => deleteDataset(item)),
      );
      row.append(actions);
    }
    return row;
  });
  body.replaceChildren(...rows);
}

async function loadDatasets() {
  const data = await api("/admin/api/datasets?per_page=100");
  adminDatasets = data.items;
  populateAdminFamilyFilter();
  populateAdminProfileFilter();
  renderAdminDatasets();
}

function openDataset(item = null) {
  editingDataset = item;
  byId("datasetDialogTitle").textContent = item ? t(`Редагування ${item.id}`, `Editing ${item.id}`) : t("Новий Dataset", "New Dataset");
  byId("datasetId").value = item?.id || "";
  byId("datasetId").disabled = Boolean(item);
  byId("datasetFamily").value = item?.family || "";
  byId("datasetProfile").value = item?.profile || "all";
  byId("datasetName").value = item?.name || "";
  byId("datasetMeasurement").value = item?.measurement || "";
  byId("datasetDescription").value = item?.description || "";
  byId("datasetHomepage").value = item?.homepage_url || "";
  byId("datasetGroundTruth").value = item?.ground_truth_url || "";
  byId("datasetConfig").value = item?.config_url || "";
  byId("datasetVisible").checked = item ? item.visible : true;
  byId("datasetDialog").showModal();
}

async function saveDataset(event) {
  event.preventDefault();
  const body = {
    family: byId("datasetFamily").value.trim(),
    profile: byId("datasetProfile").value.trim(),
    name: byId("datasetName").value.trim(),
    measurement: byId("datasetMeasurement").value.trim(),
    description: byId("datasetDescription").value.trim(),
    homepage_url: byId("datasetHomepage").value.trim(),
    ground_truth_url: byId("datasetGroundTruth").value.trim(),
    config_url: byId("datasetConfig").value.trim(),
    visible: byId("datasetVisible").checked,
  };
  try {
    if (editingDataset) {
      await api(`/admin/api/datasets/${encodeURIComponent(editingDataset.id)}`, { method: "PATCH", body });
    } else {
      body.id = byId("datasetId").value.trim();
      await api("/admin/api/datasets", { method: "POST", body });
    }
    byId("datasetDialog").close();
    editingDataset = null;
    await Promise.all([loadDatasets(), loadOverview()]);
    toast(t("Dataset збережено", "Dataset saved"));
  } catch (error) { toast(error.message, true); }
}

async function deleteDataset(item) {
  if (!window.confirm(t(`Видалити Dataset ${item.id} і всі його дзеркала?`, `Delete Dataset ${item.id} and all its mirrors?`))) return;
  try {
    await api(`/admin/api/datasets/${encodeURIComponent(item.id)}`, { method: "DELETE" });
    await Promise.all([loadDatasets(), loadOverview()]);
    toast(t("Dataset видалено", "Dataset deleted"));
  } catch (error) { toast(error.message, true); }
}

function openMirror(item) {
  mirrorDataset = item;
  byId("mirrorDialogTitle").textContent = t(`Нове дзеркало · ${item.id}`, `New mirror · ${item.id}`);
  byId("mirrorForm").reset();
  byId("mirrorDialog").showModal();
}

async function saveMirror(event) {
  event.preventDefault();
  try {
    await api(`/admin/api/datasets/${encodeURIComponent(mirrorDataset.id)}/mirrors`, {
      method: "POST",
      body: {
        format: byId("mirrorFormat").value,
        label: byId("mirrorLabel").value.trim(),
        url: byId("mirrorUrl").value.trim(),
        verified: byId("mirrorVerified").checked,
      },
    });
    byId("mirrorDialog").close();
    mirrorDataset = null;
    await Promise.all([loadDatasets(), loadOverview()]);
    toast(t("Дзеркало додано", "Mirror added"));
  } catch (error) { toast(error.message, true); }
}

async function deleteMirror(item) {
  if (!window.confirm(t(`Видалити дзеркало ${item.label}?`, `Delete mirror ${item.label}?`))) return;
  try {
    await api(`/admin/api/mirrors/${item.id}`, { method: "DELETE" });
    await Promise.all([loadDatasets(), loadOverview()]);
    toast(t("Дзеркало видалено", "Mirror deleted"));
  } catch (error) { toast(error.message, true); }
}

async function loadKeys() {
  const data = await api("/admin/api/keys?per_page=100");
  const body = byId("keysBody");
  if (!data.items.length) return tableEmpty(body, 6, t("Ключів немає", "No keys"));
  const rows = data.items.map((item) => {
    const row = document.createElement("tr");
    row.append(make("td", item.id, "hash"), make("td", item.name));
    const role = document.createElement("td"); role.append(badge(item.role, item.role === "admin" ? "good" : "")); row.append(role);
    row.append(make("td", formatDate(item.created_at)));
    const status = document.createElement("td"); status.append(badge(item.revoked_at ? t("відкликаний", "revoked") : t("активний", "active"), item.revoked_at ? "bad" : "good")); row.append(status);
    const actions = make("td", null, "row-actions");
    if (!item.revoked_at) actions.append(button(t("Відкликати", "Revoke"), "danger", () => revokeKey(item)));
    row.append(actions);
    return row;
  });
  body.replaceChildren(...rows);
}

async function createKey(event) {
  event.preventDefault();
  try {
    const result = await api("/admin/api/keys", { method: "POST", body: { name: byId("keyName").value.trim(), role: byId("keyRole").value } });
    byId("newKeyValue").textContent = result.api_key;
    byId("secretDialog").showModal();
    byId("createKeyForm").reset();
    await loadKeys();
  } catch (error) { toast(error.message, true); }
}

async function revokeKey(item) {
  if (!window.confirm(t(`Відкликати ключ ${item.name} (${item.id})?`, `Revoke key ${item.name} (${item.id})?`))) return;
  try { await api(`/admin/api/keys/${encodeURIComponent(item.id)}/revoke`, { method: "POST" }); await loadKeys(); toast(t("Ключ відкликано", "Key revoked")); }
  catch (error) { toast(error.message, true); }
}

async function loadUploads() {
  const data = await api("/admin/api/uploads?per_page=100");
  const body = byId("uploadsBody");
  if (!data.items.length) return tableEmpty(body, 8, t("Uploads відсутні", "No uploads"));
  const rows = data.items.map((item) => {
    const row = document.createElement("tr");
    row.append(make("td", item.id.slice(0, 12), "hash"), make("td", item.dataset_id), make("td", item.format), make("td", item.version), make("td", formatBytes(item.expected_size)));
    const state = document.createElement("td"); state.append(badge(stateLabel(item.state), item.state === "published" ? "good" : item.state === "rejected" ? "bad" : "warn")); row.append(state);
    row.append(make("td", formatDate(item.created_at)));
    const actions = make("td", null, "row-actions");
    if (item.state !== "published") actions.append(button(t("Видалити", "Delete"), "danger", () => deleteUpload(item)));
    row.append(actions); return row;
  });
  body.replaceChildren(...rows);
}

async function deleteUpload(item) {
  if (!window.confirm(t(`Видалити upload ${item.id}? Staging-файл також буде очищено.`, `Delete upload ${item.id}? Its staging file will also be removed.`))) return;
  try { await api(`/admin/api/uploads/${encodeURIComponent(item.id)}`, { method: "DELETE" }); await loadUploads(); toast(t("Upload видалено", "Upload deleted")); }
  catch (error) { toast(error.message, true); }
}

async function loadArtifacts() {
  const data = await api("/admin/api/artifacts?per_page=100");
  const body = byId("artifactsBody");
  if (!data.items.length) return tableEmpty(body, 8, t("Artifacts відсутні", "No artifacts"));
  const rows = data.items.map((item) => {
    const row = document.createElement("tr");
    row.append(make("td", item.dataset_id), make("td", item.format), make("td", item.version));
    const file = make("td", item.filename, "filename"); if (!item.file_exists || !item.flat_storage) file.append(" ", badge(stateLabel(!item.file_exists ? "missing" : "legacy"), "bad")); row.append(file);
    row.append(make("td", formatBytes(item.size)), make("td", item.sha256.slice(0, 16), "hash"), make("td", JSON.stringify(item.metadata), "hash"));
    const actions = make("td", null, "row-actions");
    actions.append(button("Metadata", "", () => editMetadata(item)), button(t("Видалити", "Delete"), "danger", () => deleteArtifact(item)));
    row.append(actions); return row;
  });
  body.replaceChildren(...rows);
}

function editMetadata(item) {
  editingArtifact = item;
  byId("metadataTitle").textContent = `${item.dataset_id} / ${item.format} / ${item.version}`;
  byId("metadataValue").value = JSON.stringify(item.metadata, null, 2);
  byId("metadataDialog").showModal();
}

async function saveMetadata(event) {
  event.preventDefault();
  try {
    const metadata = JSON.parse(byId("metadataValue").value);
    const path = `/admin/api/artifacts/${encodeURIComponent(editingArtifact.dataset_id)}/${encodeURIComponent(editingArtifact.format)}/${encodeURIComponent(editingArtifact.version)}`;
    await api(path, { method: "PATCH", body: { metadata } });
    byId("metadataDialog").close(); editingArtifact = null; await loadArtifacts(); toast(t("Metadata оновлено", "Metadata updated"));
  } catch (error) { toast(error.message, true); }
}

async function deleteArtifact(item) {
  if (!window.confirm(t(`Видалити запис ${item.dataset_id}/${item.format}/${item.version}?`, `Delete record ${item.dataset_id}/${item.format}/${item.version}?`))) return;
  const deleteFile = window.confirm(t("Також фізично видалити BAG-файл? Натисніть Скасувати, щоб залишити файл у каталозі.", "Also delete the BAG file physically? Select Cancel to keep the file in the directory."));
  try {
    const path = `/admin/api/artifacts/${encodeURIComponent(item.dataset_id)}/${encodeURIComponent(item.format)}/${encodeURIComponent(item.version)}`;
    await api(path, { method: "DELETE", body: { delete_file: deleteFile } });
    await Promise.all([loadArtifacts(), loadOverview()]); toast(deleteFile ? t("Artifact і файл видалено", "Artifact and file deleted") : t("Запис видалено; файл залишено", "Record deleted; file retained"));
  } catch (error) { toast(error.message, true); }
}

async function loadBags() {
  const data = await api("/admin/api/bags?per_page=100");
  const body = byId("bagsBody");
  if (!data.items.length) return tableEmpty(body, 6, t("BAG-файлів немає", "No BAG files"));
  const rows = data.items.map((item) => {
    const row = document.createElement("tr");
    row.append(make("td", item.filename, "filename"), make("td", formatBytes(item.size)), make("td", formatDate(item.modified_at, true)));
    const status = document.createElement("td"); status.append(badge(stateLabel(item.registered ? "registered" : "orphan"), item.registered ? "good" : "warn")); row.append(status);
    row.append(make("td", item.registered ? `${item.registered.dataset_id} / ${item.registered.format} / ${item.registered.version}` : "—"));
    const actions = make("td", null, "row-actions"); if (!item.registered) actions.append(button(t("Реєструвати", "Register"), "", () => chooseBag(item))); row.append(actions); return row;
  });
  body.replaceChildren(...rows);
}

function chooseBag(item) {
  byId("bagFilename").value = item.filename;
  byId("bagFormat").value = item.filename.toLowerCase().endsWith(".zip") ? "rosbag2" : "rosbag";
  byId("bagDataset").focus();
}

async function registerBag(event) {
  event.preventDefault();
  try {
    const metadata = JSON.parse(byId("bagMetadata").value);
    await api("/admin/api/bags/register", { method: "POST", body: { filename: byId("bagFilename").value, dataset_id: byId("bagDataset").value.trim(), format: byId("bagFormat").value, version: byId("bagVersion").value.trim(), metadata } });
    byId("registerBagForm").reset(); byId("bagMetadata").value = "{}"; await Promise.all([loadBags(), loadArtifacts(), loadOverview()]); toast(t("BAG-файл зареєстровано", "BAG file registered"));
  } catch (error) { toast(error.message, true); }
}

async function migrateBags() {
  if (!window.confirm(t("Перенести legacy BAG-файли в єдиний каталог? Перед перенесенням сервер перевірить розмір і SHA-256.", "Move legacy BAG files into the unified directory? The server will verify size and SHA-256 first."))) return;
  try {
    const result = await api("/admin/api/bags/migrate", { method: "POST", body: {} });
    await Promise.all([loadBags(), loadArtifacts(), loadOverview()]);
    const suffix = result.skipped.length ? t(`, пропущено: ${result.skipped.length}`, `, skipped: ${result.skipped.length}`) : "";
    toast(t(`Перенесено: ${result.migrated.length}${suffix}`, `Migrated: ${result.migrated.length}${suffix}`), result.skipped.length > 0);
  } catch (error) { toast(error.message, true); }
}

async function loadView(view) {
  activeView = view;
  document.querySelectorAll(".tab").forEach((item) => item.classList.toggle("active", item.dataset.view === view));
  document.querySelectorAll(".view").forEach((item) => { const active = item.id === `view-${view}`; item.classList.toggle("active", active); item.hidden = !active; });
  try {
    if (view === "overview") await loadOverview();
    if (view === "datasets") await loadDatasets();
    if (view === "keys") await loadKeys();
    if (view === "uploads") await loadUploads();
    if (view === "artifacts") await loadArtifacts();
    if (view === "bags") await loadBags();
  } catch (error) {
    if (error.status === 401 || error.status === 403) logout();
    toast(error.message, true);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  byId("loginForm").addEventListener("submit", login);
  byId("logoutButton").addEventListener("click", logout);
  byId("refreshButton").addEventListener("click", () => loadView(activeView));
  byId("createKeyForm").addEventListener("submit", createKey);
  byId("registerBagForm").addEventListener("submit", registerBag);
  byId("migrateBagsButton").addEventListener("click", migrateBags);
  byId("newDatasetButton").addEventListener("click", () => openDataset());
  byId("adminDatasetSearch").addEventListener("input", renderAdminDatasets);
  byId("adminFamilyFilter").addEventListener("change", () => {
    populateAdminProfileFilter();
    renderAdminDatasets();
  });
  byId("adminProfileFilter").addEventListener("change", renderAdminDatasets);
  byId("adminDatasetEditMode").addEventListener("change", (event) => {
    datasetEditMode = event.target.checked;
    byId("newDatasetButton").hidden = !datasetEditMode;
    renderAdminDatasets();
  });
  byId("datasetForm").addEventListener("submit", saveDataset);
  byId("cancelDataset").addEventListener("click", () => byId("datasetDialog").close());
  byId("mirrorForm").addEventListener("submit", saveMirror);
  byId("cancelMirror").addEventListener("click", () => byId("mirrorDialog").close());
  byId("metadataForm").addEventListener("submit", saveMetadata);
  byId("cancelMetadata").addEventListener("click", () => byId("metadataDialog").close());
  byId("copyKeyButton").addEventListener("click", async () => {
    try { await navigator.clipboard.writeText(byId("newKeyValue").textContent); toast(t("Ключ скопійовано", "Key copied")); }
    catch { toast(t("Не вдалося скопіювати автоматично; виділіть ключ вручну", "Automatic copy failed; select the key manually"), true); }
  });
  document.querySelectorAll(".tab").forEach((item) => item.addEventListener("click", () => loadView(item.dataset.view)));
  window.addEventListener("ivins-languagechange", () => {
    if (activeView === "datasets") {
      populateAdminFamilyFilter();
      populateAdminProfileFilter();
      renderAdminDatasets();
    } else {
      loadView(activeView);
    }
  });
  byId("apiKeyInput").focus();
});
