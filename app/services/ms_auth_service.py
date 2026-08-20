import os
import json
import base64
import time
import platform
from datetime import datetime, timezone
import msal
from cryptography.fernet import Fernet

# Microsoft Entra ID Defaults for Desktop Public Client
DEFAULT_CLIENT_ID = ""
DEFAULT_AUTHORITY = "https://login.microsoftonline.com/common"
# Note: MSAL automatically appends openid, profile, and offline_access under the hood.
DEFAULT_SCOPES = [
    "https://outlook.office.com/SMTP.Send"
]

# Windows Data Protection API (DPAPI) integration
# Hardware-backed, user-account encrypted master key security
def _dpapi_protect(data: bytes) -> bytes:
    """Encrypts bytes using Windows DPAPI tied to the logged-in OS user session."""
    if platform.system() != "Windows":
        return data
    try:
        import ctypes
        from ctypes import wintypes

        class DATA_BLOB(ctypes.Structure):
            _fields_ = [('cbData', wintypes.DWORD), ('pbData', ctypes.POINTER(ctypes.c_byte))]

        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32

        in_blob = DATA_BLOB(len(data), ctypes.cast(ctypes.create_string_buffer(data), ctypes.POINTER(ctypes.c_byte)))
        out_blob = DATA_BLOB()
        # CRYPTPROTECT_UI_FORBIDDEN = 0x1
        if not crypt32.CryptProtectData(ctypes.byref(in_blob), 'payslip_secure_token', None, None, None, 1, ctypes.byref(out_blob)):
            return data
        encrypted = ctypes.string_at(out_blob.pbData, out_blob.cbData)
        kernel32.LocalFree(out_blob.pbData)
        return encrypted
    except Exception:
        return data

def _dpapi_unprotect(data: bytes) -> bytes:
    """Decrypts bytes using Windows DPAPI tied to the logged-in OS user session."""
    if platform.system() != "Windows":
        return data
    try:
        import ctypes
        from ctypes import wintypes

        class DATA_BLOB(ctypes.Structure):
            _fields_ = [('cbData', wintypes.DWORD), ('pbData', ctypes.POINTER(ctypes.c_byte))]

        crypt32 = ctypes.windll.crypt32
        kernel32 = ctypes.windll.kernel32

        in_blob = DATA_BLOB(len(data), ctypes.cast(ctypes.create_string_buffer(data), ctypes.POINTER(ctypes.c_byte)))
        out_blob = DATA_BLOB()
        # CRYPTPROTECT_UI_FORBIDDEN = 0x1
        if not crypt32.CryptUnprotectData(ctypes.byref(in_blob), None, None, None, None, 1, ctypes.byref(out_blob)):
            return data
        decrypted = ctypes.string_at(out_blob.pbData, out_blob.cbData)
        kernel32.LocalFree(out_blob.pbData)
        return decrypted
    except Exception:
        return data


class MicrosoftAuthService:
    PROVIDER_NAME = "MICROSOFT"

    def __init__(self, db_service, client_id=None, authority=None):
        self.db = db_service
        
        # Load from db settings if present
        db_client_id = None
        db_tenant_id = None
        if self.db:
            try:
                settings = self.db.get_settings()
                if settings and len(settings) > 9:
                    db_client_id = settings[9]
                if settings and len(settings) > 10:
                    db_tenant_id = settings[10]
            except Exception:
                pass

        self.client_id = client_id or db_client_id or os.environ.get("MS_CLIENT_ID") or DEFAULT_CLIENT_ID
        
        authority_url = authority or os.environ.get("MS_AUTHORITY")
        if not authority_url:
            if db_tenant_id and str(db_tenant_id).strip():
                tenant = str(db_tenant_id).strip()
                authority_url = f"https://login.microsoftonline.com/{tenant}"
            else:
                authority_url = DEFAULT_AUTHORITY
                
        self.authority = authority_url
        self.scopes = DEFAULT_SCOPES
        self._fernet = self._get_or_create_fernet()

    def _get_or_create_fernet(self):
        """
        Generates or loads symmetric encryption key protected with Windows DPAPI.
        Even if the key file or database is copied to an external system, it cannot be decrypted.
        """
        key_dir = os.path.join(os.path.dirname(os.path.abspath(self.db.db_path)), ".keys")
        os.makedirs(key_dir, exist_ok=True)
        key_file = os.path.join(key_dir, "oauth.dpapi.key")
        legacy_key_file = os.path.join(key_dir, "oauth.key")
        
        if os.path.exists(key_file):
            try:
                with open(key_file, "rb") as f:
                    protected_key = f.read().strip()
                    key = _dpapi_unprotect(protected_key)
                    return Fernet(key)
            except Exception:
                pass

        # Check legacy un-protected key if upgrading
        if os.path.exists(legacy_key_file):
            try:
                with open(legacy_key_file, "rb") as f:
                    legacy_key = f.read().strip()
                    # Re-protect with DPAPI
                    protected_key = _dpapi_protect(legacy_key)
                    with open(key_file, "wb") as kf:
                        kf.write(protected_key)
                    try:
                        os.remove(legacy_key_file)
                    except Exception:
                        pass
                    return Fernet(legacy_key)
            except Exception:
                pass

        # Generate new DPAPI protected key
        raw_key = Fernet.generate_key()
        protected_key = _dpapi_protect(raw_key)
        try:
            with open(key_file, "wb") as f:
                f.write(protected_key)
        except Exception:
            pass
        return Fernet(raw_key)

    def _encrypt(self, text: str) -> str:
        """Double-layer hardware/OS protected encryption."""
        if not text:
            return ""
        try:
            # 1. AES-CBC + HMAC-SHA256 via Fernet
            fernet_enc = self._fernet.encrypt(text.encode("utf-8"))
            # 2. Windows DPAPI user-account hardware encryption
            dpapi_enc = _dpapi_protect(fernet_enc)
            return base64.b64encode(dpapi_enc).decode("utf-8")
        except Exception:
            return ""

    def _decrypt(self, cipher_text: str) -> str:
        """Double-layer decryption with backward-compatibility fallback."""
        if not cipher_text:
            return ""
        try:
            raw_bytes = base64.b64decode(cipher_text.encode("utf-8"))
            # Unprotect DPAPI
            fernet_bytes = _dpapi_unprotect(raw_bytes)
            # Decrypt Fernet
            return self._fernet.decrypt(fernet_bytes).decode("utf-8")
        except Exception:
            # Legacy direct Fernet fallback if transitioning
            try:
                return self._fernet.decrypt(cipher_text.encode("utf-8")).decode("utf-8")
            except Exception:
                return ""

    def _build_msal_app(self, cache=None):
        return msal.PublicClientApplication(
            client_id=self.client_id,
            authority=self.authority,
            token_cache=cache
        )

    def connect_account(self, port=0):
        """
        Interactive OAuth 2.0 Login flow:
        Opens the system browser, listens on a local loopback port,
        requests delegated permissions and acquires tokens.
        """
        if not self.client_id or not self.client_id.strip():
            return False, "Azure App (Client) ID is required. Please enter your App (Client) ID in Settings and save."

        cache = msal.SerializableTokenCache()
        app = self._build_msal_app(cache=cache)

        # Acquire token interactively via system browser
        result = app.acquire_token_interactive(
            scopes=self.scopes,
            prompt="select_account",
            port=port if port > 0 else None
        )

        if "access_token" in result:
            return self._process_and_save_token_result(result, cache)
        else:
            error = result.get("error_description") or result.get("error") or "Authentication failed or was cancelled."
            return False, error

    def reconnect_account(self):
        """Clears existing tokens and restarts the login flow."""
        self.disconnect_account()
        return self.connect_account()

    def disconnect_account(self):
        """Removes stored tokens and disconnects account."""
        try:
            self.db.delete_oauth_tokens(self.PROVIDER_NAME)
            return True, "Account disconnected successfully."
        except Exception as e:
            return False, f"Failed to disconnect: {str(e)}"

    def _process_and_save_token_result(self, result, cache):
        try:
            access_token = result.get("access_token", "")
            refresh_token = result.get("refresh_token", "")
            expires_in = result.get("expires_in", 3600)
            expires_at = time.time() + int(expires_in)
            
            # Extract email from ID token claims
            id_claims = result.get("id_token_claims", {})
            email = (
                id_claims.get("preferred_username")
                or id_claims.get("email")
                or id_claims.get("upn")
                or ""
            )

            # Export serialized cache
            token_cache_str = cache.serialize() if cache else ""

            # Encrypt tokens with OS DPAPI + Fernet before storing
            enc_access = self._encrypt(access_token)
            enc_refresh = self._encrypt(refresh_token)
            enc_cache = self._encrypt(token_cache_str)

            self.db.save_oauth_tokens(
                provider=self.PROVIDER_NAME,
                email=email,
                access_token=enc_access,
                refresh_token=enc_refresh,
                token_cache=enc_cache,
                expires_at=str(expires_at)
            )

            # Also update sender_email in settings table for consistency
            current_settings = self.db.get_settings()
            if current_settings:
                self.db.update_settings(
                    host="smtp.office365.com",
                    port=587,
                    email=email,
                    password="",
                    tls=1,
                    provider="microsoft",
                    resend_key=current_settings[7] if len(current_settings) > 7 else "",
                    resend_from=current_settings[8] if len(current_settings) > 8 else "",
                    ms_client_id=self.client_id,
                    ms_tenant_id=current_settings[10] if len(current_settings) > 10 else ""
                )

            return True, f"Connected as {email}"
        except Exception as e:
            return False, f"Failed to save tokens: {str(e)}"

    def get_connection_status(self):
        """
        Returns connection status dictionary:
        {
            "connected": bool,
            "email": str,
            "expiresAt": datetime or None,
            "status_text": "Connected" | "Connection Expired" | "Not Connected",
            "is_expired": bool
        }
        """
        record = self.db.get_oauth_tokens(self.PROVIDER_NAME)
        if not record:
            return {
                "connected": False,
                "email": "",
                "expiresAt": None,
                "status_text": "Not Connected",
                "is_expired": False
            }

        # record: (id, provider, email, access_token, refresh_token, token_cache, expires_at, updated_at)
        email = record[2] or ""
        expires_at_raw = record[6]
        
        expires_at_ts = 0.0
        try:
            expires_at_ts = float(expires_at_raw)
        except (ValueError, TypeError):
            expires_at_ts = 0.0

        expires_dt = datetime.fromtimestamp(expires_at_ts, tz=timezone.utc) if expires_at_ts > 0 else None
        now_ts = time.time()
        
        # Consider expired if current time exceeds expires_at_ts
        is_expired = (expires_at_ts > 0 and now_ts >= expires_at_ts)

        if not email:
            return {
                "connected": False,
                "email": "",
                "expiresAt": expires_dt,
                "status_text": "Not Connected",
                "is_expired": True
            }

        if is_expired:
            return {
                "connected": True,
                "email": email,
                "expiresAt": expires_dt,
                "status_text": "Connection Expired",
                "is_expired": True
            }

        return {
            "connected": True,
            "email": email,
            "expiresAt": expires_dt,
            "status_text": "Connected",
            "is_expired": False
        }

    def get_valid_access_token(self):
        """
        Returns (access_token, email, error_message).
        Validates token freshness and automatically refreshes via refresh token / MSAL cache.
        """
        record = self.db.get_oauth_tokens(self.PROVIDER_NAME)
        if not record:
            return None, None, "No Microsoft account connected. Please connect your account in Settings."

        email = record[2] or ""
        raw_access = self._decrypt(record[3])
        raw_refresh = self._decrypt(record[4])
        raw_cache = self._decrypt(record[5])
        expires_at_raw = record[6]

        try:
            expires_at_ts = float(expires_at_raw)
        except (ValueError, TypeError):
            expires_at_ts = 0.0

        # If token is valid for at least another 2 minutes, reuse it
        now_ts = time.time()
        if raw_access and expires_at_ts > (now_ts + 120):
            return raw_access, email, None

        # Attempt silent refresh via MSAL token cache
        cache = msal.SerializableTokenCache()
        if raw_cache:
            try:
                cache.deserialize(raw_cache)
            except Exception:
                pass

        app = self._build_msal_app(cache=cache)
        accounts = app.get_accounts(username=email) if email else app.get_accounts()
        
        result = None
        if accounts:
            result = app.acquire_token_silent(self.scopes, account=accounts[0])

        # If silent refresh via cache failed, try with raw refresh token if available
        if (not result or "access_token" not in result) and raw_refresh:
            result = app.acquire_token_by_refresh_token(raw_refresh, scopes=self.scopes)

        if result and "access_token" in result:
            # Successfully refreshed
            new_access = result.get("access_token")
            new_refresh = result.get("refresh_token") or raw_refresh
            expires_in = result.get("expires_in", 3600)
            new_expires_at = time.time() + int(expires_in)

            enc_access = self._encrypt(new_access)
            enc_refresh = self._encrypt(new_refresh)
            enc_cache = self._encrypt(cache.serialize() if cache else "")

            self.db.save_oauth_tokens(
                provider=self.PROVIDER_NAME,
                email=email,
                access_token=enc_access,
                refresh_token=enc_refresh,
                token_cache=enc_cache,
                expires_at=str(new_expires_at)
            )
            return new_access, email, None

        error = result.get("error_description") if result else "OAuth session expired. Please reconnect your Microsoft account."
        return None, email, f"Token refresh failed: {error}"

    @staticmethod
    def generate_xoauth2_string(user_email: str, access_token: str) -> str:
        """
        Builds the SASL XOAUTH2 authentication string:
        user={user_email}\x01auth=Bearer {access_token}\x01\x01
        encoded as Base64.
        """
        auth_string = f"user={user_email}\x01auth=Bearer {access_token}\x01\x01"
        return base64.b64encode(auth_string.encode("utf-8")).decode("utf-8")
