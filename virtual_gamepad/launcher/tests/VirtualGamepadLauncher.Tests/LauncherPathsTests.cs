namespace VirtualGamepadLauncher.Tests;

public sealed class LauncherPathsTests
{
    [Fact]
    public void FindsWorkspaceRuntimeBeforePathFallback()
    {
        var paths = new LauncherPaths(@"D:\ACloud\auto_modules\virtual_gamepad");

        Assert.Equal(@"D:\ACloud\dotnet-sdk2\dotnet.exe", paths.DotnetCandidates().First());
    }

    [Fact]
    public void FindsVirtualEnvironmentPythonFromModuleWorkspace()
    {
        var paths = new LauncherPaths(@"D:\ACloud\auto_modules\virtual_gamepad");

        Assert.Equal(@"D:\ACloud\.venv\Scripts\pythonw.exe", paths.PythonCandidates().First());
    }

    [Fact]
    public void UiEnvironmentIncludesAllModuleImportRoots()
    {
        var paths = new LauncherPaths(@"D:\ACloud\auto_modules\virtual_gamepad");
        var environment = LauncherCoordinator.CreateUiEnvironment(paths, "existing");

        Assert.Equal(
            string.Join(Path.PathSeparator, paths.UiRoot, paths.ClientRoot, paths.AutoModulesRoot, "existing"),
            environment);
    }

    [Fact]
    public void TreatsWindowsPipeBusyErrorAsAnExistingHost()
    {
        Assert.True(LauncherCoordinator.IsPipeBusyHResult(unchecked((int)0x800700E7)));
        Assert.False(LauncherCoordinator.IsPipeBusyHResult(unchecked((int)0x80070002)));
    }
}
