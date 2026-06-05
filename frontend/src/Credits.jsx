import { useState, useEffect } from "react";

const cardStyle = { borderRadius: "15px", border: "none", boxShadow: "0 4px 15px rgba(0,0,0,0.1)", background: "white" };
const inputStyle = { borderRadius: "10px", border: "1px solid #e0e0e0", padding: "10px 14px", width: "100%", marginBottom: "10px", boxSizing: "border-box", fontSize: "14px" };
const btnPrimary = { background: "linear-gradient(135deg, #ee0979, #ff6a00)", border: "none", borderRadius: "10px", color: "white", padding: "10px 20px", cursor: "pointer", fontWeight: "600" };

function Credits() {
  const [credits, setCredits] = useState([]);
  const [customerId, setCustomerId] = useState("");
  const [amount, setAmount] = useState("");
  const [reason, setReason] = useState("");
  const [message, setMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const token = localStorage.getItem("token");

  const loadCredits = () => {
    fetch("http://127.0.0.1:8000/ops/credits/", {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => r.json())
      .then((data) => { if (Array.isArray(data)) setCredits(data); else setCredits([]); })
      .catch(() => setCredits([]));
  };

  useEffect(() => { loadCredits(); }, []);

  const createCredit = () => {
    if (!customerId) { setMessage("Please enter a Customer ID."); return; }
    if (!amount || parseInt(amount) <= 0) { setMessage("Please enter a valid amount in cents."); return; }
    if (!reason) { setMessage("Please enter a reason for this credit."); return; }

    // Confirm before money-moving action
    if (!window.confirm(`Issue credit of $${(parseInt(amount) / 100).toFixed(2)} to customer ${customerId}?\nReason: ${reason}`)) return;

    setSubmitting(true);
    // Generate idempotency key per submission to prevent double-click
    const idempotencyKey = `credit-${Date.now()}-${Math.random().toString(36).slice(2)}`;

    fetch(`http://127.0.0.1:8000/ops/customers/${customerId}/credits/`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ amount_cents: parseInt(amount), reason, idempotency_key: idempotencyKey }),
    })
      .then((r) => r.json())
      .then((data) => {
        if (data.id) {
          setMessage(`Credit of $${(parseInt(amount) / 100).toFixed(2)} issued successfully.`);
          setCustomerId(""); setAmount(""); setReason("");
          loadCredits();
        } else { setMessage(JSON.stringify(data)); }
      })
      .catch((err) => setMessage("Error: " + err.message))
      .finally(() => setSubmitting(false));
  };

  return (
    <div>
      <h3 style={{ fontWeight: "700", marginBottom: "20px" }}>Credits</h3>

      {message && (
        <div style={{ background: "#f0fff4", border: "1px solid #9ae6b4", borderRadius: "10px", padding: "12px 16px", marginBottom: "16px", color: "#276749" }}>
          {message}
        </div>
      )}

      <div style={{ ...cardStyle, padding: "24px", marginBottom: "24px" }}>
        <h5 style={{ fontWeight: "700", marginBottom: "4px" }}>Issue Credit</h5>
        <p style={{ color: "#888", fontSize: "13px", marginBottom: "16px" }}>Credits reduce the customer next invoice total. This action is logged and cannot be undone.</p>
        <input style={inputStyle} type="text" placeholder="Customer ID" value={customerId} onChange={(e) => setCustomerId(e.target.value)} />
        <input style={inputStyle} type="number" placeholder="Amount in cents (e.g. 500 = $5.00)" value={amount} onChange={(e) => setAmount(e.target.value)} />
        <input style={inputStyle} type="text" placeholder="Reason (required)" value={reason} onChange={(e) => setReason(e.target.value)} />
        <button style={{ ...btnPrimary, opacity: submitting ? 0.6 : 1 }} onClick={createCredit} disabled={submitting}>
          {submitting ? "Issuing..." : "Issue Credit"}
        </button>
      </div>

      <div style={{ ...cardStyle, overflow: "hidden" }}>
        <div style={{ padding: "20px 24px", borderBottom: "1px solid #eee", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h5 style={{ fontWeight: "700", margin: 0 }}>All Credits</h5>
          <span style={{ background: "linear-gradient(135deg, #ee0979, #ff6a00)", color: "white", padding: "4px 14px", borderRadius: "20px", fontSize: "0.85rem", fontWeight: "600" }}>
            {credits.length} total
          </span>
        </div>
        {credits.length === 0 ? (
          <p style={{ padding: "24px", color: "#888", textAlign: "center" }}>No credits issued yet.</p>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ background: "linear-gradient(135deg, #ee0979, #ff6a00)", color: "white" }}>
                <th style={{ padding: "14px 16px", textAlign: "left" }}>Customer</th>
                <th style={{ padding: "14px 16px", textAlign: "left" }}>Amount</th>
                <th style={{ padding: "14px 16px", textAlign: "left" }}>Reason</th>
                <th style={{ padding: "14px 16px", textAlign: "left" }}>Issued by</th>
                <th style={{ padding: "14px 16px", textAlign: "left" }}>Date</th>
              </tr>
            </thead>
            <tbody>
              {credits.map((c, i) => (
                <tr key={c.id} style={{ background: i % 2 === 0 ? "#f9f9f9" : "white", borderBottom: "1px solid #eee" }}>
                  <td style={{ padding: "12px 16px" }}>
                    <span style={{ background: "linear-gradient(135deg, #667eea, #764ba2)", color: "white", padding: "3px 10px", borderRadius: "20px", fontSize: "12px", fontWeight: "600" }}>
                      {c.customer_name}
                    </span>
                  </td>
                  <td style={{ padding: "12px 16px", fontWeight: "700", color: "#11998e" }}>${(c.amount_cents / 100).toFixed(2)}</td>
                  <td style={{ padding: "12px 16px", color: "#555", fontSize: "13px" }}>{c.reason}</td>
                  <td style={{ padding: "12px 16px", color: "#888", fontSize: "12px" }}>{c.actor || "ops"}</td>
                  <td style={{ padding: "12px 16px", color: "#888", fontSize: "12px" }}>{c.created_at?.slice(0, 10)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

export default Credits;
