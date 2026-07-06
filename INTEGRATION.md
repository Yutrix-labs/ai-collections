# AI Collections — API Integration Guide (for Frontend Team)

**Base URL:** `https://aiassistant.yutrix.io/collassistantapi`
**Auth:** every request must send the header `X-API-KEY: <key>` (key shared separately).
**Response envelope:** all REST responses are `{ "success": boolean, "message": string, "data": <T> }`.
A `200` with `success:false` is still a failure — check `success`, not just the HTTP status.
Missing/invalid key → `401 { "success": false, "message": "Missing or invalid API key", "data": null }`.

> Replace `YOUR_API_KEY` with the real key and `{sessionId}` with the value returned by
> `POST /call/start`. Sample test account: `PL-2024-00847392` / mobile `7838153987`.
> LiveKit tokens in the examples below are truncated (`eyJ...`) for readability.

---

## 1. Health check (no key required)

```bash
curl -s https://aiassistant.yutrix.io/collassistantapi/actuator/health
```
**Response** `200`:
```json
{ "status": "UP" }
```

## 2. Auth check — should FAIL with 401 (no key)

```bash
curl -i -s https://aiassistant.yutrix.io/collassistantapi/worklist
```
**Response** `401`:
```json
{ "success": false, "message": "Missing or invalid API key", "data": null }
```

## 3. GET /worklist — agent worklist

```bash
curl -s https://aiassistant.yutrix.io/collassistantapi/worklist \
  -H "X-API-KEY: YOUR_API_KEY"
```
**Response** `200` (`data` is an array; one item shown):
```json
{
  "success": true,
  "message": "Worklist retrieved successfully",
  "data": [
    {
      "agreementId": "PL-2024-00847392",
      "name": "Rajesh Kumar Sharma",
      "mobile": "XXXX-XXX-987",
      "loanType": "Personal Loan",
      "outstanding": "CHF 7,10,942",
      "overdue": "CHF 1,14,099",
      "dpd": 67,
      "priority": "HIGH",
      "lastContactDate": "12-Dec",
      "lastContactSummary": "Callback req. Job change.",
      "ptpBand": "Low",
      "paymentBand": "Medium"
    }
  ]
}
```

## 4. GET /customer/{agreementId} — customer + loan + history

```bash
curl -s https://aiassistant.yutrix.io/collassistantapi/customer/PL-2024-00847392 \
  -H "X-API-KEY: YOUR_API_KEY"
```
**Response** `200`:
```json
{
  "success": true,
  "message": "Success",
  "data": {
    "customer": {
      "name": "Rajesh Kumar Sharma", "mobile": "7838153987", "loanType": "Personal Loan",
      "agreementId": "PL-2024-00847392", "email": "r***a@gmail.com", "cifNumber": "CIF-98234571",
      "noOfAgreements": 3, "writeoff": "N", "legalProceedings": null, "noOfLiabilities": 3,
      "preferredLanguage": "hi"
    },
    "loan": {
      "amount": "CHF 8,00,000", "tenure": "24 months", "emiStart": "03/07/2021", "emiEnd": "03/07/2031",
      "outstanding": "CHF 7,10,942", "overdue": "CHF 1,14,099", "disbursementDate": "02/07/2025",
      "interestRate": "13.0", "installmentAmount": "CHF 38,033", "currentInstallmentNo": "5",
      "paymentMode": "ECS", "lastPaymentOn": "03/04/2025", "lastPaymentAmount": "CHF 76,066",
      "paymentDueDate": "03/12/2025"
    },
    "additionalDetails": {
      "installmentNo": "5 of 24", "dueDate": "03 Dec 2025", "amount": "CHF 1,14,099",
      "bounceCharges": "1,500", "penalCharges": "3,240", "dpd": 67, "profession": "Accountant"
    },
    "pastCommunications": [
      { "date": "12-Dec", "caller": "Priya M.", "summary": "Callback req. Job change.", "type": "Call" },
      { "date": "5-Dec", "caller": "Priya M.", "summary": "CHF 10K PTP Dec 10. Not rcvd.", "type": "Call" }
    ],
    "callBehaviour": { "callerBehaviour": "Professional, Firm", "customerBehaviour": "Polite, Defensive" }
  }
}
```

## 5. GET /ptp/predict/{agreementId} — promise-to-pay ML score

```bash
curl -s https://aiassistant.yutrix.io/collassistantapi/ptp/predict/PL-2024-00847392 \
  -H "X-API-KEY: YOUR_API_KEY"
```
**Response** `200`:
```json
{
  "success": true,
  "message": "PTP prediction retrieved",
  "data": {
    "probability": 0.36,
    "band": "Low",
    "fulfilled": false,
    "payment_probability_15d": { "probability": 0.41, "band": "Low" },
    "payment_probability_30d": { "probability": 0.54, "band": "Medium" }
  }
}
```

## 6. POST /call/start — start a call (customer data is PUSHED in the body)

Returns `sessionId` (used for all realtime topics), `meetUrl` (agent's LiveKit audio bridge),
`customerJoinUrl` (shareable customer link) and `roomName`. `customerData` is the full customer
record; optional (omit → demo data), but for a real integration you push the account's data here.

```bash
curl -s https://aiassistant.yutrix.io/collassistantapi/call/start \
  -H "X-API-KEY: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "agreementId": "PL-2024-00847392",
    "customerMobile": "7838153987",
    "customerData": {
      "customer": { "name": "Test User", "mobile": "7838153987", "agreementId": "PL-2024-00847392", "loanType": "Personal Loan", "writeoff": "N", "legalProceedings": null },
      "loan": { "outstanding": "CHF 1,20,000", "overdue": "CHF 40,000" },
      "additionalDetails": { "dpd": 45, "profession": "Business owner" },
      "paymentHistory": [ { "status": "Missed" }, { "status": "Partial" } ],
      "pastCommunications": [ { "date": "01-Jul", "caller": "Agent", "summary": "Broken PTP, amount not rcvd" } ],
      "callBehaviour": { "customerBehaviour": "evasive" }
    }
  }'
```
**Response** `200`:
```json
{
  "success": true,
  "message": "Call initiated",
  "data": {
    "sessionId": "bf43e881-ab8a-406a-8b71-333933666baf",
    "agreementId": "PL-2024-00847392",
    "customerMobile": "7838153987",
    "exotelCallSid": null,
    "status": "ACTIVE",
    "meetUrl": "https://meet.livekit.io/custom?liveKitUrl=wss%3A%2F%2F...&token=eyJ...",
    "customerJoinUrl": "https://meet.livekit.io/custom?liveKitUrl=wss%3A%2F%2F...&token=eyJ...",
    "roomName": "call-PL-2024-00847392",
    "recordingUrl": null,
    "startedAt": "2026-07-06T07:11:38.588772992",
    "endedAt": null,
    "customerContext": { "customer": { "…echoes the customerData you sent…" } },
    "dispositionResult": null, "dispositionDate": null, "dispositionAmount": null,
    "dispositionNotes": null, "dispositionNextAction": null, "dispositionReasonCode": null,
    "dispositionPaymentSchedule": null
  }
}
```

## 7. GET /call/{sessionId} — fetch current session state

```bash
curl -s https://aiassistant.yutrix.io/collassistantapi/call/{sessionId} \
  -H "X-API-KEY: YOUR_API_KEY"
```
**Response** `200`: same `CallSession` object as `/call/start` (reflects the latest `status`,
`endedAt`, and any `disposition*` fields once set).

## 8. GET /transcript/{sessionId} — transcript history (replay)

```bash
curl -s https://aiassistant.yutrix.io/collassistantapi/transcript/{sessionId} \
  -H "X-API-KEY: YOUR_API_KEY"
```
**Response** `200` (empty until turns arrive; live turns come over STOMP):
```json
{
  "success": true,
  "message": "Success",
  "data": [
    { "speaker": "customer", "text": "Hello", "ts": "07:11:40", "sentiment": "neutral" }
  ]
}
```

## 9. GET /transcript/{sessionId}/summary — conversation summary + insights

```bash
curl -s https://aiassistant.yutrix.io/collassistantapi/transcript/{sessionId}/summary \
  -H "X-API-KEY: YOUR_API_KEY"
```
**Response** `200`:
```json
{
  "success": true,
  "message": "Success",
  "data": { "summaryItems": [], "insightItems": [] }
}
```

## 10. GET /call/customer-link/{agreementId} — shareable customer join link (LiveKit mode)

```bash
curl -s https://aiassistant.yutrix.io/collassistantapi/call/customer-link/PL-2024-00847392 \
  -H "X-API-KEY: YOUR_API_KEY"
```
**Response** `200`:
```json
{
  "success": true,
  "message": "Customer join link",
  "data": {
    "agreementId": "PL-2024-00847392",
    "roomName": "call-PL-2024-00847392",
    "customerJoinUrl": "https://meet.livekit.io/custom?liveKitUrl=wss%3A%2F%2F...&token=eyJ..."
  }
}
```

## 11. POST /call/end — end the call + save disposition

```bash
curl -s https://aiassistant.yutrix.io/collassistantapi/call/end \
  -H "X-API-KEY: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "sessionId": "{sessionId}",
    "result": "PTP",
    "date": "2026-07-10",
    "amount": "1000",
    "notes": "customer promised to pay",
    "nextAction": "Follow-up Call",
    "reasonCode": ""
  }'
```
**Response** `200`: the `CallSession` with `status: "ENDED"` and `endedAt` set. Ending a call also
broadcasts a `call_ended` event on `/topic/call/{sessionId}/status` and (once AI disposition +
next-action complete) a payload on `/topic/call/{sessionId}/next-action` (see below).

---

## Realtime (STOMP over WebSocket) — cannot be tested with curl

**WebSocket URL:** `wss://aiassistant.yutrix.io/collassistantapi/ws`
**Auth:** send the key on the STOMP **CONNECT frame** as a header (browsers can't set headers on the
WS upgrade, so it goes in `connectHeaders`, NOT on the URL). Connecting without it is rejected.

Client example (`@stomp/stompjs`):

```js
import { Client } from "@stomp/stompjs";

const client = new Client({
  brokerURL: "wss://aiassistant.yutrix.io/collassistantapi/ws",
  connectHeaders: { "X-API-KEY": "YOUR_API_KEY" }, // <-- required
  reconnectDelay: 5000,
  onConnect: () => {
    const sid = "{sessionId}"; // from POST /call/start
    client.subscribe(`/topic/call/${sid}/transcript`,   (m) => console.log("transcript",  JSON.parse(m.body)));
    client.subscribe(`/topic/call/${sid}/meet-url`,     (m) => console.log("meet-url",    JSON.parse(m.body)));
    client.subscribe(`/topic/call/${sid}/insights`,     (m) => console.log("insights",    JSON.parse(m.body)));
    client.subscribe(`/topic/call/${sid}/status`,       (m) => console.log("status",      JSON.parse(m.body)));
    client.subscribe(`/topic/call/${sid}/summary`,      (m) => console.log("summary",     JSON.parse(m.body)));
    client.subscribe(`/topic/call/${sid}/next-action`,  (m) => console.log("next-action", JSON.parse(m.body)));
  },
});
client.activate();
```

### Per-session topics (subscribe after you have a `sessionId`)

| Topic | Payload | Meaning |
| --- | --- | --- |
| `/topic/call/{sessionId}/transcript` | `{ speaker, text, ts, sentiment }` | live transcript turns |
| `/topic/call/{sessionId}/meet-url` | `{ meetUrl }` | LiveKit agent audio bridge URL |
| `/topic/call/{sessionId}/insights` | `{ type, sessionId, data }` (see below) | AI copilot cards |
| `/topic/call/{sessionId}/status` | `{ event, message, timestamp, reason? }` | `call_disconnected` / `call_ended` |
| `/topic/call/{sessionId}/summary` | `{ summaryItems, insightItems }` | end-of-call summary |
| `/topic/call/{sessionId}/next-action` | full next-action payload (see below) | fires once after call end |

`insights` is multiplexed by `type`: `copilot:next-move` `{ points[], priority }`,
`copilot:contextual-details` `ContextualDetail[]`, `copilot:disposition` `Disposition | null`,
`copilot:summary` `{ summary }`, `copilot:customer-context` `{...}`.

Example `status` message (received live on `call/end`):
```json
{ "event": "call_ended", "message": "Call ended", "timestamp": "2026-07-06T06:54:45.463176509" }
```

### `next-action` payload (pushed once, after the call ends)

Fired after `/call/end` (or a disconnect) once AI disposition + next-action processing completes.
This is the **exact same object** the backend sends to the internal next-action microservice —
delivered to the frontend on this topic so the UI has the full post-call dataset in one message.

```json
{
  "sessionId": "bf43e881-...",
  "agreementId": "PL-2024-00847392",
  "customerMobile": "7838153987",
  "exotelCallSid": null,
  "callRecordingURL": null,
  "status": "ENDED",
  "startedAt": "2026-07-06T07:11:38.5887",
  "endedAt": "2026-07-06T07:11:40.3045",
  "dpd": 45,
  "delinquencyBucket": "31-60 DPD",
  "transcript": [ { "speaker": "customer", "text": "…", "ts": "…", "sentiment": "neutral" } ],
  "customerContext": { "customer": {}, "loan": {}, "additional": {}, "payment_history": [], "past_communications": [] },
  "insights": [ /* Insight[] */ ],
  "summary": { "summaryItems": [], "insightItems": [] },
  "recommendations": [ /* RecommendationDto[] */ ],
  "dataSuggestions": [ /* DataSuggestionDto[] */ ],
  "callFlows": [ /* configured flow templates */ ],
  "disposition": {
    "result": "PTP", "date": "2026-07-10", "amount": "1000",
    "notes": "…", "nextAction": "Follow-up Call", "reason": "", "paymentSchedule": null
  },
  "preCallSummary": null,
  "callMode": "collections"
}
```

### Global topic (subscribe once, no sessionId)

| Topic | Payload | Meaning |
| --- | --- | --- |
| `/topic/agent/incoming-call` | `{ type, sessionId, mobileNumber, customerData, meetUrl? }` | inbound customer-service call |

---

## Typical flow for the frontend

1. `POST /call/start` with the account's `customerData` → get `sessionId` + `meetUrl`.
2. Open the STOMP connection (with `X-API-KEY` in `connectHeaders`) and subscribe to the
   `/topic/call/{sessionId}/*` topics (including `next-action`).
3. Mount the LiveKit bridge using `meetUrl`.
4. Render transcript / insight / status messages as they arrive.
5. `POST /call/end` with the disposition when the agent finishes; consume the final
   `next-action` payload for the post-call screen.
