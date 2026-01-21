# Template Setup Guide

This document provides step-by-step instructions for setting up a new project from this template.

## Step 1: Create Repository from Template

### Option A: GitHub UI
1. Click the **"Use this template"** button on GitHub
2. Name your new repository
3. Choose visibility (public/private)
4. Click **"Create repository from template"**

### Option B: GitHub CLI
```bash
gh repo create my-new-infra --template YOUR_ORG/cdk-web-infra-template --private
cd my-new-infra
```

## Step 2: Initial Configuration

### 2.1 Copy and Configure constants.py
```bash
cp constants.py.template constants.py
```

Edit `constants.py` with your specific values:
- AWS account IDs
- Project prefix
- Domain names
- IP whitelist
- Alert email addresses

### 2.2 Update CDK Bootstrap Qualifier

In `Makefile`, update the bootstrap qualifier:
```makefile
# Change from:
-c "@aws-cdk/core:bootstrapQualifier=beg"
# To:
-c "@aws-cdk/core:bootstrapQualifier=YOUR_PREFIX"
```

### 2.3 Update pyproject.toml
```toml
[tool.poetry]
name = "your-project-infra"
description = "Your project description"
authors = ["Your Name <your.email@example.com>"]
```

## Step 3: AWS Prerequisites

### 3.1 Create Route53 Hosted Zones
For each domain in your `DOMAINS` configuration, ensure a Route53 hosted zone exists:
```bash
aws route53 create-hosted-zone --name yourdomain.com --caller-reference $(date +%s)
```

### 3.2 Bootstrap CDK in Target Accounts
```bash
# Dev account
npx cdk bootstrap aws://DEV_ACCOUNT_ID/eu-west-1 \
  --toolkit-stack-name cdk-bootstrap \
  -c "@aws-cdk/core:bootstrapQualifier=YOUR_PREFIX"

# Prod account
npx cdk bootstrap aws://PROD_ACCOUNT_ID/eu-west-1 \
  --toolkit-stack-name cdk-bootstrap \
  -c "@aws-cdk/core:bootstrapQualifier=YOUR_PREFIX"
```

### 3.3 Configure OIDC for GitHub Actions (Optional)
For CI/CD deployments, set up OIDC authentication:
```bash
# Create OIDC provider
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com \
  --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1
```

Create an IAM role with trust policy for your repository.

## Step 4: Local Development Setup

```bash
# Install dependencies
make bootstrap

# Verify setup
make synth ENV=dev

# Run tests
make test-unit
```

## Step 5: Deploy

```bash
# Deploy to dev
make deploy ENV=dev

# Verify deployment
aws cloudformation describe-stacks --stack-name network-dev
aws cloudformation describe-stacks --stack-name compute-dev
```

## Step 6: Remove Template Files

After setup, you can remove template-specific files:
```bash
rm TEMPLATE_README.md
rm constants.py.template
rm .github/TEMPLATE_SETUP.md
mv TEMPLATE_README.md README.md  # Or write your own README
```

## Checklist

- [ ] Repository created from template
- [ ] `constants.py` configured with your values
- [ ] `Makefile` bootstrap qualifier updated
- [ ] `pyproject.toml` updated
- [ ] Route53 hosted zones created
- [ ] CDK bootstrapped in all target accounts
- [ ] OIDC configured (for GitHub Actions)
- [ ] Initial deployment successful
- [ ] Template files removed
