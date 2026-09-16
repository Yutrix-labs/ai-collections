# Arabic (Kuwait) demo — customer scripts

Two scripted customer scenarios for the collections demo. **These are the CUSTOMER's
lines only** — the tele-caller speaks live, in English, and the Gemini translation
bridge renders it into Arabic for the customer leg.

Each numbered line is **one audio clip**. Render them individually, name them exactly
as shown (`a01.wav`, `b03.wav`, …), and the soundboard plays them in order.

## Voice + rendering settings

- **Dialect:** Modern Standard Arabic with light Gulf phrasing. Deliberately *not*
  heavy Kuwaiti dialect — Deepgram transcribes MSA far more reliably, and heavy
  dialect is the single most likely thing to break the demo.
- **Voice:** any ElevenLabs Arabic male voice. Pick one and keep it for every clip in
  both scenarios, or the "customer" changes identity mid-call.
- **Format:** WAV, mono. The soundboard resamples, so the source rate doesn't matter.
- **Pacing:** leave ~0.3s of silence at the start and end of each clip. Clips that
  begin instantly get their first syllable clipped by the endpointer.

Before rendering all of them, render lines `a01`, `a06` and `b04` and run them through
the Deepgram round-trip check (`ar` vs `ar-KW`). If those three come back clean, the
rest will too.

---

## Scenario A — Ready to pay (Promise-to-Pay)

Follows the `ptp` flow in `backend/call_flows.json`: greet → verify identity → state
overdue → willing → exact date → exact amount → payment method → confirm all three.

| # | Clip | Arabic | English | Play when… |
|---|---|---|---|---|
| 1 | `a01` | آلو، السلام عليكم. | Hello, peace be upon you. | Call connects |
| 2 | `a02` | نعم، أنا فهد العتيبي. تفضل. | Yes, this is Fahad Al-Otaibi. Go ahead. | Agent asks who they're speaking to |
| 3 | `a03` | إي، أعرف. عندي قسط متأخر. | Yes, I know. I have a late installment. | Agent states the reason for calling |
| 4 | `a04` | كم المبلغ المطلوب بالضبط؟ | How much exactly is due? | Agent mentions the overdue amount |
| 5 | `a05` | تمام، أقدر أسدد. ما في مشكلة. | Fine, I can pay. No problem. | Agent asks if they can pay |
| 6 | `a06` | راح أسدد يوم خمسة وعشرين من هذا الشهر، بعد ما ينزل الراتب. | I'll pay on the 25th of this month, after my salary arrives. | Agent pushes for an exact date |
| 7 | `a07` | راح أدفع المبلغ كامل، مية وخمسين دينار. | I'll pay the full amount, one hundred and fifty dinars. | Agent pushes for an exact amount |
| 8 | `a08` | بحوّلها عن طريق التطبيق، أونلاين. | I'll transfer it through the app, online. | Agent asks the payment method |
| 9 | `a09` | إي، أأكد لك. يوم خمسة وعشرين، مية وخمسين دينار، تحويل أونلاين. | Yes, I confirm: the 25th, one hundred and fifty dinars, online transfer. | Agent reads back all three |
| 10 | `a10` | شكراً لك. مع السلامة. | Thank you. Goodbye. | Agent closes |

**What to watch in the portal:** by line 9 the copilot should have captured a PTP with
date, amount and method — that's the money shot for this scenario.

---

## Scenario B — Not ready to pay (hardship / job loss)

Follows the `cant_pay_job_loss` flow: greet → verify → state overdue → hardship
disclosed → empathise (do NOT pressure) → explore partial payment → commitment.

| # | Clip | Arabic | English | Play when… |
|---|---|---|---|---|
| 1 | `b01` | آلو، مين معاي؟ | Hello, who am I speaking with? | Call connects |
| 2 | `b02` | إي، أنا فهد. تفضل. | Yes, this is Fahad. Go ahead. | Agent identifies themselves |
| 3 | `b03` | أعرف إن القسط متأخر، بس ظروفي صعبة الحين. | I know the installment is late, but my circumstances are difficult right now. | Agent states the overdue |
| 4 | `b04` | فقدت وظيفتي قبل شهرين، ولين الحين ما لقيت شغل. | I lost my job two months ago and haven't found work yet. | Agent asks what's wrong — **the hardship trigger** |
| 5 | `b05` | والله ما أقدر أدفع المبلغ كامل هذا الشهر. | Honestly, I can't pay the full amount this month. | Agent asks for full payment |
| 6 | `b06` | عندي مصاريف علاج لوالدتي، وهذي اللي تاكل أغلب الراتب. | I have medical expenses for my mother, and those eat most of my income. | Agent probes further |
| 7 | `b07` | ممكن أدفع مبلغ بسيط، مثلاً ثلاثين دينار. | I could pay a small amount, say thirty dinars. | Agent offers partial payment |
| 8 | `b08` | تقدرون تعطوني مهلة؟ أحتاج شهر على الأقل. | Can you give me a grace period? I need at least a month. | Agent asks about timing |
| 9 | `b09` | إذا في إمكانية إعادة جدولة، أكون ممنون. | If rescheduling is possible, I'd be grateful. | Agent mentions options |
| 10 | `b10` | زين، أقدر ألتزم بثلاثين دينار يوم عشرة. | Alright, I can commit to thirty dinars on the 10th. | Agent asks for a firm commitment |
| 11 | `b11` | شكراً على تفهمك. | Thank you for your understanding. | Agent closes |

**What to watch:** line 4 is the hardship trigger — the copilot should visibly switch
tone, stop pushing for full payment, and surface restructuring options. That contrast
against Scenario A is what makes the demo land.

---

## Filler clips (render these too)

The tele-caller will go off-script — they always do. These cover the gaps without
derailing the scenario.

| Clip | Arabic | English |
|---|---|---|
| `f01` | ممكن تعيد من فضلك؟ | Could you repeat that, please? |
| `f02` | لحظة من فضلك. | One moment, please. |
| `f03` | نعم، صحيح. | Yes, that's correct. |
| `f04` | لا، مو صحيح. | No, that's not correct. |
| `f05` | ما فهمت عليك. | I didn't understand you. |
| `f06` | إي، أسمعك. | Yes, I hear you. |
| `f07` | طيب، وبعدين؟ | OK, and then? |

---

## Open item: the customer record still has an Indian name

The scope agreed was "customer voice only", so the portal still shows
`Rajesh Kumar Sharma` and ₹ amounts from `backend/src/main/resources/data/customers.json`.
A customer named Rajesh answering in Arabic about rupees will be noticed.

The minimal fix — much smaller than a full `ar` locale — is to edit **one** record in
that file: name → `فهد العتيبي` / `Fahad Al-Otaibi`, currency → KWD, and amounts to
match the scripts above (150 KWD due in Scenario A, 30 KWD partial in Scenario B).
Note KWD conventionally carries **three** decimal places (`KD 150.000`).
