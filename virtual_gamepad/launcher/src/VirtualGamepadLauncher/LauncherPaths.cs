namespace VirtualGamepadLauncher;

public sealed class LauncherPaths
{
    public const string PipeName = "AutoModules.VirtualGamepad.v1";

    public LauncherPaths(string moduleRoot)
    {
        ModuleRoot = Path.GetFullPath(moduleRoot);
        WorkspaceRoot = Directory.GetParent(ModuleRoot)?.Parent?.FullName
            ?? throw new ArgumentException("The launcher module root must have an auto_modules parent.", nameof(moduleRoot));
    }

    public string ModuleRoot { get; }

    public string WorkspaceRoot { get; }

    public string AutoModulesRoot => Directory.GetParent(ModuleRoot)?.FullName
        ?? throw new InvalidOperationException("The launcher module root has no parent directory.");

    public string HostDll => Path.Combine(ModuleRoot, "host", "src", "VirtualGamepadHost", "bin", "Release", "net8.0-windows", "VirtualGamepadHost.dll");

    public string UiRoot => Path.Combine(ModuleRoot, "ui");

    public string ClientRoot => Path.Combine(ModuleRoot, "client", "python");

    public IEnumerable<string> DotnetCandidates()
    {
        yield return Path.Combine(WorkspaceRoot, "dotnet-sdk2", "dotnet.exe");

        var dotnetRoot = Environment.GetEnvironmentVariable("DOTNET_ROOT");
        if (!string.IsNullOrWhiteSpace(dotnetRoot))
        {
            yield return Path.Combine(dotnetRoot, "dotnet.exe");
        }

        yield return "dotnet";
    }

    public IEnumerable<string> PythonCandidates()
    {
        yield return Path.Combine(WorkspaceRoot, ".venv", "Scripts", "pythonw.exe");
        yield return Path.Combine(WorkspaceRoot, ".venv", "Scripts", "python.exe");
        yield return "pythonw.exe";
        yield return "python.exe";
    }

    public string FindDotnet()
        => FindExecutable(DotnetCandidates(), "the .NET runtime");

    public string FindPython()
        => FindExecutable(PythonCandidates(), "the Python UI runtime");

    private static string FindExecutable(IEnumerable<string> candidates, string displayName)
    {
        foreach (var candidate in candidates)
        {
            if (!candidate.Contains(Path.DirectorySeparatorChar) && !candidate.Contains(Path.AltDirectorySeparatorChar))
            {
                return candidate;
            }

            if (File.Exists(candidate))
            {
                return candidate;
            }
        }

        throw new FileNotFoundException($"Could not find {displayName}. Run this launcher from the virtual_gamepad module inside D:\\ACloud.");
    }
}
