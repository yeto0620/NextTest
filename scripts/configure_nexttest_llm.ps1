[CmdletBinding()]
param(
    [switch]$Remove
)

$ErrorActionPreference = 'Stop'
$secretRoot = Join-Path $env:LOCALAPPDATA 'NextTest\secrets'
$secretFile = Join-Path $secretRoot 'deepseek.key'

if ($Remove) {
    if (Test-Path -LiteralPath $secretFile) {
        Remove-Item -LiteralPath $secretFile -Force
        Write-Host 'NextTest DeepSeek credential removed.' -ForegroundColor Yellow
    }
    else {
        Write-Host 'No stored NextTest DeepSeek credential was found.' -ForegroundColor DarkGray
    }
    exit 0
}

Write-Host ''
Write-Host 'NextTest DeepSeek permanent setup' -ForegroundColor Cyan
Write-Host 'The key is masked and encrypted with Windows DPAPI for the current user.' -ForegroundColor DarkGray
$secureKey = Read-Host 'Paste NEXTEST_LLM_API_KEY' -AsSecureString

$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
try {
    $plainKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    if ([string]::IsNullOrWhiteSpace($plainKey)) {
        throw 'API Key cannot be empty.'
    }

    Write-Host 'Validating the credential with DeepSeek before storing it...' -ForegroundColor DarkGray
    $headers = @{
        Authorization = "Bearer $plainKey"
        'Content-Type' = 'application/json'
    }
    $payload = @{
        model = 'deepseek-chat'
        messages = @(@{
            role = 'user'
            content = 'Reply with OK only.'
        })
        max_tokens = 4
        stream = $false
    } | ConvertTo-Json -Depth 5 -Compress

    try {
        $validation = Invoke-WebRequest `
            -Method Post `
            -Uri 'https://api.deepseek.com/chat/completions' `
            -Headers $headers `
            -Body $payload `
            -TimeoutSec 30 `
            -UseBasicParsing
        if ([int]$validation.StatusCode -ne 200) {
            throw "DeepSeek returned HTTP $([int]$validation.StatusCode)."
        }
    }
    catch {
        $statusCode = $null
        if ($_.Exception.Response) {
            try { $statusCode = [int]$_.Exception.Response.StatusCode } catch {}
        }
        $statusText = if ($null -ne $statusCode) { "HTTP $statusCode" } else { 'network error' }
        throw "DeepSeek credential validation failed ($statusText). The existing stored credential was not changed."
    }
}
finally {
    $plainKey = $null
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
}

[IO.Directory]::CreateDirectory($secretRoot) | Out-Null
$encrypted = ConvertFrom-SecureString -SecureString $secureKey
[IO.File]::WriteAllText($secretFile, $encrypted, [Text.UTF8Encoding]::new($false))
$secureKey = $null

Write-Host 'Credential stored with Windows current-user encryption.' -ForegroundColor Green
Write-Host 'DeepSeek credential validation passed.' -ForegroundColor Green
Write-Host 'Future launches can use start_nexttest_with_llm.cmd without entering the key again.' -ForegroundColor DarkGray
Write-Host "Stored outside the repository: $secretFile" -ForegroundColor DarkGray
