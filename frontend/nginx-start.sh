#!/bin/sh

# Start nginx immediately - don't block on backend
# The resolver directive will handle dynamic DNS resolution
echo "Starting Nginx..."
nginx -g "daemon off;"
