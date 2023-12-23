$Timestamp=(Get-Date -format "yyyyMMdd")

foreach($path in [System.IO.File]::ReadLines("\\deda1w8306\DiskSpace\FileShare\File Size Monitoring\InputFilePathsForFileSizeMonitoring_Conf_Prod.csv"))
{
       $path
       $ServerName = $path -split ","
       $Server=$ServerName[2]

       $path_=$path.replace(',','\')
       $path_
       $Server
       Write-Output $ServerName,$Server

 
      Get-childitem -path "$path_"  -Recurse | where {!$_.PSIsContainer} | select-object FullName, LastWriteTime, Length |Export-Csv -Path "\\deda1w8306\DiskSpace\FileShare\File Size Monitoring\$($Server)_FileSizeMonitoring.csv" -Delim ',' -En UTF8 -NoTypeInformation
}