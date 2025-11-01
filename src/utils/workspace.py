#!/usr/bin/env python3
"""
Workspace utilities for Kali MCP Server
Provides workspace and configuration management
"""
import logging
from typing import Dict, Any
from utils import config as config_module

# Configure logger
logger = logging.getLogger("kali-mcp-server.utils.workspace")


async def get_workspace_info() -> Dict[str, Any]:
    """
    Get the workspace directory path and folder structure configuration
    
    Returns:
        Dictionary with directory path and structure array
        
    Raises:
        RuntimeError: If workspace configuration is not found
    """
    try:
        config = config_module.get_config()
        workspace_config = config.get_workspace_config()
        
        if not workspace_config:
            raise RuntimeError("Workspace configuration not found")
        
        return {
            "directory": workspace_config.get('directory', ''),
            "structure": workspace_config.get('structure', [])
        }
    except Exception as e:
        logger.error(f"Failed to get workspace info: {e}")
        return {"error": f"Failed to get workspace info: {str(e)}"}
