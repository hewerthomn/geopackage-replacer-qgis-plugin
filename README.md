# Geopackage Replacer (QGIS 3)

**Replace any GeoPackage (.gpkg) referenced by your current QGIS project with a new file** (either a `.gpkg` or a `.zip` containing one). The plugin shows a side-by-side preview of layers with feature counts and SRIDs, logs everything, creates a backup, and can reload the project automatically.

> **Repository:** <https://github.com/hewerthomn/geopackage-replacer-qgis-plugin>  
> **Issues / Tracker:** <https://github.com/hewerthomn/geopackage-replacer-qgis-plugin/issues>

---

## ✨ Features
- Pick the **origin GeoPackage** among those currently used by the project.
- Pick the **new file** (`.gpkg` or `.zip` containing a `.gpkg`).
- **Side-by-side preview** of *Layer*, *Feature Count* and *SRID* (the new table also shows **“Exists in origin?”**).
- **Validation** via GDAL/OGR before replacing.
- **Detailed log** (dock), **progress dialog**, and **finish notifications** (message bar + pop-up).
- **Timestamped backup** in `.geopackage_replacer_backups/` next to the target file.
- **Optional auto-reload** of the project (persisted with `QSettings`).

---

## 📦 Installation
- **From ZIP:**
  1. Download or build `geopackage_replacer.zip`.
  2. In QGIS: **Plugins → Manage and Install Plugins… → Install from ZIP**.
- **From source:** copy the folder to your profile’s plugin dir:
  - **macOS:** `~/Library/Application Support/QGIS/QGIS3/profiles/<profile>/python/plugins/`
  - **Linux:** `~/.local/share/QGIS/QGIS3/profiles/<profile>/python/plugins/`
  - **Windows:** `%APPDATA%/QGIS/QGIS3/profiles/<profile>/python/plugins/`

> The plugin requires QGIS ≥ 3.22 and a working GDAL/OGR (bundled with QGIS).

---

## 🔧 Building resources
On Linux/Windows, `pyrcc5` is usually available.

On macOS (QGIS LTR/Stable), use the provided script which avoids broken wrappers:
```bash
./build_resources.sh
```

It tries (in order): `python3 -m PyQt5.pyrcc_main` from the QGIS bundle, `pyrcc5.bin`, a system `pyrcc5`, or your local Python’s `PyQt5.pyrcc_main`.

To produce a clean ZIP:

```bash
./make_zip.sh
```

---

## 🚀 Usage

1. Open your **saved** project.
2. **Plugins → Geopackage Replacer → Open Geopackage Replacer…**
3. Select the **new** file (`.gpkg`/`.zip`) and the **origin** GeoPackage (from the combo) (`.gpkg`/`.zip`).
4. The preview loads automatically when you change the new file or the origin; inspect layers, feature counts and SRIDs, and check **“Exists in origin?”**.
5. (Optional) Toggle **Auto‑reload project**.
6. Click **Replace**. The plugin removes layers that lock the file, creates a backup, copies the new GPKG and (optionally) reloads the project using `QgsProject.read()`.

---

## 📝 Notes & Limitations

- The first `.gpkg` inside the `.zip` is used.
- Large GeoPackages may take a while to count features.
- On Windows, temporary locks can happen; the plugin mitigates by removing layers and reloading the project.

---


## 📄 License

This project is released under the **MIT License**. See the [LICENSE](LICENSE) file.