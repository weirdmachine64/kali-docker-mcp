#!/usr/bin/env python3
"""
Service token and API configuration utilities
"""
from typing import Dict, Any, Optional
from utils import config as config_module


def get_service_tokens(service_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Get configured service API tokens for reconnaissance and intelligence gathering
    
    Args:
        service_name: Optional service name (e.g., 'github', 'shodan'). 
                     If provided, returns only that service's raw config.
        
    Returns:
        If service_name is provided: Raw service configuration dictionary
        If service_name is None: Dictionary of all enabled services with their raw configs
        If error: Dictionary with 'error' key containing error message
    """
    try:
        config = config_module.get_config()
        services = config.get_section('SERVICES')
        
        if not services:
            return {'error': 'No services configured'}
        
        # If specific service requested, return just that one
        if service_name:
            service_config = services.get(service_name)
            if not service_config or not isinstance(service_config, dict):
                return {'error': f'Service "{service_name}" not found'}
            
            return service_config
        
        # Otherwise return all enabled services
        enabled_services = {}
        
        for service_key, service_config in services.items():
            if not isinstance(service_config, dict):
                continue
            
            # Only include enabled services
            if service_config.get('enabled', False):
                enabled_services[service_key] = service_config
        
        return enabled_services
        
    except Exception as e:
        return {'error': f'Failed to get service tokens: {str(e)}'}

