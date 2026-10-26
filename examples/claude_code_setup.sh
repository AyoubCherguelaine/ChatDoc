#!/usr/bin/env bash
# Quickstart script to register DocuChat MCP Server with Claude Code CLI

echo "=== Registering DocuChat MCP Server with Claude Code ==="

# 1. Set your API Key (or leave empty for local development)
export DOCUCHAT_API_KEY="${DOCUCHAT_API_KEY:-docu_live_default_trial_key}"
export DOCUCHAT_BASE_URL="${DOCUCHAT_BASE_URL:-http://127.0.0.1:8000}"

# 2. Add DocuChat to Claude Code
claude mcp add docuchat -- python3 -m backend.mcp.server

echo "DocuChat MCP registered with Claude Code!"
echo "Now run 'claude' and prompt:"
echo "  'Upload invoice.pdf to DocuChat and extract all line items'"
echo "  'Search my contracts in DocuChat for indemnification terms'"

