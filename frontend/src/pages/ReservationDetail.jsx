import { useEffect, useState, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { getReservation, updateReservation, uploadReceipt, deleteReceipt } from "@/lib/api";
import { ArrowLeft, Upload, Trash2, Edit2, X, ImageIcon, FileDown } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { useToast } from "@/hooks/use-toast";
import { useSettings } from "@/context/SettingsContext";
import ReservationForm from "@/components/ReservationForm";
import { generateReservationPDF } from "@/lib/generatePDF";
import LocationsSection from "@/components/LocationsSection";
import TeamSection from "@/components/TeamSection";
import { celebrateFullPayment, celebratePayment } from "@/lib/celebrations";

const STATUS_COLORS = {
  Pendiente: "bg-amber-100/80 text-amber-700 border-amber-200/60",
  Confirmado: "bg-blue-100/80 text-blue-700 border-blue-200/60",
  Completado: "bg-emerald-100/80 text-emerald-700 border-emerald-200/60",
  Cancelado:  "bg-red-100/80 text-red-700 border-red-200/60",
};
const STATUSES = ["Pendiente","Confirmado","Completado","Cancelado"];

export default function ReservationDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { toast } = useToast();
  const { tr, formatCurrency, logoUrl, pdfLogoUrl, usePdfLogo, useCustomPdfLogo, pdfTheme } = useSettings();
  const dt = tr.detail;
  const [reservation, setReservation] = useState(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [showEdit, setShowEdit] = useState(false);

  const getEffectivePdfLogo = () => {
    if (!usePdfLogo) return null;
    if (useCustomPdfLogo && pdfLogoUrl) return pdfLogoUrl;
    return logoUrl || undefined;
  };
  const [lightbox, setLightbox] = useState(null);
  const [dragOver, setDragOver] = useState(false);
  const fileRef = useRef();

  const load = async () => {
    setLoading(true);
    try { const data = await getReservation(id); setReservation(data); }
    catch { toast({ title: dt.toasts?.loadError || "Error", variant: "destructive" }); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); }, [id]);

  const formatDate = (d) => { if (!d) return "-"; const [y,m,day] = d.split("-"); return `${day}/${m}/${y}`; };

  const handleFileUpload = async (files) => {
    const allowed = ["image/jpeg","image/png","image/gif","image/webp","application/pdf"];
    for (const file of files) {
      if (!allowed.includes(file.type)) { toast({ title: "Tipo no soportado", variant: "destructive" }); continue; }
      setUploading(true);
      try { await uploadReceipt(id, file); toast({ title: dt.toasts?.uploadSuccess || "Comprobante subido" }); load(); }
      catch (e) { toast({ title: "Error al subir", description: e.response?.data?.detail || "Error", variant: "destructive" }); }
      finally { setUploading(false); }
    }
  };

  const handleDrop = (e) => { e.preventDefault(); setDragOver(false); handleFileUpload(Array.from(e.dataTransfer.files)); };

  const handleDeleteReceipt = async (receiptId) => {
    if (!window.confirm("¿Eliminar comprobante?")) return;
    try { await deleteReceipt(id, receiptId); toast({ title: "Eliminado" }); load(); }
    catch { toast({ title: "Error", variant: "destructive" }); }
  };

  const handleStatusChange = async (newStatus) => {
    try {
      const payload = { status: newStatus };
      const wasCompleted = reservation.status === "Completado";
      // Al marcar Completado → saldo = 0 (anticipo = total)
      if (newStatus === "Completado" && reservation.total_amount) {
        payload.advance_paid = reservation.total_amount;
      }
      const updated = await updateReservation(id, payload);
      setReservation(updated);
      toast({ title: `${tr.statuses[newStatus] || newStatus}` });
      // 🎉 Celebrar pago completo
      if (newStatus === "Completado" && !wasCompleted) {
        celebrateFullPayment();
      } else if (newStatus === "Confirmado" && reservation.status === "Pendiente") {
        celebratePayment();
      }
    }
    catch { toast({ title: "Error", variant: "destructive" }); }
  };

  if (loading) return (
    <div className="px-6 py-8 max-w-4xl mx-auto space-y-4">
      <div className="h-10 w-64 glass rounded-2xl animate-pulse" />
      <div className="h-56 glass rounded-3xl animate-pulse" />
    </div>
  );
  if (!reservation) return <div className="px-6 py-8 text-center text-slate-400 font-medium">No encontrado</div>;

  const remaining = (reservation.total_amount||0) - (reservation.advance_paid||0);
  const paidPct = reservation.total_amount > 0 ? Math.min(100, ((reservation.advance_paid||0)/reservation.total_amount)*100) : 0;

  return (
    <div className="px-6 py-8 max-w-4xl mx-auto">
      <motion.div initial={{ opacity:0, y:-16 }} animate={{ opacity:1, y:0 }} transition={{ duration:0.4 }} className="flex items-center gap-3 mb-7">
        <motion.button whileHover={{ scale:1.1, x:-2 }} whileTap={{ scale:0.9 }} onClick={() => navigate(-1)} className="p-2.5 rounded-2xl glass hover:bg-white/60 text-slate-600 transition-colors" data-testid="back-btn">
          <ArrowLeft size={16} />
        </motion.button>
        <div className="flex-1">
          <h1 className="text-4xl font-black text-slate-900 tracking-tight" style={{ fontFamily:'Cabinet Grotesk, sans-serif' }}>{reservation.client_name}</h1>
          <p className="text-sm text-slate-400 font-medium">{reservation.event_type}</p>
        </div>
        <div className="flex items-center gap-2">
          <select value={reservation.status} onChange={e => handleStatusChange(e.target.value)}
            className={`text-xs px-3 py-1.5 rounded-full border font-bold cursor-pointer focus:outline-none ${STATUS_COLORS[reservation.status]}`}
            data-testid="status-select">
            {STATUSES.map(s => <option key={s} value={s} className="bg-white">{tr.statuses[s]||s}</option>)}
          </select>
          <motion.button whileHover={{ scale:1.05 }} whileTap={{ scale:0.95 }} onClick={() => setShowEdit(true)} data-testid="edit-btn"
            className="flex items-center gap-1.5 px-4 py-2 rounded-full glass border-white/60 text-sm font-bold text-slate-700 hover:bg-white/60 transition-colors">
            <Edit2 size={13} /> {tr.common.edit}
          </motion.button>
          <motion.button whileHover={{ scale:1.05 }} whileTap={{ scale:0.95 }}
            onClick={async () => { try { await generateReservationPDF(reservation, formatCurrency, getEffectivePdfLogo(), pdfTheme); toast({ title: "PDF descargado" }); } catch { toast({ title: "Error al generar PDF", variant: "destructive" }); } }}
            data-testid="download-pdf-btn"
            className="flex items-center gap-1.5 px-4 py-2 rounded-full btn-primary text-white text-sm font-bold">
            <FileDown size={13} /> PDF
          </motion.button>
        </div>
      </motion.div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        <div className="md:col-span-2 space-y-5">
          <motion.div initial={{ opacity:0, y:20 }} animate={{ opacity:1, y:0 }} transition={{ delay:0.1 }} className="glass rounded-3xl p-6">
            <h2 className="text-xs font-black text-slate-500 uppercase tracking-widest mb-5">{dt.eventInfo}</h2>
            <dl className="grid grid-cols-2 gap-5">
              <InfoItem label={dt.eventDate} value={formatDate(reservation.event_date)} />
              {reservation.event_time && <InfoItem label={dt.time} value={reservation.event_time} />}
              {reservation.venue && <InfoItem label={dt.venue} value={reservation.venue} />}
              {reservation.guests_count && <InfoItem label={dt.guests} value={`${reservation.guests_count} ${dt.persons}`} />}
              {reservation.package_type && (
                <InfoItem label="Paquete" value={
                  <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold ${
                    reservation.package_type === "Básico" ? "bg-slate-100 text-slate-600" :
                    reservation.package_type === "Intermedio" ? "bg-indigo-100 text-indigo-700" :
                    "bg-amber-100 text-amber-700"
                  }`}>{reservation.package_type}</span>
                } />
              )}
              {reservation.client_phone && <InfoItem label={dt.phone} value={reservation.client_phone} />}
              {reservation.client_email && <InfoItem label={dt.email} value={reservation.client_email} />}
            </dl>
            {reservation.notes && (
              <div className="mt-5 pt-5 border-t border-white/40">
                <p className="text-xs font-black text-slate-400 uppercase tracking-widest mb-2">{dt.notes}</p>
                <p className="text-sm text-slate-700 leading-relaxed">{reservation.notes}</p>
              </div>
            )}
          </motion.div>

          <LocationsSection reservation={reservation} onUpdated={load} />

          <TeamSection reservation={reservation} onUpdated={load} />

          <motion.div initial={{ opacity:0, y:20 }} animate={{ opacity:1, y:0 }} transition={{ delay:0.2 }} className="glass rounded-3xl p-6">
            <h2 className="text-xs font-black text-slate-500 uppercase tracking-widest mb-5">{dt.receipts}</h2>

            <input ref={fileRef} type="file" accept="image/*,application/pdf" multiple className="hidden" data-testid="file-input" onChange={e => handleFileUpload(Array.from(e.target.files))} />

            {/* Sin imágenes: zona de arrastre grande */}
            {(!reservation.receipt_images || reservation.receipt_images.length === 0) && (
              <motion.div whileHover={{ scale:1.01 }}
                className={`border-2 border-dashed rounded-3xl p-10 text-center cursor-pointer transition-all duration-300 ${dragOver ? "border-indigo-400 bg-indigo-50/60 scale-[1.02]" : "border-indigo-200/60 bg-indigo-50/20 hover:bg-indigo-50/40 hover:border-indigo-300"}`}
                onDrop={handleDrop} onDragOver={e => { e.preventDefault(); setDragOver(true); }} onDragLeave={() => setDragOver(false)}
                onClick={() => fileRef.current?.click()} data-testid="upload-zone">
                <div className="w-14 h-14 rounded-2xl bg-indigo-100/80 flex items-center justify-center mx-auto mb-4">
                  <Upload size={24} className="text-indigo-500" />
                </div>
                <p className="text-base font-bold text-slate-600">{uploading ? dt.uploading : dt.uploadHint}</p>
                <p className="text-xs text-slate-400 mt-1.5">{dt.uploadSub}</p>
              </motion.div>
            )}

            {/* Con imágenes: mostrar en grande */}
            <AnimatePresence>
              {reservation.receipt_images && reservation.receipt_images.length > 0 && (
                <motion.div initial={{ opacity:0 }} animate={{ opacity:1 }} className="space-y-4" data-testid="receipts-grid"
                  onDrop={handleDrop} onDragOver={e => { e.preventDefault(); setDragOver(true); }} onDragLeave={() => setDragOver(false)}>
                  {reservation.receipt_images.map((img, i) => (
                    <motion.div key={img.id} initial={{ opacity:0, y:12 }} animate={{ opacity:1, y:0 }} transition={{ delay:i*0.07 }}
                      className="relative group rounded-3xl overflow-hidden bg-slate-900/5 border border-white/50"
                      style={{ boxShadow:"0 4px 24px rgba(0,0,0,0.08)" }}>
                      {img.content_type?.startsWith("image/") ? (
                        <>
                          <img
                            src={`data:${img.content_type};base64,${img.data}`}
                            alt={img.filename}
                            className="w-full object-contain cursor-zoom-in rounded-3xl"
                            style={{ maxHeight:"520px", minHeight:"200px", background:"#f8fafc" }}
                            onClick={() => setLightbox(img)}
                            data-testid={`receipt-img-${img.id}`}
                          />
                          {/* Overlay con nombre y acciones */}
                          <div className="absolute bottom-0 left-0 right-0 flex items-center justify-between px-4 py-3 rounded-b-3xl opacity-0 group-hover:opacity-100 transition-all duration-200"
                            style={{ background:"linear-gradient(0deg, rgba(15,23,42,0.6) 0%, transparent 100%)" }}>
                            <p className="text-xs font-semibold text-white/80 truncate">{img.filename}</p>
                            <motion.button whileHover={{ scale:1.1 }} whileTap={{ scale:0.9 }} onClick={() => handleDeleteReceipt(img.id)}
                              className="p-2 rounded-full bg-white/20 hover:bg-red-500 text-white transition-colors flex-shrink-0"
                              data-testid={`delete-receipt-${img.id}`}><Trash2 size={13} /></motion.button>
                          </div>
                        </>
                      ) : (
                        <div className="flex flex-col items-center gap-3 py-12 cursor-pointer" onClick={() => setLightbox(img)}>
                          <ImageIcon size={40} className="text-slate-400" />
                          <p className="text-sm text-slate-500 font-medium px-4">{img.filename}</p>
                        </div>
                      )}
                    </motion.div>
                  ))}

                  {/* Botón subir otra imagen */}
                  <motion.button whileHover={{ scale:1.02 }} whileTap={{ scale:0.98 }}
                    onClick={() => fileRef.current?.click()}
                    disabled={uploading}
                    data-testid="upload-another-btn"
                    className={`w-full flex items-center justify-center gap-2.5 py-3.5 rounded-2xl border-2 border-dashed text-sm font-bold transition-all duration-200 ${dragOver ? "border-indigo-400 bg-indigo-50/60" : "border-indigo-200/70 bg-indigo-50/20 text-indigo-500 hover:bg-indigo-50/50 hover:border-indigo-400"}`}>
                    <Upload size={16} />
                    {uploading ? (dt.uploading || "Subiendo…") : "Subir otra imagen"}
                  </motion.button>
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>
        </div>

        <div className="space-y-5">
          <motion.div initial={{ opacity:0, y:20 }} animate={{ opacity:1, y:0 }} transition={{ delay:0.15 }} className="glass rounded-3xl p-6">
            <h2 className="text-xs font-black text-slate-500 uppercase tracking-widest mb-5">{dt.paymentSummary}</h2>
            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <span className="text-sm text-slate-500 font-medium">{dt.totalLabel}</span>
                <span className="text-sm font-black text-slate-900">{formatCurrency(reservation.total_amount)}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm text-slate-500 font-medium">{dt.advancePaid}</span>
                <span className="text-sm font-black text-emerald-600">{formatCurrency(reservation.advance_paid)}</span>
              </div>
              <div className="pt-3 border-t border-white/40">
                <div className="flex justify-between items-center mb-3">
                  <span className="text-sm font-bold text-slate-700">{dt.pendingBalance}</span>
                  <span className={`text-sm font-black ${remaining > 0 ? "text-amber-600" : "text-emerald-600"}`}>{formatCurrency(remaining)}</span>
                </div>
                <div className="w-full h-2.5 bg-slate-100 rounded-full overflow-hidden">
                  <motion.div initial={{ width:0 }} animate={{ width:`${paidPct}%` }} transition={{ duration:0.8, ease:"easeOut", delay:0.3 }} className="h-full rounded-full theme-progress" data-testid="payment-progress" />
                </div>
                <p className="text-xs text-slate-400 mt-1.5 font-medium">{Math.round(paidPct)}% {dt.paid}</p>
              </div>
            </div>
          </motion.div>

          <motion.div initial={{ opacity:0, y:20 }} animate={{ opacity:1, y:0 }} transition={{ delay:0.2 }} className="glass rounded-3xl p-6">
            <h2 className="text-xs font-black text-slate-500 uppercase tracking-widest mb-4">{dt.receiptsCount}</h2>
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-2xl flex items-center justify-center" style={{ backgroundColor:"color-mix(in srgb, var(--t-from) 12%, white)" }}>
                <ImageIcon size={15} style={{ color:"var(--t-from)" }} />
              </div>
              <div>
                <p className="text-sm font-bold text-slate-900">{(reservation.receipt_images||[]).length}</p>
                <p className="text-xs text-slate-400">{dt.filesUploaded}</p>
              </div>
            </div>
          </motion.div>
        </div>
      </div>

      <AnimatePresence>
        {lightbox && (
          <motion.div initial={{ opacity:0 }} animate={{ opacity:1 }} exit={{ opacity:0 }}
            className="fixed inset-0 z-50 flex items-center justify-center p-6"
            style={{ backdropFilter:"blur(20px)", backgroundColor:"rgba(15,23,42,0.7)" }}
            onClick={() => setLightbox(null)} data-testid="lightbox">
            <motion.button whileHover={{ scale:1.1 }} className="absolute top-6 right-6 p-2.5 rounded-full glass text-white" onClick={() => setLightbox(null)}><X size={20} /></motion.button>
            {lightbox.content_type?.startsWith("image/") ? (
              <motion.img initial={{ scale:0.8, opacity:0 }} animate={{ scale:1, opacity:1 }}
                src={`data:${lightbox.content_type};base64,${lightbox.data}`} alt={lightbox.filename}
                className="max-w-full max-h-[85vh] object-contain rounded-3xl shadow-2xl" onClick={e => e.stopPropagation()} />
            ) : (
              <motion.div initial={{ scale:0.8 }} animate={{ scale:1 }} className="glass-modal rounded-3xl p-10 text-center">
                <ImageIcon size={48} className="mx-auto text-slate-400 mb-3" /><p className="text-slate-700 font-bold">{lightbox.filename}</p>
              </motion.div>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {showEdit && <ReservationForm reservation={reservation} onClose={() => setShowEdit(false)} onSaved={() => { setShowEdit(false); load(); }} />}
    </div>
  );
}

function InfoItem({ label, value }) {
  return (
    <div>
      <dt className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-1">{label}</dt>
      <dd className="text-sm font-bold text-slate-900">{value}</dd>
    </div>
  );
}
