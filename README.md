# PrintMySpoolLabel

Drag-and-drop printing of 3D filament spool labels on a NIIMBOT D110M.

The workflow supports PNG exports from [3D Filament Profiles](https://3dfilamentprofiles.com) and uses Labelife `.aml` exports as a data source for the compact 40 x 12 mm layout.

## Validated Printer Setup

- Printer: NIIMBOT D110M
- Connection: USB serial
- Tested port: `COM4`
- Print task: `D110M_V4`
- Label: `40 x 12 mm`
- Raster: `320 x 96 px` at 203 dpi
- Print direction: `left`
- Mirroring: disabled
- Density: `3`
- Label type: `1`
- Copies: selectable from `1` to `99`

## Installation

Auf einem neuen Windows-Rechner muessen Git, Python 3.12 oder neuer und Node.js LTS installiert sein. Danach kann die Einrichtung per Doppelklick gestartet werden:

```text
install-print-my-spool-label.bat
```

Das Script installiert automatisch den NiimBlue-Commandline-Backend und alle Python-Abhaengigkeiten. Fehlen Git, Python oder Node.js, fragt das Script, ob die jeweilige Komponente ueber `winget` installiert werden soll. Dafuer muss der Windows-Paketmanager `winget` verfuegbar sein.

## Manual Setup

Install the NiimBlue command-line backend:

```powershell
npm.cmd install --global @mmote/niimblue-node
```

Install the Python UI dependencies:

```powershell
python -m pip install -r requirements.txt
```

Start the application:

```powershell
python .\src\app.py
```

Alternatively, double-click `start-print-my-spool-label.bat`. The batch file updates the repository first and then starts the application.

Drop a PNG or AML label into the window, verify the preview, and click `Drucken`. AML files are rendered into the compact 40 x 12 mm layout. The serial port defaults to `COM4` and can be changed in the window.
