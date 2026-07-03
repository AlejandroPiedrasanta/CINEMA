import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Shield, KeyRound, Trash2, Loader2, Eye, EyeOff, MousePointer2, Copy, TextCursor, Lock, Clock, AlertTriangle, LockKeyhole } from "lucide-react";
import { useSettings } from "@/context/SettingsContext";
import { useToast } from "@/hooks/use-toast";
import { Section } from "@/components/appearance/SectionShell";
import { setAppPassword, removeAppPassword, setPageProtection, setAdvancedSecurity, getSecurityStatus } from "@/lib/api";

const PROTECTABLE_SECTIONS = [
  { key: "/base-de-datos", label: "Base de Datos" },
  { key: "/ajustes",       label: "Ajustes" },
  { key: "/socios",        label: "Socios" },
  { key: "/reservaciones", label: "Reservaciones" },
  { key: "/apariencia",    label: "Apariencia" },
  { key: "/actualizaciones", label: "Actualizaciones" },
  { key: "/calendario",    label: "Calendario" },
];

export function SecuritySection() {
  const { language, security, refreshSecurity } = useSettings();
  const { toast } = useToast();
  const es = language === "es";

  const [newPass, setNewPass] = useState("");
  const [confirmPass, setConfirmPass] = useState("");
  const [hint, setHint] = useState("");
  const [currentPass, setCurrentPass] = useState("");
  const [showPass, setShowPass] = useState(false);
  const [saving, setSaving] = useState(false);
  const [removing, setRemoving] = useState(false);
  const [showRemove, setShowRemove] = useState(false);

  // ── Configuración avanzada ──
  const [advCfg, setAdvCfg] = useState({
    auto_lock_enabled: false,
    auto_lock_minutes: 5,
    max_attempts: 5,
    lockout_seconds: 60,
    protected_sections: [],
  });
  const [advSaving, setAdvSaving] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const s = await getSecurityStatus();
        setAdvCfg({
          auto_lock_enabled: s.auto_lock_enabled || false,
          auto_lock_minutes: s.auto_lock_minutes || 5,
          max_attempts: s.max_attempts || 5,
          lockout_seconds: s.lockout_seconds || 60,
          protected_sections: s.protected_sections || [],
        });
      } catch {}
    })();
  }, []);

  const saveAdvCfg = async (patch = {}) => {
    const merged = { ...advCfg, ...patch };
    setAdvCfg(merged);
    setAdvSaving(true);
    try {
      await setAdvancedSecurity(patch);
      toast({ title: es ? "Configuración guardada ✓" : "Config saved ✓" });
      window.dispatchEvent(new CustomEvent("cp:security-updated"));
    } catch {
      toast({ title: "Error", variant: "destructive" });
    } finally {
      setAdvSaving(false);
    }
  };

  const toggleSection = (key) => {
    const has = advCfg.protected_sections.includes(key);
    const next = has ? advCfg.protected_sections.filter(k => k !== key) : [...advCfg.protected_sections, key];
    saveAdvCfg({ protected_sections: next });
  };

  const handleProtectionToggle = async () => {
    try {
      await setPageProtection(!security.protectionEnabled);
      await refreshSecurity();
      toast({ title: !security.protectionEnabled ? (es ? "Protección de página activada ✓" : "Page protection enabled ✓") : (es ? "Protección de página desactivada" : "Page protection disabled") });
    } catch { toast({ title: "Error", variant: "destructive" }); }
  };

  const handleSavePassword = async () => {
    if (newPass.length < 4) { toast({ title: es ? "Mínimo 4 caracteres" : "Minimum 4 characters", variant: "destructive" }); return; }
    if (newPass !== confirmPass) { toast({ title: es ? "Las contraseñas no coinciden" : "Passwords don't match", variant: "destructive" }); return; }
    if (security.passwordEnabled && !currentPass) { toast({ title: es ? "Escribe tu contraseña actual" : "Enter your current password", variant: "destructive" }); return; }
    setSaving(true);
    try {
      await setAppPassword(newPass, hint, currentPass);
      sessionStorage.setItem("cp_app_unlocked", "true");
      await refreshSecurity();
      setNewPass(""); setConfirmPass(""); setCurrentPass(""); setHint("");
      toast({ title: security.passwordEnabled ? (es ? "Contraseña actualizada ✓" : "Password updated ✓") : (es ? "Contraseña activada ✓ — se pedirá al abrir la app" : "Password enabled ✓") });
    } catch (e) {
      toast({ title: e.response?.data?.detail || "Error", variant: "destructive" });
    } finally { setSaving(false); }
  };

  const handleRemove = async () => {
    if (!currentPass) { toast({ title: es ? "Escribe tu contraseña actual para quitarla" : "Enter current password to remove it", variant: "destructive" }); return; }
    setRemoving(true);
    try {
      await removeAppPassword(currentPass);
      await refreshSecurity();
      setCurrentPass(""); setShowRemove(false);
      toast({ title: es ? "Contraseña eliminada — la app ya no está bloqueada" : "Password removed" });
    } catch (e) {
      toast({ title: e.response?.data?.detail || "Error", variant: "destructive" });
    } finally { setRemoving(false); }
  };

  const inputCls = "w-full bg-white/70 border border-white/80 rounded-xl px-3 py-2.5 text-sm text-slate-800 placeholder-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-300 transition-all";

  return (
    <Section
      icon={Shield}
      isNew
      id="seguridad"
      title={es ? "Seguridad" : "Security"}
      desc={es ? "Contraseña de la app y protección de la página" : "App password and page protection"}
      keywords="seguridad contraseña password bloquear proteccion clic derecho copiar pegar seleccionar texto pista candado lock"
      badge={security.passwordEnabled && (
        <span className="flex items-center gap-1.5 text-[10px] font-black px-2.5 py-1 rounded-full bg-emerald-100 text-emerald-700">
          <Lock size={10} /> {es ? "PROTEGIDA" : "PROTECTED"}
        </span>
      )}
    >
      <div className="space-y-5">

        {/* ── Page protection toggle ── */}
        <div className="flex items-center justify-between p-3.5 rounded-2xl glass border border-white/50">
          <div className="flex-1 pr-3">
            <p className="text-sm font-bold text-slate-700">{es ? "Protección de página" : "Page protection"}</p>
            <p className="text-[11px] text-slate-400 mt-0.5">
              {es ? "Bloquea clic derecho, copiar/pegar y selección de texto (los campos de escritura siguen funcionando)" : "Blocks right-click, copy/paste and text selection (input fields keep working)"}
            </p>
            <div className="flex flex-wrap gap-1.5 mt-2">
              {[
                { icon: MousePointer2, label: es ? "Clic derecho" : "Right-click" },
                { icon: Copy, label: es ? "Copiar / Pegar" : "Copy / Paste" },
                { icon: TextCursor, label: es ? "Seleccionar texto" : "Text selection" },
              ].map(({ icon: Icon, label }) => (
                <span key={label} className="flex items-center gap-1 text-[9px] font-bold px-2 py-0.5 rounded-full bg-slate-100 text-slate-500">
                  <Icon size={9} /> {label}
                </span>
              ))}
            </div>
          </div>
          <button
            type="button"
            onClick={handleProtectionToggle}
            data-testid="page-protection-toggle"
            role="switch"
            aria-checked={security.protectionEnabled}
            className={`relative w-12 h-6 rounded-full transition-all flex-shrink-0 ${security.protectionEnabled ? "btn-primary" : "bg-slate-200"}`}>
            <span className={`absolute top-0.5 w-5 h-5 rounded-full bg-white shadow transition-all ${security.protectionEnabled ? "left-[26px]" : "left-0.5"}`} />
          </button>
        </div>

        <div className="border-t border-white/40" />

        {/* ── App password ── */}
        <div>
          <div className="flex items-center gap-2 mb-3">
            <KeyRound size={13} className="text-slate-400" />
            <p className="text-[11px] font-black text-slate-400 uppercase tracking-widest">
              {es ? "Contraseña de la app" : "App password"}
            </p>
          </div>
          <p className="text-[10px] text-slate-400 mb-3">
            {es
              ? security.passwordEnabled
                ? "La app está protegida. Se pide la contraseña una vez por sesión del navegador."
                : "Al activarla, la app pedirá la contraseña al abrirla (una vez por sesión)."
              : "The app will ask for the password once per browser session."}
          </p>

          <div className="space-y-2.5">
            {security.passwordEnabled && (
              <div className="relative">
                <input type={showPass ? "text" : "password"} value={currentPass} onChange={e => setCurrentPass(e.target.value)}
                  placeholder={es ? "Contraseña actual *" : "Current password *"}
                  data-testid="security-current-password" className={inputCls} />
              </div>
            )}
            <div className="grid grid-cols-2 gap-2.5">
              <div className="relative">
                <input type={showPass ? "text" : "password"} value={newPass} onChange={e => setNewPass(e.target.value)}
                  placeholder={es ? (security.passwordEnabled ? "Nueva contraseña" : "Contraseña (mín. 4)") : "New password"}
                  data-testid="security-new-password" className={inputCls} />
                <button type="button" onClick={() => setShowPass(s => !s)} tabIndex={-1}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-300 hover:text-slate-500 transition-colors">
                  {showPass ? <EyeOff size={13} /> : <Eye size={13} />}
                </button>
              </div>
              <input type={showPass ? "text" : "password"} value={confirmPass} onChange={e => setConfirmPass(e.target.value)}
                placeholder={es ? "Confirmar contraseña" : "Confirm password"}
                data-testid="security-confirm-password" className={inputCls} />
            </div>
            <input type="text" value={hint} onChange={e => setHint(e.target.value)}
              placeholder={es ? "Pista de seguridad (por si la olvidas) — ej: mi película favorita" : "Security hint (in case you forget)"}
              data-testid="security-hint-input" className={inputCls} />

            <motion.button whileHover={{ scale: 1.01 }} whileTap={{ scale: 0.98 }}
              onClick={handleSavePassword} disabled={saving || !newPass}
              data-testid="security-save-password-btn"
              className="w-full flex items-center justify-center gap-2 py-3 rounded-2xl btn-primary text-white text-xs font-bold disabled:opacity-50">
              {saving ? <Loader2 size={14} className="animate-spin" /> : <KeyRound size={14} />}
              {security.passwordEnabled ? (es ? "Cambiar contraseña" : "Change password") : (es ? "Activar contraseña" : "Enable password")}
            </motion.button>
          </div>

          {/* Remove password */}
          {security.passwordEnabled && (
            <div className="mt-3">
              {!showRemove ? (
                <button onClick={() => setShowRemove(true)} data-testid="security-show-remove-btn"
                  className="text-[11px] font-bold text-slate-400 hover:text-red-500 transition-colors">
                  {es ? "Quitar la contraseña de la app…" : "Remove app password…"}
                </button>
              ) : (
                <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }}
                  className="flex items-center gap-2 bg-red-50/70 border border-red-200/60 rounded-2xl p-3">
                  <p className="text-[10px] text-red-500 font-semibold flex-1">
                    {es ? "Escribe tu contraseña actual arriba y confirma para quitarla" : "Type your current password above and confirm"}
                  </p>
                  <motion.button whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.95 }}
                    onClick={handleRemove} disabled={removing}
                    data-testid="security-remove-password-btn"
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-red-500 hover:bg-red-600 text-white text-[10px] font-black disabled:opacity-50 transition-colors">
                    {removing ? <Loader2 size={11} className="animate-spin" /> : <Trash2 size={11} />}
                    {es ? "Quitar" : "Remove"}
                  </motion.button>
                </motion.div>
              )}
            </div>
          )}
        </div>

        {/* ══════════ NUEVA FUNCIÓN 1: Auto-bloqueo por inactividad ══════════ */}
        <div className="border-t border-white/40 pt-5">
          <div className="flex items-start gap-3 mb-3">
            <div className="w-9 h-9 rounded-2xl bg-gradient-to-br from-amber-100 to-orange-100 flex items-center justify-center flex-shrink-0">
              <Clock size={16} className="text-orange-600" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-black text-slate-700">
                {es ? "Auto-bloqueo por inactividad" : "Auto-lock by inactivity"}
              </p>
              <p className="text-[11px] text-slate-400 mt-0.5">
                {es
                  ? "Bloquea la app automáticamente después de X minutos sin actividad (requiere contraseña activa)"
                  : "Locks the app after X minutes of inactivity"}
              </p>
            </div>
            <button type="button"
              onClick={() => saveAdvCfg({ auto_lock_enabled: !advCfg.auto_lock_enabled })}
              disabled={!security.passwordEnabled || advSaving}
              data-testid="auto-lock-toggle"
              role="switch"
              aria-checked={advCfg.auto_lock_enabled}
              className={`relative w-12 h-6 rounded-full transition-all flex-shrink-0 ${advCfg.auto_lock_enabled ? "btn-primary" : "bg-slate-200"} ${!security.passwordEnabled ? "opacity-40 cursor-not-allowed" : ""}`}>
              <span className={`absolute top-0.5 w-5 h-5 rounded-full bg-white shadow transition-all ${advCfg.auto_lock_enabled ? "left-[26px]" : "left-0.5"}`} />
            </button>
          </div>

          {!security.passwordEnabled && (
            <div className="flex items-center gap-2 text-[10px] text-amber-600 bg-amber-50 border border-amber-200 rounded-xl p-2 mb-3">
              <AlertTriangle size={12} className="flex-shrink-0" />
              <span>{es ? "Activa primero una contraseña de la app" : "Enable app password first"}</span>
            </div>
          )}

          <AnimatePresence>
            {advCfg.auto_lock_enabled && security.passwordEnabled && (
              <motion.div
                initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }}
                className="pl-12 space-y-2 overflow-hidden">
                <p className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">
                  {es ? "Bloquear después de" : "Lock after"}
                </p>
                <div className="grid grid-cols-6 gap-1.5">
                  {[1, 3, 5, 10, 15, 30].map(m => (
                    <motion.button key={m}
                      whileHover={{ scale: 1.05, y: -2 }} whileTap={{ scale: 0.95 }}
                      onClick={() => saveAdvCfg({ auto_lock_minutes: m })}
                      className={`py-2 rounded-xl text-[11px] font-black transition-all ${
                        advCfg.auto_lock_minutes === m ? "btn-primary text-white shadow-lg" : "bg-white/70 text-slate-500 hover:bg-white"
                      }`}
                      data-testid={`auto-lock-${m}min`}>
                      {m}m
                    </motion.button>
                  ))}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* ══════════ NUEVA FUNCIÓN 2: Límite de intentos fallidos ══════════ */}
        <div className="border-t border-white/40 pt-5">
          <div className="flex items-start gap-3 mb-3">
            <div className="w-9 h-9 rounded-2xl bg-gradient-to-br from-red-100 to-rose-100 flex items-center justify-center flex-shrink-0">
              <AlertTriangle size={16} className="text-red-600" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-black text-slate-700">
                {es ? "Límite de intentos fallidos" : "Failed attempts limit"}
              </p>
              <p className="text-[11px] text-slate-400 mt-0.5">
                {es
                  ? "Bloquea el acceso temporalmente tras varios intentos incorrectos"
                  : "Temporarily blocks access after multiple failed attempts"}
              </p>
            </div>
          </div>

          <div className="pl-12 space-y-3">
            <div>
              <p className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1.5">
                {es ? "Intentos máximos" : "Max attempts"}
              </p>
              <div className="grid grid-cols-5 gap-1.5">
                {[3, 5, 7, 10, 15].map(n => (
                  <motion.button key={n}
                    whileHover={{ scale: 1.05, y: -2 }} whileTap={{ scale: 0.95 }}
                    onClick={() => saveAdvCfg({ max_attempts: n })}
                    className={`py-2 rounded-xl text-[11px] font-black transition-all ${
                      advCfg.max_attempts === n ? "bg-red-500 text-white shadow-lg" : "bg-white/70 text-slate-500 hover:bg-white"
                    }`}
                    data-testid={`max-attempts-${n}`}>
                    {n}
                  </motion.button>
                ))}
              </div>
            </div>

            <div>
              <p className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1.5">
                {es ? "Bloqueo temporal" : "Lockout duration"}
              </p>
              <div className="grid grid-cols-5 gap-1.5">
                {[
                  { s: 30, label: "30s" },
                  { s: 60, label: "1m" },
                  { s: 300, label: "5m" },
                  { s: 900, label: "15m" },
                  { s: 3600, label: "1h" },
                ].map(({ s, label }) => (
                  <motion.button key={s}
                    whileHover={{ scale: 1.05, y: -2 }} whileTap={{ scale: 0.95 }}
                    onClick={() => saveAdvCfg({ lockout_seconds: s })}
                    className={`py-2 rounded-xl text-[11px] font-black transition-all ${
                      advCfg.lockout_seconds === s ? "bg-red-500 text-white shadow-lg" : "bg-white/70 text-slate-500 hover:bg-white"
                    }`}
                    data-testid={`lockout-${s}s`}>
                    {label}
                  </motion.button>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* ══════════ NUEVA FUNCIÓN 3: Bloqueo por sección ══════════ */}
        <div className="border-t border-white/40 pt-5">
          <div className="flex items-start gap-3 mb-3">
            <div className="w-9 h-9 rounded-2xl bg-gradient-to-br from-violet-100 to-purple-100 flex items-center justify-center flex-shrink-0">
              <LockKeyhole size={16} className="text-purple-600" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-black text-slate-700">
                {es ? "Contraseña por sección" : "Password per section"}
              </p>
              <p className="text-[11px] text-slate-400 mt-0.5">
                {es
                  ? "Pide la contraseña cada vez que abras estas secciones sensibles"
                  : "Ask password every time these sensitive sections are opened"}
              </p>
            </div>
          </div>

          {!security.passwordEnabled && (
            <div className="flex items-center gap-2 text-[10px] text-amber-600 bg-amber-50 border border-amber-200 rounded-xl p-2 mb-3">
              <AlertTriangle size={12} className="flex-shrink-0" />
              <span>{es ? "Activa primero una contraseña de la app" : "Enable app password first"}</span>
            </div>
          )}

          <div className="pl-12 grid grid-cols-2 gap-2">
            {PROTECTABLE_SECTIONS.map(sec => {
              const active = advCfg.protected_sections.includes(sec.key);
              return (
                <motion.button
                  key={sec.key}
                  whileHover={{ scale: security.passwordEnabled ? 1.03 : 1, y: security.passwordEnabled ? -2 : 0 }}
                  whileTap={{ scale: 0.97 }}
                  onClick={() => security.passwordEnabled && toggleSection(sec.key)}
                  disabled={!security.passwordEnabled || advSaving}
                  data-testid={`protect-section-${sec.key.replace(/[^a-z]/g, '')}`}
                  className={`flex items-center gap-2 py-2 px-3 rounded-xl text-[11px] font-bold transition-all ${
                    active
                      ? "bg-gradient-to-r from-purple-500 to-violet-600 text-white shadow-lg"
                      : "bg-white/70 text-slate-600 hover:bg-white"
                  } ${!security.passwordEnabled ? "opacity-40 cursor-not-allowed" : ""}`}
                >
                  {active ? <Lock size={11} /> : <LockKeyhole size={11} />}
                  <span className="truncate">{sec.label}</span>
                </motion.button>
              );
            })}
          </div>
        </div>
      </div>
    </Section>
  );
}
