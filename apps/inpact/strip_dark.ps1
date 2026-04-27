$file = "C:\Users\bruke\Pre Atlas\apps\inpact\js\screens.js"
$content = Get-Content $file -Raw -Encoding UTF8

# Strip all dark: class tokens (preceded by space or after open quote)
$content = $content -replace ' dark:[a-zA-Z0-9/:_\[\].@#%-]+', ''

# Fix remaining accent color patterns that aren't dark: prefixed

# gradient cards -> plain white border
$content = $content -replace 'bg-gradient-to-br from-blue-50 to-purple-50', 'bg-white'
$content = $content -replace 'bg-gradient-to-br from-green-50 to-emerald-50', 'bg-white'
$content = $content -replace 'from-green-50 to-emerald-50', ''
$content = $content -replace 'from-blue-50 to-purple-50', ''

# blue text links -> gray
$content = $content -replace "text-blue-600 hover:text-blue-700", "text-gray-700 hover:text-gray-900"
$content = $content -replace 'text-blue-500', 'text-gray-500'
$content = $content -replace 'text-blue-600', 'text-gray-700'
$content = $content -replace 'text-blue-700', 'text-gray-700'
$content = $content -replace 'text-purple-500', 'text-gray-500'
$content = $content -replace 'text-purple-700', 'text-gray-700'
$content = $content -replace 'text-yellow-500', 'text-gray-500'
$content = $content -replace 'text-yellow-600', 'text-gray-600'
$content = $content -replace 'text-yellow-700', 'text-gray-700'
$content = $content -replace 'text-cyan-700', 'text-gray-700'
$content = $content -replace 'text-indigo-700', 'text-gray-700'

# blue bg buttons -> black
$content = $content -replace 'bg-blue-600 text-white rounded-lg hover:bg-blue-700', 'bg-gray-900 text-white rounded-lg hover:bg-gray-800'
$content = $content -replace 'bg-blue-600', 'bg-gray-900'
$content = $content -replace 'hover:bg-blue-700', 'hover:bg-gray-800'

# Routine color schemes -> neutral bg-gray with gray text
$content = $content -replace "'Morning': 'bg-blue-100 text-blue-700'", "'Morning': 'bg-gray-100 text-gray-700'"
$content = $content -replace "'Commute': 'bg-cyan-100 text-cyan-700'", "'Commute': 'bg-gray-100 text-gray-700'"
$content = $content -replace "'Evening': 'bg-purple-100 text-purple-700'", "'Evening': 'bg-gray-100 text-gray-700'"
$content = $content -replace "'Afternoon': 'bg-orange-100 text-orange-700'", "'Afternoon': 'bg-gray-100 text-gray-700'"
$content = $content -replace "'Workout': 'bg-green-100 text-green-700'", "'Workout': 'bg-gray-100 text-gray-700'"
$content = $content -replace "'Work': 'bg-indigo-100 text-indigo-700'", "'Work': 'bg-gray-100 text-gray-700'"

# bg-blue-100 / bg-indigo-100 inline in task status chips
$content = $content -replace 'bg-blue-100 text-blue-700', 'bg-gray-100 text-gray-700'
$content = $content -replace 'bg-indigo-100 text-indigo-700', 'bg-gray-100 text-gray-700'
$content = $content -replace 'bg-purple-100 text-purple-700', 'bg-gray-100 text-gray-700'
$content = $content -replace 'bg-cyan-100 text-cyan-700', 'bg-gray-100 text-gray-700'
$content = $content -replace 'bg-yellow-100 text-yellow-700', 'bg-gray-100 text-gray-700'
$content = $content -replace 'bg-indigo-100', 'bg-gray-100'

# hover:bg-blue-50 / hover:bg-blue-900\/20 
$content = $content -replace 'hover:bg-blue-50', 'hover:bg-gray-50'

# border-blue-200 -> border-gray-200
$content = $content -replace 'border-blue-200', 'border-gray-200'
$content = $content -replace 'border-blue-800', 'border-gray-300'

# text-blue-900 / text-blue-100 in headers
$content = $content -replace 'text-blue-900', 'text-gray-900'
$content = $content -replace 'text-blue-100', 'text-gray-100'
$content = $content -replace 'text-blue-300', 'text-gray-600'
$content = $content -replace 'text-blue-400', 'text-gray-500'

# fa-plus-circle color
$content = $content -replace 'fa-plus-circle text-gray-500', 'fa-plus-circle text-gray-700'

# green-600 Log Win button - keep green for action buttons (wins/streaks)
# Actually let's just leave greens alone - they make semantic sense

Set-Content $file $content -Encoding UTF8 -NoNewline
Write-Host "Done"
