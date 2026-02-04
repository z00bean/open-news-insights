#!/bin/bash

# Deployment script for Open News Insights
# Usage: ./deploy.sh [environment] [region]
# Example: ./deploy.sh dev us-east-1

set -e

ENVIRONMENT=${1:-dev}
REGION=${2:-us-east-1}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Validate environment
if [[ ! "$ENVIRONMENT" =~ ^(dev|staging|prod)$ ]]; then
    echo "Error: Environment must be one of: dev, staging, prod"
    exit 1
fi

# Set AWS region
export AWS_DEFAULT_REGION=$REGION

echo "Deploying Open News Insights to $ENVIRONMENT environment in $REGION region..."

# Build the application
echo "Building application..."
cd "$PROJECT_ROOT"
sam build --cached --parallel

# Deploy using environment-specific configuration
echo "Deploying to $ENVIRONMENT..."
sam deploy \
    --config-env "$ENVIRONMENT" \
    --region "$REGION" \
    --parameter-overrides \
        Environment="$ENVIRONMENT" \
        $(cat "infra/parameters/${ENVIRONMENT}.json" | jq -r '.Parameters | to_entries[] | "\(.key)=\(.value)"' | tr '\n' ' ')

# Get stack outputs
echo "Deployment completed. Stack outputs:"
aws cloudformation describe-stacks \
    --stack-name "open-news-insights-${ENVIRONMENT}" \
    --region "$REGION" \
    --query 'Stacks[0].Outputs[*].[OutputKey,OutputValue]' \
    --output table

echo "Deployment to $ENVIRONMENT completed successfully!"