# AWS OIDC setup for the `deploy-frontend` job

The `deploy-frontend` job authenticates to AWS **keylessly** via GitHub's OIDC
provider (no stored AWS access keys). If you see:

```
Error: Could not assume role with OIDC: Not authorized to perform sts:AssumeRoleWithWebIdentity.
```

it means AWS STS rejected the assume-role call: the IAM role's **trust policy**
does not authorize this repo's OIDC identity (or the OIDC provider isn't
registered in the account). This is an AWS-side configuration task — not a code
bug. Follow the steps below.

> Replace `<ACCOUNT_ID>` with your 12-digit AWS account ID and confirm the repo
> slug is exactly `kavithapedda-blip/login-app` (the OIDC `sub` is case-sensitive
> and uses the **GitHub** owner/repo, which may differ from your local git user).

---

## 1. Find this run's exact OIDC identity

The workflow includes a temporary **"Debug — show OIDC subject claim"** step that
prints the claims GitHub sends, e.g.:

```json
{
  "sub": "repo:kavithapedda-blip/login-app:ref:refs/heads/main",
  "aud": "sts.amazonaws.com",
  "repository": "kavithapedda-blip/login-app",
  "ref": "refs/heads/main"
}
```

Use the printed `sub` value to build the trust policy below. Remove the debug
step once the deploy succeeds.

## 2. Register the GitHub OIDC identity provider (once per account)

```bash
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com
```

`EntityAlreadyExists` just means it's already there — fine.

## 3. Create / update the IAM role and its trust policy

Trust policy (`trust-policy.json`) — authorizes any branch of this repo:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": { "Federated": "arn:aws:iam::<ACCOUNT_ID>:oidc-provider/token.actions.githubusercontent.com" },
    "Action": "sts:AssumeRoleWithWebIdentity",
    "Condition": {
      "StringEquals": { "token.actions.githubusercontent.com:aud": "sts.amazonaws.com" },
      "StringLike":   { "token.actions.githubusercontent.com:sub": "repo:kavithapedda-blip/login-app:*" }
    }
  }]
}
```

To restrict to the `main` branch only, replace the `StringLike` line with:

```json
"StringEquals": { "token.actions.githubusercontent.com:sub": "repo:kavithapedda-blip/login-app:ref:refs/heads/main" }
```

Create the role (or update an existing role's trust policy):

```bash
# new role
aws iam create-role \
  --role-name github-deploy-frontend \
  --assume-role-policy-document file://trust-policy.json

# OR update an existing role's trust relationship
aws iam update-assume-role-policy \
  --role-name github-deploy-frontend \
  --policy-document file://trust-policy.json
```

## 4. Grant the role permission to deploy to S3

The job runs `aws s3 sync frontend/ s3://$S3_BUCKET/ --delete`, which needs list +
write + delete on the bucket. Attach a policy like (`s3-policy.json`):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "s3:ListBucket",
      "Resource": "arn:aws:s3:::<BUCKET_NAME>"
    },
    {
      "Effect": "Allow",
      "Action": ["s3:PutObject", "s3:DeleteObject"],
      "Resource": "arn:aws:s3:::<BUCKET_NAME>/*"
    }
  ]
}
```

```bash
aws iam put-role-policy \
  --role-name github-deploy-frontend \
  --policy-name s3-frontend-deploy \
  --policy-document file://s3-policy.json
```

## 5. Set the repository secrets

GitHub repo → **Settings → Secrets and variables → Actions**:

| Secret | Example value |
|---|---|
| `AWS_ROLE_ARN` | `arn:aws:iam::<ACCOUNT_ID>:role/github-deploy-frontend` |
| `AWS_REGION`   | `us-east-1` (your bucket's region) |
| `S3_BUCKET`    | your bucket name |

## 6. Verify

- Re-run the workflow. The debug step prints the `sub`; the OIDC step should now
  succeed and the S3 sync should run.
- If it still denies, open **CloudTrail** and find the failed
  `AssumeRoleWithWebIdentity` event — it records the exact `sub`/`aud` presented
  and the deny reason, so you can match the trust-policy condition precisely.
- Once green, delete the temporary debug step from
  [.github/workflows/deploy.yml](../.github/workflows/deploy.yml).
