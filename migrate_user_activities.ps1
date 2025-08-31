# PowerShell Migration Script for user_activities table
# Run this script to make user_id nullable in user_activities table

Write-Host "Starting user_activities migration..." -ForegroundColor Yellow

# Change to the project directory
Set-Location "c:\Users\shafi\Documents\Work\mcp-client\mcp-client"

# Run the Python migration script
try {
    Write-Host "Running migration script..." -ForegroundColor Blue
    python migrate_user_activities.py
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "`n✓ Migration completed successfully!" -ForegroundColor Green
        Write-Host "The user_activities table now allows NULL user_id values for anonymous tracking." -ForegroundColor Green
    } else {
        Write-Host "`n✗ Migration failed!" -ForegroundColor Red
        Write-Host "Please check the error messages above and try again." -ForegroundColor Red
    }
} catch {
    Write-Host "`n✗ Error running migration: $_" -ForegroundColor Red
}

Write-Host "`nPress any key to continue..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
