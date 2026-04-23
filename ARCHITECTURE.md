# Landed Architecture

## MVP Architecture

Today the MVP runs as a single Render web service hosting the FastAPI API, static frontend files, SQLite persistence, and Jordan audio cache in one deployment.

```text
User Browser
  ↓
Render Web Service
  ├─ FastAPI routes
  ├─ Static HTML/CSS/JS
  ├─ SQLite database
  ├─ Jordan audio cache
  └─ Claude API for analysis + coaching
```

## AWS Future-State Diagram

```text
User
  ↓
CloudFront (CDN + caching)
  ↓
API Gateway
  ↓
Lambda (FastAPI via Mangum adapter)
  ↓
┌─────────────────────────────────────┐
│  Claude API (job analyzer + Jordan) │
│  DynamoDB (applications + sessions) │
│  S3 (resume versions, audio cache)  │
│  Cognito (multi-user auth)          │
│  CloudWatch (logs + monitoring)     │
│  Polly (optional: replace edge_tts) │
└─────────────────────────────────────┘
  ↓
Alexa Skills Kit (Jordan as Alexa skill)
```

## Components

- `CloudFront`: caches static assets and repeated API responses close to users.
- `API Gateway`: provides the public HTTPS entrypoint, throttling, and request routing.
- `Lambda + Mangum`: runs the FastAPI app without server management and scales by request volume.
- `Claude API`: performs job analysis and interview coaching generation.
- `DynamoDB`: stores applications and Jordan session transcripts with predictable serverless scaling.
- `S3`: stores resume versions, generated audio files, and other durable artifacts cheaply.
- `Cognito`: adds managed sign-in when Landed becomes multi-user.
- `CloudWatch`: captures logs, metrics, and alarms for errors and latency.
- `Polly`: can replace `edge_tts` when AWS-native speech generation becomes preferable.
- `Alexa Skills Kit`: turns Jordan into a voice-first interview coach on Echo devices.

## Why These AWS Services

- `CloudFront` keeps the UI fast globally and reduces repeated origin load.
- `API Gateway` is the simplest managed front door for a serverless HTTP API.
- `Lambda` fits bursty demo-to-growth traffic without paying for idle servers.
- `DynamoDB` avoids connection-pool issues and handles simple key/value plus document access well.
- `S3` is the standard low-cost store for generated assets and resume snapshots.
- `Cognito` removes the need to build authentication flows from scratch.
- `CloudWatch` gives first-party observability for logs, metrics, alarms, and dashboards.
- `Polly` aligns speech generation with the rest of the AWS stack if `edge_tts` becomes limiting.

## Cost Estimate

These are directional monthly estimates and assume moderate prompt sizes plus cached static assets.

| Users | Estimated Monthly Cost | Main Drivers |
|---|---:|---|
| 100 | $40-$90 | Claude API usage dominates; AWS infra remains small |
| 1,000 | $220-$480 | Claude API, Lambda requests, and S3 audio storage increase |
| 10,000 | $1,800-$3,600 | Claude API remains the largest line item; CloudFront and DynamoDB also scale materially |

## Jordan As An Alexa Skill

Jordan's existing session API maps cleanly to Alexa intents:

- `LaunchRequest` starts a `track` session and plays Jordan's greeting.
- `StartJobPrepIntent` maps to `POST /jordan/session/start` with `mode=job` and a selected application id.
- `AnswerIntent` maps to `POST /jordan/session/respond` with the active `session_id` and the user's spoken answer.
- `AMAZON.RepeatIntent` can replay the latest `audio_url`.
- Session attributes store the `session_id`, current question, and completion state between turns.
