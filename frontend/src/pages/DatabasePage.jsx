import React, { useEffect, useState, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Database, Download, Upload, Save, Trash2, RefreshCw,
  Wifi, WifiOff, CheckCircle, XCircle, Loader2, FileText,
  AlertCircle, ChevronRight, Clock, HardDrive, BarChart3,
  ShieldCheck, Link2, ArrowRight, FolderOpen, Zap, Timer,
  Play, Square, RotateCcw, Folder, FileSpreadsheet, Plus,
  Star, Bookmark, ChevronDown, Sparkles, Scissors,
  Network, Server, ToggleLeft, ToggleRight, Package, Globe, MonitorSpeaker,
} from "lucide-react";
import { useSettings } from "@/context/SettingsContext";
import { useToast } from "@/hooks/use-toast";
import {
  getDbStats, testDbConnection, switchDatabase, resetDatabase,
  getReservations, getBackupHistory, createServerBackup,
  deleteBackupFile, downloadBackupUrl, downloadBackupFileUrl, restoreBackup,
} from "@/lib/api";
import { generateAllReservationsPDF } from "@/lib/generatePDF";
import { useAutoBackup } from "@/hooks/useAutoBackup";

const BASE = window.__API_BASE_URL__ || process.env.REACT_APP_BACKEND_URL;

// ─── Countdown helper ────────────────────────────────────────────────────────
function useCountdown(targetDate) {
  const [display, setDisplay] = useState("");
  useEffect(() => {
    if (!targetDate) { setDisplay(""); return; }
    const update = () => {
      const diff = targetDate - Date.now();
      if (diff <= 0) { setDisplay("ahora"); return; }
      const h = Math.floor(diff / 3_600_000);
      const m = Math.floor((diff % 3_600_000) / 60_000);
      const s = Math.floor((diff % 60_000) / 1_000);
      if (h > 0) setDisplay(`${h}h ${m}m`);
      else if (m > 0) setDisplay(`${m}m ${s}s`);
      else setDisplay(`${s}s`);
    };
    update();
    const id = setInterval(update, 1000);
    return () => clearInterval(id);
  }, [targetDate]);
  return display;
}

// ─── Time-ago helper ─────────────────────────────────────────────────────────
function timeAgo(date) {
  if (!date) return null;
  const diff = Date.now() - date;
  const m = Math.floor(diff / 60_000);
  if (m < 1) return "hace un momento";
  if (m < 60) return `hace ${m} min`;
  const h = Math.floor(m / 60);
  if (h < 24) return `hace ${h}h`;
  return `hace ${Math.floor(h / 24)}d`;
}

function fmtSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function fmtDate(iso) {
  try {
    return new Date(iso).toLocaleString("es-GT", {
      day: "2-digit", month: "short", year: "numeric",
      hour: "2-digit", minute: "2-digit",
    });
  } catch { return iso; }
}

const fadeUp = { hidden: { opacity: 0, y: 20 }, show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: [0.22, 1, 0.36, 1] } } };
const stagger = { show: { transition: { staggerChildren: 0.08 } } };

export default function DatabasePage() {
  const { language, tr, logoUrl, pdfTheme, formatCurrency, usePdfLogo, useCustomPdfLogo, pdfLogoUrl } = useSettings();
  const { toast } = useToast();
  const s = tr;

  // ── Auto-backup ────────────────────────────────────────────────────────────
  const autoBackup = useAutoBackup(`${BASE}/api/backup/download`);
  const countdown  = useCountdown(autoBackup.nextBackup);
  const [lastAgoDisplay, setLastAgoDisplay] = useState("");

  useEffect(() => {
    setLastAgoDisplay(timeAgo(autoBackup.lastBackup));
    const id = setInterval(() => setLastAgoDisplay(timeAgo(autoBackup.lastBackup)), 15_000);
    return () => clearInterval(id);
  }, [autoBackup.lastBackup]);

  // Notify on each auto-backup
  const prevCountRef = useRef(autoBackup.backupCount);
  useEffect(() => {
    if (autoBackup.backupCount > prevCountRef.current) {
      prevCountRef.current = autoBackup.backupCount;
      toast({ title: `Respaldo automático guardado ✓  (${autoBackup.backupCount} total)` });
    }
  }, [autoBackup.backupCount]);

  const [dbStats, setDbStats]           = useState(null);
  const [dbLoading, setDbLoading]       = useState(true);
  const [newDbUrl, setNewDbUrl]         = useState("");
  const [dbTestResult, setDbTestResult] = useState(null);
  const [dbConnecting, setDbConnecting] = useState(false);
  const [dbTesting, setDbTesting]       = useState(false);
  const [dbResetting, setDbResetting]   = useState(false);
  const [showClear, setShowClear]       = useState(false);
  const [clearLoading, setClearLoading] = useState(false);

  // ── Connection mode ────────────────────────────────────────────────────────
  const [connMode, setConnMode] = useState("url"); // "url" | "fields" | "nas"
  const [connFields, setConnFields] = useState({ host: "", port: "27017", user: "", pass: "", db: "cinema_events" });

  const buildUrlFromFields = () => {
    const { host, port, user, pass, db } = connFields;
    if (!host.trim()) return "";
    const base = `${host.trim()}:${port || "27017"}/${db || "cinema_events"}`;
    return user.trim() && pass.trim()
      ? `mongodb://${encodeURIComponent(user.trim())}:${encodeURIComponent(pass.trim())}@${base}`
      : `mongodb://${base}`;
  };

  const activeConnUrl = connMode === "url" ? newDbUrl : buildUrlFromFields();

  // ── DB Options (toggles) ──────────────────────────────────────────────────
  const [dbOptions, setDbOptions] = useState(() => {
    try { return JSON.parse(localStorage.getItem("cp_db_options")) || { autoTest: true, notifySwitch: true, showFullUrl: false, compressBackup: false }; }
    catch { return { autoTest: true, notifySwitch: true, showFullUrl: false, compressBackup: false }; }
  });
  const saveDbOption = (key, val) => {
    const next = { ...dbOptions, [key]: val };
    setDbOptions(next);
    localStorage.setItem("cp_db_options", JSON.stringify(next));
  };

  // ── Actualizaciones en BD ─────────────────────────────────────────────────
  const [dbUpdates, setDbUpdates] = useState([]);
  const [updatesLoading, setUpdatesLoading] = useState(false);

  const loadDbUpdates = async () => {
    setUpdatesLoading(true);
    try {
      const r = await fetch(`${BASE}/api/updates/history`);
      const data = await r.json();
      setDbUpdates(Array.isArray(data) ? data : []);
    } catch { setDbUpdates([]); }
    finally { setUpdatesLoading(false); }
  };

  const handleDeleteUpdate = async (id) => {
    if (!window.confirm("¿Eliminar esta versión?")) return;
    try {
      await fetch(`${BASE}/api/updates/${id}`, { method: "DELETE" });
      setDbUpdates(prev => prev.filter(u => u.id !== id));
      toast({ title: "Versión eliminada de la base de datos" });
    } catch { toast({ title: "Error al eliminar", variant: "destructive" }); }
  };

  const [backupHistory, setBackupHistory]   = useState([]);
  const [backupCreating, setBackupCreating] = useState(false);
  const [restoreLoading, setRestoreLoading] = useState(false);
  const [restoreResult, setRestoreResult]   = useState(null);
  const restoreInputRef     = useRef(null);
  const restoreAutoInputRef = useRef(null);

  const [pdfLoading, setPdfLoading] = useState(false);

  // ── CSV Import state ──────────────────────────────────────────────────────
  const csvImportRef                          = useRef(null);
  const [csvImportLoading, setCsvImportLoading] = useState(false);
  const [csvImportResult, setCsvImportResult]   = useState(null);

  // ── Cleanup state ─────────────────────────────────────────────────────────
  const [cleanupPreview, setCleanupPreview] = useState(null);
  const [cleanupLoading, setCleanupLoading] = useState(false);
  const [cleanupAction, setCleanupAction]   = useState(null); // 'cancelled'|'old_completed'

  // ── Connection presets (localStorage) ─────────────────────────────────────
  const [presets, setPresets] = useState(() => {
    try { return JSON.parse(localStorage.getItem("cp_db_presets")) || []; } catch { return []; }
  });
  const [presetName, setPresetName] = useState("");
  const [showAddPreset, setShowAddPreset] = useState(false);

  const savePresets = (list) => {
    setPresets(list);
    localStorage.setItem("cp_db_presets", JSON.stringify(list));
  };

  useEffect(() => { loadAll(); }, []);

  const loadAll = () => { loadDbStats(); loadBackupHistory(); loadCleanupPreview(); loadDbUpdates(); };

  const loadCleanupPreview = async () => {
    try {
      const res = await fetch(`${BASE}/api/data/cleanup?action=preview&months_old=6`, { method: "POST" });
      const data = await res.json();
      if (data.ok) setCleanupPreview(data);
    } catch (err) {
      console.error("[loadCleanupPreview]", err);
    }
  };

  const loadDbStats = () => {
    setDbLoading(true);
    getDbStats().then(setDbStats).catch(() => setDbStats(null)).finally(() => setDbLoading(false));
  };

  const loadBackupHistory = () =>
    getBackupHistory().then(setBackupHistory).catch(() => setBackupHistory([]));

  const handleDbTest = async () => {
    if (!activeConnUrl.trim()) return;
    setDbTesting(true); setDbTestResult(null);
    try {
      await testDbConnection(activeConnUrl.trim());
      setDbTestResult({ ok: true, msg: s.dbTestOk || "Conexión exitosa" });
    } catch (err) {
      setDbTestResult({ ok: false, msg: err.response?.data?.detail || "Error de conexión" });
    } finally { setDbTesting(false); }
  };

  const handleDbConnect = async () => {
    if (!activeConnUrl.trim()) return;
    setDbConnecting(true);
    try {
      if (dbOptions.autoTest) {
        try { await testDbConnection(activeConnUrl.trim()); }
        catch { toast({ title: "La prueba de conexión falló. Intenta igualmente.", variant: "destructive" }); }
      }
      await switchDatabase(activeConnUrl.trim());
      toast({ title: "Base de datos conectada ✓ — Actualizando..." });
      setNewDbUrl(""); setConnFields({ host: "", port: "27017", user: "", pass: "", db: "cinema_events" }); setDbTestResult(null);
      setTimeout(() => window.location.reload(), 1200);
    } catch (err) {
      toast({ title: err.response?.data?.detail || "Error al conectar", variant: "destructive" });
    } finally { setDbConnecting(false); }
  };

  const handleDbReset = async () => {
    setDbResetting(true);
    try {
      await resetDatabase();
      toast({ title: "Restaurado a base de datos predeterminada ✓ — Actualizando..." });
      setNewDbUrl(""); setDbTestResult(null);
      setTimeout(() => window.location.reload(), 1200);
    } catch { toast({ title: "Error", variant: "destructive" }); }
    finally { setDbResetting(false); }
  };

  const handleClearAll = async () => {
    setClearLoading(true);
    try {
      const res = await fetch(`${BASE}/api/data/clear-all`, { method: "DELETE" });
      const d = await res.json();
      setShowClear(false);
      toast({ title: `Datos eliminados — ${d.deleted_reservations} reservas, ${d.deleted_socios} socios` });
      loadAll();
    } catch { toast({ title: "Error al borrar", variant: "destructive" }); }
    finally { setClearLoading(false); }
  };

  const handleDownloadBackup = () => {
    const a = document.createElement("a");
    a.href = downloadBackupUrl(); a.download = "";
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
    toast({ title: "Descargando respaldo completo..." });
  };

  const handleCreateServerBackup = async () => {
    setBackupCreating(true);
    try {
      const r = await createServerBackup();
      toast({ title: r.message || "Respaldo guardado ✓" });
      loadBackupHistory();
    } catch (e) {
      toast({ title: e.response?.data?.detail || "Error", variant: "destructive" });
    } finally { setBackupCreating(false); }
  };

  const handleRestoreFile = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setRestoreLoading(true); setRestoreResult(null);
    try {
      const r = await restoreBackup(file);
      setRestoreResult({ ok: true, msg: r.message });
      toast({ title: r.message });
      loadAll();
    } catch (err) {
      const msg = err.response?.data?.detail || "Error al restaurar el archivo";
      setRestoreResult({ ok: false, msg });
      toast({ title: msg, variant: "destructive" });
    } finally {
      setRestoreLoading(false);
      if (restoreInputRef.current) restoreInputRef.current.value = "";
      if (restoreAutoInputRef.current) restoreAutoInputRef.current.value = "";
    }
  };

  const handleDeleteBackup = async (filename) => {
    try {
      await deleteBackupFile(filename);
      setBackupHistory(prev => prev.filter(b => b.filename !== filename));
      toast({ title: "Respaldo eliminado" });
    } catch { toast({ title: "Error", variant: "destructive" }); }
  };

  const handleExport = async (format) => {
    try {
      const res = await fetch(`${BASE}/api/export/reservations?format=${format}`);
      if (!res.ok) throw new Error();
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a"); a.href = url;
      a.download = format === "json" ? "reservaciones.json" : "reservaciones.csv";
      document.body.appendChild(a); a.click();
      document.body.removeChild(a); window.URL.revokeObjectURL(url);
      toast({ title: `Exportado como ${format.toUpperCase()} ✓` });
    } catch { toast({ title: "Error al exportar", variant: "destructive" }); }
  };

  const handleExportXLSX = async () => {
    try {
      const res = await fetch(`${BASE}/api/export/reservations/xlsx`);
      if (!res.ok) throw new Error("Error al generar Excel");
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a"); a.href = url;
      a.download = `reservaciones_${new Date().toISOString().slice(0,10)}.xlsx`;
      document.body.appendChild(a); a.click();
      document.body.removeChild(a); window.URL.revokeObjectURL(url);
      toast({ title: "Excel descargado ✓" });
    } catch (e) { toast({ title: e.message || "Error al exportar Excel", variant: "destructive" }); }
  };

  const handleCsvImport = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setCsvImportLoading(true); setCsvImportResult(null);
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(`${BASE}/api/import/reservations`, { method: "POST", body: form });
      const data = await res.json();
      setCsvImportResult(data);
      toast({ title: data.message });
      if (data.imported > 0) { loadDbStats(); loadCleanupPreview(); }
    } catch { toast({ title: "Error al importar CSV", variant: "destructive" }); }
    finally {
      setCsvImportLoading(false);
      if (csvImportRef.current) csvImportRef.current.value = "";
    }
  };

  const handleCleanup = async (action) => {
    setCleanupLoading(true); setCleanupAction(action);
    try {
      const res = await fetch(`${BASE}/api/data/cleanup?action=${action}&months_old=6`, { method: "POST" });
      const data = await res.json();
      toast({ title: data.message });
      loadDbStats(); loadCleanupPreview();
    } catch { toast({ title: "Error en limpieza", variant: "destructive" }); }
    finally { setCleanupLoading(false); setCleanupAction(null); }
  };

  const handleExportPDF = async () => {
    setPdfLoading(true);
    try {
      const reservations = await getReservations();
      if (!reservations.length) { toast({ title: "No hay reservas para exportar", variant: "destructive" }); return; }
      const logo = usePdfLogo ? (useCustomPdfLogo && pdfLogoUrl ? pdfLogoUrl : logoUrl || undefined) : null;
      await generateAllReservationsPDF(reservations, formatCurrency, logo, pdfTheme);
      toast({ title: `PDF generado — ${reservations.length} reservas ✓` });
    } catch (e) { toast({ title: e.message || "Error al generar PDF", variant: "destructive" }); }
    finally { setPdfLoading(false); }
  };

  return (
    <div className="px-6 py-8 max-w-3xl mx-auto">

      {/* ── Header ── */}
      <motion.div initial={{ opacity: 0, y: -16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }} className="mb-8">
        <h1 className="text-5xl font-black gradient-text" style={{ fontFamily: "Cabinet Grotesk, sans-serif" }}>
          Base de Datos
        </h1>
        <p className="text-sm text-slate-500 font-medium mt-1.5">Respaldos y conexión MongoDB</p>
      </motion.div>

      <motion.div variants={stagger} initial="hidden" animate="show" className="space-y-4">

        {/* ── RESPALDO AUTOMÁTICO EN PC ── */}
        <motion.div variants={fadeUp}>
          <div
            style={{ background: autoBackup.config.enabled ? "linear-gradient(135deg,rgba(236,253,245,0.95),rgba(209,250,229,0.7))" : undefined }}
            className={`glass rounded-3xl overflow-hidden transition-all duration-300 ${autoBackup.config.enabled ? "ring-2 ring-emerald-400/50" : ""}`}>

            {/* Header */}
            <div className="flex items-center justify-between px-5 py-4 border-b border-white/40">
              <div className="flex items-center gap-3">
                <div className={`w-9 h-9 rounded-xl flex items-center justify-center transition-colors ${autoBackup.config.enabled ? "bg-emerald-200" : "bg-slate-100"}`}>
                  <Zap size={16} className={autoBackup.config.enabled ? "text-emerald-700" : "text-slate-400"} />
                </div>
                <div>
                  <p className="text-sm font-black text-slate-900" style={{ fontFamily: "Cabinet Grotesk, sans-serif" }}>
                    Respaldo Automático al PC
                  </p>
                  <p className="text-[11px] text-slate-400">Guarda copias automáticas en tu computadora</p>
                </div>
              </div>
              {/* Status badge */}
              <div className="flex items-center gap-2">
                {autoBackup.config.enabled && (
                  <span className="flex items-center gap-1.5 text-[10px] font-black px-3 py-1 rounded-full bg-emerald-100 text-emerald-700">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                    ACTIVO
                  </span>
                )}
                {/* Toggle */}
                <button
                  data-testid="auto-backup-toggle"
                  onClick={() => {
                    const next = !autoBackup.config.enabled;
                    autoBackup.updateConfig({ enabled: next });
                    if (next) toast({ title: "Respaldo automático activado ✓" });
                    else toast({ title: "Respaldo automático desactivado" });
                  }}
                  className={`w-11 h-6 rounded-full transition-all duration-300 relative ${autoBackup.config.enabled ? "bg-emerald-500" : "bg-slate-200"}`}>
                  <span className={`absolute top-0.5 w-5 h-5 bg-white rounded-full shadow transition-all duration-300 ${autoBackup.config.enabled ? "left-[22px]" : "left-0.5"}`} />
                </button>
              </div>
            </div>

            <div className="p-5 space-y-4">

              {/* ── Status display when active ── */}
              <AnimatePresence>
                {autoBackup.config.enabled && (
                  <motion.div key="status" initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }}
                    className="grid grid-cols-3 gap-3">
                    <div className="bg-emerald-50 rounded-2xl p-3 text-center">
                      <div className="text-lg font-black text-emerald-700" style={{ fontFamily: "Cabinet Grotesk, sans-serif" }}>{autoBackup.backupCount}</div>
                      <div className="text-[10px] font-bold text-emerald-500 mt-0.5">Respaldos esta sesión</div>
                    </div>
                    <div className="bg-white/70 rounded-2xl p-3 text-center border border-emerald-100">
                      <div className="text-xs font-black text-slate-700 truncate">{lastAgoDisplay || "—"}</div>
                      <div className="text-[10px] font-bold text-slate-400 mt-0.5">Último respaldo</div>
                    </div>
                    <div className="bg-white/70 rounded-2xl p-3 text-center border border-emerald-100">
                      <div className="text-xs font-black text-slate-700">{countdown || "—"}</div>
                      <div className="text-[10px] font-bold text-slate-400 mt-0.5">Próximo en</div>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>

              {/* ── Interval selector ── */}
              <div>
                <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-2.5">Frecuencia de respaldo</p>
                <div className="flex flex-wrap gap-2">
                  {[
                    { label: "30 min", value: 30 },
                    { label: "1 hora", value: 60 },
                    { label: "2 horas", value: 120 },
                    { label: "6 horas", value: 360 },
                    { label: "12 horas", value: 720 },
                    { label: "24 horas", value: 1440 },
                  ].map(({ label, value }) => {
                    const active = autoBackup.config.intervalMinutes === value;
                    return (
                      <motion.button key={value} whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}
                        data-testid={`interval-${value}`}
                        onClick={() => autoBackup.updateConfig({ intervalMinutes: value })}
                        className={`px-3.5 py-1.5 rounded-full text-xs font-bold transition-all ${active ? "bg-emerald-500 text-white shadow-sm" : "bg-white/60 text-slate-600 border border-slate-200/80 hover:bg-white"}`}>
                        {label}
                      </motion.button>
                    );
                  })}
                </div>
              </div>

              {/* ── Mode selector ── */}
              <div>
                <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest mb-2.5">Destino del respaldo</p>
                <div className="grid grid-cols-2 gap-2.5">

                  {/* Downloads folder */}
                  <motion.button whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}
                    data-testid="mode-downloads"
                    onClick={() => autoBackup.updateConfig({ mode: "downloads" })}
                    className={`flex flex-col items-start gap-2 p-4 rounded-2xl border-2 transition-all text-left ${autoBackup.config.mode === "downloads" ? "border-emerald-400 bg-emerald-50/60" : "border-slate-200/70 bg-white/50 hover:border-slate-300"}`}>
                    <div className={`w-8 h-8 rounded-xl flex items-center justify-center ${autoBackup.config.mode === "downloads" ? "bg-emerald-200" : "bg-slate-100"}`}>
                      <Download size={14} className={autoBackup.config.mode === "downloads" ? "text-emerald-700" : "text-slate-400"} />
                    </div>
                    <div>
                      <p className={`text-xs font-black ${autoBackup.config.mode === "downloads" ? "text-emerald-800" : "text-slate-700"}`}>Carpeta Descargas</p>
                      <p className="text-[10px] text-slate-400 mt-0.5">Descarga automática a tu carpeta Descargas del sistema</p>
                    </div>
                    {autoBackup.config.mode === "downloads" && (
                      <span className="text-[10px] font-black text-emerald-600 flex items-center gap-1">
                        <CheckCircle size={10} /> Seleccionado
                      </span>
                    )}
                  </motion.button>

                  {/* Fixed custom folder */}
                  <motion.button whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}
                    data-testid="mode-folder"
                    onClick={async () => {
                      if (!autoBackup.fsSupportado) {
                        toast({ title: "Tu navegador no soporta carpeta fija (usa Chrome o Edge)", variant: "destructive" });
                        return;
                      }
                      if (autoBackup.config.folderName && autoBackup.config.mode === "folder") {
                        autoBackup.updateConfig({ mode: "folder" });
                        return;
                      }
                      const ok = await autoBackup.pickFolder();
                      if (ok) toast({ title: `Carpeta seleccionada: ${autoBackup.config.folderName} ✓` });
                    }}
                    className={`flex flex-col items-start gap-2 p-4 rounded-2xl border-2 transition-all text-left ${autoBackup.config.mode === "folder" ? "border-indigo-400 bg-indigo-50/60" : "border-slate-200/70 bg-white/50 hover:border-slate-300"}`}>
                    <div className={`w-8 h-8 rounded-xl flex items-center justify-center ${autoBackup.config.mode === "folder" ? "bg-indigo-200" : "bg-slate-100"}`}>
                      <FolderOpen size={14} className={autoBackup.config.mode === "folder" ? "text-indigo-700" : "text-slate-400"} />
                    </div>
                    <div>
                      <p className={`text-xs font-black ${autoBackup.config.mode === "folder" ? "text-indigo-800" : "text-slate-700"}`}>Carpeta fija</p>
                      <p className="text-[10px] text-slate-400 mt-0.5">
                        {autoBackup.config.folderName ? `📁 ${autoBackup.config.folderName}` : "Elige una carpeta y la app siempre guardará ahí"}
                      </p>
                    </div>
                    {autoBackup.config.mode === "folder" && autoBackup.config.folderName && (
                      <span className="text-[10px] font-black text-indigo-600 flex items-center gap-1">
                        <CheckCircle size={10} /> {autoBackup.folderPerm === "granted" ? "Acceso activo" : "Clic para reactivar"}
                      </span>
                    )}
                    {!autoBackup.fsSupportado && (
                      <span className="text-[10px] text-amber-500 font-bold">Solo Chrome/Edge</span>
                    )}
                  </motion.button>
                </div>

                {/* Folder details / change */}
                <AnimatePresence>
                  {autoBackup.config.mode === "folder" && autoBackup.config.folderName && (
                    <motion.div key="folder-info" initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }}
                      className="mt-2.5 flex items-center gap-3 bg-indigo-50/70 rounded-2xl px-4 py-3 border border-indigo-200/50">
                      <Folder size={14} className="text-indigo-500 shrink-0" />
                      <div className="flex-1 min-w-0">
                        <p className="text-xs font-bold text-indigo-800 truncate">📁 {autoBackup.config.folderName}</p>
                        <p className="text-[10px] text-indigo-400">
                          {autoBackup.folderPerm === "granted" ? "Acceso concedido — guardando automáticamente" : "Clic en 'Cambiar carpeta' para reactivar el acceso"}
                        </p>
                      </div>
                      <div className="flex gap-1.5">
                        <button onClick={autoBackup.pickFolder} data-testid="change-folder-btn"
                          className="px-3 py-1.5 rounded-xl text-[10px] font-bold bg-indigo-100 text-indigo-700 hover:bg-indigo-200 transition-colors">
                          Cambiar
                        </button>
                        <button onClick={() => { autoBackup.clearFolder(); toast({ title: "Carpeta eliminada" }); }}
                          data-testid="clear-folder-btn"
                          className="px-2 py-1.5 rounded-xl text-[10px] font-bold bg-red-50 text-red-500 hover:bg-red-100 transition-colors">
                          <Trash2 size={10} />
                        </button>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>

              {/* ── Error message ── */}
              {autoBackup.lastError && (
                <div className="flex items-center gap-2 bg-red-50 border border-red-200/60 rounded-xl px-4 py-2.5 text-xs text-red-600 font-semibold">
                  <AlertCircle size={13} />
                  {autoBackup.lastError}
                </div>
              )}

              {/* ── Manual trigger button ── */}
              <motion.button whileHover={{ scale: 1.01 }} whileTap={{ scale: 0.98 }}
                onClick={() => {
                  autoBackup.triggerBackup();
                  toast({ title: "Creando respaldo ahora..." });
                }}
                disabled={autoBackup.isBacking}
                data-testid="manual-auto-backup-btn"
                className="w-full flex items-center justify-center gap-2 py-3 rounded-2xl text-sm font-bold text-white transition-all disabled:opacity-60"
                style={{ background: "linear-gradient(135deg,#10b981,#059669)" }}>
                {autoBackup.isBacking
                  ? <><Loader2 size={14} className="animate-spin" /> Guardando respaldo...</>
                  : <><Download size={14} /> Guardar respaldo ahora</>}
              </motion.button>

              {/* ── Contenido del respaldo ── */}
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Incluye:</span>
                {["Reservas", "Socios", "Apariencia"].map((tag) => (
                  <span key={tag} className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700 flex items-center gap-1">
                    <CheckCircle size={8} /> {tag}
                  </span>
                ))}
              </div>

              {/* ── Restaurar desde archivo ── */}
              <div className="rounded-2xl border border-emerald-200/60 bg-emerald-50/30 overflow-hidden">
                <div className="flex items-center gap-2 px-4 py-3 border-b border-emerald-100/60">
                  <Upload size={13} className="text-emerald-600" />
                  <p className="text-xs font-black text-emerald-800">Restaurar respaldo</p>
                  <span className="text-[10px] text-emerald-500 ml-auto">Sube un archivo .json guardado</span>
                </div>
                <div className="p-3 space-y-2">
                  <input ref={restoreAutoInputRef} type="file" accept=".json"
                    onChange={handleRestoreFile} className="hidden" id="restore-file-auto-input" data-testid="restore-file-auto-input" />
                  <label htmlFor="restore-file-auto-input"
                    className={`flex items-center justify-center gap-2 w-full py-2.5 rounded-xl text-xs font-bold cursor-pointer transition-all border-2 border-dashed ${restoreLoading ? "border-emerald-200 bg-emerald-50 text-emerald-300" : "border-emerald-300 bg-white hover:bg-emerald-50 text-emerald-700"}`}>
                    {restoreLoading ? <Loader2 size={13} className="animate-spin" /> : <Upload size={13} />}
                    {restoreLoading ? "Restaurando datos..." : "Seleccionar archivo .json para restaurar"}
                  </label>
                  {restoreResult && (
                    <div className={`flex items-center gap-2 text-xs font-semibold px-3 py-2 rounded-xl ${restoreResult.ok ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-600"}`}>
                      {restoreResult.ok ? <CheckCircle size={12} /> : <XCircle size={12} />}
                      {restoreResult.msg}
                    </div>
                  )}
                </div>
              </div>

              {/* ── Guardar en servidor ── */}
              <div className="grid grid-cols-2 gap-3">
                <motion.button whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}
                  onClick={handleCreateServerBackup} disabled={backupCreating} data-testid="backup-server-btn"
                  className="flex flex-col items-center gap-1.5 py-3 rounded-2xl bg-white/70 border border-emerald-200/60 text-emerald-700 disabled:opacity-60 hover:bg-emerald-50 transition-all">
                  {backupCreating ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
                  <span className="text-xs font-bold">Guardar en servidor</span>
                  <span className="text-[9px] opacity-60">Historial 15 respaldos</span>
                </motion.button>
                <div className="flex flex-col items-center gap-1.5 py-3 rounded-2xl bg-white/50 border border-slate-100">
                  <HardDrive size={16} className="text-slate-400" />
                  <span className="text-xs font-bold text-slate-600">{backupHistory.length} respaldo(s)</span>
                  <button onClick={loadBackupHistory} className="text-[9px] text-indigo-500 font-bold hover:underline">Actualizar lista</button>
                </div>
              </div>

              {/* ── Backup history list ── */}
              {backupHistory.length > 0 && (
                <div className="space-y-1.5 max-h-44 overflow-y-auto pr-0.5">
                  {backupHistory.map((b, i) => {
                    const isAuto = b.label === "auto";
                    return (
                      <div key={b.filename} className="flex items-center gap-2.5 bg-white/60 border border-slate-100 rounded-xl px-3 py-2 hover:bg-white/80 transition-all">
                        <div className={`w-6 h-6 rounded-lg flex items-center justify-center shrink-0 ${isAuto ? "bg-slate-100" : "bg-indigo-100"}`}>
                          {isAuto ? <Clock size={10} className="text-slate-400" /> : <ShieldCheck size={10} className="text-indigo-500" />}
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-[10px] font-bold text-slate-700 truncate">{b.filename}</p>
                          <span className="text-[9px] text-slate-400">{b.size} · {fmtDate(b.created_at)}</span>
                        </div>
                        <a href={downloadBackupFileUrl(b.filename)} download data-testid={`backup-dl-${b.filename}`}
                          className="w-6 h-6 rounded-lg bg-indigo-50 hover:bg-indigo-100 flex items-center justify-center transition-colors">
                          <Download size={10} className="text-indigo-600" />
                        </a>
                        <button onClick={() => handleDeleteBackup(b.filename)} data-testid={`backup-del-${b.filename}`}
                          className="w-6 h-6 rounded-lg bg-red-50 hover:bg-red-100 flex items-center justify-center transition-colors">
                          <Trash2 size={10} className="text-red-400" />
                        </button>
                      </div>
                    );
                  })}
                </div>
              )}

              {/* ── Info note ── */}
              <div className="flex items-start gap-2.5 bg-amber-50/60 rounded-2xl px-4 py-3 border border-amber-200/50">
                <AlertCircle size={13} className="text-amber-500 shrink-0 mt-0.5" />
                <p className="text-[10px] text-amber-700 leading-relaxed">
                  El respaldo automático funciona mientras esta página esté abierta. Para respaldos en segundo plano usa "Guardar en servidor".
                </p>
              </div>

            </div>
          </div>
        </motion.div>

        {/* ── CONEXIÓN MONGODB (UNIFICADO) ── */}
        <motion.div variants={fadeUp}>
          <div className="glass rounded-3xl overflow-hidden">
            {/* Header */}
            <div className="flex items-center justify-between px-5 py-4 border-b border-white/40">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-xl bg-indigo-100 flex items-center justify-center">
                  <Database size={16} className="text-indigo-600" />
                </div>
                <div>
                  <p className="text-sm font-black text-slate-900" style={{ fontFamily: "Cabinet Grotesk, sans-serif" }}>Base de Datos MongoDB</p>
                  <p className="text-[11px] text-slate-400">Estado, conexión y bases guardadas</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                {dbStats && (
                  <span className={`flex items-center gap-1.5 text-[10px] font-black px-3 py-1 rounded-full ${dbStats.is_custom ? "bg-amber-100 text-amber-700" : "bg-emerald-100 text-emerald-700"}`}>
                    {dbStats.is_custom ? <WifiOff size={10} /> : <Wifi size={10} />}
                    {dbStats.is_custom ? "BD Personalizada" : "BD Local"}
                  </span>
                )}
                <button onClick={loadDbStats} className="w-8 h-8 rounded-xl hover:bg-white/60 flex items-center justify-center text-slate-400 hover:text-slate-700 transition-all">
                  <RefreshCw size={13} className={dbLoading ? "animate-spin" : ""} />
                </button>
              </div>
            </div>

            <div className="p-5 space-y-5">

              {/* ── Stats ── */}
              {dbLoading ? (
                <div className="flex items-center justify-center py-6 gap-3 text-slate-400">
                  <Loader2 size={18} className="animate-spin" />
                  <span className="text-sm">Cargando estadísticas...</span>
                </div>
              ) : dbStats ? (
                <div className="space-y-3">
                  {dbStats.connection_error && (
                    <div className="flex items-start gap-3 bg-red-50 border border-red-200 rounded-2xl px-4 py-3">
                      <WifiOff size={14} className="text-red-500 mt-0.5 shrink-0" />
                      <div>
                        <p className="text-xs font-bold text-red-700">Sin conexión a MongoDB Atlas</p>
                        <p className="text-[10px] text-red-500 mt-0.5">Verifica tu internet y que el URL sea correcto.</p>
                      </div>
                    </div>
                  )}
                  <div className="grid grid-cols-3 gap-3">
                    {[
                      { label: "Colecciones", value: dbStats.collections, color: "bg-indigo-50 text-indigo-700" },
                      { label: "Documentos",  value: dbStats.objects?.toLocaleString(), color: "bg-emerald-50 text-emerald-700" },
                      { label: "Tamaño",      value: dbStats.total_size, color: "bg-violet-50 text-violet-700" },
                    ].map((item) => (
                      <div key={item.label} className={`rounded-2xl p-4 ${item.color}`}>
                        <div className="text-xl font-black" style={{ fontFamily: "Cabinet Grotesk, sans-serif" }}>{item.value}</div>
                        <div className="text-[11px] font-semibold mt-1 opacity-70">{item.label}</div>
                      </div>
                    ))}
                  </div>
                  <div className="flex items-center gap-3 bg-slate-50/80 rounded-2xl px-4 py-3">
                    <Link2 size={13} className="text-slate-400 shrink-0" />
                    <div className="flex-1 min-w-0">
                      <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-0.5">Conexión activa</p>
                      <p className="text-xs font-mono text-slate-600 truncate">{dbStats.current_url}</p>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="flex items-center justify-between py-4">
                  <p className="text-sm text-slate-400">No se pudieron cargar las estadísticas</p>
                  <button onClick={loadDbStats} className="text-xs text-indigo-500 font-bold hover:underline">Reintentar</button>
                </div>
              )}

              {/* ── Cambiar conexión ── */}
              <div className="border-t border-white/30 pt-4 space-y-3">
                <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Cambiar conexión</p>

                {/* Mode tabs */}
                <div className="flex gap-1 p-1 rounded-2xl bg-slate-100/70">
                  {[
                    { key: "url",    icon: Globe,   label: "URL completa" },
                    { key: "fields", icon: Server,  label: "Por IP/campos" },
                    { key: "nas",    icon: Network,  label: "NAS / Red local" },
                  ].map(({ key, icon: Icon, label }) => (
                    <button key={key} onClick={() => { setConnMode(key); setDbTestResult(null); }}
                      data-testid={`conn-mode-${key}`}
                      className={`flex-1 flex items-center justify-center gap-1.5 px-2 py-2 rounded-xl text-[11px] font-bold transition-all ${connMode === key ? "bg-white shadow-sm text-indigo-700" : "text-slate-500 hover:text-slate-700"}`}>
                      <Icon size={12} /> {label}
                    </button>
                  ))}
                </div>

                {dbStats?.connection_error && (
                  <motion.button whileHover={{ scale: 1.01 }} whileTap={{ scale: 0.98 }}
                    onClick={() => { setConnMode("url"); setNewDbUrl(dbStats.current_url?.includes("***") ? "" : (dbStats.current_url || "")); }}
                    className="w-full flex items-center gap-2 px-4 py-2.5 rounded-xl bg-amber-50 border border-amber-200 text-amber-700 text-xs font-bold hover:bg-amber-100 transition-all">
                    <Wifi size={12} /> Reintentar con URL actual
                  </motion.button>
                )}

                {/* Mode: URL completa */}
                {connMode === "url" && (
                  <input type="text" value={newDbUrl}
                    onChange={e => { setNewDbUrl(e.target.value); setDbTestResult(null); }}
                    placeholder="mongodb+srv://usuario:contraseña@cluster.mongodb.net"
                    data-testid="db-url-input"
                    className="w-full bg-white/60 border border-slate-200/80 rounded-xl px-4 py-3 text-sm font-mono text-slate-800 placeholder-slate-300 focus:outline-none focus:ring-2 focus:ring-sky-300 focus:border-transparent" />
                )}

                {/* Mode: Por IP/campos */}
                {connMode === "fields" && (
                  <div className="space-y-2.5 p-4 rounded-2xl bg-slate-50/60 border border-slate-200/50">
                    <div className="grid grid-cols-3 gap-2">
                      <div className="col-span-2">
                        <label className="text-[9px] font-black text-slate-400 uppercase tracking-wider mb-1 block">Host / IP *</label>
                        <input value={connFields.host} onChange={e => setConnFields(p => ({ ...p, host: e.target.value }))}
                          placeholder="192.168.1.100 o cluster.mongodb.net" data-testid="field-host"
                          className="w-full bg-white border border-slate-200 rounded-xl px-3 py-2 text-xs font-mono text-slate-800 placeholder-slate-300 focus:outline-none focus:ring-2 focus:ring-sky-300" />
                      </div>
                      <div>
                        <label className="text-[9px] font-black text-slate-400 uppercase tracking-wider mb-1 block">Puerto</label>
                        <input value={connFields.port} onChange={e => setConnFields(p => ({ ...p, port: e.target.value }))}
                          placeholder="27017" data-testid="field-port"
                          className="w-full bg-white border border-slate-200 rounded-xl px-3 py-2 text-xs font-mono text-slate-800 placeholder-slate-300 focus:outline-none focus:ring-2 focus:ring-sky-300" />
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <label className="text-[9px] font-black text-slate-400 uppercase tracking-wider mb-1 block">Usuario</label>
                        <input value={connFields.user} onChange={e => setConnFields(p => ({ ...p, user: e.target.value }))}
                          placeholder="admin" data-testid="field-user"
                          className="w-full bg-white border border-slate-200 rounded-xl px-3 py-2 text-xs text-slate-800 placeholder-slate-300 focus:outline-none focus:ring-2 focus:ring-sky-300" />
                      </div>
                      <div>
                        <label className="text-[9px] font-black text-slate-400 uppercase tracking-wider mb-1 block">Contraseña</label>
                        <input type="password" value={connFields.pass} onChange={e => setConnFields(p => ({ ...p, pass: e.target.value }))}
                          placeholder="••••••••" data-testid="field-pass"
                          className="w-full bg-white border border-slate-200 rounded-xl px-3 py-2 text-xs text-slate-800 placeholder-slate-300 focus:outline-none focus:ring-2 focus:ring-sky-300" />
                      </div>
                    </div>
                    <div>
                      <label className="text-[9px] font-black text-slate-400 uppercase tracking-wider mb-1 block">Base de datos</label>
                      <input value={connFields.db} onChange={e => setConnFields(p => ({ ...p, db: e.target.value }))}
                        placeholder="cinema_events" data-testid="field-db"
                        className="w-full bg-white border border-slate-200 rounded-xl px-3 py-2 text-xs font-mono text-slate-800 placeholder-slate-300 focus:outline-none focus:ring-2 focus:ring-sky-300" />
                    </div>
                    {buildUrlFromFields() && (
                      <div className="flex items-center gap-2 bg-indigo-50/50 rounded-xl px-3 py-2">
                        <Link2 size={10} className="text-indigo-400 shrink-0" />
                        <p className="text-[10px] font-mono text-indigo-700 truncate">{buildUrlFromFields().replace(/:([^@]+)@/, ":***@")}</p>
                      </div>
                    )}
                  </div>
                )}

                {/* Mode: NAS / Red local */}
                {connMode === "nas" && (
                  <div className="space-y-2.5">
                    <div className="flex items-start gap-2.5 bg-blue-50/60 rounded-2xl px-4 py-3 border border-blue-200/50">
                      <Network size={13} className="text-blue-500 shrink-0 mt-0.5" />
                      <div>
                        <p className="text-[10px] font-bold text-blue-700 mb-0.5">Conexión a NAS o servidor en red</p>
                        <p className="text-[9px] text-blue-600 leading-relaxed">
                          Ingresa la IP de tu NAS (Synology, QNAP, etc.) o servidor local con MongoDB. El puerto estándar de MongoDB es <strong>27017</strong>.
                        </p>
                      </div>
                    </div>
                    <div className="grid grid-cols-3 gap-2 p-4 rounded-2xl bg-slate-50/60 border border-slate-200/50">
                      <div className="col-span-2">
                        <label className="text-[9px] font-black text-slate-400 uppercase tracking-wider mb-1 block">IP del NAS / Servidor *</label>
                        <input value={connFields.host} onChange={e => setConnFields(p => ({ ...p, host: e.target.value }))}
                          placeholder="192.168.1.50" data-testid="nas-field-host"
                          className="w-full bg-white border border-slate-200 rounded-xl px-3 py-2 text-xs font-mono text-slate-800 placeholder-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-300" />
                      </div>
                      <div>
                        <label className="text-[9px] font-black text-slate-400 uppercase tracking-wider mb-1 block">Puerto MongoDB</label>
                        <input value={connFields.port} onChange={e => setConnFields(p => ({ ...p, port: e.target.value }))}
                          placeholder="27017" data-testid="nas-field-port"
                          className="w-full bg-white border border-slate-200 rounded-xl px-3 py-2 text-xs font-mono text-slate-800 placeholder-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-300" />
                      </div>
                      <div className="col-span-3 grid grid-cols-2 gap-2">
                        <div>
                          <label className="text-[9px] font-black text-slate-400 uppercase tracking-wider mb-1 block">Usuario MongoDB</label>
                          <input value={connFields.user} onChange={e => setConnFields(p => ({ ...p, user: e.target.value }))}
                            placeholder="admin" data-testid="nas-field-user"
                            className="w-full bg-white border border-slate-200 rounded-xl px-3 py-2 text-xs text-slate-800 placeholder-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-300" />
                        </div>
                        <div>
                          <label className="text-[9px] font-black text-slate-400 uppercase tracking-wider mb-1 block">Contraseña</label>
                          <input type="password" value={connFields.pass} onChange={e => setConnFields(p => ({ ...p, pass: e.target.value }))}
                            placeholder="••••••••" data-testid="nas-field-pass"
                            className="w-full bg-white border border-slate-200 rounded-xl px-3 py-2 text-xs text-slate-800 placeholder-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-300" />
                        </div>
                      </div>
                      <div className="col-span-3">
                        <label className="text-[9px] font-black text-slate-400 uppercase tracking-wider mb-1 block">Base de datos</label>
                        <input value={connFields.db} onChange={e => setConnFields(p => ({ ...p, db: e.target.value }))}
                          placeholder="cinema_events" data-testid="nas-field-db"
                          className="w-full bg-white border border-slate-200 rounded-xl px-3 py-2 text-xs font-mono text-slate-800 placeholder-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-300" />
                      </div>
                      {buildUrlFromFields() && (
                        <div className="col-span-3 flex items-center gap-2 bg-blue-50/50 rounded-xl px-3 py-2">
                          <Link2 size={10} className="text-blue-400 shrink-0" />
                          <p className="text-[10px] font-mono text-blue-700 truncate">{buildUrlFromFields().replace(/:([^@]+)@/, ":***@")}</p>
                        </div>
                      )}
                    </div>
                    <div className="flex items-start gap-2 bg-amber-50/60 rounded-2xl px-4 py-3 border border-amber-200/50 text-[9px] text-amber-700">
                      <AlertCircle size={11} className="shrink-0 mt-0.5" />
                      <span>Asegúrate que MongoDB esté instalado en el NAS y que el puerto 27017 esté abierto en el firewall de tu red local.</span>
                    </div>
                  </div>
                )}

                {dbTestResult && (
                  <div className={`flex items-center gap-2 text-xs font-semibold px-3 py-2.5 rounded-xl ${dbTestResult.ok ? "bg-emerald-50 text-emerald-700 border border-emerald-200/60" : "bg-red-50 text-red-600 border border-red-200/60"}`}>
                    {dbTestResult.ok ? <CheckCircle size={13} /> : <XCircle size={13} />}
                    {dbTestResult.msg}
                  </div>
                )}
                <div className="flex gap-2">
                  <motion.button whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.97 }}
                    onClick={handleDbTest} disabled={!activeConnUrl.trim() || dbTesting} data-testid="db-test-btn"
                    className="flex items-center gap-2 px-4 py-2.5 rounded-xl border border-slate-200 bg-white text-slate-700 text-xs font-bold hover:bg-slate-50 transition-all disabled:opacity-40">
                    {dbTesting ? <Loader2 size={12} className="animate-spin" /> : <Wifi size={12} />}
                    Probar
                  </motion.button>
                  <motion.button whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.97 }}
                    onClick={handleDbConnect} disabled={!activeConnUrl.trim() || dbConnecting} data-testid="db-connect-btn"
                    className="flex items-center gap-2 px-4 py-2.5 rounded-xl btn-primary text-white text-xs font-bold disabled:opacity-40">
                    {dbConnecting ? <Loader2 size={12} className="animate-spin" /> : <ArrowRight size={12} />}
                    Conectar
                  </motion.button>
                  {dbStats?.is_custom && (
                    <motion.button whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.97 }}
                      onClick={handleDbReset} disabled={dbResetting} data-testid="db-reset-btn"
                      className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-red-50 text-red-600 text-xs font-bold hover:bg-red-100 transition-all border border-red-200/60 disabled:opacity-40">
                      {dbResetting ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />}
                      Restaurar local
                    </motion.button>
                  )}
                </div>
              </div>

              {/* ── Conexiones guardadas ── */}
              <div className="border-t border-white/30 pt-4 space-y-3">
                <div className="flex items-center justify-between">
                  <p className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Conexiones guardadas</p>
                  <motion.button whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}
                    onClick={() => setShowAddPreset(p => !p)} data-testid="add-preset-btn"
                    className="flex items-center gap-1.5 px-3 py-1 rounded-xl text-xs font-bold bg-amber-100 text-amber-700 hover:bg-amber-200 transition-colors">
                    <Plus size={11} /> Agregar
                  </motion.button>
                </div>

                <AnimatePresence>
                  {showAddPreset && (
                    <motion.div key="add-form" initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }}
                      className="space-y-2 pb-3 border-b border-white/40">
                      <input type="text" value={presetName}
                        onChange={e => setPresetName(e.target.value)}
                        placeholder="Nombre (ej: Atlas Producción)"
                        data-testid="preset-name-input"
                        className="w-full bg-white/60 border border-slate-200/80 rounded-xl px-4 py-2.5 text-sm text-slate-800 placeholder-slate-300 focus:outline-none focus:ring-2 focus:ring-amber-300" />
                      <div className="flex gap-2">
                        <input type="text" value={newDbUrl}
                          onChange={e => { setNewDbUrl(e.target.value); setDbTestResult(null); }}
                          placeholder="mongodb://... o mongodb+srv://..."
                          className="flex-1 bg-white/60 border border-slate-200/80 rounded-xl px-3 py-2.5 text-xs font-mono text-slate-800 placeholder-slate-300 focus:outline-none focus:ring-2 focus:ring-amber-300" />
                        <motion.button whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.97 }}
                          data-testid="save-preset-btn"
                          disabled={!presetName.trim() || !newDbUrl.trim()}
                          onClick={() => {
                            const newPreset = { name: presetName.trim(), url: newDbUrl.trim(), color: ["indigo","emerald","sky","amber","rose","violet"][presets.length % 6] };
                            savePresets([...presets, newPreset]);
                            setPresetName(""); setNewDbUrl(""); setShowAddPreset(false);
                            toast({ title: `Preset "${newPreset.name}" guardado ✓` });
                          }}
                          className="px-4 py-2.5 rounded-xl bg-amber-500 text-white text-xs font-bold disabled:opacity-40 hover:bg-amber-600 transition-colors">
                          <Save size={12} />
                        </motion.button>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>

                {presets.length === 0 ? (
                  <div className="flex items-center justify-center py-4 text-slate-300 gap-2">
                    <Bookmark size={14} />
                    <span className="text-xs">No hay conexiones guardadas</span>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {presets.map((p, i) => {
                      const colors = {
                        indigo: "bg-indigo-50 border-indigo-200/60 text-indigo-700",
                        emerald: "bg-emerald-50 border-emerald-200/60 text-emerald-700",
                        sky: "bg-sky-50 border-sky-200/60 text-sky-700",
                        amber: "bg-amber-50 border-amber-200/60 text-amber-700",
                        rose: "bg-rose-50 border-rose-200/60 text-rose-700",
                        violet: "bg-violet-50 border-violet-200/60 text-violet-700",
                      };
                      return (
                        <div key={p.url || p.name || i} className={`flex items-center gap-3 rounded-2xl px-4 py-3 border ${colors[p.color] || colors.indigo}`}>
                          <Database size={13} className="shrink-0" />
                          <div className="flex-1 min-w-0">
                            <p className="text-xs font-black truncate">{p.name}</p>
                            <p className="text-[10px] font-mono opacity-60 truncate">{p.url.replace(/:([^@]+)@/, ":***@")}</p>
                          </div>
                          <div className="flex gap-1.5">
                            <motion.button whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}
                              data-testid={`preset-connect-${i}`}
                              onClick={async () => {
                                setNewDbUrl(p.url);
                                try {
                                  await switchDatabase(p.url);
                                  toast({ title: `Conectado a "${p.name}" ✓ — Actualizando...` });
                                  setTimeout(() => window.location.reload(), 1200);
                                } catch (e) { toast({ title: e.response?.data?.detail || "Error al conectar", variant: "destructive" }); }
                              }}
                              className="px-3 py-1.5 rounded-xl text-[10px] font-bold bg-white/80 hover:bg-white transition-colors border border-white/60">
                              Conectar
                            </motion.button>
                            <button onClick={() => savePresets(presets.filter((_, j) => j !== i))}
                              data-testid={`preset-delete-${i}`}
                              className="w-7 h-7 rounded-lg bg-white/60 hover:bg-red-50 flex items-center justify-center transition-colors">
                              <Trash2 size={10} className="text-red-400" />
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}

                {/* MongoDB Atlas guide */}
                <details className="rounded-2xl overflow-hidden border border-blue-200/60 bg-blue-50/30 group">
                  <summary className="flex items-center gap-2 px-4 py-3 cursor-pointer list-none select-none">
                    <Database size={13} className="text-blue-500 shrink-0" />
                    <span className="text-xs font-black text-blue-800 flex-1">MongoDB Atlas en la nube (gratis)</span>
                    <ChevronRight size={12} className="text-blue-400 group-open:rotate-90 transition-transform" />
                  </summary>
                  <div className="px-4 pb-4 text-[10px] text-blue-700 space-y-2 border-t border-blue-100/60">
                    <p className="font-black text-xs mt-3">4 pasos — 512 MB gratuitos:</p>
                    {[
                      <>Ve a <a href="https://www.mongodb.com/cloud/atlas/register" target="_blank" rel="noreferrer" className="underline font-bold">mongodb.com/cloud/atlas</a> → crea cuenta gratis</>,
                      <>Crea un cluster → <b>Free Tier (M0 Sandbox)</b> → región más cercana</>,
                      <>Database Access → crea usuario/contraseña → Network Access → agrega <b>0.0.0.0/0</b></>,
                      <>Connect → "Connect your application" → copia la URI → pégala arriba en "Cambiar conexión"</>,
                    ].map((step, idx) => (
                      <div key={idx} className="flex items-start gap-2">
                        <span className="w-4 h-4 rounded-full bg-blue-200 text-blue-700 font-black text-[9px] flex items-center justify-center shrink-0 mt-0.5">{idx + 1}</span>
                        <p>{step}</p>
                      </div>
                    ))}
                    <code className="block bg-white/70 px-3 py-2 rounded-xl text-[9px] font-mono break-all border border-blue-100">
                      mongodb+srv://usuario:contraseña@cluster.mongodb.net/cinema
                    </code>
                  </div>
                </details>
              </div>

            </div>
          </div>
        </motion.div>

        {/* ── LIMPIEZA DE BASE DE DATOS ── */}
        <motion.div variants={fadeUp}>
          <div className="glass rounded-3xl overflow-hidden">
            <div className="flex items-center gap-3 px-5 py-4 border-b border-white/40">
              <div className="w-9 h-9 rounded-xl bg-orange-100 flex items-center justify-center">
                <Scissors size={16} className="text-orange-600" />
              </div>
              <div>
                <p className="text-sm font-black text-slate-900" style={{ fontFamily: "Cabinet Grotesk, sans-serif" }}>Limpieza de base de datos</p>
                <p className="text-[11px] text-slate-400">Elimina registros innecesarios y libera espacio</p>
              </div>
            </div>
            <div className="p-5 space-y-3">

              {/* Preview counts */}
              {cleanupPreview && (
                <div className="grid grid-cols-2 gap-3">
                  <div className="bg-red-50/60 rounded-2xl p-3 text-center border border-red-200/40">
                    <div className="text-2xl font-black text-red-600" style={{ fontFamily: "Cabinet Grotesk, sans-serif" }}>{cleanupPreview.cancelled_count}</div>
                    <div className="text-[10px] font-bold text-red-400 mt-1">Reservas canceladas</div>
                  </div>
                  <div className="bg-slate-50/60 rounded-2xl p-3 text-center border border-slate-200/40">
                    <div className="text-2xl font-black text-slate-600" style={{ fontFamily: "Cabinet Grotesk, sans-serif" }}>{cleanupPreview.old_completed_count}</div>
                    <div className="text-[10px] font-bold text-slate-400 mt-1">Completadas {">"} 6 meses</div>
                  </div>
                </div>
              )}

              <div className="space-y-2">
                <motion.button whileHover={{ scale: 1.01 }} whileTap={{ scale: 0.98 }}
                  onClick={() => handleCleanup("cancelled")}
                  disabled={cleanupLoading || (cleanupPreview?.cancelled_count === 0)}
                  data-testid="cleanup-cancelled-btn"
                  className="w-full flex items-center justify-between py-3 px-4 rounded-2xl text-xs font-bold transition-all border bg-red-50/40 border-red-200/50 text-red-700 hover:bg-red-50 disabled:opacity-40">
                  <div className="flex items-center gap-2">
                    {cleanupLoading && cleanupAction === "cancelled" ? <Loader2 size={12} className="animate-spin" /> : <Trash2 size={12} />}
                    Eliminar reservas canceladas
                  </div>
                  <span className="text-[10px] font-black bg-red-100 px-2 py-0.5 rounded-full">
                    {cleanupPreview?.cancelled_count ?? "—"} registros
                  </span>
                </motion.button>

                <motion.button whileHover={{ scale: 1.01 }} whileTap={{ scale: 0.98 }}
                  onClick={() => handleCleanup("old_completed")}
                  disabled={cleanupLoading || (cleanupPreview?.old_completed_count === 0)}
                  data-testid="cleanup-old-btn"
                  className="w-full flex items-center justify-between py-3 px-4 rounded-2xl text-xs font-bold transition-all border bg-slate-50/40 border-slate-200/50 text-slate-700 hover:bg-slate-50 disabled:opacity-40">
                  <div className="flex items-center gap-2">
                    {cleanupLoading && cleanupAction === "old_completed" ? <Loader2 size={12} className="animate-spin" /> : <Clock size={12} />}
                    Eliminar reservas completadas {">"} 6 meses
                  </div>
                  <span className="text-[10px] font-black bg-slate-100 px-2 py-0.5 rounded-full">
                    {cleanupPreview?.old_completed_count ?? "—"} registros
                  </span>
                </motion.button>
              </div>
              <p className="text-[10px] text-slate-400 text-center">Se crea un respaldo automático antes de cada limpieza</p>
            </div>
          </div>
        </motion.div>

        {/* ── ACTUALIZACIONES EN LA BASE DE DATOS ── */}
        <motion.div variants={fadeUp}>
          <div className="glass rounded-3xl overflow-hidden">
            <div className="flex items-center justify-between px-5 py-4 border-b border-white/40">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-xl bg-violet-100 flex items-center justify-center">
                  <Package size={16} className="text-violet-600" />
                </div>
                <div>
                  <p className="text-sm font-black text-slate-900" style={{ fontFamily: "Cabinet Grotesk, sans-serif" }}>Actualizaciones guardadas</p>
                  <p className="text-[11px] text-slate-400">Versiones de la app almacenadas en esta base de datos</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-black px-2.5 py-1 rounded-full bg-violet-100 text-violet-700">{dbUpdates.length} versiones</span>
                <button onClick={loadDbUpdates} className="w-8 h-8 rounded-xl hover:bg-white/60 flex items-center justify-center text-slate-400 hover:text-slate-700 transition-all">
                  <RefreshCw size={13} className={updatesLoading ? "animate-spin" : ""} />
                </button>
              </div>
            </div>
            <div className="p-5">
              {updatesLoading ? (
                <div className="space-y-2">{[...Array(2)].map((_,i) => <div key={i} className="h-12 glass rounded-2xl animate-pulse"/>)}</div>
              ) : dbUpdates.length === 0 ? (
                <div className="py-8 text-center">
                  <Package size={28} className="mx-auto text-slate-200 mb-2"/>
                  <p className="text-xs text-slate-400 font-medium">No hay versiones en esta base de datos</p>
                  <p className="text-[10px] text-slate-300 mt-1">Descarga la App desde Ajustes para registrar la primera versión</p>
                  <a href="/actualizaciones" className="inline-flex items-center gap-1 mt-3 text-xs text-indigo-500 font-bold hover:underline">
                    Ir a Actualizaciones <ChevronRight size={12}/>
                  </a>
                </div>
              ) : (
                <div className="space-y-2">
                  {dbUpdates.map((u) => (
                    <div key={u.id} data-testid={`db-update-row-${u.id}`}
                      className="flex items-center gap-3 px-4 py-3 rounded-2xl bg-slate-50/60 border border-slate-200/40 hover:bg-white/60 transition-colors">
                      <div className="w-8 h-8 rounded-xl bg-violet-50 flex items-center justify-center flex-shrink-0">
                        <Package size={13} className="text-violet-500"/>
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <p className="text-xs font-black text-slate-800">v{u.version}</p>
                          {u.is_latest && <span className="text-[9px] font-black px-1.5 py-0.5 rounded-full bg-emerald-100 text-emerald-700">ACTIVA</span>}
                          <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded-full ${u.channel === "stable" ? "bg-slate-100 text-slate-500" : u.channel === "beta" ? "bg-amber-100 text-amber-600" : "bg-red-100 text-red-500"}`}>
                            {u.channel === "stable" ? "Estable" : u.channel === "beta" ? "Beta" : "Alpha"}
                          </span>
                        </div>
                        <p className="text-[10px] text-slate-400 truncate">{u.filename} · {u.file_size ? (u.file_size > 1048576 ? `${(u.file_size/1048576).toFixed(1)} MB` : `${(u.file_size/1024).toFixed(0)} KB`) : "—"} · {new Date(u.created_at).toLocaleDateString("es-GT")}</p>
                      </div>
                      {u.notes && <p className="text-[10px] text-slate-400 italic truncate max-w-[120px] hidden md:block">{u.notes}</p>}
                      <button onClick={() => handleDeleteUpdate(u.id)} data-testid={`db-update-del-${u.id}`}
                        className="w-7 h-7 rounded-lg bg-red-50 hover:bg-red-100 flex items-center justify-center transition-colors flex-shrink-0">
                        <Trash2 size={11} className="text-red-400"/>
                      </button>
                    </div>
                  ))}
                  <div className="flex items-center justify-center pt-2">
                    <a href="/actualizaciones" className="flex items-center gap-1.5 text-xs text-indigo-500 font-bold hover:underline">
                      Administrar versiones <ChevronRight size={12}/>
                    </a>
                  </div>
                </div>
              )}
            </div>
          </div>
        </motion.div>

        {/* ── OPCIONES DE BASE DE DATOS ── */}
        <motion.div variants={fadeUp}>
          <div className="glass rounded-3xl overflow-hidden">
            <div className="flex items-center gap-3 px-5 py-4 border-b border-white/40">
              <div className="w-9 h-9 rounded-xl bg-slate-100 flex items-center justify-center">
                <ToggleRight size={16} className="text-slate-600" />
              </div>
              <div>
                <p className="text-sm font-black text-slate-900" style={{ fontFamily: "Cabinet Grotesk, sans-serif" }}>Opciones de base de datos</p>
                <p className="text-[11px] text-slate-400">Activa o desactiva funciones de la base de datos</p>
              </div>
            </div>
            <div className="p-5 space-y-1">
              {[
                { key: "autoTest",     icon: Wifi,          label: "Probar conexión antes de conectar",      sub: "Verifica que el servidor esté disponible antes de cambiar" },
                { key: "notifySwitch", icon: MonitorSpeaker, label: "Notificar al cambiar de base de datos",  sub: "Muestra una alerta de confirmación al conectar" },
                { key: "showFullUrl",  icon: Link2,          label: "Mostrar URL completa en el estado",      sub: "Muestra la URL sin ocultar contraseñas (solo local)" },
                { key: "compressBackup", icon: HardDrive,    label: "Comprimir respaldos automáticos",        sub: "Reduce el tamaño de los archivos de backup" },
              ].map(({ key, icon: Icon, label, sub }) => (
                <div key={key} data-testid={`db-option-${key}`}
                  className="flex items-center justify-between py-3 px-3 rounded-2xl hover:bg-white/40 transition-colors cursor-pointer"
                  onClick={() => saveDbOption(key, !dbOptions[key])}>
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-xl bg-slate-100 flex items-center justify-center flex-shrink-0">
                      <Icon size={14} className="text-slate-500"/>
                    </div>
                    <div>
                      <p className="text-xs font-bold text-slate-800">{label}</p>
                      <p className="text-[10px] text-slate-400">{sub}</p>
                    </div>
                  </div>
                  <div className={`w-10 h-5 rounded-full transition-colors relative flex-shrink-0 ${dbOptions[key] ? "bg-indigo-500" : "bg-slate-200"}`}>
                    <div className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-all ${dbOptions[key] ? "right-0.5" : "left-0.5"}`}/>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </motion.div>

        {/* ── ZONA DE PELIGRO ── */}
        <motion.div variants={fadeUp}>
          <div className="rounded-3xl border-2 border-dashed border-red-200/80 bg-red-50/20 overflow-hidden">
            <div className="flex items-center gap-3 px-5 py-4 border-b border-red-100/60">
              <div className="w-9 h-9 rounded-xl bg-red-100 flex items-center justify-center">
                <AlertCircle size={16} className="text-red-500" />
              </div>
              <div>
                <p className="text-sm font-black text-red-700" style={{ fontFamily: "Cabinet Grotesk, sans-serif" }}>Zona de peligro</p>
                <p className="text-[11px] text-red-400">Acciones irreversibles — se crea respaldo automático primero</p>
              </div>
            </div>
            <div className="p-5">
              {!showClear ? (
                <motion.button whileHover={{ scale: 1.01 }} whileTap={{ scale: 0.98 }}
                  onClick={() => setShowClear(true)} data-testid="clear-all-data-btn"
                  className="w-full flex items-center justify-center gap-2 py-3 rounded-2xl text-sm font-bold text-red-600 bg-white border border-red-200 hover:bg-red-50 transition-all">
                  <Trash2 size={14} /> Borrar todos los datos
                </motion.button>
              ) : (
                <motion.div initial={{ opacity: 0, scale: 0.97 }} animate={{ opacity: 1, scale: 1 }} className="space-y-3">
                  <div className="flex items-start gap-3 bg-red-50 border border-red-200/60 rounded-2xl p-4">
                    <AlertCircle size={16} className="text-red-500 shrink-0 mt-0.5" />
                    <div>
                      <p className="text-sm font-black text-red-700">¿Confirmar borrado total?</p>
                      <p className="text-xs text-red-500 mt-1">Se eliminarán TODAS las reservas y socios. Un respaldo automático se creará antes de borrar.</p>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <motion.button whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.97 }}
                      onClick={handleClearAll} disabled={clearLoading} data-testid="clear-all-confirm-btn"
                      className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-xl text-xs font-bold text-white bg-red-500 hover:bg-red-600 transition-all disabled:opacity-60">
                      {clearLoading ? <Loader2 size={12} className="animate-spin" /> : <Trash2 size={12} />}
                      Sí, borrar todo
                    </motion.button>
                    <motion.button whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.97 }}
                      onClick={() => setShowClear(false)} data-testid="clear-all-cancel-btn"
                      className="flex-1 py-2.5 rounded-xl text-xs font-bold text-slate-600 bg-white hover:bg-slate-50 border border-slate-200 transition-all">
                      Cancelar
                    </motion.button>
                  </div>
                </motion.div>
              )}
            </div>
          </div>
        </motion.div>

      </motion.div>
    </div>
  );
}
