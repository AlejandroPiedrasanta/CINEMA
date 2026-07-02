import { useEffect, useState, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Upload, Trash2, Download, Star, RefreshCw, Copy, Check, Package, Clock, FileArchive, ChevronDown, ChevronUp, AlertCircle, CheckCircle2, Wifi } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { getUpdatesHistory, uploadAppUpdate, deleteUpdate, setLatestUpdate, getUpdateDownloadUrl, checkRemoteUpdate } from "@/lib/api";

const BASE_URL = window.__API_BASE_URL__ || process.env.REACT_APP_BACKEND_URL;

function formatBytes(bytes) {
  if (!bytes) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function formatDate(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("es-GT", { dateStyle: "short", timeStyle: "short" });
}

const CHANNEL_STYLES = {
  stable: "bg-emerald-100 text-emerald-700",
  beta:   "bg-amber-100 text-amber-700",
  alpha:  "bg-red-100 text-red-700",
};

export default function UpdatesPage() {
  const { toast } = useToast();
  const fileRef = useRef();

  // Upload state
  const [version, setVersion] = useState("");
  const [notes, setNotes] = useState("");
  const [channel, setChannel] = useState("stable");
  const [selectedFile, setSelectedFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);

  // History
  const [history, setHistory] = useState([]);
  const [loadingHistory, setLoadingHistory] = useState(true);

  // Remote check (Desktop App)
  const [remoteUrl, setRemoteUrl] = useState(() => localStorage.getItem("cp_update_server_url") || "");
  const [localVersion, setLocalVersion] = useState(() => localStorage.getItem("cp_local_version") || "1.0.0");
  const [checkResult, setCheckResult] = useState(null);
  const [checking, setChecking] = useState(false);

  // UI
  const [copied, setCopied] = useState(false);
  const [showRemoteCheck, setShowRemoteCheck] = useState(false);

  const apiUrl = `${BASE_URL}/api/updates/latest`;

  const load = async () => {
    setLoadingHistory(true);
    try { setHistory(await getUpdatesHistory()); }
    catch { toast({ title: "Error al cargar historial", variant: "destructive" }); }
    finally { setLoadingHistory(false); }
  };

  useEffect(() => { load(); }, []);

  const handleFileDrop = (e) => {
    e.preventDefault(); setDragOver(false);
    const f = e.dataTransfer.files[0];
    if (f) setSelectedFile(f);
  };

  const handleUpload = async () => {
    if (!selectedFile) { toast({ title: "Selecciona un archivo primero", variant: "destructive" }); return; }
    if (!version.trim()) { toast({ title: "Ingresa un número de versión (ej: 1.0.1)", variant: "destructive" }); return; }
    setUploading(true);
    try {
      await uploadAppUpdate(selectedFile, version.trim(), notes, channel);
      toast({ title: `Versión ${version} subida correctamente` });
      setSelectedFile(null); setVersion(""); setNotes(""); setChannel("stable");
      load();
    } catch (e) {
      toast({ title: "Error al subir", description: e.response?.data?.detail || "Error", variant: "destructive" });
    } finally { setUploading(false); }
  };

  const handleDelete = async (id) => {
    if (!window.confirm("¿Eliminar esta versión?")) return;
    try { await deleteUpdate(id); toast({ title: "Versión eliminada" }); load(); }
    catch { toast({ title: "Error", variant: "destructive" }); }
  };

  const handleSetLatest = async (id) => {
    try { await setLatestUpdate(id); toast({ title: "Versión marcada como activa" }); load(); }
    catch { toast({ title: "Error", variant: "destructive" }); }
  };

  const handleCopy = (text) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleCheckRemote = async () => {
    if (!remoteUrl.trim()) { toast({ title: "Ingresa la URL del servidor", variant: "destructive" }); return; }
    localStorage.setItem("cp_update_server_url", remoteUrl);
    localStorage.setItem("cp_local_version", localVersion);
    setChecking(true); setCheckResult(null);
    try {
      const result = await checkRemoteUpdate(remoteUrl.trim(), localVersion);
      setCheckResult(result);
    } catch (e) {
      toast({ title: "No se pudo conectar", description: e.response?.data?.detail || "Error", variant: "destructive" });
    } finally { setChecking(false); }
  };

  const latest = history.find(h => h.is_latest);

  return (
    <div className="px-6 py-8 max-w-5xl mx-auto">
      {/* Header */}
      <motion.div initial={{ opacity:0, y:-16 }} animate={{ opacity:1, y:0 }} transition={{ duration:0.4 }} className="mb-8">
        <h1 className="text-5xl font-black gradient-text tracking-tight" style={{ fontFamily:"Cabinet Grotesk, sans-serif" }}>
          Actualizaciones
        </h1>
        <p className="text-sm text-slate-500 font-medium mt-1.5">
          Gestiona las versiones de tu app de escritorio
        </p>
      </motion.div>

      {/* Stats row */}
      <motion.div initial={{ opacity:0, y:10 }} animate={{ opacity:1, y:0 }} transition={{ delay:0.05 }}
        className="grid grid-cols-3 gap-4 mb-6">
        {[
          { label: "Versión activa", value: latest?.version || "—", icon: Star, color: "bg-emerald-100 text-emerald-600" },
          { label: "Total versiones", value: history.length, icon: Package, color: "bg-indigo-100 text-indigo-600" },
          { label: "Última subida", value: latest ? formatDate(latest.created_at) : "—", icon: Clock, color: "bg-amber-100 text-amber-600" },
        ].map(({ label, value, icon: Icon, color }) => (
          <div key={label} className="glass rounded-3xl p-5 flex items-center gap-4">
            <div className={`w-10 h-10 rounded-2xl flex items-center justify-center flex-shrink-0 ${color}`}>
              <Icon size={18} strokeWidth={1.8} />
            </div>
            <div>
              <p className="text-xl font-black text-slate-900" style={{ fontFamily:"Cabinet Grotesk, sans-serif" }}>{value}</p>
              <p className="text-xs text-slate-400 font-medium">{label}</p>
            </div>
          </div>
        ))}
      </motion.div>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-5">

        {/* LEFT: Upload */}
        <motion.div initial={{ opacity:0, y:20 }} animate={{ opacity:1, y:0 }} transition={{ delay:0.1 }}
          className="lg:col-span-3 glass rounded-3xl p-6 space-y-5">
          <h2 className="text-xs font-black text-slate-500 uppercase tracking-widest">Subir nueva versión</h2>

          {/* Version + Channel */}
          <div className="flex gap-3">
            <div className="flex-1">
              <label className="text-[10px] font-black text-slate-400 uppercase tracking-wider mb-1.5 block">Número de versión *</label>
              <input value={version} onChange={e => setVersion(e.target.value)} placeholder="Ej: 1.2.0"
                className="w-full px-4 py-2.5 text-sm glass rounded-2xl border-white/50 bg-transparent focus:outline-none focus:ring-2 focus:ring-[var(--t-from)]/30 text-slate-700 font-bold"
                data-testid="version-input" />
            </div>
            <div className="w-36">
              <label className="text-[10px] font-black text-slate-400 uppercase tracking-wider mb-1.5 block">Canal</label>
              <select value={channel} onChange={e => setChannel(e.target.value)}
                className="w-full px-4 py-2.5 text-sm glass rounded-2xl border-white/50 bg-transparent focus:outline-none focus:ring-2 focus:ring-[var(--t-from)]/30 text-slate-700 font-bold"
                data-testid="channel-select">
                <option value="stable" className="bg-white">Estable</option>
                <option value="beta" className="bg-white">Beta</option>
                <option value="alpha" className="bg-white">Alpha</option>
              </select>
            </div>
          </div>

          {/* Notes */}
          <div>
            <label className="text-[10px] font-black text-slate-400 uppercase tracking-wider mb-1.5 block">Notas de la versión</label>
            <textarea value={notes} onChange={e => setNotes(e.target.value)} rows={3}
              placeholder="¿Qué cambió en esta versión? (opcional)"
              className="w-full px-4 py-2.5 text-sm glass rounded-2xl border-white/50 bg-transparent focus:outline-none focus:ring-2 focus:ring-[var(--t-from)]/30 text-slate-700 resize-none"
              data-testid="notes-input" />
          </div>

          {/* File drop zone */}
          <div>
            <label className="text-[10px] font-black text-slate-400 uppercase tracking-wider mb-1.5 block">Archivo de actualización *</label>
            <motion.div whileHover={{ scale:1.005 }}
              onDrop={handleFileDrop} onDragOver={e => { e.preventDefault(); setDragOver(true); }} onDragLeave={() => setDragOver(false)}
              onClick={() => fileRef.current?.click()}
              className={`border-2 border-dashed rounded-3xl p-8 text-center cursor-pointer transition-all ${dragOver ? "border-indigo-400 bg-indigo-50/60" : selectedFile ? "border-emerald-300 bg-emerald-50/30" : "border-indigo-200/60 bg-indigo-50/10 hover:bg-indigo-50/30 hover:border-indigo-300"}`}
              data-testid="file-drop-zone">
              {selectedFile ? (
                <div className="flex items-center justify-center gap-3">
                  <FileArchive size={28} className="text-emerald-500 flex-shrink-0" />
                  <div className="text-left">
                    <p className="font-bold text-slate-800 text-sm">{selectedFile.name}</p>
                    <p className="text-xs text-slate-400">{formatBytes(selectedFile.size)}</p>
                  </div>
                  <motion.button whileHover={{ scale:1.1 }} onClick={e => { e.stopPropagation(); setSelectedFile(null); }}
                    className="ml-2 p-1.5 rounded-full hover:bg-red-100 text-slate-400 hover:text-red-500 transition-colors">
                    <Trash2 size={14} />
                  </motion.button>
                </div>
              ) : (
                <>
                  <div className="w-12 h-12 rounded-2xl bg-indigo-100/80 flex items-center justify-center mx-auto mb-3">
                    <Upload size={22} className="text-indigo-500" />
                  </div>
                  <p className="text-sm font-bold text-slate-600">Arrastra tu archivo aquí</p>
                  <p className="text-xs text-slate-400 mt-1">EXE, ZIP, MSI, o cualquier formato · Sin límite de tamaño</p>
                </>
              )}
              <input ref={fileRef} type="file" className="hidden" data-testid="file-input"
                onChange={e => { if (e.target.files[0]) setSelectedFile(e.target.files[0]); }} />
            </motion.div>
          </div>

          {/* Upload button */}
          <motion.button whileHover={{ scale:1.02 }} whileTap={{ scale:0.98 }}
            onClick={handleUpload} disabled={uploading || !selectedFile || !version.trim()}
            data-testid="upload-btn"
            className="w-full flex items-center justify-center gap-2 py-3 rounded-2xl btn-primary text-white text-sm font-bold disabled:opacity-50 disabled:cursor-not-allowed transition-all">
            {uploading ? <><RefreshCw size={16} className="animate-spin" /> Subiendo…</> : <><Upload size={16} /> Publicar actualización</>}
          </motion.button>
        </motion.div>

        {/* RIGHT: API URL + Check */}
        <div className="lg:col-span-2 space-y-4">

          {/* API URL card */}
          <motion.div initial={{ opacity:0, y:20 }} animate={{ opacity:1, y:0 }} transition={{ delay:0.15 }}
            className="glass rounded-3xl p-5 space-y-4">
            <h2 className="text-xs font-black text-slate-500 uppercase tracking-widest">URL de auto-actualización</h2>
            <p className="text-xs text-slate-500 leading-relaxed">
              La App de Escritorio usa esta URL para verificar si hay nuevas versiones disponibles.
            </p>
            <div className="flex items-center gap-2">
              <code className="flex-1 text-[10px] bg-slate-900/5 text-slate-700 px-3 py-2.5 rounded-xl font-mono break-all leading-relaxed">
                {apiUrl}
              </code>
              <motion.button whileHover={{ scale:1.1 }} whileTap={{ scale:0.9 }} onClick={() => handleCopy(apiUrl)}
                className="p-2.5 rounded-xl glass hover:bg-white/60 text-slate-500 flex-shrink-0"
                data-testid="copy-url-btn">
                {copied ? <Check size={15} className="text-emerald-500" /> : <Copy size={15} />}
              </motion.button>
            </div>
            <div className="bg-indigo-50/50 rounded-2xl p-3 space-y-1.5">
              <p className="text-[11px] font-black text-indigo-700 uppercase tracking-wider">¿Cómo funciona?</p>
              <ul className="text-[11px] text-slate-600 space-y-1 leading-relaxed">
                <li>1. El usuario abre la App de Escritorio</li>
                <li>2. Ingresa la URL del servidor la primera vez</li>
                <li>3. La app verifica automáticamente si hay actualizaciones</li>
                <li>4. Si hay nueva versión, muestra una notificación con botón de descarga</li>
              </ul>
            </div>
          </motion.div>

          {/* Remote check (Desktop App simulation) */}
          <motion.div initial={{ opacity:0, y:20 }} animate={{ opacity:1, y:0 }} transition={{ delay:0.2 }}
            className="glass rounded-3xl overflow-hidden">
            <button onClick={() => setShowRemoteCheck(v => !v)}
              className="w-full flex items-center justify-between px-5 py-4 text-left hover:bg-white/30 transition-colors"
              data-testid="toggle-remote-check">
              <div className="flex items-center gap-3">
                <Wifi size={16} className="text-slate-500" />
                <span className="text-sm font-bold text-slate-700">Simular App de Escritorio</span>
              </div>
              {showRemoteCheck ? <ChevronUp size={14} className="text-slate-400" /> : <ChevronDown size={14} className="text-slate-400" />}
            </button>
            <AnimatePresence>
              {showRemoteCheck && (
                <motion.div initial={{ height:0, opacity:0 }} animate={{ height:"auto", opacity:1 }} exit={{ height:0, opacity:0 }} transition={{ duration:0.25 }}
                  className="overflow-hidden border-t border-white/30">
                  <div className="p-5 space-y-3">
                    <p className="text-xs text-slate-500">Prueba cómo la app detecta actualizaciones</p>
                    <div>
                      <label className="text-[10px] font-black text-slate-400 uppercase tracking-wider mb-1 block">URL del servidor</label>
                      <input value={remoteUrl} onChange={e => setRemoteUrl(e.target.value)}
                        placeholder="https://tu-servidor.com"
                        className="w-full px-3 py-2 text-xs glass rounded-xl border-white/50 bg-transparent focus:outline-none focus:ring-2 focus:ring-[var(--t-from)]/30 text-slate-700"
                        data-testid="remote-url-input" />
                    </div>
                    <div>
                      <label className="text-[10px] font-black text-slate-400 uppercase tracking-wider mb-1 block">Versión local actual</label>
                      <input value={localVersion} onChange={e => setLocalVersion(e.target.value)}
                        placeholder="1.0.0"
                        className="w-full px-3 py-2 text-xs glass rounded-xl border-white/50 bg-transparent focus:outline-none focus:ring-2 focus:ring-[var(--t-from)]/30 text-slate-700"
                        data-testid="local-version-input" />
                    </div>
                    <motion.button whileHover={{ scale:1.02 }} whileTap={{ scale:0.98 }}
                      onClick={handleCheckRemote} disabled={checking}
                      data-testid="check-remote-btn"
                      className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl btn-primary text-white text-xs font-bold disabled:opacity-50">
                      {checking ? <><RefreshCw size={13} className="animate-spin" /> Verificando…</> : <><RefreshCw size={13} /> Verificar actualizaciones</>}
                    </motion.button>

                    {/* Result */}
                    <AnimatePresence>
                      {checkResult && (
                        <motion.div initial={{ opacity:0, y:6 }} animate={{ opacity:1, y:0 }} exit={{ opacity:0 }}
                          className={`rounded-2xl p-4 ${checkResult.has_update ? "bg-amber-50 border border-amber-200" : "bg-emerald-50 border border-emerald-200"}`}
                          data-testid="check-result">
                          <div className="flex items-center gap-2 mb-2">
                            {checkResult.has_update ? <AlertCircle size={16} className="text-amber-600" /> : <CheckCircle2 size={16} className="text-emerald-600" />}
                            <p className={`text-sm font-black ${checkResult.has_update ? "text-amber-700" : "text-emerald-700"}`}>
                              {checkResult.has_update ? "¡Nueva versión disponible!" : "App actualizada"}
                            </p>
                          </div>
                          {checkResult.has_update && (
                            <>
                              <p className="text-xs text-slate-600 mb-1">
                                <span className="font-semibold">Actual:</span> {checkResult.current_version} →{" "}
                                <span className="font-semibold">Nueva:</span> {checkResult.remote_version}
                              </p>
                              {checkResult.notes && <p className="text-xs text-slate-500 mb-3 italic">{checkResult.notes}</p>}
                              <a href={checkResult.download_url} target="_blank" rel="noreferrer"
                                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl btn-primary text-white text-xs font-bold">
                                <Download size={12} /> Descargar {checkResult.filename}
                              </a>
                            </>
                          )}
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>
        </div>
      </div>

      {/* History table */}
      <motion.div initial={{ opacity:0, y:20 }} animate={{ opacity:1, y:0 }} transition={{ delay:0.25 }}
        className="glass rounded-3xl overflow-hidden mt-5">
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/30">
          <h2 className="text-sm font-black text-slate-700" style={{ fontFamily:"Cabinet Grotesk, sans-serif" }}>Historial de versiones</h2>
          <span className="text-xs font-bold px-2.5 py-1 rounded-full bg-slate-100 text-slate-500">{history.length} versiones</span>
        </div>

        {loadingHistory ? (
          <div className="p-6 space-y-3">
            {[...Array(3)].map((_,i) => <div key={i} className="h-12 glass rounded-2xl animate-pulse" />)}
          </div>
        ) : history.length === 0 ? (
          <div className="py-16 text-center">
            <Package size={36} className="mx-auto text-slate-200 mb-3" />
            <p className="text-slate-400 text-sm font-medium">Aún no has subido ninguna versión</p>
            <p className="text-slate-300 text-xs mt-1">Usa el formulario de arriba para publicar tu primera actualización</p>
          </div>
        ) : (
          <div className="divide-y divide-white/20">
            {history.map((v, idx) => (
              <motion.div key={v.id} initial={{ opacity:0, x:-8 }} animate={{ opacity:1, x:0 }} transition={{ delay:idx*0.04 }}
                className="flex items-center gap-4 px-6 py-4 hover:bg-white/20 transition-colors"
                data-testid={`update-row-${v.id}`}>

                {/* Version badge + active */}
                <div className="flex items-center gap-2 w-28 flex-shrink-0">
                  <span className="text-base font-black text-slate-900" style={{ fontFamily:"Cabinet Grotesk, sans-serif" }}>v{v.version}</span>
                  {v.is_latest && <span className="text-[9px] font-black px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700">ACTIVA</span>}
                </div>

                {/* Channel */}
                <span className={`text-[10px] font-black px-2.5 py-1 rounded-full flex-shrink-0 ${CHANNEL_STYLES[v.channel] || CHANNEL_STYLES.stable}`}>
                  {v.channel === "stable" ? "Estable" : v.channel === "beta" ? "Beta" : "Alpha"}
                </span>

                {/* Filename */}
                <p className="text-xs text-slate-500 font-medium truncate flex-1 min-w-0">{v.filename}</p>

                {/* Size */}
                <span className="text-xs text-slate-400 font-medium flex-shrink-0 hidden sm:block">{formatBytes(v.file_size)}</span>

                {/* Date */}
                <span className="text-xs text-slate-400 flex-shrink-0 hidden md:block">{formatDate(v.created_at)}</span>

                {/* Notes preview */}
                {v.notes && (
                  <span className="text-xs text-slate-400 italic truncate max-w-[140px] hidden lg:block">{v.notes}</span>
                )}

                {/* Actions */}
                <div className="flex items-center gap-1 flex-shrink-0">
                  <a href={getUpdateDownloadUrl(v.id)} target="_blank" rel="noreferrer" data-testid={`download-btn-${v.id}`}>
                    <motion.button whileHover={{ scale:1.1 }} whileTap={{ scale:0.9 }}
                      className="p-2 rounded-xl hover:bg-indigo-50 text-slate-400 hover:text-indigo-600 transition-colors" title="Descargar">
                      <Download size={14} />
                    </motion.button>
                  </a>
                  {!v.is_latest && (
                    <motion.button whileHover={{ scale:1.1 }} whileTap={{ scale:0.9 }}
                      onClick={() => handleSetLatest(v.id)} data-testid={`set-latest-btn-${v.id}`}
                      className="p-2 rounded-xl hover:bg-amber-50 text-slate-400 hover:text-amber-600 transition-colors" title="Marcar como activa">
                      <Star size={14} />
                    </motion.button>
                  )}
                  <motion.button whileHover={{ scale:1.1 }} whileTap={{ scale:0.9 }}
                    onClick={() => handleDelete(v.id)} data-testid={`delete-update-btn-${v.id}`}
                    className="p-2 rounded-xl hover:bg-red-50 text-slate-400 hover:text-red-500 transition-colors" title="Eliminar">
                    <Trash2 size={14} />
                  </motion.button>
                </div>
              </motion.div>
            ))}
          </div>
        )}
      </motion.div>
    </div>
  );
}
