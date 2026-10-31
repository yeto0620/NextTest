[CmdletBinding()]
param([switch]$NoBrowser)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $root

Add-Type -AssemblyName System.Windows.Forms
$message = @'
Choose NextTest mode:

Yes = DeepSeek mode (explain public evidence)
No  = Normal mode (local rules only; agent buttons are disabled)

If no DeepSeek key is stored, the key setup window opens first.
'@
$choice = [System.Windows.Forms.MessageBox]::Show(
    $message,
    'NextTest - Start mode',
    [System.Windows.Forms.MessageBoxButtons]::YesNoCancel,
    [System.Windows.Forms.MessageBoxIcon]::Question
)

if ($choice -eq [System.Windows.Forms.DialogResult]::Cancel) { exit 0 }
if ($choice -eq [System.Windows.Forms.DialogResult]::No) {
    & (Join-Path $root 'start_nexttest.cmd')
    exit $LASTEXITCODE
}

$secret = Join-Path $env:LOCALAPPDATA 'NextTest\secrets\deepseek.key'
if (-not (Test-Path -LiteralPath $secret)) {
    & (Join-Path $root 'configure_nexttest_llm.cmd')
    if ($LASTEXITCODE -ne 0) {
        [System.Windows.Forms.MessageBox]::Show('DeepSeek key setup failed. NextTest was not started.', 'NextTest') | Out-Null
        exit 1
    }
}
& (Join-Path $root 'start_nexttest_with_llm.cmd')
exit $LASTEXITCODE
