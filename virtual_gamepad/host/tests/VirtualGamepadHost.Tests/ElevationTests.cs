using VirtualGamepadHost.Runtime;

namespace VirtualGamepadHost.Tests;

public sealed class ElevationTests
{
    [Theory]
    [InlineData(true, false, true)]
    [InlineData(true, true, false)]
    [InlineData(false, false, false)]
    public void ElevationIsRequiredOnlyForANonAdminWindowsProcess(bool isWindows, bool isAdministrator, bool expected)
    {
        Assert.Equal(expected, Elevation.RequiresElevation(isWindows, isAdministrator));
    }

    [Fact]
    public void DotnetExecCanRelaunchTheSiblingAppHost()
    {
        var assemblyPath = @"D:\work\VirtualGamepadHost.dll";

        Assert.Equal(@"D:\work\VirtualGamepadHost.exe", Elevation.AppHostPathForAssembly(assemblyPath));
    }

    [Fact]
    public void DotnetExecRelaunchKeepsTheLocalRuntime()
    {
        var assemblyPath = @"D:\work\VirtualGamepadHost.dll";

        Assert.Equal(
            new[] { "exec", assemblyPath, "--diagnostic" },
            Elevation.RelaunchArgumentsForProcess(@"D:\ACloud\dotnet-sdk2\dotnet.exe", assemblyPath, new[] { "--diagnostic" }));
    }
}
