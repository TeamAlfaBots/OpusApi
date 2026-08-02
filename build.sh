#!/usr/bin/env bash
# Render build script.
# Python deps + Deno install (signature/n-challenge solving ke liye zaroori).
# ffmpeg alag install nahi karna padta — imageio-ffmpeg pip package
# (requirements.txt mein hai) apne saath static ffmpeg binary laata hai.

set -o errexit

pip install -r requirements.txt

# Deno install (agar already nahi hai)
if [ ! -f "$HOME/.deno/bin/deno" ]; then
  curl -fsSL https://deno.land/install.sh | sh -s -- -y
fi

echo "Build complete. Deno at: $HOME/.deno/bin/deno"
