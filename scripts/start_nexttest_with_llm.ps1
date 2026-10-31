[CmdletBinding()]
param(
    [ValidateRange(8501, 8510)]
    [int]$Port = 8501,

    [switch]$NoBrowser
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$launcher = Join-Path $root 'start_nexttest.cmd'
$secretFile = Join-Path $env:LOCALAPPDATA 'NextTest\secrets\deepseek.key'
$secureKey = $null
$bstr = [IntPtr]::Zero
$plainKey = $null
$exitCode = 1

try {
    Write-Host ''
    Write-Host 'NextTest DeepSeek secure launch' -ForegroundColor Cyan
    if (-not (Test-Path -LiteralPath $secretFile)) {
        throw 'Stored credential not found. Run configure_nexttest_llm.cmd first.'
    }
    Write-Host 'Loading the Windows current-user encrypted credential.' -ForegroundColor DarkGray
    $encrypted = [IO.File]::ReadAllText($secretFile, [Text.UTF8Encoding]::new($false)).Trim()
    if ([string]::IsNullOrWhiteSpace($encrypted)) {
        throw 'Stored credential is empty. Run configure_nexttest_llm.cmd again.'
    }
    $secureKey = ConvertTo-SecureString -String $encrypted
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
    $plainKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    if ([string]::IsNullOrWhiteSpace($plainKey)) {
        throw 'API Key cannot be empty.'
    }

    $env:NEXTEST_LLM_PROVIDER = 'deepseek'
    $env:NEXTEST_LLM_BASE_URL = 'https://api.deepseek.com'
    $env:NEXTEST_LLM_MODEL = 'deepseek-chat'
    $env:NEXTEST_LLM_API_KEY = $plainKey

    Set-Location -LiteralPath $root
    $launcherArgs = @('--port', $Port)
    if ($NoBrowser) {
        $launcherArgs += '--no-browser'
    }
    & $launcher @launcherArgs
    $exitCode = $LASTEXITCODE
}
finally {
    Remove-Item Env:NEXTEST_LLM_API_KEY -ErrorAction SilentlyContinue
    Remove-Item Env:NEXTEST_LLM_PROVIDER -ErrorAction SilentlyContinue
    Remove-Item Env:NEXTEST_LLM_BASE_URL -ErrorAction SilentlyContinue
    Remove-Item Env:NEXTEST_LLM_MODEL -ErrorAction SilentlyContinue
    $plainKey = $null
    $secureKey = $null
    if ($bstr -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
    Write-Host 'Decrypted DeepSeek credential cleared from this launcher process.' -ForegroundColor DarkGray
}

exit $exitCode
