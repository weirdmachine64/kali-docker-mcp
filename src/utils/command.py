#!/usr/bin/env python3
"""
Command execution utilities for Kali MCP Server
Provides async command execution with timeout handling and process management
"""
import os
import asyncio
import logging
import signal
import uuid
from enum import Enum

# Configure logger
logger = logging.getLogger("kali-mcp-server.utils.command")


class CommandStatus(str, Enum):
    """Command execution status enumeration"""
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
    ERROR = "error"


async def run_command(command: str, timeout: int, cwd: str) -> tuple[str, str, int]:
    """
    Run a command with timeout and collect output

    Args:
        command: The command to execute
        timeout: Maximum execution time in seconds
        cwd: Current working directory for the command (required)

    Returns:
        Tuple of (stdout, stderr, return_code)
    """
    try:
        # Create the subprocess
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.DEVNULL,
            executable='/bin/bash',
            preexec_fn=os.setsid,
            cwd=cwd
        )

        try:
            # Read both streams concurrently with timeout
            stdout_data, stderr_data = await asyncio.wait_for(
                asyncio.gather(
                    process.stdout.read(),
                    process.stderr.read()
                ),
                timeout=timeout
            )

            # Wait for process to complete
            return_code = await process.wait()

            return (
                stdout_data.decode('utf-8', errors='replace').strip(),
                stderr_data.decode('utf-8', errors='replace').strip(),
                return_code
            )

        except asyncio.TimeoutError:
            # Clean up on timeout
            await _cleanup_process(process)
            return "", f"Command timed out after {timeout} seconds", -1

    except Exception as e:
        logger.error(f"Error executing command: {e}")
        return "", f"Error executing command: {str(e)}", -1


async def _cleanup_process(process):
    """Clean up a subprocess on timeout or cancellation"""
    try:
        # Try graceful termination first
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        try:
            await asyncio.wait_for(process.wait(), timeout=5)
        except asyncio.TimeoutError:
            # Force kill if graceful termination fails
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            await process.wait()
    except Exception:
        # Ignore cleanup errors
        pass


def generate_job_id() -> str:
    """Generate a unique job ID for background commands"""
    return str(uuid.uuid4())[:8]
