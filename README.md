# Yamaha Discord RPC

A lightweight Discord-based remote control for Yamaha receivers using
the Yamaha Extended Control API (YXC).

## Features

-   Display current playing song on Discord RPC
-   Shows Album Art if LastFM api is given (Falls back to your default picture)
-   Shows current timestamp

Playback control is **not supported**, as the Yamaha API does not expose
play/pause for most sources.

------------------------------------------------------------------------

## Requirements

-   Python 3.10+
-   A Yamaha AVR that supports the YXC API (RX-V6A, RX-A2A, etc.)
-   A Discord Bot Token
-   Your Discord Application ID
-   Your Yamaha device's IP address
-   LastFM api key (Optional)

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

    pip install requests python-dotenv

Run:

    python yamaha_rpc_gui.py

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
