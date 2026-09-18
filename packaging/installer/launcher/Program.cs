using System.Diagnostics;
using System.Text;

namespace AutoModules.Installer;
internal static class Program
{
    [STAThread]
    private static int Main(string[] args)
    {
        var headless = args.Length > 0;
        var root = AppContext.BaseDirectory;
        var data = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "AutoModules", "Workbench");
        var logDirectory = Path.Combine(data, "logs");
        try
        {
            data = RuntimeLayout.DefaultDataDirectory;
            logDirectory = Path.Combine(data, "logs");
            Directory.CreateDirectory(logDirectory);
            void Log(string text) => File.AppendAllText(Path.Combine(logDirectory, "launcher.log"), $"{DateTimeOffset.Now:O} {text}{Environment.NewLine}", Encoding.UTF8);
            Log("Launcher mode: " + (headless ? string.Join(' ', args) : "workbench") + "; root=" + root);
            if (args.Length == 2 && args[0] == "--check-running") return InstallGuard.HasRunningProcesses(args[1], Log) ? 30 : 0;
            if (args.Length == 1 && args[0] == "--check-driver") return DriverInstaller.Check(Log);
            if (args.Length == 1 && args[0] == "--verify-controller") return DriverInstaller.Check(Log, createController: true);
            if (args.Length == 1 && args[0] == "--ensure-driver") return DriverInstaller.Ensure(root, logDirectory, Log);
            if (args.Length == 1 && args[0] == "--verify-prerequisite") { DriverInstaller.VerifyPrerequisite(Path.Combine(root, "prerequisites", DriverInstaller.FileName)); return 0; }
            if (headless && !(args.Length == 1 && args[0] == "--self-test")) { Log("Unknown arguments."); return 2; }
            RuntimeLayout.ValidatePayload(root);
            RuntimeLayout.SeedDefaults(Path.Combine(root, "defaults"), data);
            if (headless) { Log("Self-test passed; no driver, network or UI was activated."); return 0; }
            using var child = Process.Start(RuntimeLayout.CreateStartInfo(root, data)) ?? throw new IOException("无法启动工作台。");
            if (child.WaitForExit(2500) && child.ExitCode != 0)
                throw new IOException($"工作台提前退出（代码 {child.ExitCode}）。请检查 {Path.Combine(logDirectory, "runtime.log")}");
            Log("Workbench process started: " + child.Id);
            return 0;
        }
        catch (Exception ex)
        {
            try { Directory.CreateDirectory(logDirectory); File.AppendAllText(Path.Combine(logDirectory, "launcher.log"), ex + Environment.NewLine, Encoding.UTF8); } catch { }
            if (!headless) MessageBox.Show("工作台启动失败：\n" + ex.Message + "\n\n日志目录：" + logDirectory, "AutoModules 工作台", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
    }
}
