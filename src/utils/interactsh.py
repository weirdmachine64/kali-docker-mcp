#!/usr/bin/env python3
"""
Interactsh utilities for Kali MCP Server
Provides interactsh client management for out-of-band interaction detection
"""
import os
import asyncio
import logging
import json
import time
import select
import re
from typing import Dict, List, Optional, Any
import signal
import subprocess
import pty
from utils import config
# Configure logger
logger = logging.getLogger("kali-mcp-server.utils.interactsh")

# Global state for interactsh worker
interactsh_worker: Optional[Dict[str, Any]] = None
DEFAULT_INTERACTSH_SERVER = "oast.pro"
DEFAULT_OUTPUT_FILE = "/app/workspace/interactsh_output.json"

async def start_interactsh(output_file: Optional[str] = None) -> Dict[str, Any]:
    """
    Start an interactsh-client worker in the background to monitor for out-of-band interactions.
    Returns generated payload URLs.

    Args:
        output_file: Path to output JSON file for interactions (overrides config setting)

    Returns:
        Dict containing payload URLs and worker status
    """
    global interactsh_worker

    # Check if worker is already running
    if interactsh_worker and interactsh_worker.get('status') == 'running':
        return {
            "error": "Interactsh worker is already running",
            "status": "error",
            "payloads": interactsh_worker.get('payloads', [])
        }

    try:
        # Load configuration
        cfg = config.get_config()
        interactsh_config = cfg.get_interactsh_config()
        
        # Check if interactsh is enabled
        if not interactsh_config.get('enabled', False):
            return {
                "error": "Interactsh is disabled in configuration",
                "status": "error"
            }
        
        # Build command with config parameters
        server = interactsh_config.get('server') or DEFAULT_INTERACTSH_SERVER
        token = interactsh_config.get('token') 
        number = interactsh_config.get('number', 1)
        
        cmd = ["interactsh-client", "-s", server, "-n", str(number)]
        
        # Add token if provided
        if token:
            cmd.extend(["-t", token])
        
        # Set default output file if not specified
        if not output_file:
            output_file = DEFAULT_OUTPUT_FILE
        
        # Add output file to command
        cmd.extend(["-o", output_file])
        
        # Clean up any existing output file
        if os.path.exists(output_file):
            os.remove(output_file)

        # Start interactsh-client in background with PTY
        master_fd, slave_fd = pty.openpty()
        process = subprocess.Popen(cmd, stdin=slave_fd, stdout=slave_fd, stderr=slave_fd, preexec_fn=os.setsid)
        os.close(slave_fd)  # Close the slave end in the parent process
        
        # Read initial output to get payloads
        time.sleep(10)  # Wait for interactsh to start and generate payloads
        try:
            if select.select([master_fd], [], [], 5)[0]:  # Wait up to 5 seconds for output
                initial_output = os.read(master_fd, 4096).decode('utf-8', errors='ignore')
                payloads = _parse_payloads_from_output(initial_output, server)
            else:
                payloads = []
        except Exception as e:
            logger.error(f"Error reading payloads: {e}")
            payloads = []
        finally:
            os.close(master_fd)  # Close master end after reading

        # Check if payloads were generated successfully
        if not payloads:
            # Kill the process since it failed to generate payloads
            subprocess.run(['pkill', '-f', 'interactsh-client'], check=False)
            return {
                "error": "Failed to generate interactsh payloads",
                "status": "error",
                "message": "No payloads were generated from interactsh-client"
            }

        # Initialize worker tracking
        interactsh_worker = {
            'status': 'running',
            'start_time': time.time(),
            'server': server,
            'output_file': output_file,
            'payloads': payloads,
            'command': " ".join(cmd)
        }

        logger.info(f"Interactsh worker started with {len(payloads)} payloads")

        return {
            "status": "running",
            "payloads": payloads,
            "server": server,
            "output_file": output_file,
            "message": f"Interactsh worker started successfully with {len(payloads)} payload URLs"
        }

    except Exception as e:
        logger.error(f"Error starting interactsh worker: {e}")
        return {
            "error": f"Failed to start interactsh worker: {str(e)}",
            "status": "error"
        }


async def poll_interactsh() -> Dict[str, Any]:
    """
    Poll and retrieve all recorded interactions from the interactsh output file.

    Returns:
        Dict containing interactions and status
    """
    global interactsh_worker

    if not interactsh_worker:
        return {
            "error": "No interactsh worker is running",
            "status": "error",
            "interactions": []
        }

    if interactsh_worker['status'] != 'running':
        return {
            "error": f"Interactsh worker is {interactsh_worker['status']}",
            "status": "error",
            "interactions": []
        }

    try:
        output_file = interactsh_worker['output_file']
        interactions = []

        # Read and parse JSONL file
        if os.path.exists(output_file):
            try:
                with open(output_file, 'r') as f:
                    lines = [line.strip() for line in f if line.strip()]
                
                if lines:
                    json_content = '[' + ','.join(lines) + ']'
                    interactions = json.loads(json_content)
                    
            except (FileNotFoundError, json.JSONDecodeError) as e:
                logger.warning(f"Error parsing interactions: {e}")

        return {
            "status": "success",
            "interactions": interactions,
            "count": len(interactions),
            "output_file": output_file,
            "file_exists": os.path.exists(output_file),
            "file_size": os.path.getsize(output_file) if os.path.exists(output_file) else 0,
            "message": f"Retrieved {len(interactions)} interactions"
        }

    except Exception as e:
        logger.error(f"Error polling interactsh interactions: {e}")
        return {
            "error": f"Failed to poll interactions: {str(e)}",
            "status": "error",
            "interactions": []
        }


async def get_interactsh_status() -> Dict[str, Any]:
    """
    Get the current status of the interactsh worker (running/stopped, payloads, runtime, etc.)

    Returns:
        Dict containing worker status information
    """
    global interactsh_worker

    if not interactsh_worker:
        return {
            "status": "stopped",
            "message": "No interactsh worker has been started"
        }

    worker_status = interactsh_worker['status']
    start_time = interactsh_worker['start_time']
    runtime = time.time() - start_time

    # Check if process is still running
    is_running = subprocess.run(['pgrep', '-f', 'interactsh-client'], capture_output=True).returncode == 0
    if not is_running and worker_status == 'running':
        worker_status = 'stopped'
        interactsh_worker['status'] = 'stopped'

    return {
        "status": worker_status,
        "runtime": round(runtime, 2),
        "server": interactsh_worker['server'],
        "output_file": interactsh_worker['output_file'],
        "payload_count": len(interactsh_worker.get('payloads', [])),
        "payloads": interactsh_worker.get('payloads', []),
        "message": "Worker is running" if is_running else "Worker has stopped"
    }


async def stop_interactsh() -> Dict[str, Any]:
    """
    Stop the running interactsh-client worker.

    Returns:
        Dict containing stop operation result
    """
    global interactsh_worker

    if not interactsh_worker:
        return {
            "error": "No interactsh worker is running",
            "status": "error"
        }

    if interactsh_worker['status'] != 'running':
        return {
            "error": f"Interactsh worker is already {interactsh_worker['status']}",
            "status": "error"
        }

    try:
        # Kill all interactsh-client processes
        subprocess.run(['pkill', '-f', 'interactsh-client'], check=False)

        # Update status
        interactsh_worker['status'] = 'stopped'
        runtime = time.time() - interactsh_worker['start_time']

        result = {
            "status": "stopped",
            "message": "Interactsh worker stopped successfully",
            "runtime": round(runtime, 2),
            "payload_count": len(interactsh_worker.get('payloads', []))
        }

        logger.info("Interactsh worker stopped")
        return result

    except Exception as e:
        logger.error(f"Error stopping interactsh worker: {e}")
        return {
            "error": f"Failed to stop interactsh worker: {str(e)}",
            "status": "error"
        }


def _parse_payloads_from_output(output: str, server: str) -> List[str]:
    """Parse payload URLs from interactsh output based on server."""
    
    # Remove ANSI codes
    clean_output = re.sub(r'\[[0-9;]*m', '', output)
    
    # Build patterns from server parameter
    patterns = []
    
    # Handle both single server and comma-separated servers
    server_list = [s.strip() for s in server.split(',')]
    
    # Build regex patterns for each server
    for srv in server_list:
        # Remove protocol if present
        clean_server = re.sub(r'^https?://', '', srv)
        # Escape special regex characters and build pattern
        escaped_server = re.escape(clean_server)
        pattern = rf'[a-zA-Z0-9]{{20,}}\.{escaped_server}'
        patterns.append(pattern)
    
    domains = []
    for pattern in patterns:
        domains.extend(re.findall(pattern, clean_output))
    
    urls = re.findall(r'https?://[^\s]+', clean_output)
    
    # Return unique payloads
    return list(dict.fromkeys(domains + urls))
