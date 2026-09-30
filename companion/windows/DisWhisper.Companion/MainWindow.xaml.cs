using System;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Controls;
using DisWhisper.Companion.Views;

namespace DisWhisper.Companion;

public partial class MainWindow : Window
{
    public MainWindow()
    {
        this.InitializeComponent();

        // Navigate to default page
        NavView.SelectedItem = NavView.MenuItems[0];
        ContentFrame.Navigate(typeof(DashboardPage));
    }

    private void NavView_SelectionChanged(NavigationView sender, NavigationViewSelectionChangedEventArgs args)
    {
        if (args.SelectedItem is NavigationViewItem item)
        {
            var tag = item.Tag?.ToString();
            Type pageType = tag switch
            {
                "dashboard" => typeof(DashboardPage),
                "models" => typeof(ModelsPage),
                "cloud" => typeof(CloudProvidersPage),
                "summaries" => typeof(SummariesPage),
                "settings" => typeof(SettingsPage),
                _ => typeof(DashboardPage)
            };

            if (ContentFrame.CurrentSourcePageType != pageType)
            {
                ContentFrame.Navigate(pageType);
            }
        }
    }
}
