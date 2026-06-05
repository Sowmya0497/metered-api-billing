import { useState } from "react";

const cardStyle = { borderRadius: "15px", border: "none", boxShadow: "0 4px 15px rgba(0,0,0,0.1)", background: "white" };
const inputStyle = { borderRadius: "10px", border: "1px solid #e0e0e0", padding: "10px 14px", width: "100%", marginBottom: "10px", boxSizing: "border-box" };
const btnPrimary = { background: "linear-gradient(135deg, #f7971e, #ffd200)", border: "none", borderRadius: "10px", color: "white", padding: "10px 20px", cursor: "pointer", fontWeight: "600" };
const btnWarning = { background: "linear-gradient(135deg, #f7971e, #ffd200)", border: "none", borderRadius: "8px", color: "white", padding: "6px 14px", cursor: "pointer", fontWeight: "600", marginRight: "6px" };
const btnSuccess = { background: "linear-gradient(135deg, #11998e, #38ef7d)", border: "none", borderRadius: "8px", color: "white", padding: "6px 14px", cursor: "pointer", fontWeight: "600", marginRight: "6px" };
const btnSecondary = { background: "#6c757d", border: "none", borderRadius: "8px", color: "white", padding: "6px 14px", cursor: "pointer", fontWeight: "600" };

const statusColor = (s) => ({ PAID: "#38ef7d", DRAFT: "#ffd200", VOID: "#ff6a00", ISSUED: "#667eea" }[s] || "#667eea");

function Invoices() {
  const [invoices, setInvoices] = useState([]);
  const [customerId, setCustomerId] = useState("");
  const [message, setMessage] = useState("");
  const [selected, setSelected] = useState(null);
  const [lineItems, setLineItems] = useState([]);
  const [overrideId, setOverrideId] = useState(null);
  const [overrideAmount, setOverrideAmount] = useState("");
  const [overrideReason, setOverrideReason] = useState("");

  const token = localStorage.getItem("token");

  const loadInvoices = () => {
    if (!customerId) { setMessage("Please enter a Customer ID."); return; }
    fetch(`http://127.0.0.1:8000/v1/invoices/?customer_id=${customerId}`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => r.json())
      .then((data) => {
        if (Array.isArray(data)) { setInvoices(data); setMessage(""); }
        else setMessage(JSON.stringify(data));
      });
  };

  const loadDetail = (inv) => {
    fetch(`http://127.0.0.1:8000/v1/invoices/${inv.id}/`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => r.json())
      .then((data) => { setSelected(data); setLineItems(data.line_items || []); setOverrideId(null); });
  };

  const submitOverride = (invoiceId, lineItemId) => {
    if (!overrideAmount || !overrideReason) { setMessage("Amount and reason required for override."); return; }
    // Confirm before money-moving action
    if (!window.confirm(`Override line item to $${(parseInt(overrideAmount) / 100).toFixed(2)}? Reason: ${overrideReason}`)) return;
    fetch(`http://127.0.0.1:8000/ops/invoices/${invoiceId}/line-items/${lineItemId}/`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ amount_cents: parseInt(overrideAmount), reason: overrideReason }),
    })
      .then((r) => r.json())
      .then((data) => {
        if (data.id) {
          setMessage(`Line item overridden. New invoice total: $${(data.invoice_total_cents / 100).toFixed(2)}`);
          setOverrideId(null); setOverrideAmount(""); setOverrideReason("");
          loadDetail(selected);
          loadInvoices();
        } else { setMessage(JSON.stringify(data)); }
      });
  };

  return (
    <div>
      <h3 style={{ fontWeight: "700", marginBottom: "20px" }}>Invoices</h3>

      {message && (
        <div style={{ background: "#f0fff4", border: "1px solid #9ae6b4", borderRadius: "10px", padding: "12px 16px", marginBottom: "16px", color: "#276749" }}>
          {message}
        </div>
      )}

      <div style={{ ...cardStyle, padding: "24px", marginBottom: "24px" }}>
        <h5 style={{ fontWeight: "700", marginBottom: "16px" }}>Load Invoices</h5>
        <div style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: "12px" }}>
          <input style={{ ...inputStyle, marginBottom: 0 }} type="text" placeholder="Customer ID" value={customerId} onChange={(e) => setCustomerId(e.target.value)} onKeyDown={(e) => e.key === "Enter" && loadInvoices()} />
          <button style={btnPrimary} onClick={loadInvoices}>Load</button>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: selected ? "1fr 1fr" : "1fr", gap: "20px" }}>
        {invoices.length > 0 && (
          <div style={{ ...cardStyle, overflow: "hidden" }}>
            <div style={{ padding: "16px 24px", borderBottom: "1px solid #eee" }}>
              <h5 style={{ fontWeight: "700", margin: 0 }}>Invoice List</h5>
            </div>
            <table style={{ width: "100%", borderCollapse: "collapse" }}>
              <thead>
                <tr style={{ background: "linear-gradient(135deg, #f7971e, #ffd200)", color: "white" }}>
                  <th style={{ padding: "12px 16px", textAlign: "left" }}>Period</th>
                  <th style={{ padding: "12px 16px", textAlign: "left" }}>Amount</th>
                  <th style={{ padding: "12px 16px", textAlign: "left" }}>Status</th>
                </tr>
              </thead>
              <tbody>
                {invoices.map((inv, i) => (
                  <tr key={inv.id} onClick={() => loadDetail(inv)}
                    style={{ background: selected?.id === inv.id ? "#fff8e6" : i % 2 === 0 ? "#f9f9f9" : "white", borderBottom: "1px solid #eee", cursor: "pointer" }}>
                    <td style={{ padding: "12px 16px", fontSize: "0.8rem" }}>{inv.period_start.slice(0, 10)} to {inv.period_end.slice(0, 10)}</td>
                    <td style={{ padding: "12px 16px", fontWeight: "600" }}>${(inv.total_cents / 100).toFixed(2)}</td>
                    <td style={{ padding: "12px 16px" }}>
                      <span style={{ background: statusColor(inv.status), color: "white", padding: "3px 10px", borderRadius: "20px", fontSize: "11px", fontWeight: "600" }}>
                        {inv.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {selected && (
          <div style={{ ...cardStyle, padding: "24px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
              <h5 style={{ fontWeight: "700", margin: 0 }}>Invoice Detail</h5>
              <button style={btnSecondary} onClick={() => { setSelected(null); setLineItems([]); }}>Close</button>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px", marginBottom: "16px" }}>
              <div style={{ background: "#f9f9f9", padding: "10px", borderRadius: "8px" }}>
                <div style={{ fontSize: "11px", color: "#888" }}>Period</div>
                <div style={{ fontWeight: "600", fontSize: "13px" }}>{selected.period_start?.slice(0, 10)} to {selected.period_end?.slice(0, 10)}</div>
              </div>
              <div style={{ background: "#f9f9f9", padding: "10px", borderRadius: "8px" }}>
                <div style={{ fontSize: "11px", color: "#888" }}>Total</div>
                <div style={{ fontWeight: "700", fontSize: "18px" }}>${(selected.total_cents / 100).toFixed(2)}</div>
              </div>
            </div>

            <h6 style={{ fontWeight: "700", marginBottom: "10px" }}>Line Items</h6>
            {lineItems.map((li) => (
              <div key={li.id} style={{ border: "1px solid #eee", borderRadius: "10px", padding: "14px", marginBottom: "10px" }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "6px" }}>
                  <span style={{ fontSize: "13px" }}>{li.description}</span>
                  <span style={{ fontWeight: "700" }}>${(li.amount_cents / 100).toFixed(2)}</span>
                </div>
                <div style={{ fontSize: "12px", color: "#888", marginBottom: "8px" }}>
                  {li.units?.toLocaleString()} units
                  {li.is_overridden && <span style={{ background: "#ffd200", color: "white", padding: "2px 8px", borderRadius: "10px", marginLeft: "8px", fontSize: "11px" }}>OVERRIDDEN</span>}
                </div>

                {selected.status !== "PAID" && (
                  overrideId === li.id ? (
                    <div>
                      <input style={inputStyle} type="number" placeholder="New amount in cents" value={overrideAmount} onChange={(e) => setOverrideAmount(e.target.value)} />
                      <input style={inputStyle} type="text" placeholder="Reason (required)" value={overrideReason} onChange={(e) => setOverrideReason(e.target.value)} />
                      <button style={btnSuccess} onClick={() => submitOverride(selected.id, li.id)}>Confirm Override</button>
                      <button style={btnSecondary} onClick={() => { setOverrideId(null); setOverrideAmount(""); setOverrideReason(""); }}>Cancel</button>
                    </div>
                  ) : (
                    <button style={btnWarning} onClick={() => setOverrideId(li.id)}>Override Amount</button>
                  )
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default Invoices;
