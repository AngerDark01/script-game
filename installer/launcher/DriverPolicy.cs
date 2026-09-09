namespace AutoModules.Installer;

public static class DriverPolicy
{
    public const int Ready = 0;
    public const int Missing = 10;
    public const int VerificationFailed = 11;
    public const int InstallationFailed = 20;
    public const int ProbeFailed = 21;
    public const int RestartRequired = 3010;

    public static int ClassifyResult(int nativeCode, bool usable) => nativeCode switch
    {
        3010 or 1641 => RestartRequired,
        0 => usable ? Ready : ProbeFailed,
        _ => InstallationFailed
    };
}
