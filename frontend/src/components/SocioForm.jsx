import { useState, useEffect } from "react";
import { createSocio, updateSocio, uploadSocioPhoto } from "@/lib/api";
import { ArrowLeft, Camera, Upload, X } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { useToast } from "@/hooks/use-toast";
import { useSettings } from "@/context/SettingsContext";
import { FORM_DESIGN_CONFIGS } from "@/lib/formDesigns";
import { celebrateSocio } from "@/lib/celebrations";

const ROLES = ["Fotógrafo", "Videógrafo", "Asistente"];

export default function SocioForm({ socio, onClose, onSaved }) {
  const { toast } = useToast();
  const { socioFieldsVisibility, socioFormDesign } = useSettings();
  const sf = socioFieldsVisibility || {};
  const dc = FORM_DESIGN_CONFIGS[socioFormDesign] || FORM_DESIGN_CONFIGS.aurora;
  const isEdit = !!socio;

  const [saving, setSaving]             = useState(false);
  const [photoPreview, setPhotoPreview] = useState(null);
  const [photoFile, setPhotoFile]       = useState(null);
  const [form, setForm] = useState({
    name:"", role:"Fotógrafo", phone:"", email:"", notes:"", rate_per_event:"",
  });

  useEffect(() => {
    if (socio) {
      setForm({ name:socio.name||"", role:socio.role||"Fotógrafo", phone:socio.phone||"", email:socio.email||"", notes:socio.notes||"", rate_per_event:socio.rate_per_event||"" });
      if (socio.photo && socio.photo_content_type)
        setPhotoPreview(`data:${socio.photo_content_type};base64,${socio.photo}`);
    }
  }, [socio]);

  const set = (field) => (e) => setForm(p => ({ ...p, [field]: e.target.value }));

  const handlePhotoChange = (e) => {
    const file = e.target.files[0];
    if (!file) return;
    setPhotoFile(file);
    const reader = new FileReader();
    reader.onloadend = () => setPhotoPreview(reader.result);
    reader.readAsDataURL(file);
  };

  const handleSubmit = async (e) => {
    if (e && e.preventDefault) e.preventDefault();
    if (!form.name.trim()) { toast({ title:"Nombre requerido", variant:"destructive" }); return; }
    setSaving(true);
    try {
      const payload = {
        name: form.name.trim(), role: form.role,
        phone: form.phone||null, email: form.email||null, notes: form.notes||null,
        rate_per_event: form.rate_per_event !== "" && form.rate_per_event !== null ? parseFloat(form.rate_per_event) : null,
      };
      let saved;
      if (isEdit) saved = await updateSocio(socio.id, payload);
      else        saved = await createSocio(payload);
      if (photoFile) await uploadSocioPhoto(saved.id, photoFile);
      if (isEdit) {
        toast({ title: "Socio actualizado" });
      } else {
        toast({ title: "🎉 ¡Socio agregado al equipo!" });
        celebrateSocio();
      }
      onSaved();
    } catch (err) {
      toast({ title:"Error al guardar", description:err.response?.data?.detail||err.message||"Error", variant:"destructive" });
    } finally { setSaving(false); }
  };

  const inp = dc.inp;
  const lbl = dc.labelClass;
  const ls  = dc.labelStyle;
  const title = isEdit ? "Editar Socio" : "Nuevo Socio";
  const submitLabel = saving ? "Guardando…" : isEdit ? "Guardar cambios" : "Crear socio";

  // ── Bloque de foto (JSX inlineado — no sub-componente) ────────────────────
  const photoBlock = sf.photo !== false ? (
    <div className="flex-shrink-0 flex flex-col items-center gap-3">
      <label className="relative cursor-pointer group">
        <div className="w-32 h-32 rounded-2xl overflow-hidden ring-4 ring-white/40 shadow-lg">
          {photoPreview
            ? <img src={photoPreview} alt="foto" className="w-full h-full object-cover"/>
            : <div className="w-full h-full btn-primary flex flex-col items-center justify-center gap-1.5">
                <Camera size={32} className="text-white/80"/>
                <span className="text-white/70 text-[10px] font-bold">Foto</span>
              </div>}
        </div>
        <div className="absolute bottom-1.5 right-1.5 w-7 h-7 rounded-full btn-primary flex items-center justify-center ring-2 ring-white opacity-0 group-hover:opacity-100 transition-opacity shadow">
          <Upload size={12} className="text-white"/>
        </div>
        <input type="file" accept="image/*" className="hidden" onChange={handlePhotoChange} data-testid="socio-photo-input"/>
      </label>
      <p className={`text-[9px] font-bold text-center ${dc.isDark ? "text-white/40" : "text-slate-400"}`}>Foto opcional</p>
    </div>
  ) : null;

  // ── Campos del socio (inlineados) ─────────────────────────────────────────
  const socioFields = (
    <div className="flex gap-6 items-start">
      {photoBlock}
      <div className="flex-1 space-y-3">
        {/* Nombre */}
        <div>
          <label className={lbl} style={ls}>Nombre completo *</label>
          <input value={form.name} onChange={set("name")} placeholder="Ej: Carlos Pérez" required
            data-testid="input-socio-name" className={inp} style={dc.inpStyle}/>
        </div>
        {/* Rol */}
        <div>
          <label className={lbl} style={ls}>Rol *</label>
          <div className="grid grid-cols-3 gap-2">
            {ROLES.map(r => (
              <motion.button key={r} type="button" whileHover={{ scale:1.02 }} whileTap={{ scale:0.97 }}
                onClick={() => setForm(p => ({ ...p, role:r }))}
                className={`py-3 rounded-xl text-xs font-bold transition-all ${form.role===r ? "btn-primary text-white shadow-md" : dc.isDark ? "bg-white/10 border border-white/20 text-white/80 hover:bg-white/15" : "bg-white border border-slate-200 text-slate-600 hover:bg-slate-50"}`}
                data-testid={`role-${r.toLowerCase()}`}>
                {r==="Fotógrafo"?"📷":r==="Videógrafo"?"🎥":"👤"} {r}
              </motion.button>
            ))}
          </div>
        </div>
        {/* Phone + Rate + Email */}
        <div className="flex flex-wrap gap-3">
          {sf.phone !== false && (
            <div className="flex-1 min-w-[120px]">
              <label className={lbl} style={ls}>Teléfono</label>
              <input value={form.phone} onChange={set("phone")} placeholder="+502…"
                data-testid="input-socio-phone" className={inp} style={dc.inpStyle}/>
            </div>
          )}
          {sf.rate !== false && (
            <div className="flex-1 min-w-[110px]">
              <label className={lbl} style={ls}>Tarifa</label>
              <input type="number" value={form.rate_per_event} onChange={set("rate_per_event")} placeholder="Q 2,000" min="0"
                data-testid="input-socio-rate" className={inp} style={dc.inpStyle}/>
            </div>
          )}
          {sf.email !== false && (
            <div className="flex-1 min-w-[130px]">
              <label className={lbl} style={ls}>Email</label>
              <input type="email" value={form.email} onChange={set("email")} placeholder="correo@…"
                data-testid="input-socio-email" className={inp} style={dc.inpStyle}/>
            </div>
          )}
        </div>
        {/* Notes */}
        {sf.notes !== false && (
          <div>
            <label className={lbl} style={ls}>Notas</label>
            <input value={form.notes} onChange={set("notes")} placeholder="Especialidades, equipo, disponibilidad…"
              data-testid="input-socio-notes" className={inp} style={dc.inpStyle}/>
          </div>
        )}
      </div>
    </div>
  );

  // ── FLOATING LAYOUT ───────────────────────────────────────────────────────
  if (dc.layout === "floating") {
    return (
      <AnimatePresence>
        <motion.div
          key="overlay"
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
          transition={{ duration: 0.22 }}
          className="fixed inset-0 z-50 flex items-center justify-center px-4"
          style={{ background: dc.overlayBg, backdropFilter: dc.overlayBlur }}
          onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
          data-testid="socio-form"
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.94, y: 28 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.94, y: 16 }}
            transition={{ duration: 0.3, ease: [0.22,1,0.36,1] }}
            className={`w-full ${dc.cardMaxWidth||"max-w-2xl"} ${dc.cardRadius||"rounded-3xl"} overflow-hidden ${dc.cardShadow||"shadow-2xl"}`}
            style={{ background: dc.cardBg, backdropFilter: dc.cardBackdrop||"none", WebkitBackdropFilter: dc.cardBackdrop||"none", isolation:"isolate" }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Accent bar */}
            {dc.accentBar && (
              <div className="flex items-center gap-3 px-6 py-3.5" style={{ background: dc.accentBar }}>
                <button type="button" onClick={onClose} data-testid="cancel-socio-btn"
                  className={`flex items-center gap-1.5 text-sm font-bold px-3 py-1.5 rounded-full transition-all ${dc.cancelClass}`}>
                  <ArrowLeft size={13}/>
                </button>
                <h2 className={`flex-1 text-base font-black ${dc.titleClass}`} style={{ fontFamily:"Cabinet Grotesk, sans-serif" }}>
                  {title}
                </h2>
                <motion.button whileHover={{ scale:1.03 }} whileTap={{ scale:0.97 }} type="button" onClick={handleSubmit}
                  disabled={saving}
                  className="px-5 py-2 rounded-full bg-white/20 border border-white/30 text-white font-bold text-sm disabled:opacity-60 hover:bg-white/30"
                  data-testid="submit-socio-btn">
                  {submitLabel}
                </motion.button>
              </div>
            )}
            {/* Top bar (no accent) */}
            {!dc.accentBar && (
              <div className={`flex items-center justify-between px-6 py-4 border-b ${dc.barClass}`}>
                <div className="flex items-center gap-3">
                  <button type="button" onClick={onClose} data-testid="cancel-socio-btn"
                    className={`flex items-center gap-1.5 text-sm font-bold px-3 py-2 rounded-full transition-all ${dc.cancelClass}`}>
                    <ArrowLeft size={13}/> Cerrar
                  </button>
                  <h2 className={`text-lg font-black ${dc.titleClass}`} style={{ fontFamily:"Cabinet Grotesk, sans-serif" }}>
                    {title}
                  </h2>
                </div>
                <div className="flex items-center gap-2">
                  <motion.button whileHover={{ scale:1.03 }} whileTap={{ scale:0.97 }} type="button" onClick={handleSubmit}
                    disabled={saving}
                    className="px-6 py-2.5 rounded-full btn-primary text-white font-bold text-sm disabled:opacity-60 shadow-md"
                    data-testid="submit-socio-btn">
                    {submitLabel}
                  </motion.button>
                  <button type="button" onClick={onClose}
                    className={`w-9 h-9 rounded-full flex items-center justify-center transition-all ${dc.cancelClass}`}>
                    <X size={16}/>
                  </button>
                </div>
              </div>
            )}
            <form onSubmit={handleSubmit} className="px-6 py-5">
              {socioFields}
            </form>
          </motion.div>
        </motion.div>
      </AnimatePresence>
    );
  }

  // ── FULLSCREEN LAYOUT ─────────────────────────────────────────────────────
  return (
    <motion.div
      initial={{ opacity:0, y:30 }} animate={{ opacity:1, y:0 }}
      exit={{ opacity:0, y:20 }} transition={{ duration:0.3, ease:[0.22,1,0.36,1] }}
      className="fixed inset-0 z-50 flex flex-col"
      style={{ background: dc.containerBg, backdropFilter:"blur(20px)" }}
      data-testid="socio-form"
    >
      <div className={`flex-shrink-0 flex items-center justify-between px-10 py-5 border-b ${dc.barClass}`}>
        <div className="flex items-center gap-4">
          <motion.button whileHover={{ scale:1.05 }} whileTap={{ scale:0.95 }} type="button" onClick={onClose}
            className={`flex items-center gap-2 px-4 py-2.5 rounded-full font-bold text-sm transition-colors ${dc.cancelClass}`}
            data-testid="cancel-socio-btn">
            <ArrowLeft size={16}/> Cancelar
          </motion.button>
          <h1 className={`text-2xl font-black ${dc.titleClass}`} style={{ fontFamily:"Cabinet Grotesk, sans-serif" }}>
            {title}
          </h1>
        </div>
        <motion.button whileHover={{ scale:1.03 }} whileTap={{ scale:0.97 }} type="button" onClick={handleSubmit}
          disabled={saving}
          className="px-8 py-3 rounded-full btn-primary text-white font-bold text-base disabled:opacity-60 shadow-lg"
          data-testid="submit-socio-btn">
          {submitLabel}
        </motion.button>
      </div>
      <form onSubmit={handleSubmit} className="flex-1 flex items-center justify-center px-10 py-8">
        <div className="w-full max-w-3xl">
          {socioFields}
        </div>
      </form>
    </motion.div>
  );
}
