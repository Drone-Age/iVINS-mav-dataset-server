# Майбутній формат пакета: Windows MSI

[English version](windows-msi.md)

Статус: зарезервовано як `windows-msi`; у Distribution 2.0.0 не реалізовано.

Майбутній Windows Installer буде додатковим форматом Distribution, а не заміною
версіонування Backend, Frontend або Process. Його package manifest повинен
декларувати ті самі чотири версії компонентів і обмеження сумісності.

Мінімальні вимоги:

- встановлювати Backend і Frontend без Git, Docker або Інтернету;
- запускати Backend як Windows Service під окремим least-privilege account;
- зберігати змінні дані у налаштовуваному постійному каталозі, за замовчуванням
  `%ProgramData%\DataSetsManager\Server`;
- тримати всі BAG/ZIP у налаштованому єдиному BAG-каталозі;
- генерувати API-ключі лише через установлений server-side CLI;
- підтримувати unattended install, upgrade, repair і uninstall;
- за замовчуванням зберігати дані під час upgrade та uninstall;
- надавати перевірки версій і стану, еквівалентні `/versions` і `/health`;
- до зміни системи перевіряти checksums пакета й Authenticode signature;
- записувати свідчення install/upgrade/rollback без секретів у журналах;
- мати перевірений rollback до сумісної попередньої Distribution.

Перший сумісний MSI збільшує MINOR Distribution. Зміна, що порушує Distribution
manifest або automation contract, потребує наступної MAJOR-версії Distribution.
