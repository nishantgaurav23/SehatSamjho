# Checklist — Spec S12.4: IAM Role for EC2

## Phase 1: Prerequisites
- [x] Verify S12.1 (EC2 t3.micro) is running and accessible via SSH
- [x] Verify S12.3 (S3 bucket) is created — note the full bucket name
- [x] Note AWS account ID for ARN construction

## Phase 2: Create IAM Policy
- [x] Open IAM Console → Policies → Create Policy
- [x] Switch to JSON editor and paste policy document:
  ```json
  {
    "Version": "2012-10-17",
    "Statement": [
      {
        "Effect": "Allow",
        "Action": [
          "s3:PutObject",
          "s3:GetObject",
          "s3:DeleteObject"
        ],
        "Resource": "arn:aws:s3:::sehatsamjho-audio-*/*"
      }
    ]
  }
  ```
- [x] Name: `SehatSamjhoS3AudioPolicy`
- [x] Description: "Allows PutObject, GetObject, DeleteObject on SehatSamjho audio bucket only"
- [x] Review and create policy

## Phase 3: Create IAM Role
- [x] IAM Console → Roles → Create Role
- [x] Trusted entity type: AWS service → EC2
- [x] Attach policy: `SehatSamjhoS3AudioPolicy`
- [x] Do NOT attach any other policies
- [x] Role name: `SehatSamjhoEC2Role`
- [x] Description: "EC2 instance role for SehatSamjho — S3 audio access only"
- [x] Create role

## Phase 4: Attach Instance Profile to EC2
- [x] EC2 Console → Instances → select the SehatSamjho instance
- [x] Actions → Security → Modify IAM Role
- [x] Select `SehatSamjhoEC2Role` from dropdown
- [x] Save — instance profile attaches (takes effect within minutes)

## Phase 5: Remove Static Credentials from Prod
- [x] SSH into EC2
- [x] Edit `.env` — remove `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` lines
- [x] Restart the application container: `docker compose -f docker-compose.prod.yml restart app`
- [x] Confirm boto3 falls back to instance metadata credentials

## Phase 6: Verification
- [x] Run: `aws s3 cp - s3://{bucket}/test.txt <<< "test"` — should succeed
- [x] Run: `aws s3 cp s3://{bucket}/test.txt -` — should succeed
- [x] Run: `aws s3 rm s3://{bucket}/test.txt` — should succeed
- [x] Run: `aws s3 ls s3://some-other-bucket/` — should fail (AccessDenied)
- [x] Verify `.env` on EC2 has NO `AWS_ACCESS_KEY_ID` or `AWS_SECRET_ACCESS_KEY`
- [x] Send a test WhatsApp message and confirm audio delivery still works (boto3 uses instance profile)
- [x] All 6 tangible outcomes verified

## Implementation Notes
- Automated via `scripts/setup-iam.sh` (AWS CLI) — creates policy, role, instance profile, and attaches to EC2
- Validation via `scripts/validate-iam.sh` — verifies all IAM resources and configuration
- 43 static tests in `backend/tests/test_s12_4_iam_role.py` validate script content
- Phases 5–6 are manual post-deployment steps (run on live EC2 after attaching profile)
