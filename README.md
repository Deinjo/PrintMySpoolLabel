# PrintMySpoolLabel

PrintMySpoolLabel erzeugt kompakte Filament-Labels fuer den NIIMBOT D110M. Die Anwendung laedt PNG- und Labelife-AML-Dateien per Drag & Drop, bereitet sie auf ein festes Format von `40 x 12 mm` auf und uebergibt das fertige Label an `niimblue-node`.

## Funktionen

- Drag & Drop fuer PNG- und AML-Dateien
- Vorschau des fertigen `320 x 96 px`-Labels
- Unterstuetzung fuer strukturierte und gerasterte AML-Dateien
- OCR-Auswertung von Raster-AMLs direkt aus dem eingebetteten Bild
- Direkte Uebernahme des Herstellerlogos aus Raster-AMLs
- Direkte Uebernahme des QR-Codes aus Raster-AMLs
- QR-Code-Erzeugung aus strukturierten AML-XML-Daten
- Auswahl von `1` bis `99` Kopien
- Konfigurierbarer serieller Port mit gespeichertem Standardwert `COM4`
- Fortschrittsanzeige waehrend der AML-Verarbeitung
- Asynchrone AML-Verarbeitung, damit die GUI bedienbar bleibt

## Eingabeformate

### PNG

PNG-Dateien werden als fertiges Labelbild verwendet. Das Bild wird in der Vorschau innerhalb des Zielrahmens angezeigt und beim Druck auf `320 x 96 px` beziehungsweise `40 x 12 mm` eingepasst.

PNG ist geeignet, wenn das Label bereits fertig gestaltet ist oder keine Daten aus dem Bild extrahiert werden muessen.

### Struktur-AML

Eine Struktur-AML ist eine Labelife-AML-Datei mit separaten XML-Elementen fuer Inhalte. Typischerweise enthaelt sie:

- `<Text>` fuer Hersteller, Material, Farbe und technische Werte
- `<Qrcode>` mit einem `webContent`-Wert
- `<Image>` fuer das Herstellerlogo

Die Anwendung liest die Werte aus dem XML und rendert sie in das feste PrintMySpoolLabel-Layout. Der QR-Code wird aus dem XML-Inhalt neu erzeugt. Das Layout bleibt dadurch auch bei unterschiedlichen AML-Groessen einheitlich.

### Raster-AML

Eine Raster-AML enthaelt das komplette Label als eingebettetes Bild, bei den bisher untersuchten Exporten mit `800 x 600 px` beziehungsweise `40 x 30 mm`. Sie enthaelt keine separaten Text- oder QR-Elemente.

Die Anwendung erkennt dieses Format automatisch und verarbeitet ausschliesslich das eingebettete Rasterbild:

- Herstellerlogo wird als Grafik aus dem oberen Bildbereich ausgeschnitten und proportional uebernommen.
- QR-Code wird direkt aus dem Rasterbild ausgeschnitten und nicht neu erzeugt.
- Material, Farbe, Hex-Code und technische Werte werden per OCR aus festen Bildbereichen gelesen.
- Der Dateiname wird nicht als Datenquelle verwendet.
- Ein indeterminierter Fortschrittsbalken zeigt die laufende OCR-Verarbeitung an.

Die Raster-AML-Verarbeitung setzt `rapidocr-onnxruntime` voraus. Die Abhaengigkeit wird durch das Installationsscript beziehungsweise `requirements.txt` installiert.

## Zielgeraet und Druckparameter

- Drucker: NIIMBOT D110M
- Verbindung: USB-Seriell
- Getesteter Port: `COM4`
- NiimBlue Print Task: `D110M_V4`
- Zielformat: `40 x 12 mm`
- Zielraster: `320 x 96 px`
- Aufloesung: `203 dpi`
- Druckrichtung: `left`
- Spiegelung: deaktiviert
- Label Type: `1`
- Density: `3`
- Threshold: `128`
- Kopien: `1` bis `99`

## Installation

### One-Click-Installation

Auf einem neuen Windows-Rechner muessen Git, Python 3.12 oder neuer und Node.js LTS verfuegbar sein. Danach kann die Einrichtung per Doppelklick gestartet werden:

```text
install-print-my-spool-label.bat
```

Das Script installiert:

- Python-Abhaengigkeiten aus `requirements.txt`
- `@mmote/niimblue-node` global ueber npm

Fehlen Git, Python oder Node.js, fragt das Script, ob die jeweilige Komponente ueber `winget` installiert werden soll. Dafuer muss der Windows-Paketmanager `winget` verfuegbar sein. Nach einer Systeminstallation startet sich das Script automatisch neu, damit die neuen PATH-Eintraege aktiv werden.

### Manuelle Installation

NiimBlue-Commandline-Backend installieren:

```powershell
npm.cmd install --global @mmote/niimblue-node
```

Python-Abhaengigkeiten installieren:

```powershell
python -m pip install -r requirements.txt
```

## Startoptionen

### GUI direkt starten

```text
start-print-my-spool-label-gui.bat
```

Dieses Script startet die GUI direkt und fuehrt kein Repository-Update aus.

### Aktualisieren und starten

```text
start-print-my-spool-label.bat
```

Dieses Script fuehrt zuerst `git pull` aus und startet danach die GUI. Es eignet sich fuer Rechner, auf denen immer die aktuelle Repository-Version verwendet werden soll.

### Python direkt verwenden

```powershell
python .\src\app.py
```

## HowTo

### PNG drucken

1. Anwendung ueber `start-print-my-spool-label-gui.bat` starten.
2. Eine fertige PNG-Datei in den markierten Ablagebereich ziehen.
3. Vorschau und Labelrahmen pruefen.
4. Seriellen Druckerport kontrollieren oder anpassen.
5. Anzahl der Kopien zwischen `1` und `99` einstellen.
6. `Drucken` klicken.

### Struktur-AML drucken

1. Strukturierte AML-Datei in die GUI ziehen.
2. Warten, bis die AML-Verarbeitung abgeschlossen ist.
3. Kontrollieren, dass Herstellerlogo, Material, Farbe, Hex-Code, Temperaturwerte und QR-Code korrekt dargestellt werden.
4. Port und Kopienanzahl einstellen.
5. `Drucken` klicken.

### Raster-AML drucken

1. Raster-AML-Datei in die GUI ziehen.
2. Den Fortschrittsbalken waehrend der OCR-Verarbeitung abwarten.
3. Vorschau auf OCR-Ergebnisse, Logo und QR-Code pruefen.
4. Besonders bei ungewoehnlichen Schriftarten oder stark veraenderten Layouts die technischen Werte kontrollieren.
5. Port und Kopienanzahl einstellen.
6. `Drucken` klicken.

### QR-Code pruefen

Bei Struktur-AMLs wird der QR-Code aus dem XML-Inhalt erzeugt. Bei Raster-AMLs wird der vorhandene QR-Code direkt aus dem Bild uebernommen. Vor dem ersten Seriendruck sollte der QR-Code mit einem Smartphone getestet werden.

## Fehlerbehebung

### `niimblue-cli` wurde nicht gefunden

NiimBlue ist nicht installiert oder der globale npm-Bin-Pfad ist nicht im PATH enthalten. Installation erneut ausfuehren:

```powershell
npm.cmd install --global @mmote/niimblue-node
```

Danach ein neues Terminal beziehungsweise die GUI neu starten.

### Raster-AML kann nicht verarbeitet werden

Sicherstellen, dass die Abhaengigkeiten installiert sind:

```powershell
python -m pip install -r requirements.txt
```

Bei unbekannten Rasterlayouts koennen feste Bildkoordinaten fuer Logo und QR-Bereich abweichen. Die Vorschau vor dem Druck pruefen.

### Drucker wird nicht gefunden

- USB-Verbindung und Windows-COM-Port pruefen.
- Den korrekten Port in der GUI eintragen.
- Sicherstellen, dass kein anderes Programm den Port verwendet.
- NiimBlue-Ausgabe im Statusbereich der GUI pruefen.

### Vorschau und Druckgroesse stimmen nicht

Das Ziel ist immer `320 x 96 px` bei `203 dpi`, entsprechend `40 x 12 mm`. Andere Eingabegroessen werden in dieses Zielformat eingepasst.

## Projektstruktur

```text
src/app.py                         PySide6-GUI, Drag & Drop und Druckablauf
src/aml_renderer.py               AML-Parsing, OCR und Label-Rendering
requirements.txt                  Python-Abhaengigkeiten
install-print-my-spool-label.bat  One-Click-Installation
start-print-my-spool-label.bat    Git-Update und GUI-Start
start-print-my-spool-label-gui.bat Direkter GUI-Start
```

## Herkunft

Das Projekt entstand aus einem praktischen Workflow zum Drucken kompakter Filamentinformationen auf einem NIIMBOT D110M. Als Datenquellen dienen PNG-Exporte und Labelife-AML-Dateien, unter anderem aus Workflows rund um [3D Filament Profiles](https://3dfilamentprofiles.com).

Die Druckkommunikation erfolgt ueber [niimblue-node](https://github.com/Mmote/niimblue-node). Das feste Ziellayout und die AML-Aufbereitung sind projektspezifische Implementierungen dieses Repositories.

## Danksagungen

- Danke an die Maintainer von `niimblue-node` fuer die Ansteuerung des NIIMBOT-Druckers.
- Danke an die Open-Source-Projekte PySide6, Pillow, qrcode und RapidOCR fuer die verwendeten Bibliotheken.
- Danke an die Anbieter und Autoren der Filamentprofil- und Labeldaten, die die AML- und PNG-Workflows ermoeglichen.

## Lizenzen

Fuer dieses Repository ist derzeit keine eigene Projektlizenz hinterlegt. Ohne eine `LICENSE`-Datei gilt: Der Quellcode darf nicht automatisch weiterverwendet, veraendert oder verteilt werden. Eine ausdrueckliche Projektlizenz sollte vor einer oeffentlichen Weitergabe festgelegt werden.

Die verwendeten Drittanbieterkomponenten haben eigene Lizenzbedingungen. Fuer die konkrete Version sind die jeweiligen Paket- und Repository-Lizenzdateien zu beachten, insbesondere fuer:

- PySide6
- Pillow
- qrcode
- rapidocr-onnxruntime und die darunter verwendeten OCR-Komponenten
- `@mmote/niimblue-node`

## Status

Das Projekt ist ein funktionsfaehiger, auf den NIIMBOT D110M ausgerichteter Prototyp. Druckparameter, Raster-AML-Koordinaten und OCR-Auswertung wurden mit den bisher verfuegbaren Beispieldateien getestet. Neue AML-Layouts sollten vor einem Seriendruck immer anhand der Vorschau und eines Testlabels kontrolliert werden.
