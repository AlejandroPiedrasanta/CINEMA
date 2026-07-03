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
export const checkForUpdates = () => api.get("/updates/check").then(r => r.data);

// Appearance cloud sync & saved themes
export const getCloudAppearance = () => api.get("/settings/appearance").then(r => r.data);
export const saveCloudAppearance = (snapshot) => api.put("/settings/appearance", { snapshot }).then(r => r.data);
export const getSavedThemes = () => api.get("/themes").then(r => r.data);
export const createSavedTheme = (name, snapshot) => api.post("/themes", { name, snapshot }).then(r => r.data);
export const deleteSavedTheme = (id) => api.delete(`/themes/${id}`).then(r => r.data);

// App security
export const getSecurityStatus = () => api.get("/security/status").then(r => r.data);
export const setAppPassword = (password, hint, current_password) => api.post("/security/set-password", { password, hint, current_password }).then(r => r.data);
export const verifyAppPassword = (password) => api.post("/security/verify", { password }).then(r => r.data);
export const removeAppPassword = (current_password) => api.post("/security/remove-password", { current_password }).then(r => r.data);
export const setPageProtection = (enabled) => api.put("/security/protection", { enabled }).then(r => r.data);

// GitHub Integration
export const getGithubConfig = () => api.get("/github/config").then(r => r.data);
export const saveGithubConfig = (data) => api.post("/github/config", data).then(r => r.data);
export const checkGithubUpdates = () => api.get("/github/check-updates").then(r => r.data);
export const applyGithubUpdate = (force = true) => api.post("/github/apply-update", { force }).then(r => r.data);

// AI Context (Contexto para la próxima IA)
export const getAiContext = () => api.get("/ai-context").then(r => r.data);
export const saveAiContext = (content) => api.post("/ai-context", { content }).then(r => r.data);
export const resetAiContext = () => api.post("/ai-context/reset").then(r => r.data);

