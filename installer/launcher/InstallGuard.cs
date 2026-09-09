using System.Diagnostics;

namespace AutoModules.Installer;

public static class InstallGuard
{
    public static bool ShouldBlock(string root, string executable, int checkerPid, int processPid) =>
        checkerPid != processPid && IsInstalledExecutable(root, executable);

    public static bool IsInstalledExecutable(string root, string executable)
    {
        var actual = Path.GetFullPath(executable).Replace('/', '\\');
        return new[] { "AutoModules.exe", "python/python.exe", "python/pythonw.exe", "host/VirtualGamepadHost.exe" }
            .Any(relative => string.Equals(Path.GetFullPath(Path.Combine(root, relative)).Replace('/', '\\'), actual, StringComparison.OrdinalIgnoreCase));
    }

    public static bool HasRunningProcesses(string root, Action<string> log)
    {
        var running = false;
        foreach (var process in Process.GetProcesses())
        {
            using (process)
            {
                try
                {
                    if (process.Id == Environment.ProcessId) continue;
                    if (process.MainModule?.FileName is { } executable && ShouldBlock(root, executable, Environment.ProcessId, process.Id))
                    {
                        log($"Installed process still running: {process.Id} {executable}");
                        running = true;
                    }
                }
                catch (System.ComponentModel.Win32Exception) { /* protected OS processes cannot be application runtimes */ }
                catch (InvalidOperationException) { /* process exited during enumeration */ }
            }
        }
        return running;
    }
}
