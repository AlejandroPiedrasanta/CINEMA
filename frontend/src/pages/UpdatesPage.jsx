import { useEffect, useState, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Upload, Trash2, Download, Star, RefreshCw, Package,
  Clock, FileArchive, ArrowRight, Monitor, Cloud, CheckCircle2, Database
} from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { getUpdatesHistory, uploadAppUpdate, deleteUpdate, setLatestUpdate, getUpdateDownloadUrl } from "@/lib/api";

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

const CHANNEL_LABELS = { stable: "Estable", beta: "Beta", alpha: "Alpha" };

// How-it-works steps
const STEPS = [
  { icon: Cloud, label: "Actualizas el código aquí", sub: "Haces cambios en la app web" },
  { icon: Download, label: "Ajustes → Descargar para Windows", sub: "Se registra automáticamente en la base de datos" },
  { icon: Database, label: "Todas las apps lo detectan", sub: "Al compartir la misma base de datos, todas ven la nueva versión" },
  { icon: Monitor, label: "Notificación automática", sub: "La app muestra un aviso con botón para descargar" },
];

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
      toast({ title: `Versión ${version} publicada correctamente` });
      setSelectedFile(null); setVersion(""); setNotes(""); setChannel("stable");
      load();
    } catch (e) {
      toast({ title: "Error al subir", description: e.response?.data?.detail || "Error", variant: "destructive" });
    } finally { setUploading(false); }
  };

  const handleDelete = async (id) => {
    if (!window.confirm("¿Eliminar esta versión?")) return;
    try { await deleteUpdate(id); toast({ title: "Versión eliminada" }); load(); }
    catch { toast({ title: "Error al eliminar", variant: "destructive" }); }
  };

  const handleSetLatest = async (id) => {
    try { await setLatestUpdate(id); toast({ title: "Versión marcada como activa" }); load(); }
    catch { toast({ title: "Error", variant: "destructive" }); }
  };

  const latest = history.find(h => h.is_latest);

  return (
    <div className="px-6 py-8 max-w-5xl mx-auto">

      {/* Header */}
      <motion.div initial={{ opacity: 0, y: -16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }} className="mb-8">
        <h1 className="text-5xl font-black gradient-text tracking-tight" style={{ fontFamily: "Cabinet Grotesk, sans-serif" }}>
          Actualizaciones
        </h1>
        <p className="text-sm text-slate-500 font-medium mt-1.5">
          Publica nuevas versiones de tu App de Escritorio
        </p>
      </motion.div>

      {/* Stats */}
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }}
        className="grid grid-cols-3 gap-4 mb-6">
        {[
          { label: "Versión activa", value: latest ? `v${latest.version}` : "—", icon: Star, color: "bg-emerald-100 text-emerald-600" },
          { label: "Total versiones", value: history.length, icon: Package, color: "bg-indigo-100 text-indigo-600" },
          { label: "Última subida", value: latest ? formatDate(latest.created_at) : "—", icon: Clock, color: "bg-amber-100 text-amber-600" },
        ].map(({ label, value, icon: Icon, color }) => (
          <div key={label} className="glass rounded-3xl p-5 flex items-center gap-4">
            <div className={`w-10 h-10 rounded-2xl flex items-center justify-center flex-shrink-0 ${color}`}>
              <Icon size={18} strokeWidth={1.8} />
            </div>
            <div>
              <p className="text-xl font-black text-slate-900" style={{ fontFamily: "Cabinet Grotesk, sans-serif" }}>{value}</p>
              <p className="text-xs text-slate-400 font-medium">{label}</p>
            </div>
          </div>
        ))}
      </motion.div>

      {/* How it works */}
      <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}
        className="glass rounded-3xl p-6 mb-5">
        <h2 className="text-xs font-black text-slate-500 uppercase tracking-widest mb-5">¿Cómo funciona?</h2>
        <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3">
          {STEPS.map(({ icon: Icon, label, sub }, i) => (
            <div key={i} className="flex items-center gap-3 flex-1">
              <div className="flex flex-col items-center gap-2 flex-1">
                <div className="w-11 h-11 rounded-2xl bg-indigo-50 flex items-center justify-center flex-shrink-0">
                  <Icon size={20} className="text-indigo-500" strokeWidth={1.7} />
                </div>
                <div className="text-center">
                  <p className="text-[11px] font-black text-slate-700 leading-tight">{label}</p>
                  <p className="text-[10px] text-slate-400 mt-0.5 leading-tight">{sub}</p>
                </div>
              </div>
              {i < STEPS.length - 1 && (
                <ArrowRight size={16} className="text-slate-300 flex-shrink-0 hidden sm:block mt-[-20px]" />
              )}
            </div>
          ))}
        </div>
      </motion.div>

      {/* Upload form */}
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }}
        className="glass rounded-3xl p-6 mb-5 space-y-5">
        <div>
          <h2 className="text-xs font-black text-slate-500 uppercase tracking-widest">Subir versión manualmente</h2>
          <p className="text-xs text-slate-400 mt-1">
            Las versiones descargadas desde <strong>Ajustes → App para Windows</strong> se registran automáticamente. 
            Usa este formulario solo si necesitas subir un archivo diferente.
          </p>
        </div>

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
          <label className="text-[10px] font-black text-slate-400 uppercase tracking-wider mb-1.5 block">Notas de la versión (opcional)</label>
          <textarea value={notes} onChange={e => setNotes(e.target.value)} rows={2}
            placeholder="¿Qué cambió en esta versión?"
            className="w-full px-4 py-2.5 text-sm glass rounded-2xl border-white/50 bg-transparent focus:outline-none focus:ring-2 focus:ring-[var(--t-from)]/30 text-slate-700 resize-none"
            data-testid="notes-input" />
        </div>

        {/* File drop */}
        <div>
          <label className="text-[10px] font-black text-slate-400 uppercase tracking-wider mb-1.5 block">
            Archivo (EXE, ZIP, MSI...) *
          </label>
          <motion.div whileHover={{ scale: 1.005 }}
            onDrop={handleFileDrop}
            onDragOver={e => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
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
                <motion.button whileHover={{ scale: 1.1 }} onClick={e => { e.stopPropagation(); setSelectedFile(null); }}
                  className="ml-2 p-1.5 rounded-full hover:bg-red-100 text-slate-400 hover:text-red-500 transition-colors">
                  <Trash2 size={14} />
                </motion.button>
              </div>
            ) : (
              <>
                <div className="w-12 h-12 rounded-2xl bg-indigo-100/80 flex items-center justify-center mx-auto mb-3">
                  <Upload size={22} className="text-indigo-500" />
                </div>
                <p className="text-sm font-bold text-slate-600">Arrastra el ZIP aquí o haz clic para seleccionar</p>
                <p className="text-xs text-slate-400 mt-1">Cualquier formato · EXE, ZIP, MSI, etc.</p>
              </>
            )}
            <input ref={fileRef} type="file" className="hidden" data-testid="file-input"
              onChange={e => { if (e.target.files[0]) setSelectedFile(e.target.files[0]); }} />
          </motion.div>
        </div>

        <motion.button whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}
          onClick={handleUpload}
          disabled={uploading || !selectedFile || !version.trim()}
          data-testid="upload-btn"
          className="w-full flex items-center justify-center gap-2 py-3 rounded-2xl btn-primary text-white text-sm font-bold disabled:opacity-50 disabled:cursor-not-allowed">
          {uploading
            ? <><RefreshCw size={16} className="animate-spin" /> Publicando…</>
            : <><Upload size={16} /> Publicar actualización</>}
        </motion.button>
      </motion.div>

      {/* History */}
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}
        className="glass rounded-3xl overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/30">
          <h2 className="text-sm font-black text-slate-700" style={{ fontFamily: "Cabinet Grotesk, sans-serif" }}>
            Historial de versiones
          </h2>
          <span className="text-xs font-bold px-2.5 py-1 rounded-full bg-slate-100 text-slate-500">
            {history.length} versiones
          </span>
        </div>

        {loadingHistory ? (
          <div className="p-6 space-y-3">
            {[...Array(2)].map((_, i) => <div key={i} className="h-14 glass rounded-2xl animate-pulse" />)}
          </div>
        ) : history.length === 0 ? (
          <div className="py-16 text-center">
            <Package size={36} className="mx-auto text-slate-200 mb-3" />
            <p className="text-slate-400 text-sm font-medium">Aún no hay versiones registradas</p>
            <p className="text-slate-300 text-xs mt-1">Ve a <strong>Ajustes → App para Windows</strong> y descarga la app — se registrará automáticamente aquí</p>
          </div>
        ) : (
          <div className="divide-y divide-white/20">
            {history.map((v, idx) => (
              <motion.div key={v.id} initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: idx * 0.04 }}
                className="flex items-center gap-4 px-6 py-4 hover:bg-white/20 transition-colors"
                data-testid={`update-row-${v.id}`}>

                {/* Version */}
                <div className="flex items-center gap-2 w-32 flex-shrink-0">
                  <span className="text-base font-black text-slate-900" style={{ fontFamily: "Cabinet Grotesk, sans-serif" }}>v{v.version}</span>
                  {v.is_latest && (
                    <span className="flex items-center gap-1 text-[9px] font-black px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700">
                      <CheckCircle2 size={9} /> ACTIVA
                    </span>
                  )}
                </div>

                {/* Channel */}
                <span className={`text-[10px] font-black px-2.5 py-1 rounded-full flex-shrink-0 ${CHANNEL_STYLES[v.channel] || CHANNEL_STYLES.stable}`}>
                  {CHANNEL_LABELS[v.channel] || v.channel}
                </span>

                {/* Filename */}
                <p className="text-xs text-slate-500 font-medium truncate flex-1 min-w-0">{v.filename}</p>

                {/* Size */}
                <span className="text-xs text-slate-400 font-medium flex-shrink-0 hidden sm:block">{formatBytes(v.file_size)}</span>

                {/* Date */}
                <span className="text-xs text-slate-400 flex-shrink-0 hidden md:block">{formatDate(v.created_at)}</span>

                {/* Notes */}
                {v.notes && (
                  <span className="text-xs text-slate-400 italic truncate max-w-[130px] hidden lg:block">{v.notes}</span>
                )}

                {/* Actions */}
                <div className="flex items-center gap-1 flex-shrink-0">
                  <a href={getUpdateDownloadUrl(v.id)} target="_blank" rel="noreferrer" data-testid={`download-btn-${v.id}`}>
                    <motion.button whileHover={{ scale: 1.1 }} whileTap={{ scale: 0.9 }}
                      className="p-2 rounded-xl hover:bg-indigo-50 text-slate-400 hover:text-indigo-600 transition-colors" title="Descargar">
                      <Download size={14} />
                    </motion.button>
                  </a>
                  {!v.is_latest && (
                    <motion.button whileHover={{ scale: 1.1 }} whileTap={{ scale: 0.9 }}
                      onClick={() => handleSetLatest(v.id)} data-testid={`set-latest-btn-${v.id}`}
                      className="p-2 rounded-xl hover:bg-amber-50 text-slate-400 hover:text-amber-600 transition-colors" title="Marcar como activa">
                      <Star size={14} />
                    </motion.button>
                  )}
                  <motion.button whileHover={{ scale: 1.1 }} whileTap={{ scale: 0.9 }}
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
