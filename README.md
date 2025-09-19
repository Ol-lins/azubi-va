# Azubi Voice Assistant (azubi-va) 🤖🔊

A serverless text-to-speech (TTS) application built on **AWS SAM**, **Lambda**, **Polly**, **S3**, and **CloudFront**.  
This project was developed in phases to demonstrate real-world cloud application design, deployment, and security hardening.

---

## Phase 1: Project Setup & Architecture

### Activities
- Designed initial architecture:
  - **Frontend**: static HTML + CSS + JS
  - **Backend**: API Gateway (HTTP API) → Lambda → Polly → S3
  - **Storage**: 
    - Website bucket (private, for frontend)
    - Audio bucket (private, for synthesized audio with lifecycle expiry)
- Created initial project folder structure (`infra`, `backend`, `frontend`).
- Defined CloudFormation/SAM template (`template.yaml`).

### Challenges
- Errors creating buckets with public policies → fixed by enforcing **private buckets** + CloudFront Origin Access Control (OAC).
- Understood IAM least-privilege: Lambda only allowed to synthesize speech and read/write to Audio bucket.

---

## Phase 2: Infrastructure as Code (IaC)

### Activities
- Converted design into a SAM template with:
  - Website S3 bucket
  - Audio S3 bucket (14-day lifecycle)
  - Lambda function (`TtsFunction`)
  - API Gateway HTTP API (event trigger)
- Added **Outputs** for easy retrieval of:
  - WebsiteBucketName
  - AudioBucketName
  - ApiEndpoint

### Challenges
- First deploy failed (bucket policy blocked by `BlockPublicPolicy` setting).
- Fixed by removing public ACLs and using private buckets only.
- Learned SAM vs raw CloudFormation:
  - SAM simplified resources (e.g., `AWS::Serverless::Function` vs full IAM roles + Lambda definitions).

---

## Phase 3: Backend Development

### Activities
- Implemented **`app.py`** Lambda function:
  - Validates input (`text`, `voiceId`, `format`).
  - Calls Polly to synthesize audio.
  - Stores audio in **Audio S3 bucket**.
  - Returns **pre-signed S3 URL**.
- Added **SSML support** for more natural speech:
  ```xml
  <speak>Hello. <break time="400ms"/> World.</speak>
  ```
- Supported multiple formats: `mp3`, `ogg_vorbis`, `pcm`.
- Tested with PowerShell and `Invoke-RestMethod`.

### Challenges
- Initial runtime import errors → fixed by using Python 3.12 with SAM build.
- Learned to differentiate **text** vs **SSML** input.
- Discovered Polly char limit (3,000) → enforced limit in backend.

---

## Phase 4: Integration & Security

### Activities
- Integrated frontend with backend:
  - `index.html` sends POST requests to API Gateway.
  - Displays returned audio using `<audio>` element.
- Secured buckets:
  - Website bucket only accessible via CloudFront.
  - Audio bucket private, only accessed with pre-signed URLs.
- Implemented **CORS lock**:
  - API only accepts requests from `https://<cloudfront-domain>`.
- Applied **principle of least privilege**:
  - Lambda policies limited to Polly + Audio bucket.
- Added **input hardening**:
  - Validate voice IDs & formats against allow-lists.
  - Strip control characters.
  - Check SSML tags against a safe subset.

### Challenges
- Testing CORS: confirmed only browser calls from CloudFront domain work; other sites/local origins blocked.
- Explored but did not implement advanced auth (API keys, Cognito) → documented as future work.

---

## Phase 5: Operations & Monitoring

### Activities
- Created **AWS Budget** ($5/month) with 80% threshold email alerts.
- Added **CloudWatch Alarm**:
  - Monitors Lambda `Errors` metric.
  - Triggers if ≥1 error in 5 minutes.
- Learned how to invalidate CloudFront cache for frontend updates.

### Challenges
- CloudFront distribution deployment took time (update in progress).
- Resolved “No changes to deploy” issue by ensuring stack stable before redeploy.

---

## How to Deploy

### Prerequisites
- AWS CLI & credentials
- AWS SAM CLI
- Python 3.12
- Git

### Commands
```bash
# Build
sam build

# Deploy (guided first time, then automatic)
sam deploy --guided
sam deploy

# Upload frontend
aws s3 cp frontend/index.html s3://<WebsiteBucketName>/index.html
aws s3 cp frontend/styles.css s3://<WebsiteBucketName>/styles.css

# Get CloudFront domain
sam list stack-outputs --stack-name azubi-va
```

Open:  
`https://<CloudFrontDomain>/index.html`

---

## Lessons Learned

- **IaC is critical**: SAM simplifies CloudFormation, but still requires understanding AWS resources.
- **Security first**: Avoid public buckets; use CloudFront + OAC and signed URLs.
- **CORS matters**: Public APIs must be restricted to specific origins.
- **Ops guardrails**: Budgets + alarms keep projects safe from runaway costs.
- **Iterative design works best**: Building in phases caught errors early and let us fix them with minimal rework.

---

## Authors
- **Collins Obeng ODuro** – (student, Azubi)  
- Guided by AWS documentation and best practices.
