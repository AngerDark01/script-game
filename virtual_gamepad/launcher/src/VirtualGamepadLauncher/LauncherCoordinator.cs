using System.Diagnostics;
using System.IO.Pipes;

namespace VirtualGamepadLauncher;

public sealed class LauncherCoordinator
{
    private readonly LauncherPaths _paths;

    public LauncherCoordinator(LauncherPaths paths)
    {
        _paths = paths;
    }

    public void Start()
    {
        EnsureHostReady();
        StartUi();
    }

    public void EnsureHostReady()
    {
        if (CanConnectToHost())
        {
            return;
        }

        if (!File.Exists(_paths.HostDll))
        {
            throw new FileNotFoundException(
                "The virtual gamepad host has not been built yet. Rebuild the module, then start it again.",
                _paths.HostDll);
        }

        var host = Process.Start(CreateHostStartInfo())
            ?? throw new InvalidOperationException("Windows could not start the virtual gamepad host process.");

        var deadline = DateTime.UtcNow + TimeSpan.FromSeconds(5);
        while (DateTime.UtcNow < deadline)
        {
            if (CanConnectToHost())
            {
                return;
            }

            if (host.HasExited)
            {
                throw new InvalidOperationException($"The virtual gamepad host closed before it created its pipe (exit code {host.ExitCode}).");
            }

            Thread.Sleep(75);
        }

        throw new TimeoutException("The virtual gamepad host did not become ready within 5 seconds. Confirm that ViGEmBus is installed, then try again.");
    }

    public ProcessStartInfo CreateHostStartInfo()
    {
        var info = new ProcessStartInfo
        {
            FileName = _paths.FindDotnet(),
            WorkingDirectory = Path.GetDirectoryName(_paths.HostDll) ?? _paths.ModuleRoot,
            UseShellExecute = false,
            CreateNoWindow = true,
        };
        info.ArgumentList.Add("exec");
        info.ArgumentList.Add(_paths.HostDll);
        return info;
    }

    public void StartUi()
    {
        var info = new ProcessStartInfo
        {
            FileName = _paths.FindPython(),
            WorkingDirectory = _paths.UiRoot,
            UseShellExecute = false,
            CreateNoWindow = true,
        };
        info.ArgumentList.Add("-m");
        info.ArgumentList.Add("virtual_gamepad_ui.main");
        info.Environment["PYTHONPATH"] = CreateUiEnvironment(_paths, Environment.GetEnvironmentVariable("PYTHONPATH"));

        var ui = Process.Start(info)
            ?? throw new InvalidOperationException("Windows could not start the Virtual Gamepad UI.");
        Thread.Sleep(500);
        if (ui.HasExited)
        {
            throw new InvalidOperationException($"The Virtual Gamepad UI closed immediately (exit code {ui.ExitCode}). Check that the module Python environment is installed.");
        }
    }

    public static string CreateUiEnvironment(LauncherPaths paths, string? existingPythonPath)
    {
        var roots = new List<string> { paths.UiRoot, paths.ClientRoot, paths.AutoModulesRoot };
        if (!string.IsNullOrWhiteSpace(existingPythonPath))
        {
            roots.Add(existingPythonPath);
        }

        return string.Join(Path.PathSeparator, roots);
    }

    private static bool CanConnectToHost()
    {
        try
        {
            using var pipe = new NamedPipeClientStream(".", LauncherPaths.PipeName, PipeDirection.InOut, PipeOptions.None);
            pipe.Connect(120);
            return true;
        }
        catch (IOException ex)
        {
            return IsPipeBusyHResult(ex.HResult);
        }
        catch (UnauthorizedAccessException)
        {
            return false;
        }
        catch (TimeoutException)
        {
            return false;
        }
    }

    public static bool IsPipeBusyHResult(int hResult)
        => unchecked((uint)hResult) == 0x800700E7;
}
