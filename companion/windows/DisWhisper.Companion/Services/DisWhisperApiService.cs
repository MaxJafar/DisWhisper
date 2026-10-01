using System;
using System.Collections.Generic;
using System.IO;
using System.Net.Http;
using System.Net.WebSockets;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using DisWhisper.Companion.Models;

namespace DisWhisper.Companion.Services;

public class DisWhisperApiService : IDisposable
{
    private readonly HttpClient _httpClient;
    private readonly string _baseUrl;
    private CancellationTokenSource? _wsCts;
    private Task? _listenerTask;
    private CancellationTokenSource? _statusCts;

    public string LastError { get; private set; } = "";

    public event Action<string, JsonElement>? OnEventReceived;
    public event Action<DisWhisperStatus>? StatusChanged;
    public DisWhisperStatus LatestStatus { get; private set; } = new();

    public DisWhisperApiService(string baseUrl = "http://127.0.0.1:8765")
    {
        _baseUrl = baseUrl.TrimEnd('/');
        _httpClient = new HttpClient { Timeout = TimeSpan.FromMinutes(3) };
    }

    public async Task<DisWhisperStatus?> GetStatusAsync()
    {
        try
        {
            using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(3));
            var res = await _httpClient.GetStringAsync($"{_baseUrl}/api/status", timeout.Token);
            return JsonSerializer.Deserialize<DisWhisperStatus>(res);
        }
        catch
        {
            return new DisWhisperStatus { Status = "offline" };
        }
    }

    public async Task<Dictionary<string, object>?> GetConfigAsync()
    {
        try
        {
            var res = await _httpClient.GetStringAsync($"{_baseUrl}/api/config");
            LastError = "";
            return JsonSerializer.Deserialize<Dictionary<string, object>>(res);
        }
        catch (Exception error)
        {
            LastError = error.Message;
            return null;
        }
    }

    public async Task<bool> UpdateConfigAsync(Dictionary<string, object> newConfig)
    {
        try
        {
            var json = JsonSerializer.Serialize(newConfig);
            using var content = new StringContent(json, Encoding.UTF8, "application/json");
            using var res = await _httpClient.PostAsync($"{_baseUrl}/api/config", content);
            return await CheckResponseAsync(res);
        }
        catch (Exception ex) { LastError = ex.Message; return false; }
    }

    public async Task<List<ModelInfo>> GetModelsAsync()
    {
        try
        {
            var res = await _httpClient.GetStringAsync($"{_baseUrl}/api/models");
            var parsed = JsonSerializer.Deserialize<ModelsResponse>(res);
            return parsed?.Models ?? new List<ModelInfo>();
        }
        catch (Exception ex)
        {
            LastError = ex.Message;
            return new List<ModelInfo>();
        }
    }

    public async Task<bool> DownloadModelAsync(string modelId)
    {
        try
        {
            var payload = JsonSerializer.Serialize(new { model_id = modelId });
            using var content = new StringContent(payload, Encoding.UTF8, "application/json");
            using var res = await _httpClient.PostAsync($"{_baseUrl}/api/models/download", content);
            return await CheckResponseAsync(res);
        }
        catch (Exception ex)
        {
            LastError = ex.Message;
            return false;
        }
    }

    public async Task<bool> SwitchEngineAsync(string engine)
    {
        try
        {
            var payload = JsonSerializer.Serialize(new { engine = engine });
            using var content = new StringContent(payload, Encoding.UTF8, "application/json");
            using var res = await _httpClient.PostAsync($"{_baseUrl}/api/engine/switch", content);
            return await CheckResponseAsync(res);
        }
        catch (Exception ex)
        {
            LastError = ex.Message;
            return false;
        }
    }

    public async Task<string> SummarizeTranscriptAsync(string transcriptText, string provider = "cloud", string? model = null, string? cloudPlatform = null)
    {
        try
        {
            var payload = JsonSerializer.Serialize(new
            {
                transcript_text = transcriptText,
                provider = provider,
                model = model,
                cloud_platform = cloudPlatform
            });
            using var content = new StringContent(payload, Encoding.UTF8, "application/json");
            using var res = await _httpClient.PostAsync($"{_baseUrl}/api/summarize", content);
            if (res.IsSuccessStatusCode)
            {
                var body = await res.Content.ReadAsStringAsync();
                using var doc = JsonDocument.Parse(body);
                return doc.RootElement.GetProperty("summary").GetString() ?? "";
            }
            await CheckResponseAsync(res);
            return $"Error: {LastError}";
        }
        catch (Exception ex)
        {
            return $"Error: {ex.Message}";
        }
    }

    public async Task<List<TranscriptItem>> GetTranscriptsAsync()
    {
        try
        {
            var res = await _httpClient.GetStringAsync($"{_baseUrl}/api/transcripts");
            LastError = "";
            using var doc = JsonDocument.Parse(res);
            if (doc.RootElement.TryGetProperty("transcripts", out var arr))
            {
                return JsonSerializer.Deserialize<List<TranscriptItem>>(arr.GetRawText()) ?? new List<TranscriptItem>();
            }
            return new List<TranscriptItem>();
        }
        catch (Exception error)
        {
            LastError = error.Message;
            return new List<TranscriptItem>();
        }
    }

    public void StartWebSocketListener()
    {
        _wsCts?.Cancel();
        _wsCts?.Dispose();
        _wsCts = new CancellationTokenSource();
        var token = _wsCts.Token;
        _listenerTask = Task.Run(() => ListenWebSocketLoop(token));
        _statusCts?.Cancel();
        _statusCts?.Dispose();
        _statusCts = new CancellationTokenSource();
        var statusToken = _statusCts.Token;
        _ = Task.Run(async () =>
        {
            while (!statusToken.IsCancellationRequested)
            {
                LatestStatus = await GetStatusAsync() ?? new();
                var handlers = StatusChanged?.GetInvocationList();
                if (handlers != null)
                    foreach (Action<DisWhisperStatus> handler in handlers)
                        try { handler(LatestStatus); }
                        catch (Exception error) { System.Diagnostics.Debug.WriteLine(error); }
                try { await Task.Delay(2000, statusToken); }
                catch (OperationCanceledException) { return; }
            }
        }, statusToken);
    }

    public Task<bool> StartBotAsync() => PostControlAsync("bot/start");
    public Task<bool> StopBotAsync() => PostControlAsync("bot/stop");
    public Task<bool> FinishMeetingAsync() => PostControlAsync("meeting/finish");
    public Task<bool> ShutdownBackendAsync() => PostControlAsync("system/shutdown");

    public async Task<bool> CancelDownloadAsync(string modelId)
    {
        try
        {
            using var content = new StringContent(JsonSerializer.Serialize(new { model_id = modelId }), Encoding.UTF8, "application/json");
            using var result = await _httpClient.PostAsync($"{_baseUrl}/api/models/cancel", content);
            return await CheckResponseAsync(result);
        }
        catch (Exception error) { LastError = error.Message; return false; }
    }

    private async Task<bool> PostControlAsync(string route)
    {
        try
        {
            using var content = new StringContent("{}", Encoding.UTF8, "application/json");
            using var result = await _httpClient.PostAsync($"{_baseUrl}/api/{route}", content);
            return await CheckResponseAsync(result);
        }
        catch (Exception error) { LastError = error.Message; return false; }
    }

    public async Task<DiscordConnectionInfo?> ValidateDiscordAsync(string token)
    {
        try
        {
            using var content = new StringContent(JsonSerializer.Serialize(new { token }), Encoding.UTF8, "application/json");
            using var result = await _httpClient.PostAsync($"{_baseUrl}/api/discord/validate", content);
            if (!await CheckResponseAsync(result)) return null;
            return JsonSerializer.Deserialize<DiscordConnectionInfo>(await result.Content.ReadAsStringAsync());
        }
        catch (Exception error) { LastError = error.Message; return null; }
    }

    public async Task<string?> ReadTranscriptAsync(string filename)
    {
        try
        {
            using var result = await _httpClient.GetAsync($"{_baseUrl}/api/transcripts/{Uri.EscapeDataString(filename)}");
            if (!await CheckResponseAsync(result)) return null;
            using var doc = JsonDocument.Parse(await result.Content.ReadAsStringAsync());
            return doc.RootElement.GetProperty("content").GetString();
        }
        catch (Exception error) { LastError = error.Message; return null; }
    }

    public async Task<string?> GetTranscriptDirectoryAsync()
    {
        try
        {
            var body = await _httpClient.GetStringAsync($"{_baseUrl}/api/transcripts");
            using var doc = JsonDocument.Parse(body);
            return doc.RootElement.TryGetProperty("directory", out var directory) ? directory.GetString() : null;
        }
        catch (Exception error) { LastError = error.Message; return null; }
    }

    public async Task<Dictionary<string, DownloadProgress>> GetDownloadProgressAsync()
    {
        try
        {
            using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(5));
            var body = await _httpClient.GetStringAsync($"{_baseUrl}/api/models/progress", timeout.Token);
            return JsonSerializer.Deserialize<Dictionary<string, DownloadProgress>>(body) ?? new();
        }
        catch { return new(); }
    }

    public async Task<bool> ActivateModelAsync(string modelId)
    {
        try
        {
            using var content = new StringContent(JsonSerializer.Serialize(new { model_id = modelId }), Encoding.UTF8, "application/json");
            using var response = await _httpClient.PostAsync($"{_baseUrl}/api/models/activate", content);
            return await CheckResponseAsync(response);
        }
        catch (Exception ex) { LastError = ex.Message; return false; }
    }

    private async Task<bool> CheckResponseAsync(HttpResponseMessage response)
    {
        if (response.IsSuccessStatusCode) { LastError = ""; return true; }
        LastError = $"HTTP {(int)response.StatusCode}";
        try
        {
            using var doc = JsonDocument.Parse(await response.Content.ReadAsStringAsync());
            if (doc.RootElement.TryGetProperty("error", out var error))
                LastError = error.GetString() ?? LastError;
            if (doc.RootElement.TryGetProperty("fields", out var fields))
                foreach (var field in fields.EnumerateArray())
                    LastError += $"\n{field.GetProperty("field").GetString()}: {field.GetProperty("message").GetString()}";
        }
        catch (JsonException) { }
        return false;
    }

    private async Task ListenWebSocketLoop(CancellationToken ct)
    {
        while (!ct.IsCancellationRequested)
        {
            try
            {
                using var socket = new ClientWebSocket();
                var uri = new UriBuilder(_baseUrl) { Path = "/api/events" };
                uri.Scheme = uri.Scheme == "https" ? "wss" : "ws";
                await socket.ConnectAsync(uri.Uri, ct);

                var buffer = new byte[8192];
                while (socket.State == WebSocketState.Open && !ct.IsCancellationRequested)
                {
                    using var messageBuffer = new MemoryStream();
                    WebSocketReceiveResult result;
                    do
                    {
                        result = await socket.ReceiveAsync(new ArraySegment<byte>(buffer), ct);
                        if (result.MessageType == WebSocketMessageType.Close) break;
                        messageBuffer.Write(buffer, 0, result.Count);
                        if (messageBuffer.Length > 1024 * 1024) throw new InvalidDataException("WebSocket message is too large");
                    } while (!result.EndOfMessage);
                    if (result.MessageType == WebSocketMessageType.Close) break;
                    if (result.MessageType != WebSocketMessageType.Text) continue;

                    var message = Encoding.UTF8.GetString(messageBuffer.ToArray());
                    using var doc = JsonDocument.Parse(message);
                    if (doc.RootElement.TryGetProperty("event", out var ev) &&
                        doc.RootElement.TryGetProperty("data", out var data))
                    {
                        var handlers = OnEventReceived?.GetInvocationList();
                        if (handlers != null)
                            foreach (Action<string, JsonElement> handler in handlers)
                                try { handler(ev.GetString() ?? "", data.Clone()); }
                                catch (Exception ex) { System.Diagnostics.Debug.WriteLine(ex); }
                    }
                }
            }
            catch (OperationCanceledException) when (ct.IsCancellationRequested) { return; }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine(ex);
            }
            try { await Task.Delay(3000, ct); }
            catch (OperationCanceledException) { return; }
        }
    }

    public void Dispose()
    {
        _wsCts?.Cancel();
        _wsCts?.Dispose();
        _statusCts?.Cancel();
        _statusCts?.Dispose();
        _httpClient.Dispose();
    }
}
