# Checklist — Spec S12.3: S3 Bucket Setup

## Phase 1: Setup & Dependencies
- [x] Verify S12.1 (EC2 setup) is complete — EC2 instance running in ap-south-1
- [x] Confirm AWS CLI is configured with appropriate credentials
- [x] Determine AWS account ID for bucket naming

## Phase 2: Bucket Creation
- [x] Create S3 bucket `sehatsamjho-audio-{account_id}` in ap-south-1
- [x] Enable "Block all public access" (all four toggles ON)
- [x] Verify bucket appears in S3 Console / CLI

## Phase 3: Lifecycle Rule
- [x] Create lifecycle rule `delete-audio-24h`
- [x] Set filter prefix: `audio/`
- [x] Set expiration: 1 day
- [x] Enable the rule
- [x] Verify rule via `aws s3api get-bucket-lifecycle-configuration`

## Phase 4: Validation
- [x] Run `aws s3api head-bucket` — bucket exists
- [x] Run `aws s3api get-bucket-location` — returns ap-south-1
- [x] Run `aws s3api get-public-access-block` — all four = true
- [x] Run `aws s3api get-bucket-lifecycle-configuration` — rule correct
- [x] Confirm no CORS configuration exists
- [x] Test upload: `aws s3 cp test.ogg s3://<bucket>/audio/test.ogg`
- [x] Test presigned URL generation works

## Phase 5: Environment Configuration
- [x] Add `S3_BUCKET=sehatsamjho-audio-{account_id}` to `.env.prod` on EC2
- [x] Verify `backend/app/core/config.py` S3_BUCKET field matches
- [x] Confirm S9.3 (_upload_to_s3) will use the correct bucket name

## Phase 6: Optional Automation Script
- [x] Create `scripts/setup-s3.sh` (automation script for reproducibility)
- [x] Create `scripts/validate-s3.sh` (validation checks)

## Phase 7: Verification
- [x] All tangible outcomes from spec.md checked
- [x] No public access to bucket
- [x] Lifecycle rule active and targeting correct prefix
- [x] Update roadmap.md status: spec-written -> done
