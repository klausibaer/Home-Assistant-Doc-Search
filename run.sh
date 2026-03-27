#!/usr/bin/with-contenv bashio

export CLAUDE_API_KEY=$(bashio::config 'claude_api_key')
export GMAIL_CLIENT_ID=$(bashio::config 'gmail_client_id')
export GMAIL_CLIENT_SECRET=$(bashio::config 'gmail_client_secret')
export GMAIL_REFRESH_TOKEN=$(bashio::config 'gmail_refresh_token')
export GCAL_CLIENT_ID=$(bashio::config 'gcal_client_id')
export GCAL_CLIENT_SECRET=$(bashio::config 'gcal_client_secret')
export GCAL_REFRESH_TOKEN=$(bashio::config 'gcal_refresh_token')

bashio::log.info "Arztsuche Outreach starting..."
python3 /app/server.py
