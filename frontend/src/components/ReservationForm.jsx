import { useState, useEffect } from "react";
import { createReservation, updateReservation } from "@/lib/api";
import { ArrowLeft, X } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { useToast } from "@/hooks/use-toast";
import { useSettings } from "@/context/SettingsContext";
import { getEventTypeName } from "@/lib/eventConfig";
import { FORM_DESIGN_CONFIGS } from "@/lib/formDesigns";
import { celebrateReservation, celebratePayment, celebrateFullPayment } from "@/lib/celebrations";

const EVENT_TYPES = ["Boda","Quinceañera","Fiesta Social","Evento Corporativo","Conferencia","Otro"];

export default function ReservationForm({ reservation, onClose, onSaved }) {
  const { toast } = useToast();
  const { tr, activeStatuses, formFieldsVisibility, reservationFormDesign } = useSettings();
  const f = tr.form;
  const ff = formFieldsVisibility || {};
  const dc = FORM_DESIGN_CONFIGS[reservationFormDesign] || FORM_DESIGN_CONFIGS.aurora;
  const isEdit = !!reservation;

  const [form, setForm] = useState({
    client_name:"Desconocido", client_phone:"", client_email:"",
    event_type:"Boda", event_date:"", event_time:"",
    venue:"", guests_count:"", total_amount:"",
    advance_paid:"0", status:"Pendiente", notes:"",
    package_type: "",
  });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (reservation) setForm({
      client_name: reservation.client_name||"",
      client_phone: reservation.client_phone||"",
      client_email: reservation.client_email||"",
      event_type: reservation.event_type||"Boda",
      event_date: reservation.event_date||"",
      event_time: reservation.event_time||"",
      venue: reservation.venue||"",
      guests_count: reservation.guests_count||"",
      total_amount: reservation.total_amount||"",
      advance_paid: reservation.advance_paid||"0",
      status: reservation.status||"Pendiente",
      notes: reservation.notes||"",
      package_type: reservation.package_type||"",
    });
  }, [reservation]);

  const set = (field) => (e) => setForm(p => ({ ...p, [field]: e.target.value }));

  // Al cambiar a "Completado" → auto-llenar anticipo = total (saldo = 0)
  const setStatus = (e) => {
    const newStatus = e.target.value;
    setForm(prev => ({
      ...prev,
      status: newStatus,
      advance_paid: newStatus === "Completado"
        ? String(prev.total_amount || prev.advance_paid)
        : prev.advance_paid,
    }));
  };

  const handleSubmit = async (e) => {
    if (e && e.preventDefault) e.preventDefault();
    if (!form.client_name.trim()) { toast({ title:"Nombre requerido", variant:"destructive" }); return; }
    if (!form.event_date)         { toast({ title:"Fecha requerida",  variant:"destructive" }); return; }
    if (!form.total_amount || isNaN(Number(form.total_amount))) {
      toast({ title:"Monto inválido", variant:"destructive" }); return;
    }
    setSaving(true);
    const payload = {
      ...form,
      guests_count: form.guests_count ? parseInt(form.guests_count) : null,
      total_amount: parseFloat(form.total_amount),
      advance_paid: parseFloat(form.advance_paid) || 0,
    };
    try {
      if (isEdit) {
        await updateReservation(reservation.id, payload);
        toast({ title:"Reserva actualizada" });
        // Celebrar si aumentó el pago (nuevo anticipo > anticipo previo)
        const prevAdvance = parseFloat(reservation.advance_paid || 0);
        const newAdvance = payload.advance_paid || 0;
        if (newAdvance > prevAdvance) {
          const total = payload.total_amount || 0;
          if (newAdvance >= total) celebrateFullPayment();
          else celebratePayment();
        }
      } else {
        await createReservation(payload);
        toast({ title:"🎉 ¡Reserva creada!" });
        celebrateReservation();
      }
      onSaved();
    } catch (err) {
      toast({ title:"Error al guardar", description:err.response?.data?.detail||"Error", variant:"destructive" });
    } finally { setSaving(false); }
  };

  const inp = dc.inp;
  const sel = `${dc.inp} cursor-pointer`;
  const lbl = dc.labelClass;
  const ls  = dc.labelStyle;
  const title = isEdit ? "Editar Reserva" : "Nueva Reserva";
  const submitLabel = saving ? "Guardando…" : isEdit ? "Guardar cambios" : "Crear reserva";

  // ── Campos del formulario (JSX inlineado — sin sub-componentes para evitar re-mount) ──
  const formFields = (
    <div className="space-y-4">

      {/* Fila 1 — Cliente */}
      <div className="flex flex-wrap gap-3">
        <div className="flex-[2] min-w-[180px]">
          <label className={lbl} style={ls}>{f.clientName} *</label>
          <input value={form.client_name} onChange={set("client_name")} placeholder="Ej: María García" required
            data-testid="input-client-name" className={inp} style={dc.inpStyle}/>
        </div>
        {ff.phone !== false && (
          <div className="flex-1 min-w-[140px]">
            <label className={lbl} style={ls}>{f.phone}</label>
            <input value={form.client_phone} onChange={set("client_phone")} placeholder="+502 1234…"
              data-testid="input-phone" className={inp} style={dc.inpStyle}/>
          </div>
        )}
        {ff.email !== false && (
          <div className="flex-1 min-w-[150px]">
            <label className={lbl} style={ls}>{f.email}</label>
            <input type="email" value={form.client_email} onChange={set("client_email")} placeholder="correo@email.com"
              data-testid="input-email" className={inp} style={dc.inpStyle}/>
          </div>
        )}
      </div>

      {/* Fila 2 — Evento */}
      <div className="flex flex-wrap gap-3">
        <div className="flex-1 min-w-[140px]">
          <label className={lbl} style={ls}>{f.eventType}</label>
          <select value={form.event_type} onChange={set("event_type")} required
            data-testid="input-event-type" className={sel} style={dc.inpStyle}>
            {EVENT_TYPES.map(t => <option key={t} value={t} className="bg-white text-slate-800">{getEventTypeName(t)}</option>)}
          </select>
        </div>
        <div className="flex-1 min-w-[130px]">
          <label className={lbl} style={ls}>{f.status}</label>
          <select value={form.status} onChange={setStatus}
            data-testid="input-status" className={sel} style={dc.inpStyle}>
            {activeStatuses.map(s => <option key={s.key} value={s.key} className="bg-white text-slate-800">{s.label}</option>)}
          </select>
        </div>
        <div className="flex-1 min-w-[140px]">
          <label className={lbl} style={ls}>{f.eventDate} *</label>
          <input type="date" value={form.event_date} onChange={set("event_date")} required
            data-testid="input-event-date" className={inp} style={dc.inpStyle}/>
        </div>
        {ff.time !== false && (
          <div className="flex-1 min-w-[110px]">
            <label className={lbl} style={ls}>{f.time}</label>
            <input type="time" value={form.event_time} onChange={set("event_time")}
              data-testid="input-event-time" className={inp} style={dc.inpStyle}/>
          </div>
        )}
      </div>

      {/* Fila 3 — Lugar / Invitados / Total */}
      <div className="flex flex-wrap gap-3">
        {ff.venue !== false && (
          <div className="flex-[2] min-w-[180px]">
            <label className={lbl} style={ls}>{f.venue}</label>
            <input value={form.venue} onChange={set("venue")} placeholder="Salón / Hotel…"
              data-testid="input-venue" className={inp} style={dc.inpStyle}/>
          </div>
        )}
        {ff.guests !== false && (
          <div className="flex-1 min-w-[110px]">
            <label className={lbl} style={ls}>{f.guests}</label>
            <input type="number" value={form.guests_count} onChange={set("guests_count")} placeholder="150" min="0"
              data-testid="input-guests" className={inp} style={dc.inpStyle}/>
          </div>
        )}
        <div className="flex-1 min-w-[130px]">
          <label className={lbl} style={ls}>{f.totalAmount} *</label>
          <input type="number" value={form.total_amount} onChange={set("total_amount")} placeholder="50,000" min="0" step="0.01" required
            data-testid="input-total" className={inp} style={dc.inpStyle}/>
        </div>
      </div>

      {/* Fila 4 — Anticipo / Paquete / Notas */}
      {(ff.advance !== false || ff.package !== false || ff.notes !== false) && (
        <div className="flex flex-wrap gap-3">
          {ff.advance !== false && (
            <div className="flex-1 min-w-[130px]">
              <label className={lbl} style={ls}>{f.advancePaid}</label>
              <input type="number" value={form.advance_paid} onChange={set("advance_paid")} placeholder="10,000" min="0" step="0.01"
                data-testid="input-advance" className={inp} style={dc.inpStyle}/>
            </div>
          )}
          {ff.package !== false && (
            <div className="flex-1 min-w-[150px]">
              <label className={lbl} style={ls}>{f.package || "Paquete"}</label>
              <select value={form.package_type} onChange={set("package_type")}
                data-testid="input-package" className={sel} style={dc.inpStyle}>
                <option value="">— Sin paquete —</option>
                <option value="Básico">Básico</option>
                <option value="Intermedio">Intermedio</option>
                <option value="Completo">Completo</option>
              </select>
            </div>
          )}
          {ff.notes !== false && (
            <div className="flex-[3] min-w-[200px]">
              <label className={lbl} style={ls}>{f.notes}</label>
              <input value={form.notes} onChange={set("notes")} placeholder="Detalles especiales, temas, requerimientos…"
                data-testid="input-notes" className={inp} style={dc.inpStyle}/>
            </div>
          )}
        </div>
      )}
    </div>
  );

  // ── FLOATING LAYOUT ───────────────────────────────────────────────────────
  if (dc.layout === "floating") {
    return (
      <AnimatePresence>
        <motion.div
          key="overlay"
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
          className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto py-8 px-4"
          style={{ background: dc.overlayBg, backdropFilter: dc.overlayBlur }}
          onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
          data-testid="reservation-form"
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 24 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95 }}
            transition={{ duration: 0.28, ease: [0.22,1,0.36,1] }}
            className={`w-full ${dc.cardMaxWidth||"max-w-3xl"} ${dc.cardRadius||"rounded-3xl"} overflow-hidden ${dc.cardShadow||"shadow-2xl"} my-auto`}
            style={{ background: dc.cardBg, backdropFilter: dc.cardBackdrop||"none", WebkitBackdropFilter: dc.cardBackdrop||"none", isolation:"isolate" }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Accent bar */}
            {dc.accentBar && (
              <div className="flex items-center gap-3 px-6 py-3.5" style={{ background: dc.accentBar }}>
                <button type="button" onClick={onClose} data-testid="cancel-form-btn"
                  className={`flex items-center gap-1.5 text-sm font-bold px-3 py-1.5 rounded-full transition-all ${dc.cancelClass}`}>
                  <ArrowLeft size={13}/>
                </button>
                <h2 className={`flex-1 text-base font-black ${dc.titleClass}`} style={{ fontFamily:"Cabinet Grotesk, sans-serif" }}>
                  {title}
                </h2>
                <motion.button whileHover={{ scale:1.03 }} whileTap={{ scale:0.97 }} type="button" onClick={handleSubmit}
                  disabled={saving}
                  className="px-5 py-2 rounded-full bg-white/20 border border-white/30 text-white font-bold text-sm disabled:opacity-60 hover:bg-white/30 transition-all"
                  data-testid="submit-form-btn">
                  {submitLabel}
                </motion.button>
              </div>
            )}
            {/* Top bar (no accent) */}
            {!dc.accentBar && (
              <div className={`flex items-center justify-between px-6 py-4 border-b ${dc.barClass}`}>
                <div className="flex items-center gap-3">
                  <button type="button" onClick={onClose} data-testid="cancel-form-btn"
                    className={`flex items-center gap-1.5 text-sm font-bold px-3 py-2 rounded-full transition-all ${dc.cancelClass}`}>
                    <ArrowLeft size={13}/> Cancelar
                  </button>
                  <h2 className={`text-lg font-black ${dc.titleClass}`} style={{ fontFamily:"Cabinet Grotesk, sans-serif" }}>
                    {title}
                  </h2>
                </div>
                <div className="flex items-center gap-2">
                  <motion.button whileHover={{ scale:1.03 }} whileTap={{ scale:0.97 }} type="button" onClick={handleSubmit}
                    disabled={saving}
                    className="px-6 py-2.5 rounded-full btn-primary text-white font-bold text-sm disabled:opacity-60 shadow-md"
                    data-testid="submit-form-btn">
                    {submitLabel}
                  </motion.button>
                  <button type="button" onClick={onClose}
                    className={`w-9 h-9 rounded-full flex items-center justify-center transition-all ${dc.cancelClass}`}>
                    <X size={15}/>
                  </button>
                </div>
              </div>
            )}
            <form onSubmit={handleSubmit} className="px-6 py-5">
              {formFields}
            </form>
          </motion.div>
        </motion.div>
      </AnimatePresence>
    );
  }

  // ── FULLSCREEN LAYOUT ─────────────────────────────────────────────────────
  return (
    <motion.div
      initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 20 }} transition={{ duration: 0.3, ease: [0.22,1,0.36,1] }}
      className="fixed inset-0 z-50 flex flex-col"
      style={{ background: dc.containerBg, backdropFilter:"blur(20px)" }}
      data-testid="reservation-form"
    >
      <div className={`flex-shrink-0 flex items-center justify-between px-10 py-5 border-b ${dc.barClass}`}>
        <div className="flex items-center gap-4">
          <motion.button whileHover={{ scale:1.05 }} whileTap={{ scale:0.95 }} type="button" onClick={onClose}
            className={`flex items-center gap-2 px-4 py-2.5 rounded-full font-bold text-sm transition-colors ${dc.cancelClass}`}
            data-testid="cancel-form-btn">
            <ArrowLeft size={16}/> Cancelar
          </motion.button>
          <h1 className={`text-2xl font-black ${dc.titleClass}`} style={{ fontFamily:"Cabinet Grotesk, sans-serif" }}>
            {title}
          </h1>
        </div>
        <motion.button whileHover={{ scale:1.03 }} whileTap={{ scale:0.97 }} type="button" onClick={handleSubmit}
          disabled={saving}
          className="px-8 py-3 rounded-full btn-primary text-white font-bold text-base disabled:opacity-60 shadow-lg"
          data-testid="submit-form-btn">
          {submitLabel}
        </motion.button>
      </div>
      <form onSubmit={handleSubmit} className="flex-1 flex flex-col justify-center px-10 py-8">
        <div className="w-full max-w-5xl mx-auto">
          {formFields}
        </div>
      </form>
    </motion.div>
  );
}
