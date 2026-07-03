// Auto-lock por inactividad + Bloqueo por sección
import { useEffect, useRef, useState, useCallback } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { getSecurityStatus, verifyAppPassword } from "@/lib/api";

/**
 * Hook global: gestiona auto-lock por inactividad y protección por sección.
 * Se debe montar UNA sola vez, en Layout/App raíz.
 * Devuelve { lockedFor, unlockSection, forceLock } para orquestar UI.
 */
export function useAdvancedSecurity() {
  const location = useLocation();
  const [cfg, setCfg] = useState({
    password_enabled: false,
    auto_lock_enabled: false,
    auto_lock_minutes: 5,
    protected_sections: [],
  });
  const [sectionLock, setSectionLock] = useState(null); // { path, hint }
  const [needsAppUnlock, setNeedsAppUnlock] = useState(false);
  const timerRef = useRef(null);
  const unlockedSectionsRef = useRef(new Set()); // sesiones ya desbloqueadas en esta ventana

  // Refresh config
  const refresh = useCallback(async () => {
    try {
      const s = await getSecurityStatus();
      setCfg({
        password_enabled: s.password_enabled,
        auto_lock_enabled: s.auto_lock_enabled,
        auto_lock_minutes: s.auto_lock_minutes || 5,
        protected_sections: s.protected_sections || [],
        hint: s.hint || "",
      });
    } catch {}
  }, []);
  useEffect(() => { refresh(); }, [refresh]);

  // Escuchar cambios externos (ej: config actualizada desde SecuritySection)
  useEffect(() => {
    const handler = () => refresh();
    window.addEventListener("cp:security-updated", handler);
    return () => window.removeEventListener("cp:security-updated", handler);
  }, [refresh]);

  // ── Auto-lock por inactividad ─────────────────────────
  const resetTimer = useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    if (!cfg.auto_lock_enabled || !cfg.password_enabled) return;
    const ms = cfg.auto_lock_minutes * 60 * 1000;
    timerRef.current = setTimeout(() => {
      // Bloquear la app: quitar sessionStorage e informar
      sessionStorage.removeItem("cp_app_unlocked");
      unlockedSectionsRef.current.clear();
      setNeedsAppUnlock(true);
      window.dispatchEvent(new CustomEvent("cp:app-locked"));
    }, ms);
  }, [cfg.auto_lock_enabled, cfg.auto_lock_minutes, cfg.password_enabled]);

  useEffect(() => {
    if (!cfg.auto_lock_enabled || !cfg.password_enabled) {
      if (timerRef.current) clearTimeout(timerRef.current);
      return;
    }
    const events = ["mousedown", "mousemove", "keydown", "scroll", "touchstart", "click"];
    events.forEach(e => window.addEventListener(e, resetTimer, { passive: true }));
    resetTimer();
    return () => {
      events.forEach(e => window.removeEventListener(e, resetTimer));
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [resetTimer, cfg.auto_lock_enabled, cfg.password_enabled]);

  // ── Protección por sección ────────────────────────────
  useEffect(() => {
    if (!cfg.password_enabled) return;
    if (!cfg.protected_sections?.length) return;
    const path = location.pathname;
    const isProtected = cfg.protected_sections.some(p => path.startsWith(p));
    if (isProtected && !unlockedSectionsRef.current.has(path)) {
      setSectionLock({ path, hint: cfg.hint });
    }
  }, [location.pathname, cfg.password_enabled, cfg.protected_sections, cfg.hint]);

  const unlockSection = useCallback(async (password) => {
    try {
      await verifyAppPassword(password);
      unlockedSectionsRef.current.add(sectionLock.path);
      setSectionLock(null);
      return { ok: true };
    } catch (err) {
      return { ok: false, error: err?.response?.data?.detail || "Error" };
    }
  }, [sectionLock]);

  const cancelSectionLock = useCallback(() => {
    setSectionLock(null);
    // Redirigir a dashboard
    window.history.replaceState(null, "", "/dashboard");
    window.dispatchEvent(new PopStateEvent("popstate"));
  }, []);

  return {
    sectionLock,
    unlockSection,
    cancelSectionLock,
    needsAppUnlock,
    setNeedsAppUnlock,
    autoLockEnabled: cfg.auto_lock_enabled && cfg.password_enabled,
  };
}
