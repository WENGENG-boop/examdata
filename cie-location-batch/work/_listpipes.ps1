[System.IO.Directory]::GetFiles('\\.\pipe\') | Where-Object { $_ -like '*kimi*' -or $_ -like '*cu*' }
