# Pilot playbook

How to find out whether this is worth money to a particular forwarder — in four
weeks, with their numbers, in a way that can come back negative.

That last part is the point. A pilot designed so that it cannot fail tells you
nothing, and the customer knows it. This one measures their desk before it
changes anything, so the comparison at the end is against their own baseline
rather than against a claim.

---

## Who this is for

**Small and mid-sized freight forwarders**, roughly 3–30 people, quoting from
email. The value comes from answering more enquiries and answering them sooner,
so the fit depends on two things:

| Good fit | Poor fit |
|---|---|
| Enquiries arrive by email and are quoted by hand | Enquiries arrive through a customer portal or EDI |
| More than ~10 enquiries a week | A handful of large contracted accounts |
| Repeat lanes — the same routes come back | Every shipment is bespoke project cargo |
| No TMS, or a TMS nobody quotes in | Everything already lives in CargoWise and double entry would kill adoption |

If they run CargoWise and expect this to write into it, say so plainly: there is
no TMS integration, and without one they will be entering data twice. That is a
reason to wait, not a reason to oversell.

---

## Week 0 — set up, change nothing

Half a day.

1. Deploy (see `DEPLOYMENT.md`), or host it for them.
2. Connect the sales mailbox — **read-only**, an app password, nothing is ever
   sent. Say this out loud early; it is the objection that stops pilots.
3. Add their people with the right roles. Managers get **Viewer**, which cannot
   change anything, so nobody worries about the boss editing a quote.
4. Import a rate sheet if they have one (**Rates & Lanes → Load a rate sheet**).
   Lanes with a live rate can be quoted immediately; the rest cannot.
5. Measure their accuracy, not ours: take 30–40 of their real enquiries, label
   them, and replace `backend/app/eval/corpus/rfq_extraction.jsonl`. Run
   `python -m app.eval_extraction`. The shipped corpus is synthetic — their
   number is the one that counts.

**Do not change how they work this week.** They quote exactly as before.

## Week 1 — the baseline

The system reads the mailbox and records when each enquiry arrived and when the
first quotation went out. They keep working as usual.

At the end of the week, open **Performance** and write down:

- response rate — how many enquiries got a quotation at all;
- median and 90th-percentile time to first quotation;
- how many enquiries are still unanswered;
- win rate, split by how fast the answer went out.

This is the number that matters, and it is usually the first time anyone has
seen it. Expect discomfort. Do not soften it — the discomfort is the product
demonstration.

> If the baseline is already good — nearly everything answered, quickly — stop
> and say so. They do not need this, and telling them is worth more than a sale
> that churns in three months.

## Weeks 2–4 — work the tool

Now change the workflow:

- **Unassigned** on the RFQ list is the morning queue. Empty it daily.
- Use **rate memory** before emailing a carrier. If the lane has been priced
  before, the answer is already there.
- Approve pricing in the app so the audit trail and the response-time clock are
  real.

Two rules for the pilot to stay honest:

1. **Nothing is auto-sent.** Every quotation is still approved by a person. If
   they want automation of the send itself, that is a different product and a
   different risk conversation.
2. **Do not clean the data to make the numbers look better.** Back-dating quotes
   or marking old enquiries as answered destroys the only measurement that makes
   the decision.

## End of week 4 — the review

```
Reports → ROI (or GET /api/reports/roi.pdf)
```

The one-pager separates three things deliberately:

- **Measured** — from their records. Response rate, response times, win rates.
- **Assumed** — gross profit per shipment, and what counts as a fast answer.
  Both are inputs. Ask them for the real gross profit figure; do not use ours.
- **Projected** — their own win rate when fast, applied to every enquiry.

**No industry average enters the arithmetic.** If their fast answers do not
convert better than their slow ones, the report says exactly that and projects
nothing. If there is not enough history, it refuses to project and lists what is
missing.

### Reading the result honestly

| Outcome | What it means | What to do |
|---|---|---|
| Response rate up, response time down, uplift positive | The thesis holds for this customer | Convert, using their own number |
| Response rate up, but win rate unchanged | Speed was not the constraint — price or lane coverage is | Load more rate sheets, re-run for two weeks. If it does not move, walk away |
| Nothing moved | The tool is not being used, or email is not where their enquiries live | Find out which. Both are real answers |
| "Not enough data" | Too few enquiries in four weeks | Extend to eight, or accept they are too small for this to matter |

---

## Objections worth having a straight answer to

**"Will it email my customers on its own?"**
No. It reads; it never sends, deletes or marks mail as read. Every draft waits
for a person. This is enforced in the code, not by policy.

**"What if it gets the extraction wrong?"**
It will sometimes. That is why every field is editable and why there is a
published accuracy measurement, broken into *missed*, *wrong* and *invented* —
because a value the customer never gave is a different kind of error from one
that was overlooked. Run the harness on their own emails in week 0.

**"Who can see my rates?"**
Only their organization. Tenant isolation is enforced in the data layer, not per
screen, and there is a test suite that attacks it from every route shape.

**"What happens to my data if we stop?"**
CSV exports on RFQs, quotes, customers and performance; a nightly `pg_dump` they
can take away. Self-host and it never left in the first place.

**"Can our office manager have access without touching prices?"**
Yes — the Viewer role cannot change anything, and the restriction is applied to
every write endpoint at once rather than one at a time.

---

## Pricing

The market band for forwarding software is roughly **$39–$400 per user per
month** (Logitude at the low end, Magaya at the high end). Vooma and HappyRobot
are venture-funded competitors in exactly this space, so a buyer may well be
comparing.

A defensible position for a small forwarder:

| | Per user / month | For |
|---|---|---|
| **Starter** | $79 | 1 mailbox, rate memory, performance reporting. Up to 3 users |
| **Desk** | $129 | Multiple mailboxes, roles and audit trail, tariff import |
| **Pilot** | free for 4 weeks | The playbook above, capped at one mailbox |

Two things to hold to:

1. **Price per user, not per shipment.** Per-shipment pricing punishes exactly
   the behaviour the product exists to encourage — quoting more.
2. **Quote against the measured gross profit, not the subscription.** At $129
   per user per month, three users cost about $4,600 a year. One recovered
   shipment a month at $400 gross profit covers it. If the four-week review
   cannot show at least that, the honest move is to say the fit is not there.

Do not discount into a pilot that has not produced a number. A customer who
signs on a discount rather than on their own measurement churns at renewal,
because nothing ever demonstrated the value.
