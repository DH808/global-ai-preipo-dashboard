#!/bin/zsh
cd /Users/mac/.hermes/apps/global-ai-preipo-dashboard
HOST=0.0.0.0 PORT=${PORT:-8826} /opt/homebrew/bin/node server.js
