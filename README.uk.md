# DataSetsManager Server

[English version](README.md)

Сумісний комплект містить **Backend 4.0.0**, **Frontend 4.0.0**,
**Process 2.0.0** і **Distribution 2.1.0**. Це двомовний публічний вебкаталог
наборів візуально-інерціальних даних і автентифіковане незмінне сховище
локальних артефактів iVINS.

Публічний сайт за адресою `/` доступний без ключа. Він показує **Datasets** у
таблицях за сімействами, побудованих за зразком каталогу
[`DataSetsManager/client`](https://github.com/DataSetsManager/client): стабільний
ID, назва набору, довжина/розмір, посилання ROS Bag, ROS Bag2, ground truth і
конфігурації. Кожний Dataset також має профіль iVINS у межах свого сімейства;
доступні значення фільтра профілів залежать від вибраного сімейства.

## Модель доступу

- **Гість**: не має ключа; може переглядати публічні Datasets і переходити до
  зовнішніх HTTP/HTTPS-дзеркал BAG. Гість не може завантажувати файли, які
  зберігаються на цьому сервері.
- **Користувач**: входить за згенерованим сервером API-ключем; додатково може
  завантажувати локальні артефакти за короткочасним одноразовим квитком.
- **Адмін**: має права користувача та вбудований режим редагування Dataset у
  звичайному фільтрованому каталозі. За замовчуванням цей режим вимкнений.
  `/admin` залишається доступним для керування API-ключами, дзеркалами,
  завантаженнями, артефактами й BAG-файлами та відкривається на Datasets.

Браузер тримає введений API-ключ лише в пам'яті сторінки. Ключ ніколи не
потрапляє до URL, cookie, local storage або session storage та забувається після
перезавантаження сторінки.

Backend 4 обслуговує HTTP лише всередині приватної Compose-мережі. Distribution
2.1.0 відкриває Caddy на портах 80/443, перенаправляє HTTP на HTTPS, автоматично
керує публічним сертифікатом і додає HSTS. Не передавайте bearer-ключ через
незашифрований HTTP endpoint, крім loopback test-server.

## Версії компонентів

Backend, Frontend, Process і Distribution мають незалежні SemVer-версії.
Канонічний маніфест сумісності — [versions.json](versions.json); Backend
перевіряє його під час запуску, а `GET /versions` повертає його вміст. Застаріле
поле відповіді `server_version` залишається псевдонімом версії Backend.

Нові Git-теги й GitHub Releases мають вигляд `backend-vX.Y.Z`,
`frontend-vX.Y.Z`, `process-vX.Y.Z` і `distribution-vX.Y.Z`. Тег Docker image
відповідає Backend, а інсталяційні комплекти — Distribution. Правила сумісності
й випуску описані у [VERSIONING.uk.md](VERSIONING.uk.md), автономне
розгортання — у [distribution/DISTRIBUTION.uk.md](distribution/DISTRIBUTION.uk.md),
а нормативні політики й регламенти — у
[process/PROCESS.uk.md](process/PROCESS.uk.md).

## Швидкий запуск Docker

```powershell
Copy-Item .env.example .env
New-Item -ItemType Directory -Path var -Force
docker compose build

# Створення першого admin-ключа локально. Відкритий ключ показується один раз.
docker compose run --rm --no-deps server `
  python api_keys.py create --name initial-admin --role admin

docker compose up -d
Invoke-RestMethod http://127.0.0.1:8080/health
```

Відкрийте:

- `http://127.0.0.1:8080/` — публічний каталог Datasets;
- `http://127.0.0.1:8080/admin` — адміністрування.

## Автономне розгортання без Git

Distribution 2.1.0 створює повний ZIP для цільової архітектури. Пакет містить
збережений Docker image, автономний Compose-файл, маніфести цілісності та
скрипти install/update/rollback. База, BAG-файли й API-ключі до нього не входять.

```powershell
.\tools\build-release-bundle.ps1
```

Скопіюйте створені ZIP і sidecar `.sha256` на цільову машину, перевірте
sidecar, розпакуйте ZIP і виконайте:

```powershell
Copy-Item .env.example .env
.\install.ps1
.\new-admin-key.ps1 -Name initial-admin
.\new-user-key.ps1 -Name dataset-e2e
.\verify-tls.ps1
```

Для встановлення пакета потрібні Docker Engine і Compose, але не потрібні Git
або registry: образи Server і зафіксованого Caddy вже містяться у ZIP. Для
першої видачі й поновлення публічного сертифіката потрібні коректний DNS та
вихідний доступ до ACME. Зберігайте одноразово показаний e2e `user`-ключ лише у
сховищі секретів і передавайте клієнту як `DSM_SERVER_TOKEN`.

Дивіться [посібник Distribution](distribution/DISTRIBUTION.uk.md) і
[свідчення локального приймання Distribution 2.0](docs/acceptance/distribution-2.0.0.uk.md).

## API-ключі

Нові ключі завжди генеруються на сервері й показуються лише один раз. У базі
зберігаються тільки ID ключа та SHA-256 digest.

```powershell
# User-ключ для захищених локальних завантажень
docker compose run --rm --no-deps server `
  python api_keys.py create --name dataset-user --role user

# Перелік метаданих без секретів
docker compose run --rm --no-deps server python api_keys.py list

# Негайне відкликання
docker compose run --rm --no-deps server `
  python api_keys.py revoke 0123456789abcdef
```

Перший admin-ключ створюється через CLI. Автентифікований адмін може створювати
наступні ключі ролей `user` або `admin` через вебінтерфейс. Web API забороняє
відкликати останній активний admin-ключ.

## Публічні Datasets і дзеркала

Каталог SQLite містить окремі записи `datasets` і `mirrors`. Дзеркала повинні
мати абсолютні HTTP/HTTPS URL і чітко позначаються як зовнішні посилання. Гості
бачать лише дзеркала зі статусом verified. Сервер їх не проксіює й не завантажує.

Початковий каталог містить 57 записів, створених із маніфестів:

- EuRoC MAV;
- TUM-VI;
- RPNG AR Table і RPNG OpenVINS;
- UZH-FPV;
- KAIST Urban і KAIST VIO;
- iVINS.

Початкове наповнення ідемпотентне й не перезаписує зміни адміністратора. Адміни
можуть додавати, редагувати, приховувати й видаляти Datasets, а також додавати
або видаляти зовнішні дзеркала через контрольовані endpoints. Довільний SQL
навмисно відсутній.

### Профілі Dataset

`profile` — стабільний ідентифікатор у нижньому регістрі, наприклад `all`,
`dev_01` або `dev_04`. Якщо значення не задано або воно порожнє, сервер зберігає
`all`: Dataset стосується кожного профілю свого сімейства. Імена профілів мають
область дії сімейства: селектор профілів активується після вибору сімейства й
показує лише його специфічні профілі. Фільтрація за конкретним профілем також
включає Datasets із `all` у цьому сімействі.

Інтерфейс адміністратора явно показує й редагує це значення. Метадані
завантаження артефакту та ручної реєстрації BAG також можуть містити `profile`;
остаточну перевірку завжди виконує сервер.

Під час першого запуску Backend 4.x наявні рядки Dataset мігрують без видалення:
відсутні, порожні та колишні `general`, `dev_0`, `dev_2`, `dev_3`, `dev_4` і
`dev4` перетворюються на канонічні `all`/`dev_01`…`dev_04`. Специфічні профілі
зберігаються, а вбудований запис `iv.dev.4.ff.1` залишається класифікованим як
`dev_04`.

## Мови інтерфейсу

Публічний каталог та інтерфейс адміністратора перемикаються між українською й
англійською. Вибір мови впливає лише на відображення та не змінює вміст Dataset
або стан авторизації.

## Завантаження локальних артефактів

Прямі маршрути локального завантаження потребують bearer-ключа `user` або
`admin`. Для завантаження у браузері автентифікований сайт запитує одноразовий
квиток на 60 секунд. Зберігається лише digest квитка, а повторне використання
повертає `404`.

```powershell
$headers = @{ Authorization = "Bearer $env:DSM_CLIENT_API_KEY" }
$ticket = Invoke-RestMethod `
  http://127.0.0.1:8080/v1/datasets/iv.dev.4.ff.1/artifacts/rosbag/1/download-ticket `
  -Method Post -Headers $headers -ContentType application/json -Body '{}'

Invoke-WebRequest ("http://127.0.0.1:8080" + $ticket.download_url) -OutFile data.bag
```

## HTTP API

| Доступ | Метод | Шлях | Призначення |
|---|---|---|---|
| Public | `GET` | `/health` | Мінімальна перевірка життєздатності |
| Public | `GET` | `/public/api/datasets` | Видимі Datasets і зовнішні дзеркала |
| Public | `GET` | `/versions` | Версії компонентів і сумісність |
| Key | `GET` | `/auth/session` | Визначити роль API-ключа |
| User/Admin | `GET` | `/v1/catalog` | Каталог локальних артефактів |
| User/Admin | `GET` | `/v1/datasets/{id}/artifacts/{format}/{version}/download` | Пряме автентифіковане завантаження |
| User/Admin | `POST` | `/v1/datasets/{id}/artifacts/{format}/{version}/download-ticket` | Квиток завантаження для браузера |
| Admin | `POST` | `/v1/uploads` | Створити або відновити сесію завантаження |
| Admin | `PUT` | `/v1/uploads/{id}/content` | Потоково прийняти й перевірити байти |
| Admin | `POST` | `/v1/uploads/{id}/publish` | Опублікувати незмінну версію |
| Admin | `*` | `/admin/api/*` | Контрольоване адміністрування |

Публічний каталог і погашення квитків завантаження мають незалежні обмеження
частоти за адресою клієнта.

## Зберігання й резервне копіювання

База за замовчуванням — `var/catalog.sqlite3`. Кожний локальний артефакт `.bag`
і `.zip` є прямим дочірнім файлом `var/bags/`; незавершені завантаження містяться
у `var/staging/`. Резервуйте й відновлюйте повне дерево `var/` як одне ціле.

Опубліковані ідентичності `(dataset_id, format, version)` залишаються незмінними.
Адмін може перенести застарілі вкладені шляхи v2 до плоского каталогу BAG лише
після серверної перевірки розміру та SHA-256.

## Оновлення до Backend/Frontend 4.0.0, Process 2.0.0 і Distribution 2.1.0

1. Створіть резервну копію повного каталогу `var/`.
2. Розгорніть image Backend 4.0.0 з тим самим каталогом даних.
3. Наявні ключі `admin` залишаться адмінами; ключі `reader` і `publisher`
   мігрують до `user`.
4. Відсутні, порожні й `general`-профілі Dataset стануть `all`; перегляньте
   профілі кожного сімейства в каталозі й за потреби призначте `dev_01` тощо.
5. Перевірте початкові публічні Datasets і дзеркала у `/admin`.
6. Переконайтеся, що `/health` показує Backend 4.0.0, Frontend 4.0.0,
   Process 2.0.0, Distribution 2.1.0, `schema_version: 1.0` і
   `key_store_ready: true`.
7. Переконайтеся, що `/versions` відповідає `versions.json` і діапазонам
   сумісності розгорнутих компонентів.

## Перевірка

```powershell
docker compose config --quiet
docker compose build
docker run --rm --entrypoint python `
  -v "${PWD}:/src:ro" -w /src datasetsmanager-server:4.0.0 `
  -m unittest discover -s tests -v

.\tools\build-release-bundle.ps1 -SkipBuild

docker scout cves datasetsmanager-server:4.0.0 `
  --only-severity critical,high
```

Нормативний контракт локальних артефактів міститься у [`contract/`](contract/).
