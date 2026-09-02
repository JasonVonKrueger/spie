import { AuthError } from './errors.js';

const TOKEN_REFRESH_BUFFER_MS = 60_000;

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
  constructor(config, fetchImpl = fetch) {
    this.config = config;
    this.fetchImpl = fetchImpl;
    this.tokenState = null;
  }

  invalidate() {
    this.tokenState = null;
  }

  async getAccessToken(options = {}) {
    const forceRefresh = options.forceRefresh ?? false;

    if (!forceRefresh && this.#hasUsableAccessToken()) {
      return this.tokenState.accessToken;
    }

    if (this.tokenState?.refreshToken) {
      return this.#requestAndStoreToken('refresh_token', {
        refresh_token: this.tokenState.refreshToken
      });
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
      client_secret: this.config.clientSecret,
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
