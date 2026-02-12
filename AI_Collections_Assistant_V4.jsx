import { useState, useEffect, useRef } from "react";

const CUSTOMER = { name: "Rajesh Kumar Sharma", mobile: "XXXX-XXX-210", email: "r***a@gmail.com", agreementId: "PL-2024-00847391", loanType: "Personal Loan" };
const LOAN = { amount: "₹8,50,000", tenure: "48 months", emiStart: "15-Mar-2023", emiEnd: "15-Feb-2027", outstanding: "₹4,85,320", overdue: "₹73,800" };
const ADDITIONAL = { installmentNo: "22 of 48", dueDate: "15-Jan-2026", amount: "₹18,450", bounceCharges: "₹1,500", penalCharges: "₹3,240", dpd: 67 };
const PAST_COMMS = [
  { date: "28-Jan-2026", caller: "Priya M.", summary: "Requested callback. Job change affecting payments." },
  { date: "15-Jan-2026", caller: "Amit R.", summary: "No answer. SMS sent with payment link." },
  { date: "02-Jan-2026", caller: "Priya M.", summary: "₹10,000 promised by Jan 10. Not received." },
];

const TRANSCRIPT_FEED = [
  { speaker: "agent", text: "Good morning, am I speaking with Mr. Rajesh Kumar?", ts: "0:05", sentiment: "neutral" },
  { speaker: "customer", text: "Yes, who is this?", ts: "0:08", sentiment: "neutral" },
  { speaker: "agent", text: "Sir, this is regarding your personal loan account ending 391. Your EMI of ₹18,450 is overdue by 67 days.", ts: "0:14", sentiment: "neutral" },
  { speaker: "customer", text: "I know about it. I changed my job recently and there was a gap in salary.", ts: "0:22", sentiment: "negative" },
  { speaker: "agent", text: "I understand sir. We have some options that can help you. Would you like to hear them?", ts: "0:30", sentiment: "neutral" },
  { speaker: "customer", text: "Yes, please tell me. I want to clear this but the total amount is too much at once.", ts: "0:38", sentiment: "positive" },
  { speaker: "agent", text: "Sir, your total overdue is ₹73,800. I can offer a restructured payment plan.", ts: "0:45", sentiment: "neutral" },
  { speaker: "customer", text: "What kind of plan? Can I pay in parts?", ts: "0:50", sentiment: "positive" },
  { speaker: "agent", text: "Yes sir. You can pay ₹25,000 now, ₹25,000 by Feb 15, and ₹23,800 by March 1.", ts: "0:58", sentiment: "neutral" },
  { speaker: "customer", text: "That sounds reasonable. I can do ₹25,000 by this Friday.", ts: "1:05", sentiment: "positive" },
];

const AI_INSIGHTS_FEED = [
  { type: "intent", text: "Customer willing to pay but needs flexible plan", time: "0:38", priority: "high" },
  { type: "suggestion", text: "Offer 3-part: ₹25K now + ₹25K by Feb 15 + ₹23.8K by Mar 1", time: "0:45", priority: "high" },
  { type: "policy", text: "Eligible 50% penalty waiver (saves ₹1,620). Threshold: ₹50K+ commitment", time: "0:46", priority: "medium" },
  { type: "alert", text: "Previous broken PTP Jan 10 — secure firm date commitment", time: "0:52", priority: "high" },
  { type: "sentiment", text: "Tone shifted cooperative after plan offer", time: "1:05", priority: "low" },
];

const DISP_AUTO = { result: "PTP — Promise to Pay", date: "2026-02-07", amount: "₹25,000", reason: "Customer agreed to 3-part plan. First ₹25,000 by Fri Feb 7. Job change caused gap. Cooperative after restructuring. Penalty waiver discussed." };

const T = {
  bg: "#F4F6F8", surface: "#FFFFFF", navy: "#0C1E35",
  teal: "#0891B2", tealLight: "#22D3EE", tealMuted: "#E0F7FA",
  accent: "#059669", accentLight: "#D1FAE5",
  warm: "#D97706", warmLight: "#FEF3C7",
  red: "#DC2626", redLight: "#FEE2E2",
  green: "#16A34A", greenLight: "#DCFCE7",
  amber: "#D97706", amberLight: "#FEF3C7",
  text: "#1E293B", textSec: "#64748B", textMuted: "#94A3B8",
  border: "#E2E8F0", borderLight: "#F1F5F9",
};

const SC = { positive: { b: T.green, bg: "#F0FDF4" }, neutral: { b: T.amber, bg: "#FFFBEB" }, negative: { b: T.red, bg: "#FEF2F2" } };

export default function App() {
  const [callTime, setCallTime] = useState(0);
  const [callActive, setCallActive] = useState(true);
  const [transcripts, setTranscripts] = useState([]);
  const [insights, setInsights] = useState([]);
  const [dR, setDR] = useState("");
  const [dD, setDD] = useState("");
  const [dA, setDA] = useState("");
  const [dN, setDN] = useState("");
  const [dSaved, setDSaved] = useState(false);
  const [dAuto, setDAuto] = useState(false);
  const tRef = useRef(null);

  useEffect(() => { if (!callActive) return; const t = setInterval(() => setCallTime(p => p + 1), 1000); return () => clearInterval(t); }, [callActive]);
  useEffect(() => { TRANSCRIPT_FEED.forEach((item, i) => { setTimeout(() => { setTranscripts(prev => [...prev, item]); if (tRef.current) tRef.current.scrollTop = tRef.current.scrollHeight; }, (i + 1) * 2000); }); }, []);
  useEffect(() => { AI_INSIGHTS_FEED.forEach((item, i) => { setTimeout(() => setInsights(prev => [...prev, item]), (i + 1) * 2800 + 1500); }); }, []);
  useEffect(() => { if (transcripts.length >= 8 && !dAuto) { setDAuto(true); setDR(DISP_AUTO.result); setTimeout(() => setDD(DISP_AUTO.date), 400); setTimeout(() => setDA(DISP_AUTO.amount), 800); setTimeout(() => setDN(DISP_AUTO.reason), 1200); } }, [transcripts, dAuto]);

  const fmt = s => `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
  const inp = { width: "100%", padding: "4px 7px", fontSize: "11px", border: `1px solid ${T.border}`, borderRadius: "4px", color: T.text, background: T.surface, outline: "none", boxSizing: "border-box", transition: "all 0.3s" };
  const ag = dAuto ? { borderColor: T.accent, boxShadow: `0 0 0 1px ${T.accentLight}`, background: "#FAFFFE" } : {};

  // Inline data cell for ultra-compact top sections
  const Cell = ({ l, v, hl, tag }) => (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "1px 0", lineHeight: "1.3" }}>
      <span style={{ fontSize: "10.5px", color: T.textSec }}>{l}</span>
      <div style={{ display: "flex", alignItems: "center", gap: "4px" }}>
        {tag && <span style={{ fontSize: "7px", fontWeight: 700, padding: "0 4px", borderRadius: "2px", background: tag.bg, color: tag.c }}>{tag.t}</span>}
        <span style={{ fontSize: "10.5px", fontWeight: hl ? 700 : 600, color: hl ? T.red : T.text, fontVariantNumeric: "tabular-nums" }}>{v}</span>
      </div>
    </div>
  );

  return (
    <div style={{ width: "100vw", height: "100vh", display: "flex", flexDirection: "column", background: T.bg, fontFamily: "'DM Sans', sans-serif", overflow: "hidden" }}>
      <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap" rel="stylesheet" />

      {/* HEADER — 38px */}
      <header style={{ background: `linear-gradient(135deg, ${T.navy}, #164E63)`, padding: "0 14px", height: "38px", display: "flex", alignItems: "center", justifyContent: "space-between", flexShrink: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <span style={{ fontSize: "15px" }}>🤖</span>
          <span style={{ color: "#FFF", fontSize: "12px", fontWeight: 700 }}>AI Collections Assistant</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "8px", background: "rgba(217,119,6,0.15)", padding: "3px 12px", borderRadius: "3px", border: "1px solid rgba(217,119,6,0.3)" }}>
          <span style={{ fontSize: "8px", fontWeight: 700, color: T.warm, textTransform: "uppercase" }}>Action:</span>
          <span style={{ fontSize: "10px", fontWeight: 700, color: "#FDE68A" }}>Follow-up Call</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "12px", background: "rgba(255,255,255,0.07)", padding: "3px 14px", borderRadius: "16px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "4px" }}>
            <span className={callActive ? "live-dot" : ""} style={{ width: "6px", height: "6px", borderRadius: "50%", background: callActive ? "#22C55E" : T.textMuted }} />
            <span style={{ color: "#FFF", fontSize: "9px", fontWeight: 600 }}>{callActive ? "ON CALL" : "IDLE"}</span>
          </div>
          <span style={{ color: T.tealLight, fontSize: "13px", fontWeight: 700, fontVariantNumeric: "tabular-nums" }}>{fmt(callTime)}</span>
          <span style={{ color: "#FFF", fontSize: "9px" }}>📞 {CUSTOMER.mobile}</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          {[["LMS"], ["LiveKit"]].map(([n]) => <div key={n} style={{ display: "flex", alignItems: "center", gap: "3px" }}><span style={{ width: "5px", height: "5px", borderRadius: "50%", background: "#22C55E" }} /><span style={{ color: T.textMuted, fontSize: "8px" }}>{n}</span></div>)}
          <button onClick={() => setCallActive(!callActive)} style={{ padding: "3px 12px", borderRadius: "4px", border: "none", cursor: "pointer", fontSize: "9px", fontWeight: 700, color: "#FFF", background: callActive ? T.red : T.accent }}>{callActive ? "End Call" : "New Call"}</button>
        </div>
      </header>

      {/* BODY */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", padding: "4px 6px", gap: "4px", overflow: "hidden" }}>

        {/* ═══ TOP STATIC — ultra compact ═══ */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "4px", flexShrink: 0 }}>
          {/* Customer */}
          <div style={{ background: T.surface, borderRadius: "4px", border: `1px solid ${T.border}`, overflow: "hidden" }}>
            <div style={{ padding: "3px 8px", background: T.borderLight, borderBottom: `1px solid ${T.border}`, display: "flex", alignItems: "center", gap: "5px" }}>
              <span style={{ fontSize: "10px" }}>👤</span>
              <span style={{ fontSize: "9.5px", fontWeight: 700, color: T.navy, textTransform: "uppercase", letterSpacing: "0.3px" }}>Customer Details</span>
            </div>
            <div style={{ padding: "3px 8px" }}>
              <Cell l="Name" v={CUSTOMER.name} />
              <Cell l="Mobile" v={CUSTOMER.mobile} />
              <Cell l="Email" v={CUSTOMER.email} />
              <Cell l="Agreement ID" v={CUSTOMER.agreementId} />
              <Cell l="Loan Type" v={CUSTOMER.loanType} tag={{ t: "PL", bg: T.tealMuted, c: T.teal }} />
            </div>
          </div>
          {/* Loan */}
          <div style={{ background: T.surface, borderRadius: "4px", border: `1px solid ${T.border}`, overflow: "hidden" }}>
            <div style={{ padding: "3px 8px", background: T.borderLight, borderBottom: `1px solid ${T.border}`, display: "flex", alignItems: "center", gap: "5px" }}>
              <span style={{ fontSize: "10px" }}>💰</span>
              <span style={{ fontSize: "9.5px", fontWeight: 700, color: T.navy, textTransform: "uppercase", letterSpacing: "0.3px" }}>Loan Details</span>
            </div>
            <div style={{ padding: "3px 8px" }}>
              <Cell l="Loan Amount" v={LOAN.amount} />
              <Cell l="Tenure" v={LOAN.tenure} />
              <Cell l="EMI Start" v={LOAN.emiStart} />
              <Cell l="EMI End" v={LOAN.emiEnd} />
              <Cell l="Total Outstanding" v={LOAN.outstanding} hl />
              <Cell l="Total Overdue" v={LOAN.overdue} hl />
            </div>
          </div>
          {/* Additional */}
          <div style={{ background: T.surface, borderRadius: "4px", border: `1px solid ${T.border}`, overflow: "hidden" }}>
            <div style={{ padding: "3px 8px", background: T.borderLight, borderBottom: `1px solid ${T.border}`, display: "flex", alignItems: "center", gap: "5px" }}>
              <span style={{ fontSize: "10px" }}>📋</span>
              <span style={{ fontSize: "9.5px", fontWeight: 700, color: T.navy, textTransform: "uppercase", letterSpacing: "0.3px" }}>Additional Details</span>
            </div>
            <div style={{ padding: "3px 8px" }}>
              <Cell l="Installment No." v={ADDITIONAL.installmentNo} />
              <Cell l="Due Date" v={ADDITIONAL.dueDate} />
              <Cell l="Amount" v={`₹${ADDITIONAL.amount}`} />
              <Cell l="Bounce Charges" v={`₹${ADDITIONAL.bounceCharges}`} />
              <Cell l="Penal Charges" v={`₹${ADDITIONAL.penalCharges}`} />
              <Cell l="DPD" v={ADDITIONAL.dpd} hl tag={{ t: "HIGH", bg: T.redLight, c: T.red }} />
            </div>
          </div>
        </div>

        {/* Past Comms — single compact strip */}
        <div style={{ background: T.surface, borderRadius: "4px", border: `1px solid ${T.border}`, overflow: "hidden", flexShrink: 0 }}>
          <div style={{ display: "grid", gridTemplateColumns: "90px 70px 1fr", fontSize: "10px" }}>
            <div style={{ padding: "2px 8px", fontWeight: 700, color: T.textSec, background: T.borderLight, borderBottom: `1px solid ${T.border}`, borderRight: `1px solid ${T.borderLight}`, display: "flex", alignItems: "center", gap: "4px" }}>
              <span style={{ fontSize: "9px" }}>📞</span> Date
            </div>
            <div style={{ padding: "2px 6px", fontWeight: 700, color: T.textSec, background: T.borderLight, borderBottom: `1px solid ${T.border}`, borderRight: `1px solid ${T.borderLight}` }}>Caller</div>
            <div style={{ padding: "2px 6px", fontWeight: 700, color: T.textSec, background: T.borderLight, borderBottom: `1px solid ${T.border}` }}>Summary</div>
            {PAST_COMMS.map((c, i) => (
              <React.Fragment key={i}>
                <div style={{ padding: "2px 8px", color: T.text, fontVariantNumeric: "tabular-nums", borderBottom: i < 2 ? `1px solid ${T.borderLight}` : "none", borderRight: `1px solid ${T.borderLight}` }}>{c.date}</div>
                <div style={{ padding: "2px 6px", color: T.teal, fontWeight: 600, borderBottom: i < 2 ? `1px solid ${T.borderLight}` : "none", borderRight: `1px solid ${T.borderLight}` }}>{c.caller}</div>
                <div style={{ padding: "2px 6px", color: T.textSec, borderBottom: i < 2 ? `1px solid ${T.borderLight}` : "none" }}>{c.summary}</div>
              </React.Fragment>
            ))}
          </div>
        </div>

        {/* ═══ BOTTOM DYNAMIC — max space ═══ */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "4px", flex: 1, minHeight: 0 }}>

          {/* TRANSCRIPT */}
          <div style={{ background: T.surface, borderRadius: "4px", border: `1px solid ${T.border}`, display: "flex", flexDirection: "column", overflow: "hidden" }}>
            <div style={{ padding: "3px 8px", background: T.borderLight, borderBottom: `1px solid ${T.border}`, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "5px" }}>
                <span style={{ fontSize: "10px" }}>🎙️</span>
                <span style={{ fontSize: "9.5px", fontWeight: 700, color: T.navy, textTransform: "uppercase" }}>Transcript</span>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                {[["🟢", "Positive"], ["🟡", "Neutral"], ["🔴", "Negative"]].map(([d, l]) => (
                  <div key={l} style={{ display: "flex", alignItems: "center", gap: "2px" }}>
                    <span style={{ fontSize: "7px" }}>{d}</span>
                    <span style={{ fontSize: "7.5px", color: T.textMuted }}>{l}</span>
                  </div>
                ))}
                {callActive && <span className="live-dot" style={{ marginLeft: "4px" }} />}
              </div>
            </div>
            <div ref={tRef} style={{ flex: 1, overflowY: "auto", padding: "4px 6px", scrollBehavior: "smooth" }}>
              {transcripts.length === 0 && <div style={{ textAlign: "center", padding: "12px 0", color: T.textMuted, fontSize: "10px" }}>Waiting for conversation...</div>}
              {transcripts.map((t, i) => {
                const s = SC[t.sentiment] || SC.neutral;
                return (
                  <div key={i} style={{ marginBottom: "4px", display: "flex", gap: "5px", animation: "fadeIn 0.3s" }}>
                    <div style={{ width: "3px", borderRadius: "1px", flexShrink: 0, background: s.b }} />
                    <div style={{
                      width: "18px", height: "18px", borderRadius: "50%", flexShrink: 0,
                      background: t.speaker === "agent" ? T.teal : T.warm,
                      display: "flex", alignItems: "center", justifyContent: "center",
                      fontSize: "8px", color: "#FFF", fontWeight: 700, marginTop: "1px",
                    }}>{t.speaker === "agent" ? "A" : "C"}</div>
                    <div style={{ flex: 1 }}>
                      <div style={{ display: "flex", justifyContent: "space-between" }}>
                        <span style={{ fontSize: "8px", fontWeight: 700, textTransform: "uppercase", color: t.speaker === "agent" ? T.teal : T.warm }}>{t.speaker === "agent" ? "Agent" : "Customer"}</span>
                        <span style={{ fontSize: "7.5px", color: T.textMuted }}>{t.ts}</span>
                      </div>
                      <div style={{
                        fontSize: "10px", color: T.text, lineHeight: "1.35",
                        background: s.bg, padding: "3px 6px", borderRadius: "4px",
                        borderLeft: `2px solid ${s.b}`,
                      }}>{t.text}</div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* AI INSIGHTS */}
          <div style={{ background: T.surface, borderRadius: "4px", border: `1px solid ${T.border}`, display: "flex", flexDirection: "column", overflow: "hidden" }}>
            <div style={{ padding: "3px 8px", background: T.borderLight, borderBottom: `1px solid ${T.border}`, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "5px" }}>
                <span style={{ fontSize: "10px" }}>🧠</span>
                <span style={{ fontSize: "9.5px", fontWeight: 700, color: T.navy, textTransform: "uppercase" }}>AI Insights</span>
              </div>
              {callActive && <span className="live-dot" />}
            </div>
            <div style={{ flex: 1, overflowY: "auto", padding: "4px 6px" }}>
              {insights.length === 0 && <div style={{ textAlign: "center", padding: "12px 0", color: T.textMuted, fontSize: "10px" }}>AI analyzing conversation...</div>}
              {insights.map((ins, i) => {
                const cfg = {
                  intent: { icon: "🎯", label: "INTENT", color: T.teal, bg: T.tealMuted },
                  suggestion: { icon: "💡", label: "SUGGESTION", color: T.accent, bg: T.accentLight },
                  policy: { icon: "📜", label: "POLICY", color: T.warm, bg: T.warmLight },
                  sentiment: { icon: "😊", label: "SENTIMENT", color: T.textSec, bg: T.borderLight },
                  alert: { icon: "⚠️", label: "ALERT", color: T.red, bg: T.redLight },
                }[ins.type];
                return (
                  <div key={i} style={{
                    marginBottom: "4px", padding: "5px 7px", borderRadius: "4px",
                    background: cfg.bg, borderLeft: `3px solid ${cfg.color}`,
                    animation: "fadeIn 0.3s",
                  }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1px" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: "3px" }}>
                        <span style={{ fontSize: "9px" }}>{cfg.icon}</span>
                        <span style={{ fontSize: "7.5px", fontWeight: 700, color: cfg.color, textTransform: "uppercase", letterSpacing: "0.3px" }}>{cfg.label}</span>
                      </div>
                      <div style={{ display: "flex", alignItems: "center", gap: "3px" }}>
                        {ins.priority === "high" && <span style={{ fontSize: "7px", fontWeight: 700, padding: "0 3px", borderRadius: "2px", background: T.red, color: "#FFF" }}>HIGH</span>}
                        <span style={{ fontSize: "7.5px", color: T.textMuted }}>{ins.time}</span>
                      </div>
                    </div>
                    <div style={{ fontSize: "10px", color: T.text, lineHeight: "1.35" }}>{ins.text}</div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* DISPOSITION */}
          <div style={{ background: T.surface, borderRadius: "4px", border: `1px solid ${T.border}`, display: "flex", flexDirection: "column", overflow: "hidden" }}>
            <div style={{ padding: "3px 8px", background: T.borderLight, borderBottom: `1px solid ${T.border}`, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "5px" }}>
                <span style={{ fontSize: "10px" }}>✅</span>
                <span style={{ fontSize: "9.5px", fontWeight: 700, color: T.navy, textTransform: "uppercase" }}>Disposition</span>
              </div>
              {dAuto && <div style={{ display: "flex", alignItems: "center", gap: "3px", background: T.accentLight, padding: "1px 6px", borderRadius: "2px" }}>
                <span style={{ fontSize: "8px" }}>🤖</span>
                <span style={{ fontSize: "7.5px", fontWeight: 700, color: T.accent }}>AI AUTO-FILLED</span>
              </div>}
            </div>
            <div style={{ flex: 1, padding: "6px 8px", display: "flex", flexDirection: "column", gap: "6px" }}>
              <div>
                <label style={{ fontSize: "8px", fontWeight: 700, color: T.textSec, display: "block", marginBottom: "1px", textTransform: "uppercase", letterSpacing: "0.3px" }}>Result</label>
                <select value={dR} onChange={e => setDR(e.target.value)} style={{ ...inp, cursor: "pointer", ...ag }}>
                  <option value="">Select result...</option>
                  <option>PTP — Promise to Pay</option>
                  <option>Partial Payment</option>
                  <option>Settlement Agreed</option>
                  <option>Callback Requested</option>
                  <option>Refused to Pay</option>
                  <option>Dispute Raised</option>
                  <option>Not Reachable</option>
                  <option>Wrong Number</option>
                </select>
              </div>
              <div>
                <label style={{ fontSize: "8px", fontWeight: 700, color: T.textSec, display: "block", marginBottom: "1px", textTransform: "uppercase", letterSpacing: "0.3px" }}>Particulars — Date & Amount</label>
                <div style={{ display: "flex", gap: "4px" }}>
                  <input type="date" value={dD} onChange={e => setDD(e.target.value)} style={{ ...inp, flex: 1, ...ag }} />
                  <input value={dA} onChange={e => setDA(e.target.value)} style={{ ...inp, flex: 1, ...ag }} placeholder="₹ Amount" />
                </div>
              </div>
              <div style={{ flex: 1, display: "flex", flexDirection: "column" }}>
                <label style={{ fontSize: "8px", fontWeight: 700, color: T.textSec, display: "block", marginBottom: "1px", textTransform: "uppercase", letterSpacing: "0.3px" }}>Reason / Notes</label>
                <textarea value={dN} onChange={e => setDN(e.target.value)} placeholder="AI will auto-populate..." style={{ ...inp, flex: 1, resize: "none", minHeight: "30px", ...ag }} />
              </div>
              {dAuto && !dSaved && (
                <div style={{ padding: "3px 6px", background: T.accentLight, borderRadius: "3px", borderLeft: `2px solid ${T.accent}`, fontSize: "9px", color: T.accent }}>
                  ✓ AI auto-populated from conversation. Review & submit.
                </div>
              )}
              <button onClick={() => setDSaved(true)} style={{
                padding: "7px", borderRadius: "4px", border: "none", flexShrink: 0,
                background: dSaved ? T.accent : `linear-gradient(135deg, ${T.teal}, #164E63)`,
                color: "#FFF", fontSize: "10px", fontWeight: 700, cursor: "pointer", transition: "all 0.3s",
              }}>{dSaved ? "✓  Saved to LMS" : "Review & Submit to LMS"}</button>
            </div>
          </div>
        </div>
      </div>

      <style>{`
        @keyframes fadeIn { from { opacity: 0; transform: translateY(3px); } to { opacity: 1; transform: translateY(0); } }
        .live-dot { width: 6px; height: 6px; border-radius: 50%; background: #DC2626; animation: lp 1.5s infinite; }
        @keyframes lp { 0%,100% { opacity:1; box-shadow:0 0 0 0 rgba(220,38,38,0.4); } 50% { opacity:0.6; box-shadow:0 0 0 3px rgba(220,38,38,0); } }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        select:focus, input:focus, textarea:focus { border-color: ${T.teal} !important; box-shadow: 0 0 0 2px ${T.tealMuted}; }
        ::-webkit-scrollbar { width: 3px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: ${T.border}; border-radius: 2px; }
      `}</style>
    </div>
  );
}
