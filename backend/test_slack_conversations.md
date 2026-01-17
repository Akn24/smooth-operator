# Test Slack Conversations for Meeting Prep

Use these sample conversations between your two Slack accounts to test the meeting prep system.

---

## Account Setup
- **Account 1 (Ankit):** ankitnath1999@gmail.com
- **Account 2 (Sam):** ankitspam24@gmail.com

---

## Conversation 1: Aurora Hackathon Product Updates

**Channel:** #new-channel or DM

```
Sam: Hey Ankit, quick update on the Aurora hackathon - I've finished the initial UI mockups for the meeting prep feature.

Ankit: Nice! Can you share them before our product updates call? I want to review the dashboard layout.

Sam: Sure, I'll upload them now. Also, we need to discuss the AI prompt engineering - the context filtering isn't working as expected.

Ankit: Yeah, I noticed that too. The Slack integration is missing some messages. Let's make that a priority for the demo.

Sam: Agreed. What time is the Aurora hackathon demo scheduled for?

Ankit: It's at 6 PM today. We should do a dry run at 5:30.

Sam: Perfect. I'll also prepare the slides for the product roadmap section.

Ankit: Great. One blocker - I'm still waiting on the API keys from the backend team. Can you ping them?

Sam: On it. I'll escalate to Jonah if they don't respond in the next hour.
```

---

## Conversation 2: Technical Discussion

**Channel:** #engineering or DM

```
Sam: The document processor is throwing errors on large PDFs. Have you seen this?

Ankit: Which endpoint? The /api/meetings/{id}/generate-prep one?

Sam: Yes, specifically when there are attachments over 5MB.

Ankit: I'll add a size limit check. For now, can we skip those in the demo?

Sam: Works for me. Also, the OAuth token refresh is fixed now - tested it this morning.

Ankit: Excellent! That was blocking the calendar sync. Now we can pull meetings properly.

Sam: Should we add Slack message search by channel name too? Right now it only searches by email.

Ankit: Good idea. I'll add keyword search from the meeting title as well.

Sam: That would help. For "Aurora hackathon product updates" it should find messages mentioning "aurora" or "hackathon".

Ankit: Exactly. I'll push that fix before the demo.
```

---

## Conversation 3: Meeting Prep & Action Items

**Channel:** #product or DM

```
Sam: Reminder - we need to finalize the demo script for the Aurora presentation.

Ankit: Right, here's what I'm thinking:
1. Show the calendar integration
2. Demo the AI-generated prep document
3. Highlight the Slack/Gmail context gathering

Sam: Add document analysis to that list. The investors specifically asked about attachment parsing.

Ankit: Good call. I'll prepare a sample PDF with budget data.

Sam: I promised to have the investor deck ready by 5 PM. Running a bit behind.

Ankit: No worries, focus on the key slides. We can polish after the demo.

Sam: Thanks. One question - are we showing the external attendee filtering?

Ankit: Yes, it's a key feature. When there are external attendees, sensitive Slack DMs get filtered out.

Sam: Smart. That's a strong privacy selling point.
```

---

## Conversation 4: Personal/Health Context (Tests Tier 1 Filtering)

**Channel:** DM only

```
Sam: Hey, heads up - I'm dealing with some back pain today. Might need to take breaks during the demo.

Ankit: No problem at all, take care of yourself. We can adjust the presentation flow.

Sam: Thanks for understanding. I'll be fine for the main demo, just might need to sit down.

Ankit: Absolutely. Let me know if you need me to cover any sections.
```

---

## Conversation 5: Blocker Discussion (Tests Tier 1 - Critical)

**Channel:** #engineering

```
Sam: BLOCKER: The Supabase connection is timing out intermittently.

Ankit: Is this affecting the OAuth token storage?

Sam: Yes, about 20% of login attempts fail. I'm seeing connection pool exhaustion.

Ankit: Let's increase the pool size. Can you update the config before our meeting?

Sam: Already on it. Should be fixed in 10 minutes.

Ankit: Great, that was my main concern for the demo. Thanks for the quick turnaround.
```

---

## Conversation 6: Questions & Follow-ups

**Channel:** #product

```
Sam: Question - did you decide on the pricing tier for the AI features?

Ankit: Not yet. We have three options:
1. Include in base plan
2. Premium add-on ($10/month)
3. Usage-based pricing

Sam: I lean toward option 2. Keeps base plan accessible.

Ankit: Agreed. Let's finalize in our product updates meeting.

Sam: Also, any update on the mobile app timeline?

Ankit: Pushed to Q2. We're prioritizing the web experience first.
```

---

## How to Use These Conversations

1. **Copy the messages** from each conversation
2. **Paste them in Slack** between your two accounts (Ankit and Sam)
3. **Use the appropriate channel** or DM as indicated
4. **Schedule a meeting** with both accounts as attendees
5. **Generate the prep document** and verify Slack messages are captured

---

## Expected Search Matches

For a meeting titled "Aurora hackathon product updates", the system should find messages containing:
- "aurora"
- "hackathon"
- "product"
- "demo"
- "updates"

The system will also search for:
- Email addresses of attendees
- Names extracted from emails (e.g., "Ankitspam" -> "Sam" if you rename)
- First names mentioned in messages

---

## Verification Checklist

After posting the conversations and generating prep:

- [ ] Check `context_summary.slack_messages` count > 0
- [ ] Verify Slack channels appear in context
- [ ] Confirm keywords from meeting title matched messages
- [ ] Test with `/api/meetings/{id}/context` endpoint to see raw data
