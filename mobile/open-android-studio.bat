@echo off
cd /d C:\Projects\church_finance\mobile
echo Opening project in Android Studio...
echo.
echo If Android Studio doesn't open automatically, open it manually and select:
echo C:\Projects\church_finance\mobile\android
echo.
if exist "android" (
    echo Android project found at: %cd%\android
    echo.
    echo To run on Android Studio emulator:
    echo 1. Open Android Studio
    echo 2. Select "Open an Existing Project"
    echo 3. Navigate to: C:\Projects\church_finance\mobile\android
    echo 4. Wait for Gradle sync
    echo 5. Click Run - select your emulator
    echo.
    start "" "C:\Projects\church_finance\mobile\android"
) else (
    echo Android project not found. Run 'npx expo prebuild' first to generate it.
)
pause