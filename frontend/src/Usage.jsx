import { useEffect, useState } from "react";
import { Chart as ChartJS, CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend } from "chart.js";
import { Line } from "react-chartjs-2";

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend);

const cardStyle = { borderRadius: "15px", border: "none", boxShadow: "0 4px 15px rgba(0,0,0,0.1)", background: "white" };
const inputStyle = { borderRadius: "10px", border: "1px solid #e0e0e0", padding: "10px 14px", width: "100%", marginBottom: "10px", boxSizing: "border-box" };
const btnPrimary = { background: "linear-gradient(135deg, #667eea, #764ba2)", border: "none", borderRadius: "10px", color: "white", padding: "10px 20px", cursor: "pointer", fontWeight: "600" };
const btnWarning = { background: "linear-gradient(135deg, #f7971e, #ffd200)", border: "none", borderRadius: "8px", color: "white", padding: "6px 14px", cursor: "pointer", fontWeight: "600", marginRight: "6px" };
const btnDanger = { background: "linear-gradient(135deg, #ee0979, #ff6a00)", border: "none", borderRadius: "8px", color: "white", padding: "6px 14px", cursor: "pointer", fontWeight: "600" };
const btnSuccess = { background: "linear-gradient(135deg, #11998e, #38ef7d)", border: "none", borderRadius: "8px", color: "white", padding: "6px 14px", cursor: "pointer", fontWeight: "600", marginRight: "6px" };
const btnSecondary = { background: "#6c757d", border: "none", borderRadius: "8px", color: "white", padding: "6px 14px", cursor: "pointer", fontWeight: "600" };

function Usage() {
  const [usageEvents, setUsageEvents] = useState([]);
  const [requestId, setRequestId] = useState("");
  const [customerId, setCustomerId] = useState("");
  const [endpoint, setEndpoint] = useState("");
  const [unitsConsumed, setUnitsConsumed] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [message, setMessage] = useState("");
  const [editingId, setEditingId] = useState(null);
  const [editEndpoint, setEditEndpoint] = useState("");
  const [editUnits, setEditUnits] = useState("");

  const token = localStorage.getItem("token");

  const chartData = {
    labels: usageEvents.slice(0, 5).map((e) => e.request_id.slice(0, 8)),
    datasets: [{
      label: "Units Consumed",
      data: usageEvents.slice(0, 5).map((e) => e.units_consumed),
      borderColor: "#667eea",
      backgroundColor: "rgba(102,126,234,0.1)",
      tension: 0.4,
      pointBackgroundColor: "#764ba2",
      pointRadius: 6,
    }],
  };

  const loadUsageEvents = () => {
    fetch("http://127.0.0.1:8000/v1/usage/?page_size=5", {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => r.json())
      .then((data) => {
        if (data && Array.isArray(data.results)) setUsageEvents(data.results);
        else if (Array.isArray(data)) setUsageEvents(data);
        else setUsageEvents([]);
      })
      .catch(() => setUsageEvents([]));
  };

  const createUsageEvent = () => {
    if (!apiKey) { setMessage("Please enter your API Key."); return; }
    if (!requestId) { setMessage("Please enter a Request ID."); return; }
    fetch("http://127.0.0.1:8000/v1/events/", {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `ApiKey ${apiKey}` },
      body: JSON.stringify({ request_id: requestId, customer_id: customerId, endpoint, units_consumed: parseInt(unitsConsumed) }),
    })
      .then((r) => r.json())
      .then((data) => { setMessage(JSON.stringify(data)); loadUsageEvents(); setRequestId(""); setEndpoint(""); setUnitsConsumed(""); })
      .catch((err) => setMessage("Error: " + err.message));
  };

  const deleteUsageEvent = (reqId) => {
    if (!window.confirm(`Delete this event?`)) return;
    fetch(`http://127.0.0.1:8000/v1/events/${reqId}/`, {
      method: "DELETE", headers: { Authorization: `Bearer ${token}` },
    })
      .then((r) => { if (r.ok) { setMessage("🗑️ Event deleted!"); loadUsageEvents(); } });
  };

  const startEdit = (e) => { setEditingId(e.request_id); setEditEndpoint(e.endpoint); setEditUnits(e.units_consumed); };

  const saveEdit = (reqId) => {
    fetch(`http://127.0.0.1:8000/v1/events/${reqId}/`, {
      method: "PUT",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify({ endpoint: editEndpoint, units_consumed: parseInt(editUnits) }),
    })
      .then((r) => r.json())
      .then((data) => { if (data.request_id || data.endpoint) { setEditingId(null); setMessage("✅ Event updated!"); loadUsageEvents(); } });
  };

  useEffect(() => { loadUsageEvents(); }, []);

  return (
    <div>
      <h3 style={{ fontWeight: "700", marginBottom: "20px" }}>📊 Usage Events</h3>

      {usageEvents.length > 0 && (
        <div style={{ ...cardStyle, padding: "24px", marginBottom: "24px" }}>
          <h5 style={{ fontWeight: "700", marginBottom: "16px" }}>📈 Units Consumed Chart</h5>
          <Line data={chartData} />
        </div>
      )}

      {message && (
        <div style={{ background: "#f0fff4", border: "1px solid #9ae6b4", borderRadius: "10px", padding: "12px 16px", marginBottom: "16px", color: "#276749" }}>
          {message}
        </div>
      )}

      <div style={{ ...cardStyle, padding: "24px", marginBottom: "24px" }}>
        <h5 style={{ fontWeight: "700", marginBottom: "16px" }}>➕ Create Usage Event</h5>
        <input style={inputStyle} type="text" placeholder="API Key" value={apiKey} onChange={(e) => setApiKey(e.target.value)} />
        <input style={inputStyle} type="text" placeholder="Request ID (unique)" value={requestId} onChange={(e) => setRequestId(e.target.value)} />
        <input style={inputStyle} type="text" placeholder="Customer ID (optional)" value={customerId} onChange={(e) => setCustomerId(e.target.value)} />
        <input style={inputStyle} type="text" placeholder="Endpoint (e.g. /api/search)" value={endpoint} onChange={(e) => setEndpoint(e.target.value)} />
        <input style={inputStyle} type="number" placeholder="Units Consumed" value={unitsConsumed} onChange={(e) => setUnitsConsumed(e.target.value)} />
        <button style={btnPrimary} onClick={createUsageEvent}>Create Event</button>
      </div>

      <div style={{ ...cardStyle, overflow: "hidden" }}>
        <div style={{ padding: "20px 24px", borderBottom: "1px solid #eee" }}>
          <h5 style={{ fontWeight: "700", margin: 0 }}>📋 Latest 5 Events</h5>
        </div>
        {usageEvents.length === 0 ? (
          <p style={{ padding: "24px", color: "#888" }}>No usage events yet.</p>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ background: "linear-gradient(135deg, #11998e, #38ef7d)", color: "white" }}>
                <th style={{ padding: "14px 16px", textAlign: "left" }}>Request ID</th>
                <th style={{ padding: "14px 16px", textAlign: "left" }}>Endpoint</th>
                <th style={{ padding: "14px 16px", textAlign: "left" }}>Units</th>
                <th style={{ padding: "14px 16px", textAlign: "left" }}>Timestamp</th>
                <th style={{ padding: "14px 16px", textAlign: "left" }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {usageEvents.map((event, i) => (
                <tr key={i} style={{ background: i % 2 === 0 ? "#f9f9f9" : "white", borderBottom: "1px solid #eee" }}>
                  <td style={{ padding: "12px 16px", fontSize: "0.72rem", color: "#888" }}>{event.request_id.slice(0, 16)}...</td>
                  <td style={{ padding: "12px 16px" }}>
                    {editingId === event.request_id ? <input style={{ ...inputStyle, marginBottom: 0 }} value={editEndpoint} onChange={(e) => setEditEndpoint(e.target.value)} /> : event.endpoint}
                  </td>
                  <td style={{ padding: "12px 16px", fontWeight: "600" }}>
                    {editingId === event.request_id ? <input type="number" style={{ ...inputStyle, marginBottom: 0 }} value={editUnits} onChange={(e) => setEditUnits(e.target.value)} /> : event.units_consumed}
                  </td>
                  <td style={{ padding: "12px 16px", fontSize: "0.8rem", color: "#666" }}>{event.timestamp.slice(0, 19).replace("T", " ")}</td>
                  <td style={{ padding: "12px 16px" }}>
                    {editingId === event.request_id ? (
                      <><button style={btnSuccess} onClick={() => saveEdit(event.request_id)}>Save</button><button style={btnSecondary} onClick={() => setEditingId(null)}>Cancel</button></>
                    ) : (
                      <><button style={btnWarning} onClick={() => startEdit(event)}>Edit</button><button style={btnDanger} onClick={() => deleteUsageEvent(event.request_id)}>Delete</button></>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

export default Usage;