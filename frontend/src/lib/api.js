import axios from "axios";

const BASE = `${window.__API_BASE_URL__ || process.env.REACT_APP_BACKEND_URL}/api`;

export const api = axios.create({ baseURL: BASE });

export const getStats = () => api.get("/stats").then(r => r.data);
export const getReservations = () => api.get("/reservations").then(r => r.data);
export const getReservation = (id) => api.get(`/reservations/${id}`).then(r => r.data);
export const createReservation = (data) => api.post("/reservations", data).then(r => r.data);
export const updateReservation = (id, data) => api.put(`/reservations/${id}`, data).then(r => r.data);
export const deleteReservation = (id) => api.delete(`/reservations/${id}`).then(r => r.data);
export const getCalendarEvents = () => api.get("/calendar").then(r => r.data);

export const uploadReceipt = (id, file) => {
  const form = new FormData();
  form.append("file", file);
  return api.post(`/reservations/${id}/receipts`, form).then(r => r.data);
};

export const deleteReceipt = (id, receiptId) =>
  api.delete(`/reservations/${id}/receipts/${receiptId}`).then(r => r.data);

// Socios
export const getSocios = () => api.get("/socios").then(r => r.data);
export const getSocio = (id) => api.get(`/socios/${id}`).then(r => r.data);
export const createSocio = (data) => api.post("/socios", data).then(r => r.data);
export const updateSocio = (id, data) => api.put(`/socios/${id}`, data).then(r => r.data);
export const deleteSocio = (id) => api.delete(`/socios/${id}`).then(r => r.data);
export const uploadSocioPhoto = (id, file) => {
  const form = new FormData();
  form.append("file", file);
  return api.post(`/socios/${id}/photo`, form).then(r => r.data);
};
export const deleteSocioPhoto = (id) => api.delete(`/socios/${id}/photo`).then(r => r.data);
export const getFinancials = () => api.get("/financials").then(r => r.data);

// App Settings
export const getAppSettings = () => api.get("/settings").then(r => r.data);
export const updateAppSettings = (data) => api.put("/settings", data).then(r => r.data);

// Database Settings
export const getDbStats = () => api.get("/settings/database").then(r => r.data);
export const testDbConnection = (url) => api.post("/settings/database/test", { url }).then(r => r.data);
export const switchDatabase = (url) => api.post("/settings/database/connect", { url }).then(r => r.data);
export const resetDatabase = () => api.post("/settings/database/reset").then(r => r.data);

// Reminders
export const sendTestReminder   = () => api.post("/reminders/send").then(r => r.data);
export const testEmailConnection = () => api.post("/reminders/test-email").then(r => r.data);

// Notifications
export const getPendingNotifications = () => api.get("/notifications/pending").then(r => r.data);

// Backup
export const getBackupHistory = () => api.get("/backup/history").then(r => r.data);
export const createServerBackup = () => api.post("/backup/create").then(r => r.data);
export const deleteBackupFile = (filename) => api.delete(`/backup/${filename}`).then(r => r.data);
export const downloadBackupUrl = () => `${BASE}/backup/download`;
export const downloadBackupFileUrl = (filename) => `${BASE}/backup/${encodeURIComponent(filename)}/download`;
export const restoreBackup = (file) => {
  const form = new FormData();
  form.append("file", file);
  return api.post("/backup/restore", form).then(r => r.data);
};

// Updates
export const getUpdatesHistory = () => api.get("/updates/history").then(r => r.data);
export const getLatestUpdate = () => api.get("/updates/latest").then(r => r.data);
export const deleteUpdate = (id) => api.delete(`/updates/${id}`).then(r => r.data);
export const setLatestUpdate = (id) => api.put(`/updates/${id}/set-latest`).then(r => r.data);
export const checkRemoteUpdate = (url, currentVersion) =>
  api.get(`/updates/check-remote?url=${encodeURIComponent(url)}&current_version=${currentVersion}`).then(r => r.data);
export const getUpdateDownloadUrl = (id) => `${BASE}/updates/download/${id}`;
export const uploadAppUpdate = (file, version, notes, channel) => {
  const form = new FormData();
  form.append("file", file);
  form.append("version", version);
  form.append("notes", notes || "");
  form.append("channel", channel || "stable");
  return api.post("/updates/upload", form).then(r => r.data);
};
