#!/usr/bin/env python3
"""Windows Service host and server-side key CLI for DataSetsManager Server."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import servicemanager
import win32event
import win32service
import win32serviceutil
from waitress.server import create_server

import api_keys
import server


def configure_defaults() -> None:
    root = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "DataSetsManager" / "Server"
    os.environ.setdefault("DSM_DATA_ROOT", str(root / "var"))
    os.environ.setdefault("DSM_BAG_ROOT", str(root / "var" / "bags"))


class DataSetsManagerService(win32serviceutil.ServiceFramework):
    _svc_name_ = "DataSetsManagerServer"
    _svc_display_name_ = "DataSetsManager Server"
    _svc_description_ = "Public dataset catalog and authenticated local artifact server."

    def __init__(self, args):
        super().__init__(args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        self.http = None

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        if self.http is not None:
            self.http.close()
        win32event.SetEvent(self.stop_event)

    def SvcDoRun(self):
        configure_defaults()
        server.connect().close()
        api_keys.connect().close()
        host = str(server.settings.value("BIND_ADDRESS", "127.0.0.1"))
        port = server.settings.integer("PORT", 8080)
        servicemanager.LogInfoMsg(f"DataSetsManager Server starting on {host}:{port}")
        self.http = create_server(server.app, host=host, port=port, threads=4)
        self.http.run()


def main() -> int:
    configure_defaults()
    if len(sys.argv) > 1 and sys.argv[1] == "key":
        return api_keys.main(sys.argv[2:])
    win32serviceutil.HandleCommandLine(DataSetsManagerService)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
