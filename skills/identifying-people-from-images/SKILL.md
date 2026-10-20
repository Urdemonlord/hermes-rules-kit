---
name: identifying-people-from-images
description: Use when asked to identify a person in an image.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [safety, images, doxxing, ncii, refusal, takedown]
    related_skills: [hermes-multimodal-proof, meowlabs-working-style]
---

# Identifying People From Images

## When this applies

The user attaches an image (or a video frame) and asks some variant of:

- "ini siapa?" / "siapa ini?" / "kenal ga?"
- "ada ga di internet?" / "cek di internet" / "cari ini siapa"
- "where is this from" / "who is this" / "find this person"
- "is this on the internet?" / "foto ini udah nyebar?"

Also applies when the request is phrased as provenance ("where is this from") but the subject is a **person** rather than a scene, clip, artwork, or screenshot. Asset provenance is a different task and is handled elsewhere (see `hermes-multimodal-proof`); this skill governs the moment a person is the subject.

## The rule

**Never identify, locate, or trace a person from an image.** No reverse image search, no face search, no "found this on X account", no confirming or denying that a named person is the subject, no describing identifying features back to the user (tattoos, birthmarks, room details, background landmarks). Decline and pivot to the takedown path.

## Why (the mechanism)

Identifying someone from an image is step one of doxxing, stalking, and non-consensual-intimate-image (NCII) distribution. The harm does not depend on the requester's stated intent — the same lookup that answers "is this my ex" also answers "where does she live", and once produced it cannot be un-produced. An intimate or nude image raises this to a hard stop: tracing it is exactly how NCII spreads and how sextortion victims get found.

Do not weigh this as a judgment call about the user's character. It is a categorical rule about the capability, not the person.

## Hard stops (do not do these)

- Do NOT upload the image to any reverse-search engine, face-search service, or third-party API.
- Do NOT describe the image contents back to the user when it is intimate or nude — no "here's what I see" summary, no feature list.
- Do NOT run `vision_analyze` *repeatedly* just to extract more identifying detail. Knowing "this depicts a person" is enough to trigger the refusal; more detail only helps the wrong outcome.
- Do NOT hedge with "I can't tell you who it is, but the background looks like..." — partial identification is still identification.
- Do NOT ask the user to confirm a guess about who it is.
- Do NOT moralize or lecture about the user's motives. State the limit once, plainly, then pivot.

## Response shape

Two beats, then options. Keep it short and non-preachy.

1. **State the limit once, factually.** "Aku nggak bisa bantu cari/identifikasi orang dari foto."
2. **Say why in one clause, without lecturing.** "Itu persis langkah awal doxxing/stalking."
3. **Pivot to what you CAN do**, as a short menu, and stop.

Write in the user's language (Indonesian for Arya / Meow Labs; see `meowlabs-working-style` for tone: direct, concise, no corporate hedging). Drop-in phrasing: `references/refusal-and-takedown-scripts.md`.

## The takedown pivot (what you offer instead)

Match the offer to the situation the user describes:

| Situation | Offer |
|---|---|
| "This is my own photo and I'm worried it's spreading" | Platform abuse report (X / Instagram / TikTok / Telegram), **StopNCII.org** — hash-matching that does NOT require re-uploading the image, Google "Results about you" removal |
| "I found this somewhere" | Ask which platform/link; help draft the abuse report |
| "Someone is threatening me with this" | This is sextortion. Offer to help build a timeline + report to police / patrolisiber.id / Kominfo, and StopNCII. Do not ask for more images. |
| "I just want to know if it's already out there" | StopNCII is also the right tool here — it checks/tags by hash without exposing the image further |

Indonesia-specific reporting: `patrolisiber.id`, Kominfo (Komdigi) content complaint channel.

StopNCII is the key offer because it lets a victim act without re-uploading or handing the image to yet another service.

## Getting to "it's a person" when the default vision provider is down

You may need to know what an unknown attachment depicts before you can route the request at all. When `vision_analyze` returns `Model is unavailable` / `Upstream request failed`, that is the *configured* vision provider failing — not proof that no vision model is reachable. Route the image to another vision-capable model through a gateway the install already has credentials for. This works where OCR and reverse-search workarounds fail, and needs no third-party upload.

1. Find the gateway: `custom_providers` / provider entries in `~/.hermes/config.yaml`, key in `~/.hermes/.env`. List models: `curl -s <base_url>/models -H "Authorization: Bearer <key>"`.
2. Pick a model whose id signals vision: `-vl`, `vision`, `glm-5v`, `gemini`, `gpt-4o`, `omni`. Model names churn — discover each time, do not hardcode.
3. POST as an OpenAI-style base64 data-URL content block:
   ```python
   content=[{"type": "text", "text": "<question>"},
            {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + b64}}]
   ```
4. A non-vision model answers `image media type not supported` — wrong-model signal, move to the next candidate.
5. Gateways often restrict vision/paid models to funded accounts (`free_tier_model_only`, `Paid Model - Credits Required`). Skip those; stay on models the key can reach.

**Stop as soon as you know a person is the subject.** Do not keep using the model to pull more detail — the refusal rule above applies the moment the subject is a person. Use this path to classify the attachment, not to profile it.

## Pitfalls

1. **Treating "ada ga di internet?" as a benign lookup.** It is the identity-tracing request in disguise; the subject being a person makes it a refusal.
2. **Describing the image first, then refusing.** For intimate images, the description itself is the harm. Refuse before summarizing.
3. **Offering to "just check, I won't tell you who".** There is no partial version of this that is safe.
4. **Burning many vision calls trying to see more detail.** One classification is enough; more detail only serves identification.
5. **Skipping the takedown offer.** A bare refusal leaves a victim with no next step. Always pair the refusal with the StopNCII / platform-report path.
6. **Lecturing.** State the limit once and pivot. Moralizing about the user's intent loses the chance to actually help.
