"""Add-in de Fusion: vigila una carpeta y, cuando aparece o cambia un .step/.stp, lo importa como componente nuevo.
Solo lee archivos de esa carpeta (no abre puertos, no ejecuta codigo recibido). Carpeta por defecto:
~/Documents/FusionWatcher; cambiar con la variable de entorno FUSION_WATCH_DIR o editando WATCH_DIR."""
import adsk.core, adsk.fusion, traceback, threading, os, time

WATCH_DIR = os.environ.get("FUSION_WATCH_DIR", os.path.join(os.path.expanduser("~"), "Documents", "FusionWatcher"))
EVENT_ID = "FusionWatcherImport"
POLL_S = 2.0
EXTS = (".step", ".stp")
_app = adsk.core.Application.get()
_ui = _app.userInterface
_handlers, _stop, _thread, _seen = [], threading.Event(), None, {}

class ImportHandler(adsk.core.CustomEventHandler):
    def notify(self, args):
        try:
            path = args.additionalInfo
            if not _app.activeProduct or _app.activeProduct.objectType != adsk.fusion.Design.classType():
                return
            design = adsk.fusion.Design.cast(_app.activeProduct)
            opts = _app.importManager.createSTEPImportOptions(path)
            _app.importManager.importToTarget(opts, design.rootComponent)
            _app.activeViewport.fit()
            _ui.palettes.itemById("TextCommands").writeText("FusionWatcher: importado " + os.path.basename(path))
        except Exception:
            _ui.palettes.itemById("TextCommands").writeText("FusionWatcher error:\n" + traceback.format_exc())

def _loop():
    while not _stop.is_set():
        try:
            for n in sorted(os.listdir(WATCH_DIR)):
                if not n.lower().endswith(EXTS): continue
                p = os.path.join(WATCH_DIR, n); st = os.stat(p); key = (st.st_mtime, st.st_size)
                if _seen.get(p) == key or time.time() - st.st_mtime < 1.5: continue   # esperar a que termine de escribirse
                _seen[p] = key
                _app.fireCustomEvent(EVENT_ID, p)
        except Exception:
            pass
        _stop.wait(POLL_S)

def run(context):
    global _thread
    try:
        os.makedirs(WATCH_DIR, exist_ok=True)
        ev = _app.registerCustomEvent(EVENT_ID); h = ImportHandler(); ev.add(h); _handlers.append(h)
        _stop.clear(); _thread = threading.Thread(target=_loop, daemon=True); _thread.start()
        _ui.messageBox("FusionWatcher activo.\nCarpeta: " + WATCH_DIR + "\nLos .step nuevos se importan solos.")
    except Exception:
        _ui.messageBox("FusionWatcher fallo:\n" + traceback.format_exc())

def stop(context):
    try:
        _stop.set(); _app.unregisterCustomEvent(EVENT_ID)
    except Exception:
        pass
