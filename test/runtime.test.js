import assert from 'node:assert/strict';
import test from 'node:test';

import { AuthError } from '../src/errors.js';
import { createServiceNowRuntime } from '../src/runtime.js';

test('runtime caches successful validation for the life of the process', async () => {
  let validationCount = 0;

  const runtime = createServiceNowRuntime({
    configLoader: () => ({ instanceUrl: 'https://example.service-now.com' }),
    authFactory: () => ({ invalidate() {} }),
    clientFactory: () => ({
      async testConnection() {
        validationCount += 1;
      }
    })
  });

  const first = await runtime.execute(async () => 'first');
  const second = await runtime.execute(async () => 'second');

  assert.equal(first, 'first');
  assert.equal(second, 'second');
  assert.equal(validationCount, 1);
});

test('runtime revalidates and retries once after an auth error', async () => {
  let validationCount = 0;
  let clientId = 0;
  let invalidationCount = 0;

  const runtime = createServiceNowRuntime({
    configLoader: () => ({ instanceUrl: 'https://example.service-now.com' }),
    authFactory: () => ({
      invalidate() {
        invalidationCount += 1;
      }
    }),
    clientFactory: () => {
      const id = ++clientId;

      return {
        id,
        async testConnection() {
          validationCount += 1;
        }
      };
    }
  });

  const result = await runtime.execute(async (client) => {
    if (client.id === 1) {
      throw new AuthError('token expired');
    }

    return 'ok';
  });

  assert.equal(result, 'ok');
  assert.equal(validationCount, 2);
  assert.equal(invalidationCount, 1);
});
