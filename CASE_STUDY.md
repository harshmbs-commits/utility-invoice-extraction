# Case Study

Notes on how I built this, what broke, and why I made the choices I made. This also doubles as my rough script for the video.

## The Problem

Utility invoices come from different vendors, different countries, different languages. Most companies still process these by hand. I built a pipeline that reads real invoices (electricity, gas, water, heating) and turns them into a clean CSV. No OCR — I send the image straight to a vision LLM and let it read the invoice directly.

## Data

I used 4 real invoices, in 4 languages, covering electricity, gas, water, and heating:

- Iberdrola electricity bill (Spanish) — a published sample invoice
- Indraprastha Gas bill (Hindi/English) — my own bill
- Aigües Manresa water bill (Catalan) — a published sample invoice
- BRUNATA heating/hot water bill (German) — a published sample invoice

Even with permission, I redacted anything with real personal info before pushing to GitHub. No reason to leave someone's name and address sitting in a public repo.

## Assumptions I Made

- **One row per invoice.** The BRUNATA bill covers both heating and hot water. Instead of splitting that into two rows, I pick whichever category costs more and use that as the main usage number. The other one gets mentioned in the notes field.
- **No OCR.** I send the raw image straight to the LLM instead of running OCR first and feeding it text. Simpler pipeline, one code path for PDFs and images alike, and it's closer to how modern invoice tools actually work.
- **PDFs get converted to images first.** Every file type — PDF, JPG, PNG, WEBP — gets turned into an image right at the start. Everything downstream only ever deals with one format.
- **"Don't guess" needed to be spelled out.** This one bit me twice. More on that below.

## Key Decisions

| Decision | What I chose | What I considered instead | Why |

| LLM | Gemini 3 Flash Preview, with Groq's Qwen 3.6 27B as backup | GPT-4o-mini, Claude Haiku, Groq's text-only Llama | Needed free and vision-capable, with a fallback |
| Validation | Plain Python rule checks | A second LLM call to double-check itself | Free, deterministic, and I can actually write tests for it |
| Text extraction | Vision LLM reads the image directly | OCR first, then feed text to the LLM | Fewer moving parts |
| Confidence score | One score per invoice | A score per field | Simpler, and per-field scoring wasn't worth the extra complexity here |
| Code layout | Split into ingestion / extraction / validation / output folders | One big script | Easier to test and explain piece by piece |

## What Broke, and What I Fixed

This is honestly the most useful part of the whole project.

**Bug 1: it made up a usage number.** The Spanish electricity bill doesn't state a usage total anywhere — just a chart and an average. I'd told the model "use null instead of guessing," but it went ahead and calculated a number anyway. Turns out the model didn't think of that as guessing — it thought of it as math. I had to be a lot more specific: don't calculate, don't average, don't estimate from a chart, period. Fixed, and I checked it again to be sure.

**Bug 2: it made up a billing period.** Same problem, different field. The Catalan water bill only has one real date on it, plus a label saying "4th quarter." The model took that one date and added three months to invent a plausible-sounding end date. I had to extend the same rule to cover every field, not just usage — no calculating dates either, even if the label hints at a duration. Fixed and re-checked.

The lesson here: "don't guess" isn't specific enough on its own. The model doesn't see math as guessing. You have to spell out exactly what kind of guessing you mean.

**One thing I didn't fix:** on the German bill, the model labels the invoice as "heating" in one field, but then in its own notes says hot water was actually the more expensive category. Small inconsistency. I noticed it, but didn't chase it down given the time I had.

## A Field I Had to Clarify Mid-Build

I originally had one field, usage_amount, and it got confusing — was it consumption, or was it the amount owed? I split it into two: usage_quantity (how much was used, e.g. kWh or m³) and payable_amount (how much is owed, in its own currency). Cleaner, and it matches what's actually printed on these invoices anyway.

## Models Kept Changing Under Me

While building this, I found out gemini-2.5-flash and the old google-generativeai package were already deprecated for new API keys — even though a lot of documentation still references them. Groq had also dropped their Llama vision models in favor of Qwen 3.6 27B. I had to check current docs instead of relying on what I already knew. Qwen also needed a specific setting (reasoning_effort="none") or it would burn its whole response budget "thinking" before ever answering. This is just a real thing you deal with when you build on top of APIs that move fast.

## The Fallback Model Isn't as Reliable as the Primary

Gemini's free tier caps out at 20 requests a day. Once I hit that limit, everything fell through to Groq — and that's where I found two separate problems.

First, on the trickiest invoice (the ambiguous German one), Groq's model would return several half-finished JSON attempts with reasoning text mixed in, instead of one clean answer. That broke my parser. Turned out Qwen only supports Groq's looser JSON mode, not the strict schema-enforced one — that's only available on Groq's gpt-oss models. I fixed this by adding a fallback parser that grabs the last valid JSON object in the response, since the model does eventually land on a real answer, just after some visible back-and-forth.

Second, even after fixing that crash, the actual answer quality was worse. On that same invoice, Groq got the invoice year wrong and returned a usage number that didn't match anything on the actual bill. Gemini, tested earlier on the same file, got both right.

I didn't chase this further — documenting it felt more honest than pretending it's solved. The takeaway: having a fallback model keeps your pipeline from crashing, but it doesn't mean the fallback gives you the same quality of answer. That's worth knowing before you rely on one in production.

## What I'd Do With More Time

- Fix the heating/water labeling mismatch on the German bill
- Get a native speaker to check translation accuracy instead of relying on AI-assisted checking
- Test against way more than 4 invoices to catch rarer edge cases
- Add an optional LLM self-check step on top of the rule-based validation
- Score confidence per field instead of per invoice
- Set up a small regression test that checks extraction output against a known-good answer, so future prompt changes don't quietly break something that used to work