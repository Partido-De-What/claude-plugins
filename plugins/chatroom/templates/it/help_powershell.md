- in PowerShell (Codex su Windows) non c'è heredoc: passa una here-string tra apici singoli con una pipe, dopo aver messo la pipe
  in UTF-8 così gli accenti passano (la chiusura '@ deve iniziare la sua riga):
$OutputEncoding = [System.Text.UTF8Encoding]::new($false); @'
il tuo messaggio
'@ | python "{{CHAT}}" post --as {{AS}} --room "{{ROOM}}"
