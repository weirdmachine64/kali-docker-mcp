#!/usr/bin/env python3
"""
Kali Linux MCP Server - Provides secure command execution capabilities in a containerized Kali environment
"""
import os
import sys
import logging
import asyncio
import signal
import uuid
import time
from typing import Optional, Dict, Any, Sequence
import mcp.types as types
from mcp.server import Server
from mcp.server.models import InitializationOptions
import mcp.server.stdio
import json
from utils import command, workspace, interactsh, services

# Configure logging to stderr
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger("kali-mcp-server")

# Initialize MCP server
server = Server("kali-mcp-server")

# Security settings
MAX_TIMEOUT = 36000  # 10 hours max for long-running tasks
DEFAULT_TIMEOUT = 300

# Background job tracking
background_jobs: Dict[str, Dict[str, Any]] = {}


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List available tools."""
    return [
        types.Tool(
            name="run_kali_command",
            description="Execute a command in the Kali Linux environment. Automatically runs as a background job if timeout > 60 seconds, otherwise runs synchronously.",
            inputSchema={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The command to execute in the Kali Linux environment (required)"
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Timeout in seconds (required)",
                        "minimum": 1,
                        "maximum": MAX_TIMEOUT
                    },
                    "cwd": {
                        "type": "string",
                        "description": "Current working directory for the command (required)"
                    }
                },
                "required": ["command", "timeout", "cwd"]
            }
        ),
        types.Tool(
            name="get_job_status",
            description="Check the status of a background job using its job ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "job_id": {
                        "type": "string",
                        "description": "The job ID returned by run_kali_command when timeout > 60"
                    }
                },
                "required": ["job_id"]
            }
        ),
        types.Tool(
            name="list_background_jobs",
            description="List all background jobs and their current status",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        types.Tool(
            name="cancel_job",
            description="Cancel a running background job using its job ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "job_id": {
                        "type": "string",
                        "description": "The job ID of the command to cancel"
                    }
                },
                "required": ["job_id"]
            }
        ),
        types.Tool(
            name="start_interactsh",
            description="Start an interactsh-client worker in the background to monitor for out-of-band interactions. Returns generated payload URLs.",
            inputSchema={
                "type": "object",
                "properties": {
                    "output_file": {
                        "type": "string",
                        "description": "Path to output JSON file for interactions (overrides config file setting)"
                    }
                }
            }
        ),
        types.Tool(
            name="poll_interactsh",
            description="Poll and retrieve all recorded interactions from the interactsh output file",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        types.Tool(
            name="get_interactsh_status",
            description="Get the current status of the interactsh worker (running/stopped, payloads, runtime, etc.)",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        types.Tool(
            name="stop_interactsh",
            description="Stop the running interactsh-client worker",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        types.Tool(
            name="get_workspace_info",
            description="Get the workspace directory path and folder structure configuration",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        types.Tool(
            name="get_service_tokens",
            description="Get all configured service API tokens for reconnaissance and intelligence gathering (GitHub, Shodan, Censys, VirusTotal, etc.).",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),

    ]


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> Sequence[types.TextContent]:
    """Handle tool calls."""    
    if name == "run_kali_command":
        result = await run_kali_command(arguments["command"], arguments["timeout"], arguments["cwd"])
        # If it's a direct command result with stdout, return just the stdout
        if isinstance(result, str):
            return [types.TextContent(type="text", text=result)]
        # Otherwise return JSON for background jobs, errors, etc.
        return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
    elif name == "get_job_status":
        result = await get_job_status(arguments["job_id"])
        # If it's a formatted output string, return it directly
        if isinstance(result, str):
            return [types.TextContent(type="text", text=result)]
        # Otherwise return JSON for status info, errors, etc.
        return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
    elif name == "list_background_jobs":
        result = await list_background_jobs()
        return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
    elif name == "cancel_job":
        result = await cancel_job(arguments["job_id"])
        return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
    elif name == "get_workspace_info":
        result = await workspace.get_workspace_info()
        return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
    elif name == "start_interactsh":
        result = await interactsh.start_interactsh(arguments.get("output_file"))
        return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
    elif name == "poll_interactsh":
        result = await interactsh.poll_interactsh()
        return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
    elif name == "get_interactsh_status":
        result = await interactsh.get_interactsh_status()
        return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
    elif name == "stop_interactsh":
        result = await interactsh.stop_interactsh()
        return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
    elif name == "get_service_tokens":
        result = services.get_service_tokens()
        return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
    else:
        raise ValueError(f"Unknown tool: {name}")


async def run_kali_command(cmd: str, timeout: int, cwd: str) -> Dict[str, Any]:
    """
    Execute a command in the Kali Linux environment. If timeout > 60 seconds, runs as a background job; otherwise, runs synchronously.
    
    Args:
        cmd: The command to execute in the Kali Linux environment
        timeout: Maximum time to wait for command completion
        cwd: Current working directory for the command (required)
    
    Returns:
        If timeout > 60: JSON string with job ID and command details
        If timeout <= 60: Formatted output with stdout, stderr, and return code
    """
    logger.info(f"Executing command {'as background job' if timeout > 60 else 'synchronously'}: {cmd[:100]}{'...' if len(cmd) > 100 else ''}")
    
    try:
        # Basic command check
        if not cmd.strip():
            return {"error": "Command cannot be empty", "status": "error"}
        
        # Determine if to run as job based on timeout
        as_job = timeout > 60
        
        # Handle synchronous execution
        if not as_job:
            stdout, stderr, return_code = await command.run_command(cmd, timeout, cwd)
            
            # Return formatted output
            result = "---- [stdout] ----\n"
            result += (stdout if stdout else "(empty)") + "\n"
            result += "---- [stderr] ----\n"
            result += (stderr if stderr else "(empty)") + "\n"
            result += "---- [return code] ----\n"
            result += f"{return_code}\n"
            
            return result
        
        # Handle background job execution
        # Generate unique job ID
        job_id = command.generate_job_id()
        
        # Initialize tracking data
        background_jobs[job_id] = {
            'command': cmd,
            'status': 'running',
            'start_time': time.time(),
            'timeout': timeout,
            'return_code': None,
            'task': None,
            'process': None,
            'stdout': '',
            'stderr': ''
        }
        
        # Start the background task
        task = asyncio.create_task(run_background_command(job_id, cmd, timeout, cwd))
        background_jobs[job_id]['task'] = task
        
        # Wait briefly to catch immediate failures (e.g., command not found)
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=2.0)
            # If we get here, the command completed quickly (< 2 seconds)
            # Return the result immediately like a synchronous command
            stdout = background_jobs[job_id].get('stdout', '')
            stderr = background_jobs[job_id].get('stderr', '')
            return_code = background_jobs[job_id].get('return_code')
            
            # Clean up the job since we're returning it immediately
            del background_jobs[job_id]
            
            # Return formatted output
            result = "---- [stdout] ----\n"
            result += (stdout.strip() if stdout else "(empty)") + "\n"
            result += "---- [stderr] ----\n"
            result += (stderr.strip() if stderr else "(empty)") + "\n"
            result += "---- [return code] ----\n"
            result += f"{return_code}\n"
            
            return result
            
        except asyncio.TimeoutError:
            # Command is still running after 2 seconds, treat as background job
            pass
        
        return json.dumps({
            "job_id": job_id,
            "command": cmd,
            "status": "running",
            "timeout": timeout,
            "message": "Background job started"
        }, indent=2)
        
    except Exception as e:
        logger.error(f"Error starting command: {e}", exc_info=True)
        return {"error": f"Failed to start command: {str(e)}", "status": "error"}


async def get_job_status(job_id: str):
    """
    Check the status of a background job using its job ID.
    
    Returns:
        Status information for running jobs, formatted output for completed jobs
    """
    if job_id not in background_jobs:
        return {"error": f"Job ID `{job_id}` not found"}
    
    cmd_data = background_jobs[job_id]
    
    # Calculate runtime
    start_time = cmd_data['start_time']
    end_time = cmd_data.get('end_time', time.time())
    runtime = end_time - start_time
    
    # If job is still running, return status info
    if cmd_data['status'] == 'running':
        return {
            "job_id": job_id,
            "status": cmd_data['status'],
            "runtime": round(runtime, 2),
            "timeout": cmd_data['timeout'],
            "message": "Job is still running..."
        }
    
    # Job is completed, return formatted output like run_kali_command
    stdout = cmd_data.get('stdout', '')
    stderr = cmd_data.get('stderr', '')
    return_code = cmd_data.get('return_code')
    
    # Format output the same way as synchronous commands
    result = "---- [stdout] ----\n"
    result += (stdout.strip() if stdout else "(empty)") + "\n"
    result += "---- [stderr] ----\n"
    result += (stderr.strip() if stderr else "(empty)") + "\n"
    result += "---- [return code] ----\n"
    result += f"{return_code}\n"
    
    # Clean up completed jobs after showing their output
    del background_jobs[job_id]
    
    return result


async def list_background_jobs() -> Dict[str, Any]:
    """
    List all background jobs and their current status.
    
    Returns:
        Summary of all tracked background jobs
    """
    if not background_jobs:
        return {"jobs": [], "total_count": 0}
    
    jobs_list = []
    
    for job_id, cmd_data in background_jobs.items():
        start_time = cmd_data['start_time']
        end_time = cmd_data.get('end_time', time.time())
        runtime = end_time - start_time
        
        job_info = {
            "job_id": job_id,
            "status": cmd_data['status'],
            "runtime": round(runtime, 2),
            "timeout": cmd_data['timeout'],
            "command": cmd_data['command'][:50] + "..." if len(cmd_data['command']) > 50 else cmd_data['command']
        }
        
        jobs_list.append(job_info)
    
    return {
        "jobs": jobs_list,
        "total_count": len(jobs_list)
    }


async def cancel_job(job_id: str) -> Dict[str, Any]:
    """
    Cancel a running background job using its job ID.
    
    Returns:
        Status message indicating cancellation result
    """
    if job_id not in background_jobs:
        return {"error": f"Job ID `{job_id}` not found"}
    
    cmd_data = background_jobs[job_id]
    status = cmd_data['status']
    
    if status != 'running':
        return {
            "error": f"Cannot cancel job with status: {status.upper()}",
            "message": "Only running jobs can be cancelled",
            "job_id": job_id,
            "current_status": status
        }
    
    try:
        # Cancel the asyncio task
        if cmd_data.get('task'):
            cmd_data['task'].cancel()
        
        # Kill the process if it exists
        if cmd_data.get('process'):
            process = cmd_data['process']
            try:
                # Kill the process group to ensure all child processes are terminated
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                
                # Wait a moment for graceful termination
                try:
                    await asyncio.wait_for(process.wait(), timeout=3)
                except asyncio.TimeoutError:
                    # Force kill if graceful termination fails
                    os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                    await process.wait()
                    
            except ProcessLookupError:
                # Process already terminated
                pass
        
        # Update status
        cmd_data['status'] = 'cancelled'
        cmd_data['end_time'] = time.time()
        
        return {
            "job_id": job_id,
            "status": "cancelled",
            "message": "Job cancelled successfully"
        }
        
    except Exception as e:
        logger.error(f"Error cancelling job {job_id}: {e}", exc_info=True)
        return {"error": f"Failed to cancel job: {str(e)}"}


async def run_background_command(job_id: str, cmd: str, timeout: int, cwd: str):
    """Simple background command runner without complex buffering."""
    try:
        # Create the subprocess
        process = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.DEVNULL,
            executable='/bin/bash',
            preexec_fn=os.setsid,
            cwd=cwd
        )

        # Store process for potential cancellation
        background_jobs[job_id]['process'] = process

        try:
            # Wait for process completion with timeout
            stdout_data, stderr_data = await asyncio.wait_for(
                asyncio.gather(
                    process.stdout.read(),
                    process.stderr.read()
                ),
                timeout=timeout
            )

            return_code = await process.wait()

            # Store simple output
            background_jobs[job_id]['stdout'] = stdout_data.decode('utf-8', errors='replace')
            background_jobs[job_id]['stderr'] = stderr_data.decode('utf-8', errors='replace')
            background_jobs[job_id]['return_code'] = return_code
            background_jobs[job_id]['status'] = 'completed'
            background_jobs[job_id]['end_time'] = time.time()

        except asyncio.TimeoutError:
            # Clean up on timeout
            await _cleanup_process(process)
            background_jobs[job_id]['stderr'] = f"Command timed out after {timeout} seconds"
            background_jobs[job_id]['return_code'] = -1
            background_jobs[job_id]['status'] = 'timeout'
            background_jobs[job_id]['end_time'] = time.time()

    except asyncio.CancelledError:
        # Handle manual cancellation
        background_jobs[job_id]['status'] = 'cancelled'
        background_jobs[job_id]['end_time'] = time.time()
        background_jobs[job_id]['stderr'] = "Command was cancelled"
        raise
        
    except Exception as e:
        background_jobs[job_id]['status'] = 'error'
        background_jobs[job_id]['stderr'] = f"Failed to start command: {str(e)}"
        background_jobs[job_id]['end_time'] = time.time()


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


async def main():
    # Run the server using stdin/stdout streams
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        # Create a simple notification options object
        class NotificationOptions:
            def __init__(self):
                self.tools_changed = None
                self.prompts_changed = None
                self.resources_changed = None
                self.logging_changed = None
        
        await server.run(
            read_stream=read_stream,
            write_stream=write_stream,
            initialization_options=InitializationOptions(
                server_name="kali-mcp-server",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={}
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())