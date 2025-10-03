import os
import yaml
from pathlib import Path
from strands.handlers.callback_handler import PrintingCallbackHandler


def get_callback_handler():
    """
    Returns the appropriate callback handler based on environment.
    In dev: returns default strands callback handler
    In prod: returns None
    """
    env = os.getenv("ENVIRONMENT", "dev").lower()
    if env == "prod":
        return None
    else:
        return PrintingCallbackHandler()


def load_config():
    """Load configuration from config.yaml file."""
    project_root = Path(__file__).parent.parent
    config_path = project_root / "config.yaml"
    
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in config file: {e}")


def check_aws_credentials():
    """
    Check if AWS credentials are available and properly configured.

    Returns:
        tuple: (bool, str) - (credentials_available, error_message)
    """
    try:
        import boto3
        from botocore.exceptions import NoCredentialsError, PartialCredentialsError

        # Try to create a session and get credentials
        session = boto3.Session()
        credentials = session.get_credentials()

        if credentials is None:
            return False, "AWS credentials not found. Please configure your AWS credentials using one of the following methods:\n" \
                         "1. Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables\n" \
                         "2. Configure AWS CLI: aws configure\n" \
                         "3. Use IAM roles if running on EC2\n" \
                         "4. Create ~/.aws/credentials file"

        # Test that credentials work by trying to get caller identity
        sts = boto3.client('sts')
        sts.get_caller_identity()

        return True, ""

    except (NoCredentialsError, PartialCredentialsError):
        return False, "AWS credentials not found or incomplete. Please configure your AWS credentials using one of the following methods:\n" \
                     "1. Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables\n" \
                     "2. Configure AWS CLI: aws configure\n" \
                     "3. Use IAM roles if running on EC2\n" \
                     "4. Create ~/.aws/credentials file"
    except Exception as e:
        return False, f"Error checking AWS credentials: {str(e)}"


# Export configuration object
CONFIG = load_config()


def get_chbuild_directory():
    """Get the configured chbuild directory from config.yaml."""
    try:
        return CONFIG.get('settings', {}).get('chbuild_directory', '.')
    except:
        # Fallback to current directory if config is not available
        return '.'


def get_model_config(model_type: str = "default"):
    """
    Get model configuration from config.yaml.
    
    Args:
        model_type: Type of model config to get (default, planning, basic)
        
    Returns:
        dict: Model configuration parameters
    """
    try:
        models_config = CONFIG.get('models', {})
        model_config = models_config.get(model_type, models_config.get('default', {}))
        
        # Fallback configuration if nothing is found in config
        if not model_config:
            return {
                'model_id': 'us.anthropic.claude-sonnet-4-20250514-v1:0',
                'max_tokens': 8192,
                'temperature': 1,
                'additional_request_fields': {
                    'anthropic_beta': ['interleaved-thinking-2025-05-14'],
                    'reasoning_config': {
                        'type': 'enabled',
                        'budget_tokens': 3000
                    }
                }
            }
        
        return model_config
    except:
        # Fallback configuration if config loading fails
        return {
            'model_id': 'us.anthropic.claude-sonnet-4-20250514-v1:0',
            'max_tokens': 8192,
            'temperature': 1,
            'additional_request_fields': {
                'anthropic_beta': ['interleaved-thinking-2025-05-14'],
                'reasoning_config': {
                    'type': 'enabled',
                    'budget_tokens': 3000
                }
            }
        }


def create_bedrock_model(model_type: str = "default"):
    """
    Create a BedrockModel instance using configuration from config.yaml.
    
    Args:
        model_type: Type of model config to use (default, planning, basic)
        
    Returns:
        BedrockModel: Configured model instance
    """
    from strands.models import BedrockModel
    import boto3
    from botocore.config import Config
    
    # Get timeout settings from config with generous defaults
    settings = CONFIG.get('settings', {})
    connect_timeout = settings.get('connect_timeout', 120)
    read_timeout = settings.get('read_timeout', 300)
    max_retries = settings.get('max_retries', 3)
        # Create boto3 config with generous timeouts
    boto_client_config = Config(
        region_name=os.getenv('AWS_REGION', 'us-east-1'),
        retries={
            'max_attempts': max_retries,
            'mode': 'adaptive'
        },
        read_timeout=read_timeout,
        connect_timeout=connect_timeout,
        max_pool_connections=50
    )
    config = get_model_config(model_type)
    config['boto_client_config'] = boto_client_config

    return BedrockModel(**config)