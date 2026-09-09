using System.Diagnostics;

namespace AutoModules.Installer;

public static class RuntimeLayout
{
    public static string DefaultDataDirectory => Path.GetFullPath(
        Environment.GetEnvironmentVariable("AUTO_MODULES_DATA_DIR") is { Length: > 0 } configured
            ? configured
            : Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "AutoModules", "Workbench"));

    public static ProcessStartInfo CreateStartInfo(string installRoot, string data)
    {
        installRoot = Path.GetFullPath(installRoot);
        var info = new ProcessStartInfo(Path.Combine(installRoot, "python", "pythonw.exe"))
        { UseShellExecute = false, CreateNoWindow = true, WorkingDirectory = Path.GetFullPath(data) };
        info.ArgumentList.Add("-I");
        info.ArgumentList.Add("-B");
        info.ArgumentList.Add(Path.Combine(installRoot, "app", "main.py"));
        info.Environment.Remove("PYTHONHOME");
        info.Environment.Remove("PYTHONPATH");
        info.Environment.Remove("QT_QPA_PLATFORM");
        info.Environment["PYTHONNOUSERSITE"] = "1";
        info.Environment["PYTHONDONTWRITEBYTECODE"] = "1";
        info.Environment["AUTO_MODULES_DATA_DIR"] = Path.GetFullPath(data);
        info.Environment["AUTO_MODULES_HOST_DIR"] = Path.Combine(installRoot, "host");
        return info;
    }

    public static void ValidatePayload(string root)
    {
        foreach (var relative in new[] { "python/pythonw.exe", "python/python.exe", "app/main.py", "host/VirtualGamepadHost.exe" })
            if (!File.Exists(Path.Combine(root, relative))) throw new FileNotFoundException("安装文件不完整，请重新安装: " + relative);
    }

    public static void SeedDefaults(string defaults, string data)
    {
        Directory.CreateDirectory(data);
        CopyMissing(Path.Combine(defaults, "config.json"), Path.Combine(data, "config.json"));
        var profiles = Path.Combine(defaults, "virtual_gamepad", "configs");
        if (Directory.Exists(profiles))
            foreach (var source in Directory.EnumerateFiles(profiles, "*.json"))
                CopyMissing(source, Path.Combine(data, "virtual_gamepad", "configs", Path.GetFileName(source)));
        var maps = Path.Combine(defaults, "map_data");
        if (!Directory.Exists(maps)) return;
        var targetMaps = Path.Combine(data, "map_data");
        Directory.CreateDirectory(targetMaps);
        foreach (var source in Directory.EnumerateDirectories(maps))
        {
            var target = Path.Combine(targetMaps, Path.GetFileName(source));
            if (Directory.Exists(target) || File.Exists(target)) continue;
            // An existing map is user-owned as a whole, including intentionally removed files.
            var staged = Path.Combine(targetMaps, ".seed-" + Guid.NewGuid().ToString("N"));
            try { CopyTree(source, staged); Directory.Move(staged, target); }
            catch (IOException) when (Directory.Exists(target)) { /* another launch seeded it */ }
            finally { if (Directory.Exists(staged)) Directory.Delete(staged, true); }
        }
    }

    private static void CopyMissing(string source, string target)
    {
        if (!File.Exists(source) || File.Exists(target)) return;
        RejectLink(source);
        var directory = Path.GetDirectoryName(target)!;
        Directory.CreateDirectory(directory);
        var staged = Path.Combine(directory, ".seed-config-" + Guid.NewGuid().ToString("N") + ".tmp");
        try
        {
            File.Copy(source, staged, overwrite: false);
            File.Move(staged, target, overwrite: false);
        }
        catch (IOException) when (File.Exists(target)) { }
        finally { if (File.Exists(staged)) File.Delete(staged); }
    }

    private static void CopyTree(string source, string target)
    {
        RejectLink(source);
        Directory.CreateDirectory(target);
        foreach (var file in Directory.EnumerateFiles(source)) { RejectLink(file); File.Copy(file, Path.Combine(target, Path.GetFileName(file))); }
        foreach (var dir in Directory.EnumerateDirectories(source)) CopyTree(dir, Path.Combine(target, Path.GetFileName(dir)));
    }

    private static void RejectLink(string path)
    {
        if ((File.GetAttributes(path) & FileAttributes.ReparsePoint) != 0)
            throw new IOException("安装默认数据不能包含链接: " + path);
    }
}
