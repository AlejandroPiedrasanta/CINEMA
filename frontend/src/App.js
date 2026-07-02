import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import { AnimatePresence, motion, MotionConfig } from "framer-motion";
import { SettingsProvider, useSettings } from "@/context/SettingsContext";
import Layout from "@/components/Layout";
import Dashboard from "@/pages/Dashboard";
import Reservations from "@/pages/Reservations";
import ReservationDetail from "@/pages/ReservationDetail";
import CalendarView from "@/pages/CalendarView";
import Settings from "@/pages/Settings";
import Socios from "@/pages/Socios";
import DatabasePage from "@/pages/DatabasePage";
import AppearancePage from "@/pages/AppearancePage";
import UpdatesPage from "@/pages/UpdatesPage";
import { Toaster } from "@/components/ui/toaster";
import { useEffect } from "react";
import { useNotifications } from "@/hooks/useNotifications";

function AnimatedRoutes() {
  const location = useLocation();
  const { pageTransition } = useSettings();

  const getVariants = () => {
    if (pageTransition === "slide") return {
      initial: { opacity: 0, x: 24 },
      animate: { opacity: 1, x: 0, transition: { duration: 0.3, ease: [0.22, 1, 0.36, 1] } },
      exit: { opacity: 0, x: -12, transition: { duration: 0.18 } },
    };
    if (pageTransition === "zoom") return {
      initial: { opacity: 0, scale: 0.96 },
      animate: { opacity: 1, scale: 1, transition: { duration: 0.3, ease: [0.22, 1, 0.36, 1] } },
      exit: { opacity: 0, scale: 1.02, transition: { duration: 0.18 } },
    };
    if (pageTransition === "none") return {
      initial: {}, animate: {}, exit: {},
    };
    // default: fade
    return {
      initial: { opacity: 0, y: 16, filter: "blur(4px)" },
      animate: { opacity: 1, y: 0, filter: "blur(0px)", transition: { duration: 0.35, ease: [0.22, 1, 0.36, 1] } },
      exit: { opacity: 0, y: -8, filter: "blur(4px)", transition: { duration: 0.2 } },
    };
  };

  return (
    <AnimatePresence mode="wait">
      <motion.div key={location.pathname} variants={getVariants()} initial="initial" animate="animate" exit="exit" style={{ minHeight: "100%" }}>
        <Routes location={location}>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/reservaciones" element={<Reservations />} />
          <Route path="/reservaciones/:id" element={<ReservationDetail />} />
          <Route path="/calendario" element={<CalendarView />} />
          <Route path="/ajustes" element={<Settings />} />
          <Route path="/socios" element={<Socios />} />
          <Route path="/base-de-datos" element={<DatabasePage />} />
          <Route path="/apariencia" element={<AppearancePage />} />
          <Route path="/actualizaciones" element={<UpdatesPage />} />
        </Routes>
      </motion.div>
    </AnimatePresence>
  );
}

// Inner component — has access to SettingsContext
function AppInner() {
  const { animations } = useSettings();
  const { start } = useNotifications();

  useEffect(() => {
    if ("Notification" in window && Notification.permission === "granted") {
      const saved = localStorage.getItem("cp_notif_enabled");
      if (saved !== "false") {
        // Sync saved settings from backend to localStorage keys the hook reads
        const reminderTime = localStorage.getItem("cp_reminder_time") || "09:00";
        const reminderDays = localStorage.getItem("cp_reminder_days") || "3";
        localStorage.setItem("cp_reminder_time", reminderTime);
        localStorage.setItem("cp_reminder_days", reminderDays);
        start(true);
      }
    }
  }, [start]);

  return (
    <MotionConfig reducedMotion={animations ? "never" : "always"}>
      <div className="App">
        <div className="mesh-bg" aria-hidden="true">
          <div className="blob blob-1" />
          <div className="blob blob-2" />
          <div className="blob blob-3" />
          <div className="blob blob-4" />
        </div>
        <BrowserRouter>
          <Layout>
            <AnimatedRoutes />
          </Layout>
        </BrowserRouter>
        <Toaster />
      </div>
    </MotionConfig>
  );
}

function App() {
  return (
    <SettingsProvider>
      <AppInner />
    </SettingsProvider>
  );
}

export default App;
