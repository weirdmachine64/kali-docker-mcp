#!/usr/bin/env python3
"""
Configuration management utility for Kali MCP Server
Provides centralized configuration loading and access
"""
import os
import logging
from typing import Dict, Any, Optional, List
import tomllib

logger = logging.getLogger("kali-mcp-server.utils.config")


class PentestConfig:
    """
    Centralized configuration manager for pentest operations.
    Loads and provides access to consolidated configuration settings.
    Supports TOML format.
    """
    
    def __init__(self, config_path: str = "/app/config.toml"):
        """
        Initialize configuration manager
        
        Args:
            config_path: Path to the TOML config file
        """
        self.config_path = config_path
        self._config: Dict[str, Any] = {}
        self._load_config()
    
    def _load_config(self) -> None:
        """Load configuration from TOML file"""
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Config file not found: {self.config_path}")
        
        if not self.config_path.endswith('.toml'):
            raise ValueError(f"Unsupported config format: {self.config_path}")
        
        self._load_toml()
    
    def _load_toml(self) -> None:
        """Load TOML configuration file"""
        try:
            with open(self.config_path, 'rb') as file:
                self._config = tomllib.load(file)
            self._validate_config()
        except tomllib.TOMLDecodeError as e:
            raise ValueError(f"Invalid TOML format in {self.config_path}: {e}")
        except Exception as e:
            raise RuntimeError(f"Failed to load config file {self.config_path}: {e}")
    
    def _validate_config(self) -> None:
        """Validate required configuration sections"""
        required_sections = ['WORKSPACE', 'INTERACTSH', 'SERVICES']
        for section in required_sections:
            if section not in self._config:
                logger.warning(f"Missing required config section: {section}")
                self._config[section] = {}
    
    def reload(self) -> None:
        """Reload configuration from file"""
        self._load_config()
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get configuration value using dot notation
        
        Args:
            key_path: Dot-separated path to config value (e.g., 'IMAP.host')
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        keys = key_path.split('.')
        value = self._config
        
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
                if value is None:
                    return default
            else:
                return default
        
        return value
    
    def get_section(self, section: str) -> Dict[str, Any]:
        """
        Get entire configuration section
        
        Args:
            section: Section name (e.g., 'IMAP', 'INTERACTSH')
            
        Returns:
            Configuration section dictionary
        """
        return self._config.get(section, {})
    
    def set(self, key_path: str, value: Any) -> None:
        """
        Set configuration value using dot notation
        
        Args:
            key_path: Dot-separated path to config value
            value: Value to set
        """
        keys = key_path.split('.')
        config = self._config
        
        for key in keys[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]
        
        config[keys[-1]] = value
    
    # Convenience methods for common config sections
    
    def get_interactsh_config(self) -> Dict[str, Any]:
        """Get Interactsh configuration section"""
        return self.get_section('INTERACTSH')
    
    def get_workspace_config(self) -> Dict[str, Any]:
        """Get workspace configuration"""
        return self.get_section('WORKSPACE')
    
    def get_workspace_directory(self) -> str:
        """Get workspace directory path"""
        return self.get('WORKSPACE.directory', '/app/workspace/default')
    
    def get_workspace_structure(self) -> List[str]:
        """Get workspace directory structure"""
        return self.get('WORKSPACE.structure', ['recon', 'scans', 'exploits', 'evidence', 'reports', 'logs'])
    
    def ensure_workspace_dirs(self, workspace_dir: str = None) -> None:
        """
        Create workspace directory structure
        
        Args:
            workspace_dir: Custom workspace directory (optional)
        """
        base_dir = workspace_dir or self.get_workspace_directory()
        structure = self.get_workspace_structure()
        
        # Create base directory
        os.makedirs(base_dir, exist_ok=True)
        logger.info(f"Created workspace directory: {base_dir}")
        
        # Create subdirectories
        for subdir in structure:
            full_path = os.path.join(base_dir, subdir)
            os.makedirs(full_path, exist_ok=True)
            logger.debug(f"Created subdirectory: {full_path}")
    
    def is_enabled(self, service: str) -> bool:
        """
        Check if a service is enabled
        
        Args:
            service: Service name (e.g., 'INTERACTSH')
            
        Returns:
            True if enabled, False otherwise
        """
        return self.get(f'{service}.enabled', False)
    
    def to_dict(self) -> Dict[str, Any]:
        """Return entire configuration as dictionary"""
        return self._config.copy()


# Global configuration instance
_global_config: Optional[PentestConfig] = None


def get_config(config_path: str = "/app/config.toml") -> PentestConfig:
    """
    Get or create global configuration instance
    
    Args:
        config_path: Path to config file (defaults to config.toml)
        
    Returns:
        PentestConfig instance
    """
    global _global_config
    
    if _global_config is None:
        _global_config = PentestConfig(config_path)
    
    return _global_config


def reload_config() -> None:
    """Reload global configuration from file"""
    global _global_config
    
    if _global_config is not None:
        _global_config.reload()
