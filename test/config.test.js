import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';

import { ConfigError } from '../src/errors.js';
import { loadServiceNowConfig } from '../src/config.js';

async function makeTempDir() {
  return fs.mkdtemp(path.join(os.tmpdir(), 'servicenow-mcp-config-'));
}

test('loadServiceNowConfig reports a missing .env file', async () => {
  const tempDir = await makeTempDir();
  const envPath = path.join(tempDir, '.env');

  assert.throws(
    () => loadServiceNowConfig({ envPath }),
    (error) =>
      error instanceof ConfigError &&
      error.message.includes('Missing .env file') &&
      error.missingVariables.includes('.env')
  );
});

test('loadServiceNowConfig reports exactly which password grant variables are missing', async () => {
  const tempDir = await makeTempDir();
  const envPath = path.join(tempDir, '.env');

  await fs.writeFile(
    envPath,
    [
      'SERVICENOW_INSTANCE_URL=https://example.service-now.com',
      'SERVICENOW_CLIENT_ID=test-client',
      'SERVICENOW_CLIENT_SECRET=test-secret',
      'SERVICENOW_OAUTH_GRANT_TYPE=password'
    ].join('\n')
  );

  assert.throws(
    () => loadServiceNowConfig({ envPath }),
    (error) =>
      error instanceof ConfigError &&
      error.missingVariables.length === 2 &&
      error.missingVariables.includes('SERVICENOW_USERNAME') &&
      error.missingVariables.includes('SERVICENOW_PASSWORD')
  );
});

test('loadServiceNowConfig returns normalized config for client credentials', async () => {
  const tempDir = await makeTempDir();
  const envPath = path.join(tempDir, '.env');

  await fs.writeFile(
    envPath,
    [
      'SERVICENOW_INSTANCE_URL=https://example.service-now.com/',
      'SERVICENOW_CLIENT_ID=test-client',
      'SERVICENOW_CLIENT_SECRET=test-secret',
      'SERVICENOW_OAUTH_GRANT_TYPE=client_credentials'
    ].join('\n')
  );

  const config = loadServiceNowConfig({ envPath });

  assert.equal(config.instanceUrl, 'https://example.service-now.com');
  assert.equal(config.grantType, 'client_credentials');
  assert.equal(config.clientId, 'test-client');
});
