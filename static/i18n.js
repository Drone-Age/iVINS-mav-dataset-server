"use strict";

(() => {
  const copy = {
    "iVINS Datasets — головна": ["iVINS Datasets — головна", "iVINS Datasets — home"],
    "Dataset Catalog": ["Каталог даних", "Dataset Catalog"],
    "Основна навігація": ["Основна навігація", "Primary navigation"],
    "Гість": ["Гість", "Guest"],
    "Користувач": ["Користувач", "User"],
    "Адмін": ["Адмін", "Admin"],
    "Увійти": ["Увійти", "Sign in"],
    "Вийти": ["Вийти", "Sign out"],
    "Visual-inertial recordings": ["Візуально-інерційні записи", "Visual-inertial recordings"],
    "Datasets for repeatable VINS evaluation.": ["Дані для відтворюваного оцінювання VINS.", "Datasets for repeatable VINS evaluation."],
    "Єдиний каталог публічних записів, зовнішніх BAG-дзеркал та авторизованих iVINS artifacts.": ["Єдиний каталог публічних записів, зовнішніх BAG-дзеркал та авторизованих артефактів iVINS.", "A unified catalog of public recordings, external BAG mirrors, and authenticated iVINS artifacts."],
    "Статистика каталогу": ["Статистика каталогу", "Catalog statistics"],
    "datasets": ["наборів даних", "datasets"],
    "families": ["сімейств", "families"],
    "external mirrors": ["зовнішніх дзеркал", "external mirrors"],
    "Public catalog": ["Публічний каталог", "Public catalog"],
    "Доступ без реєстрації": ["Доступ без реєстрації", "Access without registration"],
    "Гості можуть переглядати весь публічний каталог і завантажувати файли із зовнішніх дзеркал.": ["Гості можуть переглядати весь публічний каталог і завантажувати файли із зовнішніх дзеркал.", "Guests can browse the complete public catalog and download files from external mirrors."],
    "Локальні server artifacts відкриваються після авторизації API-ключем.": ["Локальні серверні артефакти відкриваються після авторизації API-ключем.", "Local server artifacts become available after API-key authentication."],
    "Оновити": ["Оновити", "Refresh"],
    "Пошук": ["Пошук", "Search"],
    "ID або назва dataset": ["ID або назва Dataset", "Dataset ID or name"],
    "Сімейство": ["Сімейство", "Family"],
    "Профіль": ["Профіль", "Profile"],
    "Усі сімейства": ["Усі сімейства", "All families"],
    "Усі профілі": ["Усі профілі", "All profiles"],
    "Оберіть сімейство": ["Оберіть сімейство", "Select a family"],
    "Завантаження каталогу…": ["Завантаження каталогу…", "Loading catalog…"],
    "Рівні доступу": ["Рівні доступу", "Access levels"],
    "Перегляд Datasets і завантаження тільки із зовнішніх дзеркал.": ["Перегляд наборів даних і завантаження тільки із зовнішніх дзеркал.", "Browse datasets and download only from external mirrors."],
    "API-ключ відкриває захищені artifacts, що зберігаються на цьому сервері.": ["API-ключ відкриває захищені артефакти, що зберігаються на цьому сервері.", "An API key unlocks protected artifacts stored on this server."],
    "Керування ключами, Datasets, mirrors, uploads і BAG-файлами.": ["Керування ключами, наборами даних, дзеркалами, завантаженнями й BAG-файлами.", "Manage keys, datasets, mirrors, uploads, and BAG files."],
    "HTTP deployment · API keys are bearer credentials": ["HTTP-розгортання · API-ключі є bearer-обліковими даними", "HTTP deployment · API keys are bearer credentials"],
    "Закрити": ["Закрити", "Close"],
    "Авторизація": ["Авторизація", "Authentication"],
    "Ключ зберігається лише в пам’яті цієї вкладки та зникає після перезавантаження.": ["Ключ зберігається лише в пам’яті цієї вкладки та зникає після перезавантаження.", "The key is kept only in this tab's memory and disappears after reload."],
    "API-ключ": ["API-ключ", "API key"],
    "HTTP не шифрує ключ у мережі. Не вводьте його через недовірене підключення.": ["HTTP не шифрує ключ у мережі. Не вводьте його через недовірене підключення.", "HTTP does not encrypt the key in transit. Do not enter it over an untrusted connection."],
    "Режим редагування": ["Режим редагування", "Edit mode"],
    "Додати Dataset": ["Додати Dataset", "Add Dataset"],
    "Новий Dataset": ["Новий Dataset", "New Dataset"],
    "Назва": ["Назва", "Name"],
    "Опис": ["Опис", "Description"],
    "Показувати гостям": ["Показувати гостям", "Visible to guests"],
    "Зберегти": ["Зберегти", "Save"],
    "Скасувати": ["Скасувати", "Cancel"],
    "Адміністративний доступ": ["Адміністративний доступ", "Administrative access"],
    "Введіть API-ключ із роллю": ["Введіть API-ключ із роллю", "Enter an API key with the role"],
    ". Ключ зберігається лише в пам’яті цієї вкладки.": [". Ключ зберігається лише в пам’яті цієї вкладки.", ". The key is kept only in this tab's memory."],
    "HTTP не шифрує ключ. Використовуйте довірену мережу, VPN або захищену зовнішню маршрутизацію.": ["HTTP не шифрує ключ. Використовуйте довірену мережу, VPN або захищену зовнішню маршрутизацію.", "HTTP does not encrypt the key. Use a trusted network, VPN, or protected external routing."],
    "Публічний сайт": ["Публічний сайт", "Public site"],
    "Перевірка…": ["Перевірка…", "Checking…"],
    "Адміністративні розділи": ["Адміністративні розділи", "Administration sections"],
    "Огляд": ["Огляд", "Overview"],
    "Uploads": ["Завантаження", "Uploads"],
    "Artifacts": ["Артефакти", "Artifacts"],
    "Artifact": ["Артефакт", "Artifact"],
    "Mirrors": ["Дзеркала", "Mirrors"],
    "Local": ["Локальні", "Local"],
    "Legacy storage": ["Застаріле сховище", "Legacy storage"],
    "Ключі": ["Ключі", "Keys"],
    "BAG-файли": ["BAG-файли", "BAG files"],
    "Стан системи": ["Стан системи", "System status"],
    "Активні ключі": ["Активні ключі", "Active keys"],
    "Обсяг BAG": ["Обсяг BAG", "BAG size"],
    "Відсутні файли": ["Відсутні файли", "Missing files"],
    "Єдиний каталог BAG": ["Єдиний каталог BAG", "Unified BAG directory"],
    "Версія сервера": ["Версія сервера", "Server version"],
    "Вимір": ["Вимір", "Measurement"],
    "Видимість": ["Видимість", "Visibility"],
    "Доступ": ["Доступ", "Access"],
    "API-ключі": ["API-ключі", "API keys"],
    "Роль": ["Роль", "Role"],
    "Створити ключ": ["Створити ключ", "Create key"],
    "Створено": ["Створено", "Created"],
    "Статус": ["Статус", "Status"],
    "Чернетки й перевірка": ["Чернетки й перевірка", "Drafts and verification"],
    "Формат": ["Формат", "Format"],
    "Версія": ["Версія", "Version"],
    "Розмір": ["Розмір", "Size"],
    "Стан": ["Стан", "State"],
    "Опубліковані дані": ["Опубліковані дані", "Published data"],
    "Файл": ["Файл", "File"],
    "Пласке файлове сховище": ["Пласке файлове сховище", "Flat file storage"],
    "Мігрувати legacy storage": ["Мігрувати застаріле сховище", "Migrate legacy storage"],
    "Змінено": ["Змінено", "Modified"],
    "Зареєструвати": ["Зареєструвати", "Register"],
    "Оберіть orphan-файл у таблиці": ["Оберіть незареєстрований файл у таблиці", "Select an orphan file in the table"],
    "Показується один раз": ["Показується один раз", "Shown once"],
    "Новий API-ключ": ["Новий API-ключ", "New API key"],
    "Збережіть ключ зараз. Сервер зберіг лише digest і не зможе відновити секрет.": ["Збережіть ключ зараз. Сервер зберіг лише digest і не зможе відновити секрет.", "Save the key now. The server stored only its digest and cannot recover the secret."],
    "Копіювати": ["Копіювати", "Copy"],
    "Редагування": ["Редагування", "Editing"],
    "Artifact metadata": ["Метадані артефакту", "Artifact metadata"],
    "Metadata": ["Метадані", "Metadata"],
    "Public Dataset": ["Публічний Dataset", "Public Dataset"],
    "Public metadata (JSON)": ["Публічні метадані (JSON)", "Public metadata (JSON)"],
    "Порожнє значення автоматично стає all.": ["Порожнє значення автоматично стає all.", "A blank value automatically becomes all."],
    "External mirror": ["Зовнішнє дзеркало", "External mirror"],
    "Нове дзеркало": ["Нове дзеркало", "New mirror"],
    "Перевірене дзеркало": ["Перевірене дзеркало", "Verified mirror"],
    "Додати": ["Додати", "Add"],
  };

  const originalText = new WeakMap();
  const originalAttributes = new WeakMap();
  let language = "uk";

  function translated(source, selected = language) {
    const values = copy[source];
    if (!values) return source;
    return values[selected === "en" ? 1 : 0];
  }

  function translateTextNode(node) {
    const source = originalText.has(node) ? originalText.get(node) : node.nodeValue;
    if (!originalText.has(node)) originalText.set(node, source);
    const trimmed = source.trim();
    if (!trimmed || !copy[trimmed]) return;
    const leading = source.match(/^\s*/u)?.[0] || "";
    const trailing = source.match(/\s*$/u)?.[0] || "";
    node.nodeValue = `${leading}${translated(trimmed)}${trailing}`;
  }

  function translateAttributes(element) {
    const stored = originalAttributes.get(element) || {};
    ["aria-label", "placeholder", "title"].forEach((name) => {
      if (!element.hasAttribute(name) && stored[name] === undefined) return;
      const source = stored[name] === undefined ? element.getAttribute(name) : stored[name];
      stored[name] = source;
      element.setAttribute(name, translated(source));
    });
    originalAttributes.set(element, stored);
  }

  function apply(root = document) {
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    let node = walker.nextNode();
    while (node) {
      if (!node.parentElement?.matches("script, style")) translateTextNode(node);
      node = walker.nextNode();
    }
    const elements = root.querySelectorAll ? root.querySelectorAll("[aria-label], [placeholder], [title]") : [];
    elements.forEach(translateAttributes);
    document.documentElement.lang = language;
    document.title = language === "en" ? "DataSetsManager Server" : "Сервер DataSetsManager";
    document.querySelectorAll("[data-language-selector]").forEach((selector) => { selector.value = language; });
  }

  function setLanguage(value) {
    language = value === "en" ? "en" : "uk";
    apply(document);
    window.dispatchEvent(new CustomEvent("dsm-languagechange", { detail: { language } }));
    window.dispatchEvent(new CustomEvent("ivins-languagechange", { detail: { language } }));
  }

  window.DSM_I18N = {
    apply,
    getLanguage: () => language,
    setLanguage,
    t: (uk, en) => language === "en" ? en : uk,
  };
  // Frontend 4.x compatibility alias; removed in Frontend 5.0.
  window.IVINS_I18N = window.DSM_I18N;

  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("[data-language-selector]").forEach((selector) => {
      selector.addEventListener("change", () => setLanguage(selector.value));
    });
    apply(document);
  });
})();
