#!/bin/bash
cd "$(dirname "$0")"
export PATH="/Users/navyathag/.nvm/versions/node/v24.20.0/bin:$PATH"
exec node node_modules/.bin/vite --host 127.0.0.1
