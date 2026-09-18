using System.ComponentModel;
using System.Diagnostics;
using System.Security.Principal;

namespace VirtualGamepadHost.Runtime;

/// <summary>
/// Starts the input-capturing host at the same integrity level as elevated games.
/// The app manifest handles normal .exe launches; this also covers development
/// launches through <c>dotnet exec VirtualGamepadHost.dll</c>.
/// </summary>
public static class Elevation
{
    public static bool RequiresElevation(bool isWindows, bool isAdministrator) =>
        isWindows && !isAdministrator;

    public static string AppHostPathForAssembly(string assemblyPath) =>
        Path.ChangeExtension(assemblyPath, ".exe");

    public static IReadOnlyList<string> RelaunchArgumentsForProcess(
        string processPath,
        string assemblyPath,
        IReadOnlyList<string> args)
    {
        var processName = Path.GetFileNameWithoutExtension(processPath);
        if (processName.Equals("dotnet", StringComparison.OrdinalIgnoreCase))
        {
            return new[] { "exec", assemblyPath }.Concat(args).ToArray();
        }

        return args.ToArray();
    }

    public static bool IsAdministrator()
    {
        if (!OperatingSystem.IsWindows())
        {
            return true;
        }

        using var identity = WindowsIdentity.GetCurrent();
        return new WindowsPrincipal(identity).IsInRole(WindowsBuiltInRole.Administrator);
    }

    /// <summary>
    /// Requests a single UAC elevation and returns false in the original
    /// process. The caller must exit immediately when false is returned.
    /// </summary>
    public static bool EnsureAdministrator(string[] args, Action<string>? reportError = null)
    {
        if (!RequiresElevation(OperatingSystem.IsWindows(), IsAdministrator()))
        {
            return true;
        }

        var assemblyPath = typeof(Elevation).Assembly.Location;
        var currentProcess = Environment.ProcessPath ?? string.Empty;
        var processName = Path.GetFileNameWithoutExtension(currentProcess);
        var launchFile = processName.Equals("dotnet", StringComparison.OrdinalIgnoreCase)
            ? currentProcess
            : AppHostPathForAssembly(assemblyPath);
        if (!File.Exists(launchFile))
        {
            reportError?.Invoke($"Administrator permission is required, but the host executable was not found: {launchFile}");
            return false;
        }

        try
        {
            var startInfo = new ProcessStartInfo
            {
                FileName = launchFile,
                WorkingDirectory = Path.GetDirectoryName(launchFile) ?? AppContext.BaseDirectory,
                UseShellExecute = true,
                Verb = "runas",
            };
            foreach (var argument in RelaunchArgumentsForProcess(currentProcess, assemblyPath, args))
            {
                startInfo.ArgumentList.Add(argument);
            }

            Process.Start(startInfo);
            return false;
        }
        catch (Win32Exception ex) when (ex.NativeErrorCode == 1223)
        {
            reportError?.Invoke("Administrator permission was cancelled. The virtual gamepad host was not started.");
            return false;
        }
        catch (Exception ex)
        {
            reportError?.Invoke($"Could not start the virtual gamepad host as Administrator: {ex.Message}");
            return false;
        }
    }
}
