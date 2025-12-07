# Yamaha Discord Remote

A lightweight Discord-based remote control for Yamaha receivers using
the Yamaha Extended Control API (YXC).

## Features

-   Volume Up / Volume Down
-   Power On / Power Off
-   Input Selection
-   Scene Activation
-   More features planned

Playback control is **not supported**, as the Yamaha API does not expose
play/pause for most sources.

------------------------------------------------------------------------

## Requirements

-   Python 3.10+
-   A Yamaha AVR that supports the YXC API (RX-V6A, RX-A2A, etc.)
-   A Discord Bot Token
-   Your Discord Application ID
-   Your Yamaha device's IP address

------------------------------------------------------------------------

## Setup Instructions

### 1. Create a Discord Bot

1.  Go to the **Discord Developer Portal**
2.  Click **New Application**
3.  Go to **Bot** → **Add Bot**
4.  Enable:
    -   **MESSAGE CONTENT INTENT**
    -   **SERVER MEMBERS INTENT** (optional)
5.  Copy the **Bot Token**
6.  Go to **OAuth2 → URL Generator**
    -   Select **bot**
    -   Select permissions:
        -   Send Messages
        -   Read Message History
    -   Copy the invite URL and add the bot to your server

### 2. Get Your Discord Application ID

This is found in the Developer Portal under **General Information →
Application ID**

### 3. Find Your Yamaha AVR IP Address

You can find this on your receiver:

    Setup → Network → Network Information

### 4. Generate Your API Keys File

Create a `.env` file next to the script:

    DISCORD_TOKEN=your_bot_token_here
    APPLICATION_ID=your_application_id_here
    YAMAHA_IP=192.168.x.x

### 5. Running the Bot

Install dependencies:

    pip install discord.py requests python-dotenv

Run:

    python main.py

------------------------------------------------------------------------

## Commands

Example slash commands the bot includes:

  Command        Description
  -------------- -------------------------
  /volume_up     Increase Yamaha volume
  /volume_down   Decrease Yamaha volume
  /power_on      Turn AVR on
  /power_off     Turn AVR off
  /set_input     Change input source
  /set_scene     Activate a Yamaha scene

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
