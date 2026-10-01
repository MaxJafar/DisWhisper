using System.Text.Json;
using Microsoft.UI.Xaml;

namespace DisWhisper.Companion.Services;

public sealed class UiPreferences
{
    public string Theme { get; set; } = "system";
    public bool MotionEnabled { get; set; } = true;
    private static string FilePath => Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "DisWhisper", "appearance.json");

    public static UiPreferences Load()
    {
        try { return JsonSerializer.Deserialize<UiPreferences>(File.ReadAllText(FilePath)) ?? new(); }
        catch { return new(); }
    }

    public void Save()
    {
        Directory.CreateDirectory(Path.GetDirectoryName(FilePath)!);
        File.WriteAllText(FilePath, JsonSerializer.Serialize(this));
    }

    public void Apply(FrameworkElement root) => root.RequestedTheme = Theme switch
    {
        "light" => ElementTheme.Light,
        "dark" => ElementTheme.Dark,
        _ => ElementTheme.Default,
    };
}
