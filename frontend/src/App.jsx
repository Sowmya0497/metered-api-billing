import { useState, useEffect } from "react";
import Customers from "./Customers";
import Invoices from "./Invoices";
import Usage from "./Usage";
import Credits from "./Credits";

function App() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loggedIn, setLoggedIn] = useState(!!localStorage.getItem("token"));
  const [page, setPage] = useState("customers");
  const [customerCount, setCustomerCount] = useState(0);
  const [usageCount, setUsageCount] = useState(0);
  const [invoiceCount, setInvoiceCount] = useState(0);
  const [creditCount, setCreditCount] = useState(0);

  const login = async () => {
    try {
      const response = await fetch("http://127.0.0.1:8000/api/token/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      const data = await response.json();
      if (data.access) {
        localStorage.setItem("token", data.access);
        setLoggedIn(true);
      } else {
        alert("Invalid Username or Password");
      }
    } catch (error) {
      alert("Login Failed");
    }
  };

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) return;

    fetch("http://127.0.0.1:8000/ops/customers/", {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => r.json())
      .then((data) => { if (Array.isArray(data)) setCustomerCount(data.length); });

    const now = new Date();
    const since = new Date(now.getFullYear(), now.getMonth(), 1).toISOString();
    fetch(`http://127.0.0.1:8000/v1/usage/?since=${since}&page_size=1`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => r.json())
      .then((data) => { if (data && data.total !== undefined) setUsageCount(data.total); });

    fetch("http://127.0.0.1:8000/v1/invoices/count/", {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => r.json())
      .then((data) => { if (data.count !== undefined) setInvoiceCount(data.count); });

    fetch("http://127.0.0.1:8000/ops/credits/", {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => r.json())
      .then((data) => { if (Array.isArray(data)) setCreditCount(data.length); });

  }, [loggedIn]);

  if (!loggedIn) {
    return (
      <div style={{
        minHeight: "100vh",
        background: "linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}>
        <div style={{
          background: "rgba(255,255,255,0.05)",
          backdropFilter: "blur(10px)",
          border: "1px solid rgba(255,255,255,0.1)",
          borderRadius: "20px",
          padding: "50px 40px",
          width: "100%",
          maxWidth: "420px",
          boxShadow: "0 25px 45px rgba(0,0,0,0.3)",
        }}>
          <div style={{ textAlign: "center", marginBottom: "32px" }}>
            <div style={{
              width: "70px", height: "70px",
              background: "linear-gradient(135deg, #667eea, #764ba2)",
              borderRadius: "50%",
              display: "flex", alignItems: "center", justifyContent: "center",
              margin: "0 auto 20px",
              fontSize: "28px",
            }}>💳</div>
            <h2 style={{ color: "white", fontWeight: "700", marginBottom: "5px" }}>Metered API Billing</h2>
            <p style={{ color: "rgba(255,255,255,0.5)", fontSize: "14px" }}>Sign in to your dashboard</p>
          </div>

          <div style={{ marginBottom: "16px" }}>
            <label style={{ color: "rgba(255,255,255,0.7)", fontSize: "14px", marginBottom: "8px", display: "block" }}>Username</label>
            <input
              type="text"
              placeholder="Enter your username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && login()}
              style={{
                width: "100%", padding: "12px 16px",
                background: "rgba(255,255,255,0.08)",
                border: "1px solid rgba(255,255,255,0.15)",
                borderRadius: "10px", color: "white",
                fontSize: "15px", outline: "none",
                boxSizing: "border-box",
              }}
            />
          </div>

          <div style={{ marginBottom: "24px" }}>
            <label style={{ color: "rgba(255,255,255,0.7)", fontSize: "14px", marginBottom: "8px", display: "block" }}>Password</label>
            <input
              type="password"
              placeholder="Enter your password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && login()}
              style={{
                width: "100%", padding: "12px 16px",
                background: "rgba(255,255,255,0.08)",
                border: "1px solid rgba(255,255,255,0.15)",
                borderRadius: "10px", color: "white",
                fontSize: "15px", outline: "none",
                boxSizing: "border-box",
              }}
            />
          </div>

          <button
            onClick={login}
            style={{
              width: "100%", padding: "13px",
              background: "linear-gradient(135deg, #667eea, #764ba2)",
              border: "none", borderRadius: "10px",
              color: "white", fontSize: "16px",
              fontWeight: "600", cursor: "pointer",
              boxShadow: "0 5px 15px rgba(102,126,234,0.4)",
            }}
          >
            Sign In →
          </button>

          <p style={{ color: "rgba(255,255,255,0.3)", fontSize: "12px", textAlign: "center", marginTop: "20px" }}>
            Metered API Billing System
          </p>
        </div>
      </div>
    );
  }

  const navBtn = (label, pg, color) => (
    <button
      onClick={() => setPage(pg)}
      style={{
        background: page === pg ? color : "rgba(255,255,255,0.15)",
        border: "none", borderRadius: "10px",
        color: "white", padding: "10px 20px",
        cursor: "pointer", fontWeight: "600",
        marginRight: "8px", fontSize: "14px",
        transition: "all 0.2s",
      }}
    >
      {label}
    </button>
  );

  return (
    <div style={{ minHeight: "100vh", background: "#f5f7fa" }}>

      <div style={{
        background: "linear-gradient(135deg, #1a1a2e, #0f3460)",
        padding: "16px 32px",
        display: "flex", justifyContent: "space-between", alignItems: "center",
        boxShadow: "0 4px 20px rgba(0,0,0,0.3)",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <span style={{ fontSize: "24px" }}>💳</span>
          <span style={{ color: "white", fontWeight: "700", fontSize: "18px" }}>Metered API Billing</span>
        </div>
        <div>
          {navBtn("👥 Customers", "customers", "linear-gradient(135deg, #667eea, #764ba2)")}
          {navBtn("📊 Usage", "usage", "linear-gradient(135deg, #11998e, #38ef7d)")}
          {navBtn("🧾 Invoices", "invoices", "linear-gradient(135deg, #f7971e, #ffd200)")}
          {navBtn("💰 Credits", "credits", "linear-gradient(135deg, #ee0979, #ff6a00)")}
          <button
            onClick={() => { localStorage.removeItem("token"); setLoggedIn(false); }}
            style={{
              background: "rgba(255,255,255,0.1)", border: "1px solid rgba(255,255,255,0.2)",
              borderRadius: "10px", color: "white", padding: "10px 20px",
              cursor: "pointer", fontWeight: "600", fontSize: "14px",
            }}
          >
            🚪 Logout
          </button>
        </div>
      </div>

      <div style={{ padding: "32px" }}>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: "20px", marginBottom: "32px" }}>
          {[
            { label: "Customers",        icon: "👥", count: customerCount, color: "linear-gradient(135deg, #667eea, #764ba2)" },
            { label: "Usage This Month", icon: "📊", count: usageCount,    color: "linear-gradient(135deg, #11998e, #38ef7d)" },
            { label: "Invoices",         icon: "🧾", count: invoiceCount,  color: "linear-gradient(135deg, #f7971e, #ffd200)" },
            { label: "Credits",          icon: "💰", count: creditCount,   color: "linear-gradient(135deg, #ee0979, #ff6a00)" },
          ].map((card) => (
            <div key={card.label} style={{
              background: card.color,
              borderRadius: "16px",
              padding: "24px",
              color: "white",
              height: "110px",
              display: "flex",
              flexDirection: "column",
              justifyContent: "center",
              alignItems: "center",
              boxShadow: "0 8px 25px rgba(0,0,0,0.15)",
            }}>
              <div style={{ fontSize: "13px", fontWeight: "600", marginBottom: "10px", opacity: 0.9 }}>
                {card.icon} {card.label}
              </div>
              <div style={{ fontSize: "36px", fontWeight: "800", lineHeight: "1" }}>{card.count.toLocaleString()}</div>
            </div>
          ))}
        </div>

        <div style={{ background: "white", borderRadius: "16px", padding: "28px", boxShadow: "0 4px 15px rgba(0,0,0,0.08)" }}>
          {page === "customers" && <Customers />}
          {page === "usage"     && <Usage />}
          {page === "invoices"  && <Invoices />}
          {page === "credits"   && <Credits />}
        </div>

      </div>
    </div>
  );
}

export default App;