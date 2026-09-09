using AutoModules.Installer;

namespace Installer.Tests;
public sealed class DriverPolicyTests
{
    [Fact]
    public void RejectsUntrustedPrerequisiteBeforeAnyExecution()
    {
        var path = Path.GetTempFileName();
        try
        {
            File.WriteAllText(path, "not the signed official installer");
            Assert.Throws<System.Security.Cryptography.CryptographicException>(() => DriverInstaller.VerifyPrerequisite(path));
        }
        finally { File.Delete(path); }
    }

    [Fact]
    public void VerifiesOfficialSignatureWithoutInstallingWhenFixtureProvided()
    {
        var path = Environment.GetEnvironmentVariable("AUTOMODULES_DRIVER_TEST_PATH");
        if (!string.IsNullOrEmpty(path)) DriverInstaller.VerifyPrerequisite(path);
    }

    [Theory]
    [InlineData(0, true, 0)]
    [InlineData(0, false, 21)]
    [InlineData(3010, false, 3010)]
    [InlineData(1641, false, 3010)]
    [InlineData(1603, true, 20)]
    public void InstallResultDoesNotClaimSuccessOnFailureOrRequiredReboot(int nativeCode, bool usable, int expected)
    {
        Assert.Equal(expected, DriverPolicy.ClassifyResult(nativeCode, usable));
    }
}
