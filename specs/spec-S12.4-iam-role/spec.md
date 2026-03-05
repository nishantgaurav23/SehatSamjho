# Spec S12.4 — IAM Role for EC2

## Overview
Create an IAM role with an instance profile that grants the EC2 instance least-privilege access to the S3 audio bucket. The role replaces the need for hardcoded AWS access keys on the server — the application uses the instance metadata service to obtain temporary credentials automatically.

## Dependencies
- S12.1 (EC2 t3.micro setup) — instance must exist to attach the profile
- S12.3 (S3 bucket setup) — bucket must exist to reference in the policy ARN

## Target Location
AWS Console / IAM (no code files — infrastructure configuration)

---

## Functional Requirements

### FR-1: Create IAM Policy — SehatSamjhoS3AudioPolicy
- **What**: A customer-managed IAM policy scoped to the audio bucket only
- **Actions allowed**: `s3:PutObject`, `s3:GetObject`, `s3:DeleteObject`
- **Resource**: `arn:aws:s3:::sehatsamjho-audio-*/*` (audio prefix objects only)
- **Edge cases**: No `s3:ListBucket`, no `s3:*`, no wildcard bucket — principle of least privilege

### FR-2: Create IAM Role — SehatSamjhoEC2Role
- **What**: IAM role with trusted entity = EC2 service (`ec2.amazonaws.com`)
- **Attach policy**: SehatSamjhoS3AudioPolicy from FR-1
- **No other policies**: No AdministratorAccess, no AmazonS3FullAccess — only the custom policy

### FR-3: Create Instance Profile and Attach Role
- **What**: Create an instance profile named `SehatSamjhoEC2Profile`
- **Action**: Add `SehatSamjhoEC2Role` to the instance profile
- **Attach to EC2**: Associate the instance profile with the EC2 instance from S12.1

### FR-4: Remove Static AWS Credentials from Application Config
- **What**: The application (boto3) should use the instance profile for credentials, not `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` env vars
- **How**: boto3 automatically discovers credentials from instance metadata when no explicit keys are configured
- **Edge cases**: Local development still uses `.env` keys; only the prod EC2 environment relies on the instance profile

### FR-5: Verify Credential Chain Works
- **What**: SSH into EC2 and verify the instance can access S3 via the role
- **Test command**: `aws s3 ls s3://sehatsamjho-audio-{account_id}/` should succeed
- **Negative test**: Attempt to access a different bucket — should be denied

---

## Tangible Outcomes

- [ ] **Outcome 1**: IAM policy `SehatSamjhoS3AudioPolicy` exists with exactly 3 S3 actions on the audio bucket ARN
- [ ] **Outcome 2**: IAM role `SehatSamjhoEC2Role` exists with trusted entity `ec2.amazonaws.com` and only the custom policy attached
- [ ] **Outcome 3**: Instance profile `SehatSamjhoEC2Profile` is attached to the EC2 instance
- [ ] **Outcome 4**: `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` are NOT set in the production `.env` file on EC2
- [ ] **Outcome 5**: boto3 on EC2 can PutObject and GetObject to the audio bucket without explicit credentials
- [ ] **Outcome 6**: boto3 on EC2 CANNOT access any other S3 bucket (least privilege confirmed)

---

## Test-Driven Requirements

### Manual Verification Steps (No Automated Tests — AWS Console / CLI)
1. **verify_policy_exists**: `aws iam get-policy --policy-arn arn:aws:iam::{account_id}:policy/SehatSamjhoS3AudioPolicy` returns 200
2. **verify_policy_document**: Policy JSON contains exactly `s3:PutObject`, `s3:GetObject`, `s3:DeleteObject` and resource is scoped to the audio bucket
3. **verify_role_exists**: `aws iam get-role --role-name SehatSamjhoEC2Role` returns AssumeRolePolicyDocument with `ec2.amazonaws.com`
4. **verify_role_policies**: `aws iam list-attached-role-policies --role-name SehatSamjhoEC2Role` returns exactly 1 policy
5. **verify_instance_profile**: `aws ec2 describe-instances --instance-ids {id}` shows `IamInstanceProfile` is set
6. **verify_s3_put**: From EC2: `echo "test" | aws s3 cp - s3://sehatsamjho-audio-{account_id}/test.txt` succeeds
7. **verify_s3_get**: From EC2: `aws s3 cp s3://sehatsamjho-audio-{account_id}/test.txt -` succeeds
8. **verify_s3_denied_other_bucket**: From EC2: `aws s3 ls s3://some-other-bucket/` fails with AccessDenied
9. **verify_no_static_keys**: `.env` on EC2 does NOT contain `AWS_ACCESS_KEY_ID` or `AWS_SECRET_ACCESS_KEY`

### Mocking Strategy
- N/A — this is an infrastructure spec with manual verification

### Coverage Expectation
- All 9 verification steps pass on the live EC2 instance

---

## References
- roadmap.md (Phase 12, S12.4)
- specs/spec-S12.1-ec2-setup/ (EC2 instance)
- specs/spec-S12.3-s3-bucket/ (S3 bucket)
- AWS IAM best practices: https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html
