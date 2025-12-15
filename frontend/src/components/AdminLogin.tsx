import { useState } from "react";
import { api } from "../api";

type Props = {
  onLoggedIn: () => void;
};

export default function AdminLogin({ onLoggedIn }: Props) {
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("admin");
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    try {
      await api.adminLogin(username, password);
      onLoggedIn();
    } catch (err: any) {
      setError("Неверный логин или пароль");
    }
  };

  return (
    <div className="layout">
      <div className="card" style={{ maxWidth: 400, margin: "80px auto" }}>
        <h2>Admin Login</h2>
        <form onSubmit={handleSubmit}>
          <div>
            <label>Логин</label>
            <input value={username} onChange={(e) => setUsername(e.target.value)} />
          </div>
          <div>
            <label>Пароль</label>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
          </div>
          {error && <div style={{ color: "red" }}>{error}</div>}
          <div style={{ marginTop: 12 }}>
            <button type="submit" style={{ width: "100%" }}>Войти</button>
          </div>
        </form>
      </div>
    </div>
  );
}
