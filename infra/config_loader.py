#!/usr/bin/env python3
"""
Configuration loader for Open News Insights deployment
Loads environment-specific configuration from parameter files and environment variables
"""

import json
import os
from typing import Dict, Any, Optional
from pathlib import Path


class DeploymentConfig:
    """Manages deployment configuration for different environments"""
    
    def __init__(self, environment: str = "dev"):
        self.environment = environment
        self.script_dir = Path(__file__).parent
        self.project_root = self.script_dir.parent
        
    def load_parameters(self) -> Dict[str, Any]:
        """Load parameters from environment-specific JSON file"""
        param_file = self.script_dir / "parameters" / f"{self.environment}.json"
        
        if not param_file.exists():
            raise FileNotFoundError(f"Parameter file not found: {param_file}")
            
        with open(param_file, 'r') as f:
            config = json.load(f)
            
        return config.get("Parameters", {})
    
    def load_env_vars(self) -> Dict[str, str]:
        """Load environment variables from .env file"""
        env_file = self.script_dir / "env" / f"{self.environment}.env"
        env_vars = {}
        
        if env_file.exists():
            with open(env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        env_vars[key.strip()] = value.strip()
        
        return env_vars
    
    def get_stack_name(self) -> str:
        """Get the CloudFormation stack name for this environment"""
        return f"open-news-insights-{self.environment}"
    
    def get_deployment_region(self) -> str:
        """Get the AWS region for deployment"""
        return os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
    
    def validate_environment(self) -> bool:
        """Validate that the environment is supported"""
        return self.environment in ["dev", "staging", "prod"]
    
    def get_sam_config_env(self) -> str:
        """Get the SAM configuration environment name"""
        return self.environment
    
    def get_parameter_overrides(self) -> list:
        """Get parameter overrides for SAM deployment"""
        params = self.load_parameters()
        overrides = []
        
        for key, value in params.items():
            overrides.append(f"{key}={value}")
            
        return overrides
    
    def print_config_summary(self):
        """Print a summary of the current configuration"""
        print(f"Environment: {self.environment}")
        print(f"Stack Name: {self.get_stack_name()}")
        print(f"Region: {self.get_deployment_region()}")
        print(f"Valid Environment: {self.validate_environment()}")
        
        print("\nParameters:")
        params = self.load_parameters()
        for key, value in params.items():
            # Mask sensitive values
            display_value = "***" if "key" in key.lower() or "secret" in key.lower() else value
            print(f"  {key}: {display_value}")
        
        print("\nEnvironment Variables:")
        env_vars = self.load_env_vars()
        for key, value in env_vars.items():
            # Mask sensitive values
            display_value = "***" if "key" in key.lower() or "secret" in key.lower() else value
            print(f"  {key}: {display_value}")


def main():
    """CLI interface for configuration management"""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python config_loader.py <environment> [action]")
        print("Environments: dev, staging, prod")
        print("Actions: summary (default), parameters, env-vars")
        sys.exit(1)
    
    environment = sys.argv[1]
    action = sys.argv[2] if len(sys.argv) > 2 else "summary"
    
    config = DeploymentConfig(environment)
    
    if not config.validate_environment():
        print(f"Error: Invalid environment '{environment}'. Must be one of: dev, staging, prod")
        sys.exit(1)
    
    if action == "summary":
        config.print_config_summary()
    elif action == "parameters":
        params = config.load_parameters()
        print(json.dumps(params, indent=2))
    elif action == "env-vars":
        env_vars = config.load_env_vars()
        for key, value in env_vars.items():
            print(f"{key}={value}")
    else:
        print(f"Error: Unknown action '{action}'")
        sys.exit(1)


if __name__ == "__main__":
    main()