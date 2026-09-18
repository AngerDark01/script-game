namespace VirtualGamepadLauncher;

public sealed class LauncherPaths
{
    public const string PipeName = "AutoModules.VirtualGamepad.v1";

    public LauncherPaths(string moduleRoot)
    {
        ModuleRoot = Path.GetFullPath(moduleRoot);
        AutoModulesRoot = Directory.GetParent(ModuleRoot)?.Parent?.FullName
            ?? throw new ArgumentException("The launcher module root must be under services/virtual_gamepad.", nameof(moduleRoot));
        WorkspaceRoot = Directory.GetParent(AutoModulesRoot)?.FullName
            ?? throw new ArgumentException("The Auto Modules repository must have a workspace parent.", nameof(moduleRoot));
    }

    public string ModuleRoot { get; }

    public string WorkspaceRoot { get; }

    public string AutoModulesRoot { get; }

    public string SourceRoot => Path.Combine(AutoModulesRoot, "src");

    public string HostDll => Path.Combine(ModuleRoot, "host", "src", "VirtualGamepadHost", "bin", "Release", "net8.0-windows", "VirtualGamepadHost.dll");

    public string UiRoot => Path.Combine(SourceRoot, "auto_modules", "ui", "virtual_gamepad");

    public string ClientRoot => Path.Combine(SourceRoot, "auto_modules", "adapters", "virtual_gamepad");

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

        throw new FileNotFoundException($"Could not find {displayName}. Run this launcher from the Auto Modules service directory.");
    }
}
