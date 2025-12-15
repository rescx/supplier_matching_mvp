const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function request(path: string, options: RequestInit = {}, useCredentials = false) {
  const res = await fetch(`${API_URL}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    credentials: useCredentials ? "include" : "same-origin",
    ...options,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  return res.status === 204 ? null : res.json();
}

export const api = {
  getSellerGroups: (token: string) =>
    request(`/api/seller/groups?token=${encodeURIComponent(token)}`),
  searchSuppliers: (q: string) => request(`/api/seller/suppliers?q=${encodeURIComponent(q)}`),
  createMapping: (token: string, groupId: number, supplierId: number) =>
    request("/api/seller/mappings", {
      method: "POST",
      body: JSON.stringify({ token, group_id: groupId, canonical_supplier_id: supplierId }),
    }),
  createIssue: (token: string, groupId: number, comment: string) =>
    request("/api/seller/issues", {
      method: "POST",
      body: JSON.stringify({ token, group_id: groupId, comment }),
    }),
  adminLogin: (username: string, password: string) =>
    request("/api/admin/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }, true),
  listSuppliers: (q: string) => request(`/api/admin/suppliers?q=${encodeURIComponent(q)}`, {}, true),
  createSupplier: (payload: any) =>
    request("/api/admin/suppliers", { method: "POST", body: JSON.stringify(payload) }, true),
  deleteSupplier: (id: number) =>
    request(`/api/admin/suppliers/${id}`, { method: "DELETE" }, true),
  listPendingMappings: () => request("/api/admin/mappings/pending", {}, true),
  approveMapping: (id: number) =>
    request(`/api/admin/mappings/${id}/approve`, { method: "POST" }, true),
  rejectMapping: (id: number, reason_code: string, comment_internal?: string) =>
    request(`/api/admin/mappings/${id}/reject`, {
      method: "POST",
      body: JSON.stringify({ reason_code, comment_internal }),
    }, true),
  moderationHistory: (q = "", limit = 50, offset = 0) =>
    request(`/api/admin/moderation/history?limit=${limit}&offset=${offset}&q=${encodeURIComponent(q)}`, {}, true),
  listIssues: () => request("/api/admin/issues", {}, true),
  adminLogout: () => request("/api/admin/logout", { method: "POST" }, true),
};
