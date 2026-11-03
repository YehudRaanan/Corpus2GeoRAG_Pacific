[CmdletBinding()]
param([string]$Plan, [switch]$Status, [switch]$Help, [string]$DatasetVersion)
$ErrorActionPreference = 'Stop'
$pipelineFolder = Join-Path $PSScriptRoot 'pipeline'
$pipelineConfig = Get-Content -LiteralPath (Join-Path $pipelineFolder 'current.json') -Raw | ConvertFrom-Json
$pipelineEntry = Join-Path $pipelineConfig.code_root 'run.py'
if ((Get-FileHash -LiteralPath $pipelineEntry -Algorithm SHA256).Hash.ToLowerInvariant() -ne $pipelineConfig.entrypoint_sha256) {
    throw 'The selected code changed. Review and update pipeline/current.json before running.'
}
$pipelineRegistry = Get-Content -LiteralPath (Join-Path $pipelineFolder 'data_versions.json') -Raw | ConvertFrom-Json
if ($DatasetVersion -and $null -eq $pipelineRegistry.versions.PSObject.Properties[$DatasetVersion]) { throw 'Unknown data version.' }
if ($Status -or (-not $Plan -and -not $Help)) {
    $pipelineSelected = if ($DatasetVersion) { $pipelineRegistry.versions.$DatasetVersion } else { $null }
    [ordered]@{ implementation=$pipelineConfig.implementation; code_root=$pipelineConfig.code_root;
        code_checkpoint=$pipelineConfig.code_checkpoint; archive=$pipelineConfig.legacy_archive;
        data_versions=@($pipelineRegistry.versions.PSObject.Properties.Name); selected_data_version=$pipelineSelected;
        explicit_plan_required=$true; data_processing_started=$false } | ConvertTo-Json -Depth 10
    return
}
if ($Help) { $pipelineArgument = '--help' } else {
    $pipelineArgument = (Resolve-Path -LiteralPath $Plan).Path
    $pipelinePlan = Get-Content -LiteralPath $pipelineArgument -Raw | ConvertFrom-Json
    if ($DatasetVersion -and $pipelinePlan.data_version -ne $DatasetVersion) { throw 'Plan data_version differs from the selected version.' }
}
$pipelineEnvNames = @('PYTHONPATH','PYTHONDONTWRITEBYTECODE','PYTHONIOENCODING','RAPIDFUZZ_IMPLEMENTATION')
$pipelinePreviousEnv = @{}
foreach ($pipelineName in $pipelineEnvNames) { $pipelinePreviousEnv[$pipelineName]=[Environment]::GetEnvironmentVariable($pipelineName,'Process') }
try {
    $env:PYTHONPATH = (@($pipelineConfig.code_root,(Join-Path $pipelineFolder 'runtime_shims')) + @($pipelineConfig.runtime.python_paths) + @($pipelinePreviousEnv['PYTHONPATH'])) -join [IO.Path]::PathSeparator
    $env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTHONIOENCODING='utf-8'; $env:RAPIDFUZZ_IMPLEMENTATION='python'
    $pipelineBootstrap = "import sys,runpy; sys.addaudithook(lambda e,a: (_ for _ in ()).throw(RuntimeError('Offline pipeline blocked network acquisition')) if e=='socket.connect' else None); sys.argv=[sys.argv[1],sys.argv[2]]; runpy.run_path(sys.argv[0],run_name='__main__')"
    & $pipelineConfig.runtime.python_executable -B -c $pipelineBootstrap $pipelineEntry $pipelineArgument
    $pipelineExitCode=$LASTEXITCODE
} finally {
    foreach ($pipelineName in $pipelineEnvNames) { [Environment]::SetEnvironmentVariable($pipelineName,$pipelinePreviousEnv[$pipelineName],'Process') }
}
exit $pipelineExitCode
