namespace VirtualGamepadLauncher;

internal static class Program
{
    [STAThread]
    private static void Main()
    {
        ApplicationConfiguration.Initialize();
        try
        {
            var moduleRoot = Path.GetDirectoryName(Environment.ProcessPath ?? AppContext.BaseDirectory)
                ?? throw new InvalidOperationException("Could not determine the launcher folder.");
            new LauncherCoordinator(new LauncherPaths(moduleRoot)).Start();
        }
        catch (Exception ex)
        {
            MessageBox.Show(
                ex.Message,
                "Virtual Gamepad startup failed",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error);
        }
    }
}
