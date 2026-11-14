- in PowerShell (Codex on Windows) there is no heredoc: pipe a single-quoted here-string, after switching the pipe
  to UTF-8 so accents survive (the closing '@ must start its line):
$OutputEncoding = [System.Text.UTF8Encoding]::new($false); @'
your message
'@ | python "{{CHAT}}" post --as {{AS}} --room "{{ROOM}}"
