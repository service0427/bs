#!/bin/bash
# BrowserStack API 접속 정보
# 사용법: source browserstack_api_info.sh

export BROWSERSTACK_USERNAME="bsuser_wHW2oU"
export BROWSERSTACK_ACCESS_KEY="fuymXXoQNhshiN5BsZhp"
export BROWSERSTACK_API_URL="https://api.browserstack.com/automate/browsers.json"

# API 조회 함수
get_browserstack_devices() {
    curl -u "${BROWSERSTACK_USERNAME}:${BROWSERSTACK_ACCESS_KEY}" \
         "${BROWSERSTACK_API_URL}"
}

echo "✅ BrowserStack API 정보 로드됨"
echo "   Username: ${BROWSERSTACK_USERNAME}"
echo "   API URL: ${BROWSERSTACK_API_URL}"
echo ""
echo "디바이스 목록 조회: get_browserstack_devices"
