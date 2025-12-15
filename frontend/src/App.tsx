import { useEffect, useState } from "react";
import SellerPage from "./components/SellerPage";
import AdminLogin from "./components/AdminLogin";
import AdminDashboard from "./components/AdminDashboard";
import { api } from "./api";

function App() {
  const path = window.location.pathname;
  if (path.startsWith("/s/")) {
    const token = path.split("/")[2];
    return <SellerPage token={token} />;
  }
  return <AdminApp />;
}

function AdminApp() {
  const [loggedIn, setLoggedIn] = useState(false);

  useEffect(() => {
    // quick ping to check session by requesting suppliers
    api
      .listSuppliers("")
      .then(() => setLoggedIn(true))
      .catch(() => setLoggedIn(false));
  }, []);

  if (!loggedIn) {
    return <AdminLogin onLoggedIn={() => setLoggedIn(true)} />;
  }
  return <AdminDashboard onLogout={() => setLoggedIn(false)} />;
}

export default App;
