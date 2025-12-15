import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import StatusBadge from "./StatusBadge";

type Group = {
  id: number;
  inn_norm?: string | null;
  inn_invalid: boolean;
  std_supplier_raw: string;
  items_count: number;
  status: string;
  canonical_supplier?: string | null;
  canonical_supplier_id?: number | null;
  latest_status?: string | null;
  latest_decision_at?: string | null;
  reject_reason_label?: string | null;
};

type Supplier = {
  id: number;
  supplier: string;
  inn: string;
};

type Props = {
  token: string;
};

export default function SellerPage({ token }: Props) {
  const [groups, setGroups] = useState<Group[]>([]);
  const [filter, setFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [mappingGroup, setMappingGroup] = useState<Group | null>(null);
  const [issueGroup, setIssueGroup] = useState<Group | null>(null);
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [supplierQuery, setSupplierQuery] = useState("");
  const [comment, setComment] = useState("");

  const loadGroups = async () => {
    setLoading(true);
    setError("");
    try {
      const data = await api.getSellerGroups(token);
      setGroups(data);
    } catch (err: any) {
      setError(err.message || "Ошибка загрузки");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadGroups();
  }, []);

  useEffect(() => {
    if (supplierQuery.length === 0) {
      setSuppliers([]);
      return;
    }
    const timeout = setTimeout(async () => {
      try {
        const res = await api.searchSuppliers(supplierQuery);
        setSuppliers(res);
      } catch (e) {
        console.error(e);
      }
    }, 250);
    return () => clearTimeout(timeout);
  }, [supplierQuery]);

  const filtered = useMemo(() => {
    const q = filter.toLowerCase();
    return groups.filter(
      (g) =>
        g.std_supplier_raw.toLowerCase().includes(q) ||
        (g.inn_norm || "").includes(filter)
    );
  }, [groups, filter]);

  const handleCreateMapping = async (supplierId: number) => {
    if (!mappingGroup) return;
    await api.createMapping(token, mappingGroup.id, supplierId);
    setMappingGroup(null);
    setSupplierQuery("");
    await loadGroups();
  };

  const handleCreateIssue = async () => {
    if (!issueGroup) return;
    await api.createIssue(token, issueGroup.id, comment);
    setIssueGroup(null);
    setComment("");
  };

  return (
    <div className="layout">
      <h2>Поставщики в прайсе</h2>
      <p>Токен: <span className="pill">{token}</span></p>
      <div className="card">
        <input
          placeholder="Поиск по названию или ИНН"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
      </div>

      {loading && <div>Загрузка...</div>}
      {error && <div style={{ color: "red" }}>{error}</div>}

      {filtered.map((g) => (
        <div className="card" key={g.id}>
          <div className="flex" style={{ justifyContent: "space-between", alignItems: "flex-start" }}>
            <div>
              <div style={{ fontWeight: 700 }}>{g.std_supplier_raw}</div>
              <div className="flex" style={{ flexWrap: "wrap", gap: 8 }}>
                <span className="pill">ИНН: {g.inn_norm || "—"}</span>
                {g.inn_invalid && <span className="badge rejected">ИНН некорректен</span>}
                <span className="pill">Товаров: {g.items_count}</span>
              </div>
            </div>
            <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 4 }}>
              <StatusBadge status={g.latest_status || g.status} />
              {g.latest_status === "REJECTED" && g.reject_reason_label && (
                <div style={{ fontSize: 12, color: "#991b1b", textAlign: "right", lineHeight: 1.4 }}>
                  {g.reject_reason_label}
                </div>
              )}
            </div>
          </div>
          <div style={{ marginTop: 10 }} className="flex">
            <button onClick={() => setMappingGroup(g)}>Сопоставить</button>
            <button className="secondary" onClick={() => setIssueGroup(g)}>Не нашёл поставщика</button>
          </div>
          {g.canonical_supplier && (
            <div style={{ marginTop: 6, fontSize: 14 }}>
              Выбрано: {g.canonical_supplier} (#{g.canonical_supplier_id})
            </div>
          )}
        </div>
      ))}

      {mappingGroup && (
        <div className="modal">
          <div className="modal-card">
            <h3>Сопоставление</h3>
            <div style={{ marginBottom: 8 }}>{mappingGroup.std_supplier_raw}</div>
            <input
              placeholder="Искать по названию или ИНН"
              value={supplierQuery}
              onChange={(e) => setSupplierQuery(e.target.value)}
            />
            <div style={{ maxHeight: 200, overflow: "auto", marginTop: 8 }}>
              {suppliers.map((s) => (
                <div
                  key={s.id}
                  className="card"
                  style={{ cursor: "pointer", marginBottom: 6 }}
                  onClick={() => handleCreateMapping(s.id)}
                >
                  <div style={{ fontWeight: 600 }}>{s.supplier}</div>
                  <div className="pill">ИНН {s.inn}</div>
                </div>
              ))}
              {supplierQuery && suppliers.length === 0 && <div>Нет результатов</div>}
            </div>
            <div className="flex" style={{ justifyContent: "flex-end", marginTop: 8 }}>
              <button className="secondary" onClick={() => setMappingGroup(null)}>Закрыть</button>
            </div>
          </div>
        </div>
      )}

      {issueGroup && (
        <div className="modal">
          <div className="modal-card">
            <h3>Не нашёл поставщика</h3>
            <p>{issueGroup.std_supplier_raw}</p>
            <textarea
              rows={4}
              placeholder="Опишите проблему"
              value={comment}
              onChange={(e) => setComment(e.target.value)}
            />
            <div className="flex" style={{ justifyContent: "flex-end", marginTop: 8 }}>
              <button className="secondary" onClick={() => setIssueGroup(null)}>Отмена</button>
              <button onClick={handleCreateIssue} disabled={!comment.trim()}>Отправить</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
