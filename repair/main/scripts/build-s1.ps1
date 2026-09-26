param([string]$OutputDirectory = "$env:TEMP/repair-s1-build", [string]$Java = 'java', [string]$Python = 'python')
$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
$OutputDirectory = (Resolve-Path -LiteralPath $OutputDirectory).Path
$artifacts = @(
  'org/jetbrains/kotlin/kotlin-compiler-embeddable/2.1.20/kotlin-compiler-embeddable-2.1.20.jar',
  'org/jetbrains/kotlin/kotlin-stdlib/2.1.20/kotlin-stdlib-2.1.20.jar',
  'org/jetbrains/kotlin/kotlin-script-runtime/2.1.20/kotlin-script-runtime-2.1.20.jar',
  'org/jetbrains/kotlin/kotlin-reflect/1.6.10/kotlin-reflect-1.6.10.jar',
  'org/jetbrains/kotlin/kotlin-daemon-embeddable/2.1.20/kotlin-daemon-embeddable-2.1.20.jar',
  'org/jetbrains/kotlinx/kotlinx-coroutines-core-jvm/1.8.0/kotlinx-coroutines-core-jvm-1.8.0.jar',
  'org/jetbrains/intellij/deps/trove4j/1.0.20200330/trove4j-1.0.20200330.jar',
  'org/jetbrains/annotations/13.0/annotations-13.0.jar',
  'com/google/code/gson/gson/2.11.0/gson-2.11.0.jar'
)
foreach ($artifact in $artifacts) {
  $file = Join-Path $OutputDirectory ($artifact.Split('/')[-1])
  if (!(Test-Path -LiteralPath $file)) {
    & $Python -c 'import sys, urllib.request; urllib.request.urlretrieve(sys.argv[1], sys.argv[2])' "https://repo.maven.apache.org/maven2/$artifact" "$file.part"
    if ($LASTEXITCODE -ne 0) { throw "Download failed: $artifact" }
    Move-Item -LiteralPath "$file.part" -Destination $file
  }
}
$deps = ($artifacts | ForEach-Object { Join-Path $OutputDirectory ($_.Split('/')[-1]) }) -join [IO.Path]::PathSeparator
$source = Join-Path $PSScriptRoot '../kotlin/src/org/jetbrains/research/lockrepair/S1.kt'
$jar = Join-Path $OutputDirectory 's1.jar'
& $Java -cp $deps org.jetbrains.kotlin.cli.jvm.K2JVMCompiler -no-stdlib -no-reflect -classpath $deps -d $jar $source
if ($LASTEXITCODE -ne 0) { throw 'S1 compilation failed' }
$runtime = @($jar, (Join-Path $OutputDirectory 'kotlin-stdlib-2.1.20.jar'), (Join-Path $OutputDirectory 'gson-2.11.0.jar')) -join [IO.Path]::PathSeparator
Set-Content -LiteralPath (Join-Path $OutputDirectory 'classpath.txt') -Value $runtime -Encoding UTF8
Write-Output $runtime
