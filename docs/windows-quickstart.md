# DisWhisper for Windows

1. Extract the entire ZIP to a folder you want to keep.
2. Open **DisWhisper.Companion.exe**. The first launch starts a local service; no Python or .NET installation is needed.
3. In **Connect Discord**, open the Discord Developer Portal and create your own bot. Paste its token into the app, check the connection, invite it, and check again. Choose the server and language.
4. In **Models**, download Whisper Base, then choose **Use model**.
5. Connect the bot from **Home**, enter a Discord voice channel, and type **/join**.
6. Use **/leave** or **Finish meeting** to save and share the transcript.

The bot automatically creates **#live-transcript** if it has Manage Channels permission. No Administrator or privileged gateway intents are needed.

**Closing the window keeps DisWhisper in the tray.** Right-click the tray icon to show the app or quit. Quit finishes an active meeting before stopping the service. You can run **Create desktop shortcut.ps1** from the extracted folder to add a desktop shortcut.

Configuration, transcripts, logs, and models live in **%LOCALAPPDATA%\DisWhisper\Data**, separate from the extracted app. Updating the portable folder preserves your data. Keep only one production instance open.

**CPU works out of the box.** NVIDIA acceleration requires CUDA 12 cuBLAS and cuDNN 9 libraries. Automatic device selection falls back to CPU if they are missing. Models download separately and are not included in the ZIP.

For local meeting notes, install and run Ollama separately, then download an Ollama model in the app. Cloud providers are optional and may charge for usage.

Tell participants before starting transcription. Speech is processed on this PC with local models; Discord carries the call and the messages/files your bot shares. Settings lets you change sharing and saving behavior.

## Troubleshooting

- **Bot not in the server list:** use Invite bot, finish Discord's authorization, and check the connection again.
- **Commands missing:** choose a server in setup and reconnect. Global commands may take time to register.
- **No transcript channel:** verify Manage Channels, View Channel, and Send Messages permissions. The bot will not post into an unrelated channel.
- **Slow transcription:** use Whisper Base/Tiny or a Vosk model on CPU. Larger models need more resources.
- **No recognized speech:** confirm the bot joined the correct channel and is not server-deafened. Lower the silence threshold for a quiet microphone.
- **Local service unavailable:** use Retry local service on Home and inspect backend.log in the data folder.

Source, updates, and issues: https://github.com/MaxJafar/DisWhisper
