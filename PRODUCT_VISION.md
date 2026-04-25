# Landed — Product Vision & Redesign Brief
> Written: 2026-04-24 | Author: Manuel (CEO) + Claude (Chief of Staff)
> Status: LOCKED direction. Implementation starts post-Monday demo.

---

## The North Star

**Jordan tells you the truth about your fit. Then helps you build the path to the job you actually want.**

Jordan is not a chatbot. Jordan is a career navigator — honest, direct, warm. Jordan knows who you are across every session, every device, every surface. You talk to Jordan. Jordan talks back. The job search stops feeling lonely.

---

## The Core Problem We're Solving

Job searching is one of the most isolating, demoralizing experiences a person can go through. You apply into a void. You don't know if you're even close. You prep alone. You fail alone. You don't know why.

Landed breaks that open. You paste a job → Jordan tells you if you're a real fit or not → Jordan coaches you until you're ready → you walk in confident.

**The product should FEEL like you have someone in your corner. Always. On every device.**

---

## Design Principles

1. **Jordan-first, always.** Every surface leads to Jordan. The job paste and analyzer are the entry point. Jordan is why people come back.

2. **Voice-native.** The experience should work by voice first, screen second. Interview prep is a spoken skill. Train the way you'll perform.

3. **Honest, not cheerful.** No confetti, no empty encouragement. Jordan is direct. The UI reflects that — clean, minimal, no fluff.

4. **You are known.** Jordan knows your name, your history, your weak spots, your wins. Every session starts where the last one left off.

5. **Ambient.** Jordan should be available everywhere — web, phone, Echo in your kitchen, Fire TV in your living room. The session travels with you.

---

## Platform Map

### Phase 1 — Web (Current, Polish Post-Demo)
The foundation. Already working. Post-demo improvements:
- **Onboarding:** Ask for first name at registration (not email-derived)
- **Jordan UI:** Full-screen conversation mode — no chat widget aesthetic, more like sitting across from a real person
- **Dashboard:** Your readiness score over time, session history, Jordan's running notes on you
- **Resume editor:** Integrated, not bolted on

### Phase 2 — Mobile (PWA, 2-3 weeks post-demo)
Same backend. Mobile-optimized UI. Key changes:
- Tap to record answer (voice input default)
- Push notifications: "Your interview is in 2 days — prep with Jordan?"
- Job paste via share sheet (share a LinkedIn job directly to Landed)
- Offline mode for reviewing past sessions

### Phase 3 — Alexa Skill (4-6 weeks post-demo)
**"Alexa, open Landed."**

Voice-only Jordan sessions. No screen required. The Alexa skill connects to the same user account — Jordan already knows your history from web/mobile.

Session flow:
1. "Alexa, open Landed" → Jordan greets by name, asks what to work on
2. "I have an Amazon interview Friday" → Jordan pulls the job from your pipeline
3. Jordan asks questions, listens to answers, gives coaching — all by voice
4. Session saved to account, syncs to web dashboard

Amazon employees have Echos at home. This is the demo that makes people say "I need this."

### Phase 4 — Fire TV (6-8 weeks post-demo)
**Lean-back interview simulation.**

Big screen. Full presence. Jordan on your TV feels like a real interview room. Camera-optional (for eye contact practice). Session recorded, played back.

Use cases:
- Full mock interview (Jordan asks, you answer on camera)
- Playback and review (watch yourself answer, Jordan annotates)
- Ambient prep mode (flashcards, key talking points while you cook)

---

## Web Redesign — What Changes

The current web design is functional but was built fast. Post-demo redesign:

### Homepage (Analyzer)
- **Remove:** The textarea-first layout feels cold. Job paste stays but moves below a personal greeting.
- **Add:** First time = onboarding flow with name, resume, target role type. Returning = "Welcome back, [Name]. Your last session was X days ago."
- **Jordan CTA:** More prominent. The analyzer score is a doorway to Jordan, not the destination.

### Jordan Session Page
- **Remove:** The card/bubble layout feels like a chatbot. Replace with a centered conversation view — Jordan's words large and clear, your answer in a natural input area below.
- **Add:** Session type clearly labeled (Interview Prep / Career Pivot / Career Navigation). Timer optional. Voice mode toggle.
- **Feel:** Like sitting across from a real person in a quiet room, not texting a bot.

### Dashboard / Tracker
- **Rename:** "Pipeline" → "My Journey" (more personal)
- **Add:** Readiness score history chart. Jordan's summary notes per company. One-click to "Prep more with Jordan" per job.

---

## Jordan — What Changes

Jordan's personality is locked. What changes is depth:

1. **Memory across sessions:** Jordan references past sessions. "Last time you struggled with the impact question — let's work that today."
2. **Pre-session brief:** Jordan reads your resume + job post + past session notes before opening. No cold starts.
3. **Post-session debrief saved as Jordan's notes:** Not just a summary — Jordan's running file on you. Your patterns, your strong answers, your growth.
4. **Voice-first design:** Jordan's questions written for speaking, not reading. Short. Direct. Conversational.

---

## Revenue Model (for the demo room)

**Freemium:**
- Free: 3 Jordan sessions/month, basic analyzer
- Pro ($15/mo): Unlimited Jordan, all platforms, session history, resume optimization
- Teams ($49/mo): Manager gives team access, tracks team readiness

**Enterprise:** Amazon, Google, LinkedIn use Landed for employee career development or recruiting pipeline. Jordan coaches candidates before they even apply.

---

## The Demo Line That Unlocks This

> "Right now it's a web app. The infrastructure is built so Jordan can run anywhere — Alexa, Fire TV, mobile. The next 60 days, that's where we're going."

You don't need to have it built to say that. You need to have the plan. This document is that plan.

---

## Implementation Order (Post-Monday)

| Phase | What | Owner | Timeline |
|---|---|---|---|
| 1a | Web redesign — Jordan UI full-screen | Sam (Codex) | Week 1 |
| 1b | Name field at registration | Alex (Codex) | Week 1 |
| 1c | Jordan memory across sessions | Alex + Jordan (Codex) | Week 1-2 |
| 2 | Mobile PWA | Sam (Codex) | Week 2-3 |
| 3 | Alexa skill MVP | Alex (Codex) | Week 4-6 |
| 4 | Fire TV app | Sam (Codex) | Week 6-8 |
