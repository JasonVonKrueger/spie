import crypto from 'node:crypto';
import http from 'node:http';
import { spawn } from 'node:child_process';

import { SignInRequiredError } from './errors.js';

export const DEFAULT_REDIRECT_URI = 'http://127.0.0.1:8765/callback';

const LOGIN_TIMEOUT_MS = 5 * 60_000;

export function createPkcePair(randomBytes = crypto.randomBytes) {
  const verifier = randomBytes(32).toString('base64url');
  const challenge = crypto.createHash('sha256').update(verifier).digest('base64url');
  return { verifier, challenge };
}

export function buildAuthorizeUrl(config, { state, challenge }) {
  const url = new URL('/oauth_auth.do', config.instanceUrl);
  url.search = new URLSearchParams({
    response_type: 'code',
    client_id: config.clientId,
    redirect_uri: config.redirectUri,
    state,
    code_challenge: challenge,
    code_challenge_method: 'S256'
  }).toString();
  return url.toString();
}

// Best effort: the sign-in URL is also returned in the tool message if the browser does not open.
export function openInBrowser(url) {
  const [command, args] =
    process.platform === 'darwin'
      ? ['open', [url]]
      : process.platform === 'win32'
        ? ['rundll32', ['url.dll,FileProtocolHandler', url]]
        : ['xdg-open', [url]];

  try {
    const child = spawn(command, args, { stdio: 'ignore', detached: true });
    child.on('error', () => {});
    child.unref();
  } catch {
    // Ignore; the user can open the URL manually.
  }
}

function respond(res, status, title, message) {
  res.writeHead(status, { 'Content-Type': 'text/html; charset=utf-8', Connection: 'close' });
  res.end(`<!doctype html><title>${title}</title><body style="font-family:sans-serif;margin:3rem"><h2>${title}</h2><p>${message}</p></body>`);
}

/**
 * Starts the browser half of an OAuth authorization code + PKCE sign-in: listens on the loopback
 * redirect URI, opens the ServiceNow login page, and resolves `codePromise` with the returned code.
 * Nothing is written to disk; the caller exchanges the code for tokens held in memory.
 */
export async function startBrowserLogin(config, options = {}) {
  const {
    openBrowser = openInBrowser,
    timeoutMs = LOGIN_TIMEOUT_MS,
    randomBytes = crypto.randomBytes
  } = options;

  const redirect = new URL(config.redirectUri);
  const state = randomBytes(16).toString('hex');
  const { verifier, challenge } = createPkcePair(randomBytes);

  let resolveCode;
  let rejectCode;
  const codePromise = new Promise((resolve, reject) => {
    resolveCode = resolve;
    rejectCode = reject;
  });

  let timer;
  const server = http.createServer((req, res) => {
    const url = new URL(req.url, redirect);

    if (req.method !== 'GET' || url.pathname !== redirect.pathname) {
      res.writeHead(404, { Connection: 'close' }).end();
      return;
    }

    // A stray or stale request must not be able to end the pending sign-in.
    if (url.searchParams.get('state') !== state) {
      respond(res, 400, 'Sign-in failed', 'This sign-in link is not valid. Return to Claude and try again.');
      return;
    }

    const error = url.searchParams.get('error');
    const code = url.searchParams.get('code');

    if (error || !code) {
      respond(res, 400, 'Sign-in was not completed', 'You can close this tab and try again from Claude.');
      finish(() => rejectCode(new SignInRequiredError(`ServiceNow sign-in was not completed${error ? ` (${error})` : ''}. Run the request again to sign in again.`)));
      return;
    }

    respond(res, 200, 'Signed in to ServiceNow', 'You can close this tab and return to Claude.');
    finish(() => resolveCode({ code }));
  });

  function finish(settle) {
    clearTimeout(timer);
    server.close();
    server.closeAllConnections?.();
    settle();
  }

  try {
    await new Promise((resolve, reject) => {
      server.once('error', reject);
      server.listen(Number(redirect.port), redirect.hostname.replace(/^\[|\]$/g, ''), () => {
        server.off('error', reject);
        resolve();
      });
    });
  } catch (error) {
    throw new SignInRequiredError(
      error.code === 'EADDRINUSE'
        ? `Cannot start ServiceNow sign-in: port ${redirect.port} is already in use. Close whatever is using it, or set SERVICENOW_REDIRECT_URI to a different loopback port (and register the same URI on the ServiceNow OAuth application).`
        : `Cannot start the local sign-in listener at ${config.redirectUri}. ${error.message}`
    );
  }

  timer = setTimeout(
    () =>
      finish(() =>
        rejectCode(new SignInRequiredError('ServiceNow sign-in timed out. Run the request again to sign in again.'))
      ),
    timeoutMs
  );
  timer.unref();

  const authorizeUrl = buildAuthorizeUrl(config, { state, challenge });
  openBrowser(authorizeUrl);

  return { authorizeUrl, verifier, codePromise };
}
