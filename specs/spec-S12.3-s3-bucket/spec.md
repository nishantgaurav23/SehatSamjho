# Spec S12.3 — S3 Bucket Setup

## Overview
Create and configure an S3 bucket for storing TTS audio files. The bucket uses presigned URLs for access (no public access), with a 24-hour lifecycle rule to automatically clean up audio files. This is an AWS Console / IaC spec with an optional automation script.

## Dependencies
- S12.1 (EC2 t3.micro setup) — EC2 instance must exist in ap-south-1

## Target Location
- AWS Console / docs
- `scripts/aws/setup-s3.sh` (optional automation script)

---

## Functional Requirements

### FR-1: Create S3 bucket
- **What**: Create an S3 bucket named `sehatsamjho-audio-{account_id}` in ap-south-1
- **Inputs**: AWS account ID (12-digit number)
- **Outputs**: Bucket created and accessible via AWS CLI / Console
- **Edge cases**: Bucket name must be globally unique; account_id suffix ensures this

### FR-2: Block all public access
- **What**: Enable "Block all public access" on the bucket (all four toggles ON)
- **Inputs**: Bucket name
- **Outputs**: `PublicAccessBlockConfiguration` with all fields set to `true`
- **Edge cases**: Verify no bucket policy grants public access

### FR-3: Lifecycle rule for audio cleanup
- **What**: Create a lifecycle rule that deletes objects with prefix `audio/` after 24 hours (1 day expiration)
- **Inputs**: Bucket name, prefix `audio/`, expiration days = 1
- **Outputs**: Lifecycle rule `delete-audio-24h` active on the bucket
- **Edge cases**: Rule must only target `audio/` prefix, not the entire bucket

### FR-4: Bucket region matches EC2
- **What**: Bucket region must be `ap-south-1` (same as EC2) to minimize latency and data transfer costs
- **Inputs**: Region parameter
- **Outputs**: Bucket LocationConstraint = ap-south-1

### FR-5: CORS not required
- **What**: No CORS configuration needed since access is via presigned URLs (server-side, not browser)
- **Inputs**: N/A
- **Outputs**: No CORS rules on bucket

### FR-6: Verify presigned URL generation works
- **What**: After bucket creation, verify that presigned URLs can be generated for objects in the `audio/` prefix
- **Inputs**: A test object key like `audio/test.ogg`
- **Outputs**: Valid presigned URL with expiry (3600s as configured in S9.3)

---

## Tangible Outcomes

- [ ] **Outcome 1**: S3 bucket `sehatsamjho-audio-{account_id}` exists in ap-south-1
- [ ] **Outcome 2**: `aws s3api get-public-access-block --bucket <name>` shows all four blocks = true
- [ ] **Outcome 3**: `aws s3api get-bucket-lifecycle-configuration --bucket <name>` shows rule targeting `audio/` prefix with 1-day expiration
- [ ] **Outcome 4**: Bucket has no CORS configuration
- [ ] **Outcome 5**: `aws s3 cp test.txt s3://<bucket>/audio/test.txt` succeeds (with proper IAM credentials)
- [ ] **Outcome 6**: S3_BUCKET value added to `.env.prod` / EC2 environment

---

## Test-Driven Requirements

### Tests to Write First (Red -> Green)
Since this is an infrastructure/console spec, tests are validation scripts rather than pytest:

1. **test_bucket_exists**: `aws s3api head-bucket --bucket <name>` returns 200
2. **test_bucket_region**: `aws s3api get-bucket-location --bucket <name>` returns ap-south-1
3. **test_public_access_blocked**: All four public access block fields are true
4. **test_lifecycle_rule**: Lifecycle config has rule with prefix `audio/` and expiration days = 1
5. **test_no_cors**: `aws s3api get-bucket-cors --bucket <name>` returns NoSuchCORSConfiguration
6. **test_upload_download**: Can PUT and GET an object under `audio/` prefix

### Mocking Strategy
- No mocking needed — these are AWS CLI validation commands run against the real bucket
- Can optionally write a `scripts/aws/validate-s3.sh` script

### Coverage Expectation
- All 6 validation checks pass against the live bucket

---

## References
- roadmap.md (Phase 12 — AWS Deployment)
- S9.3 (S3 upload — uses this bucket)
- S12.1 (EC2 setup — same region)
- S12.4 (IAM role — grants access to this bucket)
