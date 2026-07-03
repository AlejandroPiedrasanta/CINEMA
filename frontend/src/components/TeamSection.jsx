import { useState, useEffect } from "react";
import { getSocios, getSocio, updateReservation } from "@/lib/api";
import { celebratePayment } from "@/lib/celebrations";
import { Users, Plus, X, Camera, Video, CheckCircle, Clock } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { useToast } from "@/hooks/use-toast";
import { useSettings } from "@/context/SettingsContext";

const ROLE_ICONS = { "Fotógrafo": Camera, "Videógrafo": Video, "Asistente": Users };
const ROLE_COLORS = {
  "Fotógrafo": "bg-indigo-100/80 text-indigo-700 border-indigo-200/60",
  "Videógrafo": "bg-purple-100/80 text-purple-700 border-purple-200/60",
  "Asistente":  "bg-slate-100/80 text-slate-700 border-slate-200/60",
};

function SocioAvatar({ socio, size = "sm" }) {
  const sz = size === "sm" ? "w-7 h-7 text-[10px]" : "w-9 h-9 text-xs";
  if (socio.photo && socio.photo_content_type) {
    return <img src={`data:${socio.photo_content_type};base64,${socio.photo}`} alt={socio.name} className={`${sz} rounded-full object-cover ring-2 ring-white/60`} />;
  }
  return (
    <div className={`${sz} rounded-full flex items-center justify-center font-black btn-primary text-white ring-2 ring-white/60`}>
      {socio.name?.charAt(0).toUpperCase()}
    </div>
  );
}

export default function TeamSection({ reservation, onUpdated }) {
  const { toast } = useToast();
  const { formatCurrency } = useSettings();
  const [socios, setSocios] = useState([]);
  const [selectedSocio, setSelectedSocio] = useState("");
  const [payment, setPayment] = useState("");
  const [adding, setAdding] = useState(false);
  const partners = reservation.assigned_partners || [];

  useEffect(() => {
    getSocios().then(data => {
      const assignedIds = partners.map(p => p.socio_id);
      setSocios(data.filter(s => !assignedIds.includes(s.id)));
    }).catch(console.error);
  }, [reservation]);

  const teamCost = partners.reduce((sum, p) => sum + (p.payment || 0), 0);
  const paidToTeam = partners.filter(p => p.payment_status === "Pagado").reduce((sum, p) => sum + (p.payment || 0), 0);
  const pendingToTeam = teamCost - paidToTeam;
  const realIncome = (reservation.total_amount || 0) - teamCost;

  const handleAdd = async () => {
    if (!selectedSocio) { toast({ title: "Selecciona un socio", variant: "destructive" }); return; }
    setAdding(true);
    try {
      const socio = await getSocio(selectedSocio);
      const newPartner = {
        socio_id: socio.id,
        name: socio.name,
        role: socio.role,
        photo: socio.photo || null,
        photo_content_type: socio.photo_content_type || null,
        payment: parseFloat(payment) || 0,
        payment_status: "Pendiente",
      };
      const updatedPartners = [...partners, newPartner];
      await updateReservation(reservation.id, { assigned_partners: updatedPartners });
      toast({ title: `${socio.name} asignado` });
      setSelectedSocio(""); setPayment("");
      onUpdated?.();
    } catch {
      toast({ title: "Error al asignar", variant: "destructive" });
    } finally { setAdding(false); }
  };

  const handleRemove = async (socioId) => {
    const updatedPartners = partners.filter(p => p.socio_id !== socioId);
    try {
      await updateReservation(reservation.id, { assigned_partners: updatedPartners });
      toast({ title: "Socio removido" });
      onUpdated?.();
    } catch {
      toast({ title: "Error", variant: "destructive" });
    }
  };

  const handleTogglePayment = async (socioId) => {
    let becamePaid = false;
    let socioName = "";
    const updatedPartners = partners.map(p => {
      if (p.socio_id !== socioId) return p;
      const newStatus = p.payment_status === "Pagado" ? "Pendiente" : "Pagado";
      if (newStatus === "Pagado") { becamePaid = true; socioName = p.name; }
      return { ...p, payment_status: newStatus };
    });
    try {
      await updateReservation(reservation.id, { assigned_partners: updatedPartners });
      if (becamePaid) {
        toast({ title: `💰 ¡${socioName} pagado!` });
        celebratePayment();
      }
      onUpdated?.();
    } catch {
      toast({ title: "Error", variant: "destructive" });
    }
  };

  return (
    <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }} className="glass rounded-3xl p-6">
      <div className="flex items-center gap-2.5 mb-5">
        <div className="w-8 h-8 rounded-2xl bg-gradient-to-br from-violet-400 to-indigo-600 flex items-center justify-center">
          <Users size={14} className="text-white" />
        </div>
        <h2 className="text-xs font-black text-slate-500 uppercase tracking-widest">Fotógrafo / Equipo</h2>
      </div>

      {/* Add partner */}
      <div className="flex gap-2 mb-4">
        <select value={selectedSocio} onChange={e => setSelectedSocio(e.target.value)}
          className="flex-1 text-sm px-3 py-2.5 rounded-2xl glass bg-transparent border-white/60 focus:outline-none focus:ring-2 focus:ring-[var(--t-from)]/30 text-slate-700 font-medium"
          data-testid="select-socio">
          <option value="" className="bg-white">Seleccionar socio...</option>
          {socios.map(s => <option key={s.id} value={s.id} className="bg-white">{s.name} · {s.role}</option>)}
        </select>
        <input type="number" value={payment} onChange={e => setPayment(e.target.value)} placeholder="Pago Q"
          className="w-28 text-sm px-3 py-2.5 rounded-2xl glass bg-transparent border-white/60 focus:outline-none focus:ring-2 focus:ring-[var(--t-from)]/30 text-slate-700"
          data-testid="input-partner-payment" />
        <motion.button whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }} onClick={handleAdd} disabled={adding}
          className="p-2.5 rounded-2xl btn-primary text-white disabled:opacity-60" data-testid="add-partner-btn">
          <Plus size={16} />
        </motion.button>
      </div>

      {/* Partners list */}
      <AnimatePresence>
        {partners.length > 0 && (
          <div className="space-y-2 mb-4">
            {partners.map((p, i) => {
              const RoleIcon = ROLE_ICONS[p.role] || Users;
              const isPaid = p.payment_status === "Pagado";
              return (
                <motion.div key={p.socio_id} initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 10 }} transition={{ delay: i * 0.05 }}
                  className="flex items-center gap-3 p-3 rounded-2xl bg-white/30 border border-white/40">
                  <SocioAvatar socio={p} size="sm" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-bold text-slate-900 truncate">{p.name}</p>
                    <span className={`text-[10px] px-2 py-0.5 rounded-full border font-bold inline-flex items-center gap-1 ${ROLE_COLORS[p.role] || ROLE_COLORS["Asistente"]}`}>
                      <RoleIcon size={9} /> {p.role}
                    </span>
                  </div>
                  <span className={`text-sm font-black ${isPaid ? "text-emerald-600 line-through opacity-60" : "text-amber-600"}`}>
                    {formatCurrency(p.payment)}
                  </span>
                  {/* Payment status toggle */}
                  <motion.button
                    whileHover={{ scale: 1.1 }} whileTap={{ scale: 0.9 }}
                    onClick={() => handleTogglePayment(p.socio_id)}
                    title={isPaid ? "Marcar pendiente" : "Marcar pagado"}
                    data-testid={`toggle-payment-${p.socio_id}`}
                    className={`p-1.5 rounded-full transition-colors ${isPaid ? "bg-emerald-100 text-emerald-600 hover:bg-emerald-200" : "bg-amber-50 text-amber-400 hover:bg-amber-100"}`}>
                    {isPaid ? <CheckCircle size={14} /> : <Clock size={14} />}
                  </motion.button>
                  <motion.button whileHover={{ scale: 1.1 }} whileTap={{ scale: 0.9 }} onClick={() => handleRemove(p.socio_id)}
                    className="p-1.5 rounded-full hover:bg-red-100 text-slate-400 hover:text-red-500 transition-colors"
                    data-testid={`remove-partner-${p.socio_id}`}>
                    <X size={12} />
                  </motion.button>
                </motion.div>
              );
            })}
          </div>
        )}
      </AnimatePresence>

      {/* Financial summary */}
      <div className="border-t border-white/40 pt-4 space-y-2">
        <div className="flex justify-between items-center">
          <span className="text-xs font-bold text-slate-500">Total del evento</span>
          <span className="text-sm font-black text-slate-700">{formatCurrency(reservation.total_amount || 0)}</span>
        </div>
        <div className="flex justify-between items-center">
          <span className="text-xs font-bold text-slate-500">Costo equipo</span>
          <span className="text-sm font-black text-amber-600">{formatCurrency(teamCost)}</span>
        </div>
        {partners.length > 0 && (
          <>
            <div className="flex justify-between items-center pl-3">
              <span className="text-[10px] font-bold text-emerald-500 flex items-center gap-1"><CheckCircle size={9} /> Pagado a equipo</span>
              <span className="text-xs font-black text-emerald-600">{formatCurrency(paidToTeam)}</span>
            </div>
            <div className="flex justify-between items-center pl-3">
              <span className="text-[10px] font-bold text-amber-500 flex items-center gap-1"><Clock size={9} /> Pendiente equipo</span>
              <span className="text-xs font-black text-amber-600">{formatCurrency(pendingToTeam)}</span>
            </div>
          </>
        )}
        <div className="flex justify-between items-center pt-1 border-t border-white/30">
          <span className="text-xs font-black text-slate-700 uppercase tracking-wide">Ingreso real</span>
          <span className={`text-base font-black ${realIncome >= 0 ? "text-emerald-600" : "text-red-500"}`} data-testid="real-income">
            {formatCurrency(realIncome)}
          </span>
        </div>
      </div>
    </motion.div>
  );
}
