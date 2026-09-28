# Yamaha Discord RPC

A lightweight Discord Rich Presence client for Yamaha receivers (YXC) and
optionally Navidrome (Subsonic API) now-playing.

## Features

-   Display current playing song on Discord RPC
-   Shows as **Listening to (Artist)** (Spotify-style), not Playing
-   Yamaha MusicCast and/or Navidrome (any of your devices)
-   Source mode: `auto` (prefer Navidrome when actively playing, else Yamaha), `yamaha`, or `navidrome`
-   Shows album art via public HTTPS covers (Last.fm if keyed, else iTunes Search)
-   Shows current timestamp

Playback control is **not supported**, as the Yamaha API does not expose
play/pause for most sources.

------------------------------------------------------------------------

## Requirements

-   Python 3.10+
-   `pypresence` 4.6+ (for Listening activity type)
-   A Yamaha AVR that supports the YXC API (RX-V6A, RX-A2A, etc.)
-   Your Discord Application ID
-   Your Yamaha device's IP address (optional if using Navidrome only)
-   Navidrome base URL + username + password (optional if using Yamaha only)
-   LastFM api key (Optional)

Navidrome credentials are saved in `yamaha_rpc_config.json` (or via env
`NAVIDROME_URL`, `NAVIDROME_USER`, `NAVIDROME_PASSWORD`). Do not commit that file.

------------------------------------------------------------------------

## Setup Instructions

### 1. Create a Discord Application

1.  Go to the **Discord Developer Portal** (https://discord.com/developers/applications)
2.  Click **New Application**

### 2. Get Your Discord Application ID

This is found in the Developer Portal under **General Information →
Application ID**

### 3. Find Your Yamaha AVR IP Address

You can find this on your receiver:

    Setup → Network → Network Information

### 5. Running the App

Install dependencies:

    pip install -r requirements.txt

Run:

    python yamaha_rpc_gui.py

### 6. Windows exe (optional)

A one-file Windows build is produced by GitHub Actions (`Build Windows exe`) or locally on Windows:

    powershell -ExecutionPolicy Bypass -File .\scripts\build-windows.ps1

Output: `dist/YamahaDiscordRPC.exe` (unsigned — SmartScreen may warn on first run).

------------------------------------------------------------------------

## Limitations

-   Yamaha does **not** expose play/pause transport controls in the
    public YXC API for most sources.
    -   This means the bot cannot control Spotify, AirPlay, Bluetooth,
        HDMI-CEC, or Net Radio playback.
-   If Yamaha releases transport commands publicly in the future, they
    can be added.

------------------------------------------------------------------------

## Contributing

Feel free to open issues or submit pull requests.\
Open-source and made for the community!
