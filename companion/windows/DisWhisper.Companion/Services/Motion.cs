using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Hosting;
using System.Numerics;
using System.Runtime.CompilerServices;
using Windows.UI.ViewManagement;

namespace DisWhisper.Companion.Services;

public static class Motion
{
    private static readonly ConditionalWeakTable<FrameworkElement, object> Attached = new();
    private static readonly UISettings WindowsSettings = new();
    public static bool Enabled => App.Preferences.MotionEnabled && WindowsSettings.AnimationsEnabled;

    public static void EnablePressFeedback(FrameworkElement element)
    {
        if (Attached.TryGetValue(element, out _)) return;
        Attached.Add(element, new object());
        element.PointerPressed += (_, _) => Scale(element, 0.98f, 80);
        element.PointerReleased += (_, _) => Scale(element, 1f, 140);
        element.PointerCanceled += (_, _) => Scale(element, 1f, 140);
        element.PointerExited += (_, _) => Scale(element, 1f, 140);
    }

    private static void Scale(FrameworkElement element, float value, int milliseconds)
    {
        var visual = ElementCompositionPreview.GetElementVisual(element);
        if (!Enabled) { visual.StopAnimation("Scale"); visual.Scale = Vector3.One; return; }
        visual.CenterPoint = new Vector3((float)element.ActualWidth / 2, (float)element.ActualHeight / 2, 0);
        var animation = visual.Compositor.CreateVector3KeyFrameAnimation();
        animation.InsertKeyFrame(1, new Vector3(value, value, 1));
        animation.Duration = TimeSpan.FromMilliseconds(milliseconds);
        visual.StartAnimation("Scale", animation);
    }
}
