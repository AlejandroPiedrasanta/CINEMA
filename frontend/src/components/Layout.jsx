import { NavLink } from "react-router-dom";
import { LayoutDashboard, CalendarDays, List, Menu, X, SlidersHorizontal, Users, Database, Palette, RefreshCw } from "lucide-react";
import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useSettings, PRESETS } from "@/context/SettingsContext";

export default function Layout({ children }) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const { tr, preset, logoUrl, logoSize, sidebarCompact, iconSize, sidebarStyle, islandMargins } = useSettings();
  const presetLabel = PRESETS.find(p => p.id === preset)?.name || "Glass Aurora";
  const sidebarLogoH = Math.min(Math.max(logoSize || 40, 24), 80);

  // "island" always uses islandMargins for margins; no pill style
  const compact = sidebarCompact;

  // Icon size mapping
  const iconPx = iconSize === "small" ? 14 : iconSize === "large" ? 22 : 18;
  const iconPxInline = iconSize === "small" ? 12 : iconSize === "large" ? 20 : 16;

  const { top: mTop, bottom: mBottom, side: mSide } = islandMargins || { top: 14, bottom: 14, side: 14 };
  const sidebarWidth = compact ? "72px" : "240px";

  // Per-style inline overrides
  const styleMap = {
    normal:     {},
    floating: {
      margin: "12px 0 12px 12px",
      borderRadius: "20px",
      minHeight: "calc(100vh - 24px)",
      height: "calc(100vh - 24px)",
      boxShadow: "0 20px 60px rgba(31,38,135,0.14), 0 4px 16px rgba(0,0,0,0.06)",
    },
    borderless: {
      borderRight: "none",
      boxShadow: "none",
      background: "transparent",
      backdropFilter: "none",
    },
    island: {
      top: `${mTop}px`,
      bottom: `${mBottom}px`,
      left: `${mSide}px`,
      height: "auto",
      minHeight: "auto",
      borderRadius: "28px",
      boxShadow: "0 32px 80px rgba(31,38,135,0.22), 0 8px 30px rgba(0,0,0,0.1)",
      background: "rgba(255,255,255,0.88)",
      backdropFilter: "blur(28px) saturate(180%)",
    },
    minimal: {
      background: "rgba(255,255,255,0.18)",
      borderRight: "1px solid rgba(255,255,255,0.22)",
      boxShadow: "none",
      backdropFilter: "blur(6px)",
    },
  };

  const sidebarExtra = styleMap[sidebarStyle] || {};
  const mainMarginLeft = ["floating", "island"].includes(sidebarStyle)
    ? `calc(${sidebarWidth} + ${sidebarStyle === "island" ? mSide + 12 : 14}px)`
    : sidebarWidth;

  const navItems = [
    { path: "/dashboard",      label: tr.nav.dashboard,          icon: LayoutDashboard },
    { path: "/reservaciones",  label: tr.nav.reservations,       icon: List },
    { path: "/calendario",     label: tr.nav.calendar,           icon: CalendarDays },
    { path: "/socios",         label: tr.nav.socios || "Socios", icon: Users },
    { path: "/base-de-datos",  label: tr.nav.database || "Base de Datos", icon: Database },
    { path: "/apariencia",     label: tr.nav.appearance || "Apariencia",  icon: Palette },
    { path: "/ajustes",        label: tr.nav.settings,           icon: SlidersHorizontal },
    { path: "/actualizaciones", label: "Actualizaciones",        icon: RefreshCw },
  ];

  return (
    <div className="flex min-h-screen" style={{ position: "relative", zIndex: 1 }}>
      {/* Desktop Sidebar */}
      <aside
        className="hidden md:flex flex-col min-h-screen glass-sidebar fixed left-0 top-0 z-20 transition-all duration-300"
        style={{ width: sidebarWidth, ...sidebarExtra }}
      >
        {/* Logo area */}
        <div className={`border-b border-white/40 transition-all duration-300 ${compact ? "px-3 py-5 flex justify-center" : "px-6 py-6"}`}>
          {compact ? (
            <div className="w-9 h-9 rounded-xl btn-primary flex items-center justify-center text-white font-black text-base">
              C
            </div>
          ) : (
            <>
              <div className="flex items-center gap-2.5">
                <img
                  src={logoUrl || "/logo.png"}
                  alt="Cinema Productions"
                  className="w-auto rounded-xl object-contain"
                  style={{ height: `${sidebarLogoH}px`, maxWidth: "140px" }}
                />
              </div>
              <p className="text-[10px] text-slate-400 font-medium mt-1.5 pl-0.5">{tr.nav.tagline}</p>
            </>
          )}
        </div>

        <nav className={`flex-1 py-5 space-y-1 transition-all duration-300 ${compact ? "px-2" : "px-3"}`}>
          {navItems.map(({ path, label, icon: Icon }) => (
            <NavLink
              key={path}
              to={path}
              data-testid={`nav-${path.replace("/", "")}`}
              title={compact ? label : undefined}
              className={({ isActive }) =>
                `flex items-center gap-3 py-2.5 rounded-2xl text-sm font-semibold transition-all duration-300 ${
                  compact ? "px-0 justify-center" : "px-4"
                } ${
                  isActive ? "nav-active" : "text-slate-600 hover:bg-white/50 hover:text-slate-900"
                }`
              }
            >
              {({ isActive }) => (
                <>
                  <motion.span
                    animate={{ scale: isActive ? 1.1 : 1 }}
                    transition={{ duration: 0.2 }}
                    className="flex-shrink-0"
                  >
                    <Icon size={compact ? iconPx : iconPxInline} strokeWidth={isActive ? 2.2 : 1.5} />
                  </motion.span>
                  {!compact && <span className="sidebar-compact-label">{label}</span>}
                </>
              )}
            </NavLink>
          ))}
        </nav>

        {!compact && (
          <div className="px-6 py-4 border-t border-white/40">
            <p className="text-[10px] text-slate-400 font-medium">v1.0 · {presetLabel}</p>
          </div>
        )}
      </aside>

      {/* Mobile Header */}
      <div className="md:hidden fixed top-0 left-0 right-0 z-30 glass border-b border-white/50">
        <div className="flex items-center justify-between px-5 py-4">
          <div className="flex items-center gap-2.5">
            <img
              src={logoUrl || "/logo.png"}
              alt="Cinema Productions"
              className="w-auto rounded-lg object-contain"
              style={{ height: "28px", maxWidth: "90px" }}
            />
          </div>
          <button onClick={() => setMobileOpen(!mobileOpen)} data-testid="mobile-menu-toggle" className="p-2 rounded-2xl text-slate-600 hover:bg-white/50 transition-all">
            {mobileOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>
      </div>

      <AnimatePresence>
        {mobileOpen && (
          <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }} transition={{ duration: 0.2 }} className="md:hidden fixed inset-0 z-20 glass-strong pt-16">
            <nav className="px-4 py-4 space-y-1">
              {navItems.map(({ path, label, icon: Icon }) => (
                <NavLink key={path} to={path} onClick={() => setMobileOpen(false)}
                  className={({ isActive }) => `flex items-center gap-3 px-4 py-3 rounded-2xl text-sm font-semibold transition-all duration-200 ${isActive ? "nav-active" : "text-slate-600 hover:bg-white/60"}`}
                >
                  <Icon size={18} strokeWidth={1.5} />
                  {label}
                </NavLink>
              ))}
            </nav>
          </motion.div>
        )}
      </AnimatePresence>

      <main
        className="flex-1 min-h-screen transition-all duration-300"
        style={{ marginLeft: mainMarginLeft }}
      >
        <div className="pt-16 md:pt-0 min-h-screen">{children}</div>
      </main>
    </div>
  );
}
