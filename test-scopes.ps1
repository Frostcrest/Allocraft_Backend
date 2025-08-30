# Test different OAuth scopes for Schwab
$scopes = @(
    "readonly",
    "AccountAccess", 
    "TraderAPI",
    "https://api.schwabapi.com/trader/v1"
)

$baseUrl = "https://api.schwabapi.com/v1/oauth/authorize"
$clientId = "z39NyhcZwoSlmpZNYstf38Fidd0V0HeTWGMfD9AhWGUj0uOG"  # From previous test
$redirectUri = "https://allocraft-backend.onrender.com/schwab/callback"

Write-Host "Testing different OAuth scopes for Schwab API:" -ForegroundColor Cyan
Write-Host ""

foreach ($scope in $scopes) {
    Write-Host "Scope: $scope" -ForegroundColor Yellow
    $params = @{
        response_type = "code"
        client_id = $clientId
        redirect_uri = $redirectUri
        scope = $scope
        state = "test123"
    }
    
    $queryString = ($params.GetEnumerator() | ForEach-Object { "$($_.Key)=$([System.Uri]::EscapeDataString($_.Value))" }) -join "&"
    $testUrl = "$baseUrl?$queryString"
    
    Write-Host "URL: $($testUrl.Substring(0, 100))..." -ForegroundColor Gray
    Write-Host ""
}

Write-Host "Try each of these URLs manually in your browser to see which one works:" -ForegroundColor Green
Write-Host "The one that doesn't give the 'unable to complete request' error is the correct scope." -ForegroundColor Green
