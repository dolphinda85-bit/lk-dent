$ErrorActionPreference = 'Stop'

function Deny-Command {
    param([string]$Reason)

    $result = @{
        hookSpecificOutput = @{
            hookEventName = 'PreToolUse'
            permissionDecision = 'deny'
            permissionDecisionReason = $Reason
        }
    }
    $result | ConvertTo-Json -Depth 4 -Compress
    exit 0
}

$rawInput = [Console]::In.ReadToEnd()
if ([string]::IsNullOrWhiteSpace($rawInput)) { exit 0 }

try {
    $hookInput = $rawInput | ConvertFrom-Json
} catch {
    exit 0
}

$command = [string]$hookInput.tool_input.command
if ([string]::IsNullOrWhiteSpace($command)) { exit 0 }

$massDelete = '(?i)(\brm(?:\.exe)?\s+[^;\r\n]*-(?:[a-z]*r[a-z]*f|[a-z]*f[a-z]*r)\b|\bRemove-Item\b[^;\r\n]*(?:-Recurse|-r)\b|\b(?:rmdir|rd)(?:\.exe)?\s+/s\b|\bdel(?:\.exe)?\s+[^;\r\n]*/s\b)'
if ($command -match $massDelete) {
    Deny-Command 'Blocked: recursive mass deletion is forbidden by project policy.'
}

$networkSender = '(?i)\b(curl|curl\.exe|wget|wget\.exe|Invoke-WebRequest|Invoke-RestMethod|iwr|irm)\b'
$secretFile = '(?i)(?:\.env(?:\.[\w.-]+)?|[\w.-]+\.(?:key|pem|token))'
$dollarEnv = [Regex]::Escape(([string][char]36) + 'env:')
$secretSource = '(?i)(' + $dollarEnv + '|Env:|\b(?:env|printenv)\b|%[A-Z_][A-Z0-9_]*%|' + $secretFile + ')'
if (($command -match $networkSender) -and ($command -match $secretSource)) {
    Deny-Command 'Blocked: possible transmission of environment variables or secrets.'
}

$secretRead = '(?i)\b(Get-Content|gc|cat|type|more|less)\b[^;\r\n]*' + $secretFile
if ($command -match $secretRead) {
    Deny-Command 'Blocked: full output of a secret file is forbidden.'
}

$widePermissions = '(?i)\bchmod\b[^;\r\n]*(?:^|\s)(?:-R\s+)?(?:0?777|a\+rwx)(?:\s|$)'
if ($command -match $widePermissions) {
    Deny-Command 'Blocked: excessively broad file permissions are forbidden.'
}

exit 0
