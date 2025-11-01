# Kali MCP Server

A Model Context Protocol (MCP) server that provides command execution capabilities in a containerized Kali Linux environment for semi-automated penetration testing and security research capabilities.

## Demo

[https://github.com/user-attachments/assets/demo.mp4
](https://github.com/user-attachments/assets/0e23d8ed-745f-43eb-b636-e1aa9e8d207e)

*Watch the Kali MCP Server in action*

## Disclaimer

This tool is provided for educational and authorized security testing purposes only. Use at your own risk. The authors are not responsible for any misuse or damage caused by this software. Always ensure you have proper authorization before conducting security assessments.

## Features

- **Containerized Command Execution**: Run Kali Linux security tools in a containerized environment
- **Background Job Management**: Long-running commands (>60s) automatically run as background jobs
- **Interactsh Integration**: Out-of-band interaction detection for blind vulnerabilities
- **Service API Management**: Centralized configuration for reconnaissance APIs (GitHub, Shodan, etc.)
- **Workspace Management**: Organized directory structure for pentest artifacts

## Requirements

- Docker & Docker Compose
- MCP-compatible client (Claude Code, Gemini CLI, VS Code with Copilot, etc.)

## Quick Start

1. **Start the container:**
   ```bash
   docker compose up --build -d
   ```

2. **Verify it's running:**
   ```bash
   docker ps | grep kali-mcp-server
   ```

3. **Configure your MCP client:**

   > **⚠️ IMPORTANT**: Disable any built-in terminal or command execution tools in your MCP client to prevent commands from being unintentionally executed on your host system instead of the Kali container. All security tools should run exclusively within the containerized environment for safety and isolation.

**Claude Desktop:**

```bash
claude mcp add --transport stdio kali-mcp-server "docker exec -i kali-mcp-server python3 /app/kali_server.py"
```

**Gemini CLI:**

```bash
gemini mcp add kali-mcp-server "docker exec -i kali-mcp-server python3 /app/kali_server.py"
```

**VS Code (Copilot):**

Create or edit `.vscode/mcp.json` in your workspace:

```json
{
  "servers": {
    "kali-mcp-server": {
      "type": "stdio",
      "command": "docker",
      "args": [
        "exec",
        "-i",
        "kali-mcp-server",
        "python3",
        "/app/kali_server.py"
      ]
    }
  }
}
```

**Others**

```json
{
   "mcpServers": {
      "kali-mcp-server": {
         "type": "stdio",
         "command": "docker",
         "args": [
            "exec",
            "-i",
            "kali-mcp-server",
            "python3",
            "/app/kali_server.py"
            ],
         "env": {}
      }
   }
}
```

**After configuration**: Restart your MCP client to load the Kali MCP server.

## Available Tools

### Core MCP Tools

- `run_kali_command` - Execute commands in Kali environment
- `get_job_status` - Check background job status
- `list_background_jobs` - List all running jobs
- `cancel_job` - Cancel a running job
- `get_workspace_info` - Get workspace configuration

### Interactsh Tools

- `start_interactsh` - Start out-of-band interaction monitoring
- `get_interactsh_status` - Check interactsh worker status
- `poll_interactsh` - Retrieve recorded interactions
- `stop_interactsh` - Stop interactsh worker

### Service Management

- `get_service_tokens` - Get configured API service tokens

## Pre-installed Security Tools

- **Network Scanning**: `nmap`, `masscan`
- **Web Testing**: `dirb`, `ffuf`, `whatweb`, `nikto`
- **DNS/Domain**: `dig`, `whois`, `dnsrecon`
- **Utilities**: `curl`, `wget`, `jq`, `exiftool`
- **Wordlists**: `Seclists`

## Configuration

Edit `config.toml` to configure:
- Workspace directory structure
- Interactsh settings
- API service tokens (GitHub, Shodan, VirusTotal, etc.)

## Security Notes

- Container runs with necessary privileges for security tools
- Network tools require elevated capabilities (NET_ADMIN, NET_RAW)
- All command execution is contained within the Docker environment
- API tokens should be configured securely in production

## License

This project is an independent open-source contribution and is **not affiliated with, endorsed by, or associated with OffSec or Kali Linux**. Kali Linux is a trademark of Offensive Security.
