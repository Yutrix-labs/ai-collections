# PowerShell script to download and run Redis on Windows

Write-Host "======================================" -ForegroundColor Cyan
Write-Host "Redis Installation Helper for Windows" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

# Check if Redis is already running
$redisRunning = $false
try {
    $testConnection = Test-NetConnection localhost -Port 6379 -WarningAction SilentlyContinue -ErrorAction SilentlyContinue
    if ($testConnection.TcpTestSucceeded) {
        $redisRunning = $true
        Write-Host "✅ Redis is already running on port 6379!" -ForegroundColor Green
        Write-Host ""
        Write-Host "Testing connection..." -ForegroundColor Yellow

        # Try to ping Redis (if redis-cli is available)
        try {
            $result = redis-cli ping 2>$null
            if ($result -eq "PONG") {
                Write-Host "✅ Redis is responding: PONG" -ForegroundColor Green
                exit 0
            }
        } catch {
            Write-Host "✅ Redis is running but redis-cli not in PATH" -ForegroundColor Green
            Write-Host "This is OK - your application can still connect!" -ForegroundColor Green
            exit 0
        }
    }
} catch {
    # Continue with installation
}

if (-not $redisRunning) {
    Write-Host "❌ Redis is not running on port 6379" -ForegroundColor Red
    Write-Host ""
    Write-Host "Options to install Redis:" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "1. Download Memurai (Recommended)" -ForegroundColor Cyan
    Write-Host "   URL: https://www.memurai.com/get-memurai" -ForegroundColor Gray
    Write-Host "   - Easy installer" -ForegroundColor Gray
    Write-Host "   - Runs as Windows service" -ForegroundColor Gray
    Write-Host ""
    Write-Host "2. Download Redis for Windows" -ForegroundColor Cyan
    Write-Host "   URL: https://github.com/tporadowski/redis/releases" -ForegroundColor Gray
    Write-Host "   - Download: Redis-x64-5.0.14.1.msi" -ForegroundColor Gray
    Write-Host "   - Run installer" -ForegroundColor Gray
    Write-Host ""
    Write-Host "3. Use Docker (if installed)" -ForegroundColor Cyan
    Write-Host "   Command: docker run -d -p 6379:6379 redis:7" -ForegroundColor Gray
    Write-Host ""
    Write-Host "4. Download portable Redis (no install needed)" -ForegroundColor Cyan
    Write-Host "   I can help you set this up!" -ForegroundColor Gray
    Write-Host ""

    $choice = Read-Host "Would you like to download portable Redis now? (y/n)"

    if ($choice -eq 'y' -or $choice -eq 'Y') {
        Write-Host ""
        Write-Host "Downloading portable Redis..." -ForegroundColor Yellow

        $redisUrl = "https://github.com/tporadowski/redis/releases/download/v5.0.14.1/Redis-x64-5.0.14.1.zip"
        $redisZip = "$env:TEMP\redis.zip"
        $redisDir = "$PSScriptRoot\redis"

        try {
            # Download Redis
            Write-Host "Downloading from GitHub..." -ForegroundColor Yellow
            Invoke-WebRequest -Uri $redisUrl -OutFile $redisZip -UseBasicParsing

            # Extract
            Write-Host "Extracting..." -ForegroundColor Yellow
            Expand-Archive -Path $redisZip -DestinationPath $redisDir -Force

            Write-Host "✅ Redis downloaded successfully!" -ForegroundColor Green
            Write-Host ""
            Write-Host "Starting Redis server..." -ForegroundColor Yellow

            # Start Redis
            Start-Process -FilePath "$redisDir\redis-server.exe" -WindowStyle Minimized

            Start-Sleep -Seconds 2

            # Test connection
            $testConnection = Test-NetConnection localhost -Port 6379 -WarningAction SilentlyContinue
            if ($testConnection.TcpTestSucceeded) {
                Write-Host "✅ Redis is now running!" -ForegroundColor Green
                Write-Host ""
                Write-Host "Redis server is running in the background." -ForegroundColor Cyan
                Write-Host "To stop it, close the Redis window or run: taskkill /IM redis-server.exe" -ForegroundColor Gray
            } else {
                Write-Host "⚠️ Redis may not have started. Check the Redis window." -ForegroundColor Yellow
            }

        } catch {
            Write-Host "❌ Error downloading Redis: $_" -ForegroundColor Red
            Write-Host ""
            Write-Host "Please download manually from:" -ForegroundColor Yellow
            Write-Host "https://github.com/tporadowski/redis/releases" -ForegroundColor Cyan
        }
    } else {
        Write-Host ""
        Write-Host "Please install Redis using one of the options above." -ForegroundColor Yellow
        Write-Host "Then restart your FastAPI server." -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "======================================" -ForegroundColor Cyan
