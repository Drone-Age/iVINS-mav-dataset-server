# Future package format: Windows MSI

[Українська версія](windows-msi.uk.md)

Status: reserved as `windows-msi`; not implemented in Distribution 2.0.0.

The future Windows Installer will be an additional Distribution format, not a
replacement for Backend, Frontend or Process versioning. Its package manifest
must declare the same four component versions and compatibility constraints.

Minimum requirements:

- install Backend and Frontend without Git, Docker or Internet access;
- run Backend as a Windows Service under a dedicated least-privilege account;
- store mutable data under a configurable persistent location, defaulting to
  `%ProgramData%\DataSetsManager\Server`;
- keep all BAG/ZIP artifacts in the configured single BAG directory;
- generate API keys only through the installed server-side CLI;
- support unattended install, upgrade, repair and uninstall modes;
- preserve data by default during upgrade and uninstall;
- expose version and health checks equivalent to `/versions` and `/health`;
- verify package checksums and an Authenticode signature before mutation;
- record install/upgrade/rollback evidence without logging secrets;
- provide a tested rollback path to a compatible prior Distribution.

A compatible first MSI increments Distribution MINOR. A change that breaks the
Distribution manifest or automation contract requires the next Distribution
MAJOR.
