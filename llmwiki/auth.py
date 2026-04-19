import time
import requests
from typing import Optional, Dict, Any
from rich.console import Console
from llmwiki.config import UserConfig

console = Console()

OPENAI_DEVICE_CODE_URL = "https://api.openai.com/v1/oauth/device/code"
OPENAI_TOKEN_URL = "https://api.openai.com/v1/oauth/token"
CLIENT_ID = "ooc_OpenAI_CLI"  # Official OpenAI CLI client ID
SCOPE = "openid profile email offline_access"

def start_openai_device_flow() -> bool:
    """
    Start OpenAI Device Flow authorization, guide user to login, and save tokens.
    Returns True if authorization succeeds, False otherwise.
    """
    # Step 1: Request device code
    try:
        response = requests.post(
            OPENAI_DEVICE_CODE_URL,
            data={
                "client_id": CLIENT_ID,
                "scope": SCOPE,
                "audience": "https://api.openai.com/v1/",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        response.raise_for_status()
        device_data = response.json()
    except Exception as e:
        console.print(f"❌ Failed to get device code: {str(e)}", style="red")
        return False

    device_code = device_data["device_code"]
    user_code = device_data["user_code"]
    verification_uri = device_data["verification_uri_complete"]
    expires_in = device_data["expires_in"]
    interval = device_data["interval"]

    # Step 2: Guide user to login
    console.print("\n[bold blue]🔐 OpenAI 授权登录[/bold blue]")
    console.print(f"\n请在浏览器中打开以下地址进行登录：")
    console.print(f"[link={verification_uri}]{verification_uri}[/link]", style="underline blue")
    console.print(f"\n确认代码：[bold yellow]{user_code}[/bold yellow]")
    console.print(f"\n授权将在 {expires_in // 60} 分钟后过期，请尽快完成登录。")
    console.print("\n等待授权中...", style="dim")

    # Step 3: Poll for token
    start_time = time.time()
    while time.time() - start_time < expires_in:
        time.sleep(interval)
        try:
            token_response = requests.post(
                OPENAI_TOKEN_URL,
                data={
                    "client_id": CLIENT_ID,
                    "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                    "device_code": device_code,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )

            if token_response.status_code == 200:
                token_data = token_response.json()
                access_token = token_data["access_token"]
                refresh_token = token_data.get("refresh_token")
                expires_at = int(time.time()) + token_data["expires_in"]

                # Save tokens
                UserConfig.save_openai_token(access_token, refresh_token, expires_at)
                console.print("✅ 授权成功！你现在可以使用LLM Wiki的所有功能了。", style="green")
                return True
            elif token_response.status_code == 400:
                error_data = token_response.json()
                error = error_data.get("error")
                if error == "authorization_pending":
                    # User hasn't authorized yet, continue polling
                    continue
                elif error == "slow_down":
                    # Increase polling interval
                    interval += 1
                    continue
                elif error == "access_denied":
                    console.print("❌ 授权被用户拒绝。", style="red")
                    return False
                elif error == "expired_token":
                    console.print("❌ 授权已过期，请重新尝试。", style="red")
                    return False
                else:
                    console.print(f"❌ 授权失败：{error}", style="red")
                    return False
            else:
                console.print(f"❌ 授权失败，状态码：{token_response.status_code}", style="red")
                return False
        except Exception as e:
            console.print(f"❌ 轮询授权状态失败：{str(e)}", style="red")
            return False

    console.print("❌ 授权超时，请重新尝试。", style="red")
    return False

def refresh_openai_token() -> bool:
    """
    Refresh OpenAI access token using refresh token.
    Returns True if refresh succeeds, False otherwise.
    """
    config = UserConfig._load()
    refresh_token = config.get("openai", {}).get("refresh_token")
    if not refresh_token:
        console.print("❌ 没有找到刷新令牌，请先运行 `llmwiki login` 进行授权。", style="red")
        return False

    try:
        token_response = requests.post(
            OPENAI_TOKEN_URL,
            data={
                "client_id": CLIENT_ID,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        token_response.raise_for_status()
        token_data = token_response.json()

        access_token = token_data["access_token"]
        new_refresh_token = token_data.get("refresh_token", refresh_token)
        expires_at = int(time.time()) + token_data["expires_in"]

        UserConfig.save_openai_token(access_token, new_refresh_token, expires_at)
        return True
    except Exception as e:
        console.print(f"❌ 刷新令牌失败：{str(e)}", style="red")
        # Clear invalid tokens
        UserConfig.save_openai_token(None, None, None)
        return False

def get_valid_openai_token() -> Optional[str]:
    """
    Get a valid OpenAI access token, automatically refreshing if needed.
    Returns None if no valid token is available.
    """
    config = UserConfig._load()
    openai_config = config.get("openai", {})
    access_token = openai_config.get("access_token")
    expires_at = openai_config.get("expires_at")

    if not access_token:
        return None

    # Check if token is about to expire (within 5 minutes) or already expired
    if expires_at is not None and (expires_at - time.time() < 300 or expires_at < time.time()):
        if refresh_openai_token():
            return UserConfig.get_openai_token()
        return None

    return access_token
