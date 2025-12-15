import { useEffect, useState } from "react";
import { api } from "../api";
import StatusBadge from "./StatusBadge";

type Supplier = {
  id: number;
  supplier: string;
  inn: string;
  city?: string;
  country?: string;
  branch?: string;
};

type Mapping = {
  id: number;
  owner_id: string;
  packet_id: string;
  inn_norm?: string | null;
  std_supplier_raw: string;
  canonical_supplier: string;
  canonical_supplier_id?: number;
  status: string;
  created_at: string;
};

type ModerationEvent = {
  id: number;
  owner_id: string;
  packet_id: string;
  supplier_group_id: number;
  decision: string;
  decided_at: string;
  reject_reason_label?: string | null;
  reject_comment_internal?: string | null;
  std_supplier_raw?: string | null;
  inn_norm?: string | null;
  packet?: string | null;
  canonical_supplier?: string | null;
  canonical_inn?: string | null;
  canonical_city?: string | null;
  status?: string | null;
};

type Issue = {
  id: number;
  owner_id: string;
  packet_id: string;
  std_supplier?: string;
  comment: string;
  created_at: string;
};

type Props = {
  onLogout: () => void;
};

const REJECTION_REASONS = [
  { code: "WRONG_INN", label: "ИНН указан неверно" },
  { code: "WRONG_SUPPLIER", label: "Выбран неверный поставщик" },
  { code: "NEED_MORE_INFO", label: "Недостаточно данных, уточните информацию" },
  { code: "SUPPLIER_NOT_FOUND", label: "Поставщик отсутствует в справочнике" },
  { code: "DUPLICATE_REQUEST", label: "Дубликат заявки" },
];

export default function AdminDashboard({ onLogout }: Props) {
  const [tab, setTab] = useState<"suppliers" | "moderation" | "history" | "issues">("suppliers");
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [supplierSearch, setSupplierSearch] = useState("");
  const [newSupplier, setNewSupplier] = useState<Partial<Supplier>>({ supplier: "", inn: "" });
  const [mappings, setMappings] = useState<Mapping[]>([]);
  const [moderationSearch, setModerationSearch] = useState("");
  const [historySearch, setHistorySearch] = useState("");
  const [historyEvents, setHistoryEvents] = useState<ModerationEvent[]>([]);
  const [issues, setIssues] = useState<Issue[]>([]);
  const [collapsedGroups, setCollapsedGroups] = useState<Record<string, boolean>>({});
  const [rejectModal, setRejectModal] = useState<{ open: boolean; mappingId?: number; reason: string; comment: string }>({ open: false, mappingId: undefined, reason: "", comment: "" });

  const loadSuppliers = async () => {
    const res = await api.listSuppliers(supplierSearch);
    setSuppliers(res);
  };

  const loadMappings = async () => {
    const res = await api.listPendingMappings();
    setMappings(res);
  };

  const loadHistory = async () => {
    const res = await api.moderationHistory(historySearch);
    setHistoryEvents(res);
  };

  const loadIssues = async () => {
    const res = await api.listIssues();
    setIssues(res);
  };

  useEffect(() => {
    loadSuppliers();
    loadMappings();
    loadHistory();
    loadIssues();
  }, []);

  const handleCreateSupplier = async () => {
    await api.createSupplier(newSupplier);
    setNewSupplier({ supplier: "", inn: "" });
    await loadSuppliers();
  };

  const handleDeleteSupplier = async (id: number) => {
    await api.deleteSupplier(id);
    await loadSuppliers();
  };

  const handleApprove = async (id: number) => {
    await api.approveMapping(id);
    await loadMappings();
    await loadHistory();
  };

  const handleRejectConfirm = async () => {
    if (!rejectModal.mappingId || !rejectModal.reason) return;
    await api.rejectMapping(rejectModal.mappingId, rejectModal.reason, rejectModal.comment);
    setRejectModal({ open: false, mappingId: undefined, reason: "", comment: "" });
    await loadMappings();
    await loadHistory();
  };

  const filteredMappings = (() => {
    const q = moderationSearch.trim();
    if (!q) return mappings;
    const needle = q.toLowerCase();
    return mappings.filter(
      (m) =>
        m.owner_id.toLowerCase().includes(needle) ||
        m.packet_id.toLowerCase().includes(needle)
    );
  })();

  const groupedByOwner = filteredMappings.reduce<Record<string, Mapping[]>>((acc, m) => {
    acc[m.owner_id] = acc[m.owner_id] || [];
    acc[m.owner_id].push(m);
    return acc;
  }, {});

  // Ensure new groups have a collapse state; first group expanded by default.
  useEffect(() => {
    const keys = Object.keys(groupedByOwner);
    if (keys.length === 0) return;
    setCollapsedGroups((prev) => {
      const next = { ...prev };
      keys.forEach((k, idx) => {
        if (next[k] === undefined) {
          next[k] = idx === 0 ? false : true;
        }
      });
      return next;
    });
  }, [Object.keys(groupedByOwner).join("|")]);

  const canonicalById = suppliers.reduce<Record<number, Supplier>>((acc, s) => {
    acc[s.id] = s;
    return acc;
  }, {});

  const buildInnParts = (priceInn?: string | null, canonicalInn?: string) => {
    const a = (priceInn || "").trim();
    const b = (canonicalInn || "").trim();
    const maxLen = Math.max(a.length, b.length);
    let hasDiff = false;
    const priceDigits: JSX.Element[] = [];
    const canonicalDigits: JSX.Element[] = [];
    for (let i = 0; i < maxLen; i++) {
        const ca = a[i] || "";
        const cb = b[i] || "";
        const isDiff = ca !== cb;
        if (isDiff) hasDiff = true;
        priceDigits.push(
          <span key={`p-${i}`} className={`inn-digit ${isDiff ? "mismatch" : ""}`}>
            {ca || cb || " "}
          </span>
        );
        canonicalDigits.push(
          <span key={`c-${i}`} className={`inn-digit ${isDiff ? "mismatch" : ""}`}>
            {cb || ca || " "}
          </span>
        );
    }
    return { hasDiff, priceDigits, canonicalDigits, hasAny: a || b };
  };

  const renderInnPrice = (priceInn?: string | null, canonicalInn?: string) => {
    const { hasDiff, priceDigits, hasAny } = buildInnParts(priceInn, canonicalInn);
    if (!hasAny) return <div className="inn-block price">—</div>;
    const containerClass = `inn-block price ${hasDiff ? "has-diff" : "all-match"}`;
    return <div className={containerClass}>{priceDigits}</div>;
  };

  const renderInnCanonical = (priceInn?: string | null, canonicalInn?: string) => {
    const { hasDiff, canonicalDigits, hasAny } = buildInnParts(priceInn, canonicalInn);
    if (!hasAny) return <div className="inn-block canonical">—</div>;
    const containerClass = `inn-block canonical ${hasDiff ? "has-diff" : "all-match"}`;
    return <div className={containerClass}>{canonicalDigits}</div>;
  };

  return (
    <div className="layout">
      <div className="flex" style={{ justifyContent: "space-between" }}>
        <h2>Admin</h2>
        <button className="secondary" onClick={() => { api.adminLogout(); onLogout(); }}>Выйти</button>
      </div>

      <div className="flex" style={{ gap: 8, marginBottom: 12 }}>
        <button className={tab === "suppliers" ? "" : "secondary"} onClick={() => setTab("suppliers")}>Справочник</button>
        <button className={tab === "moderation" ? "" : "secondary"} onClick={() => setTab("moderation")}>Модерация</button>
        <button className={tab === "history" ? "" : "secondary"} onClick={() => setTab("history")}>История</button>
        <button className={tab === "issues" ? "" : "secondary"} onClick={() => setTab("issues")}>Issues</button>
      </div>

      {tab === "suppliers" && (
        <div>
          <div className="card">
            <div className="flex" style={{ gap: 8 }}>
              <input
                placeholder="Поиск по названию/ИНН"
                value={supplierSearch}
                onChange={(e) => setSupplierSearch(e.target.value)}
              />
              <button onClick={loadSuppliers}>Поиск</button>
            </div>
          </div>
          <div className="card">
            <h3>Создать поставщика</h3>
            <div className="flex" style={{ gap: 8, flexWrap: "wrap" }}>
              <input
                placeholder="Название"
                value={newSupplier.supplier || ""}
                onChange={(e) => setNewSupplier({ ...newSupplier, supplier: e.target.value })}
              />
              <input
                placeholder="ИНН"
                value={newSupplier.inn || ""}
                onChange={(e) => setNewSupplier({ ...newSupplier, inn: e.target.value })}
              />
              <input
                placeholder="Город"
                value={newSupplier.city || ""}
                onChange={(e) => setNewSupplier({ ...newSupplier, city: e.target.value })}
              />
            </div>
            <div style={{ marginTop: 8 }}>
              <button onClick={handleCreateSupplier} disabled={!newSupplier.supplier || !newSupplier.inn}>
                Сохранить
              </button>
            </div>
          </div>
          <div className="card">
            <table className="table">
              <thead>
                <tr>
                  <th>Название</th>
                  <th>ИНН</th>
                  <th>Город</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {suppliers.map((s) => (
                  <tr key={s.id}>
                    <td>{s.supplier}</td>
                    <td>{s.inn}</td>
                    <td>{s.city}</td>
                    <td>
                      <button className="secondary" onClick={() => handleDeleteSupplier(s.id)}>Удалить</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === "moderation" && (
        <div className="card">
          <div className="card" style={{ marginBottom: 12 }}>
            <input
              placeholder="ownerId или packetId"
              value={moderationSearch}
              onChange={(e) => setModerationSearch(e.target.value)}
            />
          </div>

          {filteredMappings.length === 0 && <div>Ничего не найдено.</div>}

          {Object.entries(groupedByOwner).map(([ownerId, items]) => (
            <div key={ownerId} className="card" style={{ marginBottom: 12 }}>
              <div
                className="flex"
                style={{ justifyContent: "space-between", marginBottom: 8, cursor: "pointer" }}
                onClick={() =>
                  setCollapsedGroups((prev) => ({ ...prev, [ownerId]: !prev[ownerId] }))
                }
              >
                <div style={{ fontWeight: 700 }}>
                  ownerId: {ownerId} — {items.length} pending
                </div>
                <div style={{ color: "#475569", fontSize: 13 }}>
                  {collapsedGroups[ownerId] ? "Развернуть" : "Свернуть"}
                </div>
              </div>
              {!collapsedGroups[ownerId] &&
                items.map((m) => (
                  <div key={m.id} className="card" style={{ marginBottom: 8 }}>
                    <div className="mod-header">
                      <div className="mod-title">
                        <span>{m.std_supplier_raw}</span>
                        <span className="mod-arrow">→</span>
                        <span>{m.canonical_supplier}</span>
                      </div>
                      <StatusBadge status={m.status} />
                    </div>
                    <div className="mod-columns">
                      <div className="mod-col">
                        <div className="mod-col-title">Из прайса продавца</div>
                        <div className="mod-col-block">
                          <div className="mod-field-label">ИНН</div>
                          {renderInnPrice(m.inn_norm, canonicalById[m.canonical_supplier_id || -1]?.inn)}
                          <div className="mod-field-label">packetId</div>
                          <div className="mod-field-value subtle">{m.packet_id}</div>
                        </div>
                      </div>
                      <div className="mod-col">
                        <div className="mod-col-title">Из справочника</div>
                        <div className="mod-col-block">
                          <div className="mod-field-label">ИНН</div>
                          {renderInnCanonical(m.inn_norm, canonicalById[m.canonical_supplier_id || -1]?.inn)}
                          <div className="mod-field-label">Город</div>
                          <div className="mod-field-value subtle">
                            {canonicalById[m.canonical_supplier_id || -1]?.city || "—"}
                          </div>
                        </div>
                      </div>
                    </div>
                    <div className="flex" style={{ marginTop: 8, gap: 8 }}>
                      <button onClick={() => handleApprove(m.id)}>Approve</button>
                      <button
                        className="secondary"
                        onClick={() => setRejectModal({ open: true, mappingId: m.id, reason: "", comment: "" })}
                      >
                        Reject
                      </button>
                    </div>
                  </div>
                ))}
            </div>
          ))}
        </div>
      )}

      {tab === "history" && (
        <div className="card">
          <div className="card" style={{ marginBottom: 12 }}>
            <div className="flex" style={{ gap: 8 }}>
              <input
                placeholder="ownerId или packetId"
                value={historySearch}
                onChange={(e) => setHistorySearch(e.target.value)}
              />
              <button onClick={loadHistory}>Поиск</button>
            </div>
          </div>
          {historyEvents.length === 0 && <div>Нет записей.</div>}
          {historyEvents.map((ev) => (
            <div key={ev.id} className="card" style={{ marginBottom: 10 }}>
              <div className="mod-header">
                <div className="mod-title">
                  <span>{ev.std_supplier_raw}</span>
                  <span className="mod-arrow">→</span>
                  <span>{ev.canonical_supplier}</span>
                </div>
                <StatusBadge status={ev.decision} />
              </div>
              <div className="mod-columns">
                <div className="mod-col">
                  <div className="mod-col-title">Из прайса продавца</div>
                  <div className="mod-field-label">ИНН</div>
                  {renderInnPrice(ev.inn_norm, ev.canonical_inn)}
                  <div className="mod-field-label">packetId</div>
                  <div className="mod-field-value subtle">{ev.packet || ev.packet_id}</div>
                </div>
                <div className="mod-col">
                  <div className="mod-col-title">Из справочника</div>
                  <div className="mod-field-label">ИНН</div>
                  {renderInnCanonical(ev.inn_norm, ev.canonical_inn)}
                  <div className="mod-field-label">Город</div>
                  <div className="mod-field-value subtle">{ev.canonical_city || "—"}</div>
                </div>
              </div>
              <div className="mod-col-block" style={{ marginTop: 8, rowGap: 4 }}>
                <div className="mod-field-value subtle">Решение: {ev.decision}</div>
                <div className="mod-field-value subtle">
                  Дата: {new Date(ev.decided_at).toLocaleString()}
                </div>
                {ev.decision === "REJECTED" && (
                  <>
                    <div className="mod-field-value subtle">
                      Причина (продавцу): {ev.reject_reason_label || "—"}
                    </div>
                    {ev.reject_comment_internal && (
                      <div className="mod-field-value subtle">
                        Комментарий (внутренний): {ev.reject_comment_internal}
                      </div>
                    )}
                  </>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {tab === "issues" && (
        <div className="card">
          {issues.map((i) => (
            <div key={i.id} className="card" style={{ marginBottom: 6 }}>
              <div style={{ fontWeight: 600 }}>{i.std_supplier}</div>
              <div className="pill">owner: {i.owner_id}</div>{" "}
              <div className="pill">packet: {i.packet_id}</div>
              <div>{i.comment}</div>
              <div style={{ fontSize: 12, color: "#475569" }}>{new Date(i.created_at).toLocaleString()}</div>
            </div>
          ))}
        </div>
      )}

      {rejectModal.open && (
        <div className="modal">
          <div className="modal-card" style={{ width: 420 }}>
            <h3>Отклонить заявку</h3>
            <div style={{ marginBottom: 8 }}>
              <label>Причина отклонения *</label>
              <select
                value={rejectModal.reason}
                onChange={(e) => setRejectModal({ ...rejectModal, reason: e.target.value })}
              >
                <option value="">Выберите причину</option>
                {REJECTION_REASONS.map((r) => (
                  <option key={r.code} value={r.code}>{r.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label>Внутренний комментарий (не видит продавец)</label>
              <textarea
                rows={3}
                value={rejectModal.comment}
                onChange={(e) => setRejectModal({ ...rejectModal, comment: e.target.value })}
              />
            </div>
            <div className="flex" style={{ justifyContent: "flex-end", gap: 8, marginTop: 12 }}>
              <button className="secondary" onClick={() => setRejectModal({ open: false, mappingId: undefined, reason: "", comment: "" })}>Отмена</button>
              <button onClick={handleRejectConfirm} disabled={!rejectModal.reason}>Подтвердить</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
