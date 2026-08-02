# Версіонування компонентів

[English version](VERSIONING.md)

Репозиторій містить чотири компоненти з незалежними версіями:

| Компонент | Область | Поточна версія | Git tag |
|---|---|---:|---|
| Backend | HTTP API, автентифікація, сховище, міграції бази й runtime сервера | 4.0.0 | `backend-v4.0.0` |
| Frontend | Публічний каталог та адміністративний вебінтерфейс | 4.0.0 | `frontend-v4.0.0` |
| Залежність Process | Канонічні політики у `DataSetsManager/DataSetsManager` | 2.0.0 | `process-v2.0.0` |
| Distribution | Офлайн-комплекти, інсталятори, package manifests і автоматизація розгортання | 2.0.0 | `distribution-v2.0.0` |

`versions.json` — канонічний машинозчитуваний маніфест. Backend завантажує й
перевіряє його під час запуску та віддає через `GET /versions`. Ті самі значення
повертаються у відповідях health, session, catalog і administration.

Distribution не залежить від конкретної технології. Одна версія Distribution
може надавати один чи кілька форматів: `docker-bundle`, `windows-portable` або
`windows-msi`. Додавання сумісного формату змінює Distribution без примусової
зміни Backend, Frontend або Process.

## Семантичне версіонування

Кожний компонент незалежно дотримується SemVer:

- MAJOR — несумісна зміна контракту, інтерфейсу або governance;
- MINOR — зворотно сумісна можливість або правило;
- PATCH — зворотно сумісне виправлення без нового контракту.

Реліз змінює тільки компоненти, яких стосується схвалена зміна. Незмінний
компонент зберігає свою версію й наявний тег.

Версії Process є незмінними нормативними snapshots. Редакційне виправлення,
здатне змінити тлумачення, потребує щонайменше PATCH-релізу. Нові дозволи,
заборони, обов'язкові gates або відповідальності потребують MINOR чи MAJOR
відповідно до сумісності.

## Маніфест сумісності

Обмеження сумісності використовують npm-style SemVer ranges:

```json
{
  "backend": "4.0.0",
  "frontend": "4.0.0",
  "process": "2.0.0",
  "distribution": "2.0.0",
  "compatibility": {
    "frontend_requires_backend": ">=4.0.0 <5.0.0",
    "process_applies_to_backend": ">=4.0.0 <5.0.0",
    "process_applies_to_frontend": ">=4.0.0 <5.0.0",
    "process_applies_to_distribution": ">=2.0.0 <3.0.0",
    "distribution_packages_backend": ">=4.0.0 <5.0.0",
    "distribution_packages_frontend": ">=4.0.0 <5.0.0",
    "distribution_requires_process": ">=2.0.0 <3.0.0"
  }
}
```

Маніфест оновлюється в тому самому reviewed commit, що й версія компонента.
Пару Frontend/Backend поза заявленим діапазоном розгортати заборонено. Реліз
Process застосовується лише до заявлених ним діапазонів компонентів.

## Ідентифікатори релізів

Нові релізи використовують теги з префіксом компонента:

- `backend-vMAJOR.MINOR.PATCH`;
- `frontend-vMAJOR.MINOR.PATCH`;
- `process-vMAJOR.MINOR.PATCH`;
- `distribution-vMAJOR.MINOR.PATCH`.

Історичні агреговані теги `vX.Y.Z` залишаються чинними історичними записами,
але для нових релізів не використовуються. Тег Docker image відповідає версії
Backend як runtime-компонента. ZIP/MSI відповідають Distribution і декларують
усі версії у `package-manifest.json`. Runtime-версії доступні через `/versions`.

Кожний реліз компонента має посилатися на спільний commit SHA, component
changelog і відповідний маніфест сумісності.
