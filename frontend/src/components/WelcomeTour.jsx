import { useEffect, useState, useCallback, useMemo } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import {
  ArrowLeft, ArrowRight, X, Sparkles, Rocket, Zap, TrendingUp, Calendar,
  Users, Database, Palette, Settings as SettingsIcon, RefreshCw,
  Search, Filter, Shield, Bell, Download, Star, Heart, Gift,
} from "lucide-react";
import { useSettings } from "@/context/SettingsContext";
import { celebrateTutorial } from "@/lib/celebrations";

// 18 pasos con icono + color + tips destacados
const TOUR_STEPS = [
  { route: "/dashboard", target: null, icon: Rocket, gradient: "from-purple-500 to-pink-500",
    title: "¡Bienvenido a Cinema Productions! 🎬",
    desc: "Te guiaremos paso a paso por todas las funciones. Puedes salir en cualquier momento.",
    tips: ["18 pasos rápidos", "≈ 3 minutos", "Puedes reiniciarlo desde Apariencia"] },
  { route: "/dashboard", target: '[data-testid="stats-grid"]', icon: TrendingUp, gradient: "from-emerald-500 to-teal-500",
    title: "Estadísticas en vivo",
    desc: "Métricas clave siempre visibles: próximos eventos, ingresos reales y saldos pendientes.",
    tips: ["Actualización automática", "Muestra dinero acumulado", "Filtrable desde Apariencia"] },
  { route: "/dashboard", target: '[data-testid="charts-section"]', icon: TrendingUp, gradient: "from-blue-500 to-indigo-500",
    title: "Gráficos interactivos",
    desc: "Ingresos por mes visualizados con barras dinámicas. Pasa el mouse para ver detalles.",
    tips: ["Ingresos por mes", "Comparativa año actual", "Exportable como imagen"] },
  { route: "/reservaciones", target: '[data-testid="new-reservation-btn"]', icon: Zap, gradient: "from-amber-500 to-orange-500",
    title: "Crea reservas en segundos",
    desc: "Registra eventos con cliente, fecha, anticipo, paquete y estado. Todo en un solo formulario.",
    tips: ["Guarda anticipos", "Calcula saldo automáticamente", "Sube comprobantes de pago"] },
  { route: "/reservaciones", target: '[data-testid="search-input"]', icon: Search, gradient: "from-cyan-500 to-blue-500",
    title: "Búsqueda instantánea",
    desc: "Escribe cliente, tipo de evento o lugar. Los resultados aparecen mientras escribes.",
    tips: ["Sin recargar página", "Busca en todos los campos", "Ignora mayúsculas/acentos"] },
  { route: "/reservaciones", target: '[data-testid="toggle-extra-filters"]', icon: Filter, gradient: "from-violet-500 to-purple-500",
    title: "Filtros avanzados",
    desc: "Combina filtros: estado, paquete y rango de fechas. Perfecto para reportes.",
    tips: ["Estado + Paquete", "Rango de fechas", "Guarda combinaciones"] },
  { route: "/calendario", target: '[data-testid="calendar-grid"]', icon: Calendar, gradient: "from-rose-500 to-pink-500",
    title: "Calendario visual",
    desc: "Vista mensual con pastillas de color por tipo de evento. Detecta conflictos al instante.",
    tips: ["Colores por tipo", "Click para editar", "Detecta solapamientos"] },
  { route: "/calendario", target: '[data-testid="calendar-month-select"]', icon: Calendar, gradient: "from-fuchsia-500 to-rose-500",
    title: "Navega el tiempo",
    desc: "Salta a cualquier mes o año con un clic. Ideal para planificar con anticipación.",
    tips: ["Meses futuros", "Historial completo", "Zoom por semana"] },
  { route: "/socios", target: null, icon: Users, gradient: "from-sky-500 to-cyan-500",
    title: "Tu equipo de trabajo",
    desc: "Registra socios (fotógrafos, videógrafos, editores), asígnales eventos y controla pagos.",
    tips: ["Fotos de perfil", "Tarifa por evento", "Estado Pendiente/Pagado"] },
  { route: "/base-de-datos", target: '[data-testid="db-url-input"]', icon: Database, gradient: "from-emerald-500 to-green-500",
    title: "Base de datos dinámica",
    desc: "Conecta tu propio MongoDB (Atlas, NAS o local). Todos tus dispositivos comparten datos.",
    tips: ["MongoDB Atlas gratis", "Multi-dispositivo", "Cambio sin reiniciar"] },
  { route: "/base-de-datos", target: '[data-testid="backup-server-btn"]', icon: Shield, gradient: "from-lime-500 to-emerald-500",
    title: "Respaldos automáticos",
    desc: "Copias de seguridad programadas + auto-backup a tu PC. Restaura con un clic si algo falla.",
    tips: ["Backup a la nube", "Auto-backup a PC", "Historial de 30 días"] },
  { route: "/base-de-datos", target: '[data-testid="db-block-toggle-github"]', icon: Star, gradient: "from-slate-700 to-slate-900",
    title: "🆕 GitHub y Contexto IA",
    desc: "Conecta tu repositorio de GitHub y guarda el contexto de la app para la próxima IA.",
    tips: ["Sincroniza código", "Contexto oculto para IA", "Actualiza con un botón"] },
  { route: "/apariencia", target: '[data-testid="appearance-search-input"]', icon: Search, gradient: "from-indigo-500 to-blue-500",
    title: "Buscador de funciones",
    desc: "¿No encuentras una opción? Escribe aquí (ej: «fuente», «color») y salta a esa sección.",
    tips: ["Búsqueda inteligente", "Salta directo a la config", "Historial de búsquedas"] },
  { route: "/apariencia", target: '[data-testid="section-saved-themes-section"]', icon: Palette, gradient: "from-pink-500 to-rose-500",
    title: "Temas guardados",
    desc: "Guarda combinaciones de apariencia con nombre y restáuralas cuando quieras.",
    tips: ["Nombres personalizados", "Sincroniza con la nube", "Comparte temas"] },
  { route: "/apariencia", target: '[data-testid="section-nav-menu-section"]', icon: SettingsIcon, gradient: "from-orange-500 to-amber-500",
    title: "Personaliza el menú",
    desc: "Reordena y renombra las opciones del sidebar. Ocúltalas si no las usas.",
    tips: ["Arrastra para reordenar", "Renombra a tu gusto", "Oculta opciones"] },
  { route: "/ajustes", target: '[data-testid="settings-search-input"]', icon: Bell, gradient: "from-teal-500 to-cyan-500",
    title: "Notificaciones multi-canal",
    desc: "Recordatorios por Email, Telegram, WhatsApp, ntfy y Push del navegador.",
    tips: ["5 canales disponibles", "Recordatorios automáticos", "Plantillas editables"] },
  { route: "/ajustes", target: '[data-testid="section-toggle-seguridad"]', icon: Shield, gradient: "from-red-500 to-rose-500",
    title: "Seguridad avanzada",
    desc: "Protege la app con contraseña, bloquea copiar/pegar y activa auto-bloqueo por inactividad.",
    tips: ["Contraseña bcrypt", "Bloqueo por sección", "Auto-lock configurable"] },
  { route: "/actualizaciones", target: '[data-testid="check-updates-btn"]', icon: Gift, gradient: "from-purple-500 to-fuchsia-500",
    title: "¡Ya conoces la app! 🎉",
    desc: "Busca actualizaciones cuando quieras, publica nuevas versiones y sincroniza con GitHub.",
    tips: ["Chequeo automático", "GitHub sync", "Rollback disponible"] },
];

// Partículas de fondo aleatorias
const Particles = () => {
  const particles = useMemo(() => Array.from({ length: 25 }, (_, i) => ({
    id: i,
    x: Math.random() * 100,
    y: Math.random() * 100,
    size: Math.random() * 4 + 2,
    duration: Math.random() * 4 + 3,
    delay: Math.random() * 2,
  })), []);
  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none">
      {particles.map(p => (
        <motion.div
          key={p.id}
          className="absolute rounded-full bg-white/40"
          style={{ left: `${p.x}%`, top: `${p.y}%`, width: p.size, height: p.size }}
          animate={{
            y: [0, -30, 0],
            opacity: [0.2, 0.8, 0.2],
            scale: [1, 1.5, 1],
          }}
          transition={{
            duration: p.duration,
            delay: p.delay,
            repeat: Infinity,
            ease: "easeInOut",
          }}
        />
      ))}
    </div>
  );
};

export default function WelcomeTour() {
  const { showTour, endTour } = useSettings();
  const navigate = useNavigate();
  const location = useLocation();
  const [step, setStep] = useState(0);
  const [rect, setRect] = useState(null);

  const current = TOUR_STEPS[step];
  const total = TOUR_STEPS.length;

  const locateTarget = useCallback(() => {
    if (!current?.target) { setRect(null); return; }
    const el = document.querySelector(current.target);
    if (!el) { setRect(null); return; }
    el.scrollIntoView({ behavior: "smooth", block: "center" });
    setTimeout(() => {
      const r = el.getBoundingClientRect();
      if (r.width > 0 && r.height > 0) setRect({ top: r.top, left: r.left, width: r.width, height: r.height });
      else setRect(null);
    }, 380);
  }, [current]);

  useEffect(() => {
    if (!showTour) return;
    setRect(null);
    if (location.pathname !== current.route) navigate(current.route);
    const t = setTimeout(locateTarget, 550);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step, showTour]);

  useEffect(() => { if (showTour) setStep(0); }, [showTour]);

  if (!showTour || !current) return null;

  const next = () => {
    if (step < total - 1) {
      setStep(step + 1);
    } else {
      celebrateTutorial();
      setTimeout(() => endTour(), 400);
    }
  };
  const prev = () => { if (step > 0) setStep(step - 1); };

  const Icon = current.icon;
  const isLast = step === total - 1;
  const isFirst = step === 0;

  return (
    <AnimatePresence>
      <motion.div key="tour" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
        className="fixed inset-0 z-[200]" data-testid="welcome-tour-overlay">

        {/* Backdrop / spotlight */}
        {rect ? (
          <motion.div
            initial={false}
            animate={{ top: rect.top - 10, left: rect.left - 10, width: rect.width + 20, height: rect.height + 20 }}
            transition={{ type: "spring", stiffness: 200, damping: 26 }}
            className="fixed rounded-2xl pointer-events-none"
            style={{
              boxShadow: "0 0 0 9999px rgba(15,23,42,0.75)",
              border: "3px solid var(--t-from)",
            }}
          >
            {/* Pulso animado alrededor del target */}
            <motion.div
              className="absolute inset-0 rounded-2xl"
              animate={{
                boxShadow: [
                  "0 0 0 0 rgba(139,92,246,0.6)",
                  "0 0 0 16px rgba(139,92,246,0)",
                ],
              }}
              transition={{ duration: 1.6, repeat: Infinity }}
            />
            {/* Puntos brillantes en las esquinas */}
            {[[0,0],[100,0],[0,100],[100,100]].map(([x,y], i) => (
              <motion.div
                key={i}
                className="absolute w-2.5 h-2.5 rounded-full bg-white"
                style={{ left: `${x}%`, top: `${y}%`, transform: "translate(-50%,-50%)", boxShadow: "0 0 10px rgba(255,255,255,0.9)" }}
                animate={{ scale: [1, 1.5, 1], opacity: [0.6, 1, 0.6] }}
                transition={{ duration: 1.6, repeat: Infinity, delay: i * 0.15 }}
              />
            ))}
          </motion.div>
        ) : (
          <div className="fixed inset-0" style={{ background: "radial-gradient(circle at 50% 50%, rgba(15,23,42,0.55) 0%, rgba(15,23,42,0.88) 80%)" }}>
            <Particles />
          </div>
        )}

        {/* Card — épica con gradientes y animaciones */}
        <motion.div
          key={`card-${step}`}
          initial={{ opacity: 0, y: 40, scale: 0.92, rotateX: -8 }}
          animate={{ opacity: 1, y: 0, scale: 1, rotateX: 0 }}
          exit={{ opacity: 0, y: 20, scale: 0.95 }}
          transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
          className="fixed bottom-6 left-1/2 -translate-x-1/2 w-[min(500px,94vw)] rounded-3xl overflow-hidden"
          style={{
            boxShadow: "0 32px 100px rgba(0,0,0,0.6), 0 0 0 1px rgba(255,255,255,0.1)",
            transformStyle: "preserve-3d",
            perspective: "1000px",
          }}
          data-testid="tour-card"
        >
          {/* Header con gradiente dinámico */}
          <div className={`relative bg-gradient-to-br ${current.gradient} p-5 overflow-hidden`}>
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

            <div className="relative flex items-center justify-between mb-3">
              <span className="flex items-center gap-1.5 text-[10px] font-black px-2.5 py-1 rounded-full text-slate-900 bg-white/90 backdrop-blur">
                <Sparkles size={10} /> Paso {step + 1} / {total}
              </span>
              <button onClick={endTour} data-testid="tour-skip-btn"
                className="flex items-center gap-1 text-[11px] font-bold text-white/80 hover:text-white transition-colors">
                Saltar <X size={13} />
              </button>
            </div>

            <div className="relative flex items-start gap-3">
              {/* Icono animado con anillos */}
              <div className="relative flex-shrink-0">
                <motion.div
                  className="absolute inset-0 rounded-2xl bg-white/30"
                  animate={{ scale: [1, 1.4, 1], opacity: [0.6, 0, 0.6] }}
                  transition={{ duration: 1.8, repeat: Infinity }}
                />
                <motion.div
                  className="relative w-14 h-14 rounded-2xl bg-white/25 backdrop-blur flex items-center justify-center"
                  animate={{ rotate: [0, 8, -8, 0], scale: [1, 1.08, 1] }}
                  transition={{ duration: 2.4, repeat: Infinity }}
                >
                  <Icon size={28} className="text-white" strokeWidth={2} />
                </motion.div>
              </div>

              <div className="flex-1 min-w-0 text-white">
                <motion.h3
                  key={`title-${step}`}
                  initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.15 }}
                  className="text-xl font-black leading-tight"
                  style={{ fontFamily: "Cabinet Grotesk, sans-serif" }}
                >
                  {current.title}
                </motion.h3>
                <motion.p
                  key={`desc-${step}`}
                  initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.25 }}
                  className="text-sm text-white/90 leading-snug mt-1"
                >
                  {current.desc}
                </motion.p>
              </div>
            </div>
          </div>

          {/* Body con tips destacados */}
          <div className="bg-white p-5 space-y-3">
            {/* Tips como chips */}
            <div className="flex flex-wrap gap-1.5">
              {current.tips?.map((tip, i) => (
                <motion.span
                  key={`${step}-tip-${i}`}
                  initial={{ opacity: 0, scale: 0.8, y: 8 }}
                  animate={{ opacity: 1, scale: 1, y: 0 }}
                  transition={{ delay: 0.3 + i * 0.08, type: "spring", stiffness: 300 }}
                  className="text-[10px] font-bold px-2 py-1 rounded-full bg-slate-100 text-slate-700 flex items-center gap-1"
                >
                  <motion.span
                    animate={{ scale: [1, 1.4, 1] }}
                    transition={{ duration: 1.5, repeat: Infinity, delay: i * 0.2 }}
                    className="w-1.5 h-1.5 rounded-full bg-emerald-500"
                  />
                  {tip}
                </motion.span>
              ))}
            </div>

            {/* Progress bar con gradiente */}
            <div className="relative h-2 rounded-full bg-slate-100 overflow-hidden">
              <motion.div
                className={`h-full rounded-full bg-gradient-to-r ${current.gradient}`}
                animate={{ width: `${((step + 1) / total) * 100}%` }}
                transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
              />
              {/* Brillo que recorre */}
              <motion.div
                className="absolute top-0 h-full w-8 bg-white/50 blur-sm"
                animate={{ left: ["-10%", "100%"] }}
                transition={{ duration: 1.5, repeat: Infinity, ease: "easeInOut" }}
              />
            </div>

            {/* Botones */}
            <div className="flex items-center justify-between pt-1">
              <motion.button
                whileHover={{ scale: isFirst ? 1 : 1.05, x: isFirst ? 0 : -2 }}
                whileTap={{ scale: 0.95 }}
                onClick={prev} disabled={isFirst}
                data-testid="tour-prev-btn"
                className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-bold text-slate-500 hover:bg-slate-100 disabled:opacity-30 disabled:pointer-events-none transition-colors"
              >
                <ArrowLeft size={13} /> Anterior
              </motion.button>

              <motion.button
                whileHover={{ scale: 1.06, x: 2 }}
                whileTap={{ scale: 0.94 }}
                onClick={next} data-testid="tour-next-btn"
                className={`flex items-center gap-1.5 px-5 py-2.5 rounded-xl text-white text-xs font-black bg-gradient-to-r ${current.gradient} shadow-lg`}
                style={{ boxShadow: "0 8px 24px rgba(139,92,246,0.35)" }}
              >
                {isLast ? (
                  <>
                    <motion.span
                      animate={{ rotate: [0, 20, -20, 0] }}
                      transition={{ duration: 1, repeat: Infinity }}
                    >
                      🎉
                    </motion.span>
                    ¡Terminar!
                  </>
                ) : (
                  <>Siguiente <ArrowRight size={13} /></>
                )}
              </motion.button>
            </div>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
