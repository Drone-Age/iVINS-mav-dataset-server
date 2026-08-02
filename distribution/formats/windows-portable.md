# Windows portable service package

[Українська версія](windows-portable.uk.md)

Distribution 2.0.0 implements `windows-portable` as a PyInstaller one-file
executable plus PowerShell lifecycle tools. The executable hosts Flask through
Waitress and implements the Windows Service control protocol through pywin32.

The package installs `DataSetsManagerServer`, keeps mutable data outside the
package, creates API keys only through `datasetsmanager-server.exe key`, and
supports health/version verification. It contains no key, database, or BAG.

The future `windows-msi` package may wrap this contract but must not change its
data ownership, authentication, or component compatibility rules.
