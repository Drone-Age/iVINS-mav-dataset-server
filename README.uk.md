# Сервер DataSetsManager

[English version](README.md)

DataSetsManager Server — двомовний публічний каталог наборів даних і
автентифіковане сховище локальних `.bag`/`.zip`. Сумісний пакет містить Backend
4.0.0, Frontend 4.0.0, залежність Process 2.0.0 і Distribution 2.0.0.

## Доступ

- **Гість** без ключа переглядає Datasets і завантажує лише з перевірених
  зовнішніх mirrors.
- **Користувач** входить за server-generated API key і може завантажувати
  локальні artifacts через одноразовий короткоживучий ticket.
- **Адмін** за замовчуванням відкриває каталог адміністратора. Фільтри такі
  самі, як у публічному каталозі; режим редагування початково вимкнений.

Ключ зберігається лише в пам’яті вкладки. HTTP не шифрує bearer credentials,
тому зовнішній маршрут має завершувати TLS або проходити через довірену VPN.

## Профілі

Профілі належать конкретному сімейству. Після вибору сімейства інтерфейс показує
лише його профілі. Канонічний профіль за замовчуванням — `all`. Backend 4.x
приймає aliases `general`, `dev_0`, `dev_2`, `dev_3`, `dev_4`, `dev4` і
нормалізує їх до `all`, `dev_01`…`dev_04`. Стабільні dataset ID не змінюються.

## Конфігурація і запуск

Канонічні змінні мають префікс `DSM_*`. Старі `IVINS_*` підтримуються до
Backend 5.0 з попередженням; якщо задані обидві, перемагає `DSM_*`.

```powershell
Copy-Item .env.example .env
docker compose build
docker compose run --rm --no-deps server `
  python api_keys.py create --name initial-admin --role admin
docker compose up -d
Invoke-RestMethod http://127.0.0.1:8080/health
```

Нові ключі генеруються з префіксом `dsm_`; уже видані `ivins_` залишаються
дійсними до Backend 5.0. База за замовчуванням — `var/catalog.sqlite3`, а всі
локальні `.bag`/`.zip` є прямими дочірніми файлами `var/bags`.

## Розгортання без Git

- `tools/build-release-bundle.ps1` створює автономний Docker/OCI ZIP;
- `tools/build-windows-package.ps1` створює standalone EXE і Windows Service
  package без Git і Docker на цільовій машині;
- `windows-msi` зарезервовано для наступного Distribution release.

Робочі база, `.bag` та ключі до release package не входять. Перед оновленням
резервуйте весь data root, а після — перевіряйте `/health`, `/versions` і
`PRAGMA integrity_check`.

## API

Маршрути `/v1` сумісні з попередньою версією. Публічні endpoints:
`/health`, `/versions`, `/public/api/datasets`. Захищені `/v1/*` потребують
ключа User/Admin, а `/admin/api/*` — Admin. Детальний контракт міститься в
[`contract/`](contract/) і [`schemas/`](schemas/).
