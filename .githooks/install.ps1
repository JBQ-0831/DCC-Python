# 安装 Git 钩子，使预提交版本检查生效
# 只需要执行一次，之后 git commit 时会自动运行 .githooks/pre-commit

Write-Host "Setting Git hooks path to .githooks..."
git config core.hooksPath .githooks

Write-Host "Done! Pre-commit hook installed."
Write-Host "Now 'git commit' will automatically check version consistency between npm and uv packages."