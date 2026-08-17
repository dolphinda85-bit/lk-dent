param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$NotificationPayload
)

$notifierRoot = 'C:\Users\ROG\AppData\Local\OpenAI\Codex\runtimes\cua_node'
$notifier = Get-ChildItem -LiteralPath $notifierRoot -Directory -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending |
    ForEach-Object {
        Join-Path $_.FullName 'bin\node_modules\@oai\sky\bin\windows\codex-computer-use.exe'
    } |
    Where-Object { Test-Path -LiteralPath $_ } |
    Select-Object -First 1

if ($notifier) {
    & $notifier 'turn-ended' @NotificationPayload
}

[System.Media.SystemSounds]::Exclamation.Play()
Start-Sleep -Milliseconds 700
