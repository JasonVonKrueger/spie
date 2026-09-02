import { ServiceNowOAuthClient } from './auth.js';
import { loadServiceNowConfig } from './config.js';
import { AuthError } from './errors.js';
import { ServiceNowClient } from './servicenow-client.js';

export function createServiceNowRuntime(options = {}) {
  const configLoader = options.configLoader ?? (() => loadServiceNowConfig());
  const authFactory = options.authFactory ?? ((config) => new ServiceNowOAuthClient(config));
  const clientFactory =
    options.clientFactory ?? ((config, authClient) => new ServiceNowClient(config, authClient));

  let cachedContext = null;
  let validationPromise = null;

  async function validate({ force = false } = {}) {
    if (cachedContext && !force) {
      return cachedContext;
    }

    if (validationPromise && !force) {
      return validationPromise;
    }

    validationPromise = (async () => {
      const config = configLoader();
      const authClient = authFactory(config);
      const client = clientFactory(config, authClient);
      await client.testConnection();

      cachedContext = {
        config,
        authClient,
        client
      };

      return cachedContext;
    })();

    try {
      return await validationPromise;
    } catch (error) {
      cachedContext = null;
      throw error;
    } finally {
      validationPromise = null;
    }
  }

  async function execute(operation) {
    try {
      const { client } = await validate();
      return await operation(client);
    } catch (error) {
      if (!(error instanceof AuthError)) {
        throw error;
      }

      cachedContext?.authClient?.invalidate?.();
      cachedContext = null;

      const { client } = await validate({ force: true });
      return await operation(client);
    }
  }

  return {
    execute,
    validate
  };
}
