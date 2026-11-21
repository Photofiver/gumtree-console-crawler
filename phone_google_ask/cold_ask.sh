set -euo pipefail
timeout -k 5s 125s adb shell am instrument -w -r -e q_b64 "$QUESTION_B64" -e class com.photofiver.phonebrowser.GoogleAskTest com.photofiver.phonebrowser.test/androidx.test.runner.AndroidJUnitRunner | tee google-ai-ask-instrumentation.txt
grep -q 'OK (1 test)' google-ai-ask-instrumentation.txt
adb pull /sdcard/Android/data/com.photofiver.phonebrowser/files/google-ai-ask-result.json google-ai-ask-result.json
cat google-ai-ask-result.json
