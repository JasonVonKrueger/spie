import { AuthError, SignInRequiredError } from './errors.js';
import { startBrowserLogin } from './interactive-login.js';

const TOKEN_REFRESH_BUFFER_MS = 60_000;
// Stay under typical MCP client tool-call timeouts; a still-pending sign-in is picked up on the next call.
const DEFAULT_LOGIN_WAIT_MS = 45_000;

function getOAuthErrorMessage(responseBody, status) {
  if (responseBody && typeof responseBody === 'object') {
    const message = responseBody.error_description || responseBody.error || responseBody.message;
    if (typeof message === 'string' && message.trim()) {
      return message.trim();
    }
  }

  return `ServiceNow OAuth token request failed with status ${status}.`;
}

export class ServiceNowOAuthClient {
  constructor(config, fetchImpl = fetch, options = {}) {
    this.config = config;
    this.fetchImpl = fetchImpl;
    this.tokenState = null;
    this.startLogin = options.startLogin ?? ((loginConfig) => startBrowserLogin(loginConfig));
    this.loginWaitMs = options.loginWaitMs ?? DEFAULT_LOGIN_WAIT_MS;
    this.pendingLogin = null;
    this.failedLogin = null;
  }

  invalidate() {
    // A signed-in user's refresh token survives a 401 so they are not sent back to the browser needlessly.
    const refreshToken = this.config.grantType === 'interactive' ? this.tokenState?.refreshToken : undefined;
    this.tokenState = refreshToken ? { refreshToken } : null;
  }

  async getAccessToken(options = {}) {
    const forceRefresh = options.forceRefresh ?? false;

    if (!forceRefresh && this.#hasUsableAccessToken()) {
      return this.tokenState.accessToken;
    }

    if (this.tokenState?.refreshToken) {
      try {
        return await this.#requestAndStoreToken('refresh_token', {
          refresh_token: this.tokenState.refreshToken
        });
      } catch (error) {
        // The server rejected the refresh token: the next attempt must sign in again.
        if (this.config.grantType === 'interactive' && error instanceof AuthError && error.status) {
          this.tokenState = null;
        }
        throw error;
      }
    }

    if (this.config.grantType === 'interactive') {
      return this.#signInThroughBrowser();
    }

    if (this.config.grantType === 'client_credentials') {
      return this.#requestAndStoreToken('client_credentials');
    }

    if (this.config.grantType === 'password') {
      return this.#requestAndStoreToken('password', {
        username: this.config.username,
        password: this.config.password
      });
    }

    if (this.config.grantType === 'authorization_code') {
      if (this.config.refreshToken) {
        return this.#requestAndStoreToken('refresh_token', {
          refresh_token: this.config.refreshToken
        });
      }

      return this.#requestAndStoreToken('authorization_code', {
        code: this.config.authorizationCode,
        redirect_uri: this.config.redirectUri
      });
    }

    if (this.config.grantType === 'refresh_token') {
      return this.#requestAndStoreToken('refresh_token', {
        refresh_token: this.config.refreshToken
      });
    }

    throw new AuthError(`Unsupported OAuth grant type: ${this.config.grantType}.`);
  }

  async #signInThroughBrowser() {
    if (this.failedLogin) {
      const error = this.failedLogin;
      this.failedLogin = null;
      throw error;
    }

    if (!this.pendingLogin) {
      const login = await this.startLogin(this.config);
      const entry = { url: login.authorizeUrl, promise: null };

      entry.promise = login.codePromise
        .then(({ code }) =>
          this.#requestAndStoreToken('authorization_code', {
            code,
            redirect_uri: this.config.redirectUri,
            code_verifier: login.verifier
          })
        )
        .finally(() => {
          this.pendingLogin = null;
        });

      // If nobody is waiting when it fails (for example the user denied access after the tool call
      // returned), keep the error for the next call instead of leaving an unhandled rejection.
      entry.promise.catch((error) => {
        this.failedLogin = error;
      });

      this.pendingLogin = entry;
    }

    const { url, promise } = this.pendingLogin;
    let timer;
    const timedOut = new Promise((resolve) => {
      timer = setTimeout(() => resolve(null), this.loginWaitMs);
    });

    try {
      const token = await Promise.race([promise, timedOut]);

      if (token === null) {
        throw new SignInRequiredError(
          `Sign in to ServiceNow to continue. A browser window should have opened; if not, open this URL: ${url} . After signing in, run the request again.`
        );
      }

      return token;
    } finally {
      clearTimeout(timer);
      // The caller received this failure directly, so it should not be replayed on the next call.
      if (this.failedLogin && !this.pendingLogin) {
        this.failedLogin = null;
      }
    }
  }

  #hasUsableAccessToken() {
    return Boolean(
      this.tokenState?.accessToken &&
        this.tokenState.expiresAt &&
        Date.now() + TOKEN_REFRESH_BUFFER_MS < this.tokenState.expiresAt
    );
  }

  async #requestAndStoreToken(grantType, extraFields = {}) {
    const body = new URLSearchParams({
      grant_type: grantType,
      client_id: this.config.clientId,
      ...(this.config.clientSecret ? { client_secret: this.config.clientSecret } : {}),
      ...Object.fromEntries(
        Object.entries(extraFields).filter(([, value]) => value !== undefined && value !== '')
      )
    });

    const tokenUrl = new URL('/oauth_token.do', this.config.instanceUrl);
    let response;

    try {
      response = await this.fetchImpl(tokenUrl, {
        method: 'POST',
        headers: {
          Accept: 'application/json',
          'Content-Type': 'application/x-www-form-urlencoded'
        },
        body: body.toString()
      });
    } catch (error) {
      throw new AuthError(`Unable to reach ServiceNow token endpoint. ${error.message}`);
    }

    let responseBody;
    try {
      responseBody = await response.json();
    } catch {
      responseBody = null;
    }

    if (!response.ok) {
      throw new AuthError(getOAuthErrorMessage(responseBody, response.status), {
        status: response.status
      });
    }

    if (!responseBody?.access_token) {
      throw new AuthError('ServiceNow OAuth response did not include an access_token.');
    }

    const expiresInSeconds = Number(responseBody.expires_in || 3600);

    this.tokenState = {
      accessToken: responseBody.access_token,
      refreshToken: responseBody.refresh_token || extraFields.refresh_token || this.config.refreshToken,
      expiresAt: Date.now() + Math.max(expiresInSeconds, 0) * 1000
    };

    return this.tokenState.accessToken;
  }
}
