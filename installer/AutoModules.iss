; Build with Inno Setup 6:
; ISCC.exe /DPayloadDir=... /DOutputDir=... /DAppVersion=0.1.0 AutoModules.iss
#ifndef PayloadDir
  #error PayloadDir must point to a complete staged offline payload
#endif
#ifndef OutputDir
  #define OutputDir "output"
#endif
#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif

[Setup]
AppId={{6D7B4AA5-2AB1-4A57-A063-2F3D822D6F91}
AppName=AutoModules 工作台
AppVersion={#AppVersion}
AppPublisher=AutoModules
DefaultDirName={autopf}\AutoModules
DefaultGroupName=AutoModules
DisableProgramGroupPage=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64os
ArchitecturesInstallIn64BitMode=x64os
MinVersion=10.0
OutputDir={#OutputDir}
OutputBaseFilename=AutoModules-Setup-{#AppVersion}-win-x64
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupLogging=yes
CloseApplications=no
RestartApplications=no
UninstallDisplayIcon={app}\AutoModules.exe
UninstallDisplayName=AutoModules 工作台
ChangesEnvironment=no

[Languages]
Name: "chinesesimplified"; MessagesFile: "compiler:Default.isl"

[LangOptions]
LanguageName=简体中文
LanguageID=$0804
LanguageCodePage=0
DialogFontName=Microsoft YaHei UI
DialogFontSize=9

[Messages]
SetupAppTitle=安装
SetupWindowTitle=安装 - %1
UninstallAppTitle=卸载
UninstallAppFullTitle=卸载 %1
InformationTitle=提示
ConfirmTitle=确认
ErrorTitle=错误
SetupAlreadyRunning=安装程序已在运行。
AdminPrivilegesRequired=安装程序需要管理员权限。
WindowsVersionNotSupported=此程序不支持当前 Windows 版本。
ExitSetupTitle=退出安装
ExitSetupMessage=安装尚未完成。现在退出将无法完成安装。%n%n你可以稍后重新运行安装程序。确定退出吗？
ButtonBack=< 上一步(&B)
ButtonNext=下一步(&N) >
ButtonInstall=安装(&I)
ButtonOK=确定
ButtonCancel=取消
ButtonYes=是(&Y)
ButtonNo=否(&N)
ButtonFinish=完成(&F)
ButtonBrowse=浏览(&B)...
ButtonWizardBrowse=浏览(&R)...
ClickNext=点击“下一步”继续，或点击“取消”退出安装。
WelcomeLabel1=欢迎安装 [name]
WelcomeLabel2=安装程序将安装 [name/ver]、内置运行环境和虚拟手柄所需组件。%n%n请先关闭工作台和游戏，再继续安装。
WizardSelectDir=选择安装位置
SelectDirDesc=将 [name] 安装在哪里？
SelectDirLabel3=程序将安装到以下文件夹。地图和配置保存在用户数据目录，升级不会覆盖已有修改。
SelectDirBrowseLabel=点击“下一步”继续。如需更改位置，请点击“浏览”。
DiskSpaceGBLabel=至少需要 [gb] GB 可用磁盘空间。
DiskSpaceMBLabel=至少需要 [mb] MB 可用磁盘空间。
WizardSelectTasks=安装选项
SelectTasksDesc=选择需要的附加内容
SelectTasksLabel2=请选择附加内容，然后点击“下一步”。
WizardReady=准备安装
ReadyLabel1=现在可以开始安装 [name]。
ReadyLabel2a=点击“安装”继续，或点击“上一步”修改设置。
ReadyLabel2b=点击“安装”继续。
ReadyMemoDir=安装位置：
ReadyMemoGroup=开始菜单文件夹：
ReadyMemoTasks=附加内容：
WizardPreparing=正在准备安装
PreparingDesc=正在检查 [name] 的安装条件。
CannotContinue=安装无法继续，请点击“取消”退出。
PrepareToInstallNeedsRestart=需要重启 Windows。请保存正在进行的工作；重启后重新运行安装程序以完成 [name] 的安装。%n%n是否现在重启？
WizardInstalling=正在安装
InstallingLabel=正在安装 [name]，请稍候。
FinishedHeadingLabel=[name] 安装完成
FinishedLabelNoIcons=[name] 已安装到此电脑。
FinishedLabel=[name] 已安装到此电脑。以后可通过桌面或开始菜单快捷方式打开工作台。
ClickFinish=点击“完成”退出安装程序。
FinishedRestartLabel=需要重启电脑才能完成 [name] 的安装。是否现在重启？
FinishedRestartMessage=需要重启电脑才能完成 [name] 的安装。%n%n是否现在重启？
YesRadio=现在重启电脑(&Y)
NoRadio=稍后手动重启(&N)
SetupAborted=安装尚未完成。%n%n请解决问题后重新运行安装程序。
AbortRetryIgnoreRetry=重试(&T)
AbortRetryIgnoreCancel=取消安装
RetryCancelRetry=重试(&T)
RetryCancelCancel=取消
StatusCreateDirs=正在创建文件夹...
StatusExtractFiles=正在解压文件...
StatusCreateIcons=正在创建快捷方式...
StatusCreateRegistryEntries=正在写入安装信息...
StatusSavingUninstall=正在保存卸载信息...
StatusRunProgram=正在完成安装...
StatusRollback=正在回退更改...

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; Flags: checkedonce
Name: "maps"; Description: "安装随包提供的地图（保留已有地图的修改）"; Flags: checkedonce

[Files]
; The launcher MUST be published as self-contained single-file with native libraries included.
Source: "{#PayloadDir}\AutoModules.exe"; Flags: dontcopy
Source: "{#PayloadDir}\prerequisites\ViGEmBus_1.22.0_x64_x86_arm64.exe"; Flags: dontcopy
Source: "{#PayloadDir}\*"; DestDir: "{app}"; Excludes: "defaults\map_data\*"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#PayloadDir}\defaults\map_data\*"; DestDir: "{app}\defaults\map_data"; Flags: ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist; Tasks: maps

[Icons]
Name: "{group}\AutoModules 工作台"; Filename: "{app}\AutoModules.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\AutoModules 工作台"; Filename: "{app}\AutoModules.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\AutoModules.exe"; Description: "打开 AutoModules 工作台"; Flags: postinstall nowait skipifsilent

[Code]
var
  DriverReady: Boolean;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
  PrerequisiteDir: String;
begin
  Result := '';
  ExtractTemporaryFile('AutoModules.exe');
  if not Exec(ExpandConstant('{tmp}\AutoModules.exe'), '--check-running "' + ExpandConstant('{app}') + '"', ExpandConstant('{tmp}'), SW_HIDE, ewWaitUntilTerminated, ResultCode) then
  begin
    Result := '无法检查正在运行的程序，请关闭工作台后重试。';
    Exit;
  end;
  if ResultCode <> 0 then
  begin
    Result := '请关闭已安装的 AutoModules 工作台、手柄窗口和后台进程，再点击重试。安装程序不会强制结束任何进程。';
    Exit;
  end;
  if DriverReady then Exit;
  WizardForm.PreparingLabel.Caption := '正在检查虚拟 Xbox 驱动。缺少驱动时将安装经过验证的官方 ViGEmBus，请稍候……';
  ExtractTemporaryFile('ViGEmBus_1.22.0_x64_x86_arm64.exe');
  PrerequisiteDir := ExpandConstant('{tmp}\prerequisites');
  ForceDirectories(PrerequisiteDir);
  if not FileCopy(ExpandConstant('{tmp}\ViGEmBus_1.22.0_x64_x86_arm64.exe'), PrerequisiteDir + '\ViGEmBus_1.22.0_x64_x86_arm64.exe', False) then
  begin
    Result := '无法准备驱动安装文件，请检查可用磁盘空间后重试。';
    Exit;
  end;
  if not Exec(ExpandConstant('{tmp}\AutoModules.exe'), '--ensure-driver', ExpandConstant('{tmp}'), SW_HIDE, ewWaitUntilTerminated, ResultCode) then
  begin
    Result := '无法启动虚拟 Xbox 驱动安装程序。请查看 %LOCALAPPDATA%\AutoModules\Workbench\logs\launcher.log。';
    Exit;
  end;
  case ResultCode of
    0: DriverReady := True;
    3010: begin
      NeedsRestart := True;
      Result := 'ViGEmBus 需要重启 Windows。请保存工作并重启，再重新运行本安装程序。当前安装尚未完成。';
    end;
    11: Result := '驱动完整性或发布者验证失败，已停止安装。请重新获取安装包，不要跳过校验。';
    20: Result := '官方 ViGEmBus 驱动安装失败。请查看 %LOCALAPPDATA%\AutoModules\Workbench\logs\vigembus-install.log 后重试。';
    21: Result := '虚拟 Xbox 驱动暂不可用。请重启 Windows 后重试；仍失败时查看启动日志。安装程序没有降级或删除已有驱动。';
  else
    Result := '虚拟 Xbox 驱动检查失败（代码 ' + IntToStr(ResultCode) + '）。请查看 %LOCALAPPDATA%\AutoModules\Workbench\logs\launcher.log。';
  end;
end;

function InitializeUninstall(): Boolean;
var
  ResultCode: Integer;
begin
  Result := False;
  if not FileExists(ExpandConstant('{app}\AutoModules.exe')) then
  begin
    SuppressibleMsgBox('缺少用于安全检查的启动程序。请先用安装包修复安装，再卸载；此时不会删除正在使用的文件。', mbError, MB_OK, IDOK);
    Exit;
  end;
  while True do
  begin
    if not Exec(ExpandConstant('{app}\AutoModules.exe'), '--check-running "' + ExpandConstant('{app}') + '"', ExpandConstant('{app}'), SW_HIDE, ewWaitUntilTerminated, ResultCode) then
    begin
      SuppressibleMsgBox('无法检查正在运行的程序，卸载已取消。请关闭工作台后重试。', mbError, MB_OK, IDOK);
      Exit;
    end;
    if ResultCode = 0 then
    begin
      Result := True;
      Exit;
    end;
    if ResultCode <> 30 then
    begin
      SuppressibleMsgBox('安全检查失败，卸载已取消。请查看启动日志后重试（代码 ' + IntToStr(ResultCode) + '）。', mbError, MB_OK, IDOK);
      Exit;
    end;
    if SuppressibleMsgBox('工作台或手柄后台仍在运行。请先正常关闭，再点击“重试”。卸载程序不会强制结束进程，也不会删除地图或配置。', mbInformation, MB_RETRYCANCEL, IDCANCEL) = IDCANCEL then Exit;
  end;
end;

// No [UninstallDelete] entries: maps, profiles, logs and per-machine pairing identity stay intact.
// ViGEmBus is shared with other software and is never removed during application uninstall.
