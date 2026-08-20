[Setup]
; Application metadata
AppName=HR Payslip Automator
AppVersion=1.0.0
AppPublisher=SIGA Systems
DefaultDirName={autopf}\HRPayslipAutomator
DefaultGroupName=HR Payslip Automator
DisableProgramGroupPage=yes
OutputDir=dist_installer
OutputBaseFilename=HRPayslipAutomator_Setup_v1.0.0
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; Dist directory containing all bundled PyInstaller binaries
Source: "dist\HRPayslipAutomator\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\HR Payslip Automator"; Filename: "{app}\HRPayslipAutomator.exe"
Name: "{autodesktop}\HR Payslip Automator"; Filename: "{app}\HRPayslipAutomator.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\HRPayslipAutomator.exe"; Description: "{cm:LaunchProgram,HR Payslip Automator}"; Flags: nowait postinstall skipifsilent
