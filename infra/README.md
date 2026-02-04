# Infrastructure Configuration

This directory contains infrastructure configuration and deployment scripts for the Open News Insights project.

## Directory Structure

```
infra/
├── README.md                 # This file
├── deploy.sh                 # Main deployment script
├── config_loader.py          # Configuration management utility
├── parameters/               # Environment-specific parameters
│   ├── dev.json             # Development environment parameters
│   ├── staging.json         # Staging environment parameters
│   └── prod.json            # Production environment parameters
└── env/                     # Environment variable files
    ├── dev.env              # Development environment variables
    ├── staging.env          # Staging environment variables
    └── prod.env             # Production environment variables
```

## Deployment

### Prerequisites

1. AWS CLI configured with appropriate credentials
2. SAM CLI installed
3. jq installed (for JSON processing in deployment scripts)
4. Python 3.11+ (for configuration utilities)

### Quick Deployment

Deploy to development environment:
```bash
./infra/deploy.sh dev
```

Deploy to staging environment:
```bash
./infra/deploy.sh staging us-west-2
```

Deploy to production environment:
```bash
./infra/deploy.sh prod us-east-1
```

### Manual Deployment

1. Build the application:
```bash
sam build --cached --parallel
```

2. Deploy using SAM:
```bash
# Development
sam deploy --config-env dev

# Staging
sam deploy --config-env staging

# Production
sam deploy --config-env prod
```

## Configuration Management

### Environment Parameters

Each environment has its own parameter file in `parameters/`:

- **dev.json**: Development environment with minimal logging retention
- **staging.json**: Staging environment with moderate logging retention
- **prod.json**: Production environment with extended logging retention

### Environment Variables

Environment-specific variables are defined in `env/` directory:

- **dev.env**: Development configuration with debug logging
- **staging.env**: Staging configuration with info logging
- **prod.env**: Production configuration with info logging

### Configuration Utility

Use the configuration loader to inspect environment settings:

```bash
# View complete configuration summary
python infra/config_loader.py dev summary

# Get parameters only
python infra/config_loader.py prod parameters

# Get environment variables only
python infra/config_loader.py staging env-vars
```

## Environment-Specific Settings

### Development (dev)
- Log retention: 7 days
- Log level: DEBUG
- Minimal monitoring
- No external API configuration required

### Staging (staging)
- Log retention: 14 days
- Log level: INFO
- Standard monitoring
- Optional external API configuration

### Production (prod)
- Log retention: 30 days
- Log level: INFO
- Full monitoring with alarms
- External API configuration recommended

## AWS Resources Created

The SAM template creates the following resources:

### Core Resources
- **Lambda Function**: Main processing function
- **API Gateway**: REST API with CORS support
- **IAM Role**: Lambda execution role with minimal permissions

### Monitoring & Logging
- **CloudWatch Log Groups**: For Lambda and API Gateway
- **CloudWatch Alarms**: Error rate and duration monitoring
- **Dead Letter Queue**: For failed Lambda invocations

### Security
- **IAM Policies**: Least-privilege access to AWS services
- **Resource-based permissions**: Scoped to specific Bedrock models

## Customization

### Adding New Environments

1. Create parameter file: `parameters/new-env.json`
2. Create environment variables: `env/new-env.env`
3. Add SAM configuration section in `samconfig.toml`
4. Update deployment script validation

### Modifying AWS Services

Update the SAM template (`template.yaml`) to:
- Add new AWS service permissions to IAM policies
- Configure additional CloudWatch alarms
- Add new environment variables or parameters

### External API Configuration

Set external API parameters in environment-specific files:
- `ExternalApiUrl`: Target API endpoint
- `ExternalApiKey`: Authentication key (use AWS Secrets Manager for production)

## Troubleshooting

### Common Issues

1. **Permission Denied**: Ensure AWS credentials have CloudFormation and IAM permissions
2. **Stack Already Exists**: Use `sam deploy --force-upload` to overwrite
3. **Parameter Validation**: Check parameter files for correct JSON format
4. **Region Mismatch**: Ensure AWS_DEFAULT_REGION matches deployment region

### Debugging

1. Check CloudFormation events:
```bash
aws cloudformation describe-stack-events --stack-name open-news-insights-dev
```

2. View Lambda logs:
```bash
aws logs tail /aws/lambda/open-news-insights-dev --follow
```

3. Test API Gateway:
```bash
curl -X POST https://your-api-id.execute-api.region.amazonaws.com/dev/process \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/article"}'
```

## Security Considerations

- Never commit API keys or secrets to version control
- Use AWS Secrets Manager for production secrets
- Regularly rotate API keys and credentials
- Monitor CloudWatch alarms for unusual activity
- Review IAM permissions periodically

## Cost Optimization

- Use appropriate log retention periods
- Monitor AWS service usage in CloudWatch
- Consider reserved capacity for production workloads
- Use Claude 3 Haiku model for cost-effective LLM operations