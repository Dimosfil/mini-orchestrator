[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$installer = Join-Path $repoRoot "tools/install-instruction-kit.ps1"
$testRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("gi-bootstrap-test-" + [guid]::NewGuid().ToString("N"))
$forms = @(
    "https://github.com/Dimosfil/general-instructions.git",
    "Dimosfil/general-instructions.git",
    "[Dimosfil/general-instructions.git](https://github.com/Dimosfil/general-instructions.git)",
    $repoRoot
)
$requiredFiles = @(
    "AGENTS.md",
    "COMMANDS.md",
    "tools/AGENT_WORKING_AGREEMENTS.md",
    "tools/AGENT_RUNBOOK.md",
    "tools/agent-start.ps1",
    "tools/project-memory/instruction-kit.json",
    "patterns/AGENTS_RUNTIME/07-startup-and-scope.md"
)

try {
    [void](New-Item -ItemType Directory -Path $testRoot)
    for ($index = 0; $index -lt $forms.Count; $index++) {
        $target = Join-Path $testRoot ("case-" + $index)
        [void](New-Item -ItemType Directory -Path $target)

        if ($index -eq 2) {
            [System.IO.File]::WriteAllText(
                (Join-Path $target "AGENTS.md"),
                "# Existing project instructions",
                [System.Text.UTF8Encoding]::new($false)
            )
        }

        & $installer -Source $forms[$index] -SourceRoot $repoRoot -TargetPath $target | Out-Null

        foreach ($requiredFile in $requiredFiles) {
            $requiredPath = Join-Path $target $requiredFile
            if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
                throw "Bootstrap form '$($forms[$index])' did not create '$requiredFile'."
            }
        }
        if (Test-Path -LiteralPath (Join-Path $target ".git")) {
            throw "Bootstrap form '$($forms[$index])' created a Git repository."
        }
        if ($index -eq 2) {
            $agentsText = [System.IO.File]::ReadAllText((Join-Path $target "AGENTS.md"))
            if ($agentsText -ne "# Existing project instructions") {
                throw "The installer overwrote existing project instructions."
            }
        }

        $metadata = Get-Content -Raw -LiteralPath (Join-Path $target "tools/project-memory/instruction-kit.json") | ConvertFrom-Json
        if ($metadata.update_check.source_repo -ne "https://github.com/Dimosfil/general-instructions.git") {
            throw "Bootstrap form '$($forms[$index])' did not record the canonical source repository."
        }
        if ($metadata.update_check.auto_apply_pending_migrations -ne $true) {
            throw "Bootstrap form '$($forms[$index])' did not enable startup migration auto-application."
        }

        $startupRuleText = [System.IO.File]::ReadAllText(
            (Join-Path $target "patterns/AGENTS_RUNTIME/07-startup-and-scope.md")
        )
        foreach ($needle in @(
            'update_check.enabled: true',
            'auto_apply_pending_migrations',
            'Finding a newer version is not a completed startup'
        )) {
            if (-not $startupRuleText.Contains($needle)) {
                throw "Bootstrap form '$($forms[$index])' is missing startup auto-application rule text: $needle"
            }
        }

        $agentStartText = [System.IO.File]::ReadAllText((Join-Path $target "tools/agent-start.ps1"))
        if (-not $agentStartText.Contains("must apply pending migrations before task work")) {
            throw "Bootstrap form '$($forms[$index])' retained an availability-only startup notice."
        }

        $gitIgnorePath = Join-Path $target ".gitignore"
        $gitIgnoreBefore = [System.IO.File]::ReadAllText($gitIgnorePath)
        & $installer -Source $forms[$index] -SourceRoot $repoRoot -TargetPath $target | Out-Null
        $gitIgnoreAfter = [System.IO.File]::ReadAllText($gitIgnorePath)
        if ($gitIgnoreAfter -ne $gitIgnoreBefore) {
            throw "Bootstrap form '$($forms[$index])' is not idempotent for .gitignore."
        }
    }

    $readmeText = [System.IO.File]::ReadAllText((Join-Path $repoRoot "README.md"))
    $bootstrapText = [System.IO.File]::ReadAllText((Join-Path $repoRoot "BOOTSTRAP.md"))
    foreach ($needle in @(
        '[Dimosfil/general-instructions.git](https://github.com/Dimosfil/general-instructions.git)',
        'patterns/SHARED_INSTRUCTIONS_BOOTSTRAP.md',
        'never means ordinary `git init`'
    )) {
        if (-not ($readmeText + "`n" + $bootstrapText).Contains($needle)) {
            throw "Bootstrap entrypoint is missing required text: $needle"
        }
    }

    Write-Output "GI bootstrap contract checks passed for $($forms.Count) source forms."
} finally {
    if (Test-Path -LiteralPath $testRoot -PathType Container) {
        $resolvedTestRoot = (Resolve-Path -LiteralPath $testRoot).Path
        $resolvedTempRoot = (Resolve-Path -LiteralPath ([System.IO.Path]::GetTempPath())).Path
        if (-not $resolvedTestRoot.StartsWith($resolvedTempRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to remove test data outside the system temp directory: $resolvedTestRoot"
        }
        Remove-Item -LiteralPath $resolvedTestRoot -Recurse -Force
    }
}
