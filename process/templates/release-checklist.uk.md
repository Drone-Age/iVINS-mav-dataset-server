# Контрольний список релізу компонента

[English template](release-checklist.md)

- Commit SHA:
- Backend:
- Frontend:
- Process:
- Distribution:
- Маніфест сумісності перевірено:

## До релізу

- [ ] Change request схвалено
- [ ] Критерії приймання виконано
- [ ] Component changelogs оновлено
- [ ] Unit/integration/security тести пройдено
- [ ] Compose configuration валідовано
- [ ] Production image зібрано
- [ ] Offline package manifest відповідає `versions.json`
- [ ] Внутрішній SHA256SUMS і ZIP sidecar перевірено
- [ ] Bundle встановлюється без Git, build або pull
- [ ] Critical/High vulnerability gate пройдено або exception схвалено
- [ ] Посилання на backup і rollback зафіксовано
- [ ] Робоче дерево чисте

## Публікація

- [ ] Backend component tag/release створено, якщо компонент змінено
- [ ] Frontend component tag/release створено, якщо компонент змінено
- [ ] Process component tag/release створено, якщо компонент змінено
- [ ] Releases вказують на reviewed commit
- [ ] Distribution component tag/release створено, якщо компонент змінено

## Розгортання й перевірка

- [ ] `/health` і `/versions` відповідають маніфесту
- [ ] Smoke test публічного каталогу пройдено
- [ ] User/Admin authorization smoke test пройдено
- [ ] BAG storage/integrity smoke test пройдено
- [ ] Restart policy перевірено
- [ ] Результат записано; за потреби виконано rollback або відкрито incident
