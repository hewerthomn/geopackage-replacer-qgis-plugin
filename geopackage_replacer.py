import os
import re
import shutil
import tempfile
import zipfile
from datetime import datetime

# GDAL/OGR to inspect GPKG without loading into the project
from osgeo import ogr
from qgis.core import Qgis, QgsMessageLog, QgsProject
from qgis.PyQt.QtCore import QCoreApplication, QSettings, Qt, QTimer
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import (
    QAction,
    QCheckBox,
    QComboBox,
    QDialog,
    QDockWidget,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressDialog,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

# ensure .qrc resources are available
from . import resources_rc  # noqa: F401

PLUGIN_MENU = "&Geopackage Replacer"
RESOURCE_ICON = ":/geopackage_replacer/icon.png"
SETTINGS_KEY_REOPEN = "geopackage_replacer/reopen_auto"


class GeopackageReplacerPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.actions = []
        self.toolbar = None
        self.dock = None
        self.log_view = None
        self.settings = QSettings()
        self.reopen_auto = self.settings.value(SETTINGS_KEY_REOPEN, True, type=bool)

    # ------------------------------
    # Plugin lifecycle
    # ------------------------------
    def initGui(self):
        self.toolbar = self.iface.addToolBar("Geopackage Replacer")
        self.toolbar.setObjectName("GeopackageReplacerToolbar")

        icon = QIcon(RESOURCE_ICON)

        action_open = QAction(
            icon,
            self.tr("Open Geopackage Replacer…"),
            self.iface.mainWindow(),
        )
        action_open.triggered.connect(self._open_dialog)
        self._add_action(action_open)

        # Log dock
        self._create_log_dock()
        self._log(
            self.tr("Plugin initialized. Auto-reload: {}").format(self.reopen_auto)
        )

    def unload(self):
        for a in self.actions:
            try:
                self.iface.removePluginMenu(PLUGIN_MENU, a)
            except Exception:
                pass
            try:
                self.toolbar.removeAction(a)
            except Exception:
                pass
        try:
            self.iface.mainWindow().removeToolBar(self.toolbar)
        except Exception:
            pass
        if self.dock is not None:
            try:
                self.iface.removeDockWidget(self.dock)
            except Exception:
                pass
            self.dock = None
        self.actions.clear()
        self.toolbar = None

    # ------------------------------
    # UI / Log helpers
    # ------------------------------
    def _create_log_dock(self):
        self.dock = QDockWidget(
            self.tr("Geopackage Replacer – Log"), self.iface.mainWindow()
        )
        self.dock.setObjectName("GeopackageReplacerLogDock")
        container = QWidget()
        layout = QVBoxLayout(container)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setPlaceholderText(self.tr("Operation logs will appear here…"))

        btns = QHBoxLayout()
        btn_clear = QPushButton(self.tr("Clear Log"))
        btn_clear.clicked.connect(lambda: self.log_view.setPlainText(""))
        btns.addWidget(btn_clear)
        btns.addStretch(1)

        layout.addWidget(self.log_view)
        layout.addLayout(btns)

        self.dock.setWidget(container)
        self.iface.addDockWidget(Qt.BottomDockWidgetArea, self.dock)
        self.dock.hide()

    def _toggle_log_dock(self):
        if self.dock.isVisible():
            self.dock.hide()
        else:
            self.dock.show()

    def _set_log_dock_visible(self, visible: bool):
        if visible:
            self.dock.show()
        else:
            self.dock.hide()

    def _add_action(self, action: QAction):
        self.iface.addPluginToMenu(PLUGIN_MENU, action)
        self.toolbar.addAction(action)
        self.actions.append(action)

    def tr(self, message: str) -> str:
        return QCoreApplication.translate("GeopackageReplacer", message)

    def _log(self, msg: str, level: Qgis.MessageLevel = Qgis.Info):
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}"
        if self.log_view:
            self.log_view.appendPlainText(line)
        QgsMessageLog.logMessage(msg, "Geopackage Replacer", level=level)

    def _info(self, msg: str):
        self._log(msg, Qgis.Info)

    def _warn(self, msg: str):
        self._log(msg, Qgis.Warning)

    def _err(self, msg: str):
        self._log(msg, Qgis.Critical)

    def _toggle_reopen(self, checked: bool):
        self.reopen_auto = bool(checked)
        self.settings.setValue(SETTINGS_KEY_REOPEN, self.reopen_auto)
        self._info(self.tr("Auto-reload: {}").format(self.reopen_auto))

    # ------------------------------
    # Main dialog
    # ------------------------------
    def _open_dialog(self):
        project = QgsProject.instance()
        if not project.fileName():
            QMessageBox.warning(
                self.iface.mainWindow(),
                "Geopackage Replacer",
                self.tr(
                    "The project has not been saved yet. Please save it to continue."
                ),
            )
            return

        dlg = QDialog(self.iface.mainWindow())
        dlg.setWindowTitle(self.tr("Geopackage Replacer – Preview and Replace"))
        main = QVBoxLayout(dlg)

        # Selectors — NEW FIRST (left), then ORIGIN (right)
        sel_row = QHBoxLayout()

        # New (.gpkg/.zip) — LEFT side
        left_col = QVBoxLayout()
        left_col.addWidget(QLabel(self.tr("New GeoPackage (.gpkg or .zip):")))
        new_row = QHBoxLayout()
        self.txt_new = QLineEdit()
        btn_browse = QPushButton(self.tr("Browse…"))
        btn_browse.clicked.connect(self._browse_new)
        new_row.addWidget(self.txt_new)
        new_row.addWidget(btn_browse)
        left_col.addLayout(new_row)
        self.tbl_new = QTableWidget(1, 4)
        self.tbl_new.setHorizontalHeaderLabels(
            [
                self.tr("Layer"),
                self.tr("Features"),
                self.tr("SRID"),
                self.tr("Exists in origin?"),
            ]
        )
        self.tbl_new.verticalHeader().setVisible(False)
        self.tbl_new.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tbl_new.setSelectionMode(QTableWidget.NoSelection)
        left_col.addWidget(self.tbl_new)

        # Origin (from project) — RIGHT side
        right_col = QVBoxLayout()
        right_col.addWidget(QLabel(self.tr("Origin GeoPackage (from project):")))
        self.cmb_origin = QComboBox()
        gpkgs = sorted(self._collect_project_gpkgs())
        for p in gpkgs:
            self.cmb_origin.addItem(p)
        right_col.addWidget(self.cmb_origin)
        self.tbl_origin = QTableWidget(1, 3)
        self.tbl_origin.setHorizontalHeaderLabels(
            [self.tr("Layer"), self.tr("Features"), self.tr("SRID")]
        )
        self.tbl_origin.verticalHeader().setVisible(False)
        self.tbl_origin.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tbl_origin.setSelectionMode(QTableWidget.NoSelection)
        right_col.addWidget(self.tbl_origin)

        sel_row.addLayout(left_col)
        sel_row.addLayout(right_col)
        main.addLayout(sel_row)

        # Auto-preview
        self.txt_new.textChanged.connect(self._load_previews)
        self.cmb_origin.currentTextChanged.connect(self._load_previews)

        # Options & buttons
        opts = QHBoxLayout()
        self.chk_reopen = QCheckBox(self.tr("Auto-reload project after replacing"))
        self.chk_reopen.setChecked(bool(self.reopen_auto))
        self.chk_reopen.toggled.connect(self._toggle_reopen)

        self.chk_show_log = QCheckBox(self.tr("Show log panel"))
        self.chk_show_log.setChecked(False)
        self.chk_show_log.toggled.connect(self._set_log_dock_visible)

        btn_replace = QPushButton(self.tr("Replace"))
        btn_replace.clicked.connect(lambda: self._replace_from_dialog(dlg))

        opts.addWidget(self.chk_reopen)
        opts.addWidget(self.chk_show_log)
        opts.addStretch(1)
        opts.addWidget(btn_replace)
        main.addLayout(opts)

        # Initial origin preview (if any). New preview loads when user picks a file.
        if self.cmb_origin.count() > 0:
            self._load_previews()
        else:
            self._warn(self.tr("No GeoPackage detected in the project."))

        dlg.resize(1100, 600)
        dlg.exec_()

    def _browse_new(self):
        path, _ = QFileDialog.getOpenFileName(
            self.iface.mainWindow(),
            self.tr("Select .gpkg or .zip"),
            "",
            self.tr("GeoPackage (*.gpkg);;ZIP archive (*.zip)"),
        )
        if path:
            self.txt_new.setText(path)
            self._load_previews()

    def _load_previews(self, *args):
        origin_path = (
            self.cmb_origin.currentText().strip() if hasattr(self, "cmb_origin") else ""
        )
        new_sel = self.txt_new.text().strip() if hasattr(self, "txt_new") else ""

        # --- ORIGIN ---
        origin_info = {}
        if origin_path:
            try:
                origin_info = self._inspect_gpkg(origin_path)
                self._info(
                    self.tr("Origin inspected: {} layers").format(len(origin_info))
                )
                self._fill_table(self.tbl_origin, origin_info)
            except Exception as e:
                self._err(self.tr("Failed to inspect origin GeoPackage: {}").format(e))
                QMessageBox.critical(
                    self.iface.mainWindow(), "Geopackage Replacer", str(e)
                )
                self._fill_table(self.tbl_origin, {}, include_exists=False)
                origin_info = {}
        else:
            self._fill_table(self.tbl_origin, {}, include_exists=False)

        # --- NEW ---
        if new_sel:
            try:
                new_gpkg = self._prepare_new_gpkg(new_sel)
                new_info = self._inspect_gpkg(new_gpkg)
                self._info(
                    self.tr("New GeoPackage inspected: {} layers").format(len(new_info))
                )
                if origin_info:
                    origin_names = set(origin_info.keys())
                    for n, meta in new_info.items():
                        meta["exists_in_origin"] = n in origin_names
                    self._fill_table(self.tbl_new, new_info, include_exists=True)
                else:
                    self._fill_table(self.tbl_new, new_info, include_exists=False)
            except Exception as e:
                self._err(self.tr("Failed to inspect new GeoPackage: {}").format(e))
                QMessageBox.critical(
                    self.iface.mainWindow(),
                    "Geopackage Replacer",
                    self.tr("Invalid new GeoPackage."),
                )
                self._fill_table(self.tbl_new, {}, include_exists=False)
        else:
            self._fill_table(self.tbl_new, {}, include_exists=False)

    def _replace_from_dialog(self, dlg: QDialog):
        origin_path = self.cmb_origin.currentText().strip()
        new_sel = self.txt_new.text().strip()
        if not origin_path or not new_sel:
            QMessageBox.warning(
                self.iface.mainWindow(),
                "Geopackage Replacer",
                self.tr("Select both the origin GeoPackage and the new file."),
            )
            return

        try:
            new_gpkg = self._prepare_new_gpkg(new_sel)
            # validate before proceeding
            self._inspect_gpkg(new_gpkg)
        except Exception as e:
            self._err(self.tr("Failed to validate new GeoPackage: {}").format(e))
            QMessageBox.critical(
                self.iface.mainWindow(),
                "Geopackage Replacer",
                self.tr("Invalid new GeoPackage."),
            )
            return

        reopen_after = bool(self.chk_reopen.isChecked())
        backup_path = ""

        # Progress
        steps = [
            self.tr("Preparing…"),
            self.tr("Removing locked layers…"),
            self.tr("Creating backup…"),
            self.tr("Copying new GeoPackage…"),
            self.tr("Reloading project…"),
            self.tr("Finishing…"),
        ]
        prog = QProgressDialog(
            self.tr("Performing replacement…"),
            self.tr("Cancel"),
            0,
            len(steps),
            self.iface.mainWindow(),
        )
        prog.setWindowModality(Qt.WindowModal)
        prog.setMinimumDuration(0)

        def tick(i, text):
            prog.setLabelText(text)
            prog.setValue(i)

        try:
            tick(0, steps[0])
            self._info(
                self.tr("Starting replacement: {} -> {}").format(origin_path, new_sel)
            )

            tick(1, steps[1])
            removed_any = self._remove_layers_using_gpkg(origin_path)
            if removed_any:
                self._info(self.tr("Origin GeoPackage layers temporarily removed."))

            tick(2, steps[2])
            backup_path = self._create_backup(origin_path)
            self._info(
                self.tr("Backup created: {}").format(
                    backup_path or self.tr("(no previous file)")
                )
            )

            tick(3, steps[3])
            shutil.copy2(new_gpkg, origin_path)
            self._info(self.tr("New GeoPackage copied to destination."))

            tick(4, steps[4])
            if reopen_after:
                self._reload_project()
            else:
                self._info(self.tr("Auto-reload disabled for this operation."))

            tick(5, steps[5])
        except Exception as e:
            self._err(str(e))
            QMessageBox.critical(self.iface.mainWindow(), "Geopackage Replacer", str(e))
            return
        finally:
            prog.close()

        msg_done = self.tr("Replacement completed successfully. Backup: {}").format(
            backup_path or self.tr("(no previous file)")
        )
        self.iface.messageBar().pushMessage(
            "Geopackage Replacer", msg_done, level=Qgis.Success, duration=6
        )
        QMessageBox.information(
            self.iface.mainWindow(), "Geopackage Replacer", msg_done
        )
        self._info(self.tr("Operation finished."))

    def _fill_table(
        self, table: QTableWidget, info: dict, include_exists: bool = False
    ):
        """Fill a QTableWidget with layer info (optionally with the 'Exists in origin?' column)."""
        cols = 4 if include_exists else 3
        table.setRowCount(max(1, len(info)))
        table.setColumnCount(cols)
        headers = [self.tr("Layer"), self.tr("Features"), self.tr("SRID")]
        if include_exists:
            headers.append(self.tr("Exists in origin?"))
        table.setHorizontalHeaderLabels(headers)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionMode(QTableWidget.NoSelection)

        if info:
            for row, (name, meta) in enumerate(
                sorted(info.items(), key=lambda kv: kv[0].lower())
            ):
                table.setItem(row, 0, QTableWidgetItem(name))
                table.setItem(row, 1, QTableWidgetItem(str(meta.get("count", "?"))))
                table.setItem(row, 2, QTableWidgetItem(str(meta.get("srid", "?"))))
                if include_exists:
                    exists = meta.get("exists_in_origin")
                    table.setItem(
                        row,
                        3,
                        QTableWidgetItem(self.tr("Yes") if exists else self.tr("No")),
                    )
        else:
            table.setItem(0, 0, QTableWidgetItem(self.tr("(empty)")))
            table.setItem(0, 1, QTableWidgetItem("-"))
            table.setItem(0, 2, QTableWidgetItem("-"))
            if include_exists:
                table.setItem(0, 3, QTableWidgetItem("-"))

        table.resizeColumnsToContents()

    # ------------------------------
    # Utilities
    # ------------------------------
    def _collect_project_gpkgs(self):
        paths = set()
        for layer in QgsProject.instance().mapLayers().values():
            try:
                uri = layer.dataProvider().dataSourceUri()
            except Exception:
                continue
            gpkg = self._extract_gpkg_path_from_uri(uri)
            if gpkg and os.path.exists(gpkg):
                paths.add(os.path.abspath(os.path.normpath(gpkg)))
        return paths

    def _prepare_new_gpkg(self, input_path: str) -> str:
        """Accept a .gpkg or a .zip containing one; return the extracted .gpkg path."""
        if input_path.lower().endswith(".gpkg"):
            return input_path
        if input_path.lower().endswith(".zip"):
            with zipfile.ZipFile(input_path, "r") as zf:
                # grab the first .gpkg in the zip
                candidates = [
                    m
                    for m in zf.namelist()
                    if m.lower().endswith(".gpkg") and not m.endswith("/")
                ]
                if not candidates:
                    raise Exception(self.tr("ZIP contains no .gpkg."))
                member = candidates[0]
                tempdir = tempfile.mkdtemp(prefix="gpkg_replacer_")
                zf.extract(member, tempdir)
                return os.path.join(tempdir, member)
        raise Exception(
            self.tr("Unsupported file format. Please select a .zip or .gpkg.")
        )

    def _extract_gpkg_path_from_uri(self, uri: str) -> str:
        if not uri:
            return ""
        if "dbname='" in uri:
            start = uri.find("dbname='") + 8
            end = uri.find("'", start)
            if end > start:
                return uri[start:end]
        m = re.search(r"(.+?\.gpkg)", uri, re.IGNORECASE)
        if m:
            return m.group(1)
        return ""

    def _remove_layers_using_gpkg(self, gpkg_path: str) -> bool:
        gpkg_norm = os.path.abspath(os.path.normpath(gpkg_path)).lower()
        layers_to_remove = []
        for layer_id, layer in QgsProject.instance().mapLayers().items():
            try:
                uri = layer.dataProvider().dataSourceUri()
            except Exception:
                continue
            path = self._extract_gpkg_path_from_uri(uri)
            if path and os.path.abspath(os.path.normpath(path)).lower() == gpkg_norm:
                layers_to_remove.append(layer_id)
        if layers_to_remove:
            QgsProject.instance().removeMapLayers(layers_to_remove)
            return True
        return False

    def _create_backup(self, dest_gpkg: str) -> str:
        dest_dir = os.path.dirname(dest_gpkg)
        os.makedirs(dest_dir, exist_ok=True)
        backup_path = ""
        if os.path.exists(dest_gpkg):
            backups_dir = os.path.join(dest_dir, ".geopackage_replacer_backups")
            os.makedirs(backups_dir, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            base = os.path.basename(dest_gpkg)
            backup_path = os.path.join(backups_dir, f"{base}.{ts}.bak")
            shutil.copy2(dest_gpkg, backup_path)
        return backup_path

    def _reload_project(self):
        """Reload the current project from disk without saving the temporary state."""
        project = QgsProject.instance()
        path = project.fileName()
        if not path:
            self._warn(self.tr("Project has no file path; nothing to reload."))
            return

        def do_read():
            ok = project.read(path)
            if ok:
                self._info(self.tr("Project reloaded from: {}").format(path))
            else:
                self._warn(self.tr("Could not reload project from file."))

        # slight delay to ensure the copy is flushed on disk
        QTimer.singleShot(150, do_read)

    # ------------------------------
    # Inspection
    # ------------------------------
    def _inspect_gpkg(self, path: str) -> dict:
        """Open GPKG via OGR and return {layer: {count, geom, srid}}."""
        if not os.path.exists(path):
            raise Exception(self.tr("File does not exist: {}").format(path))
        ds = ogr.Open(path, 0)
        if ds is None:
            raise Exception(self.tr("Could not open GeoPackage (OGR): {}").format(path))
        info = {}
        for i in range(ds.GetLayerCount()):
            lyr = ds.GetLayerByIndex(i)
            name = lyr.GetName()
            try:
                count = int(lyr.GetFeatureCount())
            except Exception:
                count = -1
            try:
                geom_type = ogr.GeometryTypeToName(lyr.GetGeomType())
            except Exception:
                geom_type = "?"
            # SRID
            srid = "?"
            try:
                srs = lyr.GetSpatialRef()
                if srs is not None:
                    auth = srs.GetAuthorityName(None)
                    code = srs.GetAuthorityCode(None)
                    if auth and code:
                        srid = f"{auth}:{code}"
                    else:
                        srid = srs.GetName() or "?"
            except Exception:
                pass
            info[name] = {"count": count, "geom": str(geom_type), "srid": srid}
        return info
