# DataSetsManager Distribution

[English version](DISTRIBUTION.md)

Distribution — незалежно версіонований рівень постачання DataSetsManager
Server. Він пакує сумісні версії Backend, Frontend і Process в один
інсталяційний артефакт, не змінюючи їхні component versions.

Поточна версія Distribution: **2.0.0**

## Формати пакетів

- `docker-bundle`: автономний OCI image і Compose-розгортання. Потребує Docker
  Engine із Compose, але не потребує Git або Інтернету.
- `windows-portable`: standalone EXE, скрипти Windows Service, checksums і
  контракт постійних даних; розгортання не потребує ані Git, ані Docker.
- `windows-msi`: зарезервований майбутній підписаний MSI wrapper навколо того
  самого service і package-manifest contract.

Додавання сумісного формату збільшує MINOR Distribution. Порушення package
manifest, installer command contract або поведінки upgrade/rollback збільшує
MAJOR. Виправлення збільшують PATCH.

## Автономний Docker bundle

Створений ZIP містить:

- повний Docker image як архів `images/*.tar`;
- `compose.release.yaml` без секції `build` і з `pull_policy: never`;
- `package-manifest.json` і канонічний `versions.json`;
- `SHA256SUMS` та SHA-256 sidecar для ZIP;
- `install.ps1`, `update.ps1`, `rollback.ps1`, `verify.ps1` і
  `new-admin-key.ps1`;
- документи Process, versioning і component changelog.

Пакет ніколи не містить API-ключів, бази SQLite, BAG-файлів або інших runtime
даних. Каталог даних залишається зовнішнім і постійним між змінами Distribution.

## Portable Windows Service package

Збирайте на Windows через `tools/build-windows-package.ps1`. Скрипт створює
PyInstaller executable із Python runtime, використовує Waitress як HTTP service
host і пакує tools install/uninstall/verify/key-management. Runtime-дані за
замовчуванням містяться у `%ProgramData%\DataSetsManager\Server\var`; усі BAG є
прямими дочірніми файлами його каталогу `bags`. Build-залежності беруться з
`requirements-windows.lock`; `verify-integrity.ps1` перевіряє розпакований пакет
до встановлення служби.

## Збірка

У source tree з Docker Buildx:

```powershell
.\tools\build-release-bundle.ps1
```

Ціль за замовчуванням — `linux/amd64`. Іншу одиничну ціль можна створити через
`-Platform linux/arm64`. Результат міститься у `dist/` і може бути скопійований
на автономний сервер.

## Встановлення без Git

Розпакуйте ZIP і виконайте:

```powershell
Copy-Item .env.example .env
.\install.ps1
.\new-admin-key.ps1 -Name initial-admin
```

Installer перевіряє кожний файл пакета, локально завантажує image, валідовує
Compose, запускає service, перевіряє `/health` і `/versions` та підтверджує, що
розгорнуті component versions відповідають package manifest.

Для оновлення з попереднім backup використовуйте `update.ps1`. Для rollback
передайте `rollback.ps1` шлях до раніше розпакованого bundle. Автоматичний
rollback не відновлює runtime-дані; якщо міграція даних цього потребує,
відновлюйте їх лише з окремо перевіреної резервної копії.
