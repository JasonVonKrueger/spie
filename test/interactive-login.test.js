import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import fs from 'node:fs';
import net from 'node:net';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';

import { ServiceNowOAuthClient } from '../src/auth.js';
import { loadServiceNowConfig } from '../src/config.js';
import { AuthError, ServiceNowApiError, SignInRequiredError, toToolErrorResult } from '../src/errors.js';
import { createPkcePair, startBrowserLogin } from '../src/interactive-login.js';
import { createServiceNowRuntime } from '../src/runtime.js';
import { ServiceNowClient } from '../src/servicenow-client.js';

async function freePort() {
  return new Promise((resolve) => {
    const server = net.createServer();
    server.listen(0, '127.0.0.1', () => {
      const { port } = server.address();
      server.close(() => resolve(port));
    });
  });
}

function interactiveConfig(overrides = {}) {
  return {
    instanceUrl: 'https://example.service-now.com',
    clientId: 'client-id',
    clientSecret: undefined,
    grantType: 'interactive',
    redirectUri: 'http://127.0.0.1:8765/callback',
    ...overrides
  };
}

function tokenResponse(body) {
  return { ok: true, status: 200, json: async () => body };
}

test('createPkcePair produces an S256 challenge for the verifier', () => {
  const { verifier, challenge } = createPkcePair();
  assert.equal(challenge, crypto.createHash('sha256').update(verifier).digest('base64url'));
});

test('startBrowserLogin resolves the code from the loopback redirect and ignores requests with a bad state', async () => {
  const port = await freePort();
  let opened;
  const login = await startBrowserLogin(interactiveConfig({ redirectUri: `http://127.0.0.1:${port}/callback` }), {
    openBrowser: (url) => {
      opened = new URL(url);
    }
  });

  assert.equal(opened.origin, 'https://example.service-now.com');
  assert.equal(opened.pathname, '/oauth_auth.do');
  assert.equal(opened.searchParams.get('code_challenge_method'), 'S256');
  assert.equal(opened.searchParams.get('redirect_uri'), `http://127.0.0.1:${port}/callback`);

  const bad = await fetch(`http://127.0.0.1:${port}/callback?code=evil&state=wrong`);
  assert.equal(bad.status, 400);

  const state = opened.searchParams.get('state');
  const good = await fetch(`http://127.0.0.1:${port}/callback?code=abc123&state=${state}`);
  assert.equal(good.status, 200);
  assert.deepEqual(await login.codePromise, { code: 'abc123' });
});

test('startBrowserLogin rejects when the user denies access', async () => {
  const port = await freePort();
  let opened;
  const login = await startBrowserLogin(interactiveConfig({ redirectUri: `http://127.0.0.1:${port}/callback` }), {
    openBrowser: (url) => {
      opened = new URL(url);
    }
  });

  const rejection = assert.rejects(login.codePromise, SignInRequiredError);
  await fetch(`http://127.0.0.1:${port}/callback?error=access_denied&state=${opened.searchParams.get('state')}`);
  await rejection;
});

test('startBrowserLogin explains when the redirect port is already in use', async () => {
  const port = await freePort();
  const blocker = net.createServer();
  await new Promise((resolve) => blocker.listen(port, '127.0.0.1', resolve));

  try {
    await assert.rejects(
      startBrowserLogin(interactiveConfig({ redirectUri: `http://127.0.0.1:${port}/callback` }), {
        openBrowser() {}
      }),
      /already in use/
    );
  } finally {
    blocker.close();
  }
});

test('interactive auth exchanges the code with PKCE, without a client secret, and keeps tokens in memory', async () => {
  const requests = [];
  const auth = new ServiceNowOAuthClient(
    interactiveConfig(),
    async (url, init) => {
      requests.push(new URLSearchParams(init.body));
      return tokenResponse({ access_token: 'tok', refresh_token: 'ref', expires_in: 3600 });
    },
    {
      startLogin: async () => ({
        authorizeUrl: 'https://example.service-now.com/oauth_auth.do?x=1',
        verifier: 'verifier-1',
        codePromise: Promise.resolve({ code: 'code-1' })
      })
    }
  );

  assert.equal(await auth.getAccessToken(), 'tok');
  assert.equal(await auth.getAccessToken(), 'tok');

  assert.equal(requests.length, 1);
  assert.equal(requests[0].get('grant_type'), 'authorization_code');
  assert.equal(requests[0].get('code'), 'code-1');
  assert.equal(requests[0].get('code_verifier'), 'verifier-1');
  assert.equal(requests[0].get('redirect_uri'), 'http://127.0.0.1:8765/callback');
  assert.equal(requests[0].has('client_secret'), false);
});

test('interactive auth reports a pending sign-in with the URL, then finishes it on the next call', async () => {
  let resolveCode;
  let startCount = 0;
  const auth = new ServiceNowOAuthClient(
    interactiveConfig(),
    async () => tokenResponse({ access_token: 'tok', expires_in: 3600 }),
    {
      loginWaitMs: 10,
      startLogin: async () => {
        startCount += 1;
        return {
          authorizeUrl: 'https://example.service-now.com/oauth_auth.do?pending=1',
          verifier: 'v',
          codePromise: new Promise((resolve) => {
            resolveCode = resolve;
          })
        };
      }
    }
  );

  await assert.rejects(auth.getAccessToken(), (error) => {
    assert.ok(error instanceof SignInRequiredError);
    assert.match(error.message, /oauth_auth\.do\?pending=1/);
    return true;
  });

  resolveCode({ code: 'late-code' });
  assert.equal(await auth.getAccessToken(), 'tok');
  assert.equal(startCount, 1);
});

test('interactive auth surfaces a sign-in failure that happened while nobody was waiting', async () => {
  let rejectCode;
  let startCount = 0;
  const auth = new ServiceNowOAuthClient(interactiveConfig(), async () => tokenResponse({}), {
    loginWaitMs: 10,
    startLogin: async () => {
      startCount += 1;
      return {
        authorizeUrl: 'https://example.service-now.com/oauth_auth.do',
        verifier: 'v',
        codePromise: new Promise((_, reject) => {
          rejectCode = reject;
        })
      };
    }
  });

  await assert.rejects(auth.getAccessToken(), /Sign in to ServiceNow/);
  rejectCode(new SignInRequiredError('ServiceNow sign-in was not completed (access_denied).'));
  await new Promise((resolve) => setTimeout(resolve, 5));

  await assert.rejects(auth.getAccessToken(), /access_denied/);
  assert.equal(startCount, 1);
});

test('interactive auth keeps the refresh token after invalidate and drops it when the server rejects it', async () => {
  const grants = [];
  let refreshShouldFail = false;
  const auth = new ServiceNowOAuthClient(
    interactiveConfig(),
    async (url, init) => {
      const body = new URLSearchParams(init.body);
      grants.push(body.get('grant_type'));
      if (body.get('grant_type') === 'refresh_token' && refreshShouldFail) {
        return { ok: false, status: 401, json: async () => ({ error_description: 'invalid refresh token' }) };
      }
      return tokenResponse({ access_token: `tok-${grants.length}`, refresh_token: 'ref', expires_in: 3600 });
    },
    {
      startLogin: async () => ({
        authorizeUrl: 'u',
        verifier: 'v',
        codePromise: Promise.resolve({ code: 'c' })
      })
    }
  );

  await auth.getAccessToken();
  auth.invalidate();
  await auth.getAccessToken();
  assert.deepEqual(grants, ['authorization_code', 'refresh_token']);

  auth.invalidate();
  refreshShouldFail = true;
  await assert.rejects(auth.getAccessToken(), AuthError);
  refreshShouldFail = false;
  await auth.getAccessToken();
  assert.deepEqual(grants, ['authorization_code', 'refresh_token', 'refresh_token', 'authorization_code']);
});

test('runtime does not retry or re-prompt when sign-in is pending', async () => {
  let validationCount = 0;
  const runtime = createServiceNowRuntime({
    configLoader: () => ({}),
    authFactory: () => ({ invalidate() {} }),
    clientFactory: () => ({
      async testConnection() {
        validationCount += 1;
        throw new SignInRequiredError('Sign in to ServiceNow to continue.');
      }
    })
  });

  await assert.rejects(runtime.execute(async () => 'never'), SignInRequiredError);
  assert.equal(validationCount, 1);
});

test('toToolErrorResult shows the sign-in message to the user', () => {
  const result = toToolErrorResult(new SignInRequiredError('Sign in to ServiceNow to continue.'));
  assert.equal(result.isError, true);
  assert.equal(result.content[0].text, 'Sign in to ServiceNow to continue.');
});

test('testConnection tolerates 403 for interactive users but not for other grants', async () => {
  const forbidden = async () => ({
    ok: false,
    status: 403,
    headers: { get: () => 'application/json' },
    json: async () => ({ error: { message: 'denied' } })
  });
  const auth = { getAccessToken: async () => 'tok' };

  await new ServiceNowClient(interactiveConfig(), auth, forbidden).testConnection();

  await assert.rejects(
    new ServiceNowClient(
      { instanceUrl: 'https://example.service-now.com', grantType: 'client_credentials' },
      auth,
      forbidden
    ).testConnection(),
    ServiceNowApiError
  );
});

test('config: interactive grant needs no secret, defaults the redirect URI, and requires a loopback redirect', () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'spie-config-'));
  const envPath = path.join(dir, '.env');
  const base = [
    'SERVICENOW_INSTANCE_URL=https://example.service-now.com',
    'SERVICENOW_CLIENT_ID=abc',
    'SERVICENOW_OAUTH_GRANT_TYPE=interactive'
  ];

  fs.writeFileSync(envPath, base.join('\n'));
  const config = loadServiceNowConfig({ envPath });
  assert.equal(config.clientSecret, undefined);
  assert.equal(config.redirectUri, 'http://127.0.0.1:8765/callback');

  fs.writeFileSync(envPath, [...base, 'SERVICENOW_REDIRECT_URI=https://evil.example.com/callback'].join('\n'));
  assert.throws(() => loadServiceNowConfig({ envPath }), /loopback/);

  fs.writeFileSync(envPath, [...base, 'SERVICENOW_REDIRECT_URI=http://localhost:9000/callback'].join('\n'));
  assert.equal(loadServiceNowConfig({ envPath }).redirectUri, 'http://localhost:9000/callback');
});
