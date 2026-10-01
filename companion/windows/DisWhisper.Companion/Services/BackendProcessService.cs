using System.Diagnostics;
using System.Text;

namespace DisWhisper.Companion.Services;

public sealed class BackendProcessService : IAsyncDisposable
{
    private Process? _process;
    private readonly string _sessionId = Guid.NewGuid().ToString("N");
    private readonly DisWhisperApiService _api;
    private readonly bool _preview;
    public string DataDirectory { get; }
    public string LastError { get; private set; } = "";
    public bool OwnsBackend => _process != null && !_process.HasExited;

    public BackendProcessService(DisWhisperApiService api, bool preview)
    {
        _api = api;
        _preview = preview;
        DataDirectory = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "DisWhisper", preview ? "Preview" : "Data");
    }

    public async Task<bool> EnsureRunningAsync()
    {
        var status = await _api.GetStatusAsync();
        if (status is { Status: not "offline" }) return true;
        if (OwnsBackend) return false;
        try
        {
            Directory.CreateDirectory(DataDirectory);
            var configPath = Path.Combine(DataDirectory, "config.json");
            if (_preview && !File.Exists(configPath))
                await File.WriteAllTextAsync(configPath, "{\"API_SERVER_PORT\":8767}");
            var start = new ProcessStartInfo
            {
                FileName = Path.Combine(AppContext.BaseDirectory, "backend", "diswhisper-backend.exe"),
                WorkingDirectory = DataDirectory,
                UseShellExecute = false,
                CreateNoWindow = true,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                StandardOutputEncoding = Encoding.UTF8,
                StandardErrorEncoding = Encoding.UTF8,
            };
            if (!File.Exists(start.FileName))
            {
                var root = FindSourceRoot();
                if (root == null) throw new FileNotFoundException("The backend is missing. Download the complete Windows release, or run the development setup script.");
                start.FileName = Path.Combine(root, ".venv", "Scripts", "python.exe");
                if (!File.Exists(start.FileName)) throw new FileNotFoundException("Install the Python dependencies with the development setup script first.");
                start.WorkingDirectory = root;
                start.ArgumentList.Add("-X"); start.ArgumentList.Add("utf8");
                start.ArgumentList.Add("-u"); start.ArgumentList.Add("-m"); start.ArgumentList.Add("diswhisper.main");
            }
            start.ArgumentList.Add("--companion");
            start.ArgumentList.Add("--data-dir"); start.ArgumentList.Add(DataDirectory);
            start.ArgumentList.Add("--config"); start.ArgumentList.Add(configPath);
            start.ArgumentList.Add("--session-id"); start.ArgumentList.Add(_sessionId);
            start.Environment["PYTHONUTF8"] = "1";
            start.Environment["HF_HOME"] = Path.Combine(DataDirectory, "cache", "huggingface");
            start.Environment["HF_HUB_DISABLE_TELEMETRY"] = "1";
            start.Environment["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1";
            start.Environment["HF_HUB_DISABLE_XET"] = "1";
            _process?.Dispose();
            _process = new Process { StartInfo = start, EnableRaisingEvents = true };
            _process.OutputDataReceived += (_, e) => Log(e.Data);
            _process.ErrorDataReceived += (_, e) => Log(e.Data);
            _process.Start();
            _process.BeginOutputReadLine(); _process.BeginErrorReadLine();
            for (var attempt = 0; attempt < 35 && !_process.HasExited; attempt++)
            {
                await Task.Delay(500);
                status = await _api.GetStatusAsync();
                if (status is { Status: not "offline" })
                {
                    if (status?.SessionId != _sessionId) throw new InvalidOperationException("Another service is using the DisWhisper port. Close it before opening this copy.");
                    LastError = "";
                    return true;
                }
            }
            throw new InvalidOperationException("The local service did not start. Open the data folder and check backend.log.");
        }
        catch (Exception error) { LastError = error.Message; return false; }
    }

    private static string? FindSourceRoot()
    {
        DirectoryInfo? directory = new(AppContext.BaseDirectory);
        for (var attempt = 0; attempt < 12 && directory != null; attempt++, directory = directory.Parent)
            if (File.Exists(Path.Combine(directory.FullName, "diswhisper", "main.py")) && File.Exists(Path.Combine(directory.FullName, "pyproject.toml")))
                return directory.FullName;
        return null;
    }

    private void Log(string? line)
    {
        if (string.IsNullOrWhiteSpace(line)) return;
        try { lock (this) File.AppendAllText(Path.Combine(DataDirectory, "backend.log"), line + Environment.NewLine); }
        catch (Exception error) when (error is IOException or UnauthorizedAccessException) { }
    }

    public async ValueTask DisposeAsync()
    {
        if (_process == null) return;
        try
        {
            var status = await _api.GetStatusAsync();
            if (!_process.HasExited && status?.SessionId == _sessionId)
            {
                await _api.ShutdownBackendAsync();
                using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(20));
                try { await _process.WaitForExitAsync(timeout.Token); }
                catch (OperationCanceledException) { LastError = "The backend is still finishing its meeting."; }
            }
        }
        finally { _process.Dispose(); _process = null; }
    }
}
