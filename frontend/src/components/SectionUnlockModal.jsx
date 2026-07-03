// Modal de desbloqueo por sección — con animaciones épicas
import { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Lock, X, Eye, EyeOff, ShieldAlert, KeyRound, Loader2 } from "lucide-react";

const SECTION_LABELS = {
  "/base-de-datos": "Base de Datos",
  "/ajustes":       "Ajustes",
  "/socios":        "Socios",
  "/reservaciones": "Reservaciones",
  "/apariencia":    "Apariencia",
  "/actualizaciones": "Actualizaciones",
  "/calendario":    "Calendario",
};

export default function SectionUnlockModal({ sectionLock, onUnlock, onCancel }) {
  const [password, setPassword] = useState("");
  const [showPass, setShowPass] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const inputRef = useRef(null);

  useEffect(() => {
    setPassword("");
    setError("");
    setTimeout(() => inputRef.current?.focus(), 300);
  }, [sectionLock]);

  if (!sectionLock) return null;

  const label = SECTION_LABELS[sectionLock.path] || sectionLock.path;

  const handleSubmit = async (e) => {
    e?.preventDefault();
    if (!password || loading) return;
    setLoading(true);
    setError("");
    const res = await onUnlock(password);
    setLoading(false);
    if (!res.ok) {
      setError(res.error || "Contraseña incorrecta");
      // Shake animation
      inputRef.current?.classList.add("animate-shake");
      setTimeout(() => inputRef.current?.classList.remove("animate-shake"), 500);
    }
  };

  return (
    <AnimatePresence>
      <motion.div
        key="section-lock"
        initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
        className="fixed inset-0 z-[300] flex items-center justify-center p-4"
        style={{
          background: "radial-gradient(circle at 50% 30%, rgba(139,92,246,0.35) 0%, rgba(15,23,42,0.92) 70%)",
          backdropFilter: "blur(16px)",
        }}
      >
        {/* Partículas de fondo */}
        <div className="absolute inset-0 overflow-hidden pointer-events-none">
          {Array.from({ length: 20 }).map((_, i) => (
            <motion.div
              key={i}
              className="absolute rounded-full bg-white/20"
              style={{
                left: `${Math.random() * 100}%`,
                top: `${Math.random() * 100}%`,
                width: Math.random() * 4 + 2,
                height: Math.random() * 4 + 2,
              }}
              animate={{
                y: [0, -40, 0],
                opacity: [0.2, 0.8, 0.2],
              }}
              transition={{
                duration: Math.random() * 3 + 2,
                delay: Math.random() * 2,
                repeat: Infinity,
                ease: "easeInOut",
              }}
            />
          ))}
        </div>

        <motion.form
          onSubmit={handleSubmit}
          initial={{ scale: 0.85, opacity: 0, rotateX: -20, y: 30 }}
          animate={{ scale: 1, opacity: 1, rotateX: 0, y: 0 }}
          exit={{ scale: 0.9, opacity: 0 }}
          transition={{ type: "spring", damping: 22, stiffness: 260 }}
          className="relative w-full max-w-md rounded-3xl overflow-hidden"
          style={{
            boxShadow: "0 40px 100px rgba(0,0,0,0.6), 0 0 0 1px rgba(255,255,255,0.1), 0 0 80px rgba(139,92,246,0.4)",
            transformStyle: "preserve-3d",
          }}
        >
          {/* Header con gradiente animado */}
          <div className="relative bg-gradient-to-br from-purple-600 via-violet-600 to-indigo-600 p-6 overflow-hidden">
            {/* Brillos decorativos */}
            <motion.div
              className="absolute -top-8 -right-8 w-40 h-40 rounded-full bg-white/20"
              animate={{ scale: [1, 1.3, 1], opacity: [0.3, 0.5, 0.3] }}
              transition={{ duration: 3, repeat: Infinity }}
            />
            <motion.div
              className="absolute -bottom-6 -left-6 w-32 h-32 rounded-full bg-white/15"
              animate={{ scale: [1, 1.4, 1], opacity: [0.2, 0.4, 0.2] }}
              transition={{ duration: 3.5, repeat: Infinity, delay: 0.5 }}
            />

            <button
              type="button"
              onClick={onCancel}
              className="absolute right-4 top-4 w-8 h-8 rounded-full bg-white/20 hover:bg-white/30 backdrop-blur flex items-center justify-center text-white transition-colors"
              data-testid="section-lock-cancel"
            >
              <X size={16} />
            </button>

            <div className="relative flex items-center gap-4">
              {/* Icono candado con anillos pulsantes */}
              <div className="relative flex-shrink-0">
                <motion.div
                  className="absolute inset-0 rounded-2xl bg-white/40"
                  animate={{ scale: [1, 1.5, 1], opacity: [0.5, 0, 0.5] }}
                  transition={{ duration: 1.8, repeat: Infinity }}
                />
                <motion.div
                  className="absolute inset-0 rounded-2xl bg-white/30"
                  animate={{ scale: [1, 1.8, 1], opacity: [0.4, 0, 0.4] }}
                  transition={{ duration: 1.8, repeat: Infinity, delay: 0.3 }}
                />
                <motion.div
                  className="relative w-16 h-16 rounded-2xl bg-white/25 backdrop-blur flex items-center justify-center"
                  animate={{ rotateY: [0, 15, -15, 0] }}
                  transition={{ duration: 3, repeat: Infinity }}
                >
                  <Lock size={30} className="text-white" strokeWidth={2.2} />
                </motion.div>
              </div>

              <div className="flex-1 text-white">
                <div className="flex items-center gap-1.5 text-[10px] font-black uppercase tracking-widest text-white/80 mb-1">
                  <ShieldAlert size={11} /> Sección protegida
                </div>
                <h3 className="text-2xl font-black leading-tight" style={{ fontFamily: "Cabinet Grotesk, sans-serif" }}>
                  {label}
                </h3>
                <p className="text-xs text-white/85 mt-1">
                  Ingresa tu contraseña para acceder a esta sección
                </p>
              </div>
            </div>
          </div>

          {/* Body */}
          <div className="bg-white p-6 space-y-4">
            <div>
              <label className="text-[11px] font-black text-slate-500 uppercase tracking-widest flex items-center gap-1.5 mb-2">
                <KeyRound size={11} /> Contraseña
              </label>
              <div className="relative">
                <input
                  ref={inputRef}
                  type={showPass ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoFocus
                  data-testid="section-lock-password-input"
                  className="w-full px-4 py-3 pr-11 rounded-xl bg-slate-50 border-2 border-slate-200 text-sm text-slate-800 focus:outline-none focus:border-purple-500 focus:bg-white transition-all font-medium"
                  placeholder="••••••••"
                />
                <button
                  type="button"
                  onClick={() => setShowPass(v => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                  tabIndex={-1}
                >
                  {showPass ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            <AnimatePresence>
              {error && (
                <motion.div
                  initial={{ opacity: 0, y: -8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  className="flex items-center gap-2 bg-red-50 border border-red-200 rounded-xl p-3"
                  data-testid="section-lock-error"
                >
                  <ShieldAlert size={14} className="text-red-500 flex-shrink-0" />
                  <p className="text-[11px] font-bold text-red-600 flex-1">{error}</p>
                </motion.div>
              )}
            </AnimatePresence>

            {sectionLock.hint && !error && (
              <div className="text-[10px] text-slate-400 italic bg-slate-50 border border-slate-100 rounded-xl p-2.5">
                💡 Pista: {sectionLock.hint}
              </div>
            )}

            <div className="flex items-center gap-2 pt-1">
              <button
                type="button"
                onClick={onCancel}
                data-testid="section-lock-back-btn"
                className="flex-1 py-3 rounded-xl text-xs font-bold text-slate-500 hover:bg-slate-100 transition-colors"
              >
                Volver al inicio
              </button>
              <motion.button
                type="submit"
                whileHover={{ scale: 1.03 }}
                whileTap={{ scale: 0.97 }}
                disabled={!password || loading}
                data-testid="section-lock-unlock-btn"
                className="flex-1 flex items-center justify-center gap-2 py-3 rounded-xl bg-gradient-to-r from-purple-600 to-violet-600 text-white text-xs font-black shadow-lg disabled:opacity-40 disabled:cursor-not-allowed"
                style={{ boxShadow: "0 8px 24px rgba(139,92,246,0.4)" }}
              >
                {loading ? <Loader2 size={13} className="animate-spin" /> : <Lock size={13} />}
                Desbloquear
              </motion.button>
            </div>
          </div>
        </motion.form>
      </motion.div>
    </AnimatePresence>
  );
}
