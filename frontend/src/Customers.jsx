import { useState, useEffect } from "react";

const cardStyle = { borderRadius: "15px", border: "none", boxShadow: "0 4px 15px rgba(0,0,0,0.1)" };
const inputStyle = { borderRadius: "10px", border: "1px solid #e0e0e0", padding: "10px 14px", width: "100%", marginBottom: "10px", boxSizing: "border-box" };
const btnPrimary = { background: "linear-gradient(135deg, #667eea, #764ba2)", border: "none", borderRadius: "10px", color: "white", padding: "10px 20px", cursor: "pointer", fontWeight: "600" };
const btnWarning = { background: "linear-gradient(135deg, #f7971e, #ffd200)", border: "none", borderRadius: "8px", color: "white", padding: "6px 14px", cursor: "pointer", fontWeight: "600", marginRight: "6px" };
const btnDanger = { background: "linear-gradient(135deg, #ee0979, #ff6a00)", border: "none", borderRadius: "8px", color: "white", padding: "6px 14px", cursor: "pointer", fontWeight: "600" };
const btnSuccess = { background: "linear-gradient(135deg, #11998e, #38ef7d)", border: "none", borderRadius: "8px", color: "white", padding: "6px 14px", cursor: "pointer", fontWeight: "600", marginRight: "6px" };
const btnSecondary = { background: "#6c757d", border: "none", borderRadius: "8px", color: "white", padding: "6px 14px", cursor: "pointer", fontWeight: "600" };

function Customers() {
  const [customers, setCustomers] = useState([]);
  const [editingId, setEditingId] = useState(null);
  const [editName, setEditName] = useState("");
  const [editEmail, setEditEmail] = useState("");
  const [newName, setNewName] = useState("");
  const [newEmail, setNewEmail] = useState("");
  const [message, setMessage] = useState("");
  const [selected, setSelected] = useState(null);
  const [detail, setDetail] = useState(null);

  const token = localStorage.getItem("token");

  const loadCustomers = () => {
    fetch("http://127.0.0.1:8000/ops/customers/", {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => r.json())
      .then((data) => setCustomers(Array.isArray(data) ? data : []));
  };

  const loadDetail = (id) => {
    fetch(`http://127.0.0.1:8000/ops/customers/${id}/`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => r.json())
      .then((data) => { setSelected(id); setDetail(data); });
  };

  useEffect(() => { loadCustomers(); }, []);

  const createCustomer = () => {
    if (!newName || !newEmail) { setMessage("Name and email required."); return; }
    fetch("http://127.0.0.1:8000/ops/customers/", {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ name: newName, email: newEmail }),
    })
      .then((r) => r.json())
      .then((data) => {
        if (data.id) {
          setMessage(`Customer created! API Key (save this - shown once): ${data.api_key}`);
          setNewName(""); setNewEmail(""); loadCustomers();
        } else { setMessage(JSON.stringify(data)); }
      });
  };

  const startEdit = (c) => { setEditingId(c.id); setEditName(c.name); setEditEmail(c.email); };

  const saveEdit = (id) => {
    fetch(`http://127.0.0.1:8000/ops/customers/${id}/`, {
      method: "PUT",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ name: editName, email: editEmail }),
    })
      .then((r) => r.json())
      .then((data) => {
        if (data.id) { setEditingId(null); setMessage("Customer updated!"); loadCustomers(); }
        else setMessage(JSON.stringify(data));
      });
  };

  const deleteCustomer = (id, name) => {
    if (!window.confirm(`Delete ${name}? This cannot be undone.`)) return;
    fetch(`http://127.0.0.1:8000/ops/customers/${id}/`, {
      method: "DELETE", headers: { Authorization: `Bearer ${token}` },
    }).then(() => { setMessage("Customer deleted."); setSelected(null); setDetail(null); loadCustomers(); });
  };

  return (
    <div>
      <h3 style={{ fontWeight: "700", marginBottom: "20px" }}>Customers</h3>

      {message && (
        <div style={{ background: "#f0fff4", border: "1px solid #9ae6b4", borderRadius: "10px", padding: "12px 16px", marginBottom: "16px", color: "#276749", wordBreak: "break-all" }}>
          {message}
        </div>
      )}

      <div style={{ ...cardStyle, padding: "24px", marginBottom: "24px", background: "white" }}>
        <h5 style={{ fontWeight: "700", marginBottom: "16px" }}>Add New Customer</h5>
        <input style={inputStyle} type="text" placeholder="Full Name" value={newName} onChange={(e) => setNewName(e.target.value)} />
        <input style={inputStyle} type="email" placeholder="Email Address" value={newEmail} onChange={(e) => setNewEmail(e.target.value)} />
        <button style={btnPrimary} onClick={createCustomer}>Add Customer</button>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: detail ? "1fr 1fr" : "1fr", gap: "20px" }}>
        <div style={{ ...cardStyle, background: "white", overflow: "hidden" }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ background: "linear-gradient(135deg, #667eea, #764ba2)", color: "white" }}>
                <th style={{ padding: "14px 16px", textAlign: "left" }}>Name</th>
                <th style={{ padding: "14px 16px", textAlign: "left" }}>Email</th>
                <th style={{ padding: "14px 16px", textAlign: "left" }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {customers.map((c, i) => (
                <tr key={c.id} style={{ background: selected === c.id ? "#eef2ff" : i % 2 === 0 ? "#f9f9f9" : "white", borderBottom: "1px solid #eee", cursor: "pointer" }}>
                  <td style={{ padding: "12px 16px", fontWeight: "600" }} onClick={() => loadDetail(c.id)}>
                    {editingId === c.id
                      ? <input style={{ ...inputStyle, marginBottom: 0 }} value={editName} onChange={(e) => setEditName(e.target.value)} />
                      : c.name}
                  </td>
                  <td style={{ padding: "12px 16px" }} onClick={() => loadDetail(c.id)}>
                    {editingId === c.id
                      ? <input style={{ ...inputStyle, marginBottom: 0 }} value={editEmail} onChange={(e) => setEditEmail(e.target.value)} />
                      : c.email}
                  </td>
                  <td style={{ padding: "12px 16px" }}>
                    {editingId === c.id ? (
                      <><button style={btnSuccess} onClick={() => saveEdit(c.id)}>Save</button><button style={btnSecondary} onClick={() => setEditingId(null)}>Cancel</button></>
                    ) : (
                      <><button style={btnWarning} onClick={(e) => { e.stopPropagation(); startEdit(c); }}>Edit</button>
                      <button style={btnDanger} onClick={(e) => { e.stopPropagation(); deleteCustomer(c.id, c.name); }}>Delete</button></>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {detail && (
          <div style={{ ...cardStyle, padding: "24px", background: "white" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
              <h5 style={{ fontWeight: "700", margin: 0 }}>{detail.name}</h5>
              <button style={btnSecondary} onClick={() => { setSelected(null); setDetail(null); }}>Close</button>
            </div>
            <p style={{ color: "#666", marginBottom: "16px" }}>{detail.email}</p>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px", marginBottom: "16px" }}>
              <div style={{ background: detail.anomaly_detected ? "#fff5f5" : "#f0fff4", padding: "12px", borderRadius: "10px", textAlign: "center" }}>
                <div style={{ fontSize: "12px", color: "#666" }}>30-day usage</div>
                <div style={{ fontWeight: "700", fontSize: "18px" }}>{detail.usage_30d_units?.toLocaleString()}</div>
                {detail.anomaly_detected && <div style={{ color: "#e53e3e", fontSize: "12px", fontWeight: "600" }}>ANOMALY DETECTED</div>}
              </div>
              <div style={{ background: "#f0f4ff", padding: "12px", borderRadius: "10px", textAlign: "center" }}>
                <div style={{ fontSize: "12px", color: "#666" }}>Recent invoices</div>
                <div style={{ fontWeight: "700", fontSize: "18px" }}>{detail.recent_invoices?.length}</div>
              </div>
            </div>

            {detail.recent_invoices?.length > 0 && (
              <div style={{ marginBottom: "16px" }}>
                <h6 style={{ fontWeight: "700", marginBottom: "8px" }}>Recent Invoices</h6>
                {detail.recent_invoices.map((inv) => (
                  <div key={inv.id} style={{ display: "flex", justifyContent: "space-between", padding: "8px 12px", background: "#f9f9f9", borderRadius: "8px", marginBottom: "6px" }}>
                    <span style={{ fontSize: "12px", color: "#888" }}>{inv.id.slice(0, 12)}...</span>
                    <span style={{ fontWeight: "600" }}>${(inv.total_cents / 100).toFixed(2)}</span>
                    <span style={{ background: inv.status === "PAID" ? "#38ef7d" : "#667eea", color: "white", padding: "2px 8px", borderRadius: "10px", fontSize: "11px" }}>{inv.status}</span>
                  </div>
                ))}
              </div>
            )}

            {detail.credits?.length > 0 && (
              <div>
                <h6 style={{ fontWeight: "700", marginBottom: "8px" }}>Credits</h6>
                {detail.credits.map((cr) => (
                  <div key={cr.id} style={{ display: "flex", justifyContent: "space-between", padding: "8px 12px", background: "#f0fff4", borderRadius: "8px", marginBottom: "6px" }}>
                    <span style={{ fontSize: "12px", color: "#666" }}>{cr.reason}</span>
                    <span style={{ fontWeight: "700", color: "#11998e" }}>${(cr.amount_cents / 100).toFixed(2)}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default Customers;
