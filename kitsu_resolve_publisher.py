"""
Kitsu Publisher for DaVinci Resolve  ·  v4
==========================================
  • Separate windows for Shot Browser and Resolve Project picker
    (no nested RunLoop — child windows use Show()/Hide() only,
     all events handled by the single main disp.RunLoop)
  • Browse Shot & Create Project — picks Kitsu shot, creates new Resolve project
  • Assign Shot — picks existing Resolve project, copies it to proj_seq_shot_vNNN
  • Smart render path: root / sequence / shot / version / proj_seq_shot_vNNN.mp4
  • All settings persisted to ~/.kitsu_resolve.json

Install
-------
  Windows: %APPDATA%\\Blackmagic Design\\DaVinci Resolve\\Support\\Fusion\\Scripts\\Comp\\
  macOS:   ~/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Comp/

Run: Workspace > Scripts > kitsu_resolve_publisher_v4
"""

import sys, os, json, re, time, tempfile

print("[kitsu] Python:", sys.version)
print("[kitsu] sys.executable:", sys.executable)

import subprocess
r = subprocess.run([sys.executable, "-m", "pip", "install", "gazu", "requests"],
                   capture_output=True, text=True)
print("[pip returncode]", r.returncode)
if r.returncode != 0:
    print("[pip stderr]", r.stderr)

import gazu, requests
print("[kitsu] gazu:", gazu.__version__)

# ── Settings ──────────────────────────────────────────────────────────────────
SETTINGS_FILE = os.path.join(os.path.expanduser("~"), ".kitsu_resolve.json")

def load_settings():
    try:
        with open(SETTINGS_FILE) as f: return json.load(f)
    except Exception: return {}

def save_settings(d):
    try:
        with open(SETTINGS_FILE, "w") as f: json.dump(d, f, indent=2)
    except Exception as e: print(f"[settings] {e}")

# ── Kitsu client ──────────────────────────────────────────────────────────────
class KitsuClient:
    def __init__(self, server_url):
        self.gazu = gazu
        self.base = server_url.rstrip("/")
        gazu.set_host(f"{self.base}/api")

    def login(self, email, password):
        return self.gazu.log_in(email, password)

    def get_projects(self):
        return self.gazu.project.all_open_projects()

    def get_sequences(self, project_id):
        return self.gazu.shot.all_sequences_for_project({"id": project_id})

    def get_shots(self, sequence_id):
        return self.gazu.shot.all_shots_for_sequence({"id": sequence_id})

    def get_task_types(self):
        return self.gazu.task.all_task_types()

    def get_shot_tasks(self, shot_id):
        return self.gazu.task.all_tasks_for_shot({"id": shot_id})

    def get_task_statuses(self):
        return self.gazu.task.all_task_statuses()

    def download_thumbnail(self, shot_id):
        try:
            host = self.gazu.client.get_host()
            auth = self.gazu.client.default_client.tokens.get("access_token", "")
            resp = requests.get(
                f"{host}/pictures/thumbnails/shots/{shot_id}.png",
                headers={"Authorization": "Bearer " + auth},
                timeout=5)
            if resp.status_code == 200:
                return resp.content
        except Exception:
            pass
        return None

    def upload_preview_with_status(self, task_id, file_path, comment,
                                   task_status_id, log=print):
        import mimetypes
        t0 = time.time()
        T  = lambda: "%.1fs" % (time.time() - t0)

        task        = {"id": task_id, "type": "Task"}
        task_status = {"id": task_status_id} if task_status_id else None
        if task_status is None:
            task_status = {"id": self.gazu.task.get_task(task_id)["task_status_id"]}

        log("[publish] posting comment...")
        comment_obj = self.gazu.task.add_comment(task, task_status, comment=comment or "")
        log(f"[publish] comment posted ({T()})")

        log("[publish] creating preview record...")
        preview_obj = self.gazu.raw.post(
            f"actions/tasks/{task_id}/comments/{comment_obj['id']}/add-preview", {})
        log(f"[publish] preview record created ({T()})")

        mime_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
        url  = f"{self.gazu.client.get_host()}/pictures/preview-files/{preview_obj['id']}"
        auth = self.gazu.client.default_client.tokens.get("access_token", "")

        log(f"[publish] uploading {os.path.getsize(file_path)//1024//1024} MB ...")
        try:
            with open(file_path, "rb") as fh:
                resp = requests.post(url,
                    headers={"Authorization": "Bearer " + auth},
                    files={"file": (os.path.basename(file_path), fh, mime_type)},
                    stream=True, timeout=(10, 3600))
            log(f"[publish] upload done  status={resp.status_code} ({T()})")
            if resp.status_code not in (200, 201):
                raise RuntimeError(f"Upload failed: HTTP {resp.status_code}")
            preview_obj = resp.json()
        except Exception as e:
            es = str(e)
            if "504" in es or "JSONDecodeError" in es or "Expecting value" in es:
                log("[publish] nginx 504 — file likely received, continuing")
            else:
                raise

        if preview_obj and preview_obj.get("id"):
            try:
                self.gazu.task.set_main_preview(preview_obj)
                log(f"[publish] main preview set ({T()})")
            except Exception as e:
                log(f"[publish] set_main_preview: {e} (non-fatal)")

        log(f"[publish] done  total={T()}")
        return {"comment": comment_obj, "preview": preview_obj}

# ── Resolve helpers ───────────────────────────────────────────────────────────
def get_resolve():        return bmd.scriptapp("Resolve")           # noqa: F821
def get_project_manager(): return get_resolve().GetProjectManager()
def get_current_project(): return get_project_manager().GetCurrentProject()

def sanitize(name):
    return re.sub(r'[^\w\-_.]', '_', name).strip("_")

def build_project_base(proj_name, seq_name, shot_name):
    return "_".join(sanitize(x) for x in [proj_name, seq_name, shot_name])

def next_version_name(base, existing_names):
    pat  = re.compile(r'^' + re.escape(base) + r'_v(\d+)$', re.IGNORECASE)
    used = [int(m.group(1)) for n in existing_names for m in [pat.match(n)] if m]
    nv   = (max(used) + 1) if used else 1
    return f"{base}_v{nv:03d}", nv

def version_from_name(name):
    m = re.search(r'_v(\d+)$', name, re.IGNORECASE)
    return int(m.group(1)) if m else 1

def get_all_resolve_project_names():
    try:
        raw = get_project_manager().GetProjectListInCurrentFolder()
        if isinstance(raw, dict):          return list(raw.values())
        if isinstance(raw, (list, tuple)): return list(raw)
    except Exception as e:
        print(f"[resolve] project list error: {e}")
    return []

def copy_resolve_project(src_name, dst_name, log=print):
    """Export src to a temp .drp, re-import as dst_name. Original untouched."""
    pm  = get_project_manager()
    tmp = os.path.join(tempfile.gettempdir(),
                       f"_kitsu_copy_{int(time.time())}.drp")
    try:
        log(f"[resolve] loading '{src_name}' for export...")
        if not pm.LoadProject(src_name):
            log(f"[resolve] ERROR: cannot load '{src_name}'"); return False
        log("[resolve] exporting to temp .drp ...")
        if not pm.ExportProject(src_name, tmp, False):
            log("[resolve] ERROR: ExportProject failed"); return False
        log(f"[resolve] importing as '{dst_name}'...")
        if not pm.ImportProject(tmp, dst_name):
            log("[resolve] ERROR: ImportProject failed"); return False
        log(f"[resolve] opening '{dst_name}'...")
        if not pm.LoadProject(dst_name):
            log(f"[resolve] WARNING: could not auto-open '{dst_name}'")
        return True
    except Exception as e:
        log(f"[resolve] copy_project error: {e}"); return False
    finally:
        try: os.remove(tmp)
        except Exception: pass

def setup_render_job(project, folder, file_stem, preset_name=None):
    tl = project.GetCurrentTimeline()
    if not tl: raise RuntimeError("No active timeline.")
    if preset_name: project.LoadRenderPreset(preset_name)
    else:           project.SetCurrentRenderFormatAndCodec("mp4", "H264")
    project.SetRenderSettings({
        "SelectAllFrames": True, "TargetDir": folder,
        "CustomName": file_stem, "UniqueFilenameStyle": 0,
    })
    job_id = project.AddRenderJob()
    if not job_id: raise RuntimeError("Failed to add render job.")
    return job_id, os.path.join(folder, file_stem + ".mp4")

def wait_for_render(project, job_id, log=print):
    project.StartRendering(job_id)
    while project.IsRenderingInProgress():
        pct = project.GetRenderJobStatus(job_id).get("CompletionPercentage", 0)
        log(f"[render] {pct:.0f}%")
        time.sleep(1.5)
    st = project.GetRenderJobStatus(job_id)
    if st.get("JobStatus") != "Complete":
        raise RuntimeError("Render failed: " + st.get("JobStatus", "unknown"))

# ── Thumbnail cache ───────────────────────────────────────────────────────────
_thumb_cache = {}

def get_thumb_path(client, shot_id):
    if shot_id not in _thumb_cache:
        data = client.download_thumbnail(shot_id)
        if data:
            fd, path = tempfile.mkstemp(suffix=".png")
            os.close(fd)
            with open(path, "wb") as f: f.write(data)
            _thumb_cache[shot_id] = path
        else:
            _thumb_cache[shot_id] = ""
    return _thumb_cache[shot_id]

# ── Style constants ───────────────────────────────────────────────────────────
LBL        = "color:#6e7a9a;font-size:10px;font-weight:bold;"
BTN_BLUE   = "background:#3a6ff7;color:#fff;font-weight:bold;padding:5px 10px;border-radius:4px;"
BTN_GREEN  = "background:#2e8b57;color:#fff;font-weight:bold;padding:5px 10px;border-radius:4px;"
BTN_ORANGE = "background:#c76b1a;color:#fff;font-weight:bold;padding:5px 10px;border-radius:4px;"
BTN_GRAY   = "padding:5px 10px;border-radius:4px;"

# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    resolve = get_resolve()
    if not resolve:
        print("ERROR: run from inside Resolve  Workspace > Scripts"); return

    fusion = resolve.Fusion()
    ui     = fusion.UIManager
    disp   = bmd.UIDispatcher(ui)  # noqa: F821

    s = load_settings()

    state = {
        "client":       None,
        "projects":     [], "sequences": [], "shots": [],
        "task_types":   [], "shot_tasks": [], "statuses": [],
        # confirmed context
        "sel_project":  None, "sel_sequence": None, "sel_shot": None,
        "project_base": None, "version": 1, "project_name": None,
        # assign-shot source
        "assign_src":   None,
        # render root
        "render_root":  s.get("render_root", os.path.expanduser("~")),
        # child window refs  (Show/Hide only — no RunLoop)
        "browser_win":  None,
        "assign_win":   None,
        # which workflow triggered the browser: "create" | "assign"
        "browser_mode": "create",
        # pending shot picked in browser (not yet confirmed)
        "br_proj_idx":  -1,
        "br_seq_idx":   -1,
        "br_sequences": [],
        "br_shots":     [],
        "br_pending":   None,
    }

    # ── Main window ───────────────────────────────────────────────────────────
    win = disp.AddWindow(
        {"ID": "KitsuWin", "WindowTitle": "Kitsu Publisher v4",
         "Geometry": [100, 80, 490, 860]},
        [ui.VGroup({"Spacing": 5}, [
            ui.Label({"Text": "SERVER",   "StyleSheet": LBL}),
            ui.LineEdit({"ID": "Server",  "Text": s.get("server", ""),
                         "PlaceholderText": "http://192.168.x.x"}),
            ui.Label({"Text": "EMAIL",    "StyleSheet": LBL}),
            ui.LineEdit({"ID": "Email",   "Text": s.get("email", ""),
                         "PlaceholderText": "artist@studio.com"}),
            ui.Label({"Text": "PASSWORD", "StyleSheet": LBL}),
            ui.LineEdit({"ID": "Pwd",     "EchoMode": "Password",
                         "Text": s.get("password", ""),
                         "PlaceholderText": "password"}),
            ui.Button({"ID": "LoginBtn",  "Text": "Sign in",
                       "FixedHeight": 28,  "StyleSheet": BTN_BLUE}),
            ui.Label({"ID": "StatusLbl",  "Text": "", "WordWrap": True,
                      "StyleSheet": "color:#e05a6a;font-size:11px;"}),

            ui.Label({"ID": "AssignedLbl",
                      "Text": "No shot assigned",
                      "WordWrap": True,
                      "StyleSheet": "color:#c8a84b;font-size:11px;"
                                    "background:#1e1e2e;padding:6px;border-radius:4px;"}),

            ui.HGroup({"Spacing": 6}, [
                ui.Button({"ID": "BrowseKitsuBtn",
                           "Text": "Browse Shot & Create Project",
                           "Enabled": False, "FixedHeight": 34,
                           "StyleSheet": BTN_GREEN}),
                ui.Button({"ID": "AssignShotBtn",
                           "Text": "Assign Shot to Existing Project",
                           "Enabled": False, "FixedHeight": 34,
                           "StyleSheet": BTN_ORANGE}),
            ]),

            ui.Label({"Text": "TASK",   "StyleSheet": LBL}),
            ui.ComboBox({"ID": "Task",  "Enabled": False}),
            ui.Label({"Text": "STATUS", "StyleSheet": LBL}),
            ui.ComboBox({"ID": "TaskStatus", "Enabled": False}),

            ui.Label({"Text": "RENDER PRESET", "StyleSheet": LBL}),
            ui.ComboBox({"ID": "Preset"}),

            ui.Label({"Text": "RENDER ROOT PATH", "StyleSheet": LBL}),
            ui.HGroup({"Spacing": 4}, [
                ui.LineEdit({"ID": "RenderRoot",
                             "Text": s.get("render_root", os.path.expanduser("~")),
                             "Weight": 1}),
                ui.Button({"ID": "BrowseRoot", "Text": "...",
                           "FixedWidth": 28, "FixedHeight": 26}),
            ]),
            ui.Label({"ID": "RenderPathPreview", "Text": "",
                      "StyleSheet": "color:#5a8a6a;font-size:10px;",
                      "WordWrap": True}),

            ui.Label({"Text": "COMMENT", "StyleSheet": LBL}),
            ui.TextEdit({"ID": "Comment", "MinimumSize": [0, 50]}),

            ui.Button({"ID": "PublishBtn",
                       "Text": "Render & Publish to Kitsu",
                       "Enabled": False, "FixedHeight": 38,
                       "StyleSheet": ("background:#3a6ff7;color:#fff;font-weight:bold;"
                                      "font-size:13px;padding:8px;border-radius:5px;")}),

            ui.TextEdit({"ID": "Log", "ReadOnly": True, "MinimumSize": [0, 110],
                         "StyleSheet": ("background:#111318;color:#7a8aaa;"
                                        "font-family:monospace;font-size:11px;")}),
        ])]
    )
    itm = win.GetItems()

    # ── Helpers ───────────────────────────────────────────────────────────────
    def log(msg):
        print(msg)
        cur = itm["Log"].PlainText
        itm["Log"].PlainText = (cur + "\n" + msg).lstrip("\n")

    def setstatus(msg, ok=False):
        itm["StatusLbl"].Text = msg
        itm["StatusLbl"].StyleSheet = (
            "color:#4fbb6a;font-size:11px;" if ok else "color:#e05a6a;font-size:11px;")

    def set_assigned(name):
        state["project_name"] = name
        state["version"]      = version_from_name(name)
        itm["AssignedLbl"].Text = f"● {name}"
        itm["AssignedLbl"].StyleSheet = (
            "color:#4fbb6a;font-size:11px;background:#1a2e1a;"
            "padding:6px;border-radius:4px;")
        update_render_preview()
        update_publish_btn()

    def update_render_preview():
        root = itm["RenderRoot"].Text.strip()
        base = state.get("project_base")
        ver  = state.get("version", 1)
        seq  = state.get("sel_sequence")
        shot = state.get("sel_shot")
        if base and seq and shot and root:
            folder = os.path.join(root, sanitize(seq["name"]),
                                  sanitize(shot["name"]), f"v{ver:03d}")
            itm["RenderPathPreview"].Text = (
                f"→ {os.path.join(folder, base + f'_v{ver:03d}.mp4')}")
        else:
            itm["RenderPathPreview"].Text = ""

    def update_publish_btn():
        itm["PublishBtn"].Enabled = bool(
            state["client"] and state["project_name"]
            and state["sel_shot"] and itm["Task"].CurrentIndex > 0)

    def fill(cb_id, lst, key="name", placeholder="select"):
        cb = itm[cb_id]; cb.Clear(); cb.AddItem(placeholder)
        for x in lst: cb.AddItem(x[key])
        cb.Enabled = bool(lst)

    def restore(cb_id, lst, saved_id):
        for i, x in enumerate(lst):
            if x.get("id") == saved_id:
                itm[cb_id].CurrentIndex = i + 1; return True
        return False

    def presets():
        try:    p = get_current_project().GetRenderPresetList() or []
        except: p = []
        itm["Preset"].Clear(); itm["Preset"].AddItem("H.264 default")
        for x in p: itm["Preset"].AddItem(x)
    presets()

    # ── Login ─────────────────────────────────────────────────────────────────
    def do_login():
        server = itm["Server"].Text.strip()
        email  = itm["Email"].Text.strip()
        pwd    = itm["Pwd"].Text.strip()
        if not all([server, email, pwd]):
            setstatus("Fill in all fields."); return
        setstatus("Signing in...")
        try:
            c = KitsuClient(server); c.login(email, pwd)
        except Exception as e:
            import traceback
            setstatus("Login failed: " + str(e))
            log("[login error]\n" + traceback.format_exc()); return
        state["client"] = c
        setstatus("Connected ✓", ok=True)
        sv = load_settings()
        sv.update({"server": server, "email": email, "password": pwd})
        save_settings(sv)
        _load_initial()

    def _load_initial():
        c = state["client"]
        log("[kitsu] loading data...")
        try:
            state["projects"]   = c.get_projects()
            state["task_types"] = c.get_task_types()
            state["statuses"]   = c.get_task_statuses()
        except Exception as e:
            log("[kitsu] error: " + str(e)); return
        fill("TaskStatus", state["statuses"], placeholder="no change")
        itm["TaskStatus"].Enabled = True
        for i, x in enumerate(state["statuses"]):
            if x.get("short_name", "").upper() in ("WFA", "WAITING FOR APPROVAL"):
                itm["TaskStatus"].CurrentIndex = i + 1; break
        itm["BrowseKitsuBtn"].Enabled = True
        itm["AssignShotBtn"].Enabled  = True
        log(f"[kitsu] {len(state['projects'])} project(s) loaded")
        detect_current_project()

    # ── Auto-detect if current Resolve project is already a Kitsu project ───────
    def detect_current_project():
        """
        If the currently open Resolve project is named proj_seq_shot_vNNN,
        try to match it against loaded Kitsu data and restore the context.
        """
        try:
            curr_name = get_current_project().GetName()
        except Exception:
            return
        # Must match  something_something_something_vNNN
        m = re.match(r'^(.+)_v(\d+)$', curr_name, re.IGNORECASE)
        if not m:
            log(f"[detect] '{curr_name}' doesn't look like a Kitsu project name")
            return
        base = m.group(1)
        ver  = int(m.group(2))
        # base = proj_seq_shot  — split on last two underscores
        parts = base.rsplit("_", 2)
        if len(parts) != 3:
            log(f"[detect] can't parse base '{base}' into proj/seq/shot"); return
        proj_san, seq_san, shot_san = parts
        log(f"[detect] looking for proj={proj_san} seq={seq_san} shot={shot_san} v={ver}")

        c = state["client"]
        # Search through loaded projects
        for proj in state["projects"]:
            if sanitize(proj["name"]) != proj_san: continue
            try:
                seqs = c.get_sequences(proj["id"])
            except Exception: continue
            for seq in seqs:
                if sanitize(seq["name"]) != seq_san: continue
                try:
                    shots = c.get_shots(seq["id"])
                except Exception: continue
                for shot in shots:
                    if sanitize(shot["name"]) != shot_san: continue
                    # Found it!
                    state["sel_project"]  = proj
                    state["sel_sequence"] = seq
                    state["sel_shot"]     = shot
                    state["project_base"] = base
                    state["version"]      = ver
                    set_assigned(curr_name)
                    _load_tasks_for_shot(shot)
                    log(f"[detect] ✓ matched '{curr_name}' → {proj['name']} / {seq['name']} / {shot['name']}")
                    return
        log(f"[detect] no Kitsu match found for '{curr_name}'")

    # ── Shot browser window  (Show/Hide only — no RunLoop) ────────────────────
    def open_browser(mode):
        """mode = 'create' | 'assign'"""
        state["browser_mode"] = mode
        state["br_pending"]   = None

        bwin = disp.AddWindow(
            {"ID": "BrowserWin", "WindowTitle": "Shot Browser",
             "Geometry": [160, 120, 460, 420]},
            [ui.VGroup({"Spacing": 2, "MarginTop": 6, "MarginBottom": 6,
                        "MarginLeft": 8, "MarginRight": 8}, [
                ui.HGroup({"Spacing": 6, "Weight": 0}, [
                    ui.Label({"Text": "PROJECT", "StyleSheet": LBL,
                              "FixedWidth": 58}),
                    ui.ComboBox({"ID": "BrProj"}),
                ]),
                ui.HGroup({"Spacing": 6, "Weight": 0}, [
                    ui.Label({"Text": "SEQUENCE", "StyleSheet": LBL,
                              "FixedWidth": 58}),
                    ui.ComboBox({"ID": "BrSeq"}),
                ]),
                ui.Label({"Text": "SHOTS — click a row to select",
                          "StyleSheet": LBL, "Weight": 0}),
                ui.Tree({
                    "ID": "BrTree",
                    "SortingEnabled": False,
                    "AlternatingRowColors": True,
                    "RootIsDecorated": False,
                    "SelectionMode": "SingleSelection",
                    "UniformRowHeights": True,
                }),
                ui.Label({"ID": "BrSelLbl",
                          "Text": "No shot selected", "Weight": 0,
                          "StyleSheet": "color:#c8a84b;font-size:11px;"}),
                ui.HGroup({"Spacing": 6, "Weight": 0}, [
                    ui.Button({"ID": "BrCancel",  "Text": "Cancel",
                               "FixedHeight": 26, "FixedWidth": 90,
                               "StyleSheet": BTN_GRAY}),
                    ui.HGap(0),
                    ui.Button({"ID": "BrConfirm", "Text": "✓  Confirm",
                               "Enabled": False,
                               "FixedHeight": 26, "FixedWidth": 120,
                               "StyleSheet": BTN_BLUE}),
                ]),
            ])]
        )
        state["browser_win"] = bwin
        bitm = bwin.GetItems()

        # Tree: single column, shot name only (thumbnails via separate label trick
        # not possible in Tree; we show them as text icons in col 0)
        hdr = bitm["BrTree"].NewItem()
        hdr.Text[0] = "Shot"
        bitm["BrTree"].SetHeaderItem(hdr)
        bitm["BrTree"].ColumnWidth[0] = 420

        # ── inner helpers ─────────────────────────────────────────────────────
        def _br_load_seqs():
            idx = bitm["BrProj"].CurrentIndex - 1
            if idx < 0: return
            proj = state["projects"][idx]
            try:
                state["br_sequences"] = state["client"].get_sequences(proj["id"])
            except Exception as e:
                log("[browser] " + str(e)); return
            bitm["BrSeq"].Clear()
            bitm["BrSeq"].AddItem("select sequence")
            for sq in state["br_sequences"]:
                bitm["BrSeq"].AddItem(sq["name"])
            sv2 = load_settings()
            for i, sq in enumerate(state["br_sequences"]):
                if sq["id"] == sv2.get("last_sequence"):
                    bitm["BrSeq"].CurrentIndex = i + 1
                    _br_load_shots(); break

        def _br_load_shots():
            idx = bitm["BrSeq"].CurrentIndex - 1
            if idx < 0: return
            seq = state["br_sequences"][idx]
            try:
                state["br_shots"] = state["client"].get_shots(seq["id"])
            except Exception as e:
                log("[browser] " + str(e)); return
            _br_rebuild_tree()

        def _br_rebuild_tree():
            tree  = bitm["BrTree"]
            shots = state["br_shots"]
            tree.Clear()
            state["br_pending"]       = None
            bitm["BrSelLbl"].Text     = "No shot selected"
            bitm["BrConfirm"].Enabled = False

            # Download thumbnails and embed as base64 text in a hidden column,
            # but since Tree can't render images, we show a  ▪ placeholder and
            # rely on the shot name. Thumbnails are cached for potential future use.
            client = state["client"]
            for shot in shots:
                get_thumb_path(client, shot["id"])   # pre-cache silently
                itrow = tree.NewItem()
                itrow.Text[0] = shot.get("name", shot["id"])
                tree.AddTopLevelItem(itrow)

        # ── events ────────────────────────────────────────────────────────────
        def on_br_close(ev):    bwin.Hide()

        def on_br_click(ev):
            w = ev["who"]
            if w == "BrCancel":
                bwin.Hide()
            elif w == "BrConfirm":
                shot = state["br_pending"]
                if not shot: return
                idx_p = bitm["BrProj"].CurrentIndex - 1
                idx_s = bitm["BrSeq"].CurrentIndex  - 1
                if idx_p < 0 or idx_s < 0: return
                bwin.Hide()
                _on_shot_confirmed(state["projects"][idx_p],
                                   state["br_sequences"][idx_s], shot)

        def on_br_combo(ev):
            w = ev["who"]
            if   w == "BrProj": _br_load_seqs()
            elif w == "BrSeq":  _br_load_shots()

        def on_br_tree_click(ev):
            item = ev.get("item") or ev.get("Item")
            if item is None: return
            name = item.Text[0]
            for shot in state["br_shots"]:
                if shot.get("name") == name:
                    state["br_pending"]       = shot
                    bitm["BrSelLbl"].Text     = f"● {shot['name']}"
                    bitm["BrConfirm"].Enabled = True
                    break

        bwin.On.BrowserWin.Close           = on_br_close
        bwin.On.BrCancel.Clicked           = on_br_click
        bwin.On.BrConfirm.Clicked          = on_br_click
        bwin.On.BrProj.CurrentIndexChanged = on_br_combo
        bwin.On.BrSeq.CurrentIndexChanged  = on_br_combo
        bwin.On.BrTree.ItemClicked         = on_br_tree_click

        # Fill project combo
        bitm["BrProj"].Clear()
        bitm["BrProj"].AddItem("select project")
        for p in state["projects"]: bitm["BrProj"].AddItem(p["name"])
        sv = load_settings()
        for i, p in enumerate(state["projects"]):
            if p["id"] == sv.get("last_project"):
                bitm["BrProj"].CurrentIndex = i + 1
                _br_load_seqs(); break

        bwin.Show()

    # ── Called when user confirms a shot in the browser ───────────────────────
    def _on_shot_confirmed(proj, seq, shot):
        state["sel_project"]  = proj
        state["sel_sequence"] = seq
        state["sel_shot"]     = shot
        sv = load_settings()
        sv.update({"last_project": proj["id"], "last_sequence": seq["id"],
                   "last_shot": shot["id"]})
        save_settings(sv)

        base = build_project_base(proj["name"], seq["name"], shot["name"])
        state["project_base"] = base
        existing = get_all_resolve_project_names()
        new_name, ver = next_version_name(base, existing)
        state["version"] = ver

        if state["browser_mode"] == "create":
            log(f"[resolve] creating project '{new_name}'...")
            new_proj = get_project_manager().CreateProject(new_name)
            if not new_proj:
                log(f"[resolve] ERROR: could not create '{new_name}'"); return
            set_assigned(new_name)
            _load_tasks_for_shot(shot)
            log(f"[resolve] project '{new_name}' created & opened ✓")
        else:
            # assign mode — copy source project
            src = state["assign_src"]
            log(f"[resolve] copying '{src}'  →  '{new_name}'...")
            if not copy_resolve_project(src, new_name, log=log):
                log("[resolve] ERROR: project copy failed"); return
            set_assigned(new_name)
            _load_tasks_for_shot(shot)
            log(f"[resolve] '{new_name}' ready ✓  ('{src}' untouched)")

    # ── Assign-Shot window  (Show/Hide only — no RunLoop) ─────────────────────
    def open_assign_win():
        names = get_all_resolve_project_names()

        awin = disp.AddWindow(
            {"ID": "AssignWin", "WindowTitle": "Select Resolve Project to Copy",
             "Geometry": [160, 180, 440, 220]},
            [ui.VGroup({"Spacing": 8}, [
                ui.Label({"Text": "SELECT RESOLVE PROJECT TO COPY",
                          "StyleSheet": LBL}),
                ui.ComboBox({"ID": "AsnCB"}),
                ui.Label({"ID": "AsnHint",
                          "Text": "This project will be COPIED — original stays untouched.",
                          "StyleSheet": "color:#8a9a8a;font-size:10px;",
                          "WordWrap": True}),
                ui.HGroup({"Spacing": 6}, [
                    ui.Button({"ID": "AsnCancel", "Text": "Cancel",
                               "FixedHeight": 28, "StyleSheet": BTN_GRAY}),
                    ui.Button({"ID": "AsnNext",
                               "Text": "Next  →  Pick Kitsu Shot",
                               "FixedHeight": 28, "StyleSheet": BTN_ORANGE}),
                ]),
            ])]
        )
        state["assign_win"] = awin
        aitm = awin.GetItems()

        aitm["AsnCB"].Clear()
        aitm["AsnCB"].AddItem("select a project")
        for n in names: aitm["AsnCB"].AddItem(n)

        def on_asn_close(ev):
            awin.Hide()

        def on_asn_click(ev):
            w = ev["who"]
            if w == "AsnCancel":
                awin.Hide()
            elif w == "AsnNext":
                idx = aitm["AsnCB"].CurrentIndex - 1
                if idx < 0 or idx >= len(names):
                    log("[assign] no project selected"); return
                state["assign_src"] = names[idx]
                log(f"[assign] source: {names[idx]}")
                awin.Hide()
                open_browser("assign")

        awin.On.AssignWin.Close  = on_asn_close
        awin.On.AsnCancel.Clicked = on_asn_click
        awin.On.AsnNext.Clicked   = on_asn_click

        awin.Show()

    # ── Tasks ─────────────────────────────────────────────────────────────────
    def _load_tasks_for_shot(shot):
        log("[kitsu] loading tasks...")
        try:
            state["shot_tasks"] = state["client"].get_shot_tasks(shot["id"])
        except Exception as e:
            log("[kitsu] error: " + str(e)); return
        itm["Task"].Clear()
        tasks = state["shot_tasks"]
        if not tasks: itm["Task"].AddItem("no tasks"); return
        itm["Task"].AddItem("select task")
        tt = {t["id"]: t["name"] for t in state["task_types"]}
        for t in tasks: itm["Task"].AddItem(tt.get(t.get("task_type_id"), "?"))
        itm["Task"].Enabled = True
        restore("Task", tasks, load_settings().get("last_task"))
        update_publish_btn()

    # ── Publish ───────────────────────────────────────────────────────────────
    def do_publish():
        idx_task = itm["Task"].CurrentIndex - 1
        task   = state["shot_tasks"][idx_task] if 0 <= idx_task < len(state["shot_tasks"]) else None
        idx_st = itm["TaskStatus"].CurrentIndex - 1
        status = state["statuses"][idx_st] if 0 <= idx_st < len(state["statuses"]) else None
        comment = itm["Comment"].PlainText.strip()
        pi = itm["Preset"].CurrentIndex
        preset = itm["Preset"].GetItem(pi) if pi > 0 else None

        if not task: log("[error] no task selected"); return

        root  = itm["RenderRoot"].Text.strip()
        base  = state.get("project_base")
        ver   = state.get("version", 1)
        seq   = state.get("sel_sequence")
        shot  = state.get("sel_shot")
        if not (root and base and seq and shot):
            log("[error] shot not assigned or render root missing"); return

        seq_name = sanitize(seq["name"])
        shot_name = sanitize(shot["name"])

        file_stem = f"{seq_name}-{shot_name}_Rendering_v{ver:04d}"

        folder = os.path.join(
            root,
            seq_name,
            shot_name,
            "Renders",
            "2dRender",
            "Rendering",
            f"v{ver:04d}"
        )

        os.makedirs(folder, exist_ok=True)

        sv = load_settings(); sv["render_root"] = root; sv["last_task"] = task["id"]
        save_settings(sv)

        itm["PublishBtn"].Enabled = False
        project = get_current_project()
        try:
            log(f"[render] {folder}  /  {file_stem}.mp4")
            job_id, out_file = setup_render_job(project, folder, file_stem, preset)
            wait_for_render(project, job_id, log=log)

            actual = None
            for c in [out_file, os.path.splitext(out_file)[0] + "_1.mp4"]:
                if os.path.exists(c): actual = c; break
            if not actual:
                for fn in sorted(os.listdir(folder), reverse=True):
                    if fn.startswith(file_stem) and fn.endswith(".mp4"):
                        actual = os.path.join(folder, fn); break
            if not actual:
                raise RuntimeError("Rendered file not found in: " + folder)

            log(f"[render] file={actual}")
            state["client"].upload_preview_with_status(
                task["id"], actual, comment,
                status["id"] if status else None, log=log)
            log("[kitsu] published ✓")
        except Exception as e:
            log("[error] " + str(e))
        itm["PublishBtn"].Enabled = True

    # ── Main window events ────────────────────────────────────────────────────
    def on_close(ev):
        disp.ExitLoop()

    def on_click(ev):
        w = ev["who"]
        if   w == "LoginBtn":       do_login()
        elif w == "BrowseKitsuBtn": open_browser("create")
        elif w == "AssignShotBtn":  open_assign_win()
        elif w == "PublishBtn":     do_publish()
        elif w == "BrowseRoot":
            d = fusion.RequestDir(state["render_root"])
            if d:
                itm["RenderRoot"].Text = str(d)
                state["render_root"]   = str(d)
                update_render_preview()

    def on_task_combo(ev):
        t_idx = itm["Task"].CurrentIndex - 1
        if 0 <= t_idx < len(state["shot_tasks"]):
            sv = load_settings(); sv["last_task"] = state["shot_tasks"][t_idx]["id"]
            save_settings(sv)
        update_publish_btn()

    win.On.KitsuWin.Close                  = on_close
    win.On.LoginBtn.Clicked                = on_click
    win.On.BrowseKitsuBtn.Clicked          = on_click
    win.On.AssignShotBtn.Clicked           = on_click
    win.On.PublishBtn.Clicked              = on_click
    win.On.BrowseRoot.Clicked              = on_click
    win.On.Task.CurrentIndexChanged        = on_task_combo

    # ── Auto-login ────────────────────────────────────────────────────────────
    if s.get("server") and s.get("email") and s.get("password"):
        log("[kitsu] auto-signing in...")
        do_login()

    win.Show()
    disp.RunLoop()
    win.Hide()


if __name__ == "__main__":
    main()
