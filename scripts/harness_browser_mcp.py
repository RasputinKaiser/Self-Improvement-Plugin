#!/usr/bin/env python3
"""Harness Browser MCP — exposes browser_* tools to ncode via MCP stdio.

Connects to the harness-app's Unix domain socket at
~/Library/Application Support/HarnessApp/browser.sock
and forwards tool calls to the app's WKWebView IPC server.

Phase 1: read-only tools (browser_get_url, browser_get_title).
Phase 2+ will add navigate/click/extract/eval/screenshot.

Usage (registered in ~/.ncode/settings.local.json as an MCP server):
  python3 harness_browser_mcp.py

MCP Protocol: JSON-RPC over stdio. Tools are advertised via tools/list.
"""
import json
import os
import socket
import sys
import time
import uuid
from pathlib import Path

SOCKET_PATH = os.path.expanduser(
    "~/Library/Application Support/HarnessApp/browser.sock"
)

# Tool definitions exposed to ncode's MCP client
TOOLS = [
    {
        "name": "browser_get_url",
        "description": "Get the current URL of the harness-app's embedded browser (WKWebView).",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "browser_get_title",
        "description": "Get the current page <title> of the harness-app's embedded browser.",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "browser_navigate",
        "description": "Navigate the embedded WKWebView to a URL. Waits for page load (up to 8s). Returns {url, title, status}. Blocked schemes: file://, about:, data:, ftp:. Blocked: private IPs, localhost, .local.",
        "inputSchema": {
            "type": "object",
            "properties": {"url": {"type": "string", "description": "Full http(s) URL to navigate to"}},
            "required": ["url"],
        },
    },
    {
        "name": "browser_eval",
        "description": "Execute JavaScript in the WKWebView's page context. Returns {result}. Blocked patterns: fetch(), XMLHttpRequest, document.cookie, localStorage writes, window.open().",
        "inputSchema": {
            "type": "object",
            "properties": {"js": {"type": "string", "description": "JavaScript to evaluate"}},
            "required": ["js"],
        },
    },
    {
        "name": "browser_extract",
        "description": "Extract DOM elements matching a CSS selector. Returns {html, text, count}. Optionally pass attr to get a specific attribute instead of outerHTML.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "selector": {"type": "string", "description": "CSS selector (e.g. 'h1', '.content', '#main')"},
                "attr": {"type": "string", "description": "Optional: attribute to extract instead of outerHTML (e.g. 'href', 'src')"},
            },
            "required": ["selector"],
        },
    },
]

# --------------- Socket client ---------------

def send_command(tool: str, args: dict = None) -> dict:
    """Send a BrowserCommand to the app's socket server, wait for reply."""
    cmd = {
        "id": str(uuid.uuid4()),
        "tool": tool,
        "args": args or {},
    }
    line = json.dumps(cmd) + "\n"

    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(10)
        sock.connect(SOCKET_PATH)
        sock.sendall(line.encode("utf-8"))

        # Read reply (newline-delimited JSON)
        buf = b""
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            buf += chunk
            if b"\n" in buf:
                break
        sock.close()
    except (ConnectionRefusedError, FileNotFoundError) as e:
        return {"ok": False, "error": f"Cannot connect to harness-app browser socket at {SOCKET_PATH}. Is the app running? ({e})"}
    except socket.timeout:
        sock.close()
        return {"ok": False, "error": "Socket timeout — harness-app did not respond in 10s"}
    except Exception as e:
        return {"ok": False, "error": f"Socket error: {e}"}

    # Parse reply
    try:
        reply_line = buf.decode("utf-8").strip().split("\n")[0]
        return json.loads(reply_line)
    except (json.JSONDecodeError, IndexError) as e:
        return {"ok": False, "error": f"Reply parse error: {e}, got: {buf[:200]}"}


# --------------- MCP stdio protocol ---------------

def read_mcp_message():
    """Read one JSON-RPC message from stdin."""
    line = sys.stdin.readline()
    if not line:
        return None
    return json.loads(line)


def write_mcp_response(msg_id, result):
    """Write a JSON-RPC response to stdout."""
    response = {
        "jsonrpc": "2.0",
        "id": msg_id,
        "result": result,
    }
    sys.stdout.write(json.dumps(response) + "\n")
    sys.stdout.flush()


def write_mcp_error(msg_id, code, message):
    """Write a JSON-RPC error to stdout."""
    response = {
        "jsonrpc": "2.0",
        "id": msg_id,
        "error": {"code": code, "message": message},
    }
    sys.stdout.write(json.dumps(response) + "\n")
    sys.stdout.flush()


def handle_tool_call(msg):
    """Handle tools/call — dispatch to the app's socket."""
    msg_id = msg.get("id")
    params = msg.get("params", {})
    tool_name = params.get("name")
    args = params.get("arguments", {})

    if tool_name not in [t["name"] for t in TOOLS]:
        write_mcp_error(msg_id, -32601, f"Unknown tool: {tool_name}")
        return

    reply = send_command(tool_name, args)

    if reply.get("ok"):
        result = reply.get("result", {})
        # Extract the inner value for a clean text response
        if isinstance(result, dict):
            if "url" in result and "title" in result and "status" in result:
                # browser_navigate result
                text = f"URL: {result['url']}\nTitle: {result['title']}\nStatus: {result['status']}"
            elif "html" in result and "text" in result:
                # browser_extract result
                text = f"Count: {result.get('count', 0)}\n\nText:\n{result['text'][:2000]}"
                if result.get('html'):
                    text += f"\n\nHTML:\n{result['html'][:2000]}"
            elif "result" in result:
                # browser_eval result
                text = str(result["result"])
            elif "url" in result:
                text = result["url"]
            elif "title" in result:
                text = result["title"]
            else:
                text = json.dumps(result, indent=2)
        else:
            text = str(result)
        write_mcp_response(msg_id, {
            "content": [{"type": "text", "text": text}],
            "isError": False,
        })
    else:
        err = reply.get("error", "unknown error")
        write_mcp_response(msg_id, {
            "content": [{"type": "text", "text": f"Browser error: {err}"}],
            "isError": True,
        })


def main():
    while True:
        try:
            msg = read_mcp_message()
            if msg is None:
                break  # EOF — parent process closed stdin

            method = msg.get("method", "")
            msg_id = msg.get("id")

            if method == "initialize":
                write_mcp_response(msg_id, {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {
                        "name": "harness-browser",
                        "version": "0.1.0",
                    },
                })

            elif method == "tools/list":
                write_mcp_response(msg_id, {"tools": TOOLS})

            elif method == "tools/call":
                handle_tool_call(msg)

            elif method == "notifications/initialized":
                pass  # no response needed

            else:
                if msg_id is not None:
                    write_mcp_error(msg_id, -32601, f"Unknown method: {method}")

        except json.JSONDecodeError:
            continue
        except BrokenPipeError:
            break
        except KeyboardInterrupt:
            break


if __name__ == "__main__":
    main()