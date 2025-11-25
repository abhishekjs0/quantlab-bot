"""
Centralized Configuration Manager for QuantLab
Handles configuration for both backtesting and webhook services.
Supports loading from .env files and Google Secret Manager.
"""

import os
import json
import logging
from typing import Optional, Dict, Any
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

# Try to import Google Cloud Secret Manager (optional)
try:
    from google.cloud import secretmanager
    GCP_AVAILABLE = True
except ImportError:
    GCP_AVAILABLE = False
    logger.warning("Google Cloud Secret Manager not available - using .env only")


class ConfigManager:
    """
    Centralized configuration manager that loads from:
    1. Environment variables
    2. .env files (root and webhook-service)
    3. Google Secret Manager (if available)
    
    Priority: Environment Variables > Secret Manager > .env files
    """
    
    def __init__(self, 
                 env_file: Optional[str] = None,
                 use_secret_manager: bool = True,
                 gcp_project: Optional[str] = None):
        """
        Initialize configuration manager.
        
        Args:
            env_file: Path to .env file (defaults to root .env)
            use_secret_manager: Whether to use Google Secret Manager
            gcp_project: GCP project ID (auto-detected if None)
        """
        self.root_dir = Path(__file__).parent
        self.env_file = env_file or self.root_dir / ".env"
        self.use_secret_manager = use_secret_manager and GCP_AVAILABLE
        self.gcp_project = gcp_project or os.getenv("GCP_PROJECT") or os.getenv("GOOGLE_CLOUD_PROJECT")
        
        # Configuration cache
        self._config: Dict[str, Any] = {}
        self._secret_client = None
        
        # Initialize
        self._load_config()
    
    def _init_secret_manager(self) -> bool:
        """Initialize Google Secret Manager client"""
        if not self.use_secret_manager:
            return False
        
        try:
            if not self.gcp_project:
                logger.debug("No GCP project specified, skipping Secret Manager")
                return False
            
            self._secret_client = secretmanager.SecretManagerServiceClient()
            logger.info(f"✅ Secret Manager initialized for project: {self.gcp_project}")
            return True
        except Exception as e:
            logger.warning(f"Failed to initialize Secret Manager: {e}")
            return False
    
    def _load_from_env_file(self) -> Dict[str, str]:
        """Load configuration from .env file"""
        config = {}
        
        if not os.path.exists(self.env_file):
            logger.warning(f"⚠️  .env file not found: {self.env_file}")
            return config
        
        try:
            with open(self.env_file) as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    
                    if "=" in line:
                        key, value = line.split("=", 1)
                        config[key.strip()] = value.strip()
            
            logger.info(f"✅ Loaded {len(config)} variables from {self.env_file}")
        except Exception as e:
            logger.error(f"Failed to load .env file: {e}")
        
        return config
    
    def _load_from_secret_manager(self, secret_name: str) -> Optional[str]:
        """Load a secret from Google Secret Manager"""
        if not self._secret_client or not self.gcp_project:
            return None
        
        try:
            name = f"projects/{self.gcp_project}/secrets/{secret_name}/versions/latest"
            response = self._secret_client.access_secret_version(request={"name": name})
            payload = response.payload.data.decode("UTF-8")
            
            # Handle JSON secrets (like dhan-access-token)
            try:
                data = json.loads(payload)
                if isinstance(data, dict) and "access_token" in data:
                    return data["access_token"]
                return payload
            except json.JSONDecodeError:
                return payload
        except Exception as e:
            logger.debug(f"Secret {secret_name} not found in Secret Manager: {e}")
            return None
    
    def _load_config(self):
        """Load configuration from all sources"""
        # 1. Load from .env file
        env_config = self._load_from_env_file()
        self._config.update(env_config)
        
        # 2. Initialize Secret Manager
        if self.use_secret_manager:
            self._init_secret_manager()
        
        # 3. Override with environment variables
        for key in list(self._config.keys()):
            env_value = os.getenv(key)
            if env_value:
                self._config[key] = env_value
        
        logger.info(f"✅ Configuration loaded: {len(self._config)} variables")
    
    def get(self, key: str, default: Any = None, use_secret_manager: bool = True) -> Any:
        """
        Get configuration value with priority:
        1. Environment variable
        2. Secret Manager (if enabled)
        3. Cached config (.env file)
        4. Default value
        
        Args:
            key: Configuration key
            default: Default value if not found
            use_secret_manager: Whether to try Secret Manager
            
        Returns:
            Configuration value
        """
        # 1. Check environment variable
        env_value = os.getenv(key)
        if env_value:
            return env_value
        
        # 2. Check Secret Manager
        if use_secret_manager and self._secret_client:
            # Map common env vars to secret names
            secret_map = {
                "DHAN_ACCESS_TOKEN": "dhan-access-token",
                "DHAN_API_KEY": "dhan-api-key",
                "DHAN_API_SECRET": "dhan-api-secret",
                "DHAN_USER_ID": "dhan-mobile-number",
                "DHAN_TOTP_SECRET": "dhan-totp-secret",
                "DHAN_PASSWORD": "dhan-password",
                "DHAN_PIN": "dhan-pin",
            }
            
            secret_name = secret_map.get(key, key.lower().replace("_", "-"))
            secret_value = self._load_from_secret_manager(secret_name)
            if secret_value:
                return secret_value
        
        # 3. Check cached config
        if key in self._config:
            return self._config[key]
        
        # 4. Return default
        return default
    
    def get_dhan_config(self) -> Dict[str, str]:
        """
        Get all Dhan-related configuration.
        
        Returns:
            Dictionary with Dhan configuration
        """
        return {
            "client_id": self.get("DHAN_CLIENT_ID"),
            "access_token": self.get("DHAN_ACCESS_TOKEN"),
            "api_key": self.get("DHAN_API_KEY"),
            "api_secret": self.get("DHAN_API_SECRET"),
            "user_id": self.get("DHAN_USER_ID"),
            "password": self.get("DHAN_PASSWORD"),
            "totp_secret": self.get("DHAN_TOTP_SECRET"),
            "pin": self.get("DHAN_PIN"),
            "redirect_uri": self.get("DHAN_REDIRECT_URI"),
        }
    
    def update_token(self, new_token: str, expiry: Optional[datetime] = None) -> bool:
        """
        Update DHAN_ACCESS_TOKEN in all storage locations.
        
        Args:
            new_token: New access token
            expiry: Token expiry datetime
            
        Returns:
            True if at least one update succeeded
        """
        success = False
        
        # 1. Update Secret Manager
        if self._secret_client and self.gcp_project:
            try:
                payload = {
                    "access_token": new_token,
                    "expiry": expiry.isoformat() if expiry else None,
                    "updated_at": datetime.now().isoformat()
                }
                payload_bytes = json.dumps(payload).encode("UTF-8")
                
                parent = f"projects/{self.gcp_project}/secrets/dhan-access-token"
                self._secret_client.add_secret_version(
                    request={"parent": parent, "payload": {"data": payload_bytes}}
                )
                logger.info("✅ Updated token in Secret Manager")
                success = True
            except Exception as e:
                logger.error(f"Failed to update Secret Manager: {e}")
        
        # 2. Update .env files
        env_files = [
            self.root_dir / ".env",
            self.root_dir / "webhook-service" / ".env"
        ]
        
        for env_path in env_files:
            try:
                if not env_path.exists():
                    continue
                
                lines = env_path.read_text().splitlines()
                updated = False
                new_lines = []
                
                for line in lines:
                    if line.startswith("DHAN_ACCESS_TOKEN="):
                        new_lines.append(f"DHAN_ACCESS_TOKEN={new_token}")
                        updated = True
                    else:
                        new_lines.append(line)
                
                if not updated:
                    new_lines.append(f"\nDHAN_ACCESS_TOKEN={new_token}")
                
                env_path.write_text("\n".join(new_lines) + "\n")
                logger.info(f"✅ Updated {env_path}")
                success = True
            except Exception as e:
                logger.error(f"Failed to update {env_path}: {e}")
        
        # 3. Update cache
        self._config["DHAN_ACCESS_TOKEN"] = new_token
        
        return success
    
    def validate_dhan_config(self) -> tuple[bool, list[str]]:
        """
        Validate that all required Dhan configuration is present.
        
        Returns:
            Tuple of (is_valid, missing_keys)
        """
        required_keys = [
            "DHAN_CLIENT_ID",
            "DHAN_API_KEY",
            "DHAN_API_SECRET",
            "DHAN_TOTP_SECRET",
            "DHAN_USER_ID",
            "DHAN_PASSWORD",
        ]
        
        missing = []
        for key in required_keys:
            if not self.get(key):
                missing.append(key)
        
        return (len(missing) == 0, missing)
    
    def __repr__(self) -> str:
        return f"ConfigManager(env_file={self.env_file}, gcp_project={self.gcp_project})"


# Global config instance
_config: Optional[ConfigManager] = None


def get_config() -> ConfigManager:
    """Get or create global configuration manager instance"""
    global _config
    if _config is None:
        _config = ConfigManager()
    return _config


def reload_config():
    """Force reload configuration from all sources"""
    global _config
    _config = ConfigManager()
    return _config
