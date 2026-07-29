# Freight AI Ops — 5-Minute Demo Walkthrough

A scripted path through the product for a live demo (investor, customer, or
your own smoke check). Total time: ~5 minutes.

## Setup (once, before the demo)

```bash
cp .env.example .env            # set ANTHROPIC_API_KEY + ADMIN_PASSWORD
docker compose up -d --build
docker compose exec backend python -m app.demo_data   # story dataset
docker compose exec backend python -m app.smoke_llm   # proves the live AI path
```

Open <http://localhost:3000> and sign in with the admin credentials from `.env`.

> The demo dataset is idempotent and clearly marked; AI texts inside it are
> placeholders — every "Generate" button in the app hits your real provider.

## The story (follow the sidebar top-to-bottom)

**1. Dashboard (30s).** Live numbers, not mockups: today's RFQs, quotes sent,
follow-ups due, pipeline and margin totals — all computed from the database.
Every card clicks through to its module.

**2. Email Inbox — where the value actually is (60s).** This is the part worth
leading with. Connect a real mailbox under **Settings → Mailbox** (an app
password is enough), send yourself an enquiry, and press **Check now**: the
message is triaged, the RFQ is created already parsed, and its `received_at` is
the moment the *customer* wrote — not the moment somebody noticed.

Say the number out loud: forwarders answer roughly a third of enquiries, on
average in about 90 hours, and the first credible responder wins around
two-thirds of the time. Manual copy-paste cannot fix that; polling every three
minutes can.

Point out what it deliberately does **not** do: the mailbox is opened
read-only, so nothing is sent, deleted or marked as read, and every draft still
waits for a human.

**3. RFQs — anything that arrived another way (60s).** For WhatsApp, a phone
call or a portal, paste it in:

```
Hi, please quote for 1x40HC from Shanghai to Jebel Ali.
Commodity: plastic household items. Gross weight: 12,500 kg.
Cargo ready by 15 July. Need ocean freight and destination charges.
Regards, Ahmed
```

Click **Parse & create** → structured shipment fields, missing information
flagged (Incoterm, HS code…), urgency, recommended next action. Every field is
editable — the AI proposes, the human owns the record.

**4. RFQ detail — the commercial loop (90s).**
- **Rate memory** (open the Shanghai → Jebel Ali RFQ): this lane has been priced
  four times before, by four carriers, with what was charged and whether it was
  won. Click **Use** — the rate is copied onto the enquiry, annotated with where
  it came from, and the next click is *Start quote*. **This is the step that
  makes a thirty-minute answer possible**: no carrier email, no waiting.
  Say what it will not do: Dubai never matches Jebel Ali, a 20GP price is
  labelled as a different lane, and an expired rate says so.
- **Missing-info email**: one click drafts the customer email requesting
  exactly the absent details. Editable, copy-paste to send.
- **Rate request**: for a lane with no memory, pick a partner type (shipping
  line / trucker / customs broker) → tailored rate-request message.
- **Partner rates**: enter two offers, click **Compare rates (AI)** → cheapest
  / fastest / lowest-risk / recommended, with tradeoffs.
- **Start quote →** with 20% markup.

**4b. Rates &amp; Lanes (30s).** Lane coverage answers the question a buyer asks
next: *how much of my business can this price instantly?* Upload a contract rate
sheet (template on the page) and the covered lanes become quotable immediately;
re-uploading the same sheet adds nothing, and a bad row is reported with its
line number rather than silently dropped.

**5. Quote approval — the human-in-the-loop moment (60s).** The quote is
**Pending approval**: cost, selling price, margin, warnings, and the draft
text. This is a real paused LangGraph workflow persisted in Postgres — not a
UI flag. Edit the price (watch margin recompute on approve), tick **Mark as
sent** → a follow-up is scheduled automatically (day 1 of the 1/3/5/7 cadence).

**6. Follow-ups (30s).** One follow-up is already **due today** (seeded).
Generate a polite draft → **Mark sent** → the next cadence step self-schedules.

**7. Bookings — operations handover (60s).** Open the in-transit job
`JOB-…`: commercials copied from the won quote, status timeline, a document
checklist (Certificate of Origin **Missing**), and a customer status-update
draft generated from the current status. Upload a PDF against a checklist row —
it stores the real file and flips the row to **Received**. The open
**Customs-document issue** shows escalation / customer-explanation drafts.

**8. Performance — the number that justifies the invoice (60s).** The seeded
history shows four weeks of a realistic desk: about 61% of enquiries answered,
median 2.6h, and a win rate falling from ~71% when answered inside an hour to
near zero once the answer takes days. Say plainly that the benchmark column is
published industry data, not their business — then point at the *unanswered*
list, because that is the part they can act on this afternoon.

If someone asks "how do I know it worked?": measure the first week before
changing anything, then compare. The CSV export is the before/after.

**8b. Team (45s).** Add a viewer and try to change something as them — every
write is refused, because the rule lives on the router rather than on each
endpoint. Then show **Activity**: who approved which price, what it was before,
and what it became. That is usually the moment a buyer stops asking whether the
tool is safe to give their staff.

**9. Reports (30s).** Generate the daily management summary — accurate numbers
from the DB, narrated by the AI, now leading with the trailing-week response
rate — copy it or download the PDF. CSV exports are on the RFQ / Quotes /
Customers pages.

## When someone asks "but how accurate is it really?"

Do not answer with an adjective. Run it:

```bash
docker compose exec backend python -m app.eval_extraction
```

40 labelled cases, the production parser, per-field precision and recall — and
a hallucination rate reported separately, because a value the customer never
gave is a different kind of wrong from one that was missed. Say plainly that
the corpus is synthetic and offer to re-measure it on 40 of *their* emails
during the pilot; that offer is usually worth more than the number.

## The one-liner to close with

> You already lose most enquiries to the clock, not to price. This answers all
> of them, within minutes, and still lets you approve every number that leaves
> the building.

## Path to SaaS (when asked "can this scale?")

Multi-tenancy is already enforced in the data layer, not planned: every
tenant-scoped query is filtered by organization automatically, and an isolation
suite attacks that on every route shape. Add signup, add a customer. See
README → "Path to SaaS".
