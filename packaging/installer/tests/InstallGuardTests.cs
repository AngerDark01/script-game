using AutoModules.Installer;

namespace Installer.Tests;
public sealed class InstallGuardTests
{
    [Fact]
    public void CheckerDoesNotBlockItselfButOtherInstalledProcessesDo()
    {
        const string root = "C:/Program Files/AutoModules";
        const string executable = root + "/AutoModules.exe";
        Assert.False(InstallGuard.ShouldBlock(root, executable, checkerPid: 10, processPid: 10));
        Assert.True(InstallGuard.ShouldBlock(root, executable, checkerPid: 10, processPid: 11));
        Assert.False(InstallGuard.ShouldBlock(root, "C:/Other/AutoModules.exe", checkerPid: 10, processPid: 11));
    }

    [Theory]
    [InlineData("C:/Program Files/AutoModules/python/pythonw.exe", true)]
    [InlineData("c:/program files/automodules/host/VirtualGamepadHost.exe", true)]
    [InlineData("C:/Program Files/AutoModules/AutoModules.exe", true)]
    [InlineData("C:/Program Files/AutoModules-other/python/pythonw.exe", false)]
    [InlineData("D:/ACloud/.venv/Scripts/pythonw.exe", false)]
    public void UpgradeGuardOnlyMatchesThisInstalledRuntime(string executable, bool expected)
    {
        Assert.Equal(expected, InstallGuard.IsInstalledExecutable("C:/Program Files/AutoModules", executable));
    }
}
