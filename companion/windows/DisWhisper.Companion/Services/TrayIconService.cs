using System;
using System.ComponentModel;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using Microsoft.UI.Dispatching;

namespace DisWhisper.Companion.Services;

/// <summary>Owns the native notification-area icon and its window message callbacks.</summary>
public sealed class TrayIconService : IDisposable
{
    private const uint CallbackMessage = 0x8000 + 37;
    private const uint SubclassId = 37;
    private const uint NotifyAdd = 0;
    private const uint NotifyDelete = 2;
    private const uint NotifySetFocus = 3;
    private const uint NotifySetVersion = 4;
    private readonly nint _windowHandle;
    private readonly DispatcherQueue _dispatcher;
    private readonly Action _showWindow;
    private readonly Action _hideWindow;
    private readonly Action _exit;
    private readonly SubclassProcedure _procedure;
    private readonly uint _taskbarCreated;
    private NotifyIconData _iconData;
    private bool _disposed;

    public bool IsVisible { get; private set; }

    public TrayIconService(nint windowHandle, DispatcherQueue dispatcher, string iconPath,
        Action showWindow, Action hideWindow, Action exit)
    {
        _windowHandle = windowHandle;
        _dispatcher = dispatcher;
        _showWindow = showWindow;
        _hideWindow = hideWindow;
        _exit = exit;
        _procedure = WindowProcedure;
        _taskbarCreated = RegisterWindowMessage("TaskbarCreated");
        var iconHandle = LoadImage(0, iconPath, 1, GetSystemMetrics(49), GetSystemMetrics(50), 0x10);
        if (iconHandle == 0) throw new Win32Exception(Marshal.GetLastWin32Error(), "Unable to load the DisWhisper tray icon.");

        _iconData = new NotifyIconData
        {
            Size = (uint)Marshal.SizeOf<NotifyIconData>(),
            Window = windowHandle,
            Id = 1,
            Flags = 0x1 | 0x2 | 0x4 | 0x20 | 0x80,
            CallbackMessage = CallbackMessage,
            Icon = iconHandle,
            Tip = "DisWhisper Companion — click to open",
            Info = "",
            InfoTitle = "",
            Guid = new Guid("63d0a5ae-9b3c-4490-93e7-41fc5f254f0e"),
            Version = 4,
        };
        if (!SetWindowSubclass(windowHandle, _procedure, SubclassId, 0))
        {
            DestroyIcon(iconHandle);
            throw new Win32Exception(Marshal.GetLastWin32Error(), "Unable to register the tray callback.");
        }
        AddIcon();
    }

    private void AddIcon()
    {
        if (_disposed) return;
        IsVisible = ShellNotifyIcon(NotifyAdd, ref _iconData);
        if (!IsVisible)
        {
            // Recover an icon left behind by an abnormally terminated instance.
            ShellNotifyIcon(NotifyDelete, ref _iconData);
            IsVisible = ShellNotifyIcon(NotifyAdd, ref _iconData);
        }
        if (IsVisible) ShellNotifyIcon(NotifySetVersion, ref _iconData);
        WriteDiagnostic(IsVisible ? "Tray icon registered." : "Tray icon registration failed; window close will exit normally.");
    }

    private nint WindowProcedure(nint window, uint message, nuint wParam, nint lParam, nuint subclassId, nuint referenceData)
    {
        try
        {
            if (!_disposed && message == _taskbarCreated)
            {
                // Explorer recreates its notification area after a restart.
                IsVisible = false;
                AddIcon();
            }
            else if (!_disposed && message == CallbackMessage)
            {
                var notification = (uint)(lParam.ToInt64() & 0xffff);
                switch (notification)
                {
                    case 0x400: // NIN_SELECT
                    case 0x401: // NIN_KEYSELECT
                    case 0x203: // WM_LBUTTONDBLCLK (legacy fallback)
                        _dispatcher.TryEnqueue(() => _showWindow());
                        break;
                    case 0x7b: // WM_CONTEXTMENU
                    case 0x205: // WM_RBUTTONUP (legacy fallback)
                        ShowContextMenu();
                        break;
                }
                return 0;
            }
        }
        catch (Exception error)
        {
            // Never unwind a managed exception into the native window procedure.
            WriteDiagnostic($"Tray operation failed: {error.Message}");
        }
        return DefSubclassProc(window, message, wParam, lParam);
    }

    private void ShowContextMenu()
    {
        var menu = CreatePopupMenu();
        if (menu == 0) return;
        try
        {
            AppendMenu(menu, 0, 1, "Open DisWhisper");
            AppendMenu(menu, 0, 2, "Hide window");
            AppendMenu(menu, 0x800, 0, null);
            AppendMenu(menu, 0, 3, "Quit companion");
            SetMenuDefaultItem(menu, 1, false);
            if (!GetCursorPos(out var point)) return;
            SetForegroundWindow(_windowHandle);
            var selected = TrackPopupMenu(menu, 0x100 | 0x80 | 0x2, point.X, point.Y, 0, _windowHandle, 0);
            PostMessage(_windowHandle, 0, 0, 0);
            switch (selected)
            {
                case 1: _dispatcher.TryEnqueue(() => _showWindow()); break;
                case 2: _dispatcher.TryEnqueue(() => _hideWindow()); break;
                case 3: _dispatcher.TryEnqueue(() => _exit()); break;
                default: ShellNotifyIcon(NotifySetFocus, ref _iconData); break;
            }
        }
        finally { DestroyMenu(menu); }
    }

    public void Dispose()
    {
        if (_disposed) return;
        _disposed = true;
        ShellNotifyIcon(NotifyDelete, ref _iconData);
        IsVisible = false;
        RemoveWindowSubclass(_windowHandle, _procedure, SubclassId);
        if (_iconData.Icon != 0) DestroyIcon(_iconData.Icon);
        _iconData.Icon = 0;
        WriteDiagnostic("Tray icon removed.");
        GC.SuppressFinalize(this);
    }

    internal static void WriteDiagnostic(string message)
    {
        try
        {
            var directory = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "DisWhisper");
            Directory.CreateDirectory(directory);
            File.AppendAllText(Path.Combine(directory, "companion.log"), $"[{DateTimeOffset.Now:O}] {message}{Environment.NewLine}");
        }
        catch { Debug.WriteLine(message); }
    }

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    private struct NotifyIconData
    {
        public uint Size;
        public nint Window;
        public uint Id;
        public uint Flags;
        public uint CallbackMessage;
        public nint Icon;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 128)] public string Tip;
        public uint State;
        public uint StateMask;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 256)] public string Info;
        public uint Version;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 64)] public string InfoTitle;
        public uint InfoFlags;
        public Guid Guid;
        public nint BalloonIcon;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct Point { public int X; public int Y; }

    [UnmanagedFunctionPointer(CallingConvention.Winapi)]
    private delegate nint SubclassProcedure(nint window, uint message, nuint wParam, nint lParam, nuint subclassId, nuint referenceData);

    [DllImport("shell32.dll", EntryPoint = "Shell_NotifyIconW", CharSet = CharSet.Unicode)]
    [return: MarshalAs(UnmanagedType.Bool)] private static extern bool ShellNotifyIcon(uint message, ref NotifyIconData data);
    [DllImport("comctl32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)] private static extern bool SetWindowSubclass(nint window, SubclassProcedure procedure, nuint id, nuint data);
    [DllImport("comctl32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)] private static extern bool RemoveWindowSubclass(nint window, SubclassProcedure procedure, nuint id);
    [DllImport("comctl32.dll")] private static extern nint DefSubclassProc(nint window, uint message, nuint wParam, nint lParam);
    [DllImport("user32.dll", EntryPoint = "LoadImageW", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern nint LoadImage(nint instance, string name, uint type, int width, int height, uint flags);
    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)] private static extern bool DestroyIcon(nint icon);
    [DllImport("user32.dll")] private static extern int GetSystemMetrics(int index);
    [DllImport("user32.dll", EntryPoint = "RegisterWindowMessageW", CharSet = CharSet.Unicode)]
    private static extern uint RegisterWindowMessage(string message);
    [DllImport("user32.dll")] private static extern nint CreatePopupMenu();
    [DllImport("user32.dll", EntryPoint = "AppendMenuW", CharSet = CharSet.Unicode)]
    [return: MarshalAs(UnmanagedType.Bool)] private static extern bool AppendMenu(nint menu, uint flags, nuint id, string? text);
    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)] private static extern bool DestroyMenu(nint menu);
    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)] private static extern bool GetCursorPos(out Point point);
    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)] private static extern bool SetForegroundWindow(nint window);
    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)] private static extern bool SetMenuDefaultItem(nint menu, uint item, [MarshalAs(UnmanagedType.Bool)] bool byPosition);
    [DllImport("user32.dll")]
    private static extern uint TrackPopupMenu(nint menu, uint flags, int x, int y, int reserved, nint owner, nint rectangle);
    [DllImport("user32.dll", EntryPoint = "PostMessageW")]
    [return: MarshalAs(UnmanagedType.Bool)] private static extern bool PostMessage(nint window, uint message, nuint wParam, nint lParam);
}
