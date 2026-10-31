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
$validationFailure = $null
try {
    $plainKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    if ([string]::IsNullOrWhiteSpace($plainKey)) {
        $validationFailure = 'API Key cannot be empty.'
    }

    if ($null -eq $validationFailure) {
        Write-Host 'Validating the credential with DeepSeek before storing it...' -ForegroundColor DarkGray
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Add-Type -AssemblyName System.Net.Http
        $payload = @{
            model = 'deepseek-chat'
            messages = @(@{
                role = 'user'
                content = 'Reply with OK only.'
            })
            max_tokens = 4
            stream = $false
        } | ConvertTo-Json -Depth 5 -Compress

        $validated = $false
        for ($attempt = 1; $attempt -le 3 -and -not $validated; $attempt++) {
            $client = $null
            $content = $null
            $response = $null
            try {
                $client = [Net.Http.HttpClient]::new()
                $client.Timeout = [TimeSpan]::FromSeconds(30)
                $client.DefaultRequestHeaders.Authorization = [Net.Http.Headers.AuthenticationHeaderValue]::new('Bearer', $plainKey)
                $content = [Net.Http.StringContent]::new($payload, [Text.Encoding]::UTF8, 'application/json')
                $response = $client.PostAsync('https://api.deepseek.com/chat/completions', $content).GetAwaiter().GetResult()
                $statusCode = [int]$response.StatusCode
                if ($statusCode -eq 200) {
                    $validated = $true
                }
                else {
                    $validationFailure = "DeepSeek credential validation failed (HTTP $statusCode). The existing stored credential was not changed."
                    break
                }
            }
            catch {
                if ($attempt -lt 3) {
                    Write-Host "Connection attempt $attempt failed; retrying..." -ForegroundColor DarkGray
                    Start-Sleep -Seconds $attempt
                }
                else {
                    $validationFailure = 'DeepSeek credential validation failed after 3 network attempts. The existing stored credential was not changed.'
                }
            }
            finally {
                if ($null -ne $response) { $response.Dispose() }
                if ($null -ne $content) { $content.Dispose() }
                if ($null -ne $client) { $client.Dispose() }
            }
        }
    }
}
finally {
    $plainKey = $null
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
}

if ($null -ne $validationFailure) {
    $secureKey = $null
    Write-Host $validationFailure -ForegroundColor Red
    exit 1
}

[IO.Directory]::CreateDirectory($secretRoot) | Out-Null
$encrypted = ConvertFrom-SecureString -SecureString $secureKey
[IO.File]::WriteAllText($secretFile, $encrypted, [Text.UTF8Encoding]::new($false))
$secureKey = $null

Write-Host 'Credential stored with Windows current-user encryption.' -ForegroundColor Green
Write-Host 'DeepSeek credential validation passed.' -ForegroundColor Green
Write-Host 'Future launches can use start_nexttest_with_llm.cmd without entering the key again.' -ForegroundColor DarkGray
Write-Host "Stored outside the repository: $secretFile" -ForegroundColor DarkGray
