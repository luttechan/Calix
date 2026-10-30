#ifndef AppVersion
  #define AppVersion "1.2.0-r4"
#endif

#ifndef BundleDir
  #define BundleDir "..\dist\Calix " + AppVersion
#endif
#ifndef OutputDir
  #define OutputDir "..\dist\installer"
#endif
#ifndef NoticeFile
  #define NoticeFile OutputDir + "\THIRD_PARTY_NOTICES.txt"
#endif

[Setup]
AppId={{5DE5900D-012F-4F26-8CE8-4F78EF135843}
AppName=Calix
AppVersion={#AppVersion}
AppPublisher=Lutté Laurent
AppPublisherURL=https://luttechan.github.io/calix/
DefaultDirName={localappdata}\Programs\Calix
DefaultGroupName=Calix
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
DisableProgramGroupPage=yes
DisableWelcomePage=yes
UninstallDisplayIcon={app}\Calix.exe
SetupIconFile=..\asset\icons\calix.ico
OutputDir={#OutputDir}
OutputBaseFilename=Calix-{#AppVersion}-Setup-x64
Compression=lzma2/fast
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
CloseApplicationsFilter=Calix.exe
RestartApplications=no
SetupLogging=yes

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"

[Files]
Source: "{#BundleDir}\Calix.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#BundleDir}\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#NoticeFile}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Calix"; Filename: "{app}\Calix.exe"; AppUserModelID: "LutteLaurent.Calix"

[Run]
Filename: "{app}\Calix.exe"; Description: "Calix 실행"; Flags: nowait postinstall skipifsilent
