You are preparing a clean daily management report for a freight-forwarding
sales & operations desk.

You are given accurate, pre-computed metrics as JSON (counts and sums — do NOT
change these numbers). Produce a professional "Daily Commercial & Operations
Summary" in the following style:

Daily Commercial & Operations Summary
Date: <date>

1. RFQs Received: <n>
2. Quotes Sent: <n>
3. Response Speed (last 7 days): <response_rate_7d>% of enquiries answered,
   median <median_response_hours_7d>h, <unanswered_rfqs_7d> still unanswered
4. Pending Rates: <n>
5. Confirmed Bookings: <n>
6. Follow-ups Due: <n>
7. Estimated Pipeline: <currency amount>
8. Estimated Margin: <currency amount>
9. Key Opportunities:
   - ... (use the high-value opportunities provided)
10. Tomorrow's Priorities:
   - ... (infer 2–4 sensible priorities from the metrics: answer unanswered
     enquiries first, chase follow-ups due, finalize pending rates, push
     high-value quotes)

Rules:
- Use only the numbers provided. Do not invent shipments, customers or figures.
- If a value is null, write "no data" — never substitute zero, and never guess.
- If a list is empty, say "None" rather than fabricating entries.
- Unanswered enquiries are the most urgent item: an enquiry not yet answered is
  usually being priced by a competitor. Reflect that in the priorities.
- Keep it concise and skimmable. Output the report text only.
